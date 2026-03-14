import type { ArgusInternalMessage, ArgusSettings } from "../types";

// --- DOM elements ---
const statusDiv = document.getElementById("status") as HTMLDivElement;
const statusText = document.getElementById("status-text") as HTMLSpanElement;
const connectSection = document.getElementById("connect-section") as HTMLDivElement;
const connectedSection = document.getElementById("connected-section") as HTMLDivElement;

// Connect flow
const pairBtn = document.getElementById("pair-btn") as HTMLButtonElement;
const codeSection = document.getElementById("code-section") as HTMLDivElement;
const pairCodeInput = document.getElementById("pair-code") as HTMLInputElement;
const confirmBtn = document.getElementById("confirm-btn") as HTMLButtonElement;
const pairError = document.getElementById("pair-error") as HTMLParagraphElement;
const pasteBtn = document.getElementById("paste-btn") as HTMLButtonElement;

// Manual setup
const serverUrlInput = document.getElementById("server-url") as HTMLInputElement;
const authTokenInput = document.getElementById("auth-token") as HTMLInputElement;
const saveBtn = document.getElementById("save-btn") as HTMLButtonElement;

// Connected controls
const autoCaptureCheck = document.getElementById("auto-capture") as HTMLInputElement;
const captureLogsCheck = document.getElementById("capture-logs") as HTMLInputElement;
const captureNetworkCheck = document.getElementById("capture-network") as HTMLInputElement;
const captureIntervalInput = document.getElementById("capture-interval") as HTMLInputElement;
const maxScreenshotsInput = document.getElementById("max-screenshots") as HTMLInputElement;
const captureSettingsDiv = document.getElementById("capture-settings") as HTMLDivElement;
const disconnectBtn = document.getElementById("disconnect-btn") as HTMLButtonElement;

// --- State ---
function setStatus(state: "connected" | "disconnected" | "pairing", text: string) {
  statusDiv.className = `status ${state}`;
  statusText.textContent = text;
}

function showConnected() {
  connectSection.classList.add("hidden");
  connectedSection.classList.remove("hidden");
  setStatus("connected", "Connected");
}

function showDisconnected() {
  connectSection.classList.remove("hidden");
  connectedSection.classList.add("hidden");
  codeSection.classList.add("hidden");
  pairError.classList.add("hidden");
  setStatus("disconnected", "Disconnected");
}

// --- Load settings ---
async function loadSettings() {
  const stored = await chrome.storage.local.get("argus_settings");
  const s = stored.argus_settings || {};
  serverUrlInput.value = s.server_url || "http://127.0.0.1:42777";
  authTokenInput.value = s.auth_token || "";
  autoCaptureCheck.checked = s.auto_capture !== false;
  captureLogsCheck.checked = s.capture_console_logs !== false;
  captureNetworkCheck.checked = s.capture_network !== false;
  captureIntervalInput.value = String(s.capture_interval_s || 30);
  maxScreenshotsInput.value = String(s.max_screenshots || 15);
  captureSettingsDiv.style.display = autoCaptureCheck.checked ? "" : "none";
}

// --- Check connection ---
async function checkConnection() {
  const response = await chrome.runtime.sendMessage({
    type: "get-status",
  } as ArgusInternalMessage);

  if (response?.connected) {
    showConnected();
  } else {
    showDisconnected();
  }
}

// --- One-click pairing flow ---
pairBtn.addEventListener("click", async () => {
  pairBtn.disabled = true;
  pairBtn.textContent = "Requesting code...";
  setStatus("pairing", "Waiting for code...");
  pairError.classList.add("hidden");

  const response = await chrome.runtime.sendMessage({
    type: "pair-request",
  } as ArgusInternalMessage);

  if (response?.ok) {
    codeSection.classList.remove("hidden");
    pairCodeInput.value = "";
    pairCodeInput.focus();
    setStatus("pairing", "Enter code from terminal");
  } else {
    pairError.textContent = response?.error || "Cannot reach server. Is it running?";
    pairError.classList.remove("hidden");
    setStatus("disconnected", "Server unreachable");
  }

  pairBtn.disabled = false;
  pairBtn.textContent = "Connect to Server";
});

