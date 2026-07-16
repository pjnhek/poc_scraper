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
import asyncio

from src.config import get_settings
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import make_thin_lifespan


def main() -> int:
    settings = get_settings()
    resolve_and_log_tier(settings)
    app = build_server(lifespan=make_thin_lifespan(settings))
    asyncio.run(app.run_stdio_async())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
