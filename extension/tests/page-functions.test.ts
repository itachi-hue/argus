/**
 * Tests for the self-contained page functions injected via chrome.scripting.executeScript.
 * These run in the page's DOM context — tested here with jsdom.
 */
import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";

// Fake timers before the background module loads
vi.hoisted(() => {
  vi.useFakeTimers();
});

import {
  buildDescription,
  pageClick,
  pageType,
  pageScroll,
  pageGetText,
  pageRunJs,
  pageHighlight,
  pageWaitFor,
  pageFillForm,
  pageA11yAudit,
} from "../src/background/index";

afterAll(() => {
  vi.useRealTimers();
});

// ── buildDescription ────────────────────────────────────────

describe("buildDescription", () => {
  it("formats with known trigger, title, and URL", () => {
    const desc = buildDescription("hotkey", "My Page", "https://example.com/path");
    expect(desc).toBe("Manual capture: My Page (example.com/path)");
  });

  it("strips protocol and trailing slash from URL", () => {
    const desc = buildDescription("page_load", "", "https://example.com/");
    expect(desc).toBe("Page loaded: example.com");
  });

  it("uses raw trigger name for unknown triggers", () => {
    const desc = buildDescription("custom", "Title", "https://example.com");
    expect(desc).toBe("custom: Title (example.com)");
  });

  it("omits title when empty", () => {
    const desc = buildDescription("tab_switch", "", "https://example.com");
    expect(desc).toBe("Switched to tab: example.com");
  });

  it("handles all known trigger labels", () => {
    const triggers: Record<string, string> = {
      hotkey: "Manual capture",
      page_load: "Page loaded",
      tab_switch: "Switched to tab",
      periodic: "Periodic capture",
      user_click: "After click",
      element: "Element captured",
    };
    for (const [trigger, label] of Object.entries(triggers)) {
      const desc = buildDescription(trigger, "", "https://x.com");
      expect(desc).toContain(label);
    }
  });
});

// ── pageClick ───────────────────────────────────────────────

describe("pageClick", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("clicks element and returns tag + text", () => {
    document.body.innerHTML = '<button id="btn">Submit</button>';
    const result = pageClick("#btn");
    expect(result).toEqual({
      success: true,
      result: { clicked: "#btn", tag: "button", text: "Submit" },
    });
  });

  it("truncates long text content to 100 chars", () => {
    document.body.innerHTML = `<div id="long">${"a".repeat(200)}</div>`;
    const result = pageClick("#long");
    expect(result.success).toBe(true);
    expect(result.result.text.length).toBeLessThanOrEqual(100);
  });

  it("returns error for missing element", () => {
    const result = pageClick("#nonexistent");
    expect(result.success).toBe(false);
    expect(result.error).toContain("not found");
  });
});

// ── pageType ────────────────────────────────────────────────

describe("pageType", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("types text with clearFirst=true", () => {
    document.body.innerHTML = '<input id="inp" value="old" />';
    const result = pageType("#inp", "new text", true);
    expect(result.success).toBe(true);
    expect((document.querySelector("#inp") as HTMLInputElement).value).toBe("new text");
  });

  it("appends text with clearFirst=false", () => {
    document.body.innerHTML = '<input id="inp" value="hello " />';
    pageType("#inp", "world", false);
    expect((document.querySelector("#inp") as HTMLInputElement).value).toBe("hello world");
  });

  it("dispatches input and change events", () => {
    document.body.innerHTML = '<input id="inp" />';
    const events: string[] = [];
    const input = document.querySelector("#inp") as HTMLInputElement;
    input.addEventListener("input", () => events.push("input"));
    input.addEventListener("change", () => events.push("change"));

    pageType("#inp", "test", true);

    expect(events).toContain("input");
    expect(events).toContain("change");
  });

  it("returns error for missing element", () => {
    const result = pageType("#missing", "text", true);
    expect(result.success).toBe(false);
  });
});

// ── pageScroll ──────────────────────────────────────────────

describe("pageScroll", () => {
  it("scrolls by direction", () => {
    const result = pageScroll(null, 0, 0, "top");
    expect(result.success).toBe(true);
    expect(result.result.scrolled).toBe("top");
  });

  it("scrolls to selector", () => {
    document.body.innerHTML = '<div id="target" style="margin-top:2000px">Target</div>';
    const result = pageScroll("#target", 0, 0, null);
    expect(result.success).toBe(true);
    expect(result.result.scrolledTo).toBe("#target");
  });

  it("scrolls to absolute coordinates", () => {
    const result = pageScroll(null, 100, 500, null);
    expect(result.success).toBe(true);
    expect(result.result.scrolledTo).toEqual({ x: 100, y: 500 });
  });

  it("returns error for missing selector", () => {
    document.body.innerHTML = "";
    const result = pageScroll("#missing", 0, 0, null);
    expect(result.success).toBe(false);
  });
});

