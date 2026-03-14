"""Command queue for agent-initiated browser actions.

Flow:
  1. MCP tool enqueues a command (e.g. click_element)
  2. Extension polls GET /api/commands/pending — picks up the command
  3. Extension executes it via chrome.scripting.executeScript
  4. Extension reports result via POST /api/commands/{id}/result
  5. MCP tool's wait_for_result() picks up the result and returns it
"""

import asyncio
import threading
import time
import uuid


class CommandQueue:
    def __init__(self, command_timeout: float = 30.0):
        self._timeout = command_timeout
        self._pending: dict[str, dict] = {}  # id -> command dict
        self._results: dict[str, dict] = {}  # id -> result dict
        self._lock = threading.Lock()

    def enqueue(self, action: str, params: dict) -> str:
        """Add a command to the queue. Returns command ID."""
        cmd_id = uuid.uuid4().hex[:8]
        with self._lock:
            self._pending[cmd_id] = {
                "id": cmd_id,
                "action": action,
                "params": params,
                "created_at": time.time(),
            }
        return cmd_id

    def get_pending(self) -> list[dict]:
        """Get and claim all pending commands (called by extension)."""
        with self._lock:
            now = time.time()
            # Remove expired commands
            expired = [k for k, v in self._pending.items() if now - v["created_at"] > self._timeout]
            for k in expired:
                self._results[k] = {"success": False, "error": "Command expired — extension did not pick it up"}
                del self._pending[k]

            # Claim all pending
            commands = list(self._pending.values())
            self._pending.clear()

            # Strip internal fields before returning
            return [{"id": c["id"], "action": c["action"], "params": c["params"]} for c in commands]

    def set_result(self, command_id: str, result: dict) -> bool:
        """Store the result of a command (called by extension). Returns True if command was expected."""
        with self._lock:
            self._results[command_id] = result
            return True

    async def wait_for_result(self, command_id: str, timeout: float = 15.0) -> dict:
        """Async wait for a command result. Used by MCP tools."""
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if command_id in self._results:
                    return self._results.pop(command_id)
            await asyncio.sleep(0.25)
        return {
            "success": False,
            "error": "Timeout: browser did not respond within 15s. Is the extension connected and on a web page?",
        }

    def cleanup(self) -> None:
        """Remove stale results older than timeout."""
        with self._lock:
            now = time.time()
            stale = [k for k, v in self._results.items() if isinstance(v, dict) and now - v.get("_ts", 0) > 60]
            for k in stale:
                del self._results[k]
