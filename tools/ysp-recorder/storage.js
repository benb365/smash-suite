(() => {
  if (window.__YSP_HLS_STORAGE_LOADED__) {
    return;
  }
  window.__YSP_HLS_STORAGE_LOADED__ = true;

  const DB_NAME = "ysp-hls-recorder";
  const DB_VERSION = 1;
  const STORE_NAME = "chunks";

  function padSequence(sequence) {
    return String(sequence).padStart(6, "0");
  }

  function requestToPromise(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("IndexedDB request failed."));
    });
  }

  function openChunkDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Unable to open IndexedDB."));
    });
  }

  class HlsChunkStorage {
    constructor(sessionId) {
      this.sessionId = sessionId;
      this.mode = "none";
      this.root = null;
      this.sessionDirectory = null;
      this.db = null;
      this.chunks = [];
      this.active = null;
    }

    async init() {
      if (navigator.storage?.getDirectory) {
        try {
          this.root = await navigator.storage.getDirectory();
          const baseDirectory = await this.root.getDirectoryHandle("ysp-hls-recorder", {
            create: true
          });

          try {
            await baseDirectory.removeEntry(this.sessionId, { recursive: true });
          } catch (_error) {
            // It is fine when the session directory does not exist.
          }

          this.sessionDirectory = await baseDirectory.getDirectoryHandle(this.sessionId, {
            create: true
          });
          this.mode = "opfs";
          return;
        } catch (_error) {
          // Fall back to IndexedDB below.
        }
      }

      this.db = await openChunkDb();
      this.mode = "idb";
    }

    getMode() {
      return this.mode;
    }

    async beginChunk(sequence) {
      if (this.active) {
        throw new Error("A chunk is already open.");
      }

      const name = `chunk_${padSequence(sequence)}.ts`;
      this.active = {
        sequence,
        name,
        key: `${this.sessionId}:${name}`,
        sizeBytes: 0,
        durationMs: 0,
        parts: [],
        handle: null,
        writable: null
      };

      if (this.mode === "opfs") {
        const handle = await this.sessionDirectory.getFileHandle(name, { create: true });
        this.active.handle = handle;
        this.active.writable = await handle.createWritable();
      }
    }

    async appendToChunk(part, durationMs = 0) {
      if (!this.active) {
        throw new Error("No active chunk is open.");
      }

      const blob = part instanceof Blob
        ? part
        : new Blob([part], { type: "video/mp2t" });

      if (this.mode === "opfs") {
        await this.active.writable.write(blob);
      } else {
        this.active.parts.push(blob);
      }

      this.active.sizeBytes += blob.size;
      this.active.durationMs += durationMs;
    }

    async finishChunk(extra = {}) {
      if (!this.active) {
        return null;
      }

      const chunk = this.active;
      this.active = null;

      if (chunk.sizeBytes === 0) {
        if (chunk.writable) {
          await chunk.writable.close();
        }
        return null;
      }

      if (this.mode === "opfs") {
        await chunk.writable.close();
      } else {
        const blob = new Blob(chunk.parts, { type: "video/mp2t" });
        await this.putIndexedDb(chunk.key, blob);
        chunk.parts = [];
      }

      const meta = {
        sequence: chunk.sequence,
        name: chunk.name,
        key: chunk.key,
        sizeBytes: chunk.sizeBytes,
        durationMs: chunk.durationMs,
        handle: chunk.handle,
        ...extra
      };

      this.chunks.push(meta);
      return meta;
    }

    async putIndexedDb(key, value) {
      const transaction = this.db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      await requestToPromise(store.put(value, key));
    }

    async getIndexedDb(key) {
      const transaction = this.db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      return requestToPromise(store.get(key));
    }

    async deleteIndexedDb(key) {
      const transaction = this.db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      await requestToPromise(store.delete(key));
    }

    async buildFinalBlob() {
      const parts = [];
      const chunks = [...this.chunks].sort((a, b) => a.sequence - b.sequence);

      for (const chunk of chunks) {
        if (this.mode === "opfs") {
          parts.push(await chunk.handle.getFile());
        } else {
          parts.push(await this.getIndexedDb(chunk.key));
        }
      }

      return new Blob(parts, { type: "video/mp2t" });
    }

    async clear() {
      if (this.active?.writable) {
        try {
          await this.active.writable.close();
        } catch (_error) {
          // The stream may already be closed.
        }
      }

      if (this.mode === "opfs" && this.root) {
        try {
          const baseDirectory = await this.root.getDirectoryHandle("ysp-hls-recorder", {
            create: true
          });
          await baseDirectory.removeEntry(this.sessionId, { recursive: true });
        } catch (_error) {
          // Cleanup best-effort.
        }
      }

      if (this.mode === "idb") {
        await Promise.all(this.chunks.map((chunk) => this.deleteIndexedDb(chunk.key)));
      }

      this.active = null;
      this.chunks = [];
    }
  }

  window.HlsChunkStorage = HlsChunkStorage;
})();
