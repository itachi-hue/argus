/**
 * Injected into page context. Monkey-patches fetch, XHR, console, and error handlers.
 * Communicates with content script via window.postMessage.
 */

const ARGUS_ID = "__argus__";
const MAX_BODY = 2000;

function truncate(s: string | null | undefined): string | null {
  if (!s) return null;
  return s.length <= MAX_BODY ? s : s.slice(0, MAX_BODY) + `... [${s.length} chars]`;
}

function post(type: string, payload: any) {
  window.postMessage({ source: ARGUS_ID, type, payload }, "*");
}

// --- Error monitoring ---

window.addEventListener("error", (e) => {
  post("argus-error", {
    message: e.message || String(e),
    source: e.filename || "",
    lineno: e.lineno || 0,
    colno: e.colno || 0,
    stack: e.error?.stack || "",
    timestamp: Date.now(),
    occurrence_count: 1,
  });
});

window.addEventListener("unhandledrejection", (e) => {
  const reason = e.reason;
  post("argus-error", {
    message: reason?.message || String(reason),
    source: "",
    lineno: 0,
    colno: 0,
    stack: reason?.stack || "",
    timestamp: Date.now(),
    occurrence_count: 1,
  });
});

// --- Console monitoring ---

const originalConsole: Record<string, Function> = {};
const CONSOLE_LEVELS = ["log", "warn", "error", "info", "debug"] as const;

for (const level of CONSOLE_LEVELS) {
  originalConsole[level] = console[level].bind(console);
  (console as any)[level] = (...args: any[]) => {
    // Call original first
    originalConsole[level](...args);
    // Forward to content script
    post("argus-console", {
      level,
      args: args.map((a) => {
        try {
          return typeof a === "string" ? a : JSON.stringify(a, null, 0)?.slice(0, 500) ?? String(a);
        } catch {
          return String(a);
        }
      }),
      timestamp: Date.now(),
      source: "",
      lineno: 0,
    });
  };
}

// --- Network monitoring: fetch ---

const originalFetch = window.fetch;
window.fetch = async function (...args: Parameters<typeof fetch>) {
  const startTime = Date.now();
  const req = new Request(...args);
  const method = req.method;
  const url = req.url;

  let requestBody: string | null = null;
  try {
    requestBody = truncate(await req.clone().text());
  } catch {
    /* empty body */
  }

  try {
    const response = await originalFetch.apply(this, args);
    const duration = Date.now() - startTime;

    let responseBody: string | null = null;
    try {
      responseBody = truncate(await response.clone().text());
    } catch {
      /* streaming or opaque body */
    }

    post("argus-network", {
      method,
      url,
      status: response.status,
      status_text: response.statusText,
      request_headers: Object.fromEntries(req.headers),
      response_headers: Object.fromEntries(response.headers),
      request_body: requestBody,
      response_body: responseBody,
      duration_ms: duration,
      timestamp: Date.now(),
      error: null,
    });

    return response;
  } catch (error: any) {
    post("argus-network", {
      method,
      url,
      status: null,
      status_text: "",
      request_headers: Object.fromEntries(req.headers),
      response_headers: {},
      request_body: requestBody,
      response_body: null,
      duration_ms: Date.now() - startTime,
      timestamp: Date.now(),
      error: error?.message || "Network error",
    });
    throw error;
  }
};

// --- Network monitoring: XMLHttpRequest ---

const XHRProto = XMLHttpRequest.prototype;
const originalOpen = XHRProto.open;
const originalSend = XHRProto.send;
const originalSetHeader = XHRProto.setRequestHeader;

XHRProto.open = function (method: string, url: string | URL, ...rest: any[]) {
  (this as any)._argus = {
    method,
    url: String(url),
    requestHeaders: {} as Record<string, string>,
    startTime: 0,
    requestBody: null as string | null,
  };
  return (originalOpen as any).apply(this, [method, url, ...rest]);
};

XHRProto.setRequestHeader = function (name: string, value: string) {
  if ((this as any)._argus) {
    (this as any)._argus.requestHeaders[name] = value;
  }
  return originalSetHeader.apply(this, [name, value]);
};

XHRProto.send = function (body?: Document | XMLHttpRequestBodyInit | null) {
  const meta = (this as any)._argus;
  if (meta) {
    meta.startTime = Date.now();
    meta.requestBody = truncate(typeof body === "string" ? body : null);

    this.addEventListener("loadend", function () {
      const responseHeaders: Record<string, string> = {};
      const rawHeaders = this.getAllResponseHeaders();
      if (rawHeaders) {
        for (const line of rawHeaders.trim().split(/[\r\n]+/)) {
          const idx = line.indexOf(": ");
          if (idx > 0) responseHeaders[line.slice(0, idx)] = line.slice(idx + 2);
        }
      }

      post("argus-network", {
        method: meta.method,
        url: meta.url,
        status: this.status || null,
        status_text: this.statusText || "",
        request_headers: meta.requestHeaders,
        response_headers: responseHeaders,
        request_body: meta.requestBody,
        response_body: truncate(this.responseText),
        duration_ms: Date.now() - meta.startTime,
        timestamp: Date.now(),
        error: this.status === 0 ? "Network error" : null,
      });
    });
  }
  return originalSend.apply(this, [body]);
};



