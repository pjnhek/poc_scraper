"""Live eval: run the full pipeline against real domains, then judge each hook.

Unlike `evals/run_eval.py` (which compares the judge against hand-labeled
fixtures), this hits real Exa, real writer LLM, real Browserbase. It does
not require labeled data; the judge scores the generated outreach paragraphs
directly. Output is a markdown table of per-account, per-persona scores.

Usage:
    make eval-live                      # default: first 3 domains
    EVAL_LIVE_DOMAINS=mercury.com,strava.com make eval-live
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.clients.browserbase_client import BrowserbaseClient
from src.clients.exa_client import ExaClient
from src.clients.nvidia_client import GenerationParams, NvidiaClient
from src.config import get_settings
from src.csv_io import read_accounts
from src.models import Account, ScoredAccount
from src.pipeline import build_deps, process_account

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveRow:
    domain: str
    verdict: str
    icp_total: float
    persona: str
    paragraph_excerpt: str
    citations_count: int
    groundedness: float
    icp_relevance: float
    personalization: float
    notes: str | None


def _flatten(scored: list[ScoredAccount]) -> list[LiveRow]:
    rows: list[LiveRow] = []
    for sa in scored:
        if sa.status != "scored" or sa.score is None:
            rows.append(
                LiveRow(
                    domain=sa.account.domain,
                    verdict="(unscoreable)",
                    icp_total=0.0,
                    persona="-",
                    paragraph_excerpt=sa.error or "",
                    citations_count=0,
                    groundedness=0.0,
                    icp_relevance=0.0,
                    personalization=0.0,
                    notes=None,
                )
            )
            continue
        ev = sa.eval_score
        for h in sa.hooks:
            excerpt = h.paragraph[:80].replace("\n", " ") + ("..." if len(h.paragraph) > 80 else "")
            rows.append(
                LiveRow(
                    domain=sa.account.domain,
                    verdict=sa.score.verdict,
                    icp_total=sa.score.total,
                    persona=h.contact.role_title,
                    paragraph_excerpt=excerpt or "(empty paragraph)",
                    citations_count=len(h.citations),
                    groundedness=ev.groundedness if ev else 0.0,
                    icp_relevance=ev.icp_relevance if ev else 0.0,
                    personalization=ev.personalization if ev else 0.0,
                    notes=ev.notes if ev else None,
                )
            )
    return rows


def markdown_table(rows: list[LiveRow]) -> str:
    lines = [
        (
            "| domain | verdict | icp | persona | paragraph | cites | "
            "ground | icp_rel | person | notes |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.domain} "
            f"| {r.verdict} "
            f"| {r.icp_total:.1f} "
            f"| {r.persona} "
            f"| {r.paragraph_excerpt} "
            f"| {r.citations_count} "
            f"| {r.groundedness:.1f} "
            f"| {r.icp_relevance:.1f} "
            f"| {r.personalization:.1f} "
            f"| {(r.notes or '')[:60]} |"
        )
    return "\n".join(lines)


def summary_line(rows: list[LiveRow]) -> str:
    judged = [r for r in rows if r.verdict != "(unscoreable)"]
    if not judged:
        return "(no judged hooks)"
    g = sum(r.groundedness for r in judged) / len(judged)
    i = sum(r.icp_relevance for r in judged) / len(judged)
    p = sum(r.personalization for r in judged) / len(judged)
    return (
        f"averaged across {len(judged)} hooks: groundedness={g:.2f}, "
        f"icp_relevance={i:.2f}, personalization={p:.2f}"
    )


def _select_domains(settings_csv: Path, override_env: str | None, limit: int) -> list[Account]:
    if override_env:
        return [Account(domain=d.strip()) for d in override_env.split(",") if d.strip()]
    accounts = read_accounts(settings_csv)
    return accounts[:limit]


async def run() -> int:
    settings = get_settings()
    settings.require_for_pipeline()

    domains_env = os.environ.get("EVAL_LIVE_DOMAINS")
    limit = int(os.environ.get("EVAL_LIVE_LIMIT", "3"))
    accounts = _select_domains(settings.accounts_csv, domains_env, limit)
    if not accounts:
        log.error("no domains to evaluate")
        return 1

    log.info(
        "live eval against %d domains: %s", len(accounts), ", ".join(a.domain for a in accounts)
    )

    async with httpx.AsyncClient(timeout=60.0) as http:
        exa = ExaClient(api_key=settings.exa_api_key, client=http)
        bb = BrowserbaseClient(
            api_key=settings.browserbase_api_key,
            project_id=settings.browserbase_project_id,
            client=http,
        )
        writer = NvidiaClient(
            api_key=settings.nvidia_api_key,
            model=settings.writer_model,
            params=GenerationParams(
                temperature=settings.writer_temperature,
                top_p=settings.writer_top_p,
                max_tokens=settings.writer_max_tokens,
            ),
        )
        judge = NvidiaClient(
            api_key=settings.nvidia_api_key,
            model=settings.judge_model,
            params=GenerationParams(
                temperature=settings.judge_temperature,
                top_p=settings.judge_top_p,
                max_tokens=settings.judge_max_tokens,
                reasoning_budget=settings.judge_reasoning_budget,
            ),
        )
        deps = build_deps(writer=writer, judge=judge, exa=exa, browserbase=bb)
        scored = await asyncio.gather(*(process_account(a, deps) for a in accounts))

    rows = _flatten(list(scored))
    print(markdown_table(rows))
    print()
    print(summary_line(rows))
    print()
    print(f"writer={settings.writer_model}  judge={settings.judge_model}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(asyncio.run(run()))
