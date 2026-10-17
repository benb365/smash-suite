from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Optional, Protocol, Sequence, Tuple, Union

from app.models import SceneGateResult, SceneSegment


RallyState = Literal["IDLE", "PROVISIONAL_RALLY", "RALLY", "END_PENDING"]
DEFAULT_YOLO_MODEL = str(Path(__file__).resolve().parents[3] / "models/yolo11n/yolo11n.pt")


@dataclass(frozen=True)
class RallySegmentationConfig:
    detector_fps: float = 12.5
    sample_stride: Optional[int] = None
    max_frames: Optional[int] = None
    ring_buffer_ms: float = 8000.0
    start_guard_ms: float = 10000.0
    end_guard_ms: float = 1200.0
    end_confirm_ms: float = 3200.0
    max_emit_latency_ms: float = 5000.0
    active_window_ms: float = 400.0
    merge_gap_ms: float = 2000.0
    min_rally_ms: float = 1000.0
    stable_visible_ms: float = 0.0
    max_track_gap_ms: float = 1000.0
    iou_match_threshold: float = 0.12
    min_detection_confidence: float = 0.15
    active_speed_px_s: float = 70.0
    active_acceleration_px_s2: float = 200.0
    hit_like_speed_px_s: float = 300.0
    require_opposite_halves: bool = True
    roi_polygon: Optional[Sequence[Tuple[float, float]]] = None
    court_midline_y: Optional[float] = None

    def normalized(self) -> "RallySegmentationConfig":
        roi_polygon = None
        if self.roi_polygon is not None:
            roi_polygon = tuple((float(x), float(y)) for x, y in self.roi_polygon)

        return RallySegmentationConfig(
            detector_fps=max(0.1, self.detector_fps),
            sample_stride=max(1, self.sample_stride) if self.sample_stride is not None else None,
            max_frames=self.max_frames,
            ring_buffer_ms=max(0.0, self.ring_buffer_ms),
            start_guard_ms=max(0.0, self.start_guard_ms),
            end_guard_ms=max(0.0, self.end_guard_ms),
            end_confirm_ms=max(1.0, self.end_confirm_ms),
            max_emit_latency_ms=max(1.0, self.max_emit_latency_ms),
            active_window_ms=max(1.0, self.active_window_ms),
            merge_gap_ms=max(0.0, self.merge_gap_ms),
            min_rally_ms=max(0.0, self.min_rally_ms),
            stable_visible_ms=max(0.0, self.stable_visible_ms),
            max_track_gap_ms=max(1.0, self.max_track_gap_ms),
            iou_match_threshold=max(0.0, min(1.0, self.iou_match_threshold)),
            min_detection_confidence=max(0.0, min(1.0, self.min_detection_confidence)),
            active_speed_px_s=max(0.0, self.active_speed_px_s),
            active_acceleration_px_s2=max(0.0, self.active_acceleration_px_s2),
            hit_like_speed_px_s=max(0.0, self.hit_like_speed_px_s),
            require_opposite_halves=self.require_opposite_halves,
            roi_polygon=roi_polygon,
            court_midline_y=self.court_midline_y,
        )


@dataclass(frozen=True)
class PlayerDetection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    track_id: Optional[int] = None

    @property
    def foot_point(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, self.y2)


@dataclass(frozen=True)
class TrackedPlayer:
    track_id: int
    bbox: Tuple[float, float, float, float]
    confidence: float
    foot_point: Tuple[float, float]
    frame_id: int
    time_ms: float
    first_seen_ms: float
    visible_count: int
    visible_duration_ms: float
    speed_px_s: float
    acceleration_px_s2: float


@dataclass(frozen=True)
class RallyFrameSignal:
    frame_id: int
    time_ms: float
    visible_player_count: int
    main_track_ids: Tuple[int, ...]
    main_feet: Tuple[Tuple[float, float], ...]
    pair_stable: bool
    opposite_halves: bool
    active: bool
    hit_like: bool
    max_foot_speed_px_s: float
    max_foot_acceleration_px_s2: float
    confidence: float
    reason: str


@dataclass(frozen=True)
class RallySegmentationPerformance:
    wall_time_s: float
    source_duration_s: float
    frames_read: int
    frames_analyzed: int
    sample_stride: int
    detector: str
    tracker: str
    model_path: Optional[str]
    device: Optional[str]
    detections_total: int
    tracks_total: int
    segments_emitted: int
    source_fps_processed: float
    analyzed_fps: float
    realtime_factor: float
    average_detections_per_frame: float
    average_tracks_per_frame: float
    read_ms_avg: float
    detect_ms_avg: float
    detect_ms_p95: float
    track_signal_state_ms_avg: float
    debug_render_ms_avg: float


class DetectionProvider(Protocol):
    name: str

    def detect(
        self,
        frame: Any,
        frame_id: int,
        time_ms: float,
    ) -> Sequence[PlayerDetection]:
        ...


class TrackingProvider(Protocol):
    name: str
    tracker_name: str
    model_path: Optional[str]
    device: Optional[str]

    def detect_and_track(
        self,
        frame: Any,
        frame_id: int,
        time_ms: float,
    ) -> Tuple[Sequence[PlayerDetection], Sequence[TrackedPlayer]]:
        ...


class OpenCVHogPersonDetector:
    name = "opencv_hog_person"

    def __init__(
        self,
        hit_threshold: float = 0.0,
        win_stride: Tuple[int, int] = (8, 8),
        padding: Tuple[int, int] = (8, 8),
        scale: float = 1.05,
    ) -> None:
        self.hit_threshold = hit_threshold
        self.win_stride = win_stride
        self.padding = padding
        self.scale = scale
        self._hog: Any = None

    def detect(
        self,
        frame: Any,
        frame_id: int,
        time_ms: float,
    ) -> Sequence[PlayerDetection]:
        del frame_id, time_ms
        hog = self._ensure_hog()
        rects, weights = hog.detectMultiScale(
            frame,
            winStride=self.win_stride,
            padding=self.padding,
            scale=self.scale,
            hitThreshold=self.hit_threshold,
        )
        detections: list[PlayerDetection] = []
        for rect, weight in zip(rects, weights):
            x, y, width, height = rect
            detections.append(
                PlayerDetection(
                    x1=float(x),
                    y1=float(y),
                    x2=float(x + width),
                    y2=float(y + height),
                    confidence=max(0.0, min(1.0, float(weight))),
                )
            )
        return detections

    def _ensure_hog(self) -> Any:
        if self._hog is None:
            try:
                import cv2  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "OpenCV is required for the default person detector. "
                    "Run `python3 -m pip install -r backend/requirements.txt`."
                ) from exc

            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        return self._hog


