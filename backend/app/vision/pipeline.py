from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, Optional

from app.models import (
    CalibrationConfig,
    KeyframeEvent,
    RunRequest,
    SpeedSample,
    TrajectoryPoint,
)
from app.vision.calibration import CourtProjector
from app.vision.detectors import MotionDetector
from app.vision.speed import SpeedSmoother, compute_speed_between


async def analyze_source(
    session_id: str,
    request: RunRequest,
    calibration: CalibrationConfig,
) -> AsyncIterator[Dict[str, Any]]:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for video analysis. Run `python3 -m pip install -r backend/requirements.txt`."
        ) from exc

    source = request.source
    if source.source_type == "video_file":
        if not source.path:
            raise RuntimeError("A local video file path is required for video_file source.")
        capture_source: object = source.path
    else:
        capture_source = source.camera_index

    cap = cv2.VideoCapture(capture_source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source: {capture_source}")

    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    fps = source.fps or calibration.fps or native_fps or 120.0
    sample_stride = max(1, request.sample_stride)
    max_frames = request.max_frames
    projector = CourtProjector(calibration)
    detector = MotionDetector()
    smoother = SpeedSmoother(window_size=3)

    previous_point: Optional[TrajectoryPoint] = None
    last_keyframe_ms = -10_000.0
    frame_id = 0

    yield {
        "type": "session_status",
        "payload": {
            "session_id": session_id,
            "status": "running",
            "fps": fps,
            "source_type": source.source_type,
        },
    }

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_id += 1
            if max_frames is not None and frame_id > max_frames:
                break
            if frame_id % sample_stride != 0:
                continue

            detection = detector.detect(frame)
            if detection is None:
                if frame_id % 120 == 0:
                    await asyncio.sleep(0)
                continue

            time_ms = (frame_id / fps) * 1000.0
            world = projector.project(detection.pixel)
            point = TrajectoryPoint(
                frame_id=frame_id,
                time_ms=time_ms,
                pixel=detection.pixel,
                world=world,
                confidence=detection.confidence,
            )
            yield {"type": "trajectory_point", "payload": point}

            if previous_point is not None:
                computed = compute_speed_between(previous_point, point)
                if computed is not None:
                    raw_speed_kmh, confidence = computed
                    speed_kmh = smoother.push(raw_speed_kmh)
                    sample = SpeedSample(
                        time_ms=time_ms,
                        speed_kmh=round(speed_kmh, 2),
                        confidence=round(confidence, 3),
                        frame_start=previous_point.frame_id,
                        frame_end=point.frame_id,
                    )
                    yield {"type": "speed_sample", "payload": sample}

                    if (
                        request.save_keyframes
                        and speed_kmh >= 80.0
                        and time_ms - last_keyframe_ms >= 500.0
                    ):
                        keyframe = KeyframeEvent(
                            time_ms=time_ms,
                            frame_id=frame_id,
                            reason="speed_spike",
                            confidence=round(confidence, 3),
                        )
                        last_keyframe_ms = time_ms
                        yield {"type": "keyframe_event", "payload": keyframe}

            previous_point = point
            if frame_id % 120 == 0:
                await asyncio.sleep(0)
    finally:
        cap.release()
