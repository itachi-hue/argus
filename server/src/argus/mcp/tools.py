"""MCP tool definitions — the agent-facing interface."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from argus.core.commands import CommandQueue
from argus.store.base import ContextStore


def create_mcp_server(store: ContextStore, command_queue: CommandQueue) -> FastMCP:
    mcp = FastMCP(
        "argus",
        instructions=(
            "Argus gives you eyes AND hands in the browser. "
            "Use observation tools (console, network, screenshots) to understand what's happening, "
            "and action tools (click, type, navigate, run JS) to interact with the page directly."
        ),
    )

    # ═══════════════════════════════════════════════════════════════
    # OBSERVATION TOOLS (9) — read browser state
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # BROWSER ACTION TOOLS (8) — interact with the page
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def click_element(selector: str) -> str:
        """Click an element on the page.

        Args:
            selector: CSS selector for the element to click (e.g. 'button.submit', '#login-btn').
        """
        cmd_id = command_queue.enqueue("click", {"selector": selector})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def type_text(selector: str, text: str, clear_first: bool = True) -> str:
        """Type text into an input field.

        Args:
            selector: CSS selector for the input element.
            text: Text to type.
            clear_first: Whether to clear existing text before typing (default True).
        """
        cmd_id = command_queue.enqueue("type", {"selector": selector, "text": text, "clear_first": clear_first})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def scroll_to(selector: str | None = None, x: int = 0, y: int = 0, direction: str | None = None) -> str:
        """Scroll the page to an element or position.

        Args:
            selector: CSS selector to scroll into view. If provided, x/y are ignored.
            x: Horizontal scroll position in pixels (if no selector).
            y: Vertical scroll position in pixels (if no selector).
            direction: Quick scroll — 'top', 'bottom', 'up', 'down'. Overrides x/y.
        """
        cmd_id = command_queue.enqueue("scroll", {"selector": selector, "x": x, "y": y, "direction": direction})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def navigate_to(url: str) -> str:
        """Navigate the browser to a URL.

        Args:
            url: The URL to navigate to (e.g. 'https://example.com' or '/dashboard').
        """
        cmd_id = command_queue.enqueue("navigate", {"url": url})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def get_text(selector: str) -> str:
        """Get the text content of an element.

        Args:
            selector: CSS selector for the element (e.g. 'h1', '.error-message', '#price').
        """
        cmd_id = command_queue.enqueue("get_text", {"selector": selector})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def run_javascript(code: str) -> str:
        """Execute JavaScript in the page context and return the result.

        The code runs in the page's main world — you have access to window, document,
        and all page globals (React, Vue, Angular internals, etc.).

        Args:
            code: JavaScript code to execute. The last expression is returned.
                  Example: 'document.title' or 'window.__NEXT_DATA__.props'
        """
        cmd_id = command_queue.enqueue("run_js", {"code": code})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def highlight_element(selector: str, color: str = "#ff00ff", duration_ms: int = 3000) -> str:
        """Highlight an element with a colored outline for visual debugging.

        Args:
            selector: CSS selector for the element to highlight.
            color: Outline color (default '#ff00ff' — magenta).
            duration_ms: How long the highlight stays visible in milliseconds (default 3000).
        """
        cmd_id = command_queue.enqueue("highlight", {"selector": selector, "color": color, "duration_ms": duration_ms})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def wait_for_element(selector: str, timeout_ms: int = 5000) -> str:
        """Wait for an element to appear in the DOM. Useful after navigation or
        clicking something that triggers async UI updates.

        Args:
            selector: CSS selector to wait for.
            timeout_ms: Maximum time to wait in milliseconds (default 5000).
        """
        cmd_id = command_queue.enqueue("wait_for", {"selector": selector, "timeout_ms": timeout_ms})
        # Use longer server-side timeout to account for the browser-side wait
        result = await command_queue.wait_for_result(cmd_id, timeout=max(15.0, timeout_ms / 1000 + 5))
        return json.dumps(result)

    # ═══════════════════════════════════════════════════════════════
    # ADVANCED TOOLS (6) — forms, viewport, perf, storage, cookies, a11y
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def fill_form(fields: str) -> str:
        """Fill multiple form fields at once. More efficient than calling type_text
        for each field individually.

        Args:
            fields: JSON string of selector-value pairs.
                    Example: '{"#email": "test@example.com", "#password": "secret", "#name": "John"}'
        """
        try:
            parsed = json.loads(fields)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        cmd_id = command_queue.enqueue("fill_form", {"fields": parsed})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result)

    @mcp.tool()
    async def capture_at_viewport(width: int, height: int) -> list[TextContent | ImageContent]:
        """Resize browser to specific dimensions, capture a screenshot, then restore.
        Useful for testing responsive layouts.

        Args:
            width: Viewport width in pixels (e.g. 375 for iPhone, 768 for tablet, 1920 for desktop).
            height: Viewport height in pixels (e.g. 812 for iPhone, 1024 for tablet, 1080 for desktop).
        """
        cmd_id = command_queue.enqueue("capture_viewport", {"width": width, "height": height})
        result = await command_queue.wait_for_result(cmd_id, timeout=20.0)
        if not result.get("success"):
            return [TextContent(type="text", text=json.dumps(result))]

        screenshot_data = result.get("result", {}).get("screenshot")
        if not screenshot_data:
            return [TextContent(type="text", text="Viewport captured but no screenshot data returned.")]

        metadata = json.dumps({
            "viewport": {"width": width, "height": height},
            "url": result.get("result", {}).get("url", ""),
        })
        return [
            TextContent(type="text", text=metadata),
            ImageContent(type="image", data=screenshot_data, mimeType="image/jpeg"),
        ]

    @mcp.tool()
    async def get_performance_metrics() -> str:
        """Get Web Vitals and performance metrics from the current page.

        Returns: Navigation timing (TTFB, DOM load, full load), paint timing (FCP, LCP),
        layout shift (CLS), memory usage, and resource counts.
        """
        cmd_id = command_queue.enqueue("get_perf", {})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_storage(storage_type: str = "all") -> str:
        """Get contents of localStorage and/or sessionStorage.

        Args:
            storage_type: 'local', 'session', or 'all' (default 'all').
        """
        cmd_id = command_queue.enqueue("get_storage", {"type": storage_type})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_cookies() -> str:
        """Get all cookies for the current page domain.

        Returns cookie names, values (first 50 chars), domains, paths, and flags.
        """
        cmd_id = command_queue.enqueue("get_cookies", {})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    # ═══════════════════════════════════════════════════════════════
    # FRAMEWORK INSPECTION TOOLS — React, Vue, Svelte, Angular
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    async def detect_framework() -> str:
        """Detect which frontend frameworks are used on the current page.

        Returns detected frameworks with versions: React, Vue, Svelte, Angular,
        Next.js, Nuxt, jQuery, and more.
        """
        cmd_id = command_queue.enqueue("detect_framework", {})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def inspect_component(selector: str) -> str:
        """Inspect the React/Vue/Svelte/Angular component at a DOM element.

        Returns component name, props, state (hooks for React), context,
        parent components, and framework-specific details.

        This is the most powerful debugging tool for frontend development —
        see exactly what data a component is working with.

        Args:
            selector: CSS selector for the DOM element (e.g. '.user-card', '#modal', 'button.submit').
                      The tool finds the nearest framework component that owns this element.
        """
        cmd_id = command_queue.enqueue("inspect_component", {"selector": selector})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_accessibility_issues(selector: str | None = None) -> str:
        """Run accessibility audit on the current page or a specific element.

        Checks for: missing alt text, unlabeled form inputs, low contrast indicators,
        missing ARIA roles, empty links/buttons, missing document language.

        Args:
            selector: CSS selector to scope the audit (default: entire page).
        """
        cmd_id = command_queue.enqueue("a11y_audit", {"selector": selector})
        result = await command_queue.wait_for_result(cmd_id)
        return json.dumps(result, indent=2)

    return mcp