class UltralyticsPersonDetector:
    name = "ultralytics_yolo_person"

    def __init__(
        self,
        model_path: str = DEFAULT_YOLO_MODEL,
        confidence: float = 0.25,
        device: Optional[str] = None,
        image_size: Optional[int] = None,
    ) -> None:
        self.model_path = model_path
        self.confidence = confidence
        self.device = device
        self.image_size = image_size
        self._model: Any = None

    def detect(
        self,
        frame: Any,
        frame_id: int,
        time_ms: float,
    ) -> Sequence[PlayerDetection]:
        del frame_id, time_ms
        model = self._ensure_model()
        predict_kwargs: dict[str, Any] = {
            "classes": [0],
            "conf": self.confidence,
            "verbose": False,
        }
        if self.device:
            predict_kwargs["device"] = self.device
        if self.image_size:
            predict_kwargs["imgsz"] = self.image_size

        results = model.predict(frame, **predict_kwargs)
        if not results:
            return []

        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return []

        detections: list[PlayerDetection] = []
        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            detections.append(
                PlayerDetection(
                    x1=float(xyxy[0]),
                    y1=float(xyxy[1]),
                    x2=float(xyxy[2]),
                    y2=float(xyxy[3]),
                    confidence=confidence,
                )
            )
        return detections

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from ultralytics import YOLO  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "Ultralytics is required for YOLO person detection. "
                    "Install it in the active Python environment or use the default HOG detector."
                ) from exc

            self._model = YOLO(self.model_path)
        return self._model


class RallyDebugVideoWriter:
    def __init__(
        self,
        output_path: Union[str, Path],
        output_fps: float,
        roi_polygon: Optional[Sequence[Tuple[float, float]]] = None,
        resize_width: Optional[int] = 960,
    ) -> None:
        self.output_path = Path(output_path)
        self.output_fps = max(0.1, output_fps)
        self.roi_polygon = roi_polygon
        self.resize_width = resize_width
        self._writer: Any = None
        self._cv2: Any = None

    def write(
        self,
        frame: Any,
        detections: Sequence[PlayerDetection],
        tracks: Sequence[TrackedPlayer],
        signal: RallyFrameSignal,
    ) -> None:
        cv2 = self._ensure_cv2()
        annotated = frame.copy()
        self._draw_roi(annotated)
        for detection in detections:
            track_suffix = f" #{detection.track_id}" if detection.track_id is not None else ""
            _draw_box(
                cv2,
                annotated,
                (detection.x1, detection.y1, detection.x2, detection.y2),
                (60, 220, 60),
                f"person{track_suffix} {detection.confidence:.2f}",
            )

        main_ids = set(signal.main_track_ids)
        for track in tracks:
            is_main = track.track_id in main_ids
            color = (0, 165, 255) if is_main else (255, 180, 40)
            label = f"id {track.track_id} conf {track.confidence:.2f} {track.speed_px_s:.0f}px/s"
            _draw_box(cv2, annotated, track.bbox, color, label)
            cv2.circle(
                annotated,
                (int(round(track.foot_point[0])), int(round(track.foot_point[1]))),
                5,
                color,
                -1,
            )

        self._draw_header(annotated, signal)
        if self.resize_width and annotated.shape[1] > self.resize_width:
            scale = self.resize_width / float(annotated.shape[1])
            height = max(1, int(round(annotated.shape[0] * scale)))
            annotated = cv2.resize(annotated, (self.resize_width, height))

        writer = self._ensure_writer(annotated)
        writer.write(annotated)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def _draw_roi(self, frame: Any) -> None:
        if not self.roi_polygon:
            return
        cv2 = self._ensure_cv2()
        try:
            import numpy as np  # type: ignore
        except ImportError:
            return
        points = np.array(
            [[int(round(x)), int(round(y))] for x, y in self.roi_polygon],
            dtype=np.int32,
        )
        cv2.polylines(frame, [points], isClosed=True, color=(0, 255, 255), thickness=2)

    def _draw_header(self, frame: Any, signal: RallyFrameSignal) -> None:
        cv2 = self._ensure_cv2()
        active_text = "active" if signal.active else "low"
        text = (
            f"frame={signal.frame_id} time={signal.time_ms / 1000:.2f}s "
            f"players={signal.visible_player_count} {active_text} {signal.reason}"
        )
        cv2.rectangle(frame, (8, 8), (min(frame.shape[1] - 8, 1120), 44), (0, 0, 0), -1)
        cv2.putText(
            frame,
            text,
            (16, 33),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def _ensure_writer(self, frame: Any) -> Any:
        if self._writer is None:
            cv2 = self._ensure_cv2()
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            height, width = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(
                str(self.output_path),
                fourcc,
                self.output_fps,
                (width, height),
            )
            if not self._writer.isOpened():
                raise RuntimeError(f"Could not open debug video writer: {self.output_path}")
        return self._writer

    def _ensure_cv2(self) -> Any:
        if self._cv2 is None:
            try:
                import cv2  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "OpenCV is required for debug video output. "
                    "Run `python3 -m pip install -r backend/requirements.txt`."
                ) from exc
            self._cv2 = cv2
        return self._cv2


