"""MCP tool definitions — the agent-facing interface."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from argus.store.base import ContextStore


def create_mcp_server(store: ContextStore) -> FastMCP:
    mcp = FastMCP(
        "argus",
        instructions=(
            "Argus provides runtime browser context — console errors, network requests, "
            "screenshots, and UI element details. Use these tools to understand what is "
            "happening in the user's running application."
        ),
    )

    @mcp.tool()
    def get_console_errors(limit: int = 20, since_minutes: float = 5) -> str:
        """Get recent JavaScript errors from the browser console.

        Args:
            limit: Maximum number of errors to return (default 20).
            since_minutes: Only return errors from the last N minutes (default 5).
        """
        errors = store.get_errors(limit=limit, since_minutes=since_minutes)
        if not errors:
            return "No console errors captured."
        return json.dumps([e.model_dump() for e in errors], indent=2)

    @mcp.tool()
    def get_console_logs(limit: int = 50, level: str = "all") -> str:
        """Get recent console output (log, warn, info, debug).

        Args:
            limit: Maximum number of log entries to return (default 50).
            level: Filter by level — 'log', 'warn', 'info', 'debug', or 'all' (default 'all').
        """
        events = store.get_console_events(limit=limit, level=level)
        if not events:
            return "No console logs captured."
        return json.dumps([e.model_dump() for e in events], indent=2)

    @mcp.tool()
    def get_network_failures(limit: int = 20, status_filter: str | None = None, url_pattern: str | None = None) -> str:
        """Get recent failed network requests (4xx, 5xx, network errors).

        Args:
            limit: Maximum number of failures to return (default 20).
            status_filter: Filter by status — '4xx', '5xx', '401', '500', etc.
            url_pattern: Regex pattern to filter by URL.
        """
        events = store.get_network_failures(limit=limit, status_filter=status_filter, url_pattern=url_pattern)
        if not events:
            return "No network failures captured."
        return json.dumps([e.model_dump() for e in events], indent=2)

    @mcp.tool()
    def get_network_log(limit: int = 50, method: str | None = None, url_pattern: str | None = None) -> str:
        """Get recent network requests (all, not just failures).

        Args:
            limit: Maximum number of requests to return (default 50).
            method: Filter by HTTP method — 'GET', 'POST', etc.
            url_pattern: Regex pattern to filter by URL.
        """
        events = store.get_network_events(limit=limit, method=method, url_pattern=url_pattern)
        if not events:
            return "No network requests captured."
        return json.dumps([e.model_dump() for e in events], indent=2)

    @mcp.tool()
    def get_screenshot(index: int = 0) -> list[TextContent | ImageContent]:
        """Get a browser screenshot by index. Use list_screenshots first to see the
        timeline, then fetch specific screenshots by index.

        Args:
            index: Screenshot index (0 = latest, 1 = second latest, etc.)
        """
        screenshot = store.get_screenshot(index=index)
        if not screenshot:
            return [
                TextContent(
                    type="text", text="No screenshots captured. Ask the user to press the Argus hotkey in the browser."
                )
            ]

        # Return metadata as text + image as native image content block
        metadata = json.dumps(
            {
                "url": screenshot.url,
                "timestamp": screenshot.timestamp,
                "viewport": screenshot.viewport.model_dump(),
                "trigger": screenshot.trigger,
            }
        )
        return [
            TextContent(type="text", text=metadata),
            ImageContent(type="image", data=screenshot.data, mimeType="image/jpeg"),
        ]

    @mcp.tool()
    def list_screenshots() -> str:
        """List all available screenshots with metadata (without image data).

        Returns a timeline of captured screenshots with index, URL, timestamp,
        trigger (hotkey/page_load/tab_switch/periodic/user_click), and viewport size.
        Use this to decide which screenshots to fetch with get_screenshot(index).
        """
        screenshots = store.get_screenshot_list()
        if not screenshots:
            return "No screenshots captured."
        return json.dumps(screenshots, indent=2)

    @mcp.tool()
    def get_selected_element() -> str:
        """Get details about the UI element the user right-click captured.

        Returns selector, computed styles, HTML, bounding rect, and the page URL.
        """
        element = store.get_selected_element()
        if not element:
            return "No element captured. Ask the user to right-click an element and select 'Capture for AI Agent'."
        return json.dumps(element.model_dump(), indent=2)

    @mcp.tool()
    def get_page_info() -> str:
        """Get current browser page URL, title, and viewport size."""
        info = store.get_page_info()
        if not info:
            return "No page info available."
        return json.dumps(info.model_dump(), indent=2)

    @mcp.tool()
    def clear_context(event_type: str | None = None) -> str:
        """Clear stored browser context.

        Args:
            event_type: Clear specific type — 'errors', 'console', 'network', 'screenshots', 'element'.
                       Omit to clear everything.
        """
        store.clear(event_type)
        return f"Cleared {'all context' if not event_type else event_type}."

    return mcp
