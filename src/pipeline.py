from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from evals.rubric import EvalRubric

from .clients.browserbase_client import BrowserbaseClient
from .clients.exa_client import ExaClient
from .clients.nvidia_client import (
    DEEPSEEK_BASE_URL,
    NVIDIA_BASE_URL,
    GenerationParams,
    NvidiaClient,
)
from .clients.protocols import BrowserbaseLike, ExaLike, LLMClient
from .config import Settings, get_settings
from .contacts import ContactExtractor
from .csv_io import read_accounts
from .enrich import Enricher
from .icp_config import get_config
from .models import Account, Enrichment, ScoredAccount
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
    except Exception as exc:
        log.warning("enrich failed for %s: %s", account.domain, exc)
        return ScoredAccount.unscoreable(
            account, Enrichment(account=account), f"enrich failed: {exc}"
        )

    if enrichment.is_empty:
        return ScoredAccount.unscoreable(account, enrichment, "empty enrichment")

    try:
        score = await deps.scorer.score(enrichment)
    except Exception as exc:
        log.warning("score failed for %s: %s", account.domain, exc)
        return ScoredAccount.unscoreable(account, enrichment, f"score failed: {exc}")
    if score is None:
        return ScoredAccount.unscoreable(account, enrichment, "score: judge returned no JSON")

    try:
        contacts = await deps.contacts.extract(enrichment, score)
    except Exception as exc:
        log.warning("contacts failed for %s: %s", account.domain, exc)
        contacts = ()

    hooks = []
    for c in contacts:
        try:
            hook = await deps.outreach.generate(c, enrichment, score)
        except Exception as exc:
            log.warning("outreach failed for %s/%s: %s", account.domain, c.role_title, exc)
            continue
        hooks.append(hook)

    sa = ScoredAccount(
        account=account,
        status="scored",
        enrichment=enrichment,
        score=score,
        contacts=contacts,
        hooks=tuple(hooks),
    )

    try:
        eval_score = await deps.eval_rubric.evaluate_account(sa)
    except Exception as exc:
        log.warning("eval failed for %s: %s", account.domain, exc)
        eval_score = None

    return ScoredAccount(
        account=account,
        status=sa.status,
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
        exa = ExaClient(api_key=settings.exa_api_key, client=http)
        bb = BrowserbaseClient(
            api_key=settings.browserbase_api_key,
            project_id=settings.browserbase_project_id,
            client=http,
        )
        writer = _build_writer(settings)
        judge = _build_judge(settings)
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
