"""Integration-level edge cases for pipeline failure isolation."""

from __future__ import annotations

import httpx
import pytest
from openai import APIError

from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import LLMResponse
from src.models import Account, AccountStatus
from src.pipeline import build_deps, process_account, run_pipeline


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
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        if self.fail_on in system:
            # APIError is in the narrow tuple per Phase 5 D-01 so the per-stage
            # except block degrades to a ScoredAccount.unscoreable row instead
            # of propagating per D-04.
            raise APIError(
                f"deliberate failure on '{self.fail_on}'",
                request=httpx.Request("POST", "https://example.com"),
                body=None,
            )
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
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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
                    # APIError is in the outreach stage's narrow tuple (D-01).
                    raise APIError(
                        "transient outreach failure",
                        request=httpx.Request("POST", "https://example.com"),
                        body=None,
                    )
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
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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


@pytest.mark.asyncio
async def test_eval_exception_with_nonempty_hooks_status_is_judge_failed() -> None:
    """D-03: eval network exception + non-empty hooks must yield judge_failed, not clean.

    When evaluate_account raises (not returns unparseable output), eval_score=None.
    The D-03 precedence must map None to judge_failed so the reader knows the eval
    layer crashed, not that the content was clean.
    """

    class EvalCrashingLLM:
        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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
                # APIError is in the eval stage's narrow tuple (D-01); per D-04
                # any other class would now propagate as a crash.
                raise APIError(
                    "eval network error",
                    request=httpx.Request("POST", "https://example.com"),
                    body=None,
                )
            raise AssertionError(f"unscripted: {system[:60]}")

    deps = build_deps(
        writer=EvalCrashingLLM(),
        judge=EvalCrashingLLM(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    # D-03: eval exception with non-empty hooks must be judge_failed, not clean.
    assert sa.status == AccountStatus.judge_failed
    assert sa.eval_score is None


@pytest.mark.asyncio
async def test_empty_enrichment_renders_graceful_sheet_row() -> None:
    """HARD-03 + D-11: Exa returns 0 AND Browserbase returns None.

    The enricher returns Enrichment(firmographics=None, news=()) and is_empty
    fires the early-return at src/pipeline.py:78-81, producing an unscoreable
    row with status=hook_suppressed and error="empty enrichment". The writer
    LLM is never invoked along this path; FailingAnthropic(fail_on="__never_match__")
    is wired only to confirm that property.

    D-09: assertion reaches into src/sheets.py::_build_row so the graceful-row
    promise is verified at the actual unit that converts ScoredAccount to the
    Sheet payload, not just at the ScoredAccount layer.
    """
    deps = build_deps(
        writer=FailingAnthropic(fail_on="__never_match__"),
        judge=FailingAnthropic(fail_on="__never_match__"),
        exa=FakeExa(about=[], news=[]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="empty.com"), deps)
    assert sa.status == AccountStatus.hook_suppressed
    assert sa.error == "empty enrichment"

    from src.sheets import HEADERS, _build_row

    row = _build_row(sa)
    assert row[HEADERS.index("domain")] == "empty.com"
    # _build_row writes sa.status directly (a StrEnum), not sa.status.value;
    # compare against the enum member to mirror the existing assertion shape
    # at tests/unit/test_sheets_rows.py::test_build_rows_writes_account_data:92.
    assert row[HEADERS.index("status")] == AccountStatus.hook_suppressed
    assert row[HEADERS.index("icp_total")] == ""
    assert row[HEADERS.index("verdict")] == ""
    assert row[HEADERS.index("hook_1")] == ""
    assert not row[HEADERS.index("hook_1")].startswith("=HYPERLINK(")
    assert row[HEADERS.index("error")] == "empty enrichment"


@pytest.mark.asyncio
async def test_citation_drop_renders_hook_suppressed_row() -> None:
    """HARD-03 + D-10: writer emits empty claims list -> hook_suppressed row.

    With ``{"claims":[],"connective_text":""}`` from the outreach writer,
    src/citations.py::assemble_paragraph returns ("", ()) and the resulting
    OutreachHook has paragraph="" and cited_indices=(). With three contacts
    the suppression applies to all three hooks, so D-03 precedence flips the
    final status to hook_suppressed regardless of eval result.

    The existing test_all_hooks_suppressed_status above already proves the
    status flip; the incremental value here per D-09 is the _build_row reach:
    confirm that the hook column renders as the empty string when the
    citation gate suppresses the paragraph end-to-end.
    """

    class EmptyClaimLLM:
        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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
                # D-10 trigger: empty claims list -> assemble_paragraph returns
                # ("", ()) -> hook with empty paragraph -> hook_suppressed.
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
        writer=EmptyClaimLLM(),
        judge=EmptyClaimLLM(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)
    assert sa.status == AccountStatus.hook_suppressed
    # With empty claims, OutreachGenerator builds a hook with paragraph=""
    # rather than skipping the persona. Verify the shape that drives _build_row.
    assert len(sa.hooks) == 3
    assert all(h.paragraph == "" for h in sa.hooks)

    from src.sheets import HEADERS, _build_row

    row = _build_row(sa)
    assert row[HEADERS.index("domain")] == "x.com"
    assert row[HEADERS.index("status")] == AccountStatus.hook_suppressed
    for hook in ("hook_1", "hook_2", "hook_3"):
        assert not row[HEADERS.index(hook)].startswith("=HYPERLINK(")
    assert row[HEADERS.index("hook_1")] == ""
    assert row[HEADERS.index("hook_2")] == ""
    assert row[HEADERS.index("hook_3")] == ""


@pytest.mark.asyncio
async def test_flagged_eval_renders_low_groundedness_status() -> None:
    """The pipeline seam: a parseable judge response below the groundedness
    threshold, with non-empty hooks, must render AccountStatus.low_groundedness.
    This is the one status with no prior end-to-end coverage."""

    class LowGroundednessLLM:
        async def synthesize(
            self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
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
                # 1 cited of 3 claims -> (1/3)*5 = 1.7, below the 3.0 flag
                # threshold, but parseable so eval_failed stays False.
                return LLMResponse(
                    text=(
                        '{"claims":['
                        '{"text":"c1","supported_by":1},'
                        '{"text":"c2","supported_by":"uncited"},'
                        '{"text":"c3","supported_by":"uncited"}],'
                        '"icp_relevance":4,"personalization":4,'
                        '"specificity":3,"recency":3,"notes":"thin"}'
                    )
                )
            raise AssertionError(f"unscripted: {system[:60]}")

    deps = build_deps(
        writer=LowGroundednessLLM(),
        judge=LowGroundednessLLM(),
        exa=FakeExa(about=[_exa_about()]),
        browserbase=FakeBrowserbase(),
    )
    sa = await process_account(Account(domain="x.com"), deps)

    assert sa.eval_score is not None
    assert not sa.eval_score.eval_failed
    assert sa.eval_score.is_flagged
    assert sa.status == AccountStatus.low_groundedness


@pytest.mark.asyncio
async def test_unexpected_exception_does_not_abort_batch() -> None:
    # An exception type NOT in process_account's narrow except clauses (here a
    # KeyError from a hypothetical malformed response) must not propagate out of
    # run_pipeline and discard every other account's work.
    class ExplodingExa:
        async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
            raise KeyError("url")

        async def search_news(
            self, domain: str, days: int = 90, num_results: int = 8
        ) -> list[ExaResult]:
            raise KeyError("url")

    deps = build_deps(
        writer=FailingAnthropic(fail_on="__never__"),
        judge=FailingAnthropic(fail_on="__never__"),
        exa=ExplodingExa(),
        browserbase=FakeBrowserbase(),
    )

    results = await run_pipeline(
        [Account(domain="boom.com"), Account(domain="alsoboom.com")], deps, concurrency=2
    )

    assert len(results) == 2
    assert {sa.account.domain for sa in results} == {"boom.com", "alsoboom.com"}
    assert all(sa.status == AccountStatus.hook_suppressed for sa in results)
    assert all(sa.error and "unexpected error" in sa.error for sa in results)
