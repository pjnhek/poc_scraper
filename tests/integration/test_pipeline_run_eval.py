"""Integration tests for process_account's run_eval and on_stage seams (Phase 12 D-02/D-05).

D-02: a deliberate run_eval=False skip must never read as a judge failure. D-05: on_stage
fires at exactly the five stage boundaries, in order, so the MCP wrapper (Plan 12-03) can
report progress without re-composing the pipeline.
"""

from __future__ import annotations

import httpx
import pytest

from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import LLMResponse
from src.models import Account, AccountStatus
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


class ExplodingExa:
    """FakeExa that raises httpx.HTTPError before any writer call happens."""

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        raise httpx.HTTPError("exa unreachable")

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        raise httpx.HTTPError("exa unreachable")


def _exa_about() -> ExaResult:
    return ExaResult(
        url="https://x.com/about",
        title=None,
        snippet="X is a company that does things. " * 20,
        published_at=None,
    )


def _firmographics_response() -> LLMResponse:
    return LLMResponse(text='{"name":"X","industry":null,"headcount_range":null,"tech_signals":[]}')


def _score_response() -> LLMResponse:
    return LLMResponse(
        text=(
            '{"support_volume":5,"support_volume_reason":"r",'
            '"ai_maturity":5,"ai_maturity_reason":"r",'
            '"stage_fit":5,"stage_fit_reason":"r",'
            '"channel_breadth":5,"channel_breadth_reason":"r",'
            '"justification":"ok"}'
        )
    )


def _personas_response() -> LLMResponse:
    return LLMResponse(
        text=(
            '[{"role_title":"a","rationale":"r"},'
            '{"role_title":"b","rationale":"r"},'
            '{"role_title":"c","rationale":"r"}]'
        )
    )


def _hook_response() -> LLMResponse:
    return LLMResponse(
        text=(
            '{"claims":[{"claim":"X is a company that does things",'
            '"cited_indices":[1]}],"connective_text":"reach out"}'
        )
    )


def _empty_hook_response() -> LLMResponse:
    return LLMResponse(text='{"claims":[],"connective_text":""}')


def _judge_response_not_flagged() -> LLMResponse:
    return LLMResponse(
        text=(
            '{"claims":['
            '{"text":"x","supported_by":1},'
            '{"text":"y","supported_by":1},'
            '{"text":"z","supported_by":1}],'
            '"icp_relevance":4,"personalization":4,'
            '"specificity":3,"recency":3}'
        )
    )


class HappyWriter:
    """Produces a full clean happy-path run: firmographics, score, 3 personas, cited hooks."""

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        if "You are a sales analyst" in system:
            return _firmographics_response()
        if "score companies against an ICP rubric" in system:
            return _score_response()
        if "propose the top 3 buyer personas" in system:
            return _personas_response()
        if "You write outreach claims from a seller" in system:
            return _hook_response()
        raise AssertionError(f"unscripted: {system[:60]}")


class EmptyHookWriter:
    """Same as HappyWriter through personas, but every outreach call yields empty claims."""

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        if "You are a sales analyst" in system:
            return _firmographics_response()
        if "score companies against an ICP rubric" in system:
            return _score_response()
        if "propose the top 3 buyer personas" in system:
            return _personas_response()
        if "You write outreach claims from a seller" in system:
            return _empty_hook_response()
        raise AssertionError(f"unscripted: {system[:60]}")


class RaisingJudge:
    """A judge fake that must never be invoked; counts calls for a belt-and-suspenders assert."""

    def __init__(self) -> None:
        self.calls = 0

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        self.calls += 1
        raise AssertionError("judge must not be called when run_eval=False")


class WorkingJudge:
    """A judge fake that returns a clean, non-flagged eval response."""

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        if "LLM judge evaluating" in system:
            return _judge_response_not_flagged()
        raise AssertionError(f"unscripted: {system[:60]}")


