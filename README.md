<p align="center">
  <img src="extension/icons/icon-128.png" alt="Argus" width="80" />
</p>

<h1 align="center">Argus</h1>

<p align="center">
  <strong>Give your AI agent eyes and hands in the browser.</strong>
</p>

<p align="center">
  <a href="https://github.com/itachi-hue/argus/actions/workflows/test.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/test.yml/badge.svg" alt="Tests" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/lint.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/lint.yml/badge.svg" alt="Lint" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/build.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/build.yml/badge.svg" alt="Build" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-orange.svg" alt="BSL 1.1" /></a>
  <img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" />
</p>

---

Argus connects your AI agent to your browser through [MCP](https://modelcontextprotocol.io/). It captures runtime context — console errors, network failures, screenshots — and lets the agent click, type, navigate, and inspect the page directly.

Works with **Cursor** · **Claude Code** · **Claude Desktop** · **Windsurf** · **Cline** · and any MCP-compatible client.

## How It Works

```
Browser → Chrome Extension (captures) → MCP Server (stores) → AI Agent (reads + acts)
```

## MCP Tools

31 tools across 5 categories:

| Category | What the agent can do |
|---|---|
| **Observe** | Console errors · network failures · screenshots · page info · element details · error source mapping |
| **Act** | Click · type · scroll · navigate · fill forms · run JS · highlight elements |
| **Inspect** | React / Vue / Svelte / Angular component props, state, hooks, context |
| **Test** | Visual regression (pixel-diff) · responsive audit (mobile / tablet / desktop) · accessibility |
| **Measure** | Web Vitals · localStorage · sessionStorage · cookies |

<details>
<summary>Full tool reference</summary>

**Observation** (10) — `get_console_errors` · `get_console_logs` · `get_network_failures` · `get_network_log` · `get_screenshot` · `list_screenshots` · `get_selected_element` · `get_page_info` · `get_error_source_context` · `clear_context`

**Browser Actions** (8) — `click_element` · `type_text` · `scroll_to` · `navigate_to` · `get_text` · `run_javascript` · `highlight_element` · `wait_for_element`

**Framework Inspection** (2) — `detect_framework` · `inspect_component`

**Visual Regression** (4) — `snapshot_baseline` · `compare_with_baseline` · `list_baselines` · `delete_baseline`

**Advanced** (7) — `fill_form` · `capture_at_viewport` · `responsive_audit` · `get_performance_metrics` · `get_storage` · `get_cookies` · `get_accessibility_issues`

</details>

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
<summary><strong>Other MCP Clients</strong></summary>

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

1. Open **http://127.0.0.1:42777/api/pair** in your browser → click **Copy Token**
2. Click the Argus extension icon → **Paste Token & Connect**

### 5. Use It

Open your web app in Chrome and talk to your agent:

- *"Check the browser for errors and fix them"*
- *"Take a screenshot and fix the layout"*
- *"Click the login button and see what happens"*
- *"Run an accessibility audit on the page"*

## Security

- All data stays on your machine — server binds to `127.0.0.1` only
- Auth token required on every request (constant-time comparison)
- `Authorization`, `Cookie`, `Set-Cookie` headers automatically redacted
- Request/response bodies truncated · in-memory only · rate limited

<details>
<summary><strong>Configuration</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGUS_TRANSPORT` | `stdio` | `stdio`, `sse`, or `all` |
| `ARGUS_PORT` | `42777` | HTTP server port |
| `ARGUS_AUTH_TOKEN` | auto-generated | Auth token |
| `ARGUS_MAX_ERRORS` | `100` | Max errors in buffer |
| `ARGUS_MAX_SCREENSHOTS` | `15` | Max screenshots stored |
| `ARGUS_RATE_LIMIT` | `120` | Max requests/minute |

</details>

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

Business Source License 1.1 — © 2026 Vivek Rao. Free for non-commercial use. Commercial use requires a license. Converts to Apache 2.0 on March 14, 2030. See [LICENSE](LICENSE) for details.