// ── pageGetText ─────────────────────────────────────────────

describe("pageGetText", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("returns text, tag, and attributes", () => {
    document.body.innerHTML = '<a href="/page" class="link">Click here</a>';
    const result = pageGetText("a.link");
    expect(result.success).toBe(true);
    expect(result.result.text).toBe("Click here");
    expect(result.result.tag).toBe("a");
    expect(result.result.attributes.href).toBe("/page");
  });

  it("truncates text at 5000 chars", () => {
    document.body.innerHTML = `<div id="big">${"x".repeat(6000)}</div>`;
    const result = pageGetText("#big");
    expect(result.result.text.length).toBeLessThanOrEqual(5000);
  });

  it("includes outerHTML (truncated to 2000)", () => {
    document.body.innerHTML = `<div id="el">${"y".repeat(3000)}</div>`;
    const result = pageGetText("#el");
    expect(result.result.html.length).toBeLessThanOrEqual(2000);
  });

  it("returns error for missing element", () => {
    const result = pageGetText("#missing");
    expect(result.success).toBe(false);
  });
});

// ── pageRunJs ───────────────────────────────────────────────

describe("pageRunJs", () => {
  it("evaluates numeric expressions", () => {
    const result = pageRunJs("2 + 2");
    expect(result.success).toBe(true);
    expect(result.result.value).toBe("4");
    expect(result.result.type).toBe("number");
  });

  it("evaluates string expressions", () => {
    const result = pageRunJs('"hello"');
    expect(result.success).toBe(true);
    expect(result.result.value).toBe("hello");
    expect(result.result.type).toBe("string");
  });

  it("evaluates object expressions", () => {
    const result = pageRunJs("({a: 1, b: 2})");
    expect(result.success).toBe(true);
    expect(result.result.type).toBe("object");
  });

  it("handles null", () => {
    const result = pageRunJs("null");
    expect(result.success).toBe(true);
    expect(result.result.value).toBe("null");
  });

  it("handles undefined", () => {
    const result = pageRunJs("undefined");
    expect(result.success).toBe(true);
    expect(result.result.value).toBe("undefined");
  });

  it("falls back to statement evaluation", () => {
    // `var x = 5` is not a valid expression but is a valid statement
    const result = pageRunJs("var x = 5");
    expect(result.success).toBe(true);
  });

  it("returns error for runtime errors", () => {
    const result = pageRunJs("undefinedVariable.property");
    expect(result.success).toBe(false);
    expect(result.error).toBeTruthy();
  });

  it("truncates long object output at 10000 chars", () => {
    // Must return an object (not string) to trigger the truncation path
    const result = pageRunJs("Array.from({length: 5000}, (_, i) => ({key: i, val: 'x'.repeat(10)}))");
    expect(result.success).toBe(true);
    expect(result.result.type).toBe("object");
    expect(result.result.value.length).toBeLessThanOrEqual(10100); // 10000 + "... [truncated]"
  });
});

// ── pageHighlight ───────────────────────────────────────────

describe("pageHighlight", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("sets outline on element", () => {
    document.body.innerHTML = '<div id="target">Target</div>';
    const result = pageHighlight("#target", "red", 2000);
    expect(result.success).toBe(true);
    expect(result.result).toEqual({ highlighted: "#target", color: "red", duration_ms: 2000 });
    const el = document.querySelector("#target") as HTMLElement;
    expect(el.style.outline).toBe("3px solid red");
  });

  it("restores original outline after duration", () => {
    document.body.innerHTML = '<div id="target" style="outline: 1px solid blue">X</div>';
    pageHighlight("#target", "red", 500);
    const el = document.querySelector("#target") as HTMLElement;
    expect(el.style.outline).toBe("3px solid red");

    vi.advanceTimersByTime(500);
    expect(el.style.outline).toBe("1px solid blue");
  });

  it("returns error for missing element", () => {
    const result = pageHighlight("#missing", "red", 1000);
    expect(result.success).toBe(false);
  });
});

