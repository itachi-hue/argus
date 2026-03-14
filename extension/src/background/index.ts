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
    const dataUrl = await chrome.tabs.captureVisibleTab(undefined!, { format: "jpeg", quality: 80 });
    return dataUrl.replace(/^data:image\/jpeg;base64,/, "");
  } catch {
    return null;
  }
}

async function getActiveTab(): Promise<chrome.tabs.Tab | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab || null;
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
    settings = { ...settings, ...msg.payload };
    chrome.storage.local.set({ argus_settings: settings });
    sendResponse({ ok: true });
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

