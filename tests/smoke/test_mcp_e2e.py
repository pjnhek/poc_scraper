"""MCP stdio transport smoke test. Hits a live Exa call through a REAL
`python -m src.mcp_server` subprocess, over actual stdio pipes.

Skipped unless EXA_API_KEY is set (the thin tier has zero LLM involvement,
so no other provider key is required). This is the only automated test that
proves stdout carries nothing but clean JSON-RPC frames end to end; the
in-memory functional tests in tests/functional/test_mcp_server.py never
touch stdin/stdout and cannot catch stdout contamination by construction.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from src.config import get_settings

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module", autouse=True)
def _skip_if_no_exa_key() -> None:
    if not get_settings().exa_api_key:
        pytest.skip("mcp smoke requires EXA_API_KEY")


@pytest.mark.asyncio
async def test_stdio_server_returns_live_evidence() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        cwd=str(REPO_ROOT),
        env=dict(os.environ),
    )

    async with asyncio.timeout(120):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is False
    assert result.structuredContent is not None

    payload = result.structuredContent
    assert payload["retrieval_status"] in ("ok", "thin", "empty")
    assert payload["justifications"], "expected at least one numbered justification"
    for justification in payload["justifications"]:
        assert isinstance(justification["index"], int)
        assert justification["index"] >= 1
        assert justification["summary"]
        assert justification["citation"]["url"]
