"""HTTP route handlers for Chrome extension data ingestion."""

from fastapi import APIRouter
from pydantic import BaseModel

from argus.core.dedup import ErrorDeduplicator
from argus.core.filters import NoiseFilter
from argus.core.image import optimize_screenshot
from argus.core.models import (
    ElementCapture,
    IngestEventsRequest,
    IngestSnapshotRequest,
    PageInfo,
    Screenshot,
)
from argus.security.sanitizer import Sanitizer
from argus.store.base import ContextStore


class UpdateSettingsRequest(BaseModel):
    max_screenshots: int | None = None

    def validated_max_screenshots(self) -> int | None:
        if self.max_screenshots is None:
            return None
        return max(1, min(self.max_screenshots, 50))


def create_router(
    store: ContextStore,
    noise_filter: NoiseFilter,
    deduplicator: ErrorDeduplicator,
    sanitizer: Sanitizer,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def health():
        return {"status": "ok", "service": "argus"}

    @router.post("/ingest/events")
    async def ingest_events(req: IngestEventsRequest):
        errors = noise_filter.filter_errors(req.errors)
        errors = deduplicator.process_batch(errors)
        if errors:
            store.add_errors(errors)

        network = noise_filter.filter_network_events(req.network_events)
        network = sanitizer.sanitize_network_events(network)
        if network:
            store.add_network_events(network)

        if req.console_events:
            store.add_console_events(req.console_events)

        return {"accepted": True}

    @router.post("/ingest/screenshot")
    async def ingest_screenshot(screenshot: Screenshot):
        screenshot.data = optimize_screenshot(screenshot.data)
        store.add_screenshot(screenshot)
        return {"accepted": True}

    @router.post("/ingest/element")
    async def ingest_element(element: ElementCapture):
        store.set_selected_element(element)
        return {"accepted": True}

    @router.post("/ingest/page-info")
    async def ingest_page_info(info: PageInfo):
        store.set_page_info(info)
        return {"accepted": True}

    @router.post("/ingest/snapshot")
    async def ingest_snapshot(req: IngestSnapshotRequest):
        if req.screenshot:
            req.screenshot.data = optimize_screenshot(req.screenshot.data)
            store.add_screenshot(req.screenshot)

        errors = noise_filter.filter_errors(req.errors)
        errors = deduplicator.process_batch(errors)
        if errors:
            store.add_errors(errors)

        network = noise_filter.filter_network_events(req.network_events)
        network = sanitizer.sanitize_network_events(network)
        if network:
            store.add_network_events(network)

        if req.console_events:
            store.add_console_events(req.console_events)

        if req.page_info:
            store.set_page_info(req.page_info)

        if req.selected_element:
            store.set_selected_element(req.selected_element)

        return {"accepted": True}

    @router.patch("/settings")
    async def update_settings(req: UpdateSettingsRequest):
        val = req.validated_max_screenshots()
        if val is not None:
            store.set_max_screenshots(val)
        return {"updated": True}

    @router.delete("/context")
    async def clear_context(event_type: str | None = None):
        store.clear(event_type)
        return {"cleared": True}

    return router
