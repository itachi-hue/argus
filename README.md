<p align="center">
  <img src="extension/icons/icon-128.png" alt="Argus" width="80" />
</p>

<h1 align="center">Argus</h1>

<p align="center">
  <strong>Eyes and hands for AI agents.</strong>
</p>

<p align="center">
  <a href="https://github.com/itachi-hue/argus/actions/workflows/test.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/test.yml/badge.svg" alt="Tests" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/lint.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/lint.yml/badge.svg" alt="Lint" /></a>
  <a href="https://github.com/itachi-hue/argus/actions/workflows/build.yml"><img src="https://github.com/itachi-hue/argus/actions/workflows/build.yml/badge.svg" alt="Build" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-orange.svg" alt="BSL 1.1" /></a>
  <img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" />
</p>

---

AI agents can read and write code — but they can't see or interact with what's running. Argus fixes that, starting with the browser.

Your agent can see console errors, screenshots, network failures, component state — and act on them: click buttons, fill forms, navigate pages, run JS, test responsiveness. All through [MCP](https://modelcontextprotocol.io/).

Works with **Cursor** · **Claude Code** · **Claude Desktop** · **Windsurf** · **Cline** · and any MCP-compatible client.

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
<summary><strong>Observation</strong> (10 tools)</summary>

| Tool | Description |
|------|-------------|
| `get_console_errors` | JS errors with stack traces |
| `get_console_logs` | Console output (log, warn, info, debug) |
| `get_network_failures` | Failed HTTP requests (4xx, 5xx) |
| `get_network_log` | All recent network requests |
| `get_screenshot` | Browser screenshot as native image |
| `list_screenshots` | Timeline of captured screenshots with metadata |
| `get_selected_element` | Right-click captured element — selector, styles, HTML |
| `get_page_info` | Current page URL, title, viewport |
| `get_error_source_context` | Parse stack trace to file:line:column |
| `clear_context` | Clear stored context |

</details>

<details>
<summary><strong>Browser Actions</strong> (8 tools)</summary>

| Tool | Description |
|------|-------------|
| `click_element` | Click any element by CSS selector |
| `type_text` | Type into inputs (React/Vue compatible) |
| `scroll_to` | Scroll to element, position, or direction |
| `navigate_to` | Navigate to any URL |
| `get_text` | Read text content of any element |
| `run_javascript` | Execute JS in page context |
| `highlight_element` | Highlight element with colored outline |
| `wait_for_element` | Wait for element to appear in DOM |

</details>

<details>
<summary><strong>Framework Inspection</strong> (2 tools)</summary>

| Tool | Description |
|------|-------------|
| `detect_framework` | Detect React, Vue, Svelte, Angular, Next.js, Nuxt, jQuery |
| `inspect_component` | Read component props, state, hooks, context |

</details>

<details>
<summary><strong>Visual Regression</strong> (4 tools)</summary>

| Tool | Description |
|------|-------------|
| `snapshot_baseline` | Save current screenshot as named baseline |
| `compare_with_baseline` | Pixel-diff current vs baseline |
| `list_baselines` | List all saved baselines |
| `delete_baseline` | Delete a saved baseline |

</details>

<details>
<summary><strong>Advanced</strong> (7 tools)</summary>

| Tool | Description |
|------|-------------|
| `fill_form` | Fill multiple form fields in one call |
| `capture_at_viewport` | Resize browser + screenshot |
| `responsive_audit` | Capture at mobile, tablet, desktop breakpoints |
| `get_performance_metrics` | Web Vitals, memory, resource counts |
| `get_storage` | Read localStorage / sessionStorage |
| `get_cookies` | List cookies for current domain |
| `get_accessibility_issues` | Audit for missing alt text, labels, contrast |

</details>

## Quick Start

### 1. Install the MCP Server

```bash
cd server
pip install -e .
```

### 2. Connect to Your AI Agent

Your IDE starts the Argus server automatically — no need to run anything in the terminal.

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

### 4. Connect Extension to Server

1. Open any page in Chrome (e.g. your app at `localhost:3000`)
2. Click the Argus extension icon → **Connect**

That's it. The extension auto-detects the server and connects instantly. If auto-connect isn't available (e.g. another extension already claimed it), expand **Manual setup** in the popup to paste a token from **http://127.0.0.1:42777/api/pair**.

### 5. Use It

Open your web app in Chrome and talk to your agent:

- *"Check the browser for errors and fix them"*
- *"Take a screenshot and fix the layout"*
- *"Click the login button and see what happens"*
- *"Run an accessibility audit on the page"*

## Security

- All data stays on your machine — server binds to `127.0.0.1` only
- Auth token required on every request (constant-time comparison)
- Auto-connect is first-come-first-served — locks after the first extension connects
- WebSocket authenticated via token on handshake
- `Authorization`, `Cookie`, `Set-Cookie` headers automatically redacted
- Request/response bodies truncated · in-memory only · rate limited
- **Site filtering** — configurable allowlist / denylist in extension settings to control which sites Argus can observe

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
