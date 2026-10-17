const inspectedTabId = chrome.devtools.inspectedWindow.tabId;
const port = chrome.runtime.connect({ name: "ysp-hls-panel" });

const elements = {
  connectionStatus: document.getElementById("connectionStatus"),
  pickPlayerButton: document.getElementById("pickPlayerButton"),
  bindSourceButton: document.getElementById("bindSourceButton"),
  refreshSourcesButton: document.getElementById("refreshSourcesButton"),
  copyUrlButton: document.getElementById("copyUrlButton"),
  copyCurlButton: document.getElementById("copyCurlButton"),
  startButton: document.getElementById("startButton"),
  stopButton: document.getElementById("stopButton"),
  clearLogButton: document.getElementById("clearLogButton"),
  targetSummary: document.getElementById("targetSummary"),
  sourceList: document.getElementById("sourceList"),
  recordingStatus: document.getElementById("recordingStatus"),
  elapsedMetric: document.getElementById("elapsedMetric"),
  chunkMetric: document.getElementById("chunkMetric"),
  chunksMetric: document.getElementById("chunksMetric"),
  sizeMetric: document.getElementById("sizeMetric"),
  log: document.getElementById("log")
};

const state = {
  candidates: [],
  selectedCandidateId: "",
  selectedTarget: null,
  recording: null,
  isRecording: false,
  pollTimer: null
};

function log(message) {
  const line = document.createElement("div");
  line.className = "log-line";
  line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  elements.log.prepend(line);
}