@pytest.mark.asyncio
async def test_run_eval_false_happy_path_yields_clean_without_judge_call() -> None:
    """D-02 core: run_eval=False on a happy-path account never invokes the judge."""
    judge = RaisingJudge()
    deps = build_deps(
        writer=HappyWriter(),
        judge=judge,
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps, run_eval=False)
    assert sa.status == AccountStatus.clean
    assert sa.eval_score is None
    assert judge.calls == 0


@pytest.mark.asyncio
async def test_run_eval_false_with_empty_hooks_yields_hook_suppressed_not_clean() -> None:
    """Pitfall 3 canary: a deliberate skip must not mask a real hook_suppressed outcome."""
    judge = RaisingJudge()
    deps = build_deps(
        writer=EmptyHookWriter(),
        judge=judge,
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps, run_eval=False)
    assert sa.status == AccountStatus.hook_suppressed
    assert sa.eval_score is None
    assert judge.calls == 0


@pytest.mark.asyncio
async def test_run_eval_false_status_is_never_judge_failed_or_low_groundedness() -> None:
    """D-02 impossibility: across both scenarios, only clean/hook_suppressed are reachable."""
    honest_statuses = {AccountStatus.clean, AccountStatus.hook_suppressed}

    happy_deps = build_deps(
        writer=HappyWriter(),
        judge=RaisingJudge(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa_happy = await process_account(Account(domain="x.com"), happy_deps, run_eval=False)
    assert sa_happy.status in honest_statuses

    empty_deps = build_deps(
        writer=EmptyHookWriter(),
        judge=RaisingJudge(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa_empty = await process_account(Account(domain="x.com"), empty_deps, run_eval=False)
    assert sa_empty.status in honest_statuses


@pytest.mark.asyncio
async def test_on_stage_fires_in_order_and_omits_eval_when_run_eval_false() -> None:
    """D-05: on_stage receives exactly the five stage names in order on a clean run_eval=True
    run, and exactly the first four when run_eval=False (eval is skipped, not just silent)."""

    collected_full: list[str] = []

    async def collector_full(stage: str) -> None:
        collected_full.append(stage)

    deps_full = build_deps(
        writer=HappyWriter(),
        judge=WorkingJudge(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa_full = await process_account(
        Account(domain="x.com"), deps_full, run_eval=True, on_stage=collector_full
    )
    assert sa_full.status == AccountStatus.clean
    assert collected_full == ["enrich", "score", "contacts", "outreach", "eval"]

    collected_skip: list[str] = []

    async def collector_skip(stage: str) -> None:
        collected_skip.append(stage)

    deps_skip = build_deps(
        writer=HappyWriter(),
        judge=RaisingJudge(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa_skip = await process_account(
        Account(domain="x.com"), deps_skip, run_eval=False, on_stage=collector_skip
    )
    assert sa_skip.status == AccountStatus.clean
    assert collected_skip == ["enrich", "score", "contacts", "outreach"]


@pytest.mark.asyncio
async def test_on_stage_stays_empty_on_early_enrich_failure() -> None:
    """An enrich-stage exception must short-circuit before any on_stage call fires, and the
    D-03 unscoreable result (status hook_suppressed, error starting with 'enrich failed')
    is unchanged by the presence of an on_stage callback."""

    collected: list[str] = []

    async def collector(stage: str) -> None:
        collected.append(stage)

    deps = build_deps(
        writer=HappyWriter(),
        judge=RaisingJudge(),
        exa=ExplodingExa(),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps, on_stage=collector)
    assert collected == []
    assert sa.status == AccountStatus.hook_suppressed
    assert sa.error is not None and sa.error.startswith("enrich failed")


@pytest.mark.asyncio
async def test_process_account_positional_call_stays_backward_compatible() -> None:
    """D-04/D-05 row: calling process_account(account, deps) positionally, with neither new
    keyword argument, still runs the full happy path exactly as before this plan."""
    deps = build_deps(
        writer=HappyWriter(),
        judge=WorkingJudge(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    assert sa.status == AccountStatus.clean
    assert sa.eval_score is not None
