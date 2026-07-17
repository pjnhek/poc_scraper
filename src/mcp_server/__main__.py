import logging
import sys

# Configure stderr-first logging as the literal first statement, before any
# project import: stdio transport reserves stdout exclusively for JSON-RPC
# frames (Pitfall 1) and some project modules log at import time.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# ruff: noqa: E402  (imports below intentionally follow logging.basicConfig)
import argparse
import asyncio

from src.config import Settings, get_settings
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import make_full_lifespan, make_thin_lifespan

log = logging.getLogger(__name__)


def guard_full_tier_http_exposure(settings: Settings, transport: str, tier: str) -> None:
    """Refuse to serve the full tier over HTTP without an explicit opt-in.

    WR-03: research_account_full performs no quota check at all (Deps.limiter
    is always None on the full-tier path) and the endpoint has no auth, so
    "forget to demote to thin" must not fail open into unmetered public LLM
    spend. Demo mode already forces tier back to "thin" before this runs
    (Settings.mcp_tier), so this only ever fires for a deliberately full-tier
    deployment; MCP_ALLOW_FULL_HTTP=true is that deployment's explicit
    acknowledgement. stdio full tier and demo/thin HTTP are untouched.

    A small named function (rather than inlining the check in main()) so it
    can be unit-tested without spinning up a server or parsing argv.
    """
    if transport == "http" and tier == "full" and not settings.mcp_allow_full_http:
        raise SystemExit(
            "refusing to serve the full tier over HTTP without MCP_ALLOW_FULL_HTTP=true "
            "(research_account_full has no rate limiting and no auth over HTTP). "
            "Set MCP_ALLOW_FULL_HTTP=true only for a deliberate, trusted full-tier "
            "HTTP deployment; use --transport stdio or MCP_DEMO_MODE=true otherwise."
        )


def guard_non_loopback_requires_public_hostname(settings: Settings, transport: str) -> None:
    """Refuse to bind non-loopback HTTP without a public hostname configured.

    D-06: a 0.0.0.0 (or other non-loopback) bind with no MCP_PUBLIC_HOSTNAME
    means real clients' Host headers would 421 against the DNS-rebinding
    allowlist (server.py's TransportSecuritySettings), or worse, get
    silently misconfigured if the check is skipped. Loopback binds keep
    Phase 11's existing localhost allowlist untouched, so local
    make mcp-http/make mcp-demo workflows are unaffected.

    A small named function (rather than inlining the check in main()) so it
    can be unit-tested without spinning up a server or parsing argv.
    """
    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if (
        transport == "http"
        and settings.mcp_http_host not in loopback_hosts
        and not settings.mcp_public_hostname
    ):
        raise SystemExit(
            f"refusing to bind {settings.mcp_http_host!r} without MCP_PUBLIC_HOSTNAME set "
            "(a non-loopback bind with no public hostname means real clients' Host headers "
            "would 421 against the DNS-rebinding allowlist, or worse, get silently "
            "misconfigured). Set MCP_PUBLIC_HOSTNAME to the externally-visible hostname, "
            "or bind to 127.0.0.1/localhost for local development."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    args = parser.parse_args()

    settings = get_settings()
    tier = resolve_and_log_tier(settings)
    guard_full_tier_http_exposure(settings, args.transport, tier)
    guard_non_loopback_requires_public_hostname(settings, args.transport)
    # No key validation needed here: mcp_tier() == "full" already implies
    # writer/judge/Browserbase keys are present, and open_deps defers key
    # checks by design.
    lifespan = make_full_lifespan(settings) if tier == "full" else make_thin_lifespan(settings)
    app = build_server(
        lifespan=lifespan,
        tier=tier,
        settings=settings if args.transport == "http" else None,
    )

    if args.transport == "http":
        log.info(
            "mcp transport: streamable http on %s:%d",
            settings.mcp_http_host,
            settings.mcp_http_port,
        )
    if settings.mcp_demo_mode:
        log.info(
            "mcp demo limits active: %d calls/ip/hour, %d/day global, exa results clamp %d",
            settings.mcp_demo_ip_limit,
            settings.mcp_demo_daily_cap,
            settings.mcp_demo_exa_results,
        )

    if args.transport == "http":
        asyncio.run(app.run_streamable_http_async())
    else:
        asyncio.run(app.run_stdio_async())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
