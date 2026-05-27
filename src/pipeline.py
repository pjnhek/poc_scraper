from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from openai import APIError, APIStatusError, RateLimitError
from pydantic import ValidationError

from evals.rubric import EvalRubric

from .clients.browserbase_client import BrowserbaseClient, BrowserbaseError
from .clients.exa_client import ExaClient
from .clients.nvidia_client import (
    DEEPSEEK_BASE_URL,
    NVIDIA_BASE_URL,
    GenerationParams,
    NvidiaClient,
)
from .clients.protocols import BrowserbaseLike, ExaLike, LLMClient
from .clients.replay import (
    RecordingBrowserbase,
    RecordingExa,
    RecordingLLM,
    ReplayBrowserbase,
    ReplayExa,
    ReplayLLM,
)
from .config import Settings, get_settings
from .contacts import ContactExtractor
from .csv_io import read_accounts
from .enrich import Enricher
from .icp_config import get_config
from .models import Account, AccountStatus, Enrichment, ScoredAccount
from .outreach import OutreachGenerator
from .score import Scorer
from .sheets import SheetsWriter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Deps:
    enricher: Enricher
    scorer: Scorer
    contacts: ContactExtractor
    outreach: OutreachGenerator
    eval_rubric: EvalRubric


def build_deps(
    writer: LLMClient,
    judge: LLMClient,
    exa: ExaLike,
    browserbase: BrowserbaseLike,
) -> Deps:
    return Deps(
        enricher=Enricher(exa=exa, browserbase=browserbase, llm=writer),
        scorer=Scorer(llm=writer),
        contacts=ContactExtractor(llm=writer),
        outreach=OutreachGenerator(llm=writer),
        eval_rubric=EvalRubric(llm=judge),
    )


async def process_account(account: Account, deps: Deps) -> ScoredAccount:
    try:
        enrichment = await deps.enricher.enrich(account)
    except (
        httpx.HTTPError,
        BrowserbaseError,
        RateLimitError,
        APIStatusError,
        APIError,
        ValidationError,
    ) as exc:
        log.warning("enrich failed [%s] for %s: %s", type(exc).__name__, account.domain, exc)
        return ScoredAccount.unscoreable(
            account,
            Enrichment(account=account),
            f"enrich failed [{type(exc).__name__}]: {exc}",
            status=AccountStatus.hook_suppressed,
        )

    if enrichment.is_empty:
        return ScoredAccount.unscoreable(
            account, enrichment, "empty enrichment", status=AccountStatus.hook_suppressed
        )

    try:
        score = await deps.scorer.score(enrichment)
    except (RateLimitError, APIStatusError, APIError, ValidationError) as exc:
        log.warning("score failed [%s] for %s: %s", type(exc).__name__, account.domain, exc)
        return ScoredAccount.unscoreable(
            account,
            enrichment,
            f"score failed [{type(exc).__name__}]: {exc}",
            status=AccountStatus.hook_suppressed,
        )
    if score is None:
        return ScoredAccount.unscoreable(
            account,
            enrichment,
            "score: judge returned no JSON",
            status=AccountStatus.hook_suppressed,
        )

    try:
        contacts = await deps.contacts.extract(enrichment, score)
    except (RateLimitError, APIStatusError, APIError, ValidationError) as exc:
        log.warning("contacts failed [%s] for %s: %s", type(exc).__name__, account.domain, exc)
        contacts = ()

    hooks = []
    for c in contacts:
        try:
            hook = await deps.outreach.generate(c, enrichment, score)
        except (RateLimitError, APIStatusError, APIError, ValidationError) as exc:
            log.warning(
                "outreach failed [%s] for %s/%s: %s",
                type(exc).__name__,
                account.domain,
                c.role_title,
                exc,
            )
            continue
        hooks.append(hook)

    sa = ScoredAccount(
        account=account,
        status=AccountStatus.clean,
        enrichment=enrichment,
        score=score,
        contacts=contacts,
        hooks=tuple(hooks),
    )

    try:
        eval_score = await deps.eval_rubric.evaluate_account(sa)
    except (RateLimitError, APIStatusError, APIError, ValidationError) as exc:
        log.warning("eval failed [%s] for %s: %s", type(exc).__name__, account.domain, exc)
        eval_score = None

    # D-03 precedence: worst-observability-first so a judge failure is never masked.
    # judge_failed wins because it signals the eval layer is broken, not just the content.
    # hook_suppressed is next because no content was delivered regardless of eval result.
    # eval_score=None from an exception (not unparseable output) also maps to judge_failed
    # so the sheet reader can distinguish "evaluated clean" from "eval crashed silently".
    # low_groundedness means content exists but the judge flagged it.
    # clean only when none of the above apply.
    if eval_score is not None and eval_score.eval_failed:
        final_status = AccountStatus.judge_failed
    elif all(h.paragraph == "" for h in hooks):
        final_status = AccountStatus.hook_suppressed
    elif eval_score is None:
        # Eval raised a network or runtime exception; treat as judge_failed so the
        # reader knows the eval layer did not run, not that content passed review.
        final_status = AccountStatus.judge_failed
    elif eval_score.is_flagged:
        final_status = AccountStatus.low_groundedness
    else:
        final_status = AccountStatus.clean

    return ScoredAccount(
        account=account,
        status=final_status,
        enrichment=enrichment,
        score=score,
        contacts=contacts,
        hooks=tuple(hooks),
        eval_score=eval_score,
    )


