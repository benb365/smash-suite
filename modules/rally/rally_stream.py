from __future__ import annotations

import math
import time
from typing import Any, Iterable, Protocol, Sequence
from modules.media.types import TimestampedFrame
from .types import RallyInterval


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


