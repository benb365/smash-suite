#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.model_utils import model_to_dict  # noqa: E402
from app.models import SceneCandidate, SceneGateResult, SceneSegment  # noqa: E402
from app.vision.scene_gate import SceneGateConfig, run_scene_gate  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "data" / "samples" / "test001.mp4"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate.json"
DEFAULT_VALIDATION = (
    REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_validation_template.md"
)
DEFAULT_ROI_PREVIEW = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_roi_preview.jpg"
DEFAULT_MANUAL_SCENE = REPO_ROOT / "data" / "samples" / "manual_scene"
DEFAULT_EVAL_OUTPUT = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate_eval.json"
DEFAULT_EVAL_REPORT = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate_eval.md"
DEFAULT_TEST001_ROI = [
    (0.02, 1.0),
    (0.98, 1.0),
    (0.96, 0.63),
    (0.78, 0.55),
    (0.57, 0.52),
    (0.33, 0.55),
    (0.04, 0.64),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SceneGate baseline on test001.mp4.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validation-template", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--roi-preview", type=Path, default=DEFAULT_ROI_PREVIEW)
    parser.add_argument("--manual-scene", type=Path, default=DEFAULT_MANUAL_SCENE)
    parser.add_argument("--eval-output", type=Path, default=DEFAULT_EVAL_OUTPUT)
    parser.add_argument("--eval-report", type=Path, default=DEFAULT_EVAL_REPORT)
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--sample-stride", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--resize-width", type=int, default=360)
    parser.add_argument("--idle-motion-ratio", type=float, default=0.035)
    parser.add_argument("--smash-motion-ratio", type=float, default=0.115)
    parser.add_argument("--smash-component-area-ratio", type=float, default=0.05)
    parser.add_argument("--occlusion-motion-ratio", type=float, default=0.22)
    parser.add_argument("--occlusion-component-area-ratio", type=float, default=0.12)
    parser.add_argument("--smash-pre-roll-ms", type=float, default=800.0)
    parser.add_argument("--smash-post-roll-ms", type=float, default=1200.0)
    parser.add_argument("--min-rally-ms", type=float, default=4000.0)
    parser.add_argument("--min-idle-ms", type=float, default=3000.0)
    parser.add_argument(
        "--roi-polygon",
        type=str,
        default=None,
        help="JSON polygon such as '[[0,1],[1,1],[1,0.53],[0,0.54]]'.",
    )
    parser.add_argument("--no-default-roi", action="store_true")
    args = parser.parse_args()

    roi_polygon = parse_roi_polygon(args.roi_polygon)
    if roi_polygon is None and not args.no_default_roi:
        roi_polygon = DEFAULT_TEST001_ROI

    config = SceneGateConfig(
        sample_stride=args.sample_stride,
        max_frames=args.max_frames,
        resize_width=args.resize_width,
        idle_motion_ratio=args.idle_motion_ratio,
        smash_motion_ratio=args.smash_motion_ratio,
        smash_component_area_ratio=args.smash_component_area_ratio,
        occlusion_motion_ratio=args.occlusion_motion_ratio,
        occlusion_component_area_ratio=args.occlusion_component_area_ratio,
        smash_pre_roll_ms=args.smash_pre_roll_ms,
        smash_post_roll_ms=args.smash_post_roll_ms,
        min_rally_ms=args.min_rally_ms,
        min_idle_ms=args.min_idle_ms,
        roi_polygon=roi_polygon,
    )
    result = run_scene_gate(args.input, config)
    write_roi_preview(args.input, args.roi_preview, roi_polygon)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(model_to_dict(result), indent=2),
        encoding="utf-8",
    )
    args.validation_template.parent.mkdir(parents=True, exist_ok=True)
    args.validation_template.write_text(
        build_validation_template(result, args.output),
        encoding="utf-8",
    )

    category_counts = {}
    for segment in result.segments:
        category_counts[segment.category] = category_counts.get(segment.category, 0) + 1

    print(f"SceneGate result: {args.output}")
    print(f"Validation template: {args.validation_template}")
    print(f"ROI preview: {args.roi_preview}")
    print(f"Analyzed frames: {result.analyzed_frame_count} / {result.frame_count}")
    print(f"Segments: {len(result.segments)} {category_counts}")
    print(f"Retained ratio: {result.retained_ratio:.2%}")
    print(f"Smash candidates: {len(result.smash_candidates)}")
    print(f"Smash candidate ratio: {result.smash_candidate_ratio:.2%}")

    if not args.skip_evaluation and args.manual_scene.exists():
        from evaluate_manual_scene import build_report, evaluate_scene_gate_file

        metrics = evaluate_scene_gate_file(args.manual_scene, args.output)
        args.eval_output.parent.mkdir(parents=True, exist_ok=True)
        args.eval_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        args.eval_report.parent.mkdir(parents=True, exist_ok=True)
        args.eval_report.write_text(
            build_report(metrics, args.manual_scene, args.output),
            encoding="utf-8",
        )
        print(f"SceneGate evaluation JSON: {args.eval_output}")
        print(f"SceneGate evaluation report: {args.eval_report}")
        print(
            "Evaluation: "
            f"precision {metrics['precision']:.2%}, recall {metrics['recall']:.2%}, "
            f"F1 {metrics['f1']:.2%}, manual hit rate {metrics['manual_hit_rate']:.2%}"
        )
    return 0


