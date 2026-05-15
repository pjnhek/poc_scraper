from __future__ import annotations

import pytest

from src.clients.nvidia_client import LLMResponse
from src.models import Account, Citation, Enrichment, Firmographics, Justification, NewsItem
from src.score import Scorer


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append({"system": system, "context": context, "user": user_prompt})
        return LLMResponse(text=self.text)


def _enrichment() -> Enrichment:
    citation = Citation.make(url="https://example.com/news", source="exa", title="t")
    return Enrichment(
        account=Account(domain="example.com"),
        firmographics=Firmographics(
            name="Example", industry="consumer software", headcount_range="1000-2000"
        ),
        news=(
            NewsItem(
                headline="Example adds AI support",
                summary="Example expands its AI-driven support stack",
                citation=citation,
            ),
        ),
        justifications=(
            Justification(index=1, summary="Example adds AI support", citation=citation),
        ),
    )


@pytest.mark.asyncio
async def test_happy_path_score() -> None:
    llm = FakeAnthropic(
        text=(
            '{"support_volume":5,"support_volume_reason":"high consumer volume",'
            '"ai_maturity":4,"ai_maturity_reason":"posted AI jobs",'
            '"stage_fit":4,"stage_fit_reason":"late stage",'
            '"channel_breadth":5,"channel_breadth_reason":"omnichannel",'
            '"justification":"strong fit overall"}'
        )
    )
    scorer = Scorer(llm)
    score = await scorer.score(_enrichment())
    assert score is not None
    assert score.total >= 4.0
    assert score.verdict == "strong"
    assert score.breakdown.support_volume == 5
    assert "fit" in score.justification.lower()


@pytest.mark.asyncio
async def test_clips_out_of_range_values() -> None:
    llm = FakeAnthropic(
        text=(
            '{"support_volume":15,"support_volume_reason":"r",'
            '"ai_maturity":-3,"ai_maturity_reason":"r",'
            '"stage_fit":3,"stage_fit_reason":"r",'
            '"channel_breadth":3,"channel_breadth_reason":"r",'
            '"justification":"clipped"}'
        )
    )
    score = await Scorer(llm).score(_enrichment())
    assert score is not None
    assert score.breakdown.support_volume == 5.0
    assert score.breakdown.ai_maturity == 1.0


@pytest.mark.asyncio
async def test_malformed_json_returns_none() -> None:
    llm = FakeAnthropic(text="I cannot help")
    score = await Scorer(llm).score(_enrichment())
    assert score is None


@pytest.mark.asyncio
async def test_missing_reasons_get_defaults() -> None:
    llm = FakeAnthropic(
        text=('{"support_volume":3,"ai_maturity":3,"stage_fit":3,"channel_breadth":3}')
    )
    score = await Scorer(llm).score(_enrichment())
    assert score is not None
    assert score.breakdown.support_volume_reason == "(no reason given)"
    assert score.justification.startswith("Weighted total")


@pytest.mark.asyncio
async def test_score_parses_supporting_indices() -> None:
    llm = FakeAnthropic(
        text=(
            '{"support_volume":4,"support_volume_reason":"r",'
            '"ai_maturity":3,"ai_maturity_reason":"r",'
            '"stage_fit":4,"stage_fit_reason":"r",'
            '"channel_breadth":3,"channel_breadth_reason":"r",'
            '"justification":"ok","supporting_indices":[1,99,1,2]}'
        )
    )
    score = await Scorer(llm).score(_enrichment())
    assert score is not None
    assert score.supporting_indices == (1,)


@pytest.mark.asyncio
async def test_score_context_includes_numbered_justifications() -> None:
    llm = FakeAnthropic(
        text=(
            '{"support_volume":4,"support_volume_reason":"r",'
            '"ai_maturity":3,"ai_maturity_reason":"r",'
            '"stage_fit":4,"stage_fit_reason":"r",'
            '"channel_breadth":3,"channel_breadth_reason":"r",'
            '"justification":"ok"}'
        )
    )
    await Scorer(llm).score(_enrichment())
    assert "<justifications>" in llm.calls[0]["context"]
    assert "[1]" in llm.calls[0]["context"]


@pytest.mark.asyncio
async def test_handles_no_firmographics() -> None:
    enr = Enrichment(account=Account(domain="x.com"))
    llm = FakeAnthropic(
        text=(
            '{"support_volume":2,"support_volume_reason":"thin",'
            '"ai_maturity":2,"ai_maturity_reason":"thin",'
            '"stage_fit":2,"stage_fit_reason":"thin",'
            '"channel_breadth":2,"channel_breadth_reason":"thin",'
            '"justification":"thin context"}'
        )
    )
    score = await Scorer(llm).score(enr)
    assert score is not None
    assert score.verdict == "weak"
    assert "no firmographics" in llm.calls[0]["context"]
