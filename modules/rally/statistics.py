"""Optional diagnostics: bounded aggregates, no algorithm decisions or frame history."""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path


class Statistics:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.seconds = defaultdict(float)
        self.counts = defaultdict(int)
        self.sources = []
        self.mps = []
        self._active = None

    @contextmanager
    def phase(self, name):
        if not self.enabled:
            yield
            return
        now = time.monotonic()
        parent = self._active
        if parent is not None:
            self.seconds[parent[0]] += now - parent[1]
        self._active = [name, now]
        try:
            yield
        finally:
            finished = time.monotonic()
            self.seconds[name] += finished - self._active[1]
            self._active = parent
            if parent is not None:
                parent[1] = finished

    def add(self, name, value=1):
        if self.enabled:
            self.counts[name] += value

    def timing(self, name, value):
        if self.enabled:
            self.seconds[name] += value

    def source(self, name, values):
        if self.enabled:
            self.sources.append(dict(pass_name=name, **values))
            self.add("decode_passes")
            self.add("frames_decoded", values["frames_decoded"])

    def write(self, path: Path, *, error=None):
        if self.enabled:
            path.write_text(json.dumps(dict(schema_version=1, error=error,
                primary_phases=["model_initialization", "video_observation", "people_and_trajectories",
                                "action_analysis", "rally_decision", "intermediate_writes"],
                seconds=dict(self.seconds), counts=dict(self.counts), sources=self.sources,
                mps_samples=self.mps,
                accounting="Primary phases are exclusive; model and decode subtimings overlap their parent. "
                           "Decoder work is on another thread. Do not sum subtimings or process memory with MPS memory."),
                ensure_ascii=False, indent=2), encoding="utf-8")

    @contextmanager
    def mps_sampling(self):
        if not self.enabled:
            yield
            return
        import torch
        stop = threading.Event()
        def sample():
            while not stop.is_set():
                row = dict(monotonic_s=time.monotonic())
                try:
                    if torch.backends.mps.is_available():
                        row.update(allocated_bytes=torch.mps.current_allocated_memory(),
                                   driver_bytes=torch.mps.driver_allocated_memory())
                    else:
                        row["unavailable"] = "MPS unavailable"
                except RuntimeError as exc:
                    row["error"] = str(exc)
                self.mps.append(row)
                stop.wait(1)
        thread = threading.Thread(target=sample, name="benchmark-mps", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join()
