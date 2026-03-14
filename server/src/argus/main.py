"""Entry point — starts MCP server and HTTP server.

Transport modes (ARGUS_TRANSPORT env var):
  stdio (default) — MCP on stdio, HTTP in background thread. For Cursor/Claude Code.
  sse             — HTTP + MCP SSE on one port. For remote/cloud connections.
  all             — Both: HTTP + MCP SSE on one port, PLUS MCP stdio. For local dev with both.
"""

import logging
import subprocess
import sys
import threading

import uvicorn

from argus.api.server import create_app
from argus.config import settings
from argus.core.commands import CommandQueue
from argus.mcp.tools import create_mcp_server
from argus.store.memory import InMemoryStore


def _run_http(app, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode(), check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            # Linux — try xclip, then xsel, then wl-copy
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["wl-copy"]]:
                try:
                    subprocess.run(cmd, input=text.encode(), check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception:
        return False


def main() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger = logging.getLogger("argus")

    transport = settings.transport.lower()
    if transport not in ("stdio", "sse", "all"):
        print(f"Unknown transport '{transport}'. Use 'stdio', 'sse', or 'all'.", file=sys.stderr)
        sys.exit(1)

    store = InMemoryStore(settings)
    command_queue = CommandQueue()
    mcp = create_mcp_server(store, command_queue)

    use_stdio = transport in ("stdio", "all")
    use_sse = transport in ("sse", "all")

    # Build FastAPI app, mounting MCP SSE if needed
    app = create_app(store, settings, mcp=mcp if use_sse else None, command_queue=command_queue)

    # Copy token to clipboard
    if _copy_to_clipboard(settings.auth_token):
        print("✅ Auth token copied to clipboard — paste it in the extension popup", file=sys.stderr)
    else:
        print(f"Auth token: {settings.auth_token}", file=sys.stderr)

    # Log connection info to stderr (stdout is reserved for MCP stdio)
    print(f"Argus HTTP server: http://{settings.host}:{settings.port}", file=sys.stderr)
    print(f"Transport: {transport}", file=sys.stderr)
    if use_sse:
        print(f"MCP SSE endpoint: http://{settings.host}:{settings.port}/mcp/sse", file=sys.stderr)

    if use_stdio:
        # HTTP server in background, MCP stdio in foreground (blocks)
        http_thread = threading.Thread(target=_run_http, args=(app, settings.host, settings.port), daemon=True)
        http_thread.start()
        logger.info("MCP server starting on stdio...")
        mcp.run(transport="stdio")
    else:
        # SSE-only: just run the HTTP server (MCP is mounted on it)
        logger.info("MCP server available via SSE at /mcp/sse")
        uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
