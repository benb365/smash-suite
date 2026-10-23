"""File frame producer; source time stays independent of processing time."""
from __future__ import annotations

import math
import queue
import threading
import time
from fractions import Fraction
from pathlib import Path
from typing import Iterator

from .types import TimestampedFrame


class InputOverload(RuntimeError):
    pass


class PtsFrameSelector:
    """Keep the first decoded frame in each source-time bucket."""

    def __init__(self, max_fps: float | None = None) -> None:
        if max_fps is not None and (not math.isfinite(max_fps) or max_fps <= 0):
            raise ValueError("max_fps must be finite and positive")
        self.max_fps = Fraction(str(max_fps)) if max_fps is not None else None
        self.first_pts: Fraction | None = None
        self.last_bucket: int | None = None

    def select(self, pts: int, time_base: Fraction) -> bool:
        if time_base <= 0:
            raise ValueError("Decoded frame has no valid source PTS/time_base")
        absolute_pts = pts * time_base
        if self.first_pts is None:
            self.first_pts = absolute_pts
        if self.max_fps is None:
            return True
        bucket = math.floor((absolute_pts - self.first_pts + time_base / 2) * self.max_fps)
        if self.last_bucket is not None and bucket <= self.last_bucket:
            return False
        self.last_bucket = bucket
        return True


