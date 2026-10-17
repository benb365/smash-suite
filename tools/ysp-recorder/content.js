(() => {
  if (window.__YSP_HLS_CONTENT_LOADED__) {
    return;
  }
  window.__YSP_HLS_CONTENT_LOADED__ = true;

  const state = {
    selectedTarget: null,
    pickerActive: false,
    recorder: null,
    lastRecordingSnapshot: null
  };

  function sendRecordingEvent(event) {
    state.lastRecordingSnapshot = event.snapshot || state.lastRecordingSnapshot;
    chrome.runtime.sendMessage({
      type: "YSP_RECORDING_EVENT",
      event
    });
  }

  function cssPath(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }

    if (element.id) {
      return `#${CSS.escape(element.id)}`;
    }

    const parts = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 4) {
      let part = current.localName;
      if (!part) {
        break;
      }

      const classNames = [...current.classList].slice(0, 2);
      if (classNames.length > 0) {
        part += `.${classNames.map((name) => CSS.escape(name)).join(".")}`;
      }

      const parent = current.parentElement;
      if (parent) {
        const siblings = [...parent.children].filter((child) => child.localName === current.localName);
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
        }
      }

      parts.unshift(part);
      current = parent;
    }

    return parts.join(" > ");
  }

  function getElementSummary(element) {
    const rect = element.getBoundingClientRect();
    const video = element.matches("video")
      ? element
      : element.querySelector("video") || element.closest("video");

    return {
      tagName: element.tagName.toLowerCase(),
      selector: cssPath(element),
      text: (element.getAttribute("aria-label") || element.getAttribute("title") || "").slice(0, 120),
      rect: {
        x: Math.round(rect.left + window.scrollX),
        y: Math.round(rect.top + window.scrollY),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      },
      video: video
        ? {
            currentSrc: video.currentSrc || video.src || "",
            paused: video.paused,
            duration: Number.isFinite(video.duration) ? video.duration : null,
            width: video.videoWidth || 0,
            height: video.videoHeight || 0
          }
        : null
    };
  }

  function startPlayerPicker() {
    if (state.pickerActive) {
      return Promise.reject(new Error("Picker is already active."));
    }

    state.pickerActive = true;

    return new Promise((resolve) => {
      const outline = document.createElement("div");
      const label = document.createElement("div");

      Object.assign(outline.style, {
        position: "fixed",
        zIndex: "2147483647",
        border: "2px solid #1a73e8",
        background: "rgba(26, 115, 232, 0.12)",
        pointerEvents: "none",
        display: "none",
        boxSizing: "border-box"
      });

      Object.assign(label.style, {
        position: "fixed",
        zIndex: "2147483647",
        padding: "6px 8px",
        borderRadius: "4px",
        background: "#1a73e8",
        color: "#fff",
        font: "12px/1.4 -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
        pointerEvents: "none",
        display: "none",
        maxWidth: "360px"
      });

      label.textContent = "Click the target player area. Press Esc to cancel.";
      document.documentElement.append(outline, label);

      let currentElement = null;

      const cleanup = () => {
        state.pickerActive = false;
        outline.remove();
        label.remove();
        document.removeEventListener("mousemove", onMouseMove, true);
        document.removeEventListener("click", onClick, true);
        document.removeEventListener("keydown", onKeyDown, true);
      };

      const updateOutline = (element, event) => {
        if (!element || element === document.documentElement || element === document.body) {
          return;
        }

        const rect = element.getBoundingClientRect();
        currentElement = element;

        Object.assign(outline.style, {
          display: "block",
          left: `${Math.max(0, rect.left)}px`,
          top: `${Math.max(0, rect.top)}px`,
          width: `${Math.max(1, rect.width)}px`,
          height: `${Math.max(1, rect.height)}px`
        });

        Object.assign(label.style, {
          display: "block",
          left: `${Math.min(window.innerWidth - 260, event.clientX + 12)}px`,
          top: `${Math.min(window.innerHeight - 34, event.clientY + 12)}px`
        });

        label.textContent = `${element.tagName.toLowerCase()} ${Math.round(rect.width)}x${Math.round(rect.height)}`;
      };

      const onMouseMove = (event) => {
        const element = document.elementFromPoint(event.clientX, event.clientY);
        if (element && element !== outline && element !== label) {
          updateOutline(element, event);
        }
      };

      const onClick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        cleanup();

        const element = currentElement || document.elementFromPoint(event.clientX, event.clientY);
        if (!element) {
          resolve({ ok: false, error: "No element was selected." });
          return;
        }

        state.selectedTarget = getElementSummary(element);
        resolve({ ok: true, target: state.selectedTarget });
      };

      const onKeyDown = (event) => {
        if (event.key !== "Escape") {
          return;
        }

        event.preventDefault();
        event.stopPropagation();
        cleanup();
        resolve({ ok: false, error: "Picker cancelled." });
      };

      document.addEventListener("mousemove", onMouseMove, true);
      document.addEventListener("click", onClick, true);
      document.addEventListener("keydown", onKeyDown, true);
    });
  }

  async function startRecording(message) {
    if (state.recorder && state.recorder.status === "recording") {
      throw new Error("A recording is already running.");
    }

    if (!message.source?.url) {
      throw new Error("No HLS source was selected.");
    }

    state.recorder = new window.HlsRecorder({
      source: message.source,
      chunkDurationMs: message.config?.chunkDurationMs,
      pollIntervalMs: message.config?.pollIntervalMs,
      retryCount: message.config?.retryCount,
      onEvent: sendRecordingEvent
    });

    return state.recorder.start();
  }

  async function stopRecording() {
    if (!state.recorder) {
      throw new Error("No active recorder.");
    }

    const result = await state.recorder.stopAndSave();
    state.recorder = null;
    return result;
  }

  async function discardRecording() {
    if (!state.recorder) {
      return { ok: true };
    }

    await state.recorder.discard();
    state.recorder = null;
    return { ok: true };
  }

  function getContentState() {
    return {
      selectedTarget: state.selectedTarget,
      recording: state.lastRecordingSnapshot
    };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    const respond = async () => {
      switch (message.type) {
        case "YSP_PICK_PLAYER":
          return startPlayerPicker();
        case "YSP_START_RECORDING":
          return {
            ok: true,
            snapshot: await startRecording(message)
          };
        case "YSP_STOP_RECORDING":
          return {
            ok: true,
            snapshot: await stopRecording()
          };
        case "YSP_DISCARD_RECORDING":
          return discardRecording();
        case "YSP_GET_CONTENT_STATE":
          return {
            ok: true,
            state: getContentState()
          };
        default:
          return undefined;
      }
    };

    respond()
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({
        ok: false,
        error: error.message || String(error)
      }));

    return true;
  });
})();
