"""One-click pairing flow for Chrome extension.

Flow:
  1. Extension calls POST /api/pair → server generates 4-digit code, prints to stderr
  2. User sees code in terminal, types it in extension popup
  3. Extension calls POST /api/pair/confirm with {code} → server returns {token}

Codes expire after 120 seconds. Only one active code at a time.
"""

import secrets
import sys
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class PairConfirmRequest(BaseModel):
    code: str


class PairingManager:
    def __init__(self, token: str, ttl_seconds: int = 120):
        self._token = token
        self._ttl = ttl_seconds
        self._active_code: str | None = None
        self._code_created_at: float = 0

    def generate_code(self) -> str:
        """Generate a new 4-digit pairing code."""
        self._active_code = f"{secrets.randbelow(10000):04d}"
        self._code_created_at = time.time()
        return self._active_code

    def validate_code(self, code: str) -> str | None:
        """Validate code and return auth token if correct. Returns None if invalid."""
        if not self._active_code:
            return None
        if time.time() - self._code_created_at > self._ttl:
            self._active_code = None
            return None
        if code == self._active_code:
            self._active_code = None  # one-time use
            return self._token
        return None


def create_pairing_router(token: str) -> tuple[APIRouter, PairingManager]:
    router = APIRouter(prefix="/api")
    manager = PairingManager(token)

    @router.post("/pair")
    async def request_pair():
        code = manager.generate_code()
        # Print to stderr so the user sees it in terminal
        print(f"\n🔗 Extension pairing code:  {code}", file=sys.stderr)
        print(f"   Enter this code in the extension popup to connect.", file=sys.stderr)
        print(f"   Expires in 2 minutes.\n", file=sys.stderr)
        return {"message": "Check your terminal for the 4-digit code."}

    @router.post("/pair/confirm")
    async def confirm_pair(req: PairConfirmRequest):
        token_result = manager.validate_code(req.code)
        if token_result:
            return {"token": token_result}
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or expired code. Click 'Connect' to get a new one."},
        )

    return router, manager

