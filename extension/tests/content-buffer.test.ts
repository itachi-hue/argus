/**
 * Tests for the content script's event buffer and flush logic.
 * Validates the fix for event loss when service worker is inactive.
 */
import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";

// Install fake timers BEFORE the content module loads
// so its setInterval(flushBuffer, 3000) doesn't fire during tests
vi.hoisted(() => {
  vi.useFakeTimers();
});

import {
  flushBuffer,
  buildSelector,
  errorBuffer,
  consoleBuffer,
  networkBuffer,
  MAX_BUFFER_SIZE,
} from "../src/content/index";

afterAll(() => {
  vi.useRealTimers();
});

// ── Helpers ──────────────────────────────────────────────────

function mockError(msg = "test error") {
  return {
    message: msg,
    source: "app.js",
    lineno: 42,
    colno: 10,
    stack: "Error: test\n  at app.js:42:10",
    timestamp: Date.now() / 1000,
    occurrence_count: 1,
  };
}

function mockConsole(level = "log") {
  return {
    level,
    args: ["test message"],
    timestamp: Date.now() / 1000,
    source: "",
    lineno: 0,
  };
}

function mockNetwork(url = "https://api.example.com/data") {
  return {
    method: "GET",
    url,
    status: 200,
    status_text: "OK",
    request_headers: {},
    response_headers: {},
    request_body: null,
    response_body: '{"ok":true}',
    duration_ms: 120,
    timestamp: Date.now() / 1000,
    error: null,
  };
}

// ── Flush buffer tests ──────────────────────────────────────

describe("flushBuffer", () => {
  beforeEach(() => {
    errorBuffer.length = 0;
    consoleBuffer.length = 0;
    networkBuffer.length = 0;
    vi.mocked(chrome.runtime.sendMessage).mockReset();
    vi.mocked(chrome.runtime.sendMessage).mockResolvedValue({ ok: true });
  });

  it("skips when all buffers are empty", () => {
    flushBuffer();
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it("sends buffered errors to the service worker", () => {
    const err = mockError("TypeError: x is not a function");
    errorBuffer.push(err);

    flushBuffer();

    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "events-batch",
        payload: expect.objectContaining({ errors: [err] }),
      })
    );
  });

  it("sends buffered console events", () => {
    const evt = mockConsole("warn");
    consoleBuffer.push(evt);

    flushBuffer();

    const payload = vi.mocked(chrome.runtime.sendMessage).mock.calls[0][0] as any;
    expect(payload.payload.console_events).toEqual([evt]);
  });

  it("sends buffered network events", () => {
    const evt = mockNetwork();
    networkBuffer.push(evt);

    flushBuffer();

    const payload = vi.mocked(chrome.runtime.sendMessage).mock.calls[0][0] as any;
    expect(payload.payload.network_events).toEqual([evt]);
  });

  it("sends mixed event types in a single batch", () => {
    errorBuffer.push(mockError());
    consoleBuffer.push(mockConsole());
    networkBuffer.push(mockNetwork());

    flushBuffer();

    const payload = vi.mocked(chrome.runtime.sendMessage).mock.calls[0][0] as any;
    expect(payload.payload.errors).toHaveLength(1);
    expect(payload.payload.console_events).toHaveLength(1);
    expect(payload.payload.network_events).toHaveLength(1);
  });

  it("clears buffers after successful flush", () => {
    errorBuffer.push(mockError());
    consoleBuffer.push(mockConsole());
    networkBuffer.push(mockNetwork());

    flushBuffer();

    expect(errorBuffer).toHaveLength(0);
    expect(consoleBuffer).toHaveLength(0);
    expect(networkBuffer).toHaveLength(0);
  });

  it("re-queues events when service worker is inactive", async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValueOnce(
      new Error("Could not establish connection")
    );

    const err = mockError("critical error");
    errorBuffer.push(err);

    flushBuffer();
    // Buffer drained synchronously by splice
    expect(errorBuffer).toHaveLength(0);

    // Flush the .catch() microtask
    await vi.advanceTimersByTimeAsync(0);

    // Events should be back in the buffer
    expect(errorBuffer).toHaveLength(1);
    expect(errorBuffer[0].message).toBe("critical error");
  });

  it("preserves event order when re-queuing", async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValueOnce(new Error("SW down"));

    errorBuffer.push(mockError("first"));
    errorBuffer.push(mockError("second"));
    errorBuffer.push(mockError("third"));

    flushBuffer();
    await vi.advanceTimersByTimeAsync(0);

    expect(errorBuffer).toHaveLength(3);
    expect(errorBuffer[0].message).toBe("first");
    expect(errorBuffer[1].message).toBe("second");
    expect(errorBuffer[2].message).toBe("third");
  });

  it("re-queues all event types independently on failure", async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValueOnce(new Error("SW down"));

    errorBuffer.push(mockError());
    consoleBuffer.push(mockConsole());
    networkBuffer.push(mockNetwork());

    flushBuffer();
    await vi.advanceTimersByTimeAsync(0);

    expect(errorBuffer).toHaveLength(1);
    expect(consoleBuffer).toHaveLength(1);
    expect(networkBuffer).toHaveLength(1);
  });

  it("caps each buffer at MAX_BUFFER_SIZE when re-queuing", async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValueOnce(new Error("SW down"));

    for (let i = 0; i < MAX_BUFFER_SIZE + 50; i++) {
      errorBuffer.push(mockError(`error-${i}`));
    }

    flushBuffer();
    await vi.advanceTimersByTimeAsync(0);

    expect(errorBuffer.length).toBe(MAX_BUFFER_SIZE);
  });

  it("keeps oldest events when capping buffer (re-queued events first)", async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValueOnce(new Error("SW down"));

    for (let i = 0; i < MAX_BUFFER_SIZE + 10; i++) {
      errorBuffer.push(mockError(`error-${i}`));
    }

    flushBuffer();
    await vi.advanceTimersByTimeAsync(0);

    // First event should be the oldest (index 0)
    expect(errorBuffer[0].message).toBe("error-0");
    expect(errorBuffer.length).toBe(MAX_BUFFER_SIZE);
  });
});

