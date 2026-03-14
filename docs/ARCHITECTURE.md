# Project Argus — Technical Architecture

## 1. Overview

Argus is a runtime context bridge for AI coding agents. It captures what is happening in the browser — console errors, network requests, screenshots, UI element details — and exposes that data to AI agents via the Model Context Protocol (MCP).

**Two components:**

- **Chrome Extension** (TypeScript) — Captures browser runtime data and forwards it to the MCP server.
- **MCP Server** (Python) — Receives and stores browser data, exposes it to AI agents as MCP tools.

**Works with any MCP-compatible client:** Cursor, Claude Code, Claude Desktop, Windsurf, Cline, Continue, and any future MCP client. Argus is IDE-independent and agent-independent.

---

## 2. Design Principles

1. **Pull-based, not push-based.** The agent pulls context when it needs it via MCP tools. We do not push context into the agent or try to invoke the agent programmatically. This makes us IDE-independent and eliminates the agent invocation problem.

2. **Chrome extension is dumb, server is smart.** The extension captures and forwards. All intelligence — filtering, deduplication, data processing — happens server-side. This allows iterating on the brain without publishing extension updates.

3. **Local-first, cloud-ready.** V1 runs entirely on localhost. But every component is designed with an abstraction layer so cloud migration is a swap, not a rewrite.

4. **Minimal permissions.** The Chrome extension requests only the permissions it needs. No broad access, no scary banners, no debugger API.

5. **Efficiency by default.** Bounded buffers, compressed screenshots, batched events, deduplication at every layer. The system should be invisible in terms of resource consumption.

