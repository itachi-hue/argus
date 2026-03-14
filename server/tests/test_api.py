"""Tests for HTTP API routes and middleware."""

from tests.conftest import make_console, make_element, make_error, make_network, make_page_info, make_screenshot


class TestHealthCheck:
    def test_no_auth_required(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestAuthMiddleware:
    def test_missing_auth_returns_401(self, client):
        r = client.post("/api/ingest/events", json={})
        assert r.status_code == 401

    def test_wrong_token_returns_401(self, client):
        r = client.post("/api/ingest/events", json={}, headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_valid_token_passes(self, client, auth_headers):
        r = client.post(
            "/api/ingest/events", json={"errors": [], "console_events": [], "network_events": []}, headers=auth_headers
        )
        assert r.status_code == 200


class TestIngestEvents:
    def test_ingest_errors(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [make_error()],
                "console_events": [],
                "network_events": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(store.get_errors()) == 1

    def test_ingest_console(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [],
                "console_events": [make_console(), make_console(level="warn", args=["warning!"])],
                "network_events": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(store.get_console_events()) == 2

    def test_ingest_network(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [],
                "console_events": [],
                "network_events": [
                    make_network(),
                    make_network(method="POST", url="http://localhost:3000/api/submit", status=201),
                ],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(store.get_network_events()) == 2

    def test_filters_analytics(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [],
                "console_events": [],
                "network_events": [
                    make_network(url="http://localhost:3000/api/data"),
                    make_network(url="https://google-analytics.com/collect"),
                ],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(store.get_network_events()) == 1

    def test_deduplicates_errors(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [
                    make_error(timestamp=1000.0),
                    make_error(timestamp=1001.0),
                    make_error(timestamp=1002.0),
                ],
                "console_events": [],
                "network_events": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        errors = store.get_errors()
        assert len(errors) == 1
        assert errors[0].occurrence_count == 3

    def test_sanitizes_headers(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/events",
            json={
                "errors": [],
                "console_events": [],
                "network_events": [
                    make_network(
                        request_headers={"Authorization": "Bearer secret"},
                        response_headers={"Set-Cookie": "session=abc"},
                    )
                ],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        events = store.get_network_events()
        assert events[0].request_headers["Authorization"] == "[REDACTED]"
        assert events[0].response_headers["Set-Cookie"] == "[REDACTED]"

    def test_rejects_invalid_payload(self, client, auth_headers):
        r = client.post("/api/ingest/events", json={"errors": [{"bad": "data"}]}, headers=auth_headers)
        assert r.status_code == 422


class TestIngestScreenshot:
    def test_ingest(self, client, auth_headers, store):
        r = client.post("/api/ingest/screenshot", json=make_screenshot(), headers=auth_headers)
        assert r.status_code == 200
        ss = store.get_screenshot(0)
        assert ss is not None
        assert ss.trigger == "hotkey"


class TestIngestElement:
    def test_ingest(self, client, auth_headers, store):
        r = client.post("/api/ingest/element", json=make_element(), headers=auth_headers)
        assert r.status_code == 200
        elem = store.get_selected_element()
        assert elem.selector == "button.submit"


class TestIngestPageInfo:
    def test_ingest(self, client, auth_headers, store):
        r = client.post("/api/ingest/page-info", json=make_page_info(), headers=auth_headers)
        assert r.status_code == 200
        info = store.get_page_info()
        assert info.title == "Checkout"


class TestIngestSnapshot:
    def test_full_snapshot(self, client, auth_headers, store):
        r = client.post(
            "/api/ingest/snapshot",
            json={
                "screenshot": make_screenshot(),
                "errors": [make_error(message="Snapshot error")],
                "console_events": [make_console()],
                "network_events": [make_network(status=500)],
                "page_info": make_page_info(),
                "timestamp": 1000.0,
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert store.get_screenshot(0) is not None
        assert len(store.get_errors()) == 1
        assert len(store.get_console_events()) == 1
        assert len(store.get_network_events()) == 1
        assert store.get_page_info() is not None


class TestClearContext:
    def test_clear_all(self, client, auth_headers, store):
        client.post(
            "/api/ingest/events",
            json={
                "errors": [make_error()],
                "console_events": [make_console()],
                "network_events": [],
            },
            headers=auth_headers,
        )
        assert len(store.get_errors()) > 0

        r = client.delete("/api/context", headers=auth_headers)
        assert r.status_code == 200
        assert len(store.get_errors()) == 0
        assert len(store.get_console_events()) == 0

    def test_clear_specific(self, client, auth_headers, store):
        client.post(
            "/api/ingest/events",
            json={
                "errors": [make_error()],
                "console_events": [make_console()],
                "network_events": [],
            },
            headers=auth_headers,
        )

        r = client.delete("/api/context?event_type=errors", headers=auth_headers)
        assert r.status_code == 200
        assert len(store.get_errors()) == 0
        assert len(store.get_console_events()) > 0  # console not cleared
