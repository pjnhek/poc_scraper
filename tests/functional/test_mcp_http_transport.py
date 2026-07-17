"""Streamable HTTP transport verification: parity with stdio, header-driven
per-IP rationing, the fail-closed shared bucket, and DNS-rebinding rejection.

Everything here runs in-process over `httpx.ASGITransport`: no sockets, no
network. `httpx.ASGITransport` does not run Starlette lifespans, and the
StreamableHTTPSessionManager only starts inside that lifespan, so every test
enters it manually via `asgi_app.router.lifespan_context(asgi_app)` -- the
exact context a real ASGI server (uvicorn) would run.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import LATEST_PROTOCOL_VERSION, CallToolResult
from starlette.applications import Starlette

from src.config import Settings
from src.mcp_server.limits import DemoLimiter
from src.mcp_server.server import build_server
from tests.functional.test_enrich import FakeExa
from tests.functional.test_mcp_server import FakeClock, _exa_about, _exa_news, _lifespan_factory


def _asgi_client_factory(asgi_app: Starlette) -> Callable[..., httpx.AsyncClient]:
    """Match `McpHttpClientFactory`: routes every request through the ASGI
    app in-process, with a base_url host:port that passes the D-08
    allowlist ("127.0.0.1:8000").
    """

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="http://127.0.0.1:8000",
            headers=headers,
            timeout=timeout if timeout is not None else httpx.Timeout(30),
            auth=auth,
        )

    return factory


def _http_settings() -> Settings:
    return Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]


async def _call_get_account_evidence(
    asgi_app: Starlette, headers: dict[str, str] | None = None
) -> CallToolResult:
    async with (
        streamablehttp_client(
            "http://127.0.0.1:8000/mcp",
            headers=headers,
            httpx_client_factory=_asgi_client_factory(asgi_app),
        ) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        return await session.call_tool("get_account_evidence", {"domain": "notion.so"})


@pytest.mark.asyncio
async def test_transport_parity_same_tool_surface_over_http_and_stdio() -> None:
    settings = _http_settings()
    exa_http = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app_http = build_server(lifespan=_lifespan_factory(exa_http), settings=settings)
    asgi_app = app_http.streamable_http_app()

    async with asgi_app.router.lifespan_context(asgi_app):
        http_result = await _call_get_account_evidence(asgi_app)

    exa_stdio = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app_stdio = build_server(lifespan=_lifespan_factory(exa_stdio))
    async with create_connected_server_and_client_session(app_stdio) as client:
        stdio_result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert http_result.isError is False
    assert http_result.structuredContent is not None
    assert http_result.structuredContent["retrieval_status"] == "ok"
    assert len(http_result.structuredContent["justifications"]) > 0

    assert stdio_result.isError is False
    assert stdio_result.structuredContent is not None
    assert sorted(http_result.structuredContent.keys()) == sorted(
        stdio_result.structuredContent.keys()
    )


@pytest.mark.asyncio
async def test_per_ip_buckets_resolve_from_real_headers() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=1, daily_cap=100, clock=clock)
    settings = _http_settings()
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter), settings=settings)
    asgi_app = app.streamable_http_app()

    async with asgi_app.router.lifespan_context(asgi_app):
        first_ip_call_one = await _call_get_account_evidence(
            asgi_app, headers={"fly-client-ip": "203.0.113.9"}
        )
        first_ip_call_two = await _call_get_account_evidence(
            asgi_app, headers={"fly-client-ip": "203.0.113.9"}
        )
        second_ip_call_one = await _call_get_account_evidence(
            asgi_app, headers={"fly-client-ip": "198.51.100.7"}
        )

    assert first_ip_call_one.isError is False
    assert first_ip_call_two.isError is True
    text = first_ip_call_two.content[0].text  # type: ignore[union-attr]
    assert "rate limit reached, resets at " in text

    # Distinct fly-client-ip header reaches resolve_client_ip through the
    # real HTTP stack and lands in its own bucket (HOST-04): still allowed
    # even though the first IP is already exhausted.
    assert second_ip_call_one.isError is False


@pytest.mark.asyncio
async def test_fail_closed_shared_bucket_over_http_without_ip_headers() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=1, daily_cap=100, clock=clock)
    settings = _http_settings()
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter), settings=settings)
    asgi_app = app.streamable_http_app()

    async with asgi_app.router.lifespan_context(asgi_app):
        first = await _call_get_account_evidence(asgi_app)
        second = await _call_get_account_evidence(asgi_app)

    assert first.isError is False
    assert second.isError is True
    text = second.content[0].text  # type: ignore[union-attr]
    # Two headerless clients share the one fail-closed bucket (D-01/HOST-04).
    assert "rate limit reached, resets at " in text


@pytest.mark.asyncio
async def test_dns_rebinding_rejected_for_foreign_host() -> None:
    settings = _http_settings()
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa), settings=settings)
    asgi_app = app.streamable_http_app()

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "dns-rebinding-test", "version": "0.1"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    async with asgi_app.router.lifespan_context(asgi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app), base_url="http://evil.example"
        ) as evil_client:
            evil_response = await evil_client.post("/mcp", json=body, headers=headers)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app), base_url="http://127.0.0.1:8000"
        ) as ok_client:
            ok_response = await ok_client.post("/mcp", json=body, headers=headers)

    assert evil_response.status_code == 421
    assert ok_response.status_code != 421


@pytest.mark.asyncio
async def test_public_hostname_allowed_but_bare_bind_address_is_not() -> None:
    # D-07: a 0.0.0.0 bind (the Dockerfile/Fly path) must accept the real
    # client's Fly-forwarded Host header while never allowlisting the bind
    # address itself as a Host header value (12-REVIEW WR-03 follow-up).
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        mcp_http_host="0.0.0.0",
        mcp_public_hostname="poc-scraper-mcp.fly.dev",
    )
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa), settings=settings)
    asgi_app = app.streamable_http_app()

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "public-hostname-test", "version": "0.1"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    async with asgi_app.router.lifespan_context(asgi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="https://poc-scraper-mcp.fly.dev",
        ) as public_client:
            public_response = await public_client.post("/mcp", json=body, headers=headers)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app), base_url="http://0.0.0.0:8000"
        ) as bind_client:
            bind_response = await bind_client.post("/mcp", json=body, headers=headers)

    assert public_response.status_code != 421
    assert bind_response.status_code == 421


@pytest.mark.asyncio
async def test_public_hostname_is_allowed() -> None:
    # WR-02 intent via the D-05 mechanism: a real client sending the configured
    # public hostname must not be 421'd. The Host comes from mcp_public_hostname
    # (what clients actually send), not from the bind address.
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        mcp_http_host="0.0.0.0",
        mcp_public_hostname="app.internal",
    )
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa), settings=settings)
    asgi_app = app.streamable_http_app()

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "public-hostname-test", "version": "0.1"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    async with (
        asgi_app.router.lifespan_context(asgi_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app), base_url="http://app.internal"
        ) as client,
    ):
        response = await client.post("/mcp", json=body, headers=headers)

    assert response.status_code != 421


@pytest.mark.asyncio
async def test_bind_address_is_not_trusted_as_host() -> None:
    # Codex review: a bind/listener address must never become an accepted Host
    # header. Built with a routable bind and no public hostname (a config the
    # CLI guard normally blocks, exercised here in isolation), the allowlist
    # must still reject the bind value as a Host -- DNS-rebinding protection.
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        mcp_http_host="192.0.2.10",
    )
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa), settings=settings)
    asgi_app = app.streamable_http_app()

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "bind-host-test", "version": "0.1"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    async with (
        asgi_app.router.lifespan_context(asgi_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app), base_url="http://192.0.2.10:8000"
        ) as client,
    ):
        response = await client.post("/mcp", json=body, headers=headers)

    assert response.status_code == 421
