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
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" />
</p>

---

AI agents can read and write your code — but they're **blind** to what happens when you run it.

Argus gives your AI agent **eyes and hands** in the browser. It captures runtime context — **console errors, network failures, screenshots, UI element details** — and lets the agent **click, type, navigate, and inspect** the page directly, all through [MCP](https://modelcontextprotocol.io/) tools.

No more copy-pasting errors. No more describing what you see. Your agent calls `get_console_errors()` and sees the `TypeError`. Calls `get_screenshot()` and sees the broken layout. Calls `click_element()` and tests the fix. Calls `get_accessibility_issues()` and catches missing alt text.

## How It Works

```
Browser → Chrome Extension (captures) → MCP Server (stores) → AI Agent (queries + fixes)
```

1. **Chrome Extension** monitors your app — console errors, network requests, console logs
2. **Auto-capture** takes screenshots on page load, tab switch, clicks, and periodically
3. **Hotkey** `Ctrl+Shift+L` captures a screenshot + all current context on demand
4. **Right-click** any element → "Capture for AI Agent" to grab element details + styles
5. **Your agent** calls MCP tools to observe (`get_console_errors()`, `get_screenshot()`) and act (`click_element()`, `type_text()`, `navigate_to()`)

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
- *"Click the login button and see what happens"*
- *"Fill in the signup form and test the validation"*
- *"Run an accessibility audit on the page"*
- *"Check the performance metrics — is LCP too slow?"*

## MCP Tools (31)

### Observation (10 tools)

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
| `get_error_source_context` | Parse stack trace to file:line:column with workspace path mapping |
| `clear_context` | Clear stored context |

### Browser Actions (8 tools)

| Tool | What it does |
|------|-------------|
| `click_element` | Click any element by CSS selector |
| `type_text` | Type into input fields (React/Vue compatible) |
| `scroll_to` | Scroll to element, position, or direction |
| `navigate_to` | Navigate to any URL |
| `get_text` | Read text content + attributes of any element |
| `run_javascript` | Execute JS in page context (access `window`, React internals, etc.) |
| `highlight_element` | Highlight an element with a colored outline for debugging |
| `wait_for_element` | Wait for an element to appear (for async UI) |

### Framework Inspection (2 tools)

| Tool | What it does |
|------|-------------|
| `detect_framework` | Detect React, Vue, Svelte, Angular, Next.js, Nuxt, jQuery |
| `inspect_component` | Read component name, props, state, hooks, context for any element |

### Visual Regression (4 tools)

| Tool | What it does |
|------|-------------|
| `snapshot_baseline` | Save current screenshot as a named baseline |
| `compare_with_baseline` | Pixel-diff current vs baseline, returns diff image |
| `list_baselines` | List all saved baselines |
| `delete_baseline` | Delete a saved baseline |

### Advanced (7 tools)

| Tool | What it does |
|------|-------------|
| `fill_form` | Fill multiple form fields in one call |
| `capture_at_viewport` | Resize browser + screenshot (responsive testing) |
| `responsive_audit` | Capture at mobile, tablet, desktop breakpoints in one call |
| `get_performance_metrics` | Web Vitals, memory, resource counts |
| `get_storage` | Read localStorage / sessionStorage |
| `get_cookies` | List cookies for current domain |
| `get_accessibility_issues` | Audit for missing alt text, labels, contrast, headings |

## Features

- **31 MCP tools** — observe, act, inspect, compare, audit
- **Component inspector** — read React/Vue/Svelte/Angular component props, state, hooks, and context
- **Visual regression** — snapshot baselines and pixel-diff after changes
- **Error source mapping** — parse stack traces to file:line:column, maps URLs to workspace paths
- **Responsive audit** — capture mobile, tablet, and desktop screenshots in one call
- **Agent browser actions** — click, type, scroll, navigate, fill forms, run JS in the page
- **Framework detection** — auto-detect React, Vue, Svelte, Angular, Next.js, Nuxt, jQuery
- **Performance metrics** — Web Vitals (LCP, FCP, TTFB), memory, resource breakdown
- **Accessibility auditing** — missing alt text, unlabeled inputs, heading skips, low contrast
- **Storage & cookies** — read localStorage, sessionStorage, and cookies
- **Auto-capture** — screenshots on page load, tab switch, user clicks, and periodic intervals
- **Smart screenshots** — JPEG compressed, resized, sent as native image content blocks (low token cost)
- **Noise filtering** — blocks analytics, HMR, browser extension traffic automatically
- **Error deduplication** — same error in a loop won't flood the buffer
- **Sensitive data stripping** — `Authorization`, `Cookie` headers redacted automatically
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
| Agent Actions | On | Let AI click, type, navigate, and inspect the page |

## Project Structure

```
argus/
├── server/                     # Python MCP server
│   ├── src/argus/
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── mcp/tools.py        # MCP tool definitions
│   │   ├── api/                # FastAPI HTTP server
│   │   ├── core/               # Models, filters, dedup, image opt, commands, baselines, stack parser
│   │   ├── store/              # Storage abstraction (in-memory)
│   │   └── security/           # Sensitive data sanitizer
│   ├── tests/                  # 140+ tests
│   └── pyproject.toml
├── extension/                  # Chrome extension (Manifest V3)
│   ├── src/
│   │   ├── background/         # Service worker
│   │   ├── content/            # Content script + click capture
│   │   ├── injected/           # Page-context monitors (console, network)
│   │   └── popup/              # Settings UI
│   ├── tests/                  # 76 tests (vitest + jsdom)
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
pytest tests/ -v              # run tests (140+ tests)
ruff check src/ tests/        # lint
ruff format src/ tests/       # format

# Extension
cd extension
npm install
npm run build                 # production build
npm run watch                 # dev mode with auto-rebuild
npm test                      # run tests (76 tests)
```

## License

MIT — see [LICENSE](LICENSE).
