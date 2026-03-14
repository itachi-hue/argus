/**
 * Service Worker — handles hotkey, context menu, screenshots, HTTP transport,
 * and agent browser command execution.
 */

import type {
  ArgusInternalMessage,
  ArgusSettings,
  BrowserCommand,
  DEFAULT_SETTINGS,
  ErrorEvent,
  ConsoleEvent,
  NetworkEvent,
  ElementCapture,
} from "../types";

// ═══════════════════════════════════════════════════════════
// Settings
// ═══════════════════════════════════════════════════════════

let settings: ArgusSettings = {
  server_url: "http://127.0.0.1:42777",
  auth_token: "",
  capture_console_logs: true,
  capture_network: true,
  auto_capture: true,
  capture_interval_s: 30,
  max_screenshots: 15,
  max_body_length: 2000,
  batch_interval_ms: 3000,
  batch_size: 50,
  blocked_domains: [],
  allowed_domains: [],
  agent_actions: true,
};

async function loadSettings() {
  const stored = await chrome.storage.local.get("argus_settings");
  if (stored.argus_settings) {
    settings = { ...settings, ...stored.argus_settings };
  }
}

loadSettings();

// ═══════════════════════════════════════════════════════════
// HTTP transport
// ═══════════════════════════════════════════════════════════

async function sendToServer(path: string, body: any): Promise<boolean> {
  if (!settings.auth_token) return false;
  try {
    const res = await fetch(`${settings.server_url}/api${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${settings.auth_token}`,
      },
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ═══════════════════════════════════════════════════════════
// Screenshot capture
// ═══════════════════════════════════════════════════════════

async function captureScreenshot(trigger: string = "hotkey"): Promise<string | null> {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(undefined!, { format: "jpeg", quality: 40 });
    return dataUrl.replace(/^data:image\/jpeg;base64,/, "");
  } catch {
    return null;
  }
}

async function getActiveTab(): Promise<chrome.tabs.Tab | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab || null;
}

// ═══════════════════════════════════════════════════════════
// Description builder for screenshot timeline
// ═══════════════════════════════════════════════════════════

const TRIGGER_LABELS: Record<string, string> = {
  hotkey: "Manual capture",
  page_load: "Page loaded",
  tab_switch: "Switched to tab",
  periodic: "Periodic capture",
  user_click: "After click",
  element: "Element captured",
};

function buildDescription(trigger: string, title: string, url: string): string {
  const label = TRIGGER_LABELS[trigger] || trigger;
  const shortUrl = url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  if (title) {
    return `${label}: ${title} (${shortUrl})`;
  }
  return `${label}: ${shortUrl}`;
}

// ═══════════════════════════════════════════════════════════
// Message handler — events, settings, pairing
// ═══════════════════════════════════════════════════════════

