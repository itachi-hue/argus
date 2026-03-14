"""Tests for InMemoryStore."""

import time

from argus.config import Settings
from argus.core.models import ConsoleEvent, ElementCapture, ErrorEvent, NetworkEvent, PageInfo, Screenshot
from argus.store.memory import InMemoryStore


def _store(max_errors=5, max_console=5, max_network=5, max_screenshots=3):
    config = Settings(auth_token="t", max_errors=max_errors, max_console=max_console,
                      max_network=max_network, max_screenshots=max_screenshots)
    return InMemoryStore(config)


class TestErrors:
    def test_add_and_get(self):
        s = _store()
        s.add_errors([ErrorEvent(message="e1", timestamp=1.0), ErrorEvent(message="e2", timestamp=2.0)])
        errors = s.get_errors(limit=10)
        assert len(errors) == 2
        assert errors[0].message == "e1"

    def test_bounded(self):
        s = _store(max_errors=3)
        s.add_errors([ErrorEvent(message=f"e{i}", timestamp=float(i)) for i in range(5)])
        errors = s.get_errors(limit=10)
        assert len(errors) == 3
        assert errors[0].message == "e2"  # oldest evicted

    def test_limit(self):
        s = _store()
        s.add_errors([ErrorEvent(message=f"e{i}", timestamp=float(i)) for i in range(5)])
        errors = s.get_errors(limit=2)
        assert len(errors) == 2
        assert errors[-1].message == "e4"  # latest

    def test_since_minutes(self):
        s = _store()
        now = time.time()
        s.add_errors([
            ErrorEvent(message="old", timestamp=now - 600),  # 10 min ago
            ErrorEvent(message="recent", timestamp=now - 60),  # 1 min ago
        ])
        errors = s.get_errors(limit=10, since_minutes=5)
        assert len(errors) == 1
        assert errors[0].message == "recent"


class TestConsole:
    def test_add_and_filter_by_level(self):
        s = _store()
        s.add_console_events([
            ConsoleEvent(level="log", args=["hello"], timestamp=1.0),
            ConsoleEvent(level="warn", args=["careful"], timestamp=2.0),
            ConsoleEvent(level="log", args=["world"], timestamp=3.0),
        ])
        logs = s.get_console_events(limit=10, level="log")
        assert len(logs) == 2
        warns = s.get_console_events(limit=10, level="warn")
        assert len(warns) == 1


class TestNetwork:
    def test_get_failures(self):
        s = _store()
        s.add_network_events([
            NetworkEvent(method="GET", url="http://x/ok", status=200, timestamp=1.0),
            NetworkEvent(method="POST", url="http://x/fail", status=500, timestamp=2.0),
            NetworkEvent(method="GET", url="http://x/auth", status=401, timestamp=3.0),
            NetworkEvent(method="GET", url="http://x/err", timestamp=4.0, error="Network error"),
        ])
        failures = s.get_network_failures(limit=10)
        assert len(failures) == 3  # 500, 401, network error

    def test_status_filter(self):
        s = _store()
        s.add_network_events([
            NetworkEvent(method="GET", url="http://x/a", status=401, timestamp=1.0),
            NetworkEvent(method="GET", url="http://x/b", status=500, timestamp=2.0),
        ])
        only_4xx = s.get_network_failures(limit=10, status_filter="4xx")
        assert len(only_4xx) == 1
        assert only_4xx[0].status == 401

    def test_url_pattern(self):
        s = _store()
        s.add_network_events([
            NetworkEvent(method="GET", url="http://x/api/users", status=200, timestamp=1.0),
            NetworkEvent(method="GET", url="http://x/api/orders", status=200, timestamp=2.0),
            NetworkEvent(method="GET", url="http://x/health", status=200, timestamp=3.0),
        ])
        api = s.get_network_events(limit=10, url_pattern=r"/api/")
        assert len(api) == 2

    def test_method_filter(self):
        s = _store()
        s.add_network_events([
            NetworkEvent(method="GET", url="http://x/a", status=200, timestamp=1.0),
            NetworkEvent(method="POST", url="http://x/b", status=200, timestamp=2.0),
        ])
        posts = s.get_network_events(limit=10, method="POST")
        assert len(posts) == 1


class TestScreenshots:
    def test_add_and_get(self):
        s = _store(max_screenshots=3)
        s.add_screenshot(Screenshot(data="img1", url="http://x", timestamp=1.0,
                                    viewport={"width": 100, "height": 100}, trigger="hotkey"))
        ss = s.get_screenshot(0)
        assert ss is not None
        assert ss.data == "img1"

    def test_bounded(self):
        s = _store(max_screenshots=2)
        for i in range(4):
            s.add_screenshot(Screenshot(data=f"img{i}", url="http://x", timestamp=float(i),
                                        viewport={"width": 100, "height": 100}, trigger="hotkey"))
        assert s.get_screenshot(0).data == "img3"  # latest
        assert s.get_screenshot(1).data == "img2"
        assert s.get_screenshot(2) is None  # evicted

    def test_list(self):
        s = _store(max_screenshots=3)
        for i in range(2):
            s.add_screenshot(Screenshot(data=f"img{i}", url=f"http://x/{i}", timestamp=float(i),
                                        viewport={"width": 100, "height": 100}, trigger="hotkey"))
        listing = s.get_screenshot_list()
        assert len(listing) == 2
        assert "data" not in listing[0]  # metadata only, no image data


class TestElement:
    def test_set_and_get(self):
        s = _store()
        elem = ElementCapture(
            selector="button.submit", computed_styles={"color": "red"}, html="<button>X</button>",
            text="X", bounding_rect={"x": 0, "y": 0, "width": 100, "height": 40},
            timestamp=1.0, url="http://x",
        )
        s.set_selected_element(elem)
        got = s.get_selected_element()
        assert got.selector == "button.submit"


class TestClear:
    def test_clear_all(self):
        s = _store()
        s.add_errors([ErrorEvent(message="e", timestamp=1.0)])
        s.add_console_events([ConsoleEvent(level="log", args=["x"], timestamp=1.0)])
        s.clear()
        assert s.get_errors() == []
        assert s.get_console_events() == []

    def test_clear_specific(self):
        s = _store()
        s.add_errors([ErrorEvent(message="e", timestamp=1.0)])
        s.add_console_events([ConsoleEvent(level="log", args=["x"], timestamp=1.0)])
        s.clear("errors")
        assert s.get_errors() == []
        assert len(s.get_console_events()) == 1

