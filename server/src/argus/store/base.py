"""Abstract context store interface."""

from abc import ABC, abstractmethod

from argus.core.models import (
    ConsoleEvent,
    ElementCapture,
    ErrorEvent,
    NetworkEvent,
    PageInfo,
    Screenshot,
)


class ContextStore(ABC):
    """Abstract interface for storing browser context data.

    Implementations: InMemoryStore (V1), PostgresStore (future).
    """

    @abstractmethod
    def add_errors(self, errors: list[ErrorEvent]) -> None: ...

    @abstractmethod
    def add_console_events(self, events: list[ConsoleEvent]) -> None: ...

    @abstractmethod
    def add_network_events(self, events: list[NetworkEvent]) -> None: ...

    @abstractmethod
    def add_screenshot(self, screenshot: Screenshot) -> None: ...

    @abstractmethod
    def set_selected_element(self, element: ElementCapture) -> None: ...

    @abstractmethod
    def set_page_info(self, info: PageInfo) -> None: ...

    @abstractmethod
    def get_errors(self, limit: int = 20, since_minutes: float | None = None) -> list[ErrorEvent]: ...

    @abstractmethod
    def get_console_events(self, limit: int = 50, level: str | None = None) -> list[ConsoleEvent]: ...

    @abstractmethod
    def get_network_events(self, limit: int = 50, method: str | None = None, url_pattern: str | None = None) -> list[NetworkEvent]: ...

    @abstractmethod
    def get_network_failures(self, limit: int = 20, status_filter: str | None = None, url_pattern: str | None = None) -> list[NetworkEvent]: ...

    @abstractmethod
    def get_screenshot(self, index: int = 0) -> Screenshot | None: ...

    @abstractmethod
    def get_screenshot_list(self) -> list[dict]: ...

    @abstractmethod
    def get_selected_element(self) -> ElementCapture | None: ...

    @abstractmethod
    def get_page_info(self) -> PageInfo | None: ...

    @abstractmethod
    def clear(self, event_type: str | None = None) -> None: ...



