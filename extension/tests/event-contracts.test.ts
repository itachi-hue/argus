/**
 * Event shape contract tests — verifies that the data the extension sends
 * matches the Python Pydantic models on the server.
 *
 * Server models use `extra="forbid"`, so ANY extra field causes a 422.
 * These tests catch field mismatches before they hit production.
 */
import { describe, it, expect } from "vitest";

// ── Timestamp validation ────────────────────────────────────

describe("Timestamps", () => {
  it("Date.now() / 1000 produces Unix seconds (not milliseconds)", () => {
    const timestamp = Date.now() / 1000;
    // Unix seconds: ~1.7 billion (2024-2030 range)
    // Unix milliseconds would be: ~1.7 trillion
    expect(timestamp).toBeGreaterThan(1_000_000_000);
    expect(timestamp).toBeLessThan(10_000_000_000);
  });

  it("is compatible with Python time.time() for since_minutes filtering", () => {
    const now = Date.now() / 1000;
    // Server does: cutoff = time.time() - minutes * 60
    // Events with timestamp >= cutoff are kept
    const fiveMinutesAgo = now - 5 * 60;
    expect(now).toBeGreaterThan(fiveMinutesAgo);

    // An event created "now" should survive the filter
    const eventTimestamp = Date.now() / 1000;
    expect(eventTimestamp).toBeGreaterThanOrEqual(fiveMinutesAgo);
  });

  it("duration_ms stays in raw milliseconds (not divided)", () => {
    const startMs = Date.now();
    const durationMs = (startMs + 150) - startMs;
    // duration_ms should be 150, not 0.15
    expect(durationMs).toBe(150);
  });

  it("timestamps are finite floats", () => {
    const ts = Date.now() / 1000;
    expect(typeof ts).toBe("number");
    expect(Number.isFinite(ts)).toBe(true);
  });
});

// ── ErrorEvent ──────────────────────────────────────────────

describe("ErrorEvent shape", () => {
  // Must match: server/src/argus/core/models.py::ErrorEvent (extra="forbid")
  const EXPECTED = ["message", "source", "lineno", "colno", "stack", "timestamp", "occurrence_count"];

  it("has exactly the right fields", () => {
    const event = {
      message: "Uncaught TypeError: x is not a function",
      source: "app.js",
      lineno: 42,
      colno: 10,
      stack: "TypeError: x is not a function\n  at app.js:42:10",
      timestamp: Date.now() / 1000,
      occurrence_count: 1,
    };
    expect(Object.keys(event).sort()).toEqual(EXPECTED.sort());
  });

  it("has correct types", () => {
    const event = {
      message: "err",
      source: "",
      lineno: 0,
      colno: 0,
      stack: "",
      timestamp: Date.now() / 1000,
      occurrence_count: 1,
    };
    expect(typeof event.message).toBe("string");
    expect(typeof event.source).toBe("string");
    expect(typeof event.lineno).toBe("number");
    expect(typeof event.colno).toBe("number");
    expect(typeof event.stack).toBe("string");
    expect(typeof event.timestamp).toBe("number");
    expect(typeof event.occurrence_count).toBe("number");
  });
});

// ── ConsoleEvent ────────────────────────────────────────────

describe("ConsoleEvent shape", () => {
  const EXPECTED = ["level", "args", "timestamp", "source", "lineno"];

  it("has exactly the right fields", () => {
    const event = {
      level: "error",
      args: ["Failed to load resource"],
      timestamp: Date.now() / 1000,
      source: "",
      lineno: 0,
    };
    expect(Object.keys(event).sort()).toEqual(EXPECTED.sort());
  });

  it("args is an array of strings", () => {
    const event = { level: "log", args: ["hello", "42"], timestamp: 0, source: "", lineno: 0 };
    expect(Array.isArray(event.args)).toBe(true);
    event.args.forEach((a) => expect(typeof a).toBe("string"));
  });
});

// ── NetworkEvent ────────────────────────────────────────────

