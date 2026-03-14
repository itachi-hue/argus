<p align="center">
  <img src="extension/icons/icon-128.png" alt="Argus" width="80" />
</p>

<h1 align="center">Argus</h1>

<p align="center">
  <strong>Give your AI coding agent eyes into the browser.</strong>
</p>

<p align="center">
  <a href="https://github.com/itachi-hue/argus/actions/workflows/test.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/test.yml/badge.svg" alt="Tests" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/lint.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/lint.yml/badge.svg" alt="Lint" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/build.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/build.yml/badge.svg" alt="Build" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" />
</p>

---

AI agents can read and write your code — but they're **blind** to what happens when you run it.

Argus captures browser runtime context — **console errors, network failures, screenshots, UI element details** — and exposes it all as [MCP](https://modelcontextprotocol.io/) tools that any AI agent can call.

No more copy-pasting errors. No more describing what you see. Your agent calls `get_console_errors()` and sees the `TypeError`. Calls `get_screenshot()` and sees the broken layout. Calls `get_network_failures()` and sees the `401`. Then fixes the code.

## How It Works

```
Browser → Chrome Extension (captures) → MCP Server (stores) → AI Agent (queries + fixes)
```

1. **Chrome Extension** monitors your app — console errors, network requests, console logs
2. **Auto-capture** takes screenshots on page load, tab switch, clicks, and periodically
3. **Hotkey** `Ctrl+Shift+L` captures a screenshot + all current context on demand
4. **Right-click** any element → "Capture for AI Agent" to grab element details + styles
5. **Your agent** calls MCP tools like `get_console_errors()`, `get_screenshot()`, `get_selected_element()` and fixes the code

## Works With

Any MCP-compatible client: **Cursor** · **Claude Code** · **Claude Desktop** · **Windsurf** · **Cline** · **Continue** · and more.

## Quick Start

### 1. Install the MCP Server

```bash
cd server
pip install -e .
```

### 2. Connect to Your AI Agent

<details>
<summary><strong>Cursor</strong></summary>

Add to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "argus": {
      "command": "python",
      "args": ["-m", "argus"],
      "cwd": "/path/to/argus/server"
    }
  }
}
```

Restart Cursor. Look for **argus** with a green dot under **Settings → MCP**.
</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add argus -- python -m argus
```
</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "argus": {
      "command": "python",
      "args": ["-m", "argus"],
      "cwd": "/path/to/argus/server"
    }
  }
}
```
</details>

<details>
<summary><strong>Other MCP Clients (Windsurf, Cline, Continue, etc.)</strong></summary>

**stdio** (local, default):
```
command: python -m argus
working directory: /path/to/argus/server
```

**SSE** (remote):
```bash
ARGUS_TRANSPORT=sse python -m argus
# Connect your client to http://127.0.0.1:42777/mcp/sse
```
</details>

### 3. Install the Chrome Extension

```bash
cd extension
npm install
npm run build
```

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder

### 4. Pair Extension to Server

Click the Argus extension icon → **Connect to Server** → enter the 4-digit code from your terminal. Done.

Alternatives: **Paste Token from Clipboard** or enter manually via **Manual setup**.

### 5. Use It

Open your web app in Chrome and talk to your agent:

- *"Check the browser for errors and fix them"*
- *"Look at the screenshot and fix the layout"*
- *"The API call is failing, check network failures"*
- *"What does the browser console show?"*

## MCP Tools

| Tool | What it does |
|------|-------------|
| `get_console_errors` | JS errors with stack traces |
| `get_console_logs` | Console output (log, warn, info, debug) |
| `get_network_failures` | Failed HTTP requests (4xx, 5xx) |
| `get_network_log` | All recent network requests |
| `get_screenshot` | Browser screenshot as native image |
| `list_screenshots` | Timeline of all captured screenshots with metadata |
| `get_selected_element` | Right-click captured element (selector, styles, HTML) |
| `get_page_info` | Current page URL, title, viewport |
| `clear_context` | Clear stored context |

## Features

- **Auto-capture** — screenshots on page load, tab switch, user clicks, and periodic intervals
- **Configurable** — capture interval, max screenshots, toggle per-feature from the popup
- **Smart screenshots** — JPEG compressed, resized, sent as native image content blocks (low token cost)
- **Noise filtering** — blocks analytics, HMR, browser extension traffic automatically
- **Error deduplication** — same error in a loop won't flood the buffer
- **Sensitive data stripping** — `Authorization`, `Cookie` headers redacted automatically
- **Descriptive timeline** — each screenshot has title + description so the AI picks the right one
- **Local-first** — all data stays on your machine, server binds to `127.0.0.1` only

## Configuration

### Server (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGUS_TRANSPORT` | `stdio` | `stdio`, `sse`, or `all` |
| `ARGUS_PORT` | `42777` | HTTP server port |
| `ARGUS_AUTH_TOKEN` | auto-generated | Auth token |
| `ARGUS_MAX_ERRORS` | `100` | Max errors in buffer |
| `ARGUS_MAX_SCREENSHOTS` | `15` | Max screenshots stored |
| `ARGUS_RATE_LIMIT` | `120` | Max requests/minute |

### Extension (popup UI)

| Setting | Default | Description |
|---------|---------|-------------|
| Auto Screenshots | On | Capture on page load, tab switch, click, periodic |
| Capture interval | 30 sec | Periodic capture frequency (10–300s) |
| Max screenshots | 15 | Rolling buffer size (3–50) |
| Console & Errors | On | Capture console logs and JS errors |
| Network Traffic | On | Capture HTTP requests |

## Project Structure

```
argus/
├── server/                     # Python MCP server
│   ├── src/argus/
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── mcp/tools.py        # MCP tool definitions
│   │   ├── api/                # FastAPI HTTP server
│   │   ├── core/               # Models, filters, dedup, image optimization
│   │   ├── store/              # Storage abstraction (in-memory)
│   │   └── security/           # Sensitive data sanitizer
│   ├── tests/                  # 111 tests
│   └── pyproject.toml
├── extension/                  # Chrome extension (Manifest V3)
│   ├── src/
│   │   ├── background/         # Service worker
│   │   ├── content/            # Content script + click capture
│   │   ├── injected/           # Page-context monitors
│   │   └── popup/              # Settings UI
│   └── manifest.json
├── docs/
│   └── ARCHITECTURE.md         # Technical architecture
├── .github/workflows/          # CI: lint, test, build
└── LICENSE                     # MIT
```

## Security

- Server binds to `127.0.0.1` only — never exposed to network
- Auth token required on every request (constant-time comparison)
- `Authorization`, `Cookie`, `Set-Cookie` headers automatically redacted
- Request/response bodies truncated to 2000 chars
- All data in-memory only — cleared on server restart
- Rate limiting: 120 req/min

## Development

```bash
# Server
cd server
pip install -e ".[dev]"
pytest tests/ -v              # run tests
ruff check src/ tests/        # lint
ruff format src/ tests/       # format

# Extension
cd extension
npm install
npm run build                 # production build
npm run watch                 # dev mode with auto-rebuild
```

## License

[MIT](LICENSE) — Vivek Rao
