from __future__ import annotations

import pytest

from src.clients.nvidia_client import CachedSynthesis
from src.models import Account, Citation, Enrichment, Firmographics, NewsItem
from src.score import Scorer


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []

    async def synthesize(
        self,
        system: str,
        cached_context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> CachedSynthesis:
        self.calls.append({"system": system, "context": cached_context, "user": user_prompt})
        return CachedSynthesis(text=self.text, cache_read_tokens=0, cache_creation_tokens=0)


def _enrichment() -> Enrichment:
    return Enrichment(
        account=Account(domain="example.com"),
        firmographics=Firmographics(
            name="Example", industry="consumer fintech", headcount_range="1000-2000"
        ),
        news=(
            NewsItem(
                headline="Example adds AI support",
                summary="Example expands its AI-driven support stack",
                citation=Citation.make(url="https://example.com/news", source="exa", title="t"),
            ),
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
