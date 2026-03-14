"""Tests for MCP tool definitions."""

import json
import time

from argus.config import Settings
from argus.core.models import ConsoleEvent, ElementCapture, ErrorEvent, NetworkEvent, PageInfo, Screenshot, Viewport, BoundingRect
from argus.mcp.tools import create_mcp_server
from argus.store.memory import InMemoryStore


def _now():
    return time.time()


def _setup():
    config = Settings(auth_token="t")
    store = InMemoryStore(config)
    mcp = create_mcp_server(store)
    return store, mcp


def _get_tool_fn(mcp, name: str):
    """Extract the raw function registered for a tool name."""
    # FastMCP stores tools internally; we can call them directly
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"Tool {name} not found")


class TestGetConsoleErrors:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_console_errors")
        result = fn()
        assert "No console errors" in result

    def test_with_errors(self):
        store, mcp = _setup()
        store.add_errors([
            ErrorEvent(message="TypeError: x is undefined", source="app.js", lineno=42, timestamp=_now()),
        ])
        fn = _get_tool_fn(mcp, "get_console_errors")
        result = fn(since_minutes=5)
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["message"] == "TypeError: x is undefined"

    def test_limit(self):
        store, mcp = _setup()
        now = _now()
        store.add_errors([ErrorEvent(message=f"err{i}", timestamp=now - i) for i in range(10)])
        fn = _get_tool_fn(mcp, "get_console_errors")
        result = fn(limit=3, since_minutes=5)
        data = json.loads(result)
        assert len(data) == 3


class TestGetConsoleLogs:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_console_logs")
        result = fn()
        assert "No console logs" in result

    def test_with_logs(self):
        store, mcp = _setup()
        store.add_console_events([
            ConsoleEvent(level="log", args=["user clicked checkout"], timestamp=1000.0),
            ConsoleEvent(level="warn", args=["deprecation warning"], timestamp=1001.0),
        ])
        fn = _get_tool_fn(mcp, "get_console_logs")
        result = fn()
        data = json.loads(result)
        assert len(data) == 2

    def test_filter_by_level(self):
        store, mcp = _setup()
        store.add_console_events([
            ConsoleEvent(level="log", args=["info"], timestamp=1.0),
            ConsoleEvent(level="warn", args=["warn"], timestamp=2.0),
        ])
        fn = _get_tool_fn(mcp, "get_console_logs")
        result = fn(level="warn")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["level"] == "warn"


class TestGetNetworkFailures:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_network_failures")
        result = fn()
        assert "No network failures" in result

    def test_only_returns_failures(self):
        store, mcp = _setup()
        store.add_network_events([
            NetworkEvent(method="GET", url="http://x/ok", status=200, timestamp=1.0),
            NetworkEvent(method="POST", url="http://x/fail", status=500, timestamp=2.0),
            NetworkEvent(method="GET", url="http://x/auth", status=401, timestamp=3.0),
        ])
        fn = _get_tool_fn(mcp, "get_network_failures")
        result = fn()
        data = json.loads(result)
        assert len(data) == 2
        statuses = {d["status"] for d in data}
        assert statuses == {500, 401}


class TestGetNetworkLog:
    def test_returns_all(self):
        store, mcp = _setup()
        store.add_network_events([
            NetworkEvent(method="GET", url="http://x/a", status=200, timestamp=1.0),
            NetworkEvent(method="POST", url="http://x/b", status=201, timestamp=2.0),
        ])
        fn = _get_tool_fn(mcp, "get_network_log")
        result = fn()
        data = json.loads(result)
        assert len(data) == 2


class TestGetScreenshot:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_screenshot")
        result = fn()
        assert "No screenshots" in result

    def test_returns_screenshot(self):
        store, mcp = _setup()
        store.add_screenshot(Screenshot(
            data="dGVzdA==", url="http://localhost:3000", timestamp=1000.0,
            viewport=Viewport(width=1280, height=720), trigger="hotkey",
        ))
        fn = _get_tool_fn(mcp, "get_screenshot")
        result = fn()
        data = json.loads(result)
        assert data["url"] == "http://localhost:3000"
        assert data["image_base64"] == "dGVzdA=="


class TestListScreenshots:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "list_screenshots")
        result = fn()
        assert "No screenshots" in result

    def test_lists_metadata(self):
        store, mcp = _setup()
        for i in range(3):
            store.add_screenshot(Screenshot(
                data=f"img{i}", url=f"http://x/{i}", timestamp=float(i),
                viewport=Viewport(width=100, height=100), trigger="hotkey",
            ))
        fn = _get_tool_fn(mcp, "list_screenshots")
        result = fn()
        data = json.loads(result)
        assert len(data) == 3
        # Listing should not include raw image data
        for item in data:
            assert "data" not in item


class TestGetSelectedElement:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_selected_element")
        result = fn()
        assert "No element captured" in result

    def test_returns_element(self):
        store, mcp = _setup()
        store.set_selected_element(ElementCapture(
            selector="button.submit", computed_styles={"color": "red"},
            html="<button>X</button>", text="X",
            bounding_rect=BoundingRect(x=0, y=0, width=100, height=40),
            timestamp=1.0, url="http://x",
        ))
        fn = _get_tool_fn(mcp, "get_selected_element")
        result = fn()
        data = json.loads(result)
        assert data["selector"] == "button.submit"


class TestGetPageInfo:
    def test_empty(self):
        store, mcp = _setup()
        fn = _get_tool_fn(mcp, "get_page_info")
        result = fn()
        assert "No page info" in result

    def test_returns_info(self):
        store, mcp = _setup()
        store.set_page_info(PageInfo(url="http://localhost:3000", title="My App",
                                     viewport=Viewport(width=1920, height=1080), timestamp=1.0))
        fn = _get_tool_fn(mcp, "get_page_info")
        result = fn()
        data = json.loads(result)
        assert data["title"] == "My App"


class TestClearContext:
    def test_clear_all(self):
        store, mcp = _setup()
        store.add_errors([ErrorEvent(message="e", timestamp=1.0)])
        fn = _get_tool_fn(mcp, "clear_context")
        result = fn()
        assert "all context" in result
        assert store.get_errors() == []

    def test_clear_specific(self):
        store, mcp = _setup()
        store.add_errors([ErrorEvent(message="e", timestamp=1.0)])
        store.add_console_events([ConsoleEvent(level="log", args=["x"], timestamp=1.0)])
        fn = _get_tool_fn(mcp, "clear_context")
        fn(event_type="errors")
        assert store.get_errors() == []
        assert len(store.get_console_events()) == 1
