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
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT" /></a>
  <img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" />
</p>

---

## 🎬 Demo

<!-- TODO: Add demo GIF/video here -->
*Coming soon: Watch Argus in action — debugging, testing, and interacting with your browser in real-time.*

## The Problem

AI coding agents like Cursor and Claude Code are powerful. They can read your codebase, write functions, refactor entire modules. But they're **blind** — they can't see what's actually running in your browser.

When your app crashes with a `TypeError`, when a button doesn't work, when the layout breaks on mobile — your agent has no idea. You're stuck manually describing bugs, copying error messages, taking screenshots, and hoping the agent understands.

## The Solution

**Argus gives AI agents eyes and hands in the browser.**

Your agent can now:
- **See** console errors, network failures, screenshots, component state
- **Act** by clicking buttons, filling forms, navigating pages, running JavaScript
- **Test** with visual regression, responsive audits, accessibility checks
- **Debug** by inspecting React/Vue components, mapping errors to source code

All through [MCP](https://modelcontextprotocol.io/) — no custom APIs, no complex setup. Just install the extension, connect, and start talking to your agent.

## TL;DR

Chrome extension + MCP server that gives AI coding agents (Cursor, Claude Code, etc.) full browser visibility and control. See errors, take screenshots, click buttons, fill forms, test accessibility — all through natural language.

## Features

- **31 MCP tools** — observe, act, inspect, test, measure
- **Natural language E2E testing** — write tests in plain English, no code
- **Works with any MCP client** — Cursor, Claude Code, Windsurf, Cline, etc.
- **Secure by default** — all data stays local, auth tokens, site filtering
- **Zero config** — auto-connects, IDE starts server automatically
- **Visual regression** — pixel-perfect UI testing
- **Accessibility audits** — catch a11y issues automatically
- **Framework-aware** — inspects React/Vue/Svelte/Angular components

## Natural Language E2E Testing

Write tests in plain English in a markdown file — no framework, no selectors, no test code:

```markdown
## Test: Login flow
1. Go to http://localhost:3000/login
2. Type "admin@test.com" in the email field
3. Click Sign In
4. Verify the heading says "Welcome back, Admin"
5. Make sure there are no console errors
```

Then tell your agent: *"Read `tests/e2e.md` and run all the tests."*

The agent executes each step using Argus tools — clicking, typing, navigating, screenshotting, checking errors — and reports results. No Playwright, no Selenium, no brittle selectors. Anyone on your team can write tests.

See [argus-demo](https://github.com/itachi-hue/argus-demo) for a full 18-test example covering search, cart, checkout, visual regression, responsive layout, and accessibility.

## MCP Compatibility

Works with any MCP-compatible IDE or client:

- **Cursor** — Add to `.cursor/mcp.json`
- **Claude Code** — `claude mcp add argus`
- **Claude Desktop** — Add to `claude_desktop_config.json`
- **Windsurf** — Configure in settings
- **Cline** — Add to config
- **Any MCP client** — Standard stdio or SSE transport

Your IDE automatically starts the Argus server — no terminal commands needed.

## MCP Tools

31 tools across 5 categories:

| Category | What the agent can do |
|---|---|
| **Observe** | Console errors · network failures · screenshots · page info · element details · error source mapping |
| **Act** | Click · type · scroll · navigate · fill forms · run JS · highlight elements |
| **Inspect** | React / Vue / Svelte / Angular component props, state, hooks, context |
| **Test** | Visual regression (pixel-diff) · responsive audit (mobile / tablet / desktop) · accessibility |
| **Runtime** | Web Vitals · localStorage · sessionStorage · cookies · accessibility |

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
<summary><strong>Runtime</strong> (7 tools)</summary>

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

## Comparison

| Feature | Argus | Playwright/Selenium | Browser DevTools | Puppeteer |
|---|---|---|---|---|
| **AI agent integration** | ✅ Native MCP | ❌ Manual scripting | ❌ Manual inspection | ❌ Manual scripting |
| **Natural language tests** | ✅ Yes | ❌ Code required | ❌ N/A | ❌ Code required |
| **Component inspection** | ✅ React/Vue/Svelte | ❌ No | ⚠️ DevTools only | ❌ No |
| **Visual regression** | ✅ Built-in | ⚠️ Requires setup | ❌ No | ⚠️ Requires setup |
| **Zero config** | ✅ Auto-connects | ❌ Complex setup | ✅ Built-in | ⚠️ Requires setup |
| **Framework-aware** | ✅ Yes | ❌ No | ⚠️ DevTools only | ❌ No |

**Argus is designed for AI agents first** — while Playwright and Selenium are powerful, they require writing code. Argus lets you describe what you want in plain English, and your agent figures out how to do it.

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+, Chrome, and an MCP-compatible IDE (Cursor, Claude Code, etc.)

### 1. Clone & Install

```bash
git clone https://github.com/itachi-hue/argus.git
cd argus

# Server
cd server
pip install -e .

# Extension
cd ../extension
npm install
npm run build
```

### 2. Add to Your IDE

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
      "cwd": "/absolute/path/to/argus/server"
    }
  }
}
```

> **Important:** Replace `/absolute/path/to/argus/server` with the actual path to the `server/` folder on your machine (e.g. `C:/Users/you/argus/server` on Windows or `/home/you/argus/server` on Linux/Mac).

Restart Cursor. Look for **argus** with a green dot under **Settings → MCP**.
</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
cd /absolute/path/to/argus/server
claude mcp add argus -- python -m argus
```

