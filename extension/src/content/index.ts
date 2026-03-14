/**
 * Content script — bridges injected script and service worker.
 * Handles element capture for right-click context menu.
 */

import type { ErrorEvent, ConsoleEvent, NetworkEvent, ArgusInternalMessage } from "../types";

const ARGUS_ID = "__argus__";

// --- Event buffer ---
let errorBuffer: ErrorEvent[] = [];
let consoleBuffer: ConsoleEvent[] = [];
let networkBuffer: NetworkEvent[] = [];

// --- Inject page-context script ---
function injectScript() {
  const script = document.createElement("script");
  script.src = chrome.runtime.getURL("dist/injected/index.js");
  script.onload = () => script.remove();
  (document.head || document.documentElement).appendChild(script);
}

injectScript();

// --- Listen for messages from injected script ---
window.addEventListener("message", (event) => {
  if (event.source !== window || event.data?.source !== ARGUS_ID) return;

  const { type, payload } = event.data;
  switch (type) {
    case "argus-error":
      errorBuffer.push(payload as ErrorEvent);
      break;
    case "argus-console":
      consoleBuffer.push(payload as ConsoleEvent);
      break;
    case "argus-network":
      networkBuffer.push(payload as NetworkEvent);
      break;
  }
});

// --- Batch send to service worker ---
function flushBuffer() {
  if (errorBuffer.length === 0 && consoleBuffer.length === 0 && networkBuffer.length === 0) return;

  const msg: ArgusInternalMessage = {
    type: "events-batch",
    payload: {
      errors: errorBuffer.splice(0),
      console_events: consoleBuffer.splice(0),
      network_events: networkBuffer.splice(0),
    },
  };

  chrome.runtime.sendMessage(msg).catch(() => {
    /* SW might be inactive, events stored for next flush */
  });
}

setInterval(flushBuffer, 3000);

// --- Element capture ---

const CAPTURED_STYLES = [
  // Layout
  "display", "position", "top", "right", "bottom", "left",
  "float", "flex-direction", "flex-wrap", "flex-grow", "flex-shrink", "flex-basis",
  "justify-content", "align-items", "align-self",
  "grid-template-columns", "grid-template-rows", "grid-column", "grid-row", "gap",
  // Box model
  "width", "height", "min-width", "min-height", "max-width", "max-height",
  "margin-top", "margin-right", "margin-bottom", "margin-left",
  "padding-top", "padding-right", "padding-bottom", "padding-left",
  "border-width", "border-style", "border-color", "border-radius", "box-sizing",
  // Typography
  "font-family", "font-size", "font-weight", "line-height",
  "color", "text-align", "text-decoration", "text-transform",
  // Visual
  "background-color", "background-image", "opacity", "visibility",
  "overflow", "overflow-x", "overflow-y", "z-index", "box-shadow",
  // Transform
  "transform", "transition",
];

function buildSelector(el: Element): string {
  const parts: string[] = [];
  let current: Element | null = el;
  while (current && current !== document.body && parts.length < 5) {
    let s = current.tagName.toLowerCase();
    if (current.id) {
      s += `#${current.id}`;
      parts.unshift(s);
      break;
    }
    if (current.className && typeof current.className === "string") {
      const classes = current.className.trim().split(/\s+/).slice(0, 3).join(".");
      if (classes) s += `.${classes}`;
    }
    parts.unshift(s);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

function captureElement(x: number, y: number) {
  const el = document.elementFromPoint(x, y);
  if (!el) return null;

  const rect = el.getBoundingClientRect();
  const computed = window.getComputedStyle(el);
  const styles: Record<string, string> = {};
  for (const prop of CAPTURED_STYLES) {
    const val = computed.getPropertyValue(prop);
    if (val && val !== "none" && val !== "normal" && val !== "auto" && val !== "0px") {
      styles[prop] = val;
    }
  }

  // Highlight element briefly
  const origOutline = (el as HTMLElement).style.outline;
  (el as HTMLElement).style.outline = "2px solid red";
  setTimeout(() => {
    (el as HTMLElement).style.outline = origOutline;
  }, 500);

  return {
    selector: buildSelector(el),
    computed_styles: styles,
    html: el.outerHTML.slice(0, 2000),
    text: (el.textContent || "").slice(0, 500),
    bounding_rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    parent_html: el.parentElement?.outerHTML?.slice(0, 1000) || "",
    timestamp: Date.now(),
    url: window.location.href,
    screenshot_index: null,
  };
}

// Track last right-click position
let lastRightClickX = 0;
let lastRightClickY = 0;
document.addEventListener("contextmenu", (e) => {
  lastRightClickX = e.clientX;
  lastRightClickY = e.clientY;
});

// Listen for element capture requests from service worker
chrome.runtime.onMessage.addListener((msg: ArgusInternalMessage, _sender, sendResponse) => {
  if (msg.type === "capture-element-request") {
    const element = captureElement(lastRightClickX, lastRightClickY);
    sendResponse({ element });
    // Also flush current buffer so snapshot includes latest events
    flushBuffer();
    return true;
  }
  return false;
});




