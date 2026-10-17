const MAX_CANDIDATES_PER_TAB = 50;
const panelPortsByTab = new Map();
const candidatesByTab = new Map();

const HEADER_ALLOWLIST = new Set([
  "accept",
  "accept-language",
  "origin",
  "referer",
  "user-agent"
]);

function storageKey(tabId) {
  return `ysp:hls:candidates:${tabId}`;
}

function isM3u8Url(url) {
  try {
    const parsed = new URL(url);
    return parsed.pathname.toLowerCase().includes(".m3u8");
  } catch (_error) {
    return false;
  }
}

function qualityFromUrl(url) {
  const lower = url.toLowerCase();
  if (lower.includes("fhd") || lower.includes("1080")) {
    return "FHD";
  }
  if (lower.includes("shd") || lower.includes("uhd") || lower.includes("4k")) {
    return "UHD";
  }
  if (lower.includes("hd") || lower.includes("720")) {
    return "HD";
  }
  if (lower.includes("sd") || lower.includes("540") || lower.includes("480")) {
    return "SD";
  }
  return "HLS";
}

function redactHeaderValue(name, value) {
  if (name.toLowerCase() === "cookie") {
    return "[redacted]";
  }
  return value;
}

function sanitizeHeaders(requestHeaders = []) {
  const headers = {};

  for (const header of requestHeaders) {
    if (!header.name) {
      continue;
    }

    const lowerName = header.name.toLowerCase();
    if (!HEADER_ALLOWLIST.has(lowerName)) {
      continue;
    }

    headers[header.name] = redactHeaderValue(header.name, header.value || "");
  }

  return headers;
}

async function getCandidates(tabId) {
  if (candidatesByTab.has(tabId)) {
    return candidatesByTab.get(tabId);
  }

  if (!chrome.storage?.session) {
    return [];
  }

  const stored = await chrome.storage.session.get(storageKey(tabId));
  const candidates = stored[storageKey(tabId)] || [];
  candidatesByTab.set(tabId, candidates);
  return candidates;
}

async function setCandidates(tabId, candidates) {
  candidatesByTab.set(tabId, candidates);

  if (chrome.storage?.session) {
    await chrome.storage.session.set({
      [storageKey(tabId)]: candidates
    });
  }
}

function broadcastToPanels(tabId, message) {
  const ports = panelPortsByTab.get(tabId);
  if (!ports) {
    return;
  }

  for (const port of ports) {
    try {
      port.postMessage(message);
    } catch (_error) {
      // Dead ports are removed by onDisconnect.
    }
  }
}

async function publishCandidates(tabId) {
  const candidates = await getCandidates(tabId);
  broadcastToPanels(tabId, {
    type: "candidates:update",
    candidates
  });
}

async function upsertCandidate(details, requestHeaders) {
  if (details.tabId < 0 || !isM3u8Url(details.url)) {
    return;
  }

  const tabId = details.tabId;
  const candidates = await getCandidates(tabId);
  const headers = requestHeaders ? sanitizeHeaders(requestHeaders) : undefined;
  const existingIndex = candidates.findIndex((candidate) => candidate.url === details.url);
  const nowIso = new Date().toISOString();

  if (existingIndex >= 0) {
    const existing = candidates[existingIndex];
    const updated = {
      ...existing,
      lastSeenAt: nowIso,
      hitCount: (existing.hitCount || 1) + 1,
      requestId: details.requestId || existing.requestId,
      headers: headers ? { ...existing.headers, ...headers } : existing.headers
    };

    candidates.splice(existingIndex, 1);
    candidates.unshift(updated);
  } else {
    const parsed = new URL(details.url);
    candidates.unshift({
      id: `${details.requestId || "m3u8"}:${Date.now()}:${Math.random().toString(36).slice(2)}`,
      tabId,
      requestId: details.requestId || "",
      url: details.url,
      method: details.method || "GET",
      host: parsed.host,
      quality: qualityFromUrl(details.url),
      capturedAt: nowIso,
      lastSeenAt: nowIso,
      hitCount: 1,
      initiator: details.initiator || details.originUrl || "",
      headers: headers || {}
    });
  }

  await setCandidates(tabId, candidates.slice(0, MAX_CANDIDATES_PER_TAB));
  await publishCandidates(tabId);
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    void upsertCandidate(details);
  },
  { urls: ["<all_urls>"] }
);

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    void upsertCandidate(details, details.requestHeaders || []);
  },
  { urls: ["<all_urls>"] },
  ["requestHeaders", "extraHeaders"]
);

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "ysp-hls-panel") {
    return;
  }

  let tabId = null;

  port.onMessage.addListener(async (message) => {
    if (message.type === "panel:init") {
      tabId = message.tabId;

      if (!panelPortsByTab.has(tabId)) {
        panelPortsByTab.set(tabId, new Set());
      }
      panelPortsByTab.get(tabId).add(port);

      port.postMessage({
        type: "candidates:update",
        candidates: await getCandidates(tabId)
      });
      return;
    }

    if (message.type === "candidates:get") {
      port.postMessage({
        type: "candidates:update",
        candidates: await getCandidates(message.tabId)
      });
      return;
    }

    if (message.type === "candidates:clear") {
      await setCandidates(message.tabId, []);
      await publishCandidates(message.tabId);
    }
  });

  port.onDisconnect.addListener(() => {
    if (tabId === null) {
      return;
    }

    const ports = panelPortsByTab.get(tabId);
    if (!ports) {
      return;
    }

    ports.delete(port);
    if (ports.size === 0) {
      panelPortsByTab.delete(tabId);
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== "YSP_RECORDING_EVENT") {
    return;
  }

  const tabId = sender.tab?.id ?? message.tabId;
  if (typeof tabId !== "number") {
    return;
  }

  broadcastToPanels(tabId, {
    type: "recording:event",
    event: message.event
  });
});
