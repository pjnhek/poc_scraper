from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.clients.browserbase_client import RenderedPage
from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import CachedSynthesis
from src.models import Account
from src.pipeline import build_deps, process_account, run_pipeline


class FakeExa:
    def __init__(self, about: list[ExaResult], news: list[ExaResult]) -> None:
        self.about = about
        self.news = news

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        return self.about

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return self.news


class FakeBrowserbase:
    def __init__(self, page: RenderedPage | None = None) -> None:
        self.page = page

    async def render(self, url: str) -> RenderedPage | None:
        return self.page


class ScriptedAnthropic:
    def __init__(self, scripts: dict[str, str]) -> None:
        self._scripts = scripts
        self.calls: list[str] = []

    async def synthesize(
        self, system: str, cached_context: str, user_prompt: str, max_tokens=None
    ) -> CachedSynthesis:
        for key, response in self._scripts.items():
            if key in system:
                self.calls.append(key)
                return CachedSynthesis(text=response, cache_read_tokens=0, cache_creation_tokens=0)
        raise AssertionError(f"unscripted call: {system[:80]}")


def _exa_about(text: str = "Chime is a consumer fintech app. " * 30) -> ExaResult:
    return ExaResult(
        url="https://chime.com/about",
        title="About Chime",
        snippet=text,
        published_at=None,
    )


def _exa_news() -> ExaResult:
    return ExaResult(
        url="https://techcrunch.com/chime-ai",
        title="Chime expands AI support",
        snippet="Chime announced an expansion of AI customer support today.",
        published_at=datetime(2026, 4, 1, tzinfo=UTC),
    )


def _scripted_full_run() -> ScriptedAnthropic:
    return ScriptedAnthropic(
        {
            "extract structured firmographics": (
                '{"name":"Chime","industry":"consumer fintech",'
                '"headcount_range":"1000-2000","tech_signals":["zendesk","react"]}'
            ),
            "score companies against an ICP rubric": (
                '{"support_volume":5,"support_volume_reason":"high consumer volume",'
                '"ai_maturity":4,"ai_maturity_reason":"posted AI roles",'
                '"stage_fit":4,"stage_fit_reason":"late stage",'
                '"channel_breadth":4,"channel_breadth_reason":"chat email phone",'
                '"justification":"strong fit"}'
            ),
            "propose the top 3 buyer personas": (
                '[{"role_title":"VP CX","rationale":"owns deflection"},'
                '{"role_title":"Head of Support","rationale":"owns CSAT"},'
                '{"role_title":"Director CX Auto","rationale":"runs RFPs"}]'
            ),
            "write one short outreach paragraph": (
                '{"paragraph":"Saw your AI push '
                "[Chime expands AI support](https://techcrunch.com/chime-ai). "
                'High deflection on tier-1 in consumer fintech.",'
                '"cited_urls":["https://techcrunch.com/chime-ai"]}'
            ),
            "LLM judge evaluating an outreach paragraph": (
                '{"groundedness":4,"icp_relevance":5,"personalization":4,"notes":"solid"}'
            ),
        }
    )


@pytest.mark.asyncio
async def test_full_account_processing_happy_path() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    bb = FakeBrowserbase()
    anthropic = _scripted_full_run()
    deps = build_deps(writer=anthropic, judge=anthropic, exa=exa, browserbase=bb)

    sa = await process_account(Account(domain="chime.com"), deps)

    assert sa.status == "scored"
    assert sa.score is not None and sa.score.total >= 4.0
    assert sa.score.verdict == "strong"
    assert len(sa.contacts) == 3
    assert len(sa.hooks) == 3
    for h in sa.hooks:
        assert "techcrunch.com/chime-ai" in h.paragraph
        assert len(h.citations) == 1
    assert sa.eval_score is not None
    assert sa.eval_score.groundedness == 4


@pytest.mark.asyncio
async def test_unscoreable_when_no_enrichment() -> None:
    exa = FakeExa(about=[], news=[])
    bb = FakeBrowserbase()
    anthropic = _scripted_full_run()
    deps = build_deps(writer=anthropic, judge=anthropic, exa=exa, browserbase=bb)

    sa = await process_account(Account(domain="dead.example"), deps)
    assert sa.status == "unscoreable"
    assert sa.error == "empty enrichment"
    assert sa.score is None


@pytest.mark.asyncio
async def test_run_pipeline_processes_multiple_accounts() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    bb = FakeBrowserbase()
    anthropic = _scripted_full_run()
    deps = build_deps(writer=anthropic, judge=anthropic, exa=exa, browserbase=bb)

    accounts = [Account(domain="chime.com"), Account(domain="duolingo.com")]
    results = await run_pipeline(accounts, deps, concurrency=2)
    assert len(results) == 2
    assert all(sa.status == "scored" for sa in results)
    assert {sa.account.domain for sa in results} == {"chime.com", "duolingo.com"}


@pytest.mark.asyncio
async def test_one_account_failure_does_not_kill_pipeline() -> None:
    class FlakyExa(FakeExa):
        def __init__(self) -> None:
            super().__init__(about=[_exa_about()], news=[_exa_news()])
            self.count = 0

        async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
            self.count += 1
            if self.count == 1:
                raise RuntimeError("upstream blew up")
            return self.about

    exa = FlakyExa()
    bb = FakeBrowserbase()
    anthropic = _scripted_full_run()
    deps = build_deps(writer=anthropic, judge=anthropic, exa=exa, browserbase=bb)

    accounts = [Account(domain="bad.example"), Account(domain="chime.com")]
    results = await run_pipeline(accounts, deps, concurrency=1)
    statuses = {r.account.domain: r.status for r in results}
    assert statuses == {"bad.example": "unscoreable", "chime.com": "scored"}
