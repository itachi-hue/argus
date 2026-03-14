import type { ArgusInternalMessage, ArgusSettings } from "../types";

const serverUrlInput = document.getElementById("server-url") as HTMLInputElement;
const authTokenInput = document.getElementById("auth-token") as HTMLInputElement;
const captureLogsCheck = document.getElementById("capture-logs") as HTMLInputElement;
const captureNetworkCheck = document.getElementById("capture-network") as HTMLInputElement;
const saveBtn = document.getElementById("save-btn") as HTMLButtonElement;
const statusDiv = document.getElementById("status") as HTMLDivElement;
const statusText = document.getElementById("status-text") as HTMLSpanElement;

// Load saved settings
async function loadSettings() {
  const stored = await chrome.storage.local.get("argus_settings");
  const s = stored.argus_settings || {};
  serverUrlInput.value = s.server_url || "http://127.0.0.1:42777";
  authTokenInput.value = s.auth_token || "";
  captureLogsCheck.checked = s.capture_console_logs !== false;
  captureNetworkCheck.checked = s.capture_network !== false;
}

async function checkConnection() {
  const response = await chrome.runtime.sendMessage({
    type: "get-status",
  } as ArgusInternalMessage);

  if (response?.connected) {
    statusDiv.className = "status connected";
    statusText.textContent = "Connected";
  } else {
    statusDiv.className = "status disconnected";
    statusText.textContent = "Disconnected";
  }
}

saveBtn.addEventListener("click", async () => {
  const newSettings: Partial<ArgusSettings> = {
    server_url: serverUrlInput.value.replace(/\/$/, ""),
    auth_token: authTokenInput.value,
    capture_console_logs: captureLogsCheck.checked,
    capture_network: captureNetworkCheck.checked,
  };

  await chrome.runtime.sendMessage({
    type: "update-settings",
    payload: newSettings,
  } as ArgusInternalMessage);

  // Re-check connection with new settings
  setTimeout(checkConnection, 500);
});

loadSettings().then(checkConnection);

