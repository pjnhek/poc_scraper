"""Functional test: process_account runs end-to-end against a tmp_path bundle.

This is the proof point that the replay clients satisfy the ExaLike,
BrowserbaseLike, and LLMClient protocols at runtime, not just at the
type-checker level. It also confirms the bundle layout / hash function
round-trip: the same call signature produced by the live pipeline resolves
to the same fixture file the recording wrappers wrote.

The synthetic bundle is generated in tmp_path by running the recording
wrappers around in-test fake clients, then wiring ReplayExa /
ReplayBrowserbase / ReplayLLM at the bundle directory and calling
process_account against it. Two passes through identical code paths,
mediated only by disk, prove the round-trip is symmetric.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import LLMResponse
from src.clients.replay import (
    RecordingExa,
    RecordingLLM,
    ReplayBrowserbase,
    ReplayExa,
    ReplayLLM,
)
from src.models import Account, AccountStatus
from src.pipeline import build_deps, process_account

# Snippet long enough to skip the Browserbase fallback (ABOUT_TEXT_MIN_CHARS=200).
_ABOUT_SNIPPET = (
    "Synthetic Corp is a fictional company used for testing the replay pipeline. "
    "It serves a high volume of consumer-facing support tickets across chat, voice, "
    "email, and SMS channels. The company has publicly announced an AI deflection "
    "roadmap and is hiring ML engineers for the support automation team. "
    "Series B funding closed last quarter; the company is past product-market fit "
    "and scaling support spend."
)


class _SyntheticExa:
    """ExaLike stub returning a fixed about + news for synthetic.com."""

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        return [
            ExaResult(
                url=f"https://{domain}/about",
                title=None,
                snippet=_ABOUT_SNIPPET,
                published_at=None,
            )
        ]

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return [
            ExaResult(
                url=f"https://news.example/{domain}/launch",
                title=f"{domain} launches AI support",
                snippet="Recent news: AI support deflection roadmap announced.",
                published_at=None,
            )
        ]


class _ScriptedLLM:
    """LLMClient stub that scripts a valid response per prompt family.

    The keys match the unique system-prompt markers used in src/enrich.py,
    src/score.py, src/contacts.py, src/outreach.py, and evals/rubric.py.
    """

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if "You are a sales analyst" in system:
            return LLMResponse(
                text=(
                    '{"name":"Synthetic Corp","industry":"software",'
                    '"headcount_range":"200-500","tech_signals":["chat","voice"]}'
                )
            )
        if "score companies against an ICP rubric" in system:
            return LLMResponse(
                text=(
                    '{"support_volume":5,"support_volume_reason":"high ticket volume",'
                    '"ai_maturity":4,"ai_maturity_reason":"AI roadmap announced",'
                    '"stage_fit":4,"stage_fit_reason":"Series B past PMF",'
                    '"channel_breadth":5,"channel_breadth_reason":"four channels",'
                    '"justification":"strong ICP fit","supporting_indices":[1]}'
                )
            )
        if "propose the top 3 buyer personas" in system:
            return LLMResponse(
                text=(
                    '[{"role_title":"VP Customer Support","rationale":"owns deflection"},'
                    '{"role_title":"Head of CX","rationale":"owns CSAT"},'
                    '{"role_title":"Director Support Ops","rationale":"owns volume"}]'
                )
            )
        if "You write outreach claims from a seller" in system:
            return LLMResponse(text='{"claims":[],"connective_text":""}')
        if "LLM judge evaluating" in system:
            return LLMResponse(
                text=(
                    '{"claims":[{"text":"x","supported_by":1}],'
                    '"icp_relevance":3,"personalization":3,'
                    '"specificity":2,"recency":2}'
                )
            )
        raise AssertionError(f"unscripted system prompt: {system[:80]}")


class _NullBrowserbase:
    """BrowserbaseLike stub that never renders (about snippet is long enough)."""

    async def render(self, url: str) -> None:
        return None


async def _record_bundle(bundle: Path) -> None:
    """Drive a recording pass with synthetic inner clients to populate the bundle.

    Calls every external method process_account will later replay against:
    one Exa search_about, one search_news, plus the writer-side synthesize
    calls (firmographics, score, contacts, three outreach). Browserbase is
    not exercised because the synthetic about snippet exceeds the
    ABOUT_TEXT_MIN_CHARS threshold.
    """
    exa = RecordingExa(inner=_SyntheticExa(), bundle_dir=bundle)
    writer = RecordingLLM(inner=_ScriptedLLM(), bundle_dir=bundle, role="writer")

    # Drive every external call process_account will make. The Exa calls and
    # the LLM call args (system/context/user_prompt) MUST match exactly what
    # the live pipeline would produce, otherwise the digest will differ.
    # The simplest way to guarantee that is to actually run process_account
    # in recording mode against the synthetic inner clients; see below.
    await exa.search_about("synthetic.com")
    await exa.search_news("synthetic.com")
    # The writer-side prompts are constructed inside Enricher/Scorer/etc., so
    # we drive a real process_account against the recording clients to capture
    # them rather than reconstructing the prompts by hand.
    deps = build_deps(
        writer=writer,
        judge=RecordingLLM(inner=_ScriptedLLM(), bundle_dir=bundle, role="judge"),
        exa=exa,
        browserbase=_NullBrowserbase(),
    )
    await process_account(Account(domain="synthetic.com"), deps)


@pytest.mark.asyncio
async def test_process_account_runs_against_replayed_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "demo-bundle"

    # First pass: record the bundle by running the pipeline through the
    # recording wrappers against synthetic inner clients.
    await _record_bundle(bundle)

    # Second pass: run the pipeline again, this time with replay clients
    # that read every external call from disk. No inner clients; if the
    # round-trip hashing is correct, every fixture will resolve.
    deps = build_deps(
        writer=ReplayLLM(bundle, role="writer"),
        judge=ReplayLLM(bundle, role="judge"),
        exa=ReplayExa(bundle),
        browserbase=ReplayBrowserbase(bundle),
    )
    sa = await process_account(Account(domain="synthetic.com"), deps)

    # The empty-claims outreach response forces hook_suppressed regardless
    # of judge result. The substantive assertion is that process_account
    # completed end-to-end against the bundle without raising
    # ReplayMissError, which proves every external call matched a fixture.
    assert sa.account.domain == "synthetic.com"
    assert sa.status == AccountStatus.hook_suppressed
    assert sa.score is not None
    assert sa.score.total > 0
