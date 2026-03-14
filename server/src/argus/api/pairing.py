"""Pairing flow for Chrome extension.

Primary flow:
  1. User opens http://127.0.0.1:42777/pair in browser
  2. Copies the auth token with one click
  3. Pastes it in the extension popup

Fallback flow (4-digit code):
  1. Extension calls POST /api/pair → server generates 4-digit code
  2. User types code in extension popup
  3. Extension calls POST /api/pair/confirm → server returns token
"""

import secrets
import sys
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

_PAIR_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Argus — Connect Extension</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1117;
    color: #e4e4e7;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
  }
  .card {
    background: #1a1b23;
    border: 1px solid #2a2b35;
    border-radius: 16px;
    padding: 40px;
    max-width: 440px;
    width: 90%%;
    text-align: center;
  }
  .logo { font-size: 36px; margin-bottom: 8px; }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
  .subtitle { color: #9ca3af; font-size: 14px; margin-bottom: 32px; }
  .label { font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
  .token-box {
    background: #0f1117;
    border: 1px solid #2a2b35;
    border-radius: 10px;
    padding: 14px 16px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    color: #a78bfa;
    word-break: break-all;
    line-height: 1.5;
    margin-bottom: 16px;
    user-select: all;
  }
  .copy-btn {
    background: #6d5ace;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 32px;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    width: 100%%;
  }
  .copy-btn:hover { background: #7c6bd6; }
  .copy-btn.copied { background: #22c55e; }
  .steps {
    margin-top: 28px;
    padding-top: 24px;
    border-top: 1px solid #2a2b35;
    text-align: left;
  }
  .steps p {
    font-size: 13px;
    color: #9ca3af;
    margin-bottom: 8px;
    padding-left: 24px;
    position: relative;
  }
  .steps p span.num {
    position: absolute;
    left: 0;
    color: #6d5ace;
    font-weight: 600;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">👁️</div>
  <h1>Argus</h1>
  <p class="subtitle">Connect the Chrome extension to your MCP server</p>
  <p class="label">Auth Token</p>
  <div class="token-box" id="token">%s</div>
  <button class="copy-btn" id="copy" onclick="copyToken()">Copy Token</button>
  <div class="steps">
    <p><span class="num">1.</span> Click <strong>Copy Token</strong> above</p>
    <p><span class="num">2.</span> Open the Argus extension popup in Chrome</p>
    <p><span class="num">3.</span> Click <strong>Paste Token</strong> — done!</p>
  </div>
</div>
<script>
function copyToken() {
  const token = document.getElementById('token').textContent;
  navigator.clipboard.writeText(token).then(() => {
    const btn = document.getElementById('copy');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy Token'; btn.classList.remove('copied'); }, 2000);
  });
}
</script>
</body>
</html>"""


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

    @router.get("/pair", response_class=HTMLResponse)
    async def pair_page():
        """Browser-accessible pairing page — open http://127.0.0.1:42777/api/pair to copy the token."""
        return HTMLResponse(_PAIR_PAGE_HTML % token)

    @router.post("/pair")
    async def request_pair():
        code = manager.generate_code()
        print(f"\n🔗 Extension pairing code:  {code}", file=sys.stderr)
        print("   Enter this code in the extension popup to connect.", file=sys.stderr)
        print("   Expires in 2 minutes.\n", file=sys.stderr)
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
