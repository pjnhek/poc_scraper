"""Smoke E2E tests. Hit live Anthropic + Exa + Browserbase APIs.

Skipped unless ANTHROPIC_API_KEY, EXA_API_KEY, BROWSERBASE_API_KEY,
BROWSERBASE_PROJECT_ID are all set. Sheets is exercised separately because it
needs a service-account JSON; if GOOGLE_APPLICATION_CREDENTIALS points to a
real file the sheets path runs too, otherwise we stop after the in-memory
pipeline.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.clients.anthropic_client import AnthropicClient
from src.clients.browserbase_client import BrowserbaseClient
from src.clients.exa_client import ExaClient
from src.config import get_settings
from src.csv_io import read_accounts
from src.pipeline import build_deps, run_pipeline

pytestmark = pytest.mark.smoke


def _all_required_keys_set() -> bool:
    s = get_settings()
    return bool(
        s.anthropic_api_key and s.exa_api_key and s.browserbase_api_key and s.browserbase_project_id
    )


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_keys() -> None:
    if not _all_required_keys_set():
        pytest.skip(
            "smoke tests require ANTHROPIC_API_KEY, EXA_API_KEY, BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID"
        )


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
        anthropic = AnthropicClient(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
        deps = build_deps(anthropic=anthropic, exa=exa, browserbase=bb)
        results = await run_pipeline(accounts, deps, concurrency=2)

    assert len(results) == 2
    assert all(sa.account.domain in {"notion.so", "linear.app"} for sa in results)
    scored_count = sum(1 for sa in results if sa.status == "scored")
    assert scored_count >= 1, "expected at least one scored account from a real run"
    for sa in results:
        if sa.status == "scored":
            assert sa.score is not None
            assert 0 <= sa.score.total <= 10
            assert sa.eval_score is not None


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
        anthropic = AnthropicClient(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
        deps = build_deps(anthropic=anthropic, exa=exa, browserbase=bb)
        results = await run_pipeline(accounts[:1], deps, concurrency=1)

    writer = SheetsWriter(
        credentials_path=creds_path,
        spreadsheet_id=settings.google_sheet_id or None,
    )
    result = writer.write(results)
    assert result.url.startswith("https://docs.google.com/spreadsheets/d/")