def build_validation_template(result: SceneGateResult, output_path: Path) -> str:
    rally_segments = [segment for segment in result.segments if segment.category == "rally"]
    lines = [
        "# SceneGate test001 manual validation",
        "",
        "This file is generated by `backend/tests/scene_gate/run_test001.py`.",
        "Fill in the manual review fields after watching the source video.",
        "",
        "## Run Summary",
        "",
        f"- Source video: `{result.video_path}`",
        f"- SceneGate JSON: `{output_path}`",
        f"- FPS: `{result.fps}`",
        f"- Duration: `{format_ms(result.duration_ms)}`",
        f"- Analyzed frames: `{result.analyzed_frame_count}` / `{result.frame_count}`",
        f"- Segment count: `{len(result.segments)}`",
        f"- Rally retained ratio: `{result.retained_ratio:.2%}`",
        f"- Smash candidate count: `{len(result.smash_candidates)}`",
        f"- Smash candidate ratio: `{result.smash_candidate_ratio:.2%}`",
        f"- Category durations: `{result.category_durations_ms}`",
        "",
        "## Algorithm Rally Segments",
        "",
        *_format_segments(rally_segments),
        "",
        "## Nested Smash Candidate Intervals",
        "",
        *_format_candidates(result.smash_candidates),
        "",
        "## Manual Review",
        "",
        "- Reviewer:",
        "- Review date:",
        "- Manual smash intervals:",
        "- Algorithm hit intervals:",
        "- Missed smash intervals:",
        "- False positive intervals:",
        "- Keep ratio acceptable for demo: yes/no",
        "- Notes:",
        "",
        "## Review Guidance",
        "",
        "1. Watch `data/samples/test001.mp4` locally.",
        "2. Confirm the ROI preview only covers the relevant court area.",
        "3. Record visible rally and smash/high-speed candidate intervals above.",
        "4. Compare manual intervals with the generated rally and nested smash_candidate intervals.",
        "5. Mark clear misses, false positives, and occlusion-caused failures before tuning thresholds.",
    ]
    return "\n".join(lines) + "\n"


def _format_segments(segments: Iterable[SceneSegment]) -> list[str]:
    rows = list(segments)
    if not rows:
        return ["- None"]
    return [
        (
            f"- `{format_ms(segment.start_ms)}` - `{format_ms(segment.end_ms)}` "
            f"frames `{segment.source_frame_range[0]}-{segment.source_frame_range[1]}` "
            f"confidence `{segment.confidence}` reason `{segment.reason}` "
            f"smash_candidates `{len(segment.smash_candidates)}`"
        )
        for segment in rows
    ]


def _format_candidates(candidates: Iterable[SceneCandidate]) -> list[str]:
    rows = list(candidates)
    if not rows:
        return ["- None"]
    return [
        (
            f"- `{format_ms(candidate.start_ms)}` - `{format_ms(candidate.end_ms)}` "
            f"frames `{candidate.source_frame_range[0]}-{candidate.source_frame_range[1]}` "
            f"parent_segment `{candidate.parent_segment_index}` "
            f"confidence `{candidate.confidence}` reason `{candidate.reason}`"
        )
        for candidate in rows
    ]


def format_ms(value: float) -> str:
    total_ms = int(round(value))
    minutes, remainder = divmod(total_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def parse_roi_polygon(raw_value: Optional[str]) -> Optional[list[tuple[float, float]]]:
    if raw_value is None:
        return None
    data = json.loads(raw_value)
    return [(float(point[0]), float(point[1])) for point in data]


def write_roi_preview(
    input_path: Path,
    output_path: Path,
    roi_polygon: Optional[list[tuple[float, float]]],
) -> None:
    if not roi_polygon:
        return
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return

    cap = cv2.VideoCapture(str(input_path))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return

    height, width = frame.shape[:2]
    points = np.array(
        [(int(round(x * width)), int(round(y * height))) for x, y in roi_polygon],
        dtype=np.int32,
    )
    overlay = frame.copy()
    cv2.fillPoly(overlay, [points], (0, 180, 255))
    frame = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
    cv2.polylines(frame, [points], isClosed=True, color=(0, 255, 255), thickness=4)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), frame)


if __name__ == "__main__":
    raise SystemExit(main())
