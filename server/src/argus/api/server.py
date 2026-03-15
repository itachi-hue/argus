"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

from argus.api.middleware import AuthMiddleware, PayloadSizeMiddleware, RateLimitMiddleware
from argus.api.pairing import create_pairing_router
from argus.api.routes import create_router
from argus.config import Settings
from argus.core.commands import CommandQueue
from argus.core.dedup import ErrorDeduplicator
from argus.core.filters import NoiseFilter
from argus.security.sanitizer import Sanitizer
from argus.store.base import ContextStore


def create_app(
    store: ContextStore,
    config: Settings,
    mcp: FastMCP | None = None,
    command_queue: CommandQueue | None = None,
) -> FastAPI:
    app = FastAPI(title="Argus", version="0.1.0", docs_url=None, redoc_url=None)

    # CORS — allow Chrome extension to POST
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # Middleware (applied in reverse order)
    app.add_middleware(PayloadSizeMiddleware, max_size=config.max_payload_size)
    app.add_middleware(RateLimitMiddleware, max_requests=config.rate_limit)
    app.add_middleware(AuthMiddleware, token=config.auth_token)

    # Processing pipeline components
    noise_filter = NoiseFilter()
    deduplicator = ErrorDeduplicator()
    sanitizer = Sanitizer(max_body_length=config.max_body_length)

    # Command queue for agent-initiated browser actions
    if command_queue is None:
        command_queue = CommandQueue()

    # Routes
    router = create_router(store, noise_filter, deduplicator, sanitizer, command_queue, auth_token=config.auth_token)
    app.include_router(router)

    # Pairing routes (no auth required)
    pair_router, _ = create_pairing_router(config.auth_token)
    app.include_router(pair_router)

    # Mount MCP SSE transport if provided
    if mcp is not None:
        sse_app = mcp.sse_app(mount_path="/mcp")
        app.mount("/mcp", sse_app)

    return app
