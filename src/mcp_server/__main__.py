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

from src.config import get_settings
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import make_thin_lifespan

log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    args = parser.parse_args()

    settings = get_settings()
    resolve_and_log_tier(settings)
    app = build_server(
        lifespan=make_thin_lifespan(settings),
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