function formatBytes(bytes) {
  if (!bytes) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let index = 0;

  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.floor((ms || 0) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (value) => String(value).padStart(2, "0");

  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(seconds)}`;
  }

  return `${pad(minutes)}:${pad(seconds)}`;
}

function escapeShell(value) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function selectedCandidate() {
  return state.candidates.find((candidate) => candidate.id === state.selectedCandidateId) || null;
}

function setConnection(ok, text) {
  elements.connectionStatus.textContent = text;
  elements.connectionStatus.classList.toggle("ok", ok);
}

function renderTarget() {
  if (!state.selectedTarget) {
    elements.targetSummary.className = "summary empty";
    elements.targetSummary.textContent = "No player area selected.";
    return;
  }

  const target = state.selectedTarget;
  const rect = target.rect;
  elements.targetSummary.className = "summary";
  elements.targetSummary.innerHTML = "";

  const lines = [
    `${target.tagName} ${rect.width}x${rect.height} at (${rect.x}, ${rect.y})`,
    `Selector: ${target.selector || "(unavailable)"}`,
    target.video
      ? `Video: ${target.video.width || "?"}x${target.video.height || "?"}, ${target.video.paused ? "paused" : "playing"}`
      : "Video: no nested video element found"
  ];

  for (const item of lines) {
    const div = document.createElement("div");
    div.textContent = item;
    elements.targetSummary.appendChild(div);
  }
}

function renderSources() {
  elements.sourceList.innerHTML = "";

  if (state.candidates.length === 0) {
    const empty = document.createElement("div");
    empty.className = "summary empty";
    empty.textContent = "No m3u8 candidate captured for this tab yet.";
    elements.sourceList.appendChild(empty);
  }

  for (const candidate of state.candidates) {
    const item = document.createElement("label");
    item.className = `source-item ${candidate.id === state.selectedCandidateId ? "selected" : ""}`;

    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "source";
    radio.value = candidate.id;
    radio.checked = candidate.id === state.selectedCandidateId;
    radio.addEventListener("change", () => {
      state.selectedCandidateId = candidate.id;
      renderSources();
      updateButtons();
    });

    const content = document.createElement("div");
    const title = document.createElement("div");
    title.className = "source-title";
    title.textContent = `${candidate.quality || "HLS"} - ${candidate.host}`;

    const meta = document.createElement("div");
    meta.className = "source-meta";
    meta.textContent = `Seen ${candidate.hitCount || 1}x, last ${new Date(candidate.lastSeenAt || candidate.capturedAt).toLocaleTimeString()}`;

    const url = document.createElement("div");
    url.className = "source-url";
    url.textContent = candidate.url;

    content.append(title, meta, url);
    item.append(radio, content);
    elements.sourceList.appendChild(item);
  }

  updateButtons();
}

function renderRecording(snapshot = state.recording) {
  const data = snapshot || {};
  elements.elapsedMetric.textContent = formatDuration(data.elapsedMs || 0);

  const chunkProgress = data.chunkDurationMs
    ? Math.min(100, Math.round(((data.activeChunkDurationMs || 0) / data.chunkDurationMs) * 100))
    : 0;
  elements.chunkMetric.textContent = `${chunkProgress}%`;
  elements.chunksMetric.textContent = String(data.chunkCount || 0);
  elements.sizeMetric.textContent = formatBytes(data.totalBytes || data.finalBytes || 0);

  if (!snapshot) {
    elements.recordingStatus.className = "summary empty";
    elements.recordingStatus.textContent = "Idle.";
    return;
  }

  elements.recordingStatus.className = "summary";
  elements.recordingStatus.textContent = [
    `Status: ${data.status}`,
    `Segments: ${data.downloadedSegments || 0} downloaded, ${data.failedSegments || 0} failed`,
    `Output: ${data.fileName || "(pending)"}`,
    data.lastError ? `Last error: ${data.lastError}` : ""
  ].filter(Boolean).join("\n");
}

function updateButtons() {
  const hasSource = Boolean(selectedCandidate());
  elements.copyUrlButton.disabled = !hasSource;
  elements.copyCurlButton.disabled = !hasSource;
  elements.startButton.disabled = !hasSource || !state.selectedTarget || state.isRecording;
  elements.stopButton.disabled = !state.isRecording;
}

function buildCurlCommand(candidate) {
  const headers = candidate.headers || {};
  const parts = ["curl -L"];

  for (const [name, value] of Object.entries(headers)) {
    if (!value || value === "[redacted]") {
      continue;
    }
    parts.push(`  -H ${escapeShell(`${name}: ${value}`)}`);
  }

  parts.push(`  ${escapeShell(candidate.url)}`);
  return parts.join(" \\\n");
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

function sendTabMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(inspectedTabId, message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(response);
    });
  });
}

function injectContentScripts() {
  return new Promise((resolve, reject) => {
    chrome.scripting.executeScript(
      {
        target: { tabId: inspectedTabId },
        files: ["storage.js", "recorder.js", "content.js"]
      },
      () => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }
        resolve();
      }
    );
  });
}

async function sendToContent(message) {
  try {
    return await sendTabMessage(message);
  } catch (_error) {
    await injectContentScripts();
    return sendTabMessage(message);
  }
}

async function loadContentState() {
  try {
    const response = await sendToContent({ type: "YSP_GET_CONTENT_STATE" });
    if (response?.ok) {
      state.selectedTarget = response.state.selectedTarget || state.selectedTarget;
      state.recording = response.state.recording || state.recording;
      renderTarget();
      renderRecording();
    }
  } catch (error) {
    log(`Content script unavailable: ${error.message}`);
  }
}

elements.pickPlayerButton.addEventListener("click", async () => {
  log("Starting player picker.");
  const response = await sendToContent({ type: "YSP_PICK_PLAYER" });
  if (!response?.ok) {
    log(response?.error || "Player picker cancelled.");
    return;
  }

  state.selectedTarget = response.target;
  renderTarget();
  updateButtons();
  log("Player area selected.");
});

elements.bindSourceButton.addEventListener("click", () => {
  state.selectedCandidateId = "";
  port.postMessage({ type: "candidates:clear", tabId: inspectedTabId });
  log("Source binding reset. Replay or refresh the selected player now.");
});

elements.refreshSourcesButton.addEventListener("click", () => {
  port.postMessage({ type: "candidates:get", tabId: inspectedTabId });
});

elements.copyUrlButton.addEventListener("click", async () => {
  const candidate = selectedCandidate();
  if (!candidate) {
    return;
  }

  await copyText(candidate.url);
  log("Copied m3u8 URL.");
});

elements.copyCurlButton.addEventListener("click", async () => {
  const candidate = selectedCandidate();
  if (!candidate) {
    return;
  }

  await copyText(buildCurlCommand(candidate));
  log("Copied curl command.");
});

elements.startButton.addEventListener("click", async () => {
  const candidate = selectedCandidate();
  if (!candidate) {
    return;
  }

  const response = await sendToContent({
    type: "YSP_START_RECORDING",
    source: candidate,
    config: {
      chunkDurationMs: 5 * 60 * 1000,
      pollIntervalMs: 2000,
      retryCount: 3
    }
  });

  if (!response?.ok) {
    log(`Start failed: ${response?.error || "unknown error"}`);
    return;
  }

  state.isRecording = true;
  state.recording = response.snapshot;
  renderRecording();
  updateButtons();
  log("Recording started.");
});

elements.stopButton.addEventListener("click", async () => {
  log("Stopping recorder and merging chunks.");
  const response = await sendToContent({ type: "YSP_STOP_RECORDING" });

  if (!response?.ok) {
    log(`Stop failed: ${response?.error || "unknown error"}`);
    return;
  }

  state.isRecording = false;
  state.recording = response.snapshot;
  renderRecording();
  updateButtons();
  log("Final TS download started. Temporary chunks will be cleaned shortly.");
});

elements.clearLogButton.addEventListener("click", () => {
  elements.log.innerHTML = "";
});

port.onMessage.addListener((message) => {
  if (message.type === "candidates:update") {
    state.candidates = message.candidates || [];

    if (!selectedCandidate() && state.candidates.length === 1) {
      state.selectedCandidateId = state.candidates[0].id;
    }

    renderSources();
    return;
  }

  if (message.type === "recording:event") {
    state.recording = message.event.snapshot;
    state.isRecording = ["recording", "stopping", "merging"].includes(state.recording?.status);
    renderRecording();
    updateButtons();

    if (message.event.type === "warning") {
      log(`Warning: ${message.event.payload?.message || "unknown warning"}`);
    } else if (message.event.type === "chunk:finished") {
      log(`Chunk finished: ${message.event.payload?.chunk?.name || "chunk"}`);
    } else if (message.event.type === "complete") {
      state.isRecording = false;
      log(`Complete: ${message.event.payload?.fileName || "final TS"}`);
    }
  }
});

port.postMessage({ type: "panel:init", tabId: inspectedTabId });
setConnection(true, `Tab ${inspectedTabId}`);
renderTarget();
renderSources();
renderRecording();
loadContentState();
