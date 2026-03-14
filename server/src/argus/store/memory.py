"""Thread-safe in-memory context store using bounded deques."""

import re
import threading
import time
from collections import deque

from argus.config import Settings
from argus.core.models import (
    ConsoleEvent,
    ElementCapture,
    ErrorEvent,
    NetworkEvent,
    PageInfo,
    Screenshot,
)
from argus.store.base import ContextStore


class InMemoryStore(ContextStore):
    def __init__(self, config: Settings):
        self._lock = threading.Lock()
        self._errors: deque[ErrorEvent] = deque(maxlen=config.max_errors)
        self._console: deque[ConsoleEvent] = deque(maxlen=config.max_console)
        self._network: deque[NetworkEvent] = deque(maxlen=config.max_network)
        self._screenshots: list[Screenshot] = []
        self._max_screenshots = config.max_screenshots
        self._selected_element: ElementCapture | None = None
        self._page_info: PageInfo | None = None

    def add_errors(self, errors: list[ErrorEvent]) -> None:
        with self._lock:
            self._errors.extend(errors)

    def add_console_events(self, events: list[ConsoleEvent]) -> None:
        with self._lock:
            self._console.extend(events)

    def add_network_events(self, events: list[NetworkEvent]) -> None:
        with self._lock:
            self._network.extend(events)

    def add_screenshot(self, screenshot: Screenshot) -> None:
        with self._lock:
            self._screenshots.append(screenshot)
            if len(self._screenshots) > self._max_screenshots:
                self._screenshots = self._screenshots[-self._max_screenshots :]

    def set_selected_element(self, element: ElementCapture) -> None:
        with self._lock:
            self._selected_element = element

    def set_page_info(self, info: PageInfo) -> None:
        with self._lock:
            self._page_info = info

    def get_errors(self, limit: int = 20, since_minutes: float | None = None) -> list[ErrorEvent]:
        with self._lock:
            result = list(self._errors)
        if since_minutes is not None:
            cutoff = time.time() - since_minutes * 60
            result = [e for e in result if e.timestamp >= cutoff]
        return result[-limit:]

    def get_console_events(self, limit: int = 50, level: str | None = None) -> list[ConsoleEvent]:
        with self._lock:
            result = list(self._console)
        if level and level != "all":
            result = [e for e in result if e.level == level]
        return result[-limit:]

    def get_network_events(
        self, limit: int = 50, method: str | None = None, url_pattern: str | None = None
    ) -> list[NetworkEvent]:
        with self._lock:
            result = list(self._network)
        if method:
            result = [e for e in result if e.method.upper() == method.upper()]
        if url_pattern:
            try:
                pat = re.compile(url_pattern, re.IGNORECASE)
                result = [e for e in result if pat.search(e.url)]
            except re.error:
                pass
        return result[-limit:]

    def get_network_failures(
        self, limit: int = 20, status_filter: str | None = None, url_pattern: str | None = None
    ) -> list[NetworkEvent]:
        with self._lock:
            result = list(self._network)
        # Keep only failures: error set, or status >= 400
        result = [e for e in result if e.error or (e.status is not None and e.status >= 400)]
        if status_filter:
            if status_filter.endswith("xx"):
                prefix = status_filter[0]
                result = [e for e in result if e.status and str(e.status).startswith(prefix)]
            else:
                try:
                    code = int(status_filter)
                    result = [e for e in result if e.status == code]
                except ValueError:
                    pass
        if url_pattern:
            try:
                pat = re.compile(url_pattern, re.IGNORECASE)
                result = [e for e in result if pat.search(e.url)]
            except re.error:
                pass
        return result[-limit:]

    def get_screenshot(self, index: int = 0) -> Screenshot | None:
        with self._lock:
            if not self._screenshots:
                return None
            # index 0 = latest
            idx = -(index + 1)
            if abs(idx) > len(self._screenshots):
                return None
            return self._screenshots[idx]

    def get_screenshot_list(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "index": i,
                    "description": s.description,
                    "url": s.url,
                    "title": s.title,
                    "timestamp": s.timestamp,
                    "trigger": s.trigger,
                    "viewport": {"width": s.viewport.width, "height": s.viewport.height},
                }
                for i, s in enumerate(reversed(self._screenshots))
            ]

    def set_max_screenshots(self, max_screenshots: int) -> None:
        with self._lock:
            self._max_screenshots = max(1, max_screenshots)
            # Trim if needed
            if len(self._screenshots) > self._max_screenshots:
                self._screenshots = self._screenshots[-self._max_screenshots :]

    def get_selected_element(self) -> ElementCapture | None:
        with self._lock:
            return self._selected_element

    def get_page_info(self) -> PageInfo | None:
        with self._lock:
            return self._page_info

    def clear(self, event_type: str | None = None) -> None:
        with self._lock:
            if event_type is None:
                self._errors.clear()
                self._console.clear()
                self._network.clear()
                self._screenshots.clear()
                self._selected_element = None
                self._page_info = None
            elif event_type == "errors":
                self._errors.clear()
            elif event_type == "console":
                self._console.clear()
            elif event_type == "network":
                self._network.clear()
            elif event_type == "screenshots":
                self._screenshots.clear()
            elif event_type == "element":
                self._selected_element = None
