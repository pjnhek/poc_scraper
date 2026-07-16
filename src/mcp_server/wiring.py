from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

import httpx
from mcp.server.fastmcp import FastMCP

from src.clients.browserbase_client import BrowserbaseClient, NullBrowserbase
from src.clients.exa_client import ExaClient
from src.clients.protocols import BrowserbaseLike, ExaLike
from src.config import Settings


@dataclass(frozen=True)
class ThinDeps:
    exa: ExaLike
    browserbase: BrowserbaseLike


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
            yield ThinDeps(exa=exa, browserbase=bb)

    return lifespan