// Handle code input — auto-submit when 4 digits entered
pairCodeInput.addEventListener("input", () => {
  // Only allow digits
  pairCodeInput.value = pairCodeInput.value.replace(/\D/g, "");
  if (pairCodeInput.value.length === 4) {
    submitCode();
  }
});

confirmBtn.addEventListener("click", submitCode);

pairCodeInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitCode();
});

async function submitCode() {
  const code = pairCodeInput.value.trim();
  if (code.length !== 4) {
    pairError.textContent = "Enter the 4-digit code from your terminal.";
    pairError.classList.remove("hidden");
    return;
  }

  pairError.classList.add("hidden");
  confirmBtn.disabled = true;
  setStatus("pairing", "Verifying...");

  const response = await chrome.runtime.sendMessage({
    type: "pair-confirm",
    payload: { code },
  } as ArgusInternalMessage);

  if (response?.ok) {
    // Save settings and show connected
    await chrome.runtime.sendMessage({
      type: "update-settings",
      payload: { auth_token: response.token },
    } as ArgusInternalMessage);
    showConnected();
  } else {
    pairError.textContent = response?.error || "Invalid code. Try again.";
    pairError.classList.remove("hidden");
    pairCodeInput.value = "";
    pairCodeInput.focus();
    setStatus("pairing", "Enter code from terminal");
  }

  confirmBtn.disabled = false;
}

// --- Paste from clipboard ---
pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (!text || text.trim().length < 10) {
      pairError.textContent = "Clipboard doesn't contain a valid token. Start the server first.";
      pairError.classList.remove("hidden");
      return;
    }

    // Save the token and try to connect
    await chrome.runtime.sendMessage({
      type: "update-settings",
      payload: { auth_token: text.trim() },
    } as ArgusInternalMessage);

    // Check if it works
    setTimeout(async () => {
      const status = await chrome.runtime.sendMessage({
        type: "get-status",
      } as ArgusInternalMessage);

      if (status?.connected) {
        showConnected();
      } else {
        pairError.textContent = "Token pasted but server not reachable. Check the server is running.";
        pairError.classList.remove("hidden");
      }
    }, 500);
  } catch {
    pairError.textContent = "Cannot read clipboard. Please paste the token manually below.";
    pairError.classList.remove("hidden");
  }
});

// --- Manual save ---
saveBtn.addEventListener("click", async () => {
  const newSettings: Partial<ArgusSettings> = {
    server_url: serverUrlInput.value.replace(/\/$/, ""),
    auth_token: authTokenInput.value,
  };

  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: newSettings,
  } as ArgusInternalMessage);

  setTimeout(checkConnection, 500);
});

// --- Toggle saves ---
autoCaptureCheck.addEventListener("change", async () => {
  captureSettingsDiv.style.display = autoCaptureCheck.checked ? "" : "none";
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { auto_capture: autoCaptureCheck.checked },
  } as ArgusInternalMessage);
});

captureIntervalInput.addEventListener("change", async () => {
  const val = Math.max(10, Math.min(300, parseInt(captureIntervalInput.value) || 30));
  captureIntervalInput.value = String(val);
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { capture_interval_s: val },
  } as ArgusInternalMessage);
});

maxScreenshotsInput.addEventListener("change", async () => {
  const val = Math.max(3, Math.min(50, parseInt(maxScreenshotsInput.value) || 15));
  maxScreenshotsInput.value = String(val);
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { max_screenshots: val },
  } as ArgusInternalMessage);
});

captureLogsCheck.addEventListener("change", async () => {
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { capture_console_logs: captureLogsCheck.checked },
  } as ArgusInternalMessage);
});

captureNetworkCheck.addEventListener("change", async () => {
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { capture_network: captureNetworkCheck.checked },
  } as ArgusInternalMessage);
});

// --- Disconnect ---
disconnectBtn.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: { auth_token: "" },
  } as ArgusInternalMessage);
  showDisconnected();
});

// --- Init ---
loadSettings().then(checkConnection);
