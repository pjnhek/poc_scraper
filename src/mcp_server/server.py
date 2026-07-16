from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Literal

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations
from pydantic import ValidationError
from starlette.requests import Request

from src.clients.browserbase_client import BrowserbaseError
from src.config import Settings
from src.mcp_server.evidence import build_evidence_pack
from src.mcp_server.limits import DAILY_CAP_MESSAGE, resolve_client_ip
from src.mcp_server.wiring import ThinDeps
from src.models import Account, EvidencePack

log = logging.getLogger(__name__)


def resolve_and_log_tier(settings: Settings) -> Literal["thin", "full"]:
    """Resolve the MCP server's capability tier once at startup and log it.

    A small named function (rather than inlining settings.mcp_tier() at the
    call site) so functional tests can assert the logged tier via caplog
    (MCP-06). settings.mcp_tier()'s RuntimeError is allowed to propagate;
    its message already lists the missing EXA_API_KEY.
    """
    tier = settings.mcp_tier()
    sub_mode = (
        "exa+browserbase"
        if settings.browserbase_api_key and settings.browserbase_project_id
        else "exa-only"
    )
    log.info("mcp server tier resolved: %s (%s)", tier, sub_mode)
    return tier


async def get_account_evidence(
    domain: str, ctx: Context[ServerSession, ThinDeps, Request]
) -> EvidencePack:
    """Retrieve numbered, cited evidence for a company domain (about page and
    last-90-day news). Every downstream claim you build from this evidence
    MUST cite a justification by its [N] index; never state a fact without a
    matching index from `justifications`. `retrieval_status` tells you
    whether the evidence is strong enough to reason from: 'ok' means solid
    evidence, 'thin' means sparse evidence, 'empty' means this account
    cannot be researched, do not fabricate claims for it.
    """
    try:
        account = Account(domain=domain)
    except ValidationError as exc:
        msg = exc.errors()[0]["msg"]
        prefix = "Value error, "
        if msg.startswith(prefix):
            msg = msg[len(prefix) :]
        raise ValueError(msg) from None

    deps = ctx.request_context.lifespan_context

    if deps.limiter is not None:
        # D-04: quota is consumed at exactly this point, after validation
        # and before retrieval, so invalid domains and refused calls never
        # reach Exa. Over stdio and the in-memory harness the request is
        # None, so this fails closed into the shared bucket (D-01).
        client_ip = resolve_client_ip(ctx.request_context.request)
        decision = await deps.limiter.check_and_consume(client_ip)
        if not decision.allowed:
            raise ValueError(decision.message) from None

    try:
        return await build_evidence_pack(account, exa=deps.exa, browserbase=deps.browserbase)
    except (httpx.HTTPError, BrowserbaseError) as exc:
        log.warning("evidence retrieval failed [%s] for %s: %s", type(exc).__name__, domain, exc)
        if (
            deps.limiter is not None
            and isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in (402, 429)
        ):
            # D-07: in demo mode, Exa credit exhaustion surviving tenacity's
            # retries borrows the daily-cap wording so the public URL looks
            # rationed, never broken.
            raise ValueError(DAILY_CAP_MESSAGE) from None
        raise ValueError("retrieval unavailable, try again") from None
    except Exception as exc:
        log.warning(
            "unexpected error in get_account_evidence for %s: %s", domain, exc, exc_info=True
        )
        raise ValueError("internal error, try again") from None


def build_server(
    lifespan: Callable[[FastMCP], AbstractAsyncContextManager[ThinDeps]],
) -> FastMCP:
    server = FastMCP("poc-scraper", lifespan=lifespan)
    server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
        get_account_evidence
    )
    return server
