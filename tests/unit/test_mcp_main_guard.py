"""Unit tests for guard_full_tier_http_exposure (WR-03).

Calls the guard function directly (no server, no argv parsing) so the
refusal/opt-in decision is asserted in isolation, per the unit-test layer
(CLAUDE.md): pure function, crafted inputs, no I/O.
"""

from __future__ import annotations

import pytest

from src.config import Settings
from src.mcp_server.__main__ import guard_full_tier_http_exposure


def test_refuses_full_tier_over_http_without_opt_in() -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]

    with pytest.raises(SystemExit) as exc_info:
        guard_full_tier_http_exposure(settings, transport="http", tier="full")

    message = str(exc_info.value)
    assert "MCP_ALLOW_FULL_HTTP" in message
    assert "no rate limiting" in message


def test_allows_full_tier_over_http_with_explicit_opt_in() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, exa_api_key="x", mcp_allow_full_http=True
    )

    guard_full_tier_http_exposure(settings, transport="http", tier="full")


def test_stdio_full_tier_is_unaffected_by_the_guard() -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]

    guard_full_tier_http_exposure(settings, transport="stdio", tier="full")


def test_thin_tier_over_http_is_unaffected_by_the_guard() -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]

    guard_full_tier_http_exposure(settings, transport="http", tier="thin")


def test_demo_mode_thin_tier_over_http_is_unaffected_by_the_guard() -> None:
    # Settings.mcp_tier() already demotes demo mode to "thin" before this
    # guard ever sees "tier"; this test documents that the guard itself
    # imposes no additional restriction on the demo/thin HTTP path.
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, exa_api_key="x", mcp_demo_mode=True
    )

    guard_full_tier_http_exposure(settings, transport="http", tier="thin")
