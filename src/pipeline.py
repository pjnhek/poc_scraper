from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from evals.rubric import EvalRubric

from .clients.browserbase_client import BrowserbaseClient
from .clients.exa_client import ExaClient
from .clients.nvidia_client import GenerationParams, NvidiaClient
from .clients.protocols import BrowserbaseLike, ExaLike, LLMClient
from .config import Settings, get_settings
from .contacts import ContactExtractor
from .csv_io import read_accounts
from .enrich import Enricher
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


def _build_writer(settings: Settings) -> NvidiaClient:
    return NvidiaClient(
        api_key=settings.nvidia_api_key,
        model=settings.writer_model,
        params=GenerationParams(
            temperature=settings.writer_temperature,
            top_p=settings.writer_top_p,
            max_tokens=settings.writer_max_tokens,
        ),
    )


def _build_judge(settings: Settings) -> NvidiaClient:
    return NvidiaClient(
        api_key=settings.nvidia_api_key,
        model=settings.judge_model,
        params=GenerationParams(
            temperature=settings.judge_temperature,
            top_p=settings.judge_top_p,
            max_tokens=settings.judge_max_tokens,
            reasoning_budget=settings.judge_reasoning_budget,
        ),
    )


async def main(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    settings.require_for_pipeline()

    accounts = read_accounts(settings.accounts_csv)
    if not accounts:
        log.error("no accounts in %s", settings.accounts_csv)
        return 1
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
    result = writer_sheets.write(scored)
    log.info("done. sheet: %s (tab=%s)", result.url, result.sheet_title)
    print(f"sheet: {result.url}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(asyncio.run(main()))