// ── buildSelector tests ─────────────────────────────────────

describe("buildSelector", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("builds selector with id (short-circuits)", () => {
    document.body.innerHTML = '<div id="root"><span></span></div>';
    const el = document.querySelector("span")!;
    const sel = buildSelector(el);
    expect(sel).toBe("div#root > span");
  });

  it("builds selector with classes", () => {
    document.body.innerHTML = '<div class="container main"><p></p></div>';
    const el = document.querySelector("p")!;
    const sel = buildSelector(el);
    expect(sel).toContain("div.container.main");
    expect(sel).toContain("p");
  });

  it("limits to at most 3 classes per element", () => {
    document.body.innerHTML = '<div class="a b c d e"><span></span></div>';
    const el = document.querySelector("span")!;
    const sel = buildSelector(el);
    expect(sel).toContain("div.a.b.c");
    expect(sel).not.toContain(".d");
  });

  it("limits depth to 5 levels", () => {
    document.body.innerHTML =
      "<div><div><div><div><div><div><div><span></span></div></div></div></div></div></div></div>";
    const el = document.querySelector("span")!;
    const sel = buildSelector(el);
    const parts = sel.split(" > ");
    expect(parts.length).toBeLessThanOrEqual(5);
  });

  it("stops at body boundary", () => {
    document.body.innerHTML = "<p></p>";
    const el = document.querySelector("p")!;
    const sel = buildSelector(el);
    expect(sel).toBe("p");
    expect(sel).not.toContain("body");
  });

  it("handles element with no id or class", () => {
    document.body.innerHTML = "<div><section><article></article></section></div>";
    const el = document.querySelector("article")!;
    const sel = buildSelector(el);
    expect(sel).toContain("article");
    expect(sel).toContain("section");
  });
});



