"""Pairing flow for Chrome extension.

Two pairing mechanisms:
  1. Web page — GET /pair → HTML page with token + copy button.  Users open
     http://127.0.0.1:42777/pair in their browser.  Works even when the server
     was spawned by an IDE (Cursor / Claude Code) where stderr is hidden.
  2. 4-digit code — POST /api/pair → code to stderr → POST /api/pair/confirm.
     Good when the user has terminal access.

Codes expire after 120 seconds. Only one active code at a time.
"""

import secrets
import sys
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

_PAIR_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Argus — Pair Extension</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:#0f0f0f;color:#e0e0e0;display:flex;justify-content:center;
       align-items:center;min-height:100vh}
  .card{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:16px;
        padding:40px;max-width:480px;width:100%;text-align:center}
  .logo{font-size:2em;margin-bottom:4px}
  h1{font-size:1.5em;margin-bottom:4px;color:#fff}
  .subtitle{color:#888;font-size:.9em;margin-bottom:32px}
  .token-label{font-size:.8em;color:#888;text-transform:uppercase;
               letter-spacing:.1em;margin-bottom:8px}
  .token-box{background:#0d0d1a;border:1px solid #333;border-radius:8px;
             padding:14px;font-family:'SF Mono',Consolas,monospace;font-size:.85em;
             word-break:break-all;color:#7dd3fc;margin-bottom:16px;cursor:pointer;
             transition:border-color .2s}
  .token-box:hover{border-color:#7dd3fc}
  .btn{background:#7dd3fc;color:#0f0f0f;border:none;border-radius:8px;
       padding:12px 24px;font-size:.95em;font-weight:600;cursor:pointer;
       transition:opacity .2s;width:100%}
  .btn:hover{opacity:.85}
  .btn:active{transform:scale(.98)}
  .copied{color:#4ade80;font-size:.85em;margin-top:12px;opacity:0;transition:opacity .3s}
  .copied.show{opacity:1}
  .steps{text-align:left;margin-top:28px;padding-top:20px;border-top:1px solid #2a2a4a}
  .steps h3{font-size:.85em;color:#888;text-transform:uppercase;letter-spacing:.05em;
            margin-bottom:12px}
  .steps ol{padding-left:20px;color:#aaa;font-size:.85em;line-height:1.8}
  .steps code{background:#0d0d1a;padding:2px 6px;border-radius:4px;font-size:.9em}
</style>
</head>
<body>
<div class="card">
  <div class="logo">👁️</div>
  <h1>Argus</h1>
  <p class="subtitle">Pair your Chrome extension</p>

  <p class="token-label">Auth Token</p>
  <div class="token-box" id="token" title="Click to copy">{token}</div>
  <button class="btn" onclick="copyToken()">Copy to Clipboard</button>
  <p class="copied" id="copied">Copied!</p>

  <div class="steps">
    <h3>Next steps</h3>
    <ol>
      <li>Click the <strong>Argus</strong> extension icon in Chrome</li>
      <li>Click <strong>Paste Token from Clipboard</strong></li>
      <li>You're connected!</li>
    </ol>
    <p style="color:#666;font-size:.8em;margin-top:12px">
      Or expand <strong>Manual setup</strong> in the popup and paste the token there.
    </p>
  </div>
</div>
<script>
function copyToken(){
  const t=document.getElementById('token').textContent;
  navigator.clipboard.writeText(t).then(()=>{
    const c=document.getElementById('copied');
    c.classList.add('show');
    setTimeout(()=>c.classList.remove('show'),2000);
  });
}
// Also copy on click of the token box
document.getElementById('token').addEventListener('click',copyToken);
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

    @property
    def token(self) -> str:
        return self._token

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


def create_pairing_router(token: str) -> tuple[APIRouter, PairingManager, APIRouter]:
    router = APIRouter(prefix="/api")
    manager = PairingManager(token)

    @router.post("/pair")
    async def request_pair():
        code = manager.generate_code()
        # Print to stderr so the user sees it in terminal
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

    # Web pairing page (mounted at /pair, not /api/pair)
    page_router = APIRouter()

    @page_router.get("/pair")
    async def pair_page():
        """Serve an HTML page showing the auth token with a copy button.

        Users open http://127.0.0.1:42777/pair in their browser.
        This works even when the MCP server was spawned by an IDE
        (Cursor, Claude Code) and stderr is not visible.
        """
        html = _PAIR_PAGE_TEMPLATE.replace("{token}", manager.token)
        return HTMLResponse(content=html)

    return router, manager, page_router