> Replace `/absolute/path/to/argus/server` with the actual path.
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
      "cwd": "/absolute/path/to/argus/server"
    }
  }
}
```

> Replace `/absolute/path/to/argus/server` with the actual path.
</details>

<details>
<summary><strong>Other MCP Clients</strong></summary>

**stdio** (local, default):
```
command: python -m argus
working directory: /absolute/path/to/argus/server
```

**SSE** (remote):
```bash
ARGUS_TRANSPORT=sse python -m argus
# Connect your client to http://127.0.0.1:42777/mcp/sse
```
</details>

### 3. Load the Chrome Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked** → select the `extension/` folder

### 4. Connect

1. Open any page in Chrome (e.g. your app at `localhost:3000`)
2. Click the Argus extension icon → **Connect**

That's it. The extension auto-detects the running server and connects instantly.

> If auto-connect isn't available (e.g. another extension already claimed it), expand **Manual setup** in the popup to paste a token from `http://127.0.0.1:42777/api/pair`.

### 5. Use It

Open your web app in Chrome and talk to your agent:

- *"Check the browser for errors and fix them"*
- *"Take a screenshot and fix the layout"*
- *"Click the login button and see what happens"*
- *"Run an accessibility audit on the page"*

## Screenshots & Visuals

<!-- TODO: Add screenshots here -->
*Coming soon: Screenshots of the extension popup, visual regression comparisons, component inspection, and more.*

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

## Roadmap

**Near-term:**
- [ ] **Chrome Web Store** — One-click install
- [ ] **Firefox extension** — Cross-browser support
- [ ] **Safari extension** — Full browser coverage
- [ ] **Record & replay** — Capture user flows and replay them
- [ ] **CI/CD integration** — Run natural language tests in GitHub Actions
- [ ] **Team features** — Share baselines, test results, dashboards
- [ ] **More frameworks** — Better support for Svelte, Solid, Qwik

**Future directions:**
- [ ] **Desktop apps** — Support Electron and native desktop applications
- [ ] **Mobile app observability** — Monitor iOS and Android apps
- [ ] **Terminal / CLI monitoring** — Observe command-line tools and scripts
- [ ] **Self-healing workflows** — Automatically detect and fix issues across platforms

Have ideas? [Open an issue](https://github.com/itachi-hue/argus/issues)!

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

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Open a PR

## License

MIT License — © 2026 Vivek Rao. See [LICENSE](LICENSE) for details.
