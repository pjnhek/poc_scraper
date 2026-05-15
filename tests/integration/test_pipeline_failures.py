"""Integration-level edge cases for pipeline failure isolation."""

from __future__ import annotations

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
    # title=None so the snippet is used as the justification summary; allows
    # test claims that cite content from this snippet to pass the rapidfuzz gate.
    return ExaResult(
        url="https://x.com/about",
        title=None,
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
    assert sa.status == AccountStatus.hook_suppressed
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
            if "You write outreach claims from a seller" in system:
                self.outreach_calls += 1
                if self.outreach_calls == 2:
                    raise RuntimeError("transient outreach failure")
                # Return a claim citing justification [1]; rapidfuzz gate passes
                # because the claim text overlaps with the snippet content.
                return LLMResponse(
                    text=(
                        '{"claims":[{"claim":"X is a company that does things",'
                        '"cited_indices":[1]}],"connective_text":"reach out"}'
                    ),
                )
            if "LLM judge evaluating" in system:
                # 3 cited out of 3 => groundedness = 5.0, not flagged => clean status.
                return LLMResponse(
                    text=(
                        '{"claims":['
                        '{"text":"x","supported_by":1},'
                        '{"text":"y","supported_by":1},'
                        '{"text":"z","supported_by":1}],'
                        '"icp_relevance":4,"personalization":4,'
                        '"specificity":3,"recency":3}'
                    ),
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
    assert sa.status == AccountStatus.clean
    assert len(sa.hooks) == 2


@pytest.mark.asyncio
async def test_judge_failure_status_precedence() -> None:
    """D-03: judge_failed wins over hook_suppressed and low_groundedness.

    Even when hooks are non-empty, if the judge cannot produce a valid response
    the status must be judge_failed so the eval failure is visible to the reader.
    """

    class JudgeFailingLLM:
        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens=None
        ) -> LLMResponse:
            if "You are a sales analyst" in system:
                return LLMResponse(
                    text='{"name":"X","industry":null,"headcount_range":null,"tech_signals":[]}'
                )
            if "score companies against an ICP rubric" in system:
                return LLMResponse(
                    text=(
                        '{"support_volume":5,"support_volume_reason":"r",'
                        '"ai_maturity":5,"ai_maturity_reason":"r",'
                        '"stage_fit":5,"stage_fit_reason":"r",'
                        '"channel_breadth":5,"channel_breadth_reason":"r",'
                        '"justification":"ok"}'
                    )
                )
            if "propose the top 3 buyer personas" in system:
                return LLMResponse(
                    text=(
                        '[{"role_title":"a","rationale":"r"},'
                        '{"role_title":"b","rationale":"r"},'
                        '{"role_title":"c","rationale":"r"}]'
                    )
                )
            if "You write outreach claims from a seller" in system:
                return LLMResponse(
                    text=(
                        '{"claims":[{"claim":"X is a company that does things",'
                        '"cited_indices":[1]}],"connective_text":"reach out"}'
                    )
                )
            if "LLM judge evaluating" in system:
                # Unparseable output forces _floor() which sets eval_failed=True.
                return LLMResponse(text="not json at all")
            raise AssertionError(f"unscripted: {system[:60]}")

    deps = build_deps(
        writer=JudgeFailingLLM(),
        judge=JudgeFailingLLM(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    # D-03: judge_failed must win even though hooks are non-empty.
    assert sa.status == AccountStatus.judge_failed
    assert sa.eval_score is not None and sa.eval_score.eval_failed


@pytest.mark.asyncio
async def test_all_hooks_suppressed_status() -> None:
    """D-03: hook_suppressed when all outreach hooks have empty paragraphs.

    If the rapidfuzz gate drops all claims for every hook, status is
    hook_suppressed (not clean or low_groundedness).
    """

    class AllEmptyHooksLLM:
        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens=None
        ) -> LLMResponse:
            if "You are a sales analyst" in system:
                return LLMResponse(
                    text='{"name":"X","industry":null,"headcount_range":null,"tech_signals":[]}'
                )
            if "score companies against an ICP rubric" in system:
                return LLMResponse(
                    text=(
                        '{"support_volume":5,"support_volume_reason":"r",'
                        '"ai_maturity":5,"ai_maturity_reason":"r",'
                        '"stage_fit":5,"stage_fit_reason":"r",'
                        '"channel_breadth":5,"channel_breadth_reason":"r",'
                        '"justification":"ok"}'
                    )
                )
            if "propose the top 3 buyer personas" in system:
                return LLMResponse(
                    text=(
                        '[{"role_title":"a","rationale":"r"},'
                        '{"role_title":"b","rationale":"r"},'
                        '{"role_title":"c","rationale":"r"}]'
                    )
                )
            if "You write outreach claims from a seller" in system:
                # Empty claims list -> assemble_paragraph returns ("", ()) -> hook suppressed.
                return LLMResponse(text='{"claims":[],"connective_text":""}')
            if "LLM judge evaluating" in system:
                return LLMResponse(
                    text=(
                        '{"claims":[{"text":"x","supported_by":1}],'
                        '"icp_relevance":3,"personalization":3,'
                        '"specificity":2,"recency":2}'
                    )
                )
            raise AssertionError(f"unscripted: {system[:60]}")

    deps = build_deps(
        writer=AllEmptyHooksLLM(),
        judge=AllEmptyHooksLLM(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    # D-03: all hooks empty → hook_suppressed regardless of eval result.
    assert sa.status == AccountStatus.hook_suppressed
