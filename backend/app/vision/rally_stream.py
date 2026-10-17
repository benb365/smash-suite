from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol, Sequence


@dataclass(frozen=True)
class TimestampedFrame:
    frame_id: int
    timestamp_ms: float
    image: Any


@dataclass(frozen=True)
class RallyInterval:
    rally_id: int
    start_ms: float
    end_ms: float
    emitted_at_ms: float

    def __post_init__(self) -> None:
        if type(self.rally_id) is not int:
            raise ValueError("Rally id must be an integer.")
        if not all(math.isfinite(value) for value in (self.start_ms, self.end_ms, self.emitted_at_ms)):
            raise ValueError("Rally times must be finite.")
        if not self.start_ms <= self.end_ms <= self.emitted_at_ms:
            raise ValueError("Rally requires start_ms <= end_ms <= emitted_at_ms.")


class RallySegmenter(Protocol):
    def process(self, frame: TimestampedFrame) -> Sequence[RallyInterval]: ...


class RallyStream:
    """Validate the same contract for replay and live frame producers."""

    def __init__(self, segmenter: RallySegmenter) -> None:
        self.segmenter = segmenter
        self._last_frame: TimestampedFrame | None = None
        self._rally_ids: set[int] = set()

    def process(self, frame: TimestampedFrame) -> list[RallyInterval]:
        if type(frame.frame_id) is not int:
            raise ValueError("Frame id must be an integer.")
        if not math.isfinite(frame.timestamp_ms):
            raise ValueError("Frame timestamp must be finite.")
        if self._last_frame is not None:
            if frame.frame_id <= self._last_frame.frame_id:
                raise ValueError("Frame ids must be strictly increasing.")
            if frame.timestamp_ms <= self._last_frame.timestamp_ms:
                raise ValueError("Frame timestamps must be strictly increasing.")
        intervals = list(self.segmenter.process(frame))
        ids = [interval.rally_id for interval in intervals]
        if len(set(ids)) != len(ids) or self._rally_ids.intersection(ids):
            raise ValueError("A rally id may only be emitted once.")
        for interval in intervals:
            if interval.emitted_at_ms != frame.timestamp_ms:
                raise ValueError("emitted_at_ms must equal the current source frame timestamp.")
        self._rally_ids.update(ids)
        self._last_frame = frame
        return intervals


def replay_frames(
    frames: Iterable[TimestampedFrame],
    segmenter: RallySegmenter,
    *,
    source_duration_ms: float,
) -> dict[str, Any]:
    """Consume lazily, without looking ahead or inventing an EOF end event."""
    if not math.isfinite(source_duration_ms) or source_duration_ms < 0:
        raise ValueError("Source duration must be finite and nonnegative.")
    stream = RallyStream(segmenter)
    predictions: list[RallyInterval] = []
    frame_count = 0
    started = time.perf_counter()
    for frame in frames:
        predictions.extend(stream.process(frame))
        frame_count += 1
    wall_time_s = time.perf_counter() - started
    return {
        "predictions": predictions,
        "frames_processed": frame_count,
        "source_duration_ms": source_duration_ms,
        "wall_time_s": wall_time_s,
        "realtime_factor": source_duration_ms / 1000 / wall_time_s if wall_time_s > 0 else None,
    }


def iter_cfr_video_frames(
    path: str | Path, *, fps: float, sample_stride: int = 1
) -> Iterator[TimestampedFrame]:
    """CFR benchmark adapter; fps must be declared in the dataset manifest.

    VFR or live sources must supply their own source timestamps instead. This
    adapter intentionally does not guess a frame rate or silently reorder frames.
    """
    if not math.isfinite(fps) or fps <= 0 or sample_stride < 1:
        raise ValueError("CFR fps must be positive and sample_stride must be >= 1.")
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open video: {path}")
    frame_id = 0
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if frame_id % sample_stride == 0:
                yield TimestampedFrame(frame_id, frame_id * 1000 / fps, image)
            frame_id += 1
    finally:
        capture.release()