async def run_pipeline(
    accounts: list[Account],
    deps: Deps,
    concurrency: int = 5,
) -> list[ScoredAccount]:
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(acc: Account) -> ScoredAccount:
        async with sem:
            return await process_account(acc, deps)

    return list(await asyncio.gather(*(_bounded(a) for a in accounts)))


def provider_endpoint(settings: Settings) -> tuple[str, str]:
    """Return (api_key, base_url) for the resolved LLM provider."""
    if settings.resolved_provider == "deepseek":
        return settings.deepseek_api_key, DEEPSEEK_BASE_URL
    return settings.nvidia_api_key, NVIDIA_BASE_URL


def build_writer_client(settings: Settings) -> NvidiaClient:
    return _build_writer(settings)


def build_judge_client(settings: Settings) -> NvidiaClient:
    return _build_judge(settings)


def _build_writer(settings: Settings) -> NvidiaClient:
    api_key, base_url = provider_endpoint(settings)
    # DeepSeek supports response_format guaranteed JSON; NVIDIA Build
    # generally does not, so only enable when on DeepSeek.
    json_mode = settings.resolved_provider == "deepseek"
    return NvidiaClient(
        api_key=api_key,
        base_url=base_url,
        model=settings.writer_model,
        max_in_flight=settings.llm_max_in_flight,
        params=GenerationParams(
            temperature=settings.writer_temperature,
            top_p=settings.writer_top_p,
            max_tokens=settings.writer_max_tokens,
            json_mode=json_mode,
        ),
    )


def _build_judge(settings: Settings) -> NvidiaClient:
    api_key, base_url = provider_endpoint(settings)
    extra_body: dict[str, object] = {}
    reasoning_budget: int | None = None
    reasoning_effort: str | None = None
    json_mode = False
    if settings.resolved_provider == "deepseek":
        # DeepSeek toggles thinking mode via extra_body and exposes
        # reasoning_effort as a top-level kwarg.
        extra_body["thinking"] = {"type": "enabled"}
        reasoning_effort = settings.judge_reasoning_effort_deepseek
        json_mode = True
    else:
        # NVIDIA reasoning models use thinking_budget instead.
        reasoning_budget = settings.judge_reasoning_budget
    return NvidiaClient(
        api_key=api_key,
        base_url=base_url,
        model=settings.judge_model,
        max_in_flight=settings.llm_max_in_flight,
        params=GenerationParams(
            temperature=settings.judge_temperature,
            top_p=settings.judge_top_p,
            max_tokens=settings.judge_max_tokens,
            reasoning_budget=reasoning_budget,
            reasoning_effort=reasoning_effort,
            json_mode=json_mode,
            extra_body=extra_body,
        ),
    )


async def main(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    settings.require_for_pipeline()

    accounts = read_accounts(settings.accounts_csv)
    if not accounts:
        log.error("no accounts in %s", settings.accounts_csv)
        return 1
    if settings.run_limit is not None and settings.run_limit < len(accounts):
        log.info(
            "RUN_LIMIT=%d set; processing first %d of %d accounts",
            settings.run_limit,
            settings.run_limit,
            len(accounts),
        )
        accounts = accounts[: settings.run_limit]
    log.info("loaded %d accounts from %s", len(accounts), settings.accounts_csv)

    async with httpx.AsyncClient(timeout=60.0) as http:
        exa: ExaLike
        bb: BrowserbaseLike
        writer: LLMClient
        judge: LLMClient
        if settings.demo_bundle is not None:
            # D-15: replay mode swaps every external client for the JSON-backed
            # stubs. Live providers are never contacted; require_for_pipeline
            # has already skipped the API-key checks above.
            exa = ReplayExa(settings.demo_bundle)
            bb = ReplayBrowserbase(settings.demo_bundle)
            writer = ReplayLLM(settings.demo_bundle, role="writer")
            judge = ReplayLLM(settings.demo_bundle, role="judge")
        else:
            exa = ExaClient(api_key=settings.exa_api_key, client=http)
            bb = BrowserbaseClient(
                api_key=settings.browserbase_api_key,
                project_id=settings.browserbase_project_id,
                client=http,
            )
            writer = _build_writer(settings)
            judge = _build_judge(settings)
            if settings.record_bundle is not None:
                # D-17: post-construction wrap so the inner clients own
                # request formation. The wrappers only tee the response to
                # disk for later replay.
                exa = RecordingExa(inner=exa, bundle_dir=settings.record_bundle)
                bb = RecordingBrowserbase(inner=bb, bundle_dir=settings.record_bundle)
                writer = RecordingLLM(
                    inner=writer, bundle_dir=settings.record_bundle, role="writer"
                )
                judge = RecordingLLM(inner=judge, bundle_dir=settings.record_bundle, role="judge")
        deps = build_deps(writer=writer, judge=judge, exa=exa, browserbase=bb)

        scored = await run_pipeline(accounts, deps, concurrency=settings.pipeline_concurrency)

    writer_sheets = SheetsWriter(
        credentials_path=settings.google_application_credentials,
        spreadsheet_id=settings.google_sheet_id or None,
    )
    result = writer_sheets.write(scored, accounts=accounts, config=get_config())
    log.info("done. sheet: %s (tab=%s)", result.url, result.sheet_title)
    print(f"sheet: {result.url}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(asyncio.run(main()))
