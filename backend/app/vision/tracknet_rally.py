"""TrackNet flight candidate, independent of automatic court/player detection.

Boundaries are first/last observed flight, not certified racket/ground events.
Three consecutive input frames are buffered; results use the current frame's
time even when a heatmap describes either of the preceding two frames.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .rally_stream import RallyInterval, TimestampedFrame


@dataclass(frozen=True)
class ShuttlePoint:
    x: float
    y: float
    confidence: float


def heatmap_candidates(heatmap, *, width, height):
    """Record alternative observations, without changing the original decoder.

    Keep small low-confidence peaks for offline association experiments. Each
    score belongs to its own region; no position is inferred across frames.
    """
    import cv2
    import numpy as np

    py, px = np.unravel_index(heatmap.argmax(), heatmap.shape)
    def point(x, y, confidence):
        return dict(x=float(x*width/heatmap.shape[1]), y=float(y*height/heatmap.shape[0]),
                    confidence=float(confidence))
    peak = point(px, py, heatmap[py, px])
    threshold = (heatmap > .6).astype(np.uint8)
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = peak
    if contours:
        contour = max(contours, key=lambda c: cv2.boundingRect(c)[2]*cv2.boundingRect(c)[3])
        bx, by, bw, bh = cv2.boundingRect(contour)
        _, labels = cv2.connectedComponents(threshold)
        x, y = contour[0, 0]
        largest = point(bx+bw/2, by+bh/2, heatmap[labels == labels[y, x]].max())
    maxima = ((heatmap == cv2.dilate(heatmap, np.ones((5, 5), np.uint8)))
              & (heatmap >= .1)).astype(np.uint8)
    regions, _ = cv2.findContours(maxima, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    peaks = []
    for region in regions:
        x, y = region[0, 0]
        peaks.append(point(x, y, heatmap[y, x]))
    peaks.sort(key=lambda p: p['confidence'], reverse=True)
    return dict(global_peak=peak, largest_region=largest, peaks=peaks[:32],
                peak_floor=.1, max_peaks=32)


@dataclass(frozen=True)
class FlightConfig:
    confidence: float = 0.6
    motion_window_ms: float = 200
    min_motion_window_ms: float = 80
    min_speed_px_s: float = 100
    max_speed_px_s: float = 4000
    quiet_ms: float = 1600
    min_flight_span_ms: float = 2200
    # Normalized image bounds, supplied per camera. This is an expanded image
    # field, NOT a floor homography: an airborne shuttle can be above the court.
    field: tuple[float, float, float, float] = (0, 0, 1, 1)


class ShuttleRallySegmenter:
    def __init__(
        self,
        predict: Callable[[list[Any]], Sequence[ShuttlePoint]],
        *,
        width: float,
        height: float,
        config: FlightConfig | None = None,
    ) -> None:
        self.predict = predict
        self.width, self.height = width, height
        self.config = config or FlightConfig()
        self.pending: list[TimestampedFrame] = []
        self.points: deque[tuple[float, ShuttlePoint]] = deque()
        self.streak: list[tuple[float, float]] = []
        self.start_ms: float | None = None
        self.first_motion_ms: float | None = None
        self.last_motion_ms: float | None = None
        self.active = False
        self.rally_id = 0
        self.last_diagnostics: list[dict] = []

    def process(self, frame: TimestampedFrame) -> list[RallyInterval]:
        self.last_diagnostics = []
        self.pending.append(frame)
        if len(self.pending) < 3:
            return []
        points = self.predict([item.image for item in self.pending])
        if len(points) != 3:
            raise ValueError("TrackNet must return one point for each of three frames.")
        intervals = []
        for source, point in zip(self.pending, points):
            intervals.extend(self._observe(source, point, frame.timestamp_ms))
        self.pending.clear()
        return intervals

    def _observe(self, source: TimestampedFrame, point: ShuttlePoint, emitted_at: float) -> list[RallyInterval]:
        cfg, now = self.config, source.timestamp_ms
        intervals = []
        # Expire before accepting a new flight: a later observation must not
        # silently glue a finished rally to a ball-return or another rally.
        if self._quiet_expired(now, point):
            if self.active:
                self.rally_id += 1
                intervals.append(RallyInterval(self.rally_id, self.start_ms, self.last_motion_ms, emitted_at))
            self.start_ms = self.first_motion_ms = self.last_motion_ms = None
            self.active = False
            self.streak.clear()

        while self.points and now - self.points[0][0] > cfg.motion_window_ms:
            self.points.popleft()
        left, top, right, bottom = cfg.field
        finite = all(math.isfinite(value) for value in (point.x, point.y, point.confidence))
        valid = finite and point.confidence >= cfg.confidence and left <= point.x / self.width <= right and top <= point.y / self.height <= bottom
        speed = None
        motion = False
        anchor = now
        if valid:
            if self.points:
                anchor, previous = self.points[0]
                dt = now - anchor
                if dt >= cfg.min_motion_window_ms:
                    # Thresholds use the reference 1920px width; other input
                    # resolutions retain the same image-relative motion test.
                    distance = math.hypot(point.x - previous.x, point.y - previous.y) * 1920 / self.width
                    speed = distance * 1000 / dt
                    motion = cfg.min_speed_px_s <= speed <= cfg.max_speed_px_s
            self.points.append((now, point))
        motion = motion and self._allow_motion()

        if motion:
            if self.streak and now - self.streak[-1][0] > 120:
                self.streak.clear()
            self.streak.append((now, anchor))
            # Three moving observations reject a lone high-confidence jump.
            # Once a rally is confirmed, sparse observations may extend it:
            # demanding another three-frame streak would truncate fast shots.
            if len(self.streak) >= 3 or self.active:
                if self.start_ms is None:
                    self.start_ms = self.streak[0][1]
                    self.first_motion_ms = self.streak[0][0]
                self.last_motion_ms = now
                if now - self.first_motion_ms >= cfg.min_flight_span_ms:
                    self.active = True
            # Only the first point of the streak is needed for its start time.
            if len(self.streak) > 3:
                self.streak = [self.streak[0], *self.streak[-2:]]
        else:
            self.streak.clear()
        self.last_diagnostics.append(dict(
            frame_id=source.frame_id, timestamp_ms=now, confidence=point.confidence,
            x=point.x, y=point.y, valid=valid, speed_px_s=speed, motion=motion,
            candidate=self.start_ms is not None, active=self.active,
        ))
        return intervals

    def _quiet_expired(self, now: float, point: ShuttlePoint) -> bool:
        return self.last_motion_ms is not None and now - self.last_motion_ms > self.config.quiet_ms

    def _allow_motion(self) -> bool:
        return True


class TrackNetPredictor:
    """Load the existing upstream architecture/weights; never fetch a model."""
    def __init__(self, model_dir, *, device: str, record_candidates: bool = False) -> None:
        import importlib.util
        import torch

        spec = importlib.util.spec_from_file_location("smash_local_tracknet", model_dir / "TrackNet.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.torch, self.device = torch, device
        self.record_candidates = record_candidates
        self.last_candidates = []
        torch.set_num_threads(4)
        self.model = module.TrackNet()
        self.model.load_state_dict(torch.load(model_dir / "weights/ball_track.pt", map_location="cpu", weights_only=True))
        self.model.eval().to(device)

    def __call__(self, frames: list[Any]) -> list[ShuttlePoint]:
        import cv2
        import numpy as np
        from torchvision.transforms.functional import resize

        started = time.perf_counter()
        tensors = []
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor = self.torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255
            tensors.append(resize(tensor, [288, 512], antialias=True))
        preprocessed = time.perf_counter()
        with self.torch.inference_mode():
            heatmaps = self.model(self.torch.cat(tensors).unsqueeze(0).to(self.device))[0].cpu().numpy()
        inferred = time.perf_counter()
        points = []
        self.last_candidates = []
        for frame, heatmap in zip(frames, heatmaps):
            if self.record_candidates:
                self.last_candidates.append(heatmap_candidates(
                    heatmap, width=frame.shape[1], height=frame.shape[0]))
            py, px = np.unravel_index(heatmap.argmax(), heatmap.shape)
            x, y = float(px), float(py)
            contours, _ = cv2.findContours((heatmap > 0.6).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                bx, by, bw, bh = max((cv2.boundingRect(contour) for contour in contours), key=lambda box: box[2] * box[3])
                x, y = bx + bw / 2, by + bh / 2
            points.append(ShuttlePoint(x * frame.shape[1] / 512, y * frame.shape[0] / 288, float(heatmap[py, px])))
        self.last_timing = dict(preprocess_s=preprocessed - started,
                                inference_and_transfer_s=inferred - preprocessed,
                                point_decode_s=time.perf_counter() - inferred)
        return points