// ── pageWaitFor ─────────────────────────────────────────────

describe("pageWaitFor", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("resolves immediately when element already exists", async () => {
    document.body.innerHTML = '<div id="exists">here</div>';
    const result = await pageWaitFor("#exists", 5000);
    expect(result.success).toBe(true);
    expect(result.result.found).toBe(true);
    expect(result.result.waited_ms).toBe(0);
  });

  it("returns error on timeout", async () => {
    const promise = pageWaitFor("#never", 1000);
    vi.advanceTimersByTime(1001);
    const result = await promise;
    expect(result.success).toBe(false);
    expect(result.error).toContain("not found within 1000ms");
  });
});

// ── pageFillForm ────────────────────────────────────────────

describe("pageFillForm", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("fills multiple input fields", () => {
    document.body.innerHTML = '<input id="name" /><input id="email" />';
    const result = pageFillForm({ "#name": "John", "#email": "john@test.com" });
    expect(result.success).toBe(true);
    expect(result.result.filled).toBe(2);
    expect(result.result.errors).toBe(0);
    expect((document.querySelector("#name") as HTMLInputElement).value).toBe("John");
    expect((document.querySelector("#email") as HTMLInputElement).value).toBe("john@test.com");
  });

  it("fills select elements", () => {
    document.body.innerHTML =
      '<select id="country"><option value="us">US</option><option value="uk">UK</option></select>';
    const result = pageFillForm({ "#country": "uk" });
    expect(result.success).toBe(true);
    expect((document.querySelector("#country") as HTMLSelectElement).value).toBe("uk");
  });

  it("reports missing fields as errors", () => {
    document.body.innerHTML = '<input id="name" />';
    const result = pageFillForm({ "#name": "John", "#missing": "value" });
    expect(result.success).toBe(false);
    expect(result.result.filled).toBe(1);
    expect(result.result.errors).toBe(1);
    expect(result.result.details["#missing"]).toBe("not found");
  });

  it("dispatches input and change events on each field", () => {
    document.body.innerHTML = '<input id="field" />';
    const events: string[] = [];
    const input = document.querySelector("#field") as HTMLInputElement;
    input.addEventListener("input", () => events.push("input"));
    input.addEventListener("change", () => events.push("change"));

    pageFillForm({ "#field": "test" });

    expect(events).toContain("input");
    expect(events).toContain("change");
  });
});

// ── pageA11yAudit ───────────────────────────────────────────

describe("pageA11yAudit", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("detects images without alt text", () => {
    document.body.innerHTML = '<img src="photo.jpg" />';
    const result = pageA11yAudit(null);
    expect(result.success).toBe(true);
    const altIssues = result.result.issues.filter((i: any) => i.type === "missing-alt");
    expect(altIssues.length).toBeGreaterThan(0);
    expect(altIssues[0].severity).toBe("error");
  });

  it("detects form inputs without labels", () => {
    document.body.innerHTML = '<input type="text" />';
    const result = pageA11yAudit(null);
    const labelIssues = result.result.issues.filter((i: any) => i.type === "missing-label");
    expect(labelIssues.length).toBeGreaterThan(0);
  });

  it("passes clean markup without errors", () => {
    document.body.innerHTML = `
      <img src="photo.jpg" alt="A photo" />
      <label for="name">Name</label>
      <input id="name" type="text" />
    `;
    const result = pageA11yAudit(null);
    const errors = result.result.issues.filter((i: any) => i.severity === "error");
    expect(errors).toHaveLength(0);
  });

  it("scopes audit to a selector", () => {
    document.body.innerHTML = `
      <div id="scope"><img src="a.jpg" /></div>
      <img src="b.jpg" />
    `;
    const result = pageA11yAudit("#scope");
    const altIssues = result.result.issues.filter((i: any) => i.type === "missing-alt");
    // Only the img inside #scope should be flagged
    expect(altIssues).toHaveLength(1);
  });

  it("returns error for missing scope selector", () => {
    const result = pageA11yAudit("#nonexistent");
    expect(result.success).toBe(false);
  });

  it("returns summary with totals", () => {
    document.body.innerHTML = '<img src="x.jpg" /><input type="text" />';
    const result = pageA11yAudit(null);
    expect(result.result.summary).toHaveProperty("total");
    expect(result.result.summary).toHaveProperty("errors");
    expect(result.result.summary).toHaveProperty("warnings");
    expect(result.result.summary.total).toBeGreaterThan(0);
  });
});

