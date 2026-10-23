"""File-only sparse inference on the scene's existing three-frame windows."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from modules.media.types import TimestampedFrame


@dataclass
class Window:
    frames: tuple[TimestampedFrame, ...]
    points: list | None = None
    observations: list = field(default_factory=list)
    candidate: bool = False


class DynamicScan:
    """Each phase owns its memo; a predictor's model configuration is immutable.

    Windows arrive in analysis order, while their source IDs may be sparse after
    frame selection. Retain unresolved images only until a known negative barrier
    makes left expansion impossible; completed windows retain observations only.
    """

    def __init__(self, predictor, *, cache_frames=False):
        self.predictor = predictor
        self.cache_frames = cache_frames
        self.windows: list[Window] = []
        self.images: dict[int, tuple[TimestampedFrame, ...]] = {}
        self.seconds: set[int] = set()
        self.forward = False
        self.last_negative = -1
        self.counts = dict(coarse_windows=0, expansion_windows=0, reused_windows=0,
                           image_buffer_peak_frames=0)

    def add(self, frames):
        frames = tuple(frames)
        if len(frames) != 3 or any(
            not math.isfinite(f.timestamp_ms) or
            (i and (f.frame_id <= frames[i - 1].frame_id or
                    f.timestamp_ms <= frames[i - 1].timestamp_ms))
            for i, f in enumerate(frames)
        ):
            raise ValueError("Dynamic scan requires three ordered real frames")
        if self.windows and frames[0].frame_id <= self.windows[-1].frames[-1].frame_id:
            raise ValueError("Windows in one scan phase must not overlap")
        index = len(self.windows)
        self.windows.append(Window(tuple(TimestampedFrame(f.frame_id, f.timestamp_ms, None) for f in frames)))
        self.images[index] = frames
        self.counts["image_buffer_peak_frames"] = max(
            self.counts["image_buffer_peak_frames"], 3 * len(self.images))
        second = math.floor(frames[0].timestamp_ms / 1000)
        coarse = second not in self.seconds
        self.seconds.add(second)
        hit = self._evaluate(index, "coarse") if coarse else None
        if self.forward:
            hit = self._evaluate(index, "expansion")
            self.windows[index].candidate = True
        if hit:
            self.windows[index].candidate = True
            self._left(index - 1)
            self.forward = True
        elif hit is False:
            self.forward = False
        for old in [i for i in self.images if i <= self.last_negative]:
            del self.images[old]

    def _evaluate(self, index, reason):
        window = self.windows[index]
        if window.points is not None:
            self.counts["reused_windows"] += 1
        else:
            frames = self.images.pop(index)
            kwargs = {"frame_ids": [f.frame_id for f in frames]} if self.cache_frames else {}
            points = self.predictor([f.image for f in frames], **kwargs)
            if len(points) != 3 or any(not math.isfinite(p.confidence) for p in points):
                raise ValueError("TrackNet must return three finite global peak scores")
            window.points = list(points)
            window.observations = list(self.predictor.last_candidates)
            if self.predictor.record_candidates and len(window.observations) != 3:
                raise ValueError("TrackNet candidate observations must match the window")
            self.counts[reason + "_windows"] += 1
        hit = any(p.confidence >= .5 for p in window.points)
        if not hit:
            self.last_negative = max(self.last_negative, index)
        return hit

    def _left(self, index):
        while index >= 0:
            window = self.windows[index]
            already_candidate = window.candidate
            hit = self._evaluate(index, "expansion")
            window.candidate = True
            if not hit or already_candidate:
                break
            index -= 1

    def finish(self):
        self.images.clear()

    def observations(self):
        rows = {}
        for window in self.windows:
            for i, frame in enumerate(window.frames):
                observed = window.observations[i] if window.observations else dict(
                    global_peak=None, largest_region=None, peaks=[], peak_floor=.1, max_peaks=32)
                rows[frame.frame_id] = dict(observed, frame_id=frame.frame_id,
                                           timestamp_ms=frame.timestamp_ms,
                                           skip=window.points is None)
        return rows

    def candidate_ids(self):
        return {f.frame_id for window in self.windows if window.candidate for f in window.frames}

    def summary(self):
        return dict(self.counts, windows=len(self.windows),
                    model_windows=self.counts["coarse_windows"] + self.counts["expansion_windows"],
                    candidate_windows=sum(w.candidate for w in self.windows),
                    skipped_windows=sum(w.points is None for w in self.windows))