class FileFrameSource:
    """One decoder thread, at most six queued original BGR frames.

    Iteration yields the existing frame contract. Future capture adapters can
    implement that same iterable without changing the segmenter. PTS are
    normalized to the first decoded frame; gaps are never filled or retimed.
    """

    def __init__(self, path: str | Path, *, mode: str = "offline",
                 limit_s: float | None = None, max_lag_s: float = 5.0,
                 max_fps: float | None = None) -> None:
        if mode not in ("offline", "realtime"):
            raise ValueError("mode must be offline or realtime")
        if not math.isfinite(max_lag_s) or max_lag_s <= 0:
            raise ValueError("max_lag_s must be finite and positive")
        if limit_s is not None and (not math.isfinite(limit_s) or limit_s <= 0):
            raise ValueError("limit_s must be finite and positive")
        self.selector = PtsFrameSelector(max_fps)
        self.path, self.mode, self.limit_s = Path(path), mode, limit_s
        self.max_lag_s = max_lag_s
        self._queue: queue.Queue = queue.Queue(maxsize=6)
        self._stop, self._done = threading.Event(), threading.Event()
        self._error: Exception | None = None
        self._inflight_deadline: float | None = None
        self._thread: threading.Thread | None = None
        self.started_at = 0.0
        self.last_delivery: dict = {}
        self.stats = dict(frames_decoded=0, frames_selected=0, frames_skipped=0,
                          frames_converted=0, frames_delivered=0, queue_peak=0,
                          decode_s=0.0, conversion_s=0.0, max_lag_s=0.0)

    def __enter__(self) -> FileFrameSource:
        if self._thread is not None:
            raise RuntimeError("A file source is single-use")
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._produce, name="video-input", daemon=True)
        self._thread.start()
        return self

    def check_health(self, deadline: float | None = None) -> None:
        if self._error is not None:
            raise self._error
        if self.mode != "realtime":
            return
        deadlines = [value for value in (deadline, self._inflight_deadline) if value is not None]
        with self._queue.mutex:
            if self._queue.queue:
                deadlines.append(self._queue.queue[0][1])
        if deadlines:
            lag = max(0.0, time.monotonic() - min(deadlines))
            self.stats["max_lag_s"] = max(self.stats["max_lag_s"], lag)
            if lag > self.max_lag_s:
                raise InputOverload(f"Input is {lag:.3f}s late (limit {self.max_lag_s:.3f}s)")

    def _produce(self) -> None:
        try:
            import av

            with av.open(str(self.path)) as container:
                if not container.streams.video:
                    raise ValueError("Input contains no video stream")
                stream = container.streams.video[0]
                fps = float(stream.average_rate) if stream.average_rate else None
                self.stats.update(fps=fps, expected_frames=stream.frames,
                                  width=stream.codec_context.width, height=stream.codec_context.height)
                first_pts = previous_ms = None
                decoder = iter(container.decode(stream))
                reached_eof = False
                while not self._stop.is_set():
                    tick = time.monotonic()
                    try:
                        decoded = next(decoder)
                    except StopIteration:
                        reached_eof = True
                        break
                    decode_s = time.monotonic() - tick
                    frame_id = self.stats["frames_decoded"]
                    self.stats["frames_decoded"] += 1
                    self.stats["decode_s"] += decode_s
                    if decoded.is_corrupt:
                        raise RuntimeError("Decoder returned a corrupt frame")
                    if decoded.pts is None or decoded.time_base is None or decoded.time_base <= 0:
                        raise ValueError("Decoded frame has no valid source PTS/time_base")
                    pts = decoded.pts * decoded.time_base
                    if first_pts is None:
                        first_pts = pts
                        self.stats["first_pts_ms"] = float(first_pts * 1000)
                    timestamp_ms = float((pts - first_pts) * 1000)
                    if not math.isfinite(timestamp_ms) or (previous_ms is not None and timestamp_ms <= previous_ms):
                        raise ValueError("Source PTS must be finite and strictly increasing")
                    previous_ms = timestamp_ms
                    self.stats["last_timestamp_ms"] = timestamp_ms
                    if (decoded.width, decoded.height) != (self.stats["width"], self.stats["height"]):
                        raise ValueError("Frame dimensions changed within the source")
                    if self.limit_s is not None and timestamp_ms >= self.limit_s * 1000:
                        self.stats["frames_skipped"] += 1
                        break
                    if not self.selector.select(decoded.pts, decoded.time_base):
                        self.stats["frames_skipped"] += 1
                        continue
                    self.stats["frames_selected"] += 1
                    tick = time.monotonic()
                    image = decoded.to_ndarray(format="bgr24")
                    conversion_s = time.monotonic() - tick
                    if image.shape[:2] != (self.stats["height"], self.stats["width"]):
                        raise ValueError("Frame dimensions changed within the source")
                    self.stats["frames_converted"] += 1
                    self.stats["conversion_s"] += conversion_s
                    deadline = self.started_at + timestamp_ms / 1000
                    if self.mode == "realtime":
                        while not self._stop.is_set():
                            self.check_health(deadline)
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            self._stop.wait(min(remaining, .05))
                    while not self._stop.is_set():
                        self.check_health(deadline)
                        try:
                            self._queue.put((TimestampedFrame(frame_id, timestamp_ms, image), deadline,
                                             time.monotonic(), decode_s, conversion_s), timeout=.05)
                            self.stats["queue_peak"] = max(self.stats["queue_peak"], self._queue.qsize())
                            break
                        except queue.Full:
                            continue
                if reached_eof and stream.frames and self.stats["frames_decoded"] != stream.frames:
                    raise RuntimeError(f"Premature EOF: decoded {self.stats['frames_decoded']} of {stream.frames} frames")
                if reached_eof and self.stats["frames_decoded"] == 0:
                    raise ValueError("Input contains no decodable video frames")
        except Exception as exc:
            self._error = exc
        finally:
            self._done.set()

    def __iter__(self) -> Iterator[TimestampedFrame]:
        if self._thread is None:
            raise RuntimeError("Use FileFrameSource as a context manager")
        while True:
            self.check_health()
            try:
                frame, deadline, queued_at, decode_s, conversion_s = self._queue.get(timeout=.05)
            except queue.Empty:
                if self._done.is_set():
                    self.check_health()
                    return
                continue
            self._inflight_deadline = deadline
            self.check_health(deadline)
            delivered_at = time.monotonic()
            self.last_delivery = dict(queue_wait_s=delivered_at - queued_at,
                                      schedule_lag_s=max(0, delivered_at - deadline) if self.mode == "realtime" else None,
                                      decode_s=decode_s, conversion_s=conversion_s)
            self.stats["frames_delivered"] += 1
            self.stats["last_delivered_timestamp_ms"] = frame.timestamp_ms
            yield frame
            self.check_health(deadline)
            self._inflight_deadline = None

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("File decoder did not stop within 5 seconds")
        # Release decoded images even when the consumer stopped early.
        with self._queue.mutex:
            self._queue.queue.clear()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


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
