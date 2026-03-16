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
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0c0c14;
    color: #e4e4e7;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
  }
  .card {
    background: #16171f;
    border: 1px solid #25262f;
    border-radius: 20px;
    padding: 44px 40px;
    max-width: 420px;
    width: 100%%;
    text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
  }
  .logo-wrap {
    margin-bottom: 16px;
  }
  .logo-wrap svg {
    filter: drop-shadow(0 4px 20px rgba(99, 102, 241, 0.3));
  }
  h1 {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 4px;
    letter-spacing: -0.5px;
  }
  .tagline {
    font-size: 12px;
    font-weight: 600;
    color: #818cf8;
    letter-spacing: 0.3px;
    margin-bottom: 32px;
  }
  .label {
    font-size: 11px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
    margin-bottom: 10px;
  }
  .token-box {
    background: #0c0c14;
    border: 1px solid #25262f;
    border-radius: 10px;
    padding: 14px 16px;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    color: #a78bfa;
    word-break: break-all;
    line-height: 1.6;
    margin-bottom: 16px;
    user-select: all;
    cursor: text;
    transition: border-color 0.2s;
  }
  .token-box:hover {
    border-color: #6366f1;
  }
  .copy-btn {
    background: linear-gradient(135deg, #6366f1, #7c3aed);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 13px 32px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    width: 100%%;
    position: relative;
    overflow: hidden;
  }
  .copy-btn::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, transparent 40%%, rgba(255,255,255,0.1));
    pointer-events: none;
  }
  .copy-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(99, 102, 241, 0.35);
  }
  .copy-btn:active { transform: translateY(0); }
  .copy-btn.copied {
    background: linear-gradient(135deg, #22c55e, #16a34a);
  }
  .steps {
    margin-top: 28px;
    padding-top: 24px;
    border-top: 1px solid #1f2029;
  }
  .step {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 7px 0;
    text-align: left;
  }
  .step-num {
    width: 24px;
    height: 24px;
    border-radius: 50%%;
    background: rgba(99, 102, 241, 0.12);
    color: #818cf8;
    font-size: 12px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .step-text {
    font-size: 13px;
    color: #9ca3af;
  }
  .step-text strong {
    color: #e4e4e7;
    font-weight: 600;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo-wrap">
    <svg width="52" height="52" viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="8" fill="url(#lg)"/>
      <line x1="16" y1="3" x2="16" y2="7" stroke="white" stroke-width="1.5" opacity="0.5" stroke-linecap="round"/>
      <line x1="16" y1="25" x2="16" y2="29" stroke="white" stroke-width="1.5" opacity="0.5" stroke-linecap="round"/>
      <line x1="3" y1="16" x2="7" y2="16" stroke="white" stroke-width="1.5" opacity="0.5" stroke-linecap="round"/>
      <line x1="25" y1="16" x2="29" y2="16" stroke="white" stroke-width="1.5" opacity="0.5" stroke-linecap="round"/>
      <line x1="6.2" y1="6.2" x2="8.8" y2="8.8" stroke="white" stroke-width="1.3" opacity="0.35" stroke-linecap="round"/>
      <line x1="25.8" y1="6.2" x2="23.2" y2="8.8" stroke="white" stroke-width="1.3" opacity="0.35" stroke-linecap="round"/>
      <line x1="6.2" y1="25.8" x2="8.8" y2="23.2" stroke="white" stroke-width="1.3" opacity="0.35" stroke-linecap="round"/>
      <line x1="25.8" y1="25.8" x2="23.2" y2="23.2" stroke="white" stroke-width="1.3" opacity="0.35" stroke-linecap="round"/>
      <path d="M6.5 16C6.5 16 10.5 10.5 16 10.5C21.5 10.5 25.5 16 25.5 16C25.5 16 21.5 21.5 16 21.5C10.5 21.5 6.5 16 6.5 16Z" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="16" cy="16" r="3.5" fill="white" opacity="0.95"/>
      <circle cx="16" cy="16" r="1.5" fill="#6366f1"/>
      <defs><linearGradient id="lg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>
    </svg>
  </div>
  <h1>Argus</h1>
  <p class="tagline">Eyes & Hands for AI</p>
  <p class="label">Your Auth Token</p>
  <div class="token-box" id="token">%s</div>
  <button class="copy-btn" id="copy" onclick="copyToken()">Copy Token</button>
  <div class="steps">
    <div class="step">
      <span class="step-num">1</span>
      <span class="step-text">Click <strong>Copy Token</strong> above</span>
    </div>
    <div class="step">
      <span class="step-num">2</span>
      <span class="step-text">Open the <strong>Argus extension</strong> in Chrome toolbar</span>
    </div>
    <div class="step">
      <span class="step-num">3</span>
      <span class="step-text">Click <strong>Paste Token & Connect</strong></span>
    </div>
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
