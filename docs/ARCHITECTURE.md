# Argus — Technical Architecture

## 1. Overview

Argus is a runtime context bridge for AI coding agents. It captures what's happening in the browser — console errors, network requests, screenshots, UI element details — and exposes that data to AI agents via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

**Two components:**

- **Chrome Extension** (TypeScript, Manifest V3) — captures browser runtime data and forwards it to the MCP server.
- **MCP Server** (Python, FastAPI) — receives and stores browser data, exposes it to AI agents as MCP tools.

Works with any MCP-compatible client: Cursor, Claude Code, Claude Desktop, Windsurf, Cline, Continue, and any future MCP client.

---

## 2. Design Principles

1. **Pull-based, not push-based.** The agent pulls context when it needs it via MCP tools. We don't push context into the agent. This makes Argus IDE-independent and agent-independent.

2. **Extension captures, server thinks.** The Chrome extension captures and forwards. All intelligence — filtering, deduplication, image optimization — happens server-side so we can iterate without publishing extension updates.

3. **Local-first.** Everything runs on localhost. The HTTP server binds to `127.0.0.1` only. All data is in-memory. Nothing leaves your machine.

4. **Minimal permissions.** The extension requests only what it needs. No `debugger` API (scary banner), no broad host access for capture, no background page.

5. **Efficient by default.** Bounded buffers, JPEG compression, server-side image resizing, batched events, error deduplication, native image content blocks for low token cost.

