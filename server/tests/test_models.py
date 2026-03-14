"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from argus.core.models import (
    ConsoleEvent,
    ElementCapture,
    ErrorEvent,
    IngestEventsRequest,
    IngestSnapshotRequest,
    NetworkEvent,
    PageInfo,
    Screenshot,
)


class TestErrorEvent:
    def test_minimal(self):
        e = ErrorEvent(message="fail", timestamp=1.0)
        assert e.message == "fail"
        assert e.source == ""
        assert e.occurrence_count == 1

    def test_full(self):
        e = ErrorEvent(
            message="TypeError", source="app.js", lineno=10, colno=5,
            stack="at app.js:10:5", timestamp=1000.0, occurrence_count=3,
        )
        assert e.lineno == 10
        assert e.occurrence_count == 3

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ErrorEvent(message="fail", timestamp=1.0, unknown_field="bad")


class TestNetworkEvent:
    def test_success(self):
        n = NetworkEvent(method="GET", url="http://localhost/api", status=200, timestamp=1.0)
        assert n.status == 200
        assert n.error is None

    def test_failure(self):
        n = NetworkEvent(method="POST", url="http://localhost/api", status=500,
                         status_text="Internal Server Error", timestamp=1.0, error=None)
        assert n.status == 500

    def test_network_error(self):
        n = NetworkEvent(method="GET", url="http://localhost/api", timestamp=1.0, error="Network error")
        assert n.status is None
        assert n.error == "Network error"


class TestConsoleEvent:
    def test_basic(self):
        c = ConsoleEvent(level="log", args=["hello", "world"], timestamp=1.0)
        assert c.level == "log"
        assert len(c.args) == 2

    def test_empty_args(self):
        c = ConsoleEvent(level="warn", timestamp=1.0)
        assert c.args == []


class TestScreenshot:
    def test_basic(self):
        s = Screenshot(data="abc123", url="http://localhost", timestamp=1.0,
                       viewport={"width": 1280, "height": 720}, trigger="hotkey")
        assert s.viewport.width == 1280
        assert s.trigger == "hotkey"


class TestIngestEventsRequest:
    def test_empty(self):
        r = IngestEventsRequest()
        assert r.errors == []
        assert r.console_events == []
        assert r.network_events == []

    def test_mixed(self):
        r = IngestEventsRequest(
            errors=[{"message": "err", "timestamp": 1.0}],
            network_events=[{"method": "GET", "url": "http://x", "timestamp": 1.0}],
        )
        assert len(r.errors) == 1
        assert len(r.network_events) == 1


class TestIngestSnapshotRequest:
    def test_full(self):
        r = IngestSnapshotRequest(
            screenshot={"data": "x", "url": "http://x", "timestamp": 1.0,
                        "viewport": {"width": 100, "height": 100}, "trigger": "hotkey"},
            errors=[{"message": "err", "timestamp": 1.0}],
            page_info={"url": "http://x", "title": "X", "viewport": {"width": 100, "height": 100}, "timestamp": 1.0},
            timestamp=1.0,
        )
        assert r.screenshot is not None
        assert r.page_info.title == "X"




