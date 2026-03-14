"""End-to-end tests simulating Chrome extension → HTTP API → MCP tool flow.

Spins up the full FastAPI app and runs through realistic scenarios
like a buggy frontend would produce.
"""

import json
import time

from fastapi.testclient import TestClient

from tests.conftest import make_console, make_element, make_error, make_network, make_page_info, make_screenshot


class TestBuggyReactApp:
    """Simulate a React app throwing errors, failing API calls, etc."""

    def test_full_debugging_session(self, client: TestClient, auth_headers: dict, store):
        """
        Scenario: Dev opens a checkout page. The page has:
        - A TypeError in the payment component
        - A 500 from POST /api/checkout
        - Console logs from the app
        - A screenshot from the hotkey
        - A captured element (the broken button)
        """
        now = time.time()

        # 1. Extension sends a batch of events (console errors + network + logs)
        r = client.post("/api/ingest/events", json={
            "errors": [
                make_error(
                    message="TypeError: Cannot read properties of undefined (reading 'cardNumber')",
                    source="http://localhost:3000/static/js/PaymentForm.js",
                    lineno=147,
                    timestamp=now - 2,
                    stack=(
                        "TypeError: Cannot read properties of undefined (reading 'cardNumber')\n"
                        "    at PaymentForm (http://localhost:3000/static/js/PaymentForm.js:147:23)\n"
                        "    at renderWithHooks (http://localhost:3000/static/js/bundle.js:12345:18)"
                    ),
                ),
                # This is a duplicate of the first error (same msg/source/lineno) — should be deduped
                make_error(
                    message="TypeError: Cannot read properties of undefined (reading 'cardNumber')",
                    source="http://localhost:3000/static/js/PaymentForm.js",
                    lineno=147,
                    timestamp=now - 1,
                ),
            ],
            "network_events": [
                make_network(method="GET", url="http://localhost:3000/api/cart", status=200, timestamp=now - 5),
                make_network(method="POST", url="http://localhost:3000/api/checkout", status=500,
                             status_text="Internal Server Error", timestamp=now - 1,
                             request_headers={"Authorization": "Bearer user-jwt-secret-token",
                                              "Content-Type": "application/json"},
                             response_headers={"Set-Cookie": "session=abc123"},
                             request_body='{"items": [1, 2, 3]}',
                             response_body='{"error": "Stripe API key not configured"}'),
                # Analytics noise — should be filtered out
                make_network(method="POST", url="https://google-analytics.com/collect", status=200, timestamp=now - 3),
                make_network(method="GET", url="https://cdn.segment.com/v1/projects/abc/settings", status=200, timestamp=now - 4),
            ],
            "console_events": [
                make_console(level="log", args=["[App] Cart loaded with 3 items"], timestamp=now - 5),
                make_console(level="warn", args=["[React] Each child in a list should have a unique 'key' prop"], timestamp=now - 4),
                make_console(level="error", args=["Payment form crashed"], timestamp=now - 2),
            ],
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["accepted"] is True

        # 2. Extension sends page info
        r = client.post("/api/ingest/page-info", json=make_page_info(
            url="http://localhost:3000/checkout",
            title="MyShop - Checkout",
            timestamp=now,
        ), headers=auth_headers)
        assert r.status_code == 200

        # 3. User presses Ctrl+Shift+L → extension sends screenshot
        r = client.post("/api/ingest/screenshot", json=make_screenshot(
            url="http://localhost:3000/checkout",
            timestamp=now,
            trigger="hotkey",
        ), headers=auth_headers)
        assert r.status_code == 200

        # 4. User right-clicks the broken Pay button → element capture
        r = client.post("/api/ingest/element", json=make_element(
            selector="button.pay-btn",
            url="http://localhost:3000/checkout",
            timestamp=now,
        ), headers=auth_headers)
        assert r.status_code == 200

        # ---- Now simulate the AI agent querying via MCP tools ----
        # (We test against the store which is the same data source MCP tools read from)

        # Agent: "What errors are happening?"
        errors = store.get_errors(limit=20, since_minutes=9999)
        assert len(errors) == 1  # deduplication collapsed 2 identical errors
        err = errors[0]
        assert "cardNumber" in err.message
        assert err.occurrence_count == 2
        assert "PaymentForm.js" in err.source

        # Agent: "Show me network failures"
        failures = store.get_network_failures(limit=20)
        assert len(failures) == 1
        fail = failures[0]
        assert fail.status == 500
        assert "/api/checkout" in fail.url
        # Sensitive headers should be redacted
        assert fail.request_headers["Authorization"] == "[REDACTED]"
        assert fail.response_headers["Set-Cookie"] == "[REDACTED]"
        # Body should still be present (under max length)
        assert "Stripe API key" in fail.response_body

        # Agent: "Show me all network requests"
        network = store.get_network_events(limit=50)
        assert len(network) == 2  # analytics filtered out, only cart + checkout
        urls = [e.url for e in network]
        assert any("/api/cart" in u for u in urls)
        assert any("/api/checkout" in u for u in urls)
        assert not any("google-analytics" in u for u in urls)

        # Agent: "Show me console logs"
        logs = store.get_console_events(limit=50)
        assert len(logs) == 3
        assert any("Cart loaded" in l.args[0] for l in logs)

        # Agent: "Get the screenshot"
        ss = store.get_screenshot(0)
        assert ss is not None
        assert ss.url == "http://localhost:3000/checkout"
        assert ss.trigger == "hotkey"

        # Agent: "What element was captured?"
        elem = store.get_selected_element()
        assert elem is not None
        assert elem.selector == "button.pay-btn"

        # Agent: "Page info?"
        page = store.get_page_info()
        assert page is not None
        assert page.title == "MyShop - Checkout"

    def test_high_volume_error_spam(self, client: TestClient, auth_headers: dict, store):
        """Simulate a render loop spamming the same error 100 times."""
        now = time.time()
        errors = [
            make_error(
                message="Error: Maximum update depth exceeded",
                source="http://localhost:3000/static/js/bundle.js",
                lineno=999,
                timestamp=now + i * 0.01,  # all within the dedup window
            )
            for i in range(100)
        ]

        r = client.post("/api/ingest/events", json={
            "errors": errors,
            "console_events": [],
            "network_events": [],
        }, headers=auth_headers)
        assert r.status_code == 200

        stored = store.get_errors(limit=100, since_minutes=9999)
        assert len(stored) == 1
        assert stored[0].occurrence_count == 100

    def test_snapshot_captures_everything(self, client: TestClient, auth_headers: dict, store):
        """Test the snapshot endpoint that sends everything at once."""
        now = time.time()

        r = client.post("/api/ingest/snapshot", json={
            "screenshot": make_screenshot(url="http://localhost:3000/profile", timestamp=now, trigger="hotkey"),
            "errors": [make_error(message="ReferenceError: user is not defined", timestamp=now)],
            "console_events": [make_console(level="error", args=["Failed to load profile"], timestamp=now)],
            "network_events": [
                make_network(method="GET", url="http://localhost:3000/api/profile", status=403, timestamp=now,
                             response_body='{"error": "Not authorized"}'),
            ],
            "page_info": make_page_info(url="http://localhost:3000/profile", title="User Profile", timestamp=now),
            "timestamp": now,
        }, headers=auth_headers)
        assert r.status_code == 200

        assert store.get_screenshot(0) is not None
        assert len(store.get_errors(since_minutes=9999)) == 1
        assert len(store.get_console_events()) == 1
        assert len(store.get_network_events()) == 1
        assert store.get_page_info().title == "User Profile"


class TestMiddleware:
    """Test security middleware behavior."""

    def test_health_no_auth(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_no_token_401(self, client):
        r = client.post("/api/ingest/events", json={})
        assert r.status_code == 401

    def test_wrong_token_401(self, client):
        r = client.post("/api/ingest/events", json={}, headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_payload_too_large_413(self, client, auth_headers):
        """Server rejects huge payloads."""
        huge_body = "x" * (6 * 1024 * 1024)  # 6MB > 5MB limit
        r = client.post("/api/ingest/events",
                        content=huge_body,
                        headers={**auth_headers, "Content-Type": "application/json",
                                 "Content-Length": str(len(huge_body))})
        assert r.status_code == 413

    def test_invalid_json_422(self, client, auth_headers):
        r = client.post("/api/ingest/events", json={"errors": [{"bad": "data"}]}, headers=auth_headers)
        assert r.status_code == 422


class TestClearFlow:
    """Test clearing context mid-session."""

    def test_clear_and_re_ingest(self, client: TestClient, auth_headers: dict, store):
        now = time.time()

        # Ingest some data
        client.post("/api/ingest/events", json={
            "errors": [make_error(timestamp=now)],
            "console_events": [make_console(timestamp=now)],
            "network_events": [make_network(timestamp=now)],
        }, headers=auth_headers)
        assert len(store.get_errors(since_minutes=9999)) > 0

        # Clear everything
        r = client.delete("/api/context", headers=auth_headers)
        assert r.status_code == 200
        assert store.get_errors() == []
        assert store.get_console_events() == []
        assert store.get_network_events() == []

        # Ingest new data after clear
        client.post("/api/ingest/events", json={
            "errors": [make_error(message="new error after clear", timestamp=now + 10)],
            "console_events": [],
            "network_events": [],
        }, headers=auth_headers)
        errors = store.get_errors(since_minutes=9999)
        assert len(errors) == 1
        assert errors[0].message == "new error after clear"

    def test_clear_specific_type(self, client: TestClient, auth_headers: dict, store):
        now = time.time()

        client.post("/api/ingest/events", json={
            "errors": [make_error(timestamp=now)],
            "console_events": [make_console(timestamp=now)],
            "network_events": [],
        }, headers=auth_headers)

        # Clear only errors
        client.delete("/api/context?event_type=errors", headers=auth_headers)
        assert store.get_errors(since_minutes=9999) == []
        assert len(store.get_console_events()) == 1  # console still there






