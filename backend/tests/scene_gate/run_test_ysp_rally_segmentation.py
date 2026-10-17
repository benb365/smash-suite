#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.vision.rally_segmentation import (  # noqa: E402
    OpenCVHogPersonDetector,
    RallySegmentationConfig,
    UltralyticsByteTrackProvider,
    UltralyticsPersonDetector,
    build_rally_segments_from_trace,
    load_roi_polygon,
    run_rally_segmentation,
)
from app.vision.scene_eval import (  # noqa: E402
    ManualAnnotationNotVerifiedError,
    evaluate_rally_boundaries,
    load_manual_rally_annotations,
    scene_gate_rally_intervals,
)


DEFAULT_VIDEO = REPO_ROOT / "datasets/badminton-v1/local/ysp/test_ysp.ts"
DEFAULT_ROI = REPO_ROOT / "datasets/badminton-v1/annotations/seed/ysp/ROI.json"
DEFAULT_MANUAL = REPO_ROOT / "datasets/badminton-v1/annotations/seed/ysp/rally-segment-manual.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / "models/yolo11n/.runtime/scene_gate" / "test_ysp_rally_segmentation.json"
)
DEFAULT_EVAL = (
    REPO_ROOT / "models/yolo11n/.runtime/scene_gate" / "test_ysp_rally_segmentation_eval.json"
)
DEFAULT_STATS = (
    REPO_ROOT / "models/yolo11n/.runtime/scene_gate" / "test_ysp_rally_segmentation_perf.json"
)
DEFAULT_DEBUG_VIDEO = (
    REPO_ROOT / "models/yolo11n/.runtime/scene_gate" / "test_ysp_rally_segmentation_debug.mp4"
)
DEFAULT_TRACE = (
    REPO_ROOT / "models/yolo11n/.runtime/scene_gate" / "test_ysp_rally_segmentation_trace.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fixed-camera rally segmentation streaming simulator on test_ysp.ts."
    )
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--roi", type=Path, default=DEFAULT_ROI)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--eval-output", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--stats-output", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--detector-fps", type=float, default=10.0)
    parser.add_argument(
        "--detector",
        choices=["yolo-bytetrack", "hog", "yolo"],
        default="yolo-bytetrack",
    )
    parser.add_argument("--yolo-model", default=str(REPO_ROOT / "models/yolo11n/yolo11n.pt"))
    parser.add_argument("--yolo-device", default=None)
    parser.add_argument("--yolo-image-size", type=int, default=None)
    parser.add_argument("--tracker-config", default="bytetrack.yaml")
    parser.add_argument("--sample-stride", type=int, default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--stable-visible-ms", type=float, default=None)
    parser.add_argument("--active-speed-px-s", type=float, default=None)
    parser.add_argument("--active-acceleration-px-s2", type=float, default=None)
    parser.add_argument("--active-window-ms", type=float, default=None)
    parser.add_argument("--start-guard-ms", type=float, default=None)
    parser.add_argument("--end-guard-ms", type=float, default=None)
    parser.add_argument("--end-confirm-ms", type=float, default=None)
    parser.add_argument("--merge-gap-ms", type=float, default=None)
    parser.add_argument("--min-rally-ms", type=float, default=None)
    parser.add_argument("--write-debug-video", action="store_true")
    parser.add_argument("--debug-video-output", type=Path, default=DEFAULT_DEBUG_VIDEO)
    parser.add_argument("--debug-resize-width", type=int, default=960)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument("--replay-trace", type=Path, default=None)
    parser.add_argument("--evaluate-boundaries", action="store_true")
    args = parser.parse_args()

    roi_polygon = load_roi_polygon(args.roi)
    roi_status = _json_status(args.roi)
    if roi_status != "verified":
        print(f"ROI warning: {args.roi} status is {roi_status!r}; using it as a draft ROI.")

    config = _build_config(args, roi_polygon)
    if args.replay_trace is not None:
        segments = build_rally_segments_from_trace(args.replay_trace, config)
        result = _build_replay_result(args.video, args.replay_trace, config, segments)
    else:
        detector, tracking_provider = _build_providers(args)
        result = run_rally_segmentation(
            args.video,
            config=config,
            detector=detector,
            tracking_provider=tracking_provider,
            debug_video_path=args.debug_video_output if args.write_debug_video else None,
            debug_video_resize_width=args.debug_resize_width,
            trace_path=None if args.no_trace else args.trace_output,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    performance = result.config.get("performance", {})
    args.stats_output.parent.mkdir(parents=True, exist_ok=True)
    args.stats_output.write_text(json.dumps(performance, indent=2), encoding="utf-8")
    print(f"Rally segmentation JSON: {args.output}")
    print(f"Performance JSON: {args.stats_output}")
    if not args.no_trace and args.replay_trace is None:
        print(f"Frame trace JSONL: {args.trace_output}")
    if args.replay_trace is not None:
        print(f"Replayed frame trace JSONL: {args.replay_trace}")
    if args.write_debug_video:
        print(f"Debug video: {args.debug_video_output}")
    print(
        f"Segments: {len(result.segments)}, retained: {result.retained_ratio:.2%}, "
        f"analyzed frames: {result.analyzed_frame_count}"
    )
    if performance:
        print(
            "Runtime: "
            f"{performance['wall_time_s']:.2f}s, "
            f"analyzed FPS: {performance['analyzed_fps']:.2f}, "
            f"realtime factor: {performance['realtime_factor']:.2f}x, "
            f"detect avg/p95: {performance['detect_ms_avg']:.1f}/"
            f"{performance['detect_ms_p95']:.1f}ms"
        )

    if not args.evaluate_boundaries:
        print("Boundary evaluation skipped. Add --evaluate-boundaries after manual labels are verified.")
        return 0

    try:
        manual = load_manual_rally_annotations(args.manual, require_verified=True)
    except ManualAnnotationNotVerifiedError as exc:
        print(f"Boundary evaluation blocked: {exc}")
        return 2

    metrics = evaluate_rally_boundaries(
        predicted=scene_gate_rally_intervals(result.model_dump()),
        manual=manual,
    )
    args.eval_output.parent.mkdir(parents=True, exist_ok=True)
    args.eval_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Boundary evaluation JSON: {args.eval_output}")
    print(
        "Containment: "
        f"{metrics['containment_rate']:.2%}, "
        f"2s boundary pass: {metrics['boundary_pass_rate_2s']:.2%}, "
        f"missed: {metrics['missed_rally_count']}"
    )
    return 0


def _json_status(path: Path) -> str:
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "missing"
    return str(data.get("status", "unknown"))


def _build_providers(args: argparse.Namespace):
    if args.detector == "yolo-bytetrack":
        return None, UltralyticsByteTrackProvider(
            model_path=args.yolo_model,
            tracker_config=args.tracker_config,
            device=args.yolo_device,
            image_size=args.yolo_image_size,
        )
    if args.detector == "yolo":
        return UltralyticsPersonDetector(
            model_path=args.yolo_model,
            device=args.yolo_device,
            image_size=args.yolo_image_size,
        ), None
    return OpenCVHogPersonDetector(), None


def _build_config(args: argparse.Namespace, roi_polygon) -> RallySegmentationConfig:
    defaults = RallySegmentationConfig(
        detector_fps=args.detector_fps,
        sample_stride=args.sample_stride,
        max_frames=args.max_frames,
        roi_polygon=roi_polygon,
    )
    overrides = {
        "stable_visible_ms": args.stable_visible_ms,
        "active_speed_px_s": args.active_speed_px_s,
        "active_acceleration_px_s2": args.active_acceleration_px_s2,
        "active_window_ms": args.active_window_ms,
        "start_guard_ms": args.start_guard_ms,
        "end_guard_ms": args.end_guard_ms,
        "end_confirm_ms": args.end_confirm_ms,
        "merge_gap_ms": args.merge_gap_ms,
        "min_rally_ms": args.min_rally_ms,
    }
    values = {
        key: (value if overrides.get(key) is None else overrides[key])
        for key, value in defaults.__dict__.items()
    }
    return RallySegmentationConfig(**values)


def _build_replay_result(
    video_path: Path,
    trace_path: Path,
    config: RallySegmentationConfig,
    segments,
):
    import cv2  # type: ignore

    from app.vision.rally_segmentation import build_rally_scene_gate_result

    cap = cv2.VideoCapture(str(video_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    duration_ms = (frame_count / fps) * 1000.0 if frame_count else 0.0
    analyzed_count = _count_jsonl_lines(trace_path)
    sample_stride = config.sample_stride or max(1, int(round(fps / config.detector_fps)))
    return build_rally_scene_gate_result(
        video_path=video_path,
        fps=fps,
        frame_count=frame_count,
        duration_ms=duration_ms,
        analyzed_frame_count=analyzed_count,
        sample_stride=sample_stride,
        segments=segments,
        config=config,
        detector_name="trace_replay",
        tracker_name="trace_replay",
        model_path=None,
        device=None,
        trace_path=trace_path,
    )


def _count_jsonl_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