6. **Security is not optional.** Auth tokens, input validation, sensitive header stripping, rate limiting — all present from day one.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                              │
│                                                             │
│  ┌─────────────┐    window.postMessage    ┌───────────────┐ │
│  │  Injected   │ ──────────────────────►  │   Content     │ │
│  │  Script     │                          │   Script      │ │
│  │             │  (page context:          │               │ │
│  │  - onerror  │   errors, network,       │  - bridge     │ │
│  │  - fetch    │   console logs)          │  - element    │ │
│  │  - XHR      │                          │    capture    │ │
│  │  - console  │                          │  - click      │ │
│  └─────────────┘                          │    listener   │ │
│                                           └───────┬───────┘ │
│                              chrome.runtime       │         │
│                              .sendMessage         │         │
│                                                   ▼         │
│                                          ┌────────────────┐ │
│                                          │  Service       │ │
│  ┌─────────────┐    chrome.commands      │  Worker        │ │
│  │  Popup UI   │ ◄────────────────────── │                │ │
│  │  (settings, │                         │ - batch events │ │
│  │   status)   │                         │ - screenshot   │ │
│  └─────────────┘                         │ - auto-capture │ │
│                                          │ - hotkey       │ │
│  ┌─────────────┐    chrome.contextMenus  │ - context menu │ │
│  │ Right-click  │ ────────────────────►  │ - periodic     │ │
│  │ "Capture    │                         │   alarm        │ │
│  │  for AI"    │                         └───────┬────────┘ │
│  └─────────────┘                                 │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                              HTTP POST to 127.0.0.1:PORT
                              Authorization: Bearer <token>
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  MCP SERVER (Python)                         │
│                                                             │
│  ┌──────────────┐         ┌───────────────────────┐        │
│  │  HTTP Server │         │  MCP Server (stdio)    │        │
│  │  (FastAPI)   │         │                        │        │
│  │              │         │  Tools:                │        │
│  │  /ingest/*   │────────►│  - get_console_errors  │        │
│  │  /health     │  write  │  - get_console_logs    │        │
│  │              │         │  - get_network_*       │        │
│  └──────────────┘         │  - get_screenshot      │        │
│         │                 │  - list_screenshots    │        │
│         ▼                 │  - get_selected_element │        │
│  ┌──────────────┐         │  - get_page_info       │        │
│  │  Processing  │         │  - clear_context       │        │
│  │  Pipeline    │         └───────────┬────────────┘        │
│  │              │                     │                     │
│  │  - Validate  │                     │ read                │
│  │  - Filter    │                     │                     │
│  │  - Dedup     │         ┌───────────▼────────────┐        │
│  │  - Sanitize  │────────►│   Context Store        │        │
│  │  - Optimize  │  write  │   (In-Memory)          │        │
│  │    images    │         │                        │        │
│  └──────────────┘         │   - errors: deque      │        │
│                           │   - console: deque     │        │
│                           │   - network: deque     │        │
│                           │   - screenshots: list  │        │
│                           │   - element: latest    │        │
│                           │   - page_info: latest  │        │
│                           └────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
         │
         │ stdin/stdout (MCP protocol)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                  AI AGENT                                    │
│  (Cursor / Claude Code / Claude Desktop / Windsurf / etc.)  │
│                                                             │
│  Agent calls MCP tools:                                     │
│  → get_console_errors()   — see the TypeError               │
│  → get_screenshot()       — see the broken UI               │
│  → get_network_failures() — see the 401                     │
│  → list_screenshots()     — browse the timeline             │
│                                                             │
│  Agent reads code, makes fix, applies to editor.             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Component Details

### 4.1 Chrome Extension

**Scripts:**

| Script | Context | What it does |
|--------|---------|-------------|
| `injected.ts` | Page (same as web app) | Monkey-patches `fetch`, `XMLHttpRequest`, `console.*`. Listens for `window.onerror`, `unhandledrejection`. Posts events via `window.postMessage`. |
| `content/index.ts` | Isolated content script | Receives events from injected script. Extracts element details for right-click captures. Sends click events for auto-capture. Forwards to Service Worker. |
| `background/index.ts` | Service Worker (MV3) | Buffers events, handles hotkey, captures screenshots, manages context menu, periodic alarm, auto-capture logic. Sends to server via HTTP. |
| `popup/popup.ts` | Extension popup | Settings UI — server pairing, capture toggles, interval/count config, connection status. |

**Capture triggers:**

| Trigger | What's captured | How |
|---------|----------------|-----|
| Passive (automatic) | Console errors, logs, network requests | Injected script monitors continuously |
| Auto-capture: page load | Screenshot + page info | `chrome.tabs.onUpdated` (status=complete) |
| Auto-capture: tab switch | Screenshot + page info | `chrome.tabs.onActivated` |
| Auto-capture: user click | Screenshot + page info | Content script click listener → Service Worker (2s debounce) |
| Auto-capture: periodic | Screenshot + page info | `chrome.alarms` (configurable interval, default 30s) |
| Hotkey (Ctrl+Shift+L) | Screenshot + all buffered context | `chrome.commands` |
| Right-click element | Element details + styles + screenshot | `chrome.contextMenus` → content script extraction |

All auto-captures are throttled to max once per 10 seconds to prevent spamming.

### 4.2 MCP Server

**Single process, two interfaces:**

1. **HTTP Server** (FastAPI) — receives data from the Chrome extension. Binds to `127.0.0.1`. Token-authenticated.
2. **MCP Server** (stdio) — exposes tools to AI agents. Cursor/Claude Code spawns this process and communicates via stdin/stdout.

Both run on the same asyncio event loop.

**Processing pipeline:**

```
HTTP Request
    → Auth validation (token check)
    → Input validation (Pydantic models)
    → Rate limiting (120 req/min)
    → Noise filtering (domain blocklist, URL patterns)
    → Error deduplication (hash + 5s time window)
    → Sensitive data stripping (auth headers, cookies)
    → Image optimization (resize to 1280px, JPEG Q35)
    → Store in bounded buffer
```

### 4.3 Screenshot Pipeline

| Stage | Where | What |
|-------|-------|------|
| Capture | Extension | `chrome.tabs.captureVisibleTab` — JPEG, quality 40 |
| Optimize | Server | Pillow: resize to max 1280px width, recompress JPEG Q35 |
| Store | Server | In-memory, rolling buffer (default 15, configurable) |
| Serve | MCP | Native `ImageContent` block — tokenized by pixels, not base64 chars |
| Metadata | MCP | Each screenshot has title, description, URL, trigger, viewport, timestamp |

The `list_screenshots` tool returns a timeline with descriptions so the AI can pick which screenshot to fetch without downloading all of them.

---

## 5. Data Flows

### 5.1 Passive Monitoring

```
Web app throws error → injected script catches via window.onerror
→ window.postMessage → content script buffers
→ every 3s, batch sent to Service Worker via chrome.runtime.sendMessage
→ Service Worker POSTs to MCP server
→ server validates, filters, deduplicates, strips sensitive data, stores
→ agent calls get_console_errors() → sees the error
```

### 5.2 Auto-Capture

```
Page loads / tab switches / user clicks / periodic alarm fires
→ Service Worker checks throttle (10s minimum gap)
→ captures screenshot via chrome.tabs.captureVisibleTab
→ builds description ("Page loaded: My App (http://localhost:3000)")
→ POSTs screenshot + page info to server
→ server optimizes image (resize + recompress)
→ agent calls list_screenshots() → sees the timeline
→ agent calls get_screenshot(index) → sees the image
```

### 5.3 Hotkey Capture

```
User presses Ctrl+Shift+L
→ Service Worker captures screenshot
→ reads all buffered events
→ bundles: screenshot + errors + network + console + page info
→ POSTs as snapshot to server
→ agent queries any MCP tool → full context available
```

### 5.4 Right-Click Element Capture

```
User right-clicks element → "Capture for AI Agent"
→ Service Worker messages content script: "capture at click position"
→ content script extracts: selector, computed styles, HTML, bounding rect
→ draws red outline on element
→ Service Worker captures screenshot (with highlight visible)
→ POSTs element data + screenshot to server
→ agent calls get_selected_element() → sees element details + screenshot
```

---

## 6. Storage

### Abstract Interface

All data access goes through `ContextStore` (abstract base class). Current implementation is `InMemoryStore`.

### Buffer Sizes (defaults, configurable)

| Buffer | Max items |
|--------|-----------|
| Errors | 100 |
| Console events | 200 |
| Network events | 200 |
| Screenshots | 15 |
| Selected element | 1 (latest) |
| Page info | 1 (latest) |

All buffers are bounded `deque`s — oldest items are evicted when full. Thread-safe. All data cleared on process exit.

---

## 7. Security

### Authentication
- Cryptographically random token generated on startup (`secrets.token_urlsafe(32)`)
- Every HTTP request requires `Authorization: Bearer <token>`
- Constant-time comparison via `hmac.compare_digest`

### Network
- HTTP server binds to `127.0.0.1` only — never exposed to network
- No TLS for localhost (data never leaves the machine)

### Input Validation
- All payloads validated via Pydantic models with strict types
- Max payload size: 5MB
- Max field lengths enforced (stack traces: 10K chars, HTML: 2K chars)

### Sensitive Data Stripping

| Header | Action |
|--------|--------|
| `Authorization` | Replaced with `[REDACTED]` |
| `Cookie` | Replaced with `[REDACTED]` |
| `Set-Cookie` | Replaced with `[REDACTED]` |
| `X-API-Key` | Replaced with `[REDACTED]` |

Request/response bodies truncated to 2,000 characters.

### Rate Limiting
- 120 requests/minute sliding window
- Returns `429 Too Many Requests` when exceeded

### Extension Permissions

| Permission | Why |
|------------|-----|
| `activeTab` | Screenshot capture for the current tab |
| `scripting` | Inject the page-context monitoring script |
| `storage` | Persist settings and event buffer |
| `contextMenus` | Right-click "Capture for AI Agent" |
| `alarms` | Periodic auto-capture |
| `host_permissions: <all_urls>` | Auto-capture on page load / tab switch |

---

## 8. Noise Filtering

### Default Domain Blocklist

Analytics, error tracking, and ad domains are ignored automatically:

```
google-analytics.com, googletagmanager.com, facebook.net, fbcdn.net,
sentry.io, hotjar.com, intercom.io, segment.com, mixpanel.com,
amplitude.com, fullstory.com, clarity.ms, newrelic.com, datadog,
rollbar.com, bugsnag.com, logrocket.com, posthog.com, plausible.io,
doubleclick.net, googlesyndication.com, adservice.google.com
```

### URL Pattern Blocklist

Dev tooling noise is filtered:

```
favicon.ico, .hot-update., __webpack_hmr, sockjs-node,
/_next/webpack-hmr, /vite-hmr, /__vite_ping, .map, chrome-extension://
```

### Error Source Filtering

Errors are dropped if their stack trace only contains frames from browser extensions or third-party CDNs. Errors are kept if any frame references `localhost`, `127.0.0.1`, or the current page's origin.

### User Configuration

- **Domain allowlist** — always capture from these domains
- **Domain blocklist additions** — also ignore these domains
- Configured via extension popup, synced to server

---

## 9. Error Deduplication

Same error firing in a loop should not flood the buffer.

- **Key:** `hash(message + source + line_number)`
- **Window:** 5 seconds
- First occurrence stored normally
- Subsequent in window: `occurrence_count` incremented, `last_seen` updated
- After window expires: next occurrence treated as new

Applied both client-side (extension) and server-side (double safety).
