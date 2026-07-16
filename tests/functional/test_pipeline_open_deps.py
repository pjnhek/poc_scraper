"""Functional tests for open_deps() (D-11): proves replay/record/live wiring.

Fake non-empty key strings are sufficient because only client construction
is exercised, never `.synthesize()` / `.search_about()` / `.render()` (no
live network calls occur in this test).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.clients.browserbase_client import BrowserbaseClient
from src.clients.exa_client import ExaClient
from src.clients.replay import RecordingBrowserbase, RecordingExa, ReplayBrowserbase, ReplayExa
from src.config import Settings
from src.pipeline import open_deps


def _base_settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        deepseek_api_key="test-deepseek-key",
        exa_api_key="test-exa-key",
        browserbase_api_key="test-bb-key",
        browserbase_project_id="test-project",
        **overrides,
    )  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_open_deps_replay_settings_yield_replay_clients(tmp_path: Path) -> None:
    settings = _base_settings(demo_bundle=tmp_path)
    async with open_deps(settings) as deps:
        assert isinstance(deps.enricher._exa, ReplayExa)
        assert isinstance(deps.enricher._browserbase, ReplayBrowserbase)


@pytest.mark.asyncio
async def test_open_deps_record_settings_yield_recording_wrappers(tmp_path: Path) -> None:
    settings = _base_settings(record_bundle=tmp_path)
    async with open_deps(settings) as deps:
        assert isinstance(deps.enricher._exa, RecordingExa)
        assert isinstance(deps.enricher._browserbase, RecordingBrowserbase)


@pytest.mark.asyncio
async def test_open_deps_live_settings_yield_real_clients_and_closes_http_on_exit() -> None:
    settings = _base_settings()
    async with open_deps(settings) as deps:
        assert isinstance(deps.enricher._exa, ExaClient)
        assert isinstance(deps.enricher._browserbase, BrowserbaseClient)
        http_client = deps.enricher._exa._client
        assert http_client.is_closed is False
    assert http_client.is_closed is True
