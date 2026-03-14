/** Shared types matching Python Pydantic models. */

export interface ErrorEvent {
  message: string;
  source: string;
  lineno: number;
  colno: number;
  stack: string;
  timestamp: number;
  occurrence_count: number;
}

export interface ConsoleEvent {
  level: string;
  args: string[];
  timestamp: number;
  source: string;
  lineno: number;
}

export interface NetworkEvent {
  method: string;
  url: string;
  status: number | null;
  status_text: string;
  request_headers: Record<string, string>;
  response_headers: Record<string, string>;
  request_body: string | null;
  response_body: string | null;
  duration_ms: number | null;
  timestamp: number;
  error: string | null;
}

export interface Screenshot {
  data: string; // base64 JPEG
  url: string;
  timestamp: number;
  viewport: { width: number; height: number };
  trigger: string;
}

export interface ElementCapture {
  selector: string;
  computed_styles: Record<string, string>;
  html: string;
  text: string;
  bounding_rect: { x: number; y: number; width: number; height: number };
  parent_html: string;
  timestamp: number;
  url: string;
  screenshot_index: number | null;
}

export interface PageInfo {
  url: string;
  title: string;
  viewport: { width: number; height: number };
  timestamp: number;
}

/** Messages from injected script → content script via window.postMessage */
export interface ArgusMessage {
  type: "argus-error" | "argus-console" | "argus-network";
  payload: ErrorEvent | ConsoleEvent | NetworkEvent;
}

/** Messages from content script → service worker via chrome.runtime.sendMessage */
export interface ArgusInternalMessage {
  type:
    | "events-batch"
    | "element-captured"
    | "capture-element-request"
    | "get-status"
    | "update-settings"
    | "pair-request"
    | "pair-confirm";
  payload?: any;
}

export interface ArgusSettings {
  server_url: string;
  auth_token: string;
  capture_console_logs: boolean;
  capture_network: boolean;
  auto_capture: boolean;
  max_body_length: number;
  batch_interval_ms: number;
  batch_size: number;
  blocked_domains: string[];
  allowed_domains: string[];
}

export const DEFAULT_SETTINGS: ArgusSettings = {
  server_url: "http://127.0.0.1:42777",
  auth_token: "",
  capture_console_logs: true,
  capture_network: true,
  auto_capture: true,
  max_body_length: 2000,
  batch_interval_ms: 3000,
  batch_size: 50,
  blocked_domains: [],
  allowed_domains: [],
};

