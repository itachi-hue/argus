"""Auth, rate limiting, and payload size middleware."""

import hmac
import time
from collections import deque
from typing import ClassVar

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    # Paths that don't require auth
    PUBLIC_PATHS: ClassVar[set[str]] = {"/api/health", "/api/pair", "/api/pair/confirm"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing authorization header"})

        provided = auth[7:]
        if not hmac.compare_digest(provided, self.token):
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 120):
        super().__init__(app)
        self.max_requests = max_requests
        self._timestamps: deque[float] = deque()

    # High-frequency endpoints exempt from rate limiting
    RATE_EXEMPT: ClassVar[set[str]] = {"/api/health", "/api/commands/pending"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.RATE_EXEMPT:
            return await call_next(request)

        now = time.time()
        while self._timestamps and self._timestamps[0] < now - 60:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_requests:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        self._timestamps.append(now)
        return await call_next(request)


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(status_code=413, content={"detail": "Payload too large"})
        return await call_next(request)
