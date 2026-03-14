/**
 * Global test setup — mocks Chrome extension APIs and fetch
 * so source modules can be imported without errors.
 */
import { vi } from "vitest";

const chromeMock = {
  runtime: {
    getURL: vi.fn((path: string) => `chrome-extension://test-id/${path}`),
    sendMessage: vi.fn().mockResolvedValue({ ok: true }),
    onMessage: { addListener: vi.fn() },
    onInstalled: { addListener: vi.fn() },
  },
  storage: {
    local: {
      get: vi.fn().mockResolvedValue({}),
      set: vi.fn(),
    },
  },
  tabs: {
    query: vi.fn().mockResolvedValue([]),
    captureVisibleTab: vi.fn(),
    onUpdated: { addListener: vi.fn() },
    onActivated: { addListener: vi.fn() },
    sendMessage: vi.fn(),
    update: vi.fn(),
  },
  commands: {
    onCommand: { addListener: vi.fn() },
  },
  action: {
    setBadgeText: vi.fn(),
    setBadgeBackgroundColor: vi.fn(),
  },
  alarms: {
    create: vi.fn(),
    clear: vi.fn((_name: string, cb?: Function) => {
      if (cb) cb();
      return Promise.resolve(true);
    }),
    onAlarm: { addListener: vi.fn() },
  },
  contextMenus: {
    create: vi.fn(),
    onClicked: { addListener: vi.fn() },
  },
  scripting: {
    executeScript: vi.fn(),
  },
  cookies: {
    getAll: vi.fn().mockResolvedValue([]),
  },
  windows: {
    get: vi.fn(),
    update: vi.fn(),
  },
};

vi.stubGlobal("chrome", chromeMock);

// jsdom stubs for APIs it doesn't implement
Element.prototype.scrollIntoView = vi.fn();
window.scrollTo = vi.fn() as any;

// Prevent real network calls from any module
vi.stubGlobal(
  "fetch",
  vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve([]),
    text: () => Promise.resolve(""),
  })
);