chrome.runtime.onMessage.addListener((msg: ArgusInternalMessage, sender, sendResponse) => {
  if (msg.type === "events-batch" && msg.payload) {
    const { errors, console_events, network_events } = msg.payload;
    const body: any = {};
    if (errors?.length) body.errors = errors;
    if (console_events?.length && settings.capture_console_logs) body.console_events = console_events;
    if (network_events?.length && settings.capture_network) body.network_events = network_events;

    if (Object.keys(body).length > 0) {
      sendToServer("/ingest/events", body);
    }
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "get-status") {
    fetch(`${settings.server_url}/api/health`, {
      headers: { Authorization: `Bearer ${settings.auth_token}` },
    })
      .then((r) => sendResponse({ connected: r.ok }))
      .catch(() => sendResponse({ connected: false }));
    return true;
  }

  if (msg.type === "update-settings" && msg.payload) {
    const prevInterval = settings.capture_interval_s;
    const prevAutoCapture = settings.auto_capture;
    const prevMaxScreenshots = settings.max_screenshots;
    const prevAgentActions = settings.agent_actions;

    settings = { ...settings, ...msg.payload };
    chrome.storage.local.set({ argus_settings: settings });

    // Re-create alarm if interval or auto_capture changed
    if (settings.capture_interval_s !== prevInterval || settings.auto_capture !== prevAutoCapture) {
      setupPeriodicCapture();
    }

    // Sync max_screenshots to server if changed
    if (settings.max_screenshots !== prevMaxScreenshots) {
      syncMaxScreenshots();
    }

    // Start/stop command polling if agent_actions changed
    if (settings.agent_actions !== prevAgentActions) {
      if (settings.agent_actions) {
        startCommandPolling();
      } else {
        stopCommandPolling();
      }
    }

    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "user-interaction") {
    setTimeout(() => autoCapture("user_click"), 2000);
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "pair-request") {
    fetch(`${settings.server_url}/api/pair`, { method: "POST" })
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, message: data.message }))
      .catch(() => sendResponse({ ok: false, error: "Cannot reach server. Is it running?" }));
    return true;
  }

  if (msg.type === "pair-confirm" && msg.payload?.code) {
    fetch(`${settings.server_url}/api/pair/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: msg.payload.code }),
    })
      .then(async (r) => {
        const data = await r.json();
        if (r.ok && data.token) {
          settings = { ...settings, auth_token: data.token };
          chrome.storage.local.set({ argus_settings: settings });
          sendResponse({ ok: true, token: data.token });
        } else {
          sendResponse({ ok: false, error: data.error || "Invalid code" });
        }
      })
      .catch(() => sendResponse({ ok: false, error: "Cannot reach server" }));
    return true;
  }

  return false;
});

// ═══════════════════════════════════════════════════════════
// Hotkey handler
// ═══════════════════════════════════════════════════════════

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-context") return;

  const tab = await getActiveTab();
  if (!tab?.id || !tab.url) return;

  const screenshotData = await captureScreenshot("hotkey");

  const snapshot: any = {
    timestamp: Date.now(),
    page_info: {
      url: tab.url,
      title: tab.title || "",
      viewport: { width: tab.width || 0, height: tab.height || 0 },
      timestamp: Date.now(),
    },
  };

  if (screenshotData) {
    snapshot.screenshot = {
      data: screenshotData,
      url: tab.url,
      timestamp: Date.now(),
      viewport: { width: tab.width || 0, height: tab.height || 0 },
      trigger: "hotkey",
      title: tab.title || "",
      description: buildDescription("hotkey", tab.title || "", tab.url),
    };
  }

  await sendToServer("/ingest/page-info", snapshot.page_info);
  const sent = await sendToServer("/ingest/snapshot", snapshot);

  if (sent) {
    chrome.action.setBadgeText({ text: "✓", tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
    setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 2000);
  }
});

// ═══════════════════════════════════════════════════════════
// Auto-capture
// ═══════════════════════════════════════════════════════════

let lastAutoCaptureTime = 0;
const AUTO_CAPTURE_THROTTLE_MS = 10_000;

async function autoCapture(trigger: string) {
  if (!settings.auto_capture || !settings.auth_token) return;

  const now = Date.now();
  if (now - lastAutoCaptureTime < AUTO_CAPTURE_THROTTLE_MS) return;
  lastAutoCaptureTime = now;

  const tab = await getActiveTab();
  if (!tab?.id || !tab.url) return;
  if (tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) return;

  const screenshotData = await captureScreenshot(trigger);
  if (!screenshotData) return;

  await sendToServer("/ingest/page-info", {
    url: tab.url,
    title: tab.title || "",
    viewport: { width: tab.width || 0, height: tab.height || 0 },
    timestamp: Date.now(),
  });

  await sendToServer("/ingest/screenshot", {
    data: screenshotData,
    url: tab.url,
    timestamp: Date.now(),
    viewport: { width: tab.width || 0, height: tab.height || 0 },
    trigger,
    title: tab.title || "",
    description: buildDescription(trigger, tab.title || "", tab.url),
  });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.active) {
    autoCapture("page_load");
  }
});

chrome.tabs.onActivated.addListener(() => {
  setTimeout(() => autoCapture("tab_switch"), 500);
});

// ═══════════════════════════════════════════════════════════
// Periodic capture
// ═══════════════════════════════════════════════════════════

const PERIODIC_ALARM_NAME = "argus-periodic-capture";

function setupPeriodicCapture() {
  chrome.alarms.clear(PERIODIC_ALARM_NAME, () => {
    if (settings.auto_capture && settings.capture_interval_s > 0) {
      chrome.alarms.create(PERIODIC_ALARM_NAME, {
        periodInMinutes: settings.capture_interval_s / 60,
      });
    }
  });
}

setupPeriodicCapture();

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === PERIODIC_ALARM_NAME) {
    autoCapture("periodic");
  }
});

// ═══════════════════════════════════════════════════════════
// Sync max_screenshots to server
// ═══════════════════════════════════════════════════════════

function syncMaxScreenshots() {
  if (!settings.auth_token) return;
  fetch(`${settings.server_url}/api/settings`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${settings.auth_token}`,
    },
    body: JSON.stringify({ max_screenshots: settings.max_screenshots }),
  }).catch(() => {});
}

