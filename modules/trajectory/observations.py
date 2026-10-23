"""Persistent TrackNet point observations for offline trajectory analysis."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ObservationLog:
    """Write one TrackNet observation per line and a completion manifest."""

    reference_size = [1920, 1080]

    def __init__(self, point_path, *, source, info, weight):
        self.point_path = Path(point_path)
        self.source = Path(source)
        self.info = info
        self.weight = Path(weight)
        self.meta_path = self.point_path.with_suffix(".meta.json")
        self._stream = None
        self._last_timestamp_ms = None
        self._last_frame_id = None
        self._frame_count = 0
        self._meta = None

    def __enter__(self):
        self.point_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta = {
            "source": str(self.source),
            "source_sha256": _sha256(self.source),
            "model_sha256": _sha256(self.weight),
            "model_path": str(self.weight),
            "video_info": {
                "duration_ms": self.info.duration_ms,
                "width": self.info.width,
                "height": self.info.height,
                "first_pts_ms": self.info.first_pts_ms,
            },
            "reference_size": self.reference_size,
            "complete": False,
        }
        self._stream = self.point_path.open("w", encoding="utf-8")
        self._write_meta(False)
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._stream.flush()
        self._stream.close()
        self._stream = None
        self._meta.update(frame_count=self._frame_count,
                          last_timestamp_ms=self._last_timestamp_ms)
        self._write_meta(exc_type is None)
        return False

    def _write_meta(self, complete):
        meta = dict(self._meta, complete=complete)
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    def __call__(self, frame, point):
        if self._stream is None:
            raise RuntimeError("ObservationLog must be used inside its context manager.")
        timestamp_ms = float(frame.timestamp_ms)
        frame_id = frame.frame_id
        confidence = float(point.confidence)
        if type(frame_id) is not int or (
            self._last_frame_id is not None and frame_id <= self._last_frame_id
        ):
            raise ValueError("Observation frame IDs must be integers and strictly increasing.")
        if not math.isfinite(timestamp_ms) or (
            self._last_timestamp_ms is not None and timestamp_ms <= self._last_timestamp_ms
        ):
            raise ValueError("Observation timestamps must be finite and strictly increasing.")
        if not math.isfinite(confidence):
            raise ValueError("Observation confidence must be finite.")
        x, y = float(point.x), float(point.y)
        if confidence < 0.6 or not (math.isfinite(x) and math.isfinite(y)):
            x = y = None
        row = {
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
            "x": x,
            "y": y,
            "confidence": confidence,
        }
        self._stream.write(json.dumps(row, allow_nan=False) + "\n")
        self._last_timestamp_ms = timestamp_ms
        self._last_frame_id = frame_id
        self._frame_count += 1