class RallyTraceWriter:
    def __init__(self, output_path: Union[str, Path]) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("w", encoding="utf-8")

    def write_frame(
        self,
        frame_id: int,
        time_ms: float,
        state_before: RallyState,
        state_after: RallyState,
        detections: Sequence[PlayerDetection],
        tracks: Sequence[TrackedPlayer],
        signal: RallyFrameSignal,
        emitted_segments: Sequence[SceneSegment],
    ) -> None:
        payload = {
            "frame_id": frame_id,
            "time_ms": round(time_ms, 3),
            "state_before": state_before,
            "state_after": state_after,
            "detections": [_detection_to_dict(detection) for detection in detections],
            "tracks": [_track_to_dict(track) for track in tracks],
            "signal": asdict(signal),
            "emitted_segments": [segment.model_dump() for segment in emitted_segments],
        }
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._file.close()


@dataclass
class _MutableTrack:
    track_id: int
    detection: PlayerDetection
    first_seen_ms: float
    last_seen_ms: float
    frame_id: int
    visible_count: int = 1
    missed_count: int = 0
    speed_px_s: float = 0.0
    acceleration_px_s2: float = 0.0

    def update(self, detection: PlayerDetection, frame_id: int, time_ms: float) -> None:
        previous_foot = self.detection.foot_point
        previous_speed = self.speed_px_s
        dt_s = max(0.0, (time_ms - self.last_seen_ms) / 1000.0)
        self.detection = detection
        self.frame_id = frame_id
        self.last_seen_ms = time_ms
        self.visible_count += 1
        self.missed_count = 0

        if dt_s <= 0:
            self.speed_px_s = 0.0
            self.acceleration_px_s2 = 0.0
            return

        next_foot = detection.foot_point
        dx = next_foot[0] - previous_foot[0]
        dy = next_foot[1] - previous_foot[1]
        self.speed_px_s = ((dx * dx + dy * dy) ** 0.5) / dt_s
        self.acceleration_px_s2 = abs(self.speed_px_s - previous_speed) / dt_s

    def snapshot(self) -> TrackedPlayer:
        return TrackedPlayer(
            track_id=self.track_id,
            bbox=(self.detection.x1, self.detection.y1, self.detection.x2, self.detection.y2),
            confidence=self.detection.confidence,
            foot_point=self.detection.foot_point,
            frame_id=self.frame_id,
            time_ms=self.last_seen_ms,
            first_seen_ms=self.first_seen_ms,
            visible_count=self.visible_count,
            visible_duration_ms=max(0.0, self.last_seen_ms - self.first_seen_ms),
            speed_px_s=self.speed_px_s,
            acceleration_px_s2=self.acceleration_px_s2,
        )


class SimpleOnlineTracker:
    """Small IoU tracker used until a heavier ByteTrack/BoT-SORT dependency is selected."""

    def __init__(self, config: Optional[RallySegmentationConfig] = None) -> None:
        self.config = (config or RallySegmentationConfig()).normalized()
        self._tracks: dict[int, _MutableTrack] = {}
        self._next_track_id = 1

    def update(
        self,
        detections: Sequence[PlayerDetection],
        frame_id: int,
        time_ms: float,
    ) -> list[TrackedPlayer]:
        usable_detections = [
            detection
            for detection in detections
            if detection.confidence >= self.config.min_detection_confidence
        ]
        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()

        for detection_index, detection in enumerate(usable_detections):
            if detection.track_id is None:
                continue
            track = self._tracks.get(detection.track_id)
            if track is None:
                track = self._create_track(detection, frame_id, time_ms)
            else:
                track.update(detection, frame_id, time_ms)
            matched_tracks.add(track.track_id)
            matched_detections.add(detection_index)

        pairs: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            if track_id in matched_tracks:
                continue
            if time_ms - track.last_seen_ms > self.config.max_track_gap_ms:
                continue
            for detection_index, detection in enumerate(usable_detections):
                if detection_index in matched_detections:
                    continue
                pairs.append((_bbox_iou(track.detection, detection), track_id, detection_index))

        for score, track_id, detection_index in sorted(pairs, reverse=True):
            if score < self.config.iou_match_threshold:
                continue
            if track_id in matched_tracks or detection_index in matched_detections:
                continue
            self._tracks[track_id].update(usable_detections[detection_index], frame_id, time_ms)
            matched_tracks.add(track_id)
            matched_detections.add(detection_index)

        for detection_index, detection in enumerate(usable_detections):
            if detection_index in matched_detections:
                continue
            track = self._create_track(detection, frame_id, time_ms)
            matched_tracks.add(track.track_id)

        for track_id in list(self._tracks):
            track = self._tracks[track_id]
            if track_id not in matched_tracks:
                track.missed_count += 1
            if time_ms - track.last_seen_ms > self.config.max_track_gap_ms:
                del self._tracks[track_id]

        return [self._tracks[track_id].snapshot() for track_id in sorted(matched_tracks)]

    def _create_track(
        self,
        detection: PlayerDetection,
        frame_id: int,
        time_ms: float,
    ) -> _MutableTrack:
        track_id = detection.track_id if detection.track_id is not None else self._next_track_id
        self._next_track_id = max(self._next_track_id, track_id + 1)
        track = _MutableTrack(
            track_id=track_id,
            detection=detection,
            first_seen_ms=time_ms,
            last_seen_ms=time_ms,
            frame_id=frame_id,
        )
        self._tracks[track_id] = track
        return track


