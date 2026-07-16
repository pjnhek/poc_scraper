from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from src.clients.browserbase_client import NullBrowserbase
from src.clients.exa_client import ExaResult
from src.clients.protocols import ExaLike
from src.config import Settings
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import ThinDeps
from tests.functional.test_enrich import FakeExa


def _lifespan_factory(
    exa: ExaLike,
) -> Callable[[FastMCP], AbstractAsyncContextManager[ThinDeps]]:
    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[ThinDeps]:
        yield ThinDeps(exa=exa, browserbase=NullBrowserbase())

    return lifespan


class RaisingExa:
    """FakeExa variant whose search_about raises, for provider/unexpected error tests."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        raise self._exc

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return []


def _exa_about(text: str = "Notion is a workspace tool. " * 30) -> ExaResult:
    return ExaResult(
        url="https://notion.so/about",
        title="About Notion",
        snippet=text,
        published_at=None,
    )


def _exa_news(url: str = "https://techcrunch.com/notion") -> ExaResult:
    return ExaResult(
        url=url,
        title="Notion launches AI",
        snippet="Notion shipped a new AI feature today.",
        published_at=None,
    )


@pytest.mark.asyncio
async def test_happy_path_returns_structured_evidence_pack() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["retrieval_status"] == "ok"
    justifications = result.structuredContent["justifications"]
    assert len(justifications) > 0
    for j in justifications:
        assert j["index"] >= 1
        assert j["summary"]
        assert j["citation"]["url"]
    assert isinstance(result.structuredContent["about_text"], str)
    assert result.structuredContent["about_text"] != ""


@pytest.mark.asyncio
async def test_empty_retrieval_is_not_an_error() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "dead.example"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["retrieval_status"] == "empty"


@pytest.mark.parametrize(
    "domain",
    [
        "example.com/path",
        "example.com?query=yes",
        "example.com#fragment",
        "example.com?",
        "example.com#",
        "https://example.com/?",
        "https://example.com/#",
        "https://user@example.com",
        "example.com:443",
        "example.com\n",
        "example.com\t",
        "a..example.com",
        "-leading.example",
        "trailing-.example",
        f"{'a' * 64}.example",
        f"{'a' * 63}.{'b' * 63}.{'c' * 63}.{'d' * 62}.com",
        "127.0.0.1",
        "https://127.0.0.1/",
        "2001:db8::1",
        "[2001:db8::1]",
        "https://[2001:db8::1]/",
        "xn--a.example",
    ],
)
@pytest.mark.asyncio
async def test_invalid_domain_sanitized_error_before_provider_access(domain: str) -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": domain})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "invalid domain" in text
    assert "Traceback" not in text
    assert "/Users/" not in text
    assert exa.calls == []


@pytest.mark.asyncio
async def test_invalid_domain_error_is_bounded_without_raw_input_reflection() -> None:
    raw_suffix = "distinctive-raw-suffix.example"
    domain = f"{'x' * 1_000_000}.{raw_suffix}"
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": domain})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "invalid domain" in text
    assert len(text.encode("utf-8")) <= 256
    assert raw_suffix not in text
    assert exa.calls == []


@pytest.mark.asyncio
async def test_provider_failure_sanitized_error() -> None:
    exa = RaisingExa(httpx.HTTPError("connect boom secret-host"))
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "retrieval unavailable, try again" in text
    assert "secret-host" not in text


@pytest.mark.asyncio
async def test_unexpected_exception_sanitized_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exa = RaisingExa(RuntimeError("/private/path/leak"))
    app = build_server(lifespan=_lifespan_factory(exa))

    with caplog.at_level(logging.WARNING):
        async with create_connected_server_and_client_session(app) as client:
            result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "internal error" in text
    assert "/private/path/leak" not in text
    assert any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_annotations_and_description_over_the_wire() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    tool = listed.tools[0]
    assert tool.name == "get_account_evidence"
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.description is not None
    assert "[N]" in tool.description


def test_tier_logging_thin(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]

    with caplog.at_level(logging.INFO):
        tier = resolve_and_log_tier(settings)

    assert tier == "thin"
    assert any("thin" in record.message for record in caplog.records)


def test_tier_logging_full(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        deepseek_api_key="y",
        browserbase_api_key="z",
        browserbase_project_id="p",
    )

    with caplog.at_level(logging.INFO):
        tier = resolve_and_log_tier(settings)

    assert tier == "full"
    assert any("full" in record.message for record in caplog.records)
