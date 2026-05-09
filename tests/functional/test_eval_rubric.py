from __future__ import annotations

import pytest

from evals.rubric import EvalRubric
from src.clients.anthropic_client import CachedSynthesis
from src.models import Citation, Contact, OutreachHook


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text

    async def synthesize(
        self, system: str, cached_context: str, user_prompt: str, max_tokens=None
    ) -> CachedSynthesis:
        return CachedSynthesis(text=self.text, cache_read_tokens=0, cache_creation_tokens=0)


def _hook(paragraph: str = "p") -> OutreachHook:
    return OutreachHook(
        contact=Contact(role_title="VP CX", rationale="r"),
        paragraph=paragraph,
        citations=(Citation.make(url="https://x.com/a", source="exa"),),
    )


@pytest.mark.asyncio
async def test_happy_path_eval() -> None:
    llm = FakeAnthropic(
        text='{"groundedness":9,"icp_relevance":8,"personalization":7,"notes":"solid"}'
    )
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert score.groundedness == 9
    assert score.icp_relevance == 8
    assert score.personalization == 7
    assert score.notes == "solid"
    assert score.is_flagged is False


@pytest.mark.asyncio
async def test_flags_low_groundedness() -> None:
    llm = FakeAnthropic(
        text='{"groundedness":3,"icp_relevance":7,"personalization":7,"notes":"hallucinated"}'
    )
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert score.is_flagged is True


@pytest.mark.asyncio
async def test_clips_out_of_range() -> None:
    llm = FakeAnthropic(text='{"groundedness":15,"icp_relevance":-2,"personalization":7}')
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert score.groundedness == 10.0
    assert score.icp_relevance == 0.0


@pytest.mark.asyncio
async def test_unparseable_returns_zero_with_notes() -> None:
    llm = FakeAnthropic(text="not json")
    score = await EvalRubric(llm).evaluate_hook(_hook(), "x.com")
    assert score.groundedness == 0
    assert score.notes is not None and "unparseable" in score.notes