class UltralyticsByteTrackProvider:
    name = "ultralytics_yolo_bytetrack"

    def __init__(
        self,
        model_path: str = DEFAULT_YOLO_MODEL,
        tracker_config: str = "bytetrack.yaml",
        confidence: float = 0.25,
        device: Optional[str] = None,
        image_size: Optional[int] = None,
        max_track_gap_ms: float = 1000.0,
        model: Optional[Any] = None,
    ) -> None:
        self.model_path = model_path
        self.tracker_name = tracker_config
        self.confidence = confidence
        self.device = device
        self.image_size = image_size
        self.max_track_gap_ms = max(1.0, max_track_gap_ms)
        self._model = model
        self._tracks: dict[int, _MutableTrack] = {}

    def detect_and_track(
        self,
        frame: Any,
        frame_id: int,
        time_ms: float,
    ) -> Tuple[Sequence[PlayerDetection], Sequence[TrackedPlayer]]:
        model = self._ensure_model()
        track_kwargs: dict[str, Any] = {
            "classes": [0],
            "conf": self.confidence,
            "persist": True,
            "tracker": self.tracker_name,
            "verbose": False,
        }
        if self.device:
            track_kwargs["device"] = self.device
        if self.image_size:
            track_kwargs["imgsz"] = self.image_size

        results = model.track(frame, **track_kwargs)
        detections = self._parse_detections(results)
        tracks = self._update_tracks(detections, frame_id, time_ms)
        return detections, tracks

    def _parse_detections(self, results: Any) -> list[PlayerDetection]:
        if not results:
            return []

        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return []

        xyxy_rows = _to_list(getattr(boxes, "xyxy", []))
        confidence_values = _flatten_values(getattr(boxes, "conf", []))
        class_values = _flatten_values(getattr(boxes, "cls", []))
        raw_track_ids = getattr(boxes, "id", None)
        track_id_values = _flatten_values(raw_track_ids) if raw_track_ids is not None else []

        detections: list[PlayerDetection] = []
        for index, xyxy in enumerate(xyxy_rows):
            if len(xyxy) < 4:
                continue
            class_id = int(class_values[index]) if index < len(class_values) else 0
            if class_id != 0:
                continue
            confidence = (
                float(confidence_values[index]) if index < len(confidence_values) else 0.0
            )
            track_id = (
                int(track_id_values[index])
                if index < len(track_id_values) and track_id_values[index] is not None
                else None
            )
            detections.append(
                PlayerDetection(
                    x1=float(xyxy[0]),
                    y1=float(xyxy[1]),
                    x2=float(xyxy[2]),
                    y2=float(xyxy[3]),
                    confidence=confidence,
                    track_id=track_id,
                )
            )
        return detections

    def _update_tracks(
        self,
        detections: Sequence[PlayerDetection],
        frame_id: int,
        time_ms: float,
    ) -> list[TrackedPlayer]:
        active_track_ids: set[int] = set()
        for detection in detections:
            if detection.track_id is None:
                continue
            track = self._tracks.get(detection.track_id)
            if track is None:
                track = _MutableTrack(
                    track_id=detection.track_id,
                    detection=detection,
                    first_seen_ms=time_ms,
                    last_seen_ms=time_ms,
                    frame_id=frame_id,
                )
                self._tracks[detection.track_id] = track
            else:
                track.update(detection, frame_id, time_ms)
            active_track_ids.add(detection.track_id)

        for track_id in list(self._tracks):
            track = self._tracks[track_id]
            if time_ms - track.last_seen_ms > self.max_track_gap_ms:
                del self._tracks[track_id]

        return [
            self._tracks[track_id].snapshot()
            for track_id in sorted(active_track_ids)
            if track_id in self._tracks
        ]

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from ultralytics import YOLO  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "Ultralytics is required for YOLO + ByteTrack. "
                    "Run `.venv/bin/python -m pip install -r backend/requirements.txt`."
                ) from exc

            self._model = YOLO(self.model_path)
        return self._model


class RallySignalBuilder:
    def __init__(self, config: Optional[RallySegmentationConfig] = None) -> None:
        self.config = (config or RallySegmentationConfig()).normalized()
        self._roi_polygon = self.config.roi_polygon
        self._court_midline_y = self.config.court_midline_y or _roi_midline_y(self._roi_polygon)

    def build(
        self,
        frame_id: int,
        time_ms: float,
        tracks: Sequence[TrackedPlayer],
    ) -> RallyFrameSignal:
        eligible_tracks = [track for track in tracks if self._is_eligible(track)]
        main_tracks = self._select_main_pair(eligible_tracks)
        opposite_halves = self._opposite_halves(main_tracks)
        pair_stable = (
            len(main_tracks) == 2
            and all(track.visible_duration_ms >= self.config.stable_visible_ms for track in main_tracks)
        )
        max_speed = max((track.speed_px_s for track in main_tracks), default=0.0)
        max_acceleration = max((track.acceleration_px_s2 for track in main_tracks), default=0.0)
        active = (
            pair_stable
            and opposite_halves
            and (
                max_speed >= self.config.active_speed_px_s
                or max_acceleration >= self.config.active_acceleration_px_s2
            )
        )
        hit_like = pair_stable and max_speed >= self.config.hit_like_speed_px_s
        confidence = self._confidence(pair_stable, opposite_halves, max_speed, max_acceleration)
        reason = self._reason(len(eligible_tracks), pair_stable, opposite_halves, active, hit_like)

        return RallyFrameSignal(
            frame_id=frame_id,
            time_ms=round(time_ms, 3),
            visible_player_count=len(eligible_tracks),
            main_track_ids=tuple(track.track_id for track in main_tracks),
            main_feet=tuple(track.foot_point for track in main_tracks),
            pair_stable=pair_stable,
            opposite_halves=opposite_halves,
            active=active,
            hit_like=hit_like,
            max_foot_speed_px_s=round(max_speed, 3),
            max_foot_acceleration_px_s2=round(max_acceleration, 3),
            confidence=round(confidence, 3),
            reason=reason,
        )

    def _is_eligible(self, track: TrackedPlayer) -> bool:
        if track.confidence < self.config.min_detection_confidence:
            return False
        if self._roi_polygon is None:
            return True
        return _point_in_polygon(track.foot_point, self._roi_polygon)

    def _select_main_pair(self, tracks: Sequence[TrackedPlayer]) -> list[TrackedPlayer]:
        if len(tracks) < 2:
            return list(tracks)

        ranked = sorted(tracks, key=_track_score, reverse=True)
        best_pair: Optional[tuple[TrackedPlayer, TrackedPlayer]] = None
        best_score = -1.0
        for left_index, left in enumerate(ranked):
            for right in ranked[left_index + 1 :]:
                pair = (left, right)
                if self.config.require_opposite_halves and not self._opposite_halves(pair):
                    continue
                score = _track_score(left) + _track_score(right)
                if score > best_score:
                    best_pair = pair
                    best_score = score

        if best_pair is not None:
            return [best_pair[0], best_pair[1]]
        return ranked[:2]

    def _opposite_halves(self, tracks: Sequence[TrackedPlayer]) -> bool:
        if len(tracks) != 2:
            return False
        if self._court_midline_y is None:
            return True
        first_y = tracks[0].foot_point[1]
        second_y = tracks[1].foot_point[1]
        return (first_y < self._court_midline_y <= second_y) or (
            second_y < self._court_midline_y <= first_y
        )

    def _confidence(
        self,
        pair_stable: bool,
        opposite_halves: bool,
        max_speed: float,
        max_acceleration: float,
    ) -> float:
        speed_score = _bounded_ratio(max_speed, self.config.active_speed_px_s)
        acceleration_score = _bounded_ratio(
            max_acceleration,
            self.config.active_acceleration_px_s2,
        )
        confidence = 0.25 + 0.35 * max(speed_score, acceleration_score)
        if pair_stable:
            confidence += 0.25
        if opposite_halves:
            confidence += 0.15
        return min(0.95, confidence)

    @staticmethod
    def _reason(
        visible_count: int,
        pair_stable: bool,
        opposite_halves: bool,
        active: bool,
        hit_like: bool,
    ) -> str:
        if hit_like:
            return "main_players_hit_like_speed"
        if active:
            return "main_players_active"
        if visible_count < 2:
            return "less_than_two_players_in_roi"
        if not opposite_halves:
            return "main_players_not_on_opposite_halves"
        if not pair_stable:
            return "main_players_not_stable_yet"
        return "main_players_visible_but_low_motion"


