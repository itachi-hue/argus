"""Command queue for agent-initiated browser actions.

THREADING MODEL:
  The MCP server runs on the MAIN thread (event loop A — stdio).
  The HTTP/WebSocket server runs on a BACKGROUND thread (event loop B — uvicorn).

  This means:
    - wait_for_result() creates Futures on loop A (main thread)
    - set_result() is called from loop B (HTTP thread)
    - We MUST use loop.call_soon_threadsafe() to resolve Futures cross-thread,
      otherwise the main event loop never wakes up and tools appear to hang.

Flow (WebSocket):
  1. MCP tool calls enqueue() — pushes command over WebSocket instantly
  2. Extension receives it, executes via chrome.scripting.executeScript
  3. Extension sends result back over the same WebSocket
  4. set_result() uses call_soon_threadsafe() to resolve the Future on the MCP loop
  5. MCP tool returns immediately

Fallback (HTTP polling — kept for backwards compatibility):
  1. If no WebSocket is connected, commands are queued in _pending
  2. Extension polls GET /api/commands/pending
  3. Extension reports result via POST /api/commands/{id}/result
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class CommandQueue:
    def __init__(self, command_timeout: float = 30.0):
        self._timeout = command_timeout
        # WebSocket connection to the extension
        self._ws: WebSocket | None = None
        # asyncio.Future for each pending command — resolved when result arrives
        self._futures: dict[str, asyncio.Future] = {}
        # Fallback: HTTP polling (only used when no WebSocket)
        self._pending: dict[str, dict] = {}
        self._results: dict[str, dict] = {}

    @property
    def has_ws(self) -> bool:
        return self._ws is not None

    def set_ws(self, ws: WebSocket) -> None:
        """Register a live WebSocket connection from the extension."""
        self._ws = ws
        logger.info("Extension WebSocket connected")

    def clear_ws(self) -> None:
        """Called when the WebSocket disconnects."""
        self._ws = None
        logger.info("Extension WebSocket disconnected")
        # Fail any pending futures — extension is gone
        for cmd_id, future in list(self._futures.items()):
            if not future.done():
                try:
                    loop = future.get_loop()
                    loop.call_soon_threadsafe(future.set_result, {
                        "success": False,
                        "error": "Extension disconnected",
                    })
                except RuntimeError:
                    pass  # Loop already closed
        self._futures.clear()

    async def enqueue(self, action: str, params: dict) -> str:
        """Add a command. If WebSocket is connected, push immediately."""
        cmd_id = uuid.uuid4().hex[:8]
        cmd = {"id": cmd_id, "action": action, "params": params}

        if self._ws is not None:
            # Push instantly over WebSocket
            try:
                await self._ws.send_json(cmd)
                return cmd_id
            except Exception:
                # WebSocket broke — fall through to HTTP fallback
                self._ws = None
                logger.warning("WebSocket send failed, falling back to HTTP polling")

        # Fallback: queue for HTTP polling
        self._pending[cmd_id] = {**cmd, "created_at": time.time()}
        return cmd_id

    def set_result(self, command_id: str, result: dict) -> bool:
        """Store the result of a command (called from WebSocket or HTTP POST).

        IMPORTANT: This is called from the HTTP thread, but the Future lives on
        the MCP thread's event loop. We use call_soon_threadsafe() to properly
        wake up the MCP event loop and resolve the Future instantly.
        """
        future = self._futures.pop(command_id, None)
        if future and not future.done():
            try:
                loop = future.get_loop()
                loop.call_soon_threadsafe(future.set_result, result)
            except RuntimeError:
                # Loop is closed — store as fallback
                self._results[command_id] = result
            return True
        # Fallback: store for later pickup
        self._results[command_id] = result
        return True

    async def wait_for_result(self, command_id: str, timeout: float = 15.0) -> dict:
        """Async wait for a command result. Used by MCP tools."""
        # Check if extension is connected at all
        if self._ws is None and command_id not in self._pending:
            return {
                "success": False,
                "error": "No browser connected. Is the Argus extension active on a web page?",
            }

        # Create a Future on the CURRENT (MCP) event loop
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict] = loop.create_future()
        self._futures[command_id] = future

        # Check if result already arrived (race condition guard)
        if command_id in self._results:
            result = self._results.pop(command_id)
            if not future.done():
                future.set_result(result)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._futures.pop(command_id, None)
            return {
                "success": False,
                "error": f"Timeout: browser did not respond within {timeout:.0f}s. "
                         "Is the extension connected and on a web page?",
            }

    # --- HTTP polling fallback (kept for backwards compatibility) ---

    def get_pending(self) -> list[dict]:
        """Get and claim all pending commands (called by extension HTTP poll)."""
        now = time.time()
        # Remove expired commands
        expired = [k for k, v in self._pending.items() if now - v["created_at"] > self._timeout]
        for k in expired:
            self.set_result(k, {"success": False, "error": "Command expired — extension did not pick it up"})
            del self._pending[k]

        # Claim all pending
        commands = list(self._pending.values())
        self._pending.clear()

        return [{"id": c["id"], "action": c["action"], "params": c["params"]} for c in commands]

    def cleanup(self) -> None:
        """Remove stale results and futures."""
        now = time.time()
        stale = [k for k, v in self._results.items()
                 if isinstance(v, dict) and now - v.get("_ts", 0) > 60]
        for k in stale:
            del self._results[k]
