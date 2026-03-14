/**
 * Service Worker — handles hotkey, context menu, screenshots, and HTTP transport.
 */

import type {
  ArgusInternalMessage,
  ArgusSettings,
  DEFAULT_SETTINGS,
  ErrorEvent,
  ConsoleEvent,
  NetworkEvent,
  ElementCapture,
} from "../types";

// --- Settings ---
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
};

async function loadSettings() {
  const stored = await chrome.storage.local.get("argus_settings");
  if (stored.argus_settings) {
    settings = { ...settings, ...stored.argus_settings };
  }
}

loadSettings();

// --- HTTP transport ---
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

// --- Screenshot capture ---
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

// --- Description builder ---
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

// --- Handle event batches from content script ---
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

    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "user-interaction") {
    // Content script detected a user click — capture after a short delay for UI to settle
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

// --- Hotkey handler ---
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-context") return;

  const tab = await getActiveTab();
  if (!tab?.id || !tab.url) return;

  // Capture screenshot
  const screenshotData = await captureScreenshot("hotkey");

  // Build snapshot
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

  // Send page info
  await sendToServer("/ingest/page-info", snapshot.page_info);

  // Send full snapshot
  const sent = await sendToServer("/ingest/snapshot", snapshot);

  // Notify user
  if (sent) {
    chrome.action.setBadgeText({ text: "✓", tabId: tab.id });
    chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
    setTimeout(() => chrome.action.setBadgeText({ text: "", tabId: tab.id }), 2000);
  }
});

// --- Auto-capture ---
let lastAutoCaptureTime = 0;
const AUTO_CAPTURE_THROTTLE_MS = 10_000; // max once every 10 seconds

async function autoCapture(trigger: string) {
  if (!settings.auto_capture || !settings.auth_token) return;

  const now = Date.now();
  if (now - lastAutoCaptureTime < AUTO_CAPTURE_THROTTLE_MS) return;
  lastAutoCaptureTime = now;

  const tab = await getActiveTab();
  if (!tab?.id || !tab.url) return;

  // Skip chrome:// and extension pages
  if (tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) return;

  const screenshotData = await captureScreenshot(trigger);
  if (!screenshotData) return;

  // Send page info
  await sendToServer("/ingest/page-info", {
    url: tab.url,
    title: tab.title || "",
    viewport: { width: tab.width || 0, height: tab.height || 0 },
    timestamp: Date.now(),
  });

  // Send screenshot
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

// Auto-capture on page load complete
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.active) {
    autoCapture("page_load");
  }
});

// Auto-capture on tab switch
chrome.tabs.onActivated.addListener(() => {
  // Small delay to let the tab render
  setTimeout(() => autoCapture("tab_switch"), 500);
});

// --- Periodic capture — catches HMR, scroll, state changes ---
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

// --- Sync max_screenshots to server ---
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

// --- Context menu ---
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "argus-capture-element",
    title: "Capture for AI Agent",
    contexts: ["all"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "argus-capture-element" || !tab?.id) return;

  // Ask content script to capture element details
  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: "capture-element-request",
    } as ArgusInternalMessage);

    if (response?.element) {
      // Capture screenshot with element highlighted
      const screenshotData = await captureScreenshot("element");

      // Send element
      await sendToServer("/ingest/element", response.element);

      // Send screenshot
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

      // Also send page info
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