@dataclass
class _RallyDraft:
    start_ms: float
    start_frame_id: int
    first_active_ms: float
    last_active_ms: float
    last_active_frame_id: int
    confidence_total: float
    confidence_count: int
    active_count: int = 1
    hit_like_count: int = 0

    def add_signal(self, signal: RallyFrameSignal) -> None:
        self.confidence_total += signal.confidence
        self.confidence_count += 1
        if signal.active or signal.hit_like:
            self.last_active_ms = signal.time_ms
            self.last_active_frame_id = signal.frame_id
            self.active_count += 1
        if signal.hit_like:
            self.hit_like_count += 1

    @property
    def confidence(self) -> float:
        if self.confidence_count <= 0:
            return 0.5
        return min(0.95, self.confidence_total / self.confidence_count)


class RallyStateMachine:
    def __init__(self, config: Optional[RallySegmentationConfig] = None) -> None:
        self.config = (config or RallySegmentationConfig()).normalized()
        self.state: RallyState = "IDLE"
        self._draft: Optional[_RallyDraft] = None
        self._last_time_ms: Optional[float] = None

    def process(self, signal: RallyFrameSignal) -> list[SceneSegment]:
        if self._last_time_ms is not None and signal.time_ms < self._last_time_ms:
            raise ValueError("RallyStateMachine requires monotonically increasing frame times.")
        self._last_time_ms = signal.time_ms

        if self.state == "IDLE":
            if self._is_start_signal(signal):
                self._start(signal)
            return []

        if self._draft is None:
            self.state = "IDLE"
            return []

        if self.state == "PROVISIONAL_RALLY":
            self._draft.add_signal(signal)
            if self._should_confirm_rally(signal):
                self.state = "RALLY"
                return []
            if signal.time_ms - self._draft.last_active_ms >= self.config.end_confirm_ms:
                self._draft = None
                self.state = "IDLE"
            return []

        if self.state == "RALLY":
            self._draft.add_signal(signal)
            if self._is_start_signal(signal):
                return []
            if signal.time_ms - self._draft.last_active_ms >= self.config.active_window_ms:
                self.state = "END_PENDING"
            return []

        if self.state == "END_PENDING":
            self._draft.add_signal(signal)
            if self._is_start_signal(signal):
                self.state = "RALLY"
                return []
            confirm_ms = min(self.config.end_confirm_ms, self.config.max_emit_latency_ms)
            if signal.time_ms - self._draft.last_active_ms >= confirm_ms:
                segment = self._emit(signal, "end_confirmed_after_low_activity")
                self._draft = None
                self.state = "IDLE"
                return [segment] if segment is not None else []
            return []

        return []

    def flush(self, time_ms: float, frame_id: int) -> list[SceneSegment]:
        if self._draft is None or self.state == "IDLE":
            return []
        signal = RallyFrameSignal(
            frame_id=frame_id,
            time_ms=round(time_ms, 3),
            visible_player_count=0,
            main_track_ids=(),
            main_feet=(),
            pair_stable=False,
            opposite_halves=False,
            active=False,
            hit_like=False,
            max_foot_speed_px_s=0.0,
            max_foot_acceleration_px_s2=0.0,
            confidence=0.45,
            reason="stream_ended",
        )
        segment = self._emit(signal, "stream_ended_with_open_rally")
        self._draft = None
        self.state = "IDLE"
        return [segment] if segment is not None else []

    def _is_start_signal(self, signal: RallyFrameSignal) -> bool:
        return signal.pair_stable and signal.opposite_halves and (signal.active or signal.hit_like)

    def _start(self, signal: RallyFrameSignal) -> None:
        self.state = "PROVISIONAL_RALLY"
        self._draft = _RallyDraft(
            start_ms=max(0.0, signal.time_ms - self.config.start_guard_ms),
            start_frame_id=signal.frame_id,
            first_active_ms=signal.time_ms,
            last_active_ms=signal.time_ms,
            last_active_frame_id=signal.frame_id,
            confidence_total=signal.confidence,
            confidence_count=1,
            hit_like_count=1 if signal.hit_like else 0,
        )

    def _should_confirm_rally(self, signal: RallyFrameSignal) -> bool:
        if self._draft is None:
            return False
        enough_active_time = signal.time_ms - self._draft.first_active_ms >= self.config.active_window_ms
        enough_events = self._draft.active_count >= 2
        return enough_active_time and enough_events

    def _emit(self, signal: RallyFrameSignal, boundary_reason: str) -> Optional[SceneSegment]:
        if self._draft is None:
            return None
        end_ms = min(signal.time_ms, self._draft.last_active_ms + self.config.end_guard_ms)
        duration_ms = max(0.0, end_ms - self._draft.start_ms)
        if duration_ms < self.config.min_rally_ms:
            return None

        return SceneSegment(
            category="rally",
            start_ms=round(self._draft.start_ms, 3),
            end_ms=round(end_ms, 3),
            confidence=round(self._draft.confidence, 3),
            reason="person_tracking_state_machine",
            source_frame_range=[self._draft.start_frame_id, signal.frame_id],
            emitted_at_ms=round(signal.time_ms, 3),
            latency_ms=round(max(0.0, signal.time_ms - end_ms), 3),
            boundary_reason=boundary_reason,
            signal_source="person_detection_tracking",
        )


