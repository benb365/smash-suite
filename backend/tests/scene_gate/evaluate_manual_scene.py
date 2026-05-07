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

from app.vision.scene_eval import (  # noqa: E402
    evaluate_intervals,
    parse_manual_scene_intervals,
    scene_gate_rally_intervals,
)


DEFAULT_MANUAL = REPO_ROOT / "data" / "samples" / "manual_scene"
DEFAULT_SCENE_GATE = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate.json"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate_eval.json"
DEFAULT_REPORT = REPO_ROOT / "data" / "exports" / "scene_gate" / "test001_scene_gate_eval.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate SceneGate rally intervals against manual_scene annotations."
    )
    parser.add_argument("--manual-scene", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--scene-gate", type=Path, default=DEFAULT_SCENE_GATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--tolerance-ms", type=float, default=1000.0)
    parser.add_argument("--min-false-positive-ms", type=float, default=1000.0)
    args = parser.parse_args()

    metrics = evaluate_scene_gate_file(
        manual_scene_path=args.manual_scene,
        scene_gate_path=args.scene_gate,
        tolerance_ms=args.tolerance_ms,
        min_false_positive_ms=args.min_false_positive_ms,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(metrics, args.manual_scene, args.scene_gate), encoding="utf-8")

    print(f"SceneGate evaluation JSON: {args.output}")
    print(f"SceneGate evaluation report: {args.report}")
    print(
        "Precision: "
        f"{metrics['precision']:.2%}, Recall: {metrics['recall']:.2%}, "
        f"F1: {metrics['f1']:.2%}, manual hit rate: {metrics['manual_hit_rate']:.2%}"
    )
    return 0


def evaluate_scene_gate_file(
    manual_scene_path: Path,
    scene_gate_path: Path,
    tolerance_ms: float = 1000.0,
    min_false_positive_ms: float = 1000.0,
) -> dict[str, Any]:
    manual = parse_manual_scene_intervals(manual_scene_path.read_text(encoding="utf-8"))
    scene_gate = json.loads(scene_gate_path.read_text(encoding="utf-8"))
    predicted = scene_gate_rally_intervals(scene_gate)
    metrics = evaluate_intervals(
        predicted=predicted,
        manual=manual,
        tolerance_ms=tolerance_ms,
        min_false_positive_ms=min_false_positive_ms,
    )
    metrics["manual_scene_path"] = str(manual_scene_path)
    metrics["scene_gate_path"] = str(scene_gate_path)
    return metrics


def build_report(metrics: dict[str, Any], manual_scene_path: Path, scene_gate_path: Path) -> str:
    lines = [
        "# SceneGate manual_scene evaluation",
        "",
        f"- Manual annotations: `{manual_scene_path}`",
        f"- SceneGate output: `{scene_gate_path}`",
        f"- Tolerance: `{metrics['tolerance_ms']}ms`",
        f"- Manual intervals: `{metrics['manual_count']}`",
        f"- Predicted rally intervals: `{metrics['predicted_count']}`",
        f"- Manual duration: `{metrics['manual_duration_ms'] / 1000:.2f}s`",
        f"- Predicted duration: `{metrics['predicted_duration_ms'] / 1000:.2f}s`",
        f"- Precision: `{metrics['precision']:.2%}`",
        f"- Recall: `{metrics['recall']:.2%}`",
        f"- F1: `{metrics['f1']:.2%}`",
        f"- Tolerant IoU: `{metrics['tolerant_iou']:.2%}`",
        f"- Manual hit rate: `{metrics['manual_hit_rate']:.2%}`",
        f"- False positive duration: `{metrics['false_positive_ms'] / 1000:.2f}s`",
        f"- Missed manual duration: `{metrics['missed_manual_ms'] / 1000:.2f}s`",
        "",
        "## Missed Manual Intervals",
        "",
        *_format_interval_list(metrics["missed_manual_intervals"]),
        "",
        "## False Positive Intervals",
        "",
        *_format_interval_list(metrics["false_positive_intervals"]),
        "",
        "## Interpretation",
        "",
        "This evaluation is automated, but it is not a replacement for watching the video.",
        "The manual labels have about 1s boundary noise, so use the metrics to compare",
        "algorithm versions rather than as absolute product quality.",
    ]
    return "\n".join(lines) + "\n"


def _format_interval_list(intervals: list[dict[str, Any]]) -> list[str]:
    if not intervals:
        return ["- None"]
    return [
        f"- `{interval['start']}` - `{interval['end']}` ({interval['duration_ms'] / 1000:.2f}s)"
        for interval in intervals
    ]


if __name__ == "__main__":
    raise SystemExit(main())