syncMaxScreenshots();

// ═══════════════════════════════════════════════════════════
// Context menu — right-click element capture
// ═══════════════════════════════════════════════════════════

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "argus-capture-element",
    title: "Capture for AI Agent",
    contexts: ["all"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "argus-capture-element" || !tab?.id) return;

  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: "capture-element-request",
    } as ArgusInternalMessage);

    if (response?.element) {
      const screenshotData = await captureScreenshot("element");

      await sendToServer("/ingest/element", response.element);

      if (screenshotData) {
        await sendToServer("/ingest/screenshot", {
          data: screenshotData,
          url: tab.url || "",
          timestamp: Date.now(),
          viewport: { width: tab.width || 0, height: tab.height || 0 },
          trigger: "element",
          title: tab.title || "",
          description: buildDescription("element", tab.title || "", tab.url || ""),
        });
      }

      await sendToServer("/ingest/page-info", {
        url: tab.url || "",
        title: tab.title || "",
        viewport: { width: tab.width || 0, height: tab.height || 0 },
        timestamp: Date.now(),
      });

      chrome.action.setBadgeText({ text: "✓", tabId: tab.id });
      chrome.action.setBadgeBackgroundColor({ color: "#3b82f6" });
      setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 2000);
    }
  } catch {
    /* content script not available */
  }
});

// ═══════════════════════════════════════════════════════════
// AGENT BROWSER ACTIONS — command polling + execution
// ═══════════════════════════════════════════════════════════

let commandPollInterval: ReturnType<typeof setInterval> | null = null;
const COMMAND_POLL_MS = 800; // poll every 800ms for responsiveness

function startCommandPolling() {
  if (commandPollInterval) return;
  commandPollInterval = setInterval(pollAndExecuteCommands, COMMAND_POLL_MS);
}

function stopCommandPolling() {
  if (commandPollInterval) {
    clearInterval(commandPollInterval);
    commandPollInterval = null;
  }
}