def build_rally_segments_from_signals(
    signals: Sequence[RallyFrameSignal],
    config: Optional[RallySegmentationConfig] = None,
) -> list[SceneSegment]:
    scene_config = (config or RallySegmentationConfig()).normalized()
    state_machine = RallyStateMachine(scene_config)
    segments: list[SceneSegment] = []
    last_signal: Optional[RallyFrameSignal] = None
    for signal in signals:
        last_signal = signal
        segments.extend(state_machine.process(signal))
    if last_signal is not None:
        segments.extend(state_machine.flush(last_signal.time_ms, last_signal.frame_id))
    return _merge_close_rally_segments(segments, scene_config.merge_gap_ms)


def run_rally_segmentation(
    video_path: Union[str, Path],
    config: Optional[RallySegmentationConfig] = None,
    detector: Optional[DetectionProvider] = None,
    tracking_provider: Optional[TrackingProvider] = None,
    debug_video_path: Optional[Union[str, Path]] = None,
    debug_video_resize_width: Optional[int] = 960,
    trace_path: Optional[Union[str, Path]] = None,
) -> SceneGateResult:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for rally segmentation. "
            "Run `python3 -m pip install -r backend/requirements.txt`."
        ) from exc

    scene_config = (config or RallySegmentationConfig()).normalized()
    source_path = Path(video_path)
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {source_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_ms = (frame_count / fps) * 1000.0 if frame_count else 0.0
    sample_stride = scene_config.sample_stride or max(1, int(round(fps / scene_config.detector_fps)))

    active_tracking_provider = tracking_provider
    active_detector = detector
    if active_tracking_provider is None and active_detector is None:
        active_tracking_provider = UltralyticsByteTrackProvider(
            max_track_gap_ms=scene_config.max_track_gap_ms,
        )
    if active_tracking_provider is None:
        active_detector = active_detector or OpenCVHogPersonDetector()

    detector_name = (
        active_tracking_provider.name
        if active_tracking_provider is not None
        else active_detector.name
    )
    tracker_name = (
        active_tracking_provider.tracker_name
        if active_tracking_provider is not None
        else "simple_iou"
    )
    model_path = (
        active_tracking_provider.model_path
        if active_tracking_provider is not None
        else getattr(active_detector, "model_path", None)
    )
    device = (
        active_tracking_provider.device
        if active_tracking_provider is not None
        else getattr(active_detector, "device", None)
    )
    debug_writer = (
        RallyDebugVideoWriter(
            output_path=debug_video_path,
            output_fps=fps / sample_stride,
            roi_polygon=scene_config.roi_polygon,
            resize_width=debug_video_resize_width,
        )
        if debug_video_path is not None
        else None
    )
    trace_writer = RallyTraceWriter(trace_path) if trace_path is not None else None
    tracker = SimpleOnlineTracker(scene_config) if active_tracking_provider is None else None
    signal_builder = RallySignalBuilder(scene_config)
    state_machine = RallyStateMachine(scene_config)
    segments: list[SceneSegment] = []
    analyzed_frame_count = 0
    frame_id = 0
    last_sampled_frame_id = 0
    last_time_ms = 0.0
    run_started_s = time.perf_counter()
    read_durations_s: list[float] = []
    detect_durations_s: list[float] = []
    track_signal_state_durations_s: list[float] = []
    debug_render_durations_s: list[float] = []
    detections_total = 0
    tracks_total = 0

    try:
        while True:
            if scene_config.max_frames is not None and frame_id >= scene_config.max_frames:
                break

            read_started_s = time.perf_counter()
            ok, frame = cap.read()
            read_durations_s.append(time.perf_counter() - read_started_s)
            if not ok:
                break

            frame_id += 1
            if frame_id % sample_stride != 0:
                continue

            time_ms = ((frame_id - 1) / fps) * 1000.0
            last_time_ms = time_ms
            detect_started_s = time.perf_counter()
            if active_tracking_provider is not None:
                detections, tracks = active_tracking_provider.detect_and_track(
                    frame,
                    frame_id,
                    time_ms,
                )
            else:
                assert active_detector is not None
                detections = active_detector.detect(frame, frame_id, time_ms)
            detect_durations_s.append(time.perf_counter() - detect_started_s)

            track_started_s = time.perf_counter()
            if tracker is not None:
                tracks = tracker.update(detections, frame_id, time_ms)
            signal = signal_builder.build(frame_id, time_ms, tracks)
            state_before = state_machine.state
            emitted_segments = state_machine.process(signal)
            state_after = state_machine.state
            segments.extend(emitted_segments)
            track_signal_state_durations_s.append(time.perf_counter() - track_started_s)

            if trace_writer is not None:
                trace_writer.write_frame(
                    frame_id=frame_id,
                    time_ms=time_ms,
                    state_before=state_before,
                    state_after=state_after,
                    detections=detections,
                    tracks=tracks,
                    signal=signal,
                    emitted_segments=emitted_segments,
                )

            if debug_writer is not None:
                render_started_s = time.perf_counter()
                debug_writer.write(frame, detections, tracks, signal)
                debug_render_durations_s.append(time.perf_counter() - render_started_s)

            analyzed_frame_count += 1
            last_sampled_frame_id = frame_id
            detections_total += len(detections)
            tracks_total += len(tracks)
    finally:
        cap.release()
        if debug_writer is not None:
            debug_writer.close()
        if trace_writer is not None:
            trace_writer.close()

    effective_duration_ms = (
        min(duration_ms, last_time_ms) if scene_config.max_frames is not None else duration_ms
    )
    segments.extend(state_machine.flush(last_time_ms, last_sampled_frame_id or frame_id))
    segments = _merge_close_rally_segments(segments, scene_config.merge_gap_ms)
    wall_time_s = time.perf_counter() - run_started_s
    performance = _build_performance_stats(
        wall_time_s=wall_time_s,
        source_duration_s=effective_duration_ms / 1000.0,
        frames_read=frame_id,
        frames_analyzed=analyzed_frame_count,
        sample_stride=sample_stride,
        detector_name=detector_name,
        tracker_name=tracker_name,
        model_path=model_path,
        device=device,
        detections_total=detections_total,
        tracks_total=tracks_total,
        segments_emitted=len(segments),
        read_durations_s=read_durations_s,
        detect_durations_s=detect_durations_s,
        track_signal_state_durations_s=track_signal_state_durations_s,
        debug_render_durations_s=debug_render_durations_s,
    )
    return build_rally_scene_gate_result(
        video_path=source_path,
        fps=fps,
        frame_count=frame_count,
        duration_ms=effective_duration_ms,
        analyzed_frame_count=analyzed_frame_count,
        sample_stride=sample_stride,
        segments=segments,
        config=scene_config,
        detector_name=detector_name,
        tracker_name=tracker_name,
        model_path=model_path,
        device=device,
        performance=performance,
        debug_video_path=debug_video_path,
        trace_path=trace_path,
    )


def build_rally_scene_gate_result(
    video_path: Union[str, Path],
    fps: float,
    frame_count: int,
    duration_ms: float,
    analyzed_frame_count: int,
    sample_stride: int,
    segments: Sequence[SceneSegment],
    config: RallySegmentationConfig,
    detector_name: str,
    tracker_name: str = "simple_iou",
    model_path: Optional[str] = None,
    device: Optional[str] = None,
    performance: Optional[RallySegmentationPerformance] = None,
    debug_video_path: Optional[Union[str, Path]] = None,
    trace_path: Optional[Union[str, Path]] = None,
) -> SceneGateResult:
    retained_ms = sum(max(0.0, segment.end_ms - segment.start_ms) for segment in segments)
    retained_ratio = retained_ms / duration_ms if duration_ms > 0 else 0.0
    config_payload: dict[str, Any] = {
        **asdict(config.normalized()),
        "algorithm": "person_tracking_state_machine",
        "detector": detector_name,
        "tracker": tracker_name,
        "model_path": model_path,
        "device": device,
    }
    if performance is not None:
        config_payload["performance"] = asdict(performance)
    if debug_video_path is not None:
        config_payload["debug_video_path"] = str(debug_video_path)
    if trace_path is not None:
        config_payload["trace_path"] = str(trace_path)
    return SceneGateResult(
        video_path=str(video_path),
        fps=round(float(fps), 3),
        frame_count=frame_count,
        duration_ms=round(duration_ms, 3),
        analyzed_frame_count=analyzed_frame_count,
        sample_stride=sample_stride,
        retained_ms=round(retained_ms, 3),
        retained_ratio=round(retained_ratio, 4),
        category_durations_ms={"rally": round(retained_ms, 3)},
        segments=list(segments),
        config=config_payload,
    )


def load_roi_polygon(path: Union[str, Path]) -> list[Tuple[float, float]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(point["x"]), float(point["y"])) for point in data.get("roi_polygon", [])]