6. **Security is not optional.** Auth tokens, input validation, sensitive data stripping, and localhost-only binding — all present in V1, not deferred.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     BROWSER                             │
│                                                         │
│  ┌─────────────┐    window.postMessage    ┌───────────┐ │
│  │  Injected   │ ──────────────────────►  │  Content  │ │
│  │  Script     │                          │  Script   │ │
│  │             │  (page context:          │           │ │
│  │  - onerror  │   errors, network,       │  (bridge: │ │
│  │  - fetch    │   console logs)          │  forwards │ │
│  │  - XHR      │                          │  + element│ │
│  │  - console  │                          │  capture) │ │
│  └─────────────┘                          └─────┬─────┘ │
│                                                 │       │
│                              chrome.runtime     │       │
│                              .sendMessage       │       │
│                                                 ▼       │
│                                          ┌────────────┐ │
│                                          │  Service   │ │
│  ┌─────────────┐    chrome.commands      │  Worker    │ │
│  │  Popup UI   │ ◄────────────────────── │            │ │
│  │  (settings, │                         │ - buffer   │ │
│  │   status)   │                         │ - batch    │ │
│  └─────────────┘                         │ - send     │ │
│                                          │ - hotkey   │ │
│                                          │ - screenshot│
│  ┌─────────────┐    chrome.contextMenus  │ - context  │ │
│  │ Context     │ ────────────────────►   │   menu     │ │
│  │ Menu        │                         └──────┬─────┘ │
│  │ "Capture    │                                │       │
│  │  for AI"    │                                │       │
│  └─────────────┘                                │       │
└─────────────────────────────────────────────────┼───────┘
                                                  │
                              HTTP POST to 127.0.0.1:PORT
                              Authorization: Bearer <token>
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────┐
│                  MCP SERVER (Python)                    │
│                                                         │
│  ┌──────────────┐         ┌─────────────────────┐      │
│  │  HTTP Server │         │  MCP Server (stdio)  │      │
│  │  (FastAPI)   │         │                      │      │
│  │              │         │  Tools:              │      │
│  │  /ingest/*   │────────►│  - get_console_errors│      │
│  │  /health     │  write  │  - get_console_logs  │      │
│  │              │         │  - get_network_*     │      │
│  └──────────────┘         │  - get_screenshot    │      │
│         │                 │  - get_selected_elem │      │
│         ▼                 │  - get_page_info     │      │
│  ┌──────────────┐         │  - clear_context     │      │
│  │  Processing  │         └──────────┬───────────┘      │
│  │  Pipeline    │                    │                  │
│  │              │                    │ read             │
│  │  - Validate  │                    │                  │
│  │  - Filter    │         ┌──────────▼───────────┐      │
│  │  - Dedup     │────────►│   Context Store      │      │
│  │  - Strip     │  write  │   (In-Memory)        │      │
│  │    sensitive  │         │                      │      │
│  └──────────────┘         │   - errors: deque    │      │
│                           │   - console: deque   │      │
│                           │   - network: deque   │      │
│                           │   - screenshots: []  │      │
│                           │   - element: latest  │      │
│                           │   - page_info: latest│      │
│                           └──────────────────────┘      │
└─────────────────────────────────────────────────────────┘
         │
         │ stdin/stdout (MCP protocol)
         ▼
┌─────────────────────────────────────────────────────────┐
│                  AI AGENT                               │
│  (Cursor / Claude Code / Claude Desktop / any MCP      │
│   compatible client)                                    │
│                                                         │
│  Agent calls MCP tools:                                 │
│  "Let me check browser errors..."                      │
│  → get_console_errors()                                │
│  "Show me the screenshot..."                           │
│  → get_screenshot()                                    │
│  "What element was selected?"                          │
│  → get_selected_element()                              │
│                                                         │
│  Agent reads code, makes fix, applies to editor.        │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Component Details

### 4.1 Chrome Extension

**Role:** Capture browser runtime data and forward it to the MCP server.

**Scripts:**

| Script | Execution Context | Responsibilities |
|--------|-------------------|------------------|
| `injected.ts` | Page context (same as the web app) | Monkey-patches `fetch`, `XMLHttpRequest`, `console.*`. Listens for `window.onerror`, `unhandledrejection`. Posts events via `window.postMessage`. |
| `content-script.ts` | Isolated content script context | Receives events from injected script via `window.postMessage`. Extracts element details for right-click captures. Forwards events to Service Worker via `chrome.runtime.sendMessage`. |
| `background.ts` | Service Worker (Manifest V3) | Buffers events. Handles hotkey (`chrome.commands`). Captures screenshots (`chrome.tabs.captureVisibleTab`). Manages context menu. Sends batches to MCP server via HTTP POST. Persists buffer to `chrome.storage.local`. |
| `popup.ts` | Extension popup | Settings UI. Token input for MCP server pairing. Connection status display. Buffer stats. |

**Capture Triggers:**

| Trigger | What Gets Captured | How |
|---------|--------------------|-----|
| Automatic (passive) | Console errors, console logs, network requests | Injected script monitors continuously, events flow through content script to Service Worker |
| Hotkey (user-initiated) | Screenshot + all buffered errors + network log + page info | Service Worker handles `chrome.commands`, captures screenshot, bundles everything into a snapshot |
| Right-click (user-initiated) | Element details + styles + highlighted screenshot | Context menu triggers content script element extraction, Service Worker captures screenshot |

**Manifest V3 Constraints:**
- Service Worker dies after ~30 seconds of inactivity
- All state must be persisted to `chrome.storage.local`
- No persistent connections (no WebSocket, no long-lived SSE)
- Event batching happens in content script (which stays alive as long as the page is open), not in Service Worker

### 4.2 MCP Server (Python)

**Role:** Receive data from Chrome extension, store it, expose it to AI agents via MCP tools.

**Single process, two interfaces:**

1. **HTTP Server** — Receives data from Chrome extension. Built with FastAPI/uvicorn. Binds to `127.0.0.1` only. Token-authenticated.

2. **MCP Server** — Exposes tools to AI agents. Communicates via stdio (stdin/stdout) using the MCP protocol. Cursor/Claude Code spawns this process and communicates through it.

Both run on the same Python asyncio event loop. The HTTP server runs in a background async task. The MCP server runs on the main stdio loop.

**Processing Pipeline:**

```
HTTP Request
    → Auth validation (token check)
    → Input validation (Pydantic models)
    → Rate limiting
    → Noise filtering (domain blocklist, pattern matching)
    → Error deduplication (hash + time window)
    → Sensitive data stripping (auth headers, cookies)
    → Store in bounded buffer
```

### 4.3 Communication Protocol

**Chrome Extension → MCP Server:**
- Transport: HTTP POST over localhost
- Auth: `Authorization: Bearer <token>` header
- Content-Type: `application/json` (events) or `multipart/form-data` (screenshots)
- Payloads validated against strict schemas

**MCP Server → AI Agent:**
- Transport: stdio (stdin/stdout)
- Protocol: MCP (Model Context Protocol)
- Tools return `TextContent` (JSON) or `ImageContent` (base64 JPEG)

**No bidirectional communication in V1.** The Chrome extension pushes data to the server. The agent pulls data from the server. The server cannot request data from the Chrome extension. This means:
- Screenshots are captured on user action (hotkey or right-click), not on agent demand
- The agent reads stored screenshots, it cannot take new ones on its own
- This limitation is acceptable for V1 and avoids Manifest V3 Service Worker lifecycle complexity

---

## 5. Data Flow

### 5.1 Passive Monitoring Flow

```
1. User's web app throws a JS error
2. Injected script catches it via window.onerror
3. Injected script posts event via window.postMessage
4. Content script receives the message
5. Content script buffers the event (in-memory, content script stays alive)
6. Every 2-3 seconds (or when buffer hits N items), content script sends batch to Service Worker
7. Service Worker persists batch to chrome.storage.local (survives SW death)
8. Service Worker sends batch to MCP server via HTTP POST
9. MCP server validates, filters, deduplicates, strips sensitive data
10. MCP server stores in bounded in-memory buffer
11. Agent calls get_console_errors() → receives the error
```

### 5.2 Hotkey Capture Flow

```
1. User sees something wrong in the browser
2. User presses hotkey (e.g., Ctrl+Shift+A)
3. Service Worker receives chrome.commands event
4. Service Worker captures screenshot (chrome.tabs.captureVisibleTab)
5. Service Worker compresses screenshot (JPEG, 80% quality, max 1280px)
6. Service Worker reads all buffered events from chrome.storage.local
7. Service Worker bundles: screenshot + errors + network log + console log + page info
8. Service Worker sends snapshot to MCP server via POST /api/ingest/snapshot
9. MCP server stores the complete snapshot
10. Service Worker shows toast notification: "Context captured ✓"
11. User switches to IDE
12. User tells agent: "something broke in the browser, check and fix it"
13. Agent calls get_console_errors(), get_screenshot(), get_network_failures()
14. Agent has full context, makes the fix
```

### 5.3 Right-Click Element Capture Flow

```
1. Developer sees a UI element that looks wrong
2. Developer right-clicks the element
3. Context menu shows "Capture for AI Agent"
4. Developer clicks it
5. chrome.contextMenus.onClicked fires in Service Worker
6. Service Worker sends message to content script: "capture element at click position"
7. Content script finds the element at the click coordinates
8. Content script extracts:
   - CSS selector path (e.g., div.checkout > form > button.submit)
   - Computed styles (filtered ~40 properties: layout, box model, typography, visual)
   - Element HTML (outerHTML, truncated to 2000 chars)
   - Bounding rect (x, y, width, height)
   - Parent element HTML (truncated)
   - Text content
9. Content script sends element data to Service Worker
10. Service Worker captures screenshot
11. Service Worker sends element capture + screenshot to MCP server
12. MCP server stores as selected element
13. Agent calls get_selected_element() → receives full element details + screenshot
```

### 5.4 Agent Query Flow

```
1. Agent decides to check browser context (user asked, or agent is proactive)
2. Agent calls MCP tool (e.g., get_console_errors(limit=10, since_minutes=5))
3. MCP server receives tool call via stdio
4. MCP server queries in-memory store
5. MCP server returns formatted response as TextContent or ImageContent
6. Agent processes the context
7. Agent identifies the issue
8. Agent finds relevant code in the workspace
9. Agent makes the fix
10. Fix appears in the editor
```

---

## 6. Storage Architecture

### 6.1 Abstract Interface

All data access goes through an abstract `ContextStore` interface. This enables swapping the storage backend without changing any business logic.

```
ContextStore (abstract)
├── add_errors(session_id, errors) → None
├── add_console_events(session_id, events) → None
├── add_network_events(session_id, events) → None
├── add_screenshot(session_id, screenshot) → None
├── set_selected_element(session_id, element) → None
├── set_page_info(session_id, page_info) → None
├── add_snapshot(session_id, snapshot) → None
├── get_errors(session_id, limit, since) → list[ErrorEvent]
├── get_console_events(session_id, limit, level) → list[ConsoleEvent]
├── get_network_events(session_id, limit, method, url_pattern) → list[NetworkEvent]
├── get_network_failures(session_id, limit, status_filter, url_pattern) → list[NetworkEvent]
├── get_screenshot(session_id, index) → Screenshot | None
├── get_all_screenshot_metadata(session_id) → list[ScreenshotMeta]
├── get_selected_element(session_id) → ElementCapture | None
├── get_page_info(session_id) → PageInfo | None
├── clear(session_id, event_type) → None
```

### 6.2 In-Memory Implementation (V1)

- Uses `collections.deque(maxlen=N)` for bounded storage
- Buffer sizes (configurable):
  - Errors: 100
  - Console events: 200
  - Network events: 200
  - Screenshots: 10
  - Selected element: 1 (latest only)
  - Page info: 1 (latest only)
- Thread-safe via `asyncio.Lock`
- All data cleared on process exit
- No persistence to disk

### 6.3 Cloud Migration Path (Future)

- Implement `PostgresStore(ContextStore)` with asyncpg
- Screenshots stored in S3/R2, database stores references
- Session management with user/org scoping
- Data retention policies
- The MCP tools, HTTP routes, and processing pipeline remain unchanged

---

## 7. Security Architecture

### 7.1 Authentication

**Token Generation:**
- MCP server generates a cryptographically random token on startup using `secrets.token_urlsafe(32)`
- Token is printed to terminal output on startup
- User copies token to Chrome extension popup (one-time setup)
- Token is stored in `chrome.storage.local` (encrypted by Chrome)

**Token Validation:**
- Every HTTP request from Chrome extension must include `Authorization: Bearer <token>`
- Requests without valid token receive `401 Unauthorized`
- Token comparison uses `hmac.compare_digest` (constant-time, prevents timing attacks)

**Cloud Migration:**
- Replace static token with per-user API keys
- Add OAuth/SSO for web dashboard
- API keys scoped to organization/workspace

### 7.2 Network Security

- HTTP server binds to `127.0.0.1` ONLY — never `0.0.0.0`
- Not accessible from other machines on the network
- No TLS for localhost in V1 (acceptable — data never leaves the machine)
- Cloud migration adds TLS everywhere

### 7.3 Input Validation

- All incoming data validated through Pydantic models with strict types
- Max payload size: 5MB per request (screenshots can be large)
- Max field lengths enforced (e.g., stack traces truncated to 10,000 chars)
- Unknown fields rejected (`model_config = ConfigDict(extra="forbid")`)
- Invalid data returns `422 Unprocessable Entity` with details

### 7.4 Rate Limiting

- Max 120 requests per minute from Chrome extension (2 per second sustained)
- Implemented as simple sliding window counter in memory
- Exceeded limit returns `429 Too Many Requests`
- Prevents runaway extension bugs from overwhelming the server

### 7.5 Sensitive Data Handling

**Server-side stripping (applied on all incoming data before storage):**

| Data Type | Action |
|-----------|--------|
| `Authorization` header | Value replaced with `[REDACTED]` |
| `Cookie` header | Value replaced with `[REDACTED]` |
| `Set-Cookie` header | Value replaced with `[REDACTED]` |
| `X-API-Key` header | Value replaced with `[REDACTED]` |
| Request body | Truncated to 2,000 characters |
| Response body | Truncated to 2,000 characters |
| Element HTML | Truncated to 2,000 characters |
| Stack traces | Truncated to 10,000 characters |

**What we do NOT strip in V1:**
- Screenshot content (would require OCR/ML to detect sensitive info)
- URL parameters (may contain tokens — warn users in docs)
- Console log arguments (may contain user data)

**Data at rest:**
- V1: In-memory only. Data dies with the process. No disk persistence.
- Cloud: Encryption at rest (S3 SSE, Postgres TDE). Retention policies. Auto-deletion.

### 7.6 Chrome Extension Permissions

Minimal permissions only:

| Permission | Why |
|------------|-----|
| `activeTab` | Access the tab the user is currently on (for screenshots) |
| `scripting` | Inject the page-context monitoring script |
| `storage` | Persist event buffer across Service Worker restarts |
| `contextMenus` | Right-click "Capture for AI Agent" menu item |

**Not requested:**
- `<all_urls>` — Too broad. `activeTab` is sufficient.
- `tabs` — Not needed. We use `activeTab`.
- `debugger` — Shows scary "debugging this browser" banner. Avoided entirely.
- `webRequest` — Not needed. We monkey-patch fetch/XHR in page context instead.

### 7.7 Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| Malicious local process sends fake context | Low | Medium | Auth token required on every request |
| Extension captures sensitive data (passwords, PII) | Medium | High | Header stripping, body truncation, user education |
| Token leaked in logs or screenshots | Low | Medium | Token only displayed once on startup, not logged after |
| Malicious website detects Argus and sends fake errors | Low | Low | Extension uses isolated content script, injected script is not accessible to page |
| Denial of service from rapid-fire events | Medium | Low | Rate limiting, deduplication, bounded buffers |

---

## 8. Noise Filtering

### 8.1 Two-Layer Filtering

**Layer 1: Client-side (Chrome Extension)**
- Quick filtering before events leave the browser
- Reduces network traffic and storage writes
- Filters by domain and known patterns

**Layer 2: Server-side (MCP Server)**
- Thorough filtering with more context
- Server can be updated without extension republish
- Handles edge cases and user-configured rules

### 8.2 Default Domain Blocklist

Network requests and errors from these domains are ignored by default:

```
google-analytics.com, googletagmanager.com, googleapis.com/analytics,
facebook.net, fbcdn.net, connect.facebook.net,
sentry.io, sentry-cdn.com, browser.sentry-cdn.com,
hotjar.com, static.hotjar.com,
intercom.io, widget.intercom.io,
segment.com, cdn.segment.com,
mixpanel.com, cdn.mixpanel.com,
amplitude.com, cdn.amplitude.com,
heap-analytics.com, heapanalytics.com,
fullstory.com, rs.fullstory.com,
clarity.ms,
newrelic.com, js-agent.newrelic.com,
nr-data.net,
datadog-agent.com, browser-intake-datadoghq.com,
rollbar.com, cdn.rollbar.com,
bugsnag.com, notify.bugsnag.com,
logrocket.com, cdn.lr-ingest.io,
mouseflow.com,
smartlook.com,
posthog.com,
plausible.io,
doubleclick.net, googlesyndication.com,
adservice.google.com
```

### 8.3 URL Pattern Blocklist

Requests matching these patterns are ignored:

```
favicon.ico
.hot-update.              (Webpack HMR)
__webpack_hmr             (Webpack HMR)
sockjs-node               (Webpack dev server)
/_next/webpack-hmr         (Next.js HMR)
/vite-hmr                 (Vite HMR)
/__vite_ping              (Vite)
/ws                       (Generic WebSocket upgrade, if not user's)
.map                      (Source map files)
chrome-extension://        (Browser extension resources)
```

### 8.4 Error Source Filtering

Errors are filtered if their stack trace contains ONLY frames from:
- `chrome-extension://` URLs (browser extension errors)
- Known third-party CDN domains
- `<anonymous>` with no useful context

Errors are KEPT if any stack frame references:
- `localhost` or `127.0.0.1`
- The current page's origin
- User-configured domains

### 8.5 User Configuration

Users can customize filtering via:
- **Domain allowlist:** "Always capture events from these domains" (e.g., `api.myapp.com`)
- **Domain blocklist additions:** "Also ignore these domains"
- **Pattern overrides:** "Keep events matching this pattern even if domain is blocked"

Configuration stored in Chrome extension settings (popup UI) and synced to MCP server.

---

## 9. Error Deduplication

### 9.1 Strategy

Same error firing repeatedly (e.g., React render loop) should not flood the buffer with 100 identical entries.

**Deduplication key:** `hash(error.message + error.source + error.line_number)`

**Time window:** 5 seconds

**Behavior:**
- First occurrence: stored normally
- Subsequent occurrences within window: `occurrence_count` incremented, `last_seen` updated
- After window expires: next occurrence treated as new entry

### 9.2 Implementation Layers

- **Client-side (Chrome Extension):** Dedup in content script buffer before sending to Service Worker. Prevents storage thrashing.
- **Server-side (MCP Server):** Dedup again in case batches from different content script cycles contain duplicates.

---

## 10. Screenshot Handling

### 10.1 Capture

- API: `chrome.tabs.captureVisibleTab(null, { format: 'jpeg', quality: 80 })`
- Captures visible viewport only (not full page scroll)
- Returns base64-encoded JPEG

### 10.2 Optimization

- Format: JPEG (not PNG — 5-10x smaller for photos/UI)
- Quality: 80% (visually lossless for UI screenshots)
- Max width: 1280px (resize if viewport is wider)
- Target size: 50-150KB per screenshot
- Compression and resize done in Chrome extension before sending to server

### 10.3 Storage

- Last 10 screenshots stored in memory
- Each tagged with: timestamp, page URL, viewport dimensions, capture trigger (hotkey/element/error)
- FIFO eviction — oldest screenshot dropped when 11th is added
- Agent can request by index (0 = latest, 9 = oldest)

### 10.4 Element Highlighting

When screenshot is captured as part of a right-click element capture:
- Content script draws a temporary red outline (2px solid red) around the selected element
- Screenshot is captured with the highlight visible
- Highlight is removed after capture
- This visually "points" the agent at the element in the screenshot

---

## 11. Configuration

### 11.1 MCP Server Configuration

| Setting | Default | Env Var | Description |
|---------|---------|---------|-------------|
| `host` | `127.0.0.1` | `ARGUS_HOST` | HTTP server bind address |
| `port` | `42777` | `ARGUS_PORT` | HTTP server port |
| `auth_token` | Auto-generated | `ARGUS_AUTH_TOKEN` | Bearer token (auto-generated if not set) |
| `max_errors` | `100` | `ARGUS_MAX_ERRORS` | Max error events in buffer |
| `max_console` | `200` | `ARGUS_MAX_CONSOLE` | Max console events in buffer |
| `max_network` | `200` | `ARGUS_MAX_NETWORK` | Max network events in buffer |
| `max_screenshots` | `10` | `ARGUS_MAX_SCREENSHOTS` | Max screenshots in buffer |
| `max_payload_size` | `5242880` (5MB) | `ARGUS_MAX_PAYLOAD` | Max HTTP request body size |
| `rate_limit` | `120` | `ARGUS_RATE_LIMIT` | Max requests per minute |
| `log_level` | `INFO` | `ARGUS_LOG_LEVEL` | Logging verbosity |

Configuration loaded via Pydantic Settings: environment variables > config file (`~/.argus/config.json`) > defaults.

### 11.2 Chrome Extension Configuration

Stored in `chrome.storage.local`:

| Setting | Default | Description |
|---------|---------|-------------|
| `server_url` | `http://127.0.0.1:42777` | MCP server URL |
| `auth_token` | `""` | Bearer token (entered by user) |
| `capture_console_logs` | `true` | Capture console.log/warn/info |
| `capture_network` | `true` | Capture network requests |
| `max_body_length` | `2000` | Max request/response body length to capture |
| `batch_interval_ms` | `3000` | How often to send batched events |
| `batch_size` | `50` | Max events per batch |
| `blocked_domains` | (defaults) | Additional domains to ignore |
| `allowed_domains` | `[]` | Domains to always capture (overrides blocklist) |

---

## 12. Cloud Migration Path

### 12.1 What Changes

| Component | Local (V1) | Cloud (V2) |
|-----------|-----------|------------|
| Storage | In-memory (Python dicts/deques) | PostgreSQL + S3 |
| MCP Transport | stdio (Cursor spawns process) | SSE over HTTPS (remote MCP server) |
| Auth | Static bearer token | Per-user API keys, OAuth |
| Chrome Extension target | `http://127.0.0.1:42777` | `https://api.argus.dev` |
| Data retention | Until process exits | Configurable (7/30/90 days) |
| Multi-user | Single user | Multi-tenant (user → org → workspace) |
| Billing | None | Stripe subscriptions |

### 12.2 What Stays The Same

- Chrome extension capture logic (unchanged — just POSTs to a different URL)
- MCP tool definitions (same tools, same parameters, same return types)
- Noise filtering logic
- Error deduplication logic
- Data models (Pydantic models extended, not rewritten)
- Processing pipeline (validate → filter → dedup → strip → store)

### 12.3 Data Model Extension for Cloud

```
V1:  session_id (single implicit session)
V2:  user → organization → workspace → session
```

The `session_id` parameter already exists in the store interface. For cloud, it becomes a real entity with user scoping. The interface doesn't change.

---

## 13. Project Structure

```
project_argus/
│
├── server/                          # Python MCP Server
│   ├── pyproject.toml               # Dependencies and project metadata
│   ├── src/
│   │   └── argus/
│   │       ├── __init__.py          # Version, package info
│   │       ├── main.py              # Entry point — starts MCP + HTTP
│   │       ├── config.py            # Pydantic Settings configuration
│   │       │
│   │       ├── mcp/
│   │       │   ├── __init__.py
│   │       │   └── tools.py         # MCP tool definitions
│   │       │
│   │       ├── api/
│   │       │   ├── __init__.py
│   │       │   ├── server.py        # FastAPI app setup
│   │       │   ├── routes.py        # HTTP route handlers
│   │       │   └── middleware.py    # Auth, rate limiting, payload size
│   │       │
│   │       ├── core/
│   │       │   ├── __init__.py
│   │       │   ├── models.py        # All Pydantic data models
│   │       │   ├── filters.py       # Noise filtering logic
│   │       │   └── dedup.py         # Error deduplication
│   │       │
│   │       ├── store/
│   │       │   ├── __init__.py
│   │       │   ├── base.py          # Abstract ContextStore interface
│   │       │   └── memory.py        # In-memory implementation
│   │       │
│   │       └── security/
│   │           ├── __init__.py
│   │           └── sanitizer.py     # Sensitive data stripping
│   │
│   └── tests/
│       ├── conftest.py              # Fixtures (store, app, client)
│       ├── test_models.py
│       ├── test_tools.py
│       ├── test_routes.py
│       ├── test_filters.py
│       ├── test_dedup.py
│       ├── test_sanitizer.py
│       └── test_store.py
│
├── extension/                       # Chrome Extension
│   ├── manifest.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── esbuild.config.mjs          # Build configuration
│   ├── src/
│   │   ├── types.ts                 # Shared TypeScript types
│   │   ├── config.ts               # Extension configuration
│   │   ├── background/
│   │   │   ├── index.ts            # Service Worker entry
│   │   │   ├── screenshot.ts       # Screenshot capture + compression
│   │   │   ├── transport.ts        # HTTP client for MCP server
│   │   │   └── commands.ts         # Hotkey + context menu handlers
│   │   ├── content/
│   │   │   ├── index.ts            # Content script entry
│   │   │   ├── bridge.ts           # Message bridge (injected ↔ service worker)
│   │   │   ├── element-capture.ts  # Element detail extraction
│   │   │   └── buffer.ts           # Event buffering and batching
│   │   ├── injected/
│   │   │   ├── index.ts            # Injected script entry
│   │   │   ├── console-monitor.ts  # Console interception
│   │   │   ├── network-monitor.ts  # Fetch/XHR interception
│   │   │   └── error-monitor.ts    # Error listeners
│   │   └── popup/
│   │       ├── popup.html
│   │       ├── popup.ts
│   │       └── popup.css
│   └── icons/
│       ├── icon-16.png
│       ├── icon-48.png
│       └── icon-128.png
│
├── docs/
│   ├── ARCHITECTURE.md              # This document
│   ├── API_SPEC.md                  # API and tool specifications
│   └── EXTENSION_SPEC.md           # Chrome extension specification
│
└── .gitignore
```

---

## 14. Development Plan

### Week 1: Foundation + Core Loop

**Goal:** End-to-end loop working — capture a JS error in browser, agent sees it via MCP tool.

**Python MCP Server:**
- Project setup (pyproject.toml, dependencies, structure)
- Pydantic data models (`models.py`)
- Configuration management (`config.py`)
- In-memory store (`memory.py`)
- MCP server with `get_console_errors()` and `get_page_info()` tools
- HTTP server with `POST /api/ingest/errors` and `GET /api/health`
- Auth token generation and validation middleware
- Basic input validation

**Chrome Extension:**
- Manifest V3 setup with esbuild build pipeline
- Injected script: `window.onerror` and `unhandledrejection` capture
- Content script: message bridge (injected → service worker)
- Service Worker: receive events, POST to MCP server
- Minimal popup: token input, connection status

**Validation:** Trigger a JS error in a test app → agent calls `get_console_errors()` → sees the error.

### Week 2: Full Capture

**Goal:** All capture mechanisms working, all MCP tools functional.

**Chrome Extension:**
- Injected script: monkey-patch `fetch` and `XMLHttpRequest`
- Injected script: intercept `console.log`, `console.warn`, `console.info`, `console.debug`
- Service Worker: hotkey handler + screenshot capture + JPEG compression
- Content script: element detail extraction (selector, styles, HTML, bounding rect)
- Context menu: "Capture for AI Agent"
- Content script: event batching (buffer in content script, send every 2-3s)
- Service Worker: persist buffer to `chrome.storage.local`
- Popup: full settings UI (server URL, token, capture toggles, domain filters)

**Python MCP Server:**
- All remaining MCP tools: `get_console_logs`, `get_network_log`, `get_network_failures`, `get_screenshot`, `get_selected_element`, `clear_context`
- HTTP routes: all ingest endpoints (console, network, screenshot, element, snapshot, page-info)
- Screenshot storage with metadata

**Validation:** Full capture flow — hotkey captures everything, right-click captures element, agent queries any tool.

### Week 3: Intelligence + Security Hardening

**Goal:** Clean, filtered, secure data pipeline.

**Server-side:**
- Noise filter with default domain blocklist and URL patterns
- Error deduplication (hash + time window)
- Sensitive data stripping (headers, body truncation)
- Rate limiting middleware
- Payload size enforcement
- Input validation edge cases (malformed data, oversized fields)
- Structured logging

**Chrome Extension:**
- Client-side noise filtering (filter before sending)
- Client-side deduplication (reduce storage writes)
- Screenshot resize optimization
- Service Worker lifecycle handling (reconnect after death, rebuffer)
- Connection retry with exponential backoff

**Validation:** Noisy app (React dev mode, analytics, HMR) → agent sees only relevant errors, clean data.

### Week 4: Polish + Ship

**Goal:** Production-ready, installable, tested.

- Integration testing with real apps (React, Next.js, vanilla JS)
- Edge case handling (iframes, SPA navigation, React error boundaries)
- Chrome extension packaging for Chrome Web Store submission
- MCP server packaging (installable via pip/pipx)
- User-facing setup instructions
- Error handling and graceful degradation (server down, extension disconnected)
- Performance profiling (memory usage, CPU overhead)
- Configuration documentation

---

## 15. Future Considerations (Not V1)

### V1.5: Bidirectional Communication
- Content script SSE connection to MCP server
- Agent-initiated screenshots (`take_screenshot` tool)
- Agent-initiated element inspection
- Live page monitoring

### V2: Cloud Platform
- Cloud-hosted MCP server with SSE transport
- User accounts, API keys, billing (Stripe)
- PostgreSQL storage, S3 for screenshots
- Web dashboard (session history, settings, usage)
- Team features (shared sessions, bug handoff)
- Lovable/Bolt integration (clipboard formatting, direct injection)

### V2.5: Expanded Capture
- localStorage / sessionStorage capture
- Cookie state capture
- React/Vue/Angular component tree inspection
- Performance metrics (Web Vitals, long tasks)
- Full page screenshots (scroll + stitch)
- WebSocket message capture

### V3: Backend Observability
- Backend SDKs (Node.js, Python, Go)
- Server log capture
- Distributed trace integration
- Database query capture
- Infrastructure metrics
- The agent sees the entire running system





