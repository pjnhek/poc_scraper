"""HOST-05 regression coverage: cross-cutting banned-substring assertion over
the get_account_evidence tool error paths (invalid domain, provider failure,
unexpected internal exception). Offline counterpart to the phase's live D-14
real-client check; this file is the repeatable regression net.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import TypeAdapter, ValidationError

from src.clients.exa_client import ExaResult
from src.mcp_server.scoring import ScoreResult
from src.mcp_server.server import build_server
from tests.functional.test_enrich import FakeExa
from tests.functional.test_mcp_server import _lifespan_factory

BANNED_SUBSTRINGS = (
    "Traceback",
    "EXA_API_KEY",
    "DEEPSEEK_API_KEY",
    "NVIDIA_API_KEY",
    "BROWSERBASE_API_KEY",
    "site-packages",
    "sk-test-secret-fragment",
)


class RaisingExa:
    """Exa-shaped stub whose search_about and search_news both raise, for the
    provider-failure error path."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        raise self._exc

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        raise self._exc


class PoisonedExa:
    """Exa-shaped stub whose search_about raises a RuntimeError carrying a
    deliberately poisoned message (fake secret fragment plus a fake
    traceback-like line), to prove the catch-all path drops the message
    rather than echoing it."""

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        raise RuntimeError(
            'EXA_API_KEY=sk-test-secret-fragment\n  File "app.py", line 42, in call\n'
        )

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return []


def _assert_sanitized(text: str) -> None:
    for banned in BANNED_SUBSTRINGS:
        assert banned not in text


async def test_invalid_domain_error_is_sanitized() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "not-a-domain"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    _assert_sanitized(text)


async def test_provider_failure_error_is_sanitized() -> None:
    exa = RaisingExa(httpx.HTTPError("boom"))
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "retrieval unavailable, try again" in text
    _assert_sanitized(text)


async def test_unexpected_internal_error_is_sanitized() -> None:
    exa = PoisonedExa()
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "internal error, try again" in text
    _assert_sanitized(text)


async def test_score_account_range_violation_error_is_sanitized() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {"support_volume": 6, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    _assert_sanitized(text)


async def test_score_account_unexpected_internal_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """WR-01: score_account's first call is what triggers the lazy
    get_config(); a missing configs/icp.yaml raises FileNotFoundError naming
    the server filesystem path, which FastMCP surfaces verbatim without a
    catch-all. Mirrors the Codex repro that delivered a poisoned RuntimeError
    to the client unmodified."""

    def _raise(**kwargs: object) -> ScoreResult:
        raise RuntimeError("/private/secret/config.yaml EXA_API_KEY=sk-test-secret-fragment")

    monkeypatch.setattr("src.mcp_server.server.build_score_result", _raise)
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    with caplog.at_level(logging.WARNING):
        async with create_connected_server_and_client_session(app) as client:
            result = await client.call_tool(
                "score_account",
                {"support_volume": 3, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
            )

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "internal error, try again" in text
    assert "/private/secret/config.yaml" not in text
    _assert_sanitized(text)
    assert any(record.levelno == logging.WARNING for record in caplog.records)


async def test_score_account_pydantic_validation_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-01 subtlety: pydantic's ValidationError IS a ValueError, so a naive
    `except ValueError: raise` passthrough would deliver an ICPConfig
    validation failure (which quotes config file content) verbatim. It must
    fall into the sanitized path; only the per-axis 1-5 message passes
    through."""
    captured: ValidationError | None = None
    try:
        TypeAdapter(int).validate_python("sk-test-secret-fragment")
    except ValidationError as exc:
        captured = exc
    assert captured is not None
    assert "sk-test-secret-fragment" in str(captured)

    def _raise(**kwargs: object) -> ScoreResult:
        assert captured is not None
        raise captured

    monkeypatch.setattr("src.mcp_server.server.build_score_result", _raise)
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {"support_volume": 3, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "internal error, try again" in text
    _assert_sanitized(text)


async def test_score_account_type_violation_error_is_sanitized() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        string_result = await client.call_tool(
            "score_account",
            {"support_volume": "abc", "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )
        fractional_result = await client.call_tool(
            "score_account",
            {"support_volume": 3.5, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert string_result.isError is True
    assert fractional_result.isError is True
    _assert_sanitized(string_result.content[0].text)  # type: ignore[union-attr]
    _assert_sanitized(fractional_result.content[0].text)  # type: ignore[union-attr]
