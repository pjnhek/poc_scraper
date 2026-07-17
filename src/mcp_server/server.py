from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Literal

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import ValidationError
from starlette.requests import Request

from evals.report import REPORT_PATH
from src.clients.browserbase_client import BrowserbaseError
from src.config import Settings
from src.icp_config import DEFAULT_CONFIG_PATH
from src.mcp_server.evidence import build_evidence_pack
from src.mcp_server.limits import DAILY_CAP_MESSAGE, resolve_client_ip
from src.mcp_server.wiring import EvidenceDeps
from src.models import Account, EvidencePack, ScoredAccount
from src.pipeline import Deps, process_account

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


def _sanitized_validation_message(exc: ValidationError) -> str:
    """Strip pydantic's 'Value error, ' prefix from an Account validation error.

    Shared by get_account_evidence and research_account_full so both tools
    validate through Account and surface identical, sanitized wording for
    an invalid domain.
    """
    msg = exc.errors()[0]["msg"]
    prefix = "Value error, "
    if msg.startswith(prefix):
        msg = msg[len(prefix) :]
    return msg


async def get_account_evidence(
    domain: str, ctx: Context[ServerSession, EvidenceDeps, Request]
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
        raise ValueError(_sanitized_validation_message(exc)) from None

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


def read_icp_rubric() -> str:
    """Serve configs/icp.yaml verbatim so any MCP client can inspect the ICP
    rubric this server scores against. Reads from disk on every call, no
    startup caching, so an edited rubric is visible without a server restart
    (D-07).
    """
    try:
        return DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("icp rubric resource unavailable: %s", exc)
        return "resource unavailable: the ICP rubric could not be read on the server."


def read_eval_report() -> str:
    """Serve evals/REPORT.md verbatim so any MCP client can inspect the eval
    calibration narrative backing this server's groundedness claims. Reads
    from disk on every call, no startup caching, so a refreshed report is
    visible without a server restart (D-07).
    """
    try:
        return REPORT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("eval report resource unavailable: %s", exc)
        return "resource unavailable: the eval calibration report could not be read on the server."


def research_account(domain: str) -> str:
    """Guide rubric-based ICP research for one domain with hard [N]-citation
    discipline: never fabricate, drop any uncited claim.
    """
    return (
        f"Research {domain} for ICP fit. Read the icp://rubric resource for the "
        "current axis definitions and weights. Call "
        f"get_account_evidence({domain!r}) to retrieve numbered justifications. "
        "Score each rubric axis 1-5 using the stated weights, propose the top 3 "
        "buyer personas, and draft an outreach hook per persona. Every claim MUST "
        "cite an [N] index from justifications; drop any claim without a matching "
        "index. If retrieval_status is 'empty', state that the account cannot be "
        "researched, never fabricate."
    )


async def research_account_full(
    domain: str, ctx: Context[ServerSession, Deps, Request], run_eval: bool = True
) -> ScoredAccount:
    """Run the complete grounded research pipeline for one domain (full tier
    only): enrich, score against the ICP rubric, propose the top 3 buyer
    personas, draft cited outreach hooks, and (unless run_eval=False)
    judge-evaluate groundedness. Outreach claims cite [N] justification
    indices that resolve into the returned `enrichment.justifications`,
    exactly like `get_account_evidence`'s numbered evidence.

    `status` is one of four values: `clean` (grounded output produced,
    judged or not), `hook_suppressed` (no citeable claims survived, common
    on thin/empty evidence), `low_groundedness` (the judge flagged weak
    citation coverage), or `judge_failed` (the eval layer itself errored --
    never returned when run_eval=False, since the judge never ran).

    Takes 30-60 seconds for the full pipeline; run_eval=False skips the
    judge call for roughly half the latency. Progress is reported at each
    stage boundary via ctx.report_progress for clients that render it;
    clients that ignore it lose nothing.
    """
    try:
        account = Account(domain=domain)
    except ValidationError as exc:
        raise ValueError(_sanitized_validation_message(exc)) from None

    deps = ctx.request_context.lifespan_context

    if not hasattr(deps, "enricher"):
        # WR-01: research_account_full is only ever registered when tier=="full"
        # (build_server), which the caller must pair with make_full_lifespan's
        # full Deps bundle. A thin lifespan (ThinDeps) has no .enricher at all;
        # catching that here, before the catch-all below, turns a wiring bug
        # into an explicit misconfiguration message instead of a sanitized
        # "internal error, try again" masquerading as a transient fault.
        log.error(
            "research_account_full called with a thin lifespan for %s: "
            "server wiring bug, tier='full' must be paired with make_full_lifespan",
            domain,
        )
        raise RuntimeError(
            "server misconfiguration: research_account_full is registered (tier='full') "
            "but the lifespan context has no enricher/scorer/etc (a thin Deps bundle). "
            "Pair tier='full' with make_full_lifespan, not make_thin_lifespan."
        )

    stages = (
        ("enrich", "score", "contacts", "outreach", "eval")
        if run_eval
        else ("enrich", "score", "contacts", "outreach")
    )
    total = len(stages)
    seen = {"n": 0}

    async def on_stage(stage: str) -> None:
        seen["n"] += 1
        try:
            await ctx.report_progress(seen["n"], total, message=f"{stage} complete")
        except Exception as exc:
            # WR-02: progress is advisory ("clients that ignore it lose
            # nothing," per this tool's own docstring). A client that
            # requests it and then misbehaves (disconnects mid-run, closed
            # stdio) must not discard the completed pipeline run and the
            # writer/judge tokens already spent on it. process_account's
            # on_stage call sites sit deliberately outside its per-stage
            # try/except blocks, so this is the one place that owns "the
            # progress send itself failed" and keeps it from propagating.
            log.warning("progress notification failed at stage %s for %s: %s", stage, domain, exc)

    try:
        return await process_account(account, deps, run_eval=run_eval, on_stage=on_stage)
    except Exception as exc:
        # process_account already isolates per-stage domain failures and
        # returns a degraded-but-successful ScoredAccount (D-03); anything
        # escaping it here is genuinely unexpected -- the same catch-all
        # discipline as get_account_evidence's own last except clause.
        log.warning(
            "unexpected error in research_account_full for %s: %s", domain, exc, exc_info=True
        )
        raise ValueError("internal error, try again") from None


def build_server(
    lifespan: Callable[[FastMCP], AbstractAsyncContextManager[EvidenceDeps]],
    tier: Literal["thin", "full"] = "thin",
    settings: Settings | None = None,
) -> FastMCP:
    """Construct the FastMCP server for either transport.

    `settings=None` (stdio path, and every pre-existing test) builds the
    server exactly as before: zero behavior change. `settings` provided
    (HTTP path) additionally passes host/port/stateless/transport-security
    kwargs sourced from this project's own Settings, never the SDK's
    parallel FASTMCP_*-prefixed env config, so there is exactly one source
    of truth (HOST-02, D-08, D-09).

    `tier` gates registration of `research_account_full` and is deliberately
    independent of `settings`, which stays `None` on the stdio path for
    transport-kwarg reasons only (RESEARCH Pitfall 1). `tier` defaults to
    `"thin"` so every pre-existing call site keeps registering exactly one
    tool, unchanged. The caller must always derive `tier` from
    `settings.mcp_tier()` (via `resolve_and_log_tier`), never from an
    independent key-presence check -- that is what keeps `MCP_DEMO_MODE`
    hiding the full tool even when full-tier keys are present (RESEARCH
    Pitfall 4).
    """
    if settings is None:
        server = FastMCP("poc-scraper", lifespan=lifespan)
    else:
        # The allowlist is explicit rather than relying on the SDK's
        # auto-built localhost wildcard so it is greppable in project code
        # and gives a single place to set the public hostname (D-08). Only
        # two kinds of value are trusted as a Host header: the loopback dev
        # entries below (so the default bind keeps working locally) and the
        # validated public hostname a real client actually sends, sourced
        # from settings.mcp_public_hostname (D-05). The BIND address
        # (settings.mcp_http_host) is deliberately NOT added: a listener
        # address is not a Host header, and folding a routable bind value
        # into the allowlist would widen the DNS-rebinding surface for no
        # gain (HOST-06, D-07). This supersedes the earlier WR-02 bind
        # threading, now that D-05 supplies the client-facing hostname
        # separately. stateless_http=True avoids long-lived per-session
        # tasks on an unauthenticated public endpoint and is spec-compliant
        # for standard clients (RESEARCH.md A1: a one-kwarg flip if a
        # Phase 13 client misbehaves).
        allowed_hosts = [
            f"127.0.0.1:{settings.mcp_http_port}",
            f"localhost:{settings.mcp_http_port}",
        ]
        allowed_origins = [
            f"http://127.0.0.1:{settings.mcp_http_port}",
            f"http://localhost:{settings.mcp_http_port}",
        ]
        if settings.mcp_public_hostname:
            # Bare hostname: Fly's edge forwards the client's original Host
            # header verbatim, and HTTPS on default port 443 omits the port
            # suffix (RESEARCH Pitfall 3). ":443" is added as defense-in-depth
            # for a client that does send an explicit port.
            allowed_hosts.append(settings.mcp_public_hostname)
            allowed_hosts.append(f"{settings.mcp_public_hostname}:443")
            allowed_origins.append(f"https://{settings.mcp_public_hostname}")
        server = FastMCP(
            "poc-scraper",
            lifespan=lifespan,
            host=settings.mcp_http_host,
            port=settings.mcp_http_port,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins,
            ),
        )
    server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
        get_account_evidence
    )
    server.resource("icp://rubric", mime_type="application/yaml")(read_icp_rubric)
    server.resource("icp://eval-report", mime_type="text/markdown")(read_eval_report)
    server.prompt()(research_account)
    if tier == "full":
        server.tool(
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
            description=(
                "Runs the complete grounded research pipeline for one domain: "
                "enrich, score against the ICP rubric, propose personas, draft "
                "cited outreach, and judge-eval groundedness. Outreach claims "
                "cite [N] justification indices that resolve into the returned "
                "enrichment.justifications. Takes 30-60 seconds; run_eval=False "
                "skips the judge for roughly half the latency."
            ),
        )(research_account_full)
    return server
