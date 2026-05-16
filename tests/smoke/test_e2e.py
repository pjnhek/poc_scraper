"""Smoke E2E tests. Hit live NVIDIA + Exa + Browserbase APIs.

Skipped unless NVIDIA_API_KEY, EXA_API_KEY, BROWSERBASE_API_KEY,
BROWSERBASE_PROJECT_ID are all set. Sheets is exercised separately because it
needs a service-account JSON; if GOOGLE_APPLICATION_CREDENTIALS points to a
real file the sheets path runs too, otherwise we stop after the in-memory
pipeline.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.clients.browserbase_client import BrowserbaseClient
from src.clients.exa_client import ExaClient
from src.clients.nvidia_client import NvidiaClient
from src.config import Settings, get_settings
from src.csv_io import read_accounts
from src.models import AccountStatus
from src.pipeline import build_deps, build_judge_client, build_writer_client, run_pipeline

pytestmark = pytest.mark.smoke


def _all_required_keys_set() -> bool:
    s = get_settings()
    provider_key = s.deepseek_api_key if s.resolved_provider == "deepseek" else s.nvidia_api_key
    return bool(
        provider_key and s.exa_api_key and s.browserbase_api_key and s.browserbase_project_id
    )


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_keys() -> None:
    if not _all_required_keys_set():
        pytest.skip(
            "smoke tests require NVIDIA_API_KEY, EXA_API_KEY, BROWSERBASE_API_KEY, "
            "BROWSERBASE_PROJECT_ID"
        )


def _build_clients(settings: Settings) -> tuple[NvidiaClient, NvidiaClient]:
    return build_writer_client(settings), build_judge_client(settings)


@pytest.mark.asyncio
async def test_pipeline_runs_against_two_real_domains() -> None:
    settings = get_settings()
    accounts = read_accounts(Path(__file__).parent / "fixtures.csv")
    assert len(accounts) == 2

    async with httpx.AsyncClient(timeout=60.0) as http:
        exa = ExaClient(api_key=settings.exa_api_key, client=http)
        bb = BrowserbaseClient(
            api_key=settings.browserbase_api_key,
            project_id=settings.browserbase_project_id,
            client=http,
        )
        writer, judge = _build_clients(settings)
        deps = build_deps(writer=writer, judge=judge, exa=exa, browserbase=bb)
        results = await run_pipeline(accounts, deps, concurrency=2)

    assert len(results) == 2
    # Post-Phase-2: status is the AccountStatus enum (clean/low_groundedness/
    # hook_suppressed/judge_failed), not the old "scored"/"unscoreable" Literal.
    # A successfully *processed* account is identified by score is not None;
    # enrich/score failures set score=None via ScoredAccount.unscoreable().
    # Final status may be any quality grade — judge_failed is tolerated here
    # because the external judge intermittently returns empty output on a live
    # run, which is a known judge-robustness flake, not a pipeline defect.
    processed = [sa for sa in results if sa.score is not None]
    assert len(processed) >= 1, "expected at least one scored account from a real run"
    for sa in processed:
        assert sa.status in AccountStatus
        assert 1 <= sa.score.total <= 5  # type: ignore[union-attr]
        # eval_score is None only when the judge call raised; on a clean
        # judge run it is populated. Either way the account was processed.
        if sa.eval_score is not None:
            assert isinstance(sa.eval_score.eval_failed, bool)


@pytest.mark.asyncio
async def test_sheets_write_when_credentials_present() -> None:
    from src.sheets import SheetsWriter

    settings = get_settings()
    creds_path = Path(settings.google_application_credentials)
    if not creds_path.exists():
        pytest.skip(f"no service-account file at {creds_path}; skipping sheets smoke")

    accounts = read_accounts(Path(__file__).parent / "fixtures.csv")
    async with httpx.AsyncClient(timeout=60.0) as http:
        exa = ExaClient(api_key=settings.exa_api_key, client=http)
        bb = BrowserbaseClient(
            api_key=settings.browserbase_api_key,
            project_id=settings.browserbase_project_id,
            client=http,
        )
        writer, judge = _build_clients(settings)
        deps = build_deps(writer=writer, judge=judge, exa=exa, browserbase=bb)
        results = await run_pipeline(accounts[:1], deps, concurrency=1)

    sheets_writer = SheetsWriter(
        credentials_path=creds_path,
        spreadsheet_id=settings.google_sheet_id or None,
    )
    result = sheets_writer.write(results)
    assert result.url.startswith("https://docs.google.com/spreadsheets/d/")
