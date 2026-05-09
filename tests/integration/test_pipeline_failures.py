"""Integration-level edge cases for pipeline failure isolation."""

from __future__ import annotations

import pytest

from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import LLMResponse
from src.models import Account
from src.pipeline import build_deps, process_account


class FakeBrowserbase:
    async def render(self, url: str) -> None:
        return None


class FakeExa:
    def __init__(
        self, about: list[ExaResult] | None = None, news: list[ExaResult] | None = None
    ) -> None:
        self.about = about or []
        self.news = news or []

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        return self.about

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return self.news


class FailingAnthropic:
    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens=None
    ) -> LLMResponse:
        if self.fail_on in system:
            raise RuntimeError(f"deliberate failure on '{self.fail_on}'")
        return LLMResponse(text="{}")


def _exa_about() -> ExaResult:
    return ExaResult(
        url="https://x.com/about",
        title="About",
        snippet="X is a company that does things. " * 20,
        published_at=None,
    )


@pytest.mark.asyncio
async def test_score_failure_marks_unscoreable() -> None:
    failing = FailingAnthropic(fail_on="score companies against an ICP rubric")
    deps = build_deps(
        writer=failing,
        judge=failing,
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    assert sa.status == "unscoreable"
    assert sa.error is not None and "score" in sa.error.lower()


@pytest.mark.asyncio
async def test_outreach_failure_continues_with_remaining_contacts() -> None:
    class HalfFailing:
        def __init__(self) -> None:
            self.outreach_calls = 0

        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens=None
        ) -> LLMResponse:
            if "extract structured firmographics" in system:
                return LLMResponse(
                    text='{"name":"X","industry":null,"headcount_range":null,"tech_signals":[]}',
                )
            if "score companies against an ICP rubric" in system:
                return LLMResponse(
                    text=(
                        '{"support_volume":5,"support_volume_reason":"r",'
                        '"ai_maturity":5,"ai_maturity_reason":"r",'
                        '"stage_fit":5,"stage_fit_reason":"r",'
                        '"channel_breadth":5,"channel_breadth_reason":"r",'
                        '"justification":"ok"}'
                    ),
                )
            if "propose the top 3 buyer personas" in system:
                return LLMResponse(
                    text=(
                        '[{"role_title":"a","rationale":"r"},'
                        '{"role_title":"b","rationale":"r"},'
                        '{"role_title":"c","rationale":"r"}]'
                    ),
                )
            if "write one short outreach paragraph" in system:
                self.outreach_calls += 1
                if self.outreach_calls == 2:
                    raise RuntimeError("transient outreach failure")
                return LLMResponse(
                    text='{"paragraph":"","cited_urls":[]}',
                )
            if "LLM judge evaluating" in system:
                return LLMResponse(
                    text='{"groundedness":4,"icp_relevance":4,"personalization":4}',
                )
            raise AssertionError(f"unscripted: {system[:60]}")

    half = HalfFailing()
    deps = build_deps(
        writer=half,
        judge=half,
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    assert sa.status == "scored"
    assert len(sa.hooks) == 2
