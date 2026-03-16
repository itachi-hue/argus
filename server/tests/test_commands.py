"""Tests for the command queue and command API endpoints."""

import asyncio
import time

import pytest

from argus.core.commands import CommandQueue


class TestCommandQueue:
    """Unit tests for CommandQueue."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_id(self):
        q = CommandQueue()
        cmd_id = await q.enqueue("click", {"selector": "#btn"})
        assert isinstance(cmd_id, str)
        assert len(cmd_id) == 8

    @pytest.mark.asyncio
    async def test_get_pending_returns_and_clears(self):
        q = CommandQueue()
        await q.enqueue("click", {"selector": "#btn"})
        await q.enqueue("type", {"selector": "#input", "text": "hello"})

        pending = q.get_pending()
        assert len(pending) == 2
        assert pending[0]["action"] == "click"
        assert pending[1]["action"] == "type"

        # Second call should be empty — commands were claimed
        assert q.get_pending() == []

    @pytest.mark.asyncio
    async def test_set_and_retrieve_result(self):
        """Simulates the HTTP polling flow: enqueue → wait + poll/set_result concurrently."""
        q = CommandQueue()
        cmd_id = await q.enqueue("click", {"selector": "#btn"})

        # Simulate extension polling and setting result after a short delay
        async def simulate_extension():
            await asyncio.sleep(0.05)
            q.get_pending()  # extension claims the command
            q.set_result(cmd_id, {"success": True, "result": {"clicked": "#btn"}})

        task = asyncio.create_task(simulate_extension())

        # wait_for_result sees cmd_id in _pending (not yet claimed), creates future
        result = await q.wait_for_result(cmd_id, timeout=2.0)
        assert result["success"] is True
        await task

    @pytest.mark.asyncio
    async def test_wait_for_result_timeout(self):
        q = CommandQueue()
        cmd_id = await q.enqueue("click", {"selector": "#btn"})

        # Don't set any result — command is in _pending, so wait_for_result
        # will create a future and then timeout
        result = await q.wait_for_result(cmd_id, timeout=0.3)
        assert result["success"] is False
        assert "Timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_wait_for_result_no_browser(self):
        """When there's no WS and command isn't pending, returns error immediately."""
        q = CommandQueue()
        result = await q.wait_for_result("nonexistent-id", timeout=0.1)
        assert result["success"] is False
        assert "No browser connected" in result["error"]

    @pytest.mark.asyncio
    async def test_expired_commands_cleaned_up(self):
        q = CommandQueue(command_timeout=0.0)  # 0s timeout = immediately expire
        await q.enqueue("click", {"selector": "#btn"})

        time.sleep(0.01)

        # get_pending should clean expired
        pending = q.get_pending()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_set_result_before_wait(self):
        """Result arriving before wait_for_result is called should still work."""
        q = CommandQueue()
        cmd_id = await q.enqueue("click", {"selector": "#btn"})

        # Set result immediately (before wait) — stored in _results fallback
        q.set_result(cmd_id, {"success": True, "result": {"clicked": "#btn"}})

        # wait_for_result sees cmd_id in _pending AND in _results, picks it up
        result = await q.wait_for_result(cmd_id, timeout=1.0)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_clear_ws_fails_pending_futures(self):
        """Disconnecting WebSocket should fail all pending futures."""
        q = CommandQueue()
        cmd_id = await q.enqueue("click", {"selector": "#btn"})

        # Create a future as wait_for_result would
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        q._futures[cmd_id] = future

        # clear_ws uses call_soon_threadsafe — need to yield to let it execute
        q.clear_ws()
        await asyncio.sleep(0)  # let event loop process the scheduled callback

        # Future should be resolved with an error
        assert future.done()
        result = future.result()
        assert result["success"] is False
        assert "disconnected" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_enqueue_uses_pending_without_ws(self):
        """Without WS, enqueue should add to _pending for HTTP polling."""
        q = CommandQueue()
        cmd_id = await q.enqueue("scroll", {"direction": "top"})

        assert cmd_id in q._pending
        assert q._pending[cmd_id]["action"] == "scroll"


class TestCommandAPI:
    """Integration tests for command API endpoints."""

    def test_get_pending_empty(self, client, auth_headers):
        resp = client.get("/api/commands/pending", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_submit_result(self, client, auth_headers):
        resp = client.post(
            "/api/commands/test-id-123/result",
            json={"success": True, "result": {"clicked": "#btn"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_requires_auth(self, client):
        resp = client.get("/api/commands/pending")
        assert resp.status_code == 401