async function pollAndExecuteCommands() {
  if (!settings.auth_token || !settings.agent_actions) return;

  try {
    const res = await fetch(`${settings.server_url}/api/commands/pending`, {
      headers: { Authorization: `Bearer ${settings.auth_token}` },
    });
    if (!res.ok) return;

    const commands: BrowserCommand[] = await res.json();
    for (const cmd of commands) {
      const result = await executeCommand(cmd);
      // Report result back to server
      await fetch(`${settings.server_url}/api/commands/${cmd.id}/result`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${settings.auth_token}`,
        },
        body: JSON.stringify(result),
      }).catch(() => {});
    }
  } catch {
    /* server unreachable — skip this cycle */
  }
}

// Start polling on load if settings allow
loadSettings().then(() => {
  if (settings.agent_actions) startCommandPolling();
});

// ═══════════════════════════════════════════════════════════
// Command executor — dispatches to the right handler
// ═══════════════════════════════════════════════════════════

async function executeCommand(cmd: BrowserCommand): Promise<{ success: boolean; result?: any; error?: string }> {
  const tab = await getActiveTab();
  if (!tab?.id) return { success: false, error: "No active tab" };

  const url = tab.url || "";
  if (url.startsWith("chrome://") || url.startsWith("chrome-extension://")) {
    return { success: false, error: "Cannot execute on chrome:// or extension pages" };
  }

  try {
    switch (cmd.action) {
      case "click":
        return await execInPage(tab.id, pageClick, [cmd.params.selector]);
      case "type":
        return await execInPage(tab.id, pageType, [cmd.params.selector, cmd.params.text, cmd.params.clear_first ?? true]);
      case "scroll":
        return await execInPage(tab.id, pageScroll, [cmd.params.selector, cmd.params.x, cmd.params.y, cmd.params.direction]);
      case "navigate":
        return await execNavigate(tab.id, cmd.params.url);
      case "get_text":
        return await execInPage(tab.id, pageGetText, [cmd.params.selector]);
      case "run_js":
        return await execInPageMain(tab.id, pageRunJs, [cmd.params.code]);
      case "highlight":
        return await execInPage(tab.id, pageHighlight, [cmd.params.selector, cmd.params.color, cmd.params.duration_ms]);
      case "wait_for":
        return await execInPage(tab.id, pageWaitFor, [cmd.params.selector, cmd.params.timeout_ms]);
      case "fill_form":
        return await execInPage(tab.id, pageFillForm, [cmd.params.fields]);
      case "capture_viewport":
        return await execCaptureViewport(tab, cmd.params.width, cmd.params.height);
      case "get_perf":
        return await execInPageMain(tab.id, pageGetPerf, []);
      case "get_storage":
        return await execInPageMain(tab.id, pageGetStorage, [cmd.params.type]);
      case "get_cookies":
        return await execGetCookies(tab.url || "");
      case "a11y_audit":
        return await execInPage(tab.id, pageA11yAudit, [cmd.params.selector]);
      default:
        return { success: false, error: `Unknown action: ${cmd.action}` };
    }
  } catch (e: any) {
    return { success: false, error: e.message || String(e) };
  }
}

// ═══════════════════════════════════════════════════════════
// Helper: execute a function in the page (isolated world)
// ═══════════════════════════════════════════════════════════

async function execInPage(tabId: number, func: (...args: any[]) => any, args: any[]): Promise<any> {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func,
    args,
  });
  return results[0]?.result ?? { success: false, error: "No result from page script" };
}

// Execute in MAIN world (access page globals like window.__NEXT_DATA__)
async function execInPageMain(tabId: number, func: (...args: any[]) => any, args: any[]): Promise<any> {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func,
    args,
    world: "MAIN" as any,
  });
  return results[0]?.result ?? { success: false, error: "No result from page script" };
}

// ═══════════════════════════════════════════════════════════
// Page functions — serialized & injected into tab context
// Each must be self-contained (no closures, no imports)
// ═══════════════════════════════════════════════════════════

function pageClick(selector: string) {
  const el = document.querySelector(selector);
  if (!el) return { success: false, error: `Element not found: ${selector}` };
  (el as HTMLElement).click();
  const tag = el.tagName.toLowerCase();
  const text = (el.textContent || "").slice(0, 100).trim();
  return { success: true, result: { clicked: selector, tag, text } };
}

function pageType(selector: string, text: string, clearFirst: boolean) {
  const el = document.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement | null;
  if (!el) return { success: false, error: `Element not found: ${selector}` };
  el.focus();
  if (clearFirst) {
    el.value = "";
  }
  // Type character by character for better framework compatibility
  el.value = clearFirst ? text : el.value + text;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  // For React — dispatch a native input event
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(el),
    "value"
  )?.set;
  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(el, clearFirst ? text : el.value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
  return { success: true, result: { typed: text, into: selector } };
}

function pageScroll(selector: string | null, x: number, y: number, direction: string | null) {
  if (direction) {
    const map: Record<string, [number, number]> = {
      top: [0, 0],
      bottom: [0, document.body.scrollHeight],
      up: [0, window.scrollY - window.innerHeight],
      down: [0, window.scrollY + window.innerHeight],
    };
    const [sx, sy] = map[direction] || [0, 0];
    window.scrollTo({ left: sx, top: sy, behavior: "smooth" });
    return { success: true, result: { scrolled: direction } };
  }
  if (selector) {
    const el = document.querySelector(selector);
    if (!el) return { success: false, error: `Element not found: ${selector}` };
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    return { success: true, result: { scrolledTo: selector } };
  }
  window.scrollTo({ left: x, top: y, behavior: "smooth" });
  return { success: true, result: { scrolledTo: { x, y } } };
}

function pageGetText(selector: string) {
  const el = document.querySelector(selector);
  if (!el) return { success: false, error: `Element not found: ${selector}` };
  const text = (el.textContent || "").trim().slice(0, 5000);
  const tag = el.tagName.toLowerCase();
  const attrs: Record<string, string> = {};
  for (const attr of Array.from(el.attributes).slice(0, 10)) {
    attrs[attr.name] = attr.value.slice(0, 200);
  }
  return { success: true, result: { text, tag, attributes: attrs, html: el.outerHTML.slice(0, 2000) } };
}

function pageRunJs(code: string) {
  try {
    // Use Function constructor for cleaner scoping
    const result = new Function(`"use strict"; return (${code})`)();
    let serialized: string;
    const type = typeof result;
    if (result === undefined) {
      serialized = "undefined";
    } else if (result === null) {
      serialized = "null";
    } else if (type === "object") {
      try {
        serialized = JSON.stringify(result, null, 2);
        if (serialized && serialized.length > 10000) {
          serialized = serialized.slice(0, 10000) + "... [truncated]";
        }
      } catch {
        serialized = String(result);
      }
    } else {
      serialized = String(result);
    }
    return { success: true, result: { value: serialized, type } };
  } catch (e: any) {
    // Try as statement (not expression)
    try {
      const result = new Function(`"use strict"; ${code}`)();
      return { success: true, result: { value: String(result ?? "undefined"), type: typeof result } };
    } catch (e2: any) {
      return { success: false, error: e.message || String(e) };
    }
  }
}

function pageHighlight(selector: string, color: string, durationMs: number) {
  const el = document.querySelector(selector) as HTMLElement | null;
  if (!el) return { success: false, error: `Element not found: ${selector}` };
  const origOutline = el.style.outline;
  const origOutlineOffset = el.style.outlineOffset;
  el.style.outline = `3px solid ${color}`;
  el.style.outlineOffset = "2px";
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => {
    el.style.outline = origOutline;
    el.style.outlineOffset = origOutlineOffset;
  }, durationMs);
  return { success: true, result: { highlighted: selector, color, duration_ms: durationMs } };
}

function pageWaitFor(selector: string, timeoutMs: number): Promise<any> {
  return new Promise((resolve) => {
    // Check immediately
    if (document.querySelector(selector)) {
      resolve({ success: true, result: { found: true, selector, waited_ms: 0 } });
      return;
    }
    const start = Date.now();
    const observer = new MutationObserver(() => {
      if (document.querySelector(selector)) {
        observer.disconnect();
        resolve({ success: true, result: { found: true, selector, waited_ms: Date.now() - start } });
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      if (document.querySelector(selector)) {
        resolve({ success: true, result: { found: true, selector, waited_ms: Date.now() - start } });
      } else {
        resolve({ success: false, error: `Element "${selector}" not found within ${timeoutMs}ms` });
      }
    }, timeoutMs);
  });
}

function pageFillForm(fields: Record<string, string>) {
  const results: Record<string, string> = {};
  let filled = 0;
  let errors = 0;
  for (const [selector, value] of Object.entries(fields)) {
    const el = document.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null;
    if (!el) {
      results[selector] = "not found";
      errors++;
      continue;
    }
    el.focus();
    if (el.tagName === "SELECT") {
      (el as HTMLSelectElement).value = value;
    } else {
      (el as HTMLInputElement).value = value;
      // React compatibility
      const setter = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(el),
        "value"
      )?.set;
      if (setter) {
        setter.call(el, value);
      }
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    results[selector] = "filled";
    filled++;
  }
  return { success: errors === 0, result: { filled, errors, details: results } };
}

function pageGetPerf() {
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  const paint = performance.getEntriesByType("paint");
  const lcpEntries = performance.getEntriesByType("largest-contentful-paint");
  const resources = performance.getEntriesByType("resource");

  const fcp = paint.find((e) => e.name === "first-contentful-paint");
  const lcp = lcpEntries.length > 0 ? lcpEntries[lcpEntries.length - 1] : null;

  const metrics: Record<string, any> = {
    // Navigation timing
    ttfb: nav ? Math.round(nav.responseStart - nav.requestStart) : null,
    dom_content_loaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
    dom_interactive: nav ? Math.round(nav.domInteractive) : null,
    load_time: nav ? Math.round(nav.loadEventEnd) : null,

    // Paint timing
    fcp_ms: fcp ? Math.round(fcp.startTime) : null,

    // Largest Contentful Paint
    lcp_ms: lcp ? Math.round(lcp.startTime) : null,

    // Memory (Chrome-specific)
    memory: (performance as any).memory
      ? {
          used_mb: Math.round((performance as any).memory.usedJSHeapSize / 1048576),
          total_mb: Math.round((performance as any).memory.totalJSHeapSize / 1048576),
          limit_mb: Math.round((performance as any).memory.jsHeapSizeLimit / 1048576),
        }
      : null,

    // Resource summary
    resource_count: resources.length,
    resource_breakdown: {} as Record<string, number>,
    total_transfer_kb: 0,
  };

  // Breakdown by type
  const breakdown: Record<string, number> = {};
  let totalTransfer = 0;
  for (const r of resources as PerformanceResourceTiming[]) {
    const type = r.initiatorType || "other";
    breakdown[type] = (breakdown[type] || 0) + 1;
    totalTransfer += r.transferSize || 0;
  }
  metrics.resource_breakdown = breakdown;
  metrics.total_transfer_kb = Math.round(totalTransfer / 1024);

  return { success: true, result: metrics };
}

function pageGetStorage(storageType: string) {
  const result: Record<string, any> = {};

  if (storageType === "local" || storageType === "all") {
    try {
      const local: Record<string, string> = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key) {
          const val = localStorage.getItem(key) || "";
          local[key] = val.length > 500 ? val.slice(0, 500) + `... [${val.length} chars]` : val;
        }
      }
      result.localStorage = { count: localStorage.length, items: local };
    } catch (e: any) {
      result.localStorage = { error: e.message };
    }
  }

  if (storageType === "session" || storageType === "all") {
    try {
      const session: Record<string, string> = {};
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key) {
          const val = sessionStorage.getItem(key) || "";
          session[key] = val.length > 500 ? val.slice(0, 500) + `... [${val.length} chars]` : val;
        }
      }
      result.sessionStorage = { count: sessionStorage.length, items: session };
    } catch (e: any) {
      result.sessionStorage = { error: e.message };
    }
  }

  return { success: true, result };
}

function pageA11yAudit(scopeSelector: string | null) {
  const root = scopeSelector ? document.querySelector(scopeSelector) : document.documentElement;
  if (!root) return { success: false, error: `Scope element not found: ${scopeSelector}` };

  const issues: { type: string; severity: string; element: string; message: string }[] = [];

  // 1. Images without alt text
  for (const img of Array.from(root.querySelectorAll("img"))) {
    if (!img.hasAttribute("alt")) {
      issues.push({
        type: "missing-alt",
        severity: "error",
        element: img.outerHTML.slice(0, 200),
        message: "Image missing alt attribute",
      });
    }
  }

  // 2. Form inputs without labels
  for (const input of Array.from(root.querySelectorAll("input, textarea, select"))) {
    const inp = input as HTMLInputElement;
    if (inp.type === "hidden" || inp.type === "submit" || inp.type === "button") continue;
    const id = inp.id;
    const hasLabel = id && root.querySelector(`label[for="${id}"]`);
    const hasAria = inp.getAttribute("aria-label") || inp.getAttribute("aria-labelledby");
    const hasTitle = inp.getAttribute("title");
    const hasPlaceholder = inp.getAttribute("placeholder");
    if (!hasLabel && !hasAria && !hasTitle && !hasPlaceholder) {
      issues.push({
        type: "missing-label",
        severity: "error",
        element: inp.outerHTML.slice(0, 200),
        message: "Form input has no label, aria-label, or title",
      });
    }
  }

  // 3. Empty links
  for (const a of Array.from(root.querySelectorAll("a"))) {
    const text = (a.textContent || "").trim();
    const aria = a.getAttribute("aria-label");
    const title = a.getAttribute("title");
    if (!text && !aria && !title && !a.querySelector("img")) {
      issues.push({
        type: "empty-link",
        severity: "warning",
        element: a.outerHTML.slice(0, 200),
        message: "Link has no text content or aria-label",
      });
    }
  }

  // 4. Empty buttons
  for (const btn of Array.from(root.querySelectorAll("button"))) {
    const text = (btn.textContent || "").trim();
    const aria = btn.getAttribute("aria-label");
    const title = btn.getAttribute("title");
    if (!text && !aria && !title && !btn.querySelector("img, svg")) {
      issues.push({
        type: "empty-button",
        severity: "warning",
        element: btn.outerHTML.slice(0, 200),
        message: "Button has no text content or aria-label",
      });
    }
  }

  // 5. Missing document language
  if (!scopeSelector) {
    const html = document.documentElement;
    if (!html.getAttribute("lang")) {
      issues.push({
        type: "missing-lang",
        severity: "warning",
        element: "<html>",
        message: "Document missing lang attribute on <html>",
      });
    }
  }

  // 6. Missing document title
  if (!scopeSelector && !document.title) {
    issues.push({
      type: "missing-title",
      severity: "warning",
      element: "<head>",
      message: "Document has no <title>",
    });
  }

  // 7. Headings skip levels
  if (!scopeSelector) {
    const headings = Array.from(root.querySelectorAll("h1, h2, h3, h4, h5, h6"));
    let lastLevel = 0;
    for (const h of headings) {
      const level = parseInt(h.tagName[1]);
      if (lastLevel > 0 && level > lastLevel + 1) {
        issues.push({
          type: "heading-skip",
          severity: "warning",
          element: h.outerHTML.slice(0, 200),
          message: `Heading skips level: h${lastLevel} → h${level}`,
        });
      }
      lastLevel = level;
    }
  }

  // 8. Low contrast indicators — check for very light text on white bg
  for (const el of Array.from(root.querySelectorAll("p, span, a, li, td, th, label, h1, h2, h3, h4, h5, h6")).slice(0, 50)) {
    const style = window.getComputedStyle(el);
    const color = style.color;
    const bg = style.backgroundColor;
    // Simple check: if text color is very light (#ccc or lighter) and bg is transparent/white
    const rgbMatch = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (rgbMatch) {
      const [, r, g, b] = rgbMatch.map(Number);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      if (luminance > 0.85 && (bg === "rgba(0, 0, 0, 0)" || bg === "rgb(255, 255, 255)")) {
        issues.push({
          type: "low-contrast",
          severity: "warning",
          element: `<${el.tagName.toLowerCase()}> "${(el.textContent || "").slice(0, 50)}"`,
          message: `Potentially low contrast text (color: ${color})`,
        });
      }
    }
  }

  // 9. Tab index > 0 (anti-pattern)
  for (const el of Array.from(root.querySelectorAll("[tabindex]"))) {
    const ti = parseInt(el.getAttribute("tabindex") || "0");
    if (ti > 0) {
      issues.push({
        type: "tabindex-positive",
        severity: "warning",
        element: el.outerHTML.slice(0, 200),
        message: `tabindex="${ti}" disrupts natural tab order`,
      });
    }
  }

  const summary = {
    total: issues.length,
    errors: issues.filter((i) => i.severity === "error").length,
    warnings: issues.filter((i) => i.severity === "warning").length,
  };

  return { success: true, result: { summary, issues: issues.slice(0, 50) } };
}

// ═══════════════════════════════════════════════════════════
// Special commands — navigate, cookies, viewport capture
// ═══════════════════════════════════════════════════════════

async function execNavigate(tabId: number, url: string): Promise<any> {
  try {
    await chrome.tabs.update(tabId, { url });
    // Wait a bit for navigation to start
    return { success: true, result: { navigated: url } };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

async function execGetCookies(url: string): Promise<any> {
  try {
    const cookies = await chrome.cookies.getAll({ url });
    const sanitized = cookies.map((c) => ({
      name: c.name,
      value: c.value.length > 50 ? c.value.slice(0, 50) + "..." : c.value,
      domain: c.domain,
      path: c.path,
      secure: c.secure,
      httpOnly: c.httpOnly,
      sameSite: c.sameSite,
      expirationDate: c.expirationDate,
    }));
    return { success: true, result: { count: cookies.length, cookies: sanitized } };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}

async function execCaptureViewport(
  tab: chrome.tabs.Tab,
  width: number,
  height: number
): Promise<any> {
  const windowId = tab.windowId;
  if (!windowId) return { success: false, error: "No window ID" };

  try {
    // Get current window size
    const currentWindow = await chrome.windows.get(windowId);
    const origWidth = currentWindow.width || 1280;
    const origHeight = currentWindow.height || 800;

    // Resize to target dimensions
    await chrome.windows.update(windowId, { width, height });

    // Wait for resize to settle
    await new Promise((r) => setTimeout(r, 1000));

    // Capture screenshot
    const screenshotData = await captureScreenshot("viewport_test");

    // Restore original size
    await chrome.windows.update(windowId, { width: origWidth, height: origHeight });

    if (!screenshotData) {
      return { success: false, error: "Failed to capture screenshot after resize" };
    }

    return {
      success: true,
      result: {
        screenshot: screenshotData,
        url: tab.url || "",
        viewport: { width, height },
        original_viewport: { width: origWidth, height: origHeight },
      },
    };
  } catch (e: any) {
    return { success: false, error: e.message };
  }
}