def build_rally_segments_from_trace(
    trace_path: Union[str, Path],
    config: Optional[RallySegmentationConfig] = None,
) -> list[SceneSegment]:
    scene_config = (config or RallySegmentationConfig()).normalized()
    signal_builder = RallySignalBuilder(scene_config)
    signals: list[RallyFrameSignal] = []
    with Path(trace_path).open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            if "tracks" in payload:
                tracks = [_track_from_trace_dict(track) for track in payload["tracks"]]
                signals.append(signal_builder.build(payload["frame_id"], payload["time_ms"], tracks))
            else:
                signals.append(RallyFrameSignal(**payload["signal"]))
    return build_rally_segments_from_signals(signals, scene_config)


def _build_performance_stats(
    wall_time_s: float,
    source_duration_s: float,
    frames_read: int,
    frames_analyzed: int,
    sample_stride: int,
    detector_name: str,
    tracker_name: str,
    model_path: Optional[str],
    device: Optional[str],
    detections_total: int,
    tracks_total: int,
    segments_emitted: int,
    read_durations_s: Sequence[float],
    detect_durations_s: Sequence[float],
    track_signal_state_durations_s: Sequence[float],
    debug_render_durations_s: Sequence[float],
) -> RallySegmentationPerformance:
    return RallySegmentationPerformance(
        wall_time_s=round(wall_time_s, 3),
        source_duration_s=round(source_duration_s, 3),
        frames_read=frames_read,
        frames_analyzed=frames_analyzed,
        sample_stride=sample_stride,
        detector=detector_name,
        tracker=tracker_name,
        model_path=model_path,
        device=device,
        detections_total=detections_total,
        tracks_total=tracks_total,
        segments_emitted=segments_emitted,
        source_fps_processed=round(_safe_divide(frames_read, wall_time_s), 3),
        analyzed_fps=round(_safe_divide(frames_analyzed, wall_time_s), 3),
        realtime_factor=round(_safe_divide(source_duration_s, wall_time_s), 3),
        average_detections_per_frame=round(_safe_divide(detections_total, frames_analyzed), 3),
        average_tracks_per_frame=round(_safe_divide(tracks_total, frames_analyzed), 3),
        read_ms_avg=round(_average_ms(read_durations_s), 3),
        detect_ms_avg=round(_average_ms(detect_durations_s), 3),
        detect_ms_p95=round(_percentile_ms(detect_durations_s, 95), 3),
        track_signal_state_ms_avg=round(_average_ms(track_signal_state_durations_s), 3),
        debug_render_ms_avg=round(_average_ms(debug_render_durations_s), 3),
    )


