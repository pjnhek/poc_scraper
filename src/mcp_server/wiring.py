from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

import httpx
from mcp.server.fastmcp import FastMCP

from src.clients.browserbase_client import BrowserbaseClient, NullBrowserbase
from src.clients.exa_client import ExaClient, ExaResult
from src.clients.protocols import BrowserbaseLike, ExaLike
from src.config import Settings
from src.mcp_server.limits import DemoLimiter
from src.pipeline import Deps, open_deps


class DemoClampedExa:
    """ExaLike wrapper that caps num_results in demo mode (D-01/D-02/D-03).

    Structural (not inheriting ExaLike), matching the codebase's protocol
    convention. Clamp semantics are min(), not replace: a caller asking for
    fewer results than the clamp still gets fewer -- the clamp only caps
    spend, it never inflates a request.
    """

    def __init__(self, inner: ExaLike, max_results: int) -> None:
        self._inner = inner
        self._max_results = max_results

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        return await self._inner.search_about(
            domain, num_results=min(num_results, self._max_results)
        )

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return await self._inner.search_news(
            domain, days=days, num_results=min(num_results, self._max_results)
        )


@dataclass(frozen=True)
class ThinDeps:
    exa: ExaLike
    browserbase: BrowserbaseLike
    limiter: DemoLimiter | None = None


class EvidenceDeps(Protocol):
    """Structural contract for get_account_evidence's lifespan context.

    Names exactly the three attributes get_account_evidence reads: exa,
    browserbase, limiter. Property members (not plain attributes) are
    load-bearing: property return types are covariant, so the frozen
    ThinDeps (limiter: DemoLimiter | None) and the extended Deps from
    src.pipeline (limiter typed bare None, keeping pipeline.py MCP-free)
    both satisfy this protocol structurally under strict mypy without either
    inheriting from it -- this is the codebase's existing *Like protocol
    convention (ExaLike, BrowserbaseLike) applied to the lifespan-context
    shape instead of a client shape.
    """

    @property
    def exa(self) -> ExaLike: ...

    @property
    def browserbase(self) -> BrowserbaseLike: ...

    @property
    def limiter(self) -> DemoLimiter | None: ...


def make_thin_lifespan(
    settings: Settings,
) -> Callable[[FastMCP], AbstractAsyncContextManager[ThinDeps]]:
    """Build the thin-tier lifespan factory for the given settings.

    Settings are resolved once by the caller (the __main__ entrypoint) so
    tests can build a lifespan around fakes without touching env vars. The
    thin tier has no LLM clients (Phase 9 D-04), so there is no counterpart
    to open_deps's finally-block LLM teardown; the `async with` on the
    shared httpx.AsyncClient is the only teardown needed.
    """

    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[ThinDeps]:
        async with httpx.AsyncClient(timeout=60.0) as http:
            exa: ExaLike = ExaClient(api_key=settings.exa_api_key, client=http)
            bb: BrowserbaseLike
            if settings.browserbase_api_key and settings.browserbase_project_id:
                bb = BrowserbaseClient(
                    api_key=settings.browserbase_api_key,
                    project_id=settings.browserbase_project_id,
                    client=http,
                )
            else:
                bb = NullBrowserbase()

            limiter: DemoLimiter | None
            if settings.mcp_demo_mode:
                # Demo mode rations and clamps regardless of transport
                # (D-01/D-02/D-03): the limiter presence, not the transport,
                # is what downstream code checks.
                exa = DemoClampedExa(exa, max_results=settings.mcp_demo_exa_results)
                # Demo mode may spend rationed Exa credit but must never trigger
                # paid Browserbase fallback, per the design spec's demo scope
                # clamps -- override any key-aware BrowserbaseClient above.
                bb = NullBrowserbase()
                limiter = DemoLimiter(
                    ip_limit=settings.mcp_demo_ip_limit,
                    daily_cap=settings.mcp_demo_daily_cap,
                )
            else:
                limiter = None

            yield ThinDeps(exa=exa, browserbase=bb, limiter=limiter)

    return lifespan


def make_full_lifespan(
    settings: Settings,
) -> Callable[[FastMCP], AbstractAsyncContextManager[Deps]]:
    """Build the full-tier lifespan factory for the given settings.

    Full tier is never demo mode (locked decision), so no limiter/clamp/
    NullBrowserbase wiring belongs here -- Deps.limiter stays None by its
    field default. Delegating entirely to open_deps means the full-tier
    server runs one shared httpx connection pool (not a second one built
    independently, as make_thin_lifespan does) and inherits open_deps's
    replay/record branching for free: a second, independently-constructed
    client stack would silently skip replay fixtures for get_account_evidence
    while research_account_full correctly replayed from disk in the same
    process (RESEARCH.md "Alternatives Considered").
    """

    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[Deps]:
        async with open_deps(settings) as deps:
            yield deps

    return lifespan