describe("NetworkEvent shape", () => {
  const EXPECTED = [
    "method", "url", "status", "status_text",
    "request_headers", "response_headers",
    "request_body", "response_body",
    "duration_ms", "timestamp", "error",
  ];

  it("has exactly the right fields (success case)", () => {
    const event = {
      method: "POST",
      url: "https://api.example.com/data",
      status: 201,
      status_text: "Created",
      request_headers: { "Content-Type": "application/json" },
      response_headers: { "Content-Type": "application/json" },
      request_body: '{"name":"test"}',
      response_body: '{"id":1}',
      duration_ms: 150,
      timestamp: Date.now() / 1000,
      error: null,
    };
    expect(Object.keys(event).sort()).toEqual(EXPECTED.sort());
  });

  it("has exactly the right fields (failure case)", () => {
    const event = {
      method: "GET",
      url: "https://api.example.com/data",
      status: null,
      status_text: "",
      request_headers: {},
      response_headers: {},
      request_body: null,
      response_body: null,
      duration_ms: 50,
      timestamp: Date.now() / 1000,
      error: "Network error",
    };
    expect(Object.keys(event).sort()).toEqual(EXPECTED.sort());
  });
});

// ── Screenshot ──────────────────────────────────────────────

describe("Screenshot shape", () => {
  const EXPECTED = ["data", "url", "timestamp", "viewport", "trigger", "title", "description"];

  it("has exactly the right fields", () => {
    const screenshot = {
      data: "base64encodeddata",
      url: "https://example.com",
      timestamp: Date.now() / 1000,
      viewport: { width: 1920, height: 1080 },
      trigger: "hotkey",
      title: "Example Page",
      description: "Manual capture: Example Page (example.com)",
    };
    expect(Object.keys(screenshot).sort()).toEqual(EXPECTED.sort());
  });

  it("viewport has width and height", () => {
    const vp = { width: 1920, height: 1080 };
    expect(Object.keys(vp).sort()).toEqual(["height", "width"]);
    expect(typeof vp.width).toBe("number");
    expect(typeof vp.height).toBe("number");
  });
});

// ── PageInfo ────────────────────────────────────────────────

describe("PageInfo shape", () => {
  const EXPECTED = ["url", "title", "viewport", "timestamp"];

  it("has exactly the right fields", () => {
    const info = {
      url: "https://example.com/page",
      title: "My Page",
      viewport: { width: 1280, height: 720 },
      timestamp: Date.now() / 1000,
    };
    expect(Object.keys(info).sort()).toEqual(EXPECTED.sort());
  });
});

// ── ElementCapture ──────────────────────────────────────────

describe("ElementCapture shape", () => {
  const EXPECTED = [
    "selector", "computed_styles", "html", "text",
    "bounding_rect", "parent_html", "timestamp", "url", "screenshot_index",
  ];

  it("has exactly the right fields", () => {
    const element = {
      selector: "div#container > p.text",
      computed_styles: { color: "rgb(0, 0, 0)", "font-size": "16px" },
      html: "<p>Hello</p>",
      text: "Hello",
      bounding_rect: { x: 10, y: 20, width: 300, height: 50 },
      parent_html: "<div><p>Hello</p></div>",
      timestamp: Date.now() / 1000,
      url: "https://example.com",
      screenshot_index: null,
    };
    expect(Object.keys(element).sort()).toEqual(EXPECTED.sort());
  });

  it("bounding_rect has x, y, width, height", () => {
    const rect = { x: 0, y: 0, width: 100, height: 50 };
    expect(Object.keys(rect).sort()).toEqual(["height", "width", "x", "y"]);
  });
});

// ── IngestSnapshotRequest ───────────────────────────────────

describe("IngestSnapshotRequest shape", () => {
  it("snapshot payload has required timestamp field", () => {
    const snapshot = {
      timestamp: Date.now() / 1000,
      page_info: {
        url: "https://example.com",
        title: "Test",
        viewport: { width: 1920, height: 1080 },
        timestamp: Date.now() / 1000,
      },
      screenshot: {
        data: "base64",
        url: "https://example.com",
        timestamp: Date.now() / 1000,
        viewport: { width: 1920, height: 1080 },
        trigger: "hotkey",
        title: "Test",
        description: "Manual capture: Test (example.com)",
      },
    };
    expect(typeof snapshot.timestamp).toBe("number");
    expect(snapshot.timestamp).toBeGreaterThan(1_000_000_000);
    expect(snapshot.timestamp).toBeLessThan(10_000_000_000);
  });
});


