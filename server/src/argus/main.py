"""Entry point — starts both MCP server (stdio) and HTTP server (background thread)."""

import logging
import sys
import threading

import uvicorn

from argus.api.server import create_app
from argus.config import settings
from argus.mcp.tools import create_mcp_server
from argus.store.memory import InMemoryStore


def _run_http(app, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger = logging.getLogger("argus")

    store = InMemoryStore(settings)
    mcp = create_mcp_server(store)
    app = create_app(store, settings)

    # Start HTTP server in daemon thread
    http_thread = threading.Thread(
        target=_run_http,
        args=(app, settings.host, settings.port),
        daemon=True,
    )
    http_thread.start()

    # Log connection info to stderr (stdout is reserved for MCP stdio)
    print(f"Argus HTTP server: http://{settings.host}:{settings.port}", file=sys.stderr)
    print(f"Auth token: {settings.auth_token}", file=sys.stderr)
    logger.info("MCP server starting on stdio...")

    # Run MCP server on stdio (blocks)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

