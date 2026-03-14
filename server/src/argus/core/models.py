"""Pydantic data models for all Argus event types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Viewport(BaseModel):
    width: int
    height: int


class BoundingRect(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    source: str = ""
    lineno: int = 0
    colno: int = 0
    stack: str = ""
    timestamp: float
    occurrence_count: int = 1


class ConsoleEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str  # log, warn, error, info, debug
    args: list[str] = Field(default_factory=list)
    timestamp: float
    source: str = ""
    lineno: int = 0


class NetworkEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    url: str
    status: int | None = None
    status_text: str = ""
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_headers: dict[str, str] = Field(default_factory=dict)
    request_body: str | None = None
    response_body: str | None = None
    duration_ms: float | None = None
    timestamp: float
    error: str | None = None


class Screenshot(BaseModel):
    data: str  # base64 JPEG
    url: str
    timestamp: float
    viewport: Viewport
    trigger: str = "hotkey"  # hotkey, element, auto


class ElementCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selector: str
    computed_styles: dict[str, str] = Field(default_factory=dict)
    html: str = ""
    text: str = ""
    bounding_rect: BoundingRect
    parent_html: str = ""
    timestamp: float
    url: str
    screenshot_index: int | None = None


class PageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    viewport: Viewport
    timestamp: float


# --- Request models for HTTP API ---


class IngestEventsRequest(BaseModel):
    errors: list[ErrorEvent] = Field(default_factory=list)
    console_events: list[ConsoleEvent] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)


class IngestSnapshotRequest(BaseModel):
    screenshot: Screenshot | None = None
    errors: list[ErrorEvent] = Field(default_factory=list)
    console_events: list[ConsoleEvent] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    page_info: PageInfo | None = None
    selected_element: ElementCapture | None = None
    timestamp: float



