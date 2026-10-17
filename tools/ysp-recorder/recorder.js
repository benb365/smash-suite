(() => {
  if (window.__YSP_HLS_RECORDER_LOADED__) {
    return;
  }
  window.__YSP_HLS_RECORDER_LOADED__ = true;

  const DEFAULT_POLL_INTERVAL_MS = 2000;
  const DEFAULT_CHUNK_DURATION_MS = 5 * 60 * 1000;
  const DEFAULT_RETRY_COUNT = 3;
  const DEFAULT_TIMEOUT_MS = 20000;

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function isoFileStamp(date) {
    const pad = (value) => String(value).padStart(2, "0");
    return [
      date.getFullYear(),
      pad(date.getMonth() + 1),
      pad(date.getDate()),
      "_",
      pad(date.getHours()),
      pad(date.getMinutes()),
      pad(date.getSeconds())
    ].join("");
  }

  function parseAttributeList(input) {
    const attributes = {};
    const pattern = /([A-Z0-9-]+)=("[^"]*"|[^,]*)/gi;
    let match = pattern.exec(input);

    while (match) {
      const rawValue = match[2];
      attributes[match[1].toUpperCase()] = rawValue.startsWith("\"")
        ? rawValue.slice(1, -1)
        : rawValue;
      match = pattern.exec(input);
    }

    return attributes;
  }

  function parsePlaylist(text, baseUrl) {
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    const segments = [];
    const variants = [];
    let pendingDurationMs = 3000;
    let pendingVariant = null;
    let hasKey = false;

    for (const line of lines) {
      if (line.startsWith("#EXT-X-KEY")) {
        hasKey = true;
        continue;
      }

      if (line.startsWith("#EXTINF:")) {
        const rawDuration = line.slice("#EXTINF:".length).split(",")[0];
        const durationSeconds = Number.parseFloat(rawDuration);
        pendingDurationMs = Number.isFinite(durationSeconds)
          ? Math.max(0, Math.round(durationSeconds * 1000))
          : 3000;
        continue;
      }

      if (line.startsWith("#EXT-X-STREAM-INF:")) {
        pendingVariant = parseAttributeList(line.slice("#EXT-X-STREAM-INF:".length));
        continue;
      }

      if (line.startsWith("#")) {
        continue;
      }

      const absoluteUrl = new URL(line, baseUrl).href;

      if (pendingVariant || absoluteUrl.toLowerCase().includes(".m3u8")) {
        variants.push({
          url: absoluteUrl,
          bandwidth: Number.parseInt(pendingVariant?.BANDWIDTH || "0", 10) || 0,
          resolution: pendingVariant?.RESOLUTION || ""
        });
        pendingVariant = null;
        continue;
      }

      segments.push({
        url: absoluteUrl,
        durationMs: pendingDurationMs || 3000
      });
      pendingDurationMs = 3000;
    }

    return {
      hasKey,
      segments,
      variants
    };
  }

  async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      return await fetch(url, {
        ...options,
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function fetchWithRetry(url, options, retryCount, timeoutMs) {
    let lastError = null;

    for (let attempt = 1; attempt <= retryCount; attempt += 1) {
      try {
        const response = await fetchWithTimeout(url, options, timeoutMs);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} ${response.statusText}`.trim());
        }
        return response;
      } catch (error) {
        lastError = error;
        if (attempt < retryCount) {
          await sleep(Math.min(1000 * attempt, 3000));
        }
      }
    }

    throw lastError || new Error("Request failed.");
  }

  class HlsRecorder {
    constructor(options) {
      this.source = options.source;
      this.chunkDurationMs = options.chunkDurationMs || DEFAULT_CHUNK_DURATION_MS;
      this.pollIntervalMs = options.pollIntervalMs || DEFAULT_POLL_INTERVAL_MS;
      this.retryCount = options.retryCount || DEFAULT_RETRY_COUNT;
      this.timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
      this.onEvent = options.onEvent || (() => {});
      this.storage = null;
      this.playlistUrl = this.source.url;
      this.seenSegments = new Set();
      this.stopRequested = false;
      this.status = "idle";
      this.loopPromise = null;
      this.startedAt = null;
      this.lastError = "";
      this.chunkSequence = 0;
      this.activeChunkStarted = false;
      this.activeChunkDurationMs = 0;
      this.activeChunkBytes = 0;
      this.totalDurationMs = 0;
      this.totalBytes = 0;
      this.downloadedSegments = 0;
      this.failedSegments = 0;
      this.finalFileName = "";
    }

    async start() {
      if (this.status !== "idle") {
        throw new Error("Recorder is already running.");
      }

      const sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      this.storage = new window.HlsChunkStorage(sessionId);
      await this.storage.init();

      this.startedAt = new Date();
      this.finalFileName = `ysp_${isoFileStamp(this.startedAt)}.ts`;
      this.status = "recording";
      this.emit("started", {
        storageMode: this.storage.getMode(),
        fileName: this.finalFileName
      });

      this.loopPromise = this.runLoop();
      return this.snapshot();
    }

    async stopAndSave() {
      if (this.status !== "recording" && this.status !== "error") {
        throw new Error("Recorder is not running.");
      }

      this.stopRequested = true;
      this.status = "stopping";
      this.emit("status", { message: "Stopping and finalizing chunks." });

      if (this.loopPromise) {
        await this.loopPromise;
      }

      await this.finishActiveChunk();

      if (this.storage.chunks.length === 0) {
        await this.storage.clear();
        this.status = "idle";
        throw new Error("No media chunks were recorded.");
      }

      this.status = "merging";
      this.emit("status", { message: "Merging recorded chunks." });

      const finalBlob = await this.storage.buildFinalBlob();
      this.downloadBlob(finalBlob, this.finalFileName);

      const chunkCount = this.storage.chunks.length;
      const cleanupStorage = this.storage;
      window.setTimeout(() => {
        void cleanupStorage.clear();
      }, 60000);

      this.status = "complete";
      this.emit("complete", {
        fileName: this.finalFileName,
        finalBytes: finalBlob.size,
        chunkCount
      });

      return this.snapshot({
        finalBytes: finalBlob.size,
        chunkCount
      });
    }

    async discard() {
      this.stopRequested = true;
      if (this.loopPromise) {
        await this.loopPromise;
      }
      if (this.storage) {
        await this.storage.clear();
      }
      this.status = "idle";
      this.emit("discarded", {});
    }

    async runLoop() {
      while (!this.stopRequested) {
        try {
          await this.pollOnce();
          this.lastError = "";
        } catch (error) {
          this.lastError = error.message || String(error);
          this.emit("warning", {
            message: this.lastError
          });

          if (String(this.lastError).includes("Encrypted HLS")) {
            this.status = "error";
            this.stopRequested = true;
          }
        }

        if (!this.stopRequested) {
          await sleep(this.pollIntervalMs);
        }
      }
    }

    async pollOnce() {
      let playlistText = await this.fetchText(this.playlistUrl);
      let parsed = parsePlaylist(playlistText, this.playlistUrl);

      if (parsed.hasKey) {
        throw new Error("Encrypted HLS with EXT-X-KEY is not supported in v1.");
      }

      if (parsed.segments.length === 0 && parsed.variants.length > 0) {
        const variant = [...parsed.variants].sort((a, b) => b.bandwidth - a.bandwidth)[0];
        this.playlistUrl = variant.url;
        playlistText = await this.fetchText(this.playlistUrl);
        parsed = parsePlaylist(playlistText, this.playlistUrl);

        if (parsed.hasKey) {
          throw new Error("Encrypted HLS with EXT-X-KEY is not supported in v1.");
        }
      }

      for (const segment of parsed.segments) {
        if (this.stopRequested) {
          break;
        }

        if (this.seenSegments.has(segment.url)) {
          continue;
        }

        this.seenSegments.add(segment.url);
        await this.downloadSegment(segment);
      }
    }

    async fetchText(url) {
      const response = await fetchWithRetry(
        url,
        {
          cache: "no-store",
          credentials: "include"
        },
        this.retryCount,
        this.timeoutMs
      );
      return response.text();
    }

    async downloadSegment(segment) {
      try {
        const response = await fetchWithRetry(
          segment.url,
          {
            cache: "no-store",
            credentials: "include"
          },
          this.retryCount,
          this.timeoutMs
        );
        const blob = await response.blob();
        await this.appendSegment(blob, segment.durationMs);
        this.downloadedSegments += 1;
        this.totalBytes += blob.size;
        this.totalDurationMs += segment.durationMs;
        this.emit("progress", this.snapshot());
      } catch (error) {
        this.failedSegments += 1;
        this.emit("warning", {
          message: `Segment failed: ${error.message || error}`,
          segmentUrl: segment.url
        });
      }
    }

    async appendSegment(blob, durationMs) {
      if (!this.activeChunkStarted) {
        await this.beginChunk();
      }

      await this.storage.appendToChunk(blob, durationMs);
      this.activeChunkDurationMs += durationMs;
      this.activeChunkBytes += blob.size;

      if (this.activeChunkDurationMs >= this.chunkDurationMs) {
        await this.finishActiveChunk();
      }
    }

    async beginChunk() {
      this.chunkSequence += 1;
      this.activeChunkDurationMs = 0;
      this.activeChunkBytes = 0;
      await this.storage.beginChunk(this.chunkSequence);
      this.activeChunkStarted = true;
      this.emit("chunk:started", this.snapshot());
    }

    async finishActiveChunk() {
      if (!this.activeChunkStarted) {
        return null;
      }

      const chunk = await this.storage.finishChunk({
        closedAt: new Date().toISOString()
      });

      this.activeChunkStarted = false;
      this.activeChunkDurationMs = 0;
      this.activeChunkBytes = 0;

      if (chunk) {
        this.emit("chunk:finished", {
          ...this.snapshot(),
          chunk
        });
      }

      return chunk;
    }

    downloadBlob(blob, fileName) {
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = fileName;
      link.rel = "noopener";
      link.style.display = "none";
      document.documentElement.appendChild(link);
      link.click();
      link.remove();

      window.setTimeout(() => {
        URL.revokeObjectURL(objectUrl);
      }, 60000);
    }

    snapshot(extra = {}) {
      return {
        status: this.status,
        playlistUrl: this.playlistUrl,
        startedAt: this.startedAt ? this.startedAt.toISOString() : "",
        elapsedMs: this.startedAt ? Date.now() - this.startedAt.getTime() : 0,
        totalDurationMs: this.totalDurationMs,
        totalBytes: this.totalBytes,
        downloadedSegments: this.downloadedSegments,
        failedSegments: this.failedSegments,
        activeChunkDurationMs: this.activeChunkDurationMs,
        activeChunkBytes: this.activeChunkBytes,
        chunkCount: this.storage ? this.storage.chunks.length : 0,
        nextChunkNumber: this.chunkSequence,
        chunkDurationMs: this.chunkDurationMs,
        lastError: this.lastError,
        fileName: this.finalFileName,
        ...extra
      };
    }

    emit(type, payload = {}) {
      this.onEvent({
        type,
        snapshot: this.snapshot(),
        payload,
        time: new Date().toISOString()
      });
    }
  }

  window.HlsRecorder = HlsRecorder;
})();
