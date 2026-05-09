from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from evals.rubric import EvalRubric

from .clients.anthropic_client import AnthropicClient
from .clients.browserbase_client import BrowserbaseClient
from .clients.exa_client import ExaClient
from .clients.protocols import AnthropicLike, BrowserbaseLike, ExaLike
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
    anthropic: AnthropicLike,
    exa: ExaLike,
    browserbase: BrowserbaseLike,
) -> Deps:
    return Deps(
        enricher=Enricher(exa=exa, browserbase=browserbase, anthropic=anthropic),
        scorer=Scorer(anthropic=anthropic),
        contacts=ContactExtractor(anthropic=anthropic),
        outreach=OutreachGenerator(anthropic=anthropic),
        eval_rubric=EvalRubric(anthropic=anthropic),
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
        anthropic = AnthropicClient(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
        deps = build_deps(anthropic=anthropic, exa=exa, browserbase=bb)

        scored = await run_pipeline(accounts, deps, concurrency=settings.pipeline_concurrency)

    writer = SheetsWriter(
        credentials_path=settings.google_application_credentials,
        spreadsheet_id=settings.google_sheet_id or None,
    )
    result = writer.write(scored)
    log.info("done. sheet: %s (tab=%s)", result.url, result.sheet_title)
    print(f"sheet: {result.url}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(asyncio.run(main()))
