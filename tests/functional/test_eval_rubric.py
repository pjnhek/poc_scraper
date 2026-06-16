from __future__ import annotations

import pytest

from evals.rubric import EvalRubric, _compute_groundedness
from src.clients.nvidia_client import LLMResponse
from src.models import Citation, Contact, Justification, OutreachHook


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[str] = []

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens=None
    ) -> LLMResponse:
        self.calls.append(system)
        return LLMResponse(text=self.text)


def _hook(paragraph: str = "p [1]") -> OutreachHook:
    return OutreachHook(
        contact=Contact(role_title="VP CX", rationale="r"),
        paragraph=paragraph,
        cited_indices=(1,),
    )


def _justification(index: int = 1) -> Justification:
    return Justification(
        index=index,
        summary=f"summary {index}",
        citation=Citation.make(url=f"https://x.com/{index}", source="exa"),
    )


@pytest.mark.asyncio
async def test_groundedness_derived_from_claims_array() -> None:
    # 3 claims, 2 cited, 1 uncited: (2 / max(3,3)) * 5 = 3.33, rounded = 3.3
    llm = FakeAnthropic(
        text=(
            '{"claims":['
            '{"text":"claim 1","supported_by":1},'
            '{"text":"claim 2","supported_by":2},'
            '{"text":"claim 3","supported_by":"uncited"}'
            '],"icp_relevance":4,"personalization":4,"notes":"ok"}'
        )
    )
    score = await EvalRubric(llm).evaluate_hook(
        _hook(), "x.com", justifications=(_justification(1), _justification(2))
    )
    assert score.groundedness == 3.3
    assert score.icp_relevance == 4
    assert score.personalization == 4


@pytest.mark.asyncio
async def test_short_hook_penalized_by_min_total_floor() -> None:
    # 1 claim, 1 cited: (1 / max(1, 3)) * 5 = 1.67, rounded = 1.7
    llm = FakeAnthropic(
        text=(
            '{"claims":[{"text":"single claim","supported_by":1}],'
            '"icp_relevance":4,"personalization":4,"notes":"ok"}'
        )
    )
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com", (_justification(),))
    assert score.groundedness == 1.7


@pytest.mark.asyncio
async def test_all_uncited_yields_floor() -> None:
    llm = FakeAnthropic(
        text=(
            '{"claims":['
            '{"text":"a","supported_by":"uncited"},'
            '{"text":"b","supported_by":"uncited"},'
            '{"text":"c","supported_by":"uncited"}'
            '],"icp_relevance":3,"personalization":3,"notes":"hallucinated"}'
        )
    )
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com", (_justification(),))
    assert score.groundedness == 1.0
    assert score.is_flagged is True


@pytest.mark.asyncio
async def test_all_cited_caps_at_five() -> None:
    # 4 claims, all cited: (4 / max(4, 3)) * 5 = 5.0
    llm = FakeAnthropic(
        text=(
            '{"claims":['
            '{"text":"a","supported_by":1},'
            '{"text":"b","supported_by":1},'
            '{"text":"c","supported_by":1},'
            '{"text":"d","supported_by":1}'
            '],"icp_relevance":5,"personalization":5,"notes":"solid"}'
        )
    )
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com", (_justification(),))
    assert score.groundedness == 5.0


@pytest.mark.asyncio
async def test_unparseable_returns_floor_with_notes() -> None:
    llm = FakeAnthropic(text="not json")
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert score.groundedness == 1
    assert score.notes is not None and "unparseable" in score.notes


@pytest.mark.asyncio
async def test_judge_prompt_includes_buyer_description() -> None:
    llm = FakeAnthropic(text='{"claims":[],"icp_relevance":3,"personalization":3,"notes":"none"}')
    await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert "Buyer description" in llm.calls[0]


def test_compute_groundedness_pure_function() -> None:
    # No claims at all -> floor of 1.0
    assert _compute_groundedness([], {1, 2}) == 1.0
    # 2 of 4 cited -> (2 / 4) * 5 = 2.5
    claims = [
        {"text": "a", "supported_by": 1},
        {"text": "b", "supported_by": 2},
        {"text": "c", "supported_by": "uncited"},
        {"text": "d", "supported_by": "uncited"},
    ]
    assert _compute_groundedness(claims, {1, 2}) == 2.5


def test_compute_groundedness_rejects_invalid_supported_by() -> None:
    # supported_by must be a real 1-based index. 0, out-of-range, and bool
    # (an int subclass) must NOT count as grounded, so they cannot inflate
    # the headline metric. Only the genuine index-1 claim counts: 1/3 -> 1.7.
    claims = [
        {"text": "valid", "supported_by": 1},
        {"text": "zero", "supported_by": 0},
        {"text": "out-of-range", "supported_by": 99},
        {"text": "bool", "supported_by": True},
    ]
    assert _compute_groundedness(claims, {1, 2}) == round((1 / 4) * 5, 1)
