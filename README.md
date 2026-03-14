# 🔭 Argus — Give Your AI Agent Eyes

Argus bridges the gap between your running app and your AI coding agent. It captures what's happening in the browser — console errors, network failures, screenshots, UI element details — and exposes it all as MCP tools that any AI agent can call.

**The problem:** AI agents can read and write your code, but they're blind to what happens when you run it. You manually copy errors, describe UI bugs, paste network failures. Dozens of times a day.

**The fix:** Argus captures runtime context automatically. Your agent calls `get_console_errors()` and sees the `TypeError`. Calls `get_screenshot()` and sees the broken UI. Calls `get_network_failures()` and sees the `401`. Then fixes the code. No copy-pasting. No describing what you saw.

## How It Works

```
Browser (your app) → Chrome Extension (captures) → MCP Server (stores) → AI Agent (queries + fixes)
```

1. **Chrome Extension** monitors your app passively — console errors, network requests, console logs
2. You hit **Ctrl+Shift+L** when something breaks — extension captures a screenshot + all context
3. You right-click any element → **"Capture for AI Agent"** — captures element details, styles, and a highlighted screenshot
4. Your agent calls MCP tools like `get_console_errors()`, `get_screenshot()`, `get_selected_element()`
5. Agent sees the problem, finds the code, makes the fix

## Works With

Any MCP-compatible client: **Cursor**, **Claude Code**, **Claude Desktop**, **Windsurf**, **Cline**, **Continue**, and more.

## Quick Start

### 1. Install the MCP Server

```bash
cd server
pip install -e .
```

### 2. Connect to Your AI Agent

#### Cursor

Add to your project's `.cursor/mcp.json` (or global `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "argus": {
      "command": "python",
      "args": ["-m", "argus"],
      "cwd": "/path/to/project_argus/server"
    }
  }
}
```

On Windows, use the full path:

```json
{
  "mcpServers": {
    "argus": {
      "command": "python",
      "args": ["-m", "argus"],
      "cwd": "C:\\Users\\YourName\\projects\\project_argus\\server"
    }
  }
}
```

After saving, restart Cursor. You should see **argus** listed under **Settings → MCP** with a green dot.

#### Claude Code

```bash
claude mcp add argus -- python -m argus
```

That's it. Claude Code will start the server automatically when you open a session.

#### Claude Desktop

Add to `claude_desktop_config.json` (find it via **Settings → Developer → Edit Config**):

```json
{
  "mcpServers": {
    "argus": {
      "command": "python",
      "args": ["-m", "argus"],
      "cwd": "/path/to/project_argus/server"
    }
  }
}
```

Restart Claude Desktop after saving.

#### Other MCP Clients (Windsurf, Cline, Continue, etc.)

Any client that supports MCP stdio transport works. Point it at:

```
command: python -m argus
working directory: /path/to/project_argus/server
```

### 3. Get the Auth Token

When the MCP server starts, it writes the auth token to `~/.argus/config.json`. You can grab it with:

```bash
# Mac/Linux
cat ~/.argus/config.json

# Windows (PowerShell)
Get-Content "$env:USERPROFILE\.argus\config.json"
```

The token is auto-generated on first run and persists across restarts.

### 4. Install the Chrome Extension

```bash
cd extension
npm install
npm run build
```

Then load it in Chrome:

1. Open `chrome://extensions`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked** → select the `extension/` folder
4. Click the Argus extension icon in the toolbar → paste the auth token from step 3 → **Save & Connect**

The popup should show a green **Connected** status.

### 5. Use It

1. Open your web app in Chrome
2. **Automatic:** Errors and network requests are captured passively in the background
3. **Hotkey:** Hit **Ctrl+Shift+L** (Mac: **Cmd+Shift+L**) to capture a screenshot + all current context
4. **Right-click:** Right-click any element → **Capture for AI Agent** to capture element details + styles
5. **Ask your agent:**
   - *"Check the browser for errors and fix them"*
   - *"Look at the screenshot and fix the layout"*
   - *"The API call is failing, check network failures and fix the backend"*
   - *"What does the browser console show?"*

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_console_errors` | Recent JS errors with stack traces |
| `get_console_logs` | Console output (log, warn, info, debug) |
| `get_network_failures` | Failed HTTP requests (4xx, 5xx, network errors) |
| `get_network_log` | All recent network requests |
| `get_screenshot` | Browser screenshot (JPEG) |
| `list_screenshots` | List all stored screenshots with metadata |
| `get_selected_element` | Right-click captured element (selector, styles, HTML) |
| `get_page_info` | Current page URL, title, viewport |
| `clear_context` | Clear stored context |

## Configuration

### MCP Server

Environment variables (or `~/.argus/config.json`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGUS_PORT` | `42777` | HTTP server port |
| `ARGUS_AUTH_TOKEN` | auto-generated | Auth token (persisted in `~/.argus/config.json`) |
| `ARGUS_MAX_ERRORS` | `100` | Max errors in buffer |
| `ARGUS_MAX_SCREENSHOTS` | `10` | Max screenshots stored |
| `ARGUS_RATE_LIMIT` | `120` | Max requests/minute |

### Chrome Extension

Configure via the extension popup:
- Server URL and auth token
- Toggle console log / network capture
- Domain blocklist/allowlist

## Architecture

Two components, one loop:

- **Chrome Extension** (TypeScript, Manifest V3) — captures browser events, screenshots, element details. Sends to MCP server via HTTP.
- **MCP Server** (Python) — receives data, filters noise, deduplicates errors, strips sensitive headers, stores in memory. Exposes MCP tools via stdio.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full technical design.

## Security

- HTTP server binds to `127.0.0.1` only — never exposed to network
- Auth token required on every request
- Sensitive headers (`Authorization`, `Cookie`) automatically redacted
- Request/response bodies truncated to 2000 chars
- All data in-memory only — cleared on server restart
- Minimal Chrome extension permissions: `activeTab`, `scripting`, `storage`, `contextMenus`

## Project Structure

```
project_argus/
├── server/           # Python MCP server
│   ├── src/argus/
│   │   ├── main.py          # Entry point
│   │   ├── config.py        # Settings
│   │   ├── mcp/tools.py     # MCP tool definitions
│   │   ├── api/             # HTTP server (FastAPI)
│   │   ├── core/            # Models, filters, dedup
│   │   ├── store/           # Storage abstraction
│   │   └── security/        # Sanitizer
│   ├── tests/               # 103 tests
│   └── pyproject.toml
├── extension/        # Chrome extension
│   ├── src/
│   │   ├── injected/        # Page-context monitors
│   │   ├── content/         # Bridge + element capture
│   │   ├── background/      # Service worker
│   │   └── popup/           # Settings UI
│   └── manifest.json
└── docs/
    └── ARCHITECTURE.md
```

## License

Proprietary. All rights reserved.