def _detection_to_dict(detection: PlayerDetection) -> dict[str, Any]:
    return {
        "bbox": [
            round(detection.x1, 3),
            round(detection.y1, 3),
            round(detection.x2, 3),
            round(detection.y2, 3),
        ],
        "confidence": round(detection.confidence, 4),
        "track_id": detection.track_id,
        "foot_point": [round(detection.foot_point[0], 3), round(detection.foot_point[1], 3)],
    }


def _track_to_dict(track: TrackedPlayer) -> dict[str, Any]:
    return {
        "track_id": track.track_id,
        "bbox": [round(value, 3) for value in track.bbox],
        "confidence": round(track.confidence, 4),
        "foot_point": [round(track.foot_point[0], 3), round(track.foot_point[1], 3)],
        "frame_id": track.frame_id,
        "time_ms": round(track.time_ms, 3),
        "first_seen_ms": round(track.first_seen_ms, 3),
        "visible_count": track.visible_count,
        "visible_duration_ms": round(track.visible_duration_ms, 3),
        "speed_px_s": round(track.speed_px_s, 3),
        "acceleration_px_s2": round(track.acceleration_px_s2, 3),
    }


def _track_from_trace_dict(track: dict[str, Any]) -> TrackedPlayer:
    return TrackedPlayer(
        track_id=int(track["track_id"]),
        bbox=tuple(float(value) for value in track["bbox"]),
        confidence=float(track["confidence"]),
        foot_point=tuple(float(value) for value in track["foot_point"]),
        frame_id=int(track["frame_id"]),
        time_ms=float(track["time_ms"]),
        first_seen_ms=float(track["first_seen_ms"]),
        visible_count=int(track["visible_count"]),
        visible_duration_ms=float(track["visible_duration_ms"]),
        speed_px_s=float(track["speed_px_s"]),
        acceleration_px_s2=float(track["acceleration_px_s2"]),
    )


def _merge_close_rally_segments(
    segments: Sequence[SceneSegment],
    merge_gap_ms: float,
) -> list[SceneSegment]:
    if not segments:
        return []

    merged = [segments[0]]
    for segment in segments[1:]:
        previous = merged[-1]
        if segment.start_ms - previous.end_ms > merge_gap_ms:
            merged.append(segment)
            continue

        previous_duration = max(0.0, previous.end_ms - previous.start_ms)
        current_duration = max(0.0, segment.end_ms - segment.start_ms)
        total_duration = previous_duration + current_duration
        confidence = (
            (previous.confidence * previous_duration + segment.confidence * current_duration)
            / total_duration
            if total_duration > 0
            else max(previous.confidence, segment.confidence)
        )
        emitted_at_ms = max(
            previous.emitted_at_ms or previous.end_ms,
            segment.emitted_at_ms or segment.end_ms,
        )
        merged[-1] = SceneSegment(
            category="rally",
            start_ms=previous.start_ms,
            end_ms=segment.end_ms,
            confidence=round(confidence, 3),
            reason="person_tracking_state_machine",
            source_frame_range=[previous.source_frame_range[0], segment.source_frame_range[-1]],
            emitted_at_ms=round(emitted_at_ms, 3),
            latency_ms=round(max(0.0, emitted_at_ms - segment.end_ms), 3),
            boundary_reason="rally_merged_after_short_gap",
            signal_source="person_detection_tracking",
        )
    return merged


def _draw_box(
    cv2: Any,
    frame: Any,
    bbox: Tuple[float, float, float, float],
    color: Tuple[int, int, int],
    label: str,
) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in bbox]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    label_y = max(18, y1 - 6)
    cv2.putText(
        frame,
        label,
        (x1, label_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
        cv2.LINE_AA,
    )


def _bbox_iou(left: PlayerDetection, right: PlayerDetection) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection <= 0:
        return 0.0
    left_area = max(0.0, left.x2 - left.x1) * max(0.0, left.y2 - left.y1)
    right_area = max(0.0, right.x2 - right.x1) * max(0.0, right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _track_score(track: TrackedPlayer) -> float:
    return (
        track.visible_duration_ms
        + min(20, track.visible_count) * 50.0
        + track.confidence * 100.0
    )


def _point_in_polygon(
    point: Tuple[float, float],
    polygon: Sequence[Tuple[float, float]],
) -> bool:
    if len(polygon) < 3:
        return True
    x, y = point
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            slope_x = (previous_x - current_x) * (y - current_y) / (
                previous_y - current_y
            ) + current_x
            if x < slope_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _roi_midline_y(polygon: Optional[Sequence[Tuple[float, float]]]) -> Optional[float]:
    if not polygon:
        return None
    ys = [point[1] for point in polygon]
    return (min(ys) + max(ys)) / 2.0


def _bounded_ratio(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0
    return max(0.0, min(1.0, value / threshold))


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _flatten_values(value: Any) -> list[Any]:
    values = _to_list(value)
    if len(values) == 1 and isinstance(values[0], list):
        return values[0]
    return values


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _average_ms(values_s: Sequence[float]) -> float:
    if not values_s:
        return 0.0
    return sum(values_s) * 1000.0 / len(values_s)


def _percentile_ms(values_s: Sequence[float], percentile: float) -> float:
    if not values_s:
        return 0.0
    ordered = sorted(values_s)
    index = int(round((len(ordered) - 1) * percentile / 100.0))
    return ordered[max(0, min(len(ordered) - 1, index))] * 1000.0
