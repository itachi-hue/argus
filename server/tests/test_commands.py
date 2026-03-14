"""Tests for the command queue and command API endpoints."""

import asyncio

from argus.core.commands import CommandQueue


class TestCommandQueue:
    """Unit tests for CommandQueue."""

    def test_enqueue_returns_id(self):
        q = CommandQueue()
        cmd_id = q.enqueue("click", {"selector": "#btn"})
        assert isinstance(cmd_id, str)
        assert len(cmd_id) == 8

    def test_get_pending_returns_and_clears(self):
        q = CommandQueue()
        q.enqueue("click", {"selector": "#btn"})
        q.enqueue("type", {"selector": "#input", "text": "hello"})

        pending = q.get_pending()
        assert len(pending) == 2
        assert pending[0]["action"] == "click"
        assert pending[1]["action"] == "type"

        # Second call should be empty — commands were claimed
        assert q.get_pending() == []

    def test_set_and_retrieve_result(self):
        q = CommandQueue()
        cmd_id = q.enqueue("click", {"selector": "#btn"})
        q.get_pending()  # claim the command

        q.set_result(cmd_id, {"success": True, "result": {"clicked": "#btn"}})

        # Result should be available via wait
        result = asyncio.get_event_loop().run_until_complete(q.wait_for_result(cmd_id, timeout=1.0))
        assert result["success"] is True

    def test_wait_for_result_timeout(self):
        q = CommandQueue()
        cmd_id = q.enqueue("click", {"selector": "#btn"})
        q.get_pending()

        # Don't set any result — should timeout
        result = asyncio.get_event_loop().run_until_complete(q.wait_for_result(cmd_id, timeout=0.5))
        assert result["success"] is False
        assert "Timeout" in result["error"]

    def test_expired_commands_cleaned_up(self):
        q = CommandQueue(command_timeout=0.0)  # 0s timeout = immediately expire
        q.enqueue("click", {"selector": "#btn"})

        import time

        time.sleep(0.01)

        # get_pending should clean expired
        pending = q.get_pending()
        assert len(pending) == 0


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

