"""Optimistic A-short TrackNet cost replay; this does not run rally recognition."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

from scan import ROOT, sha256


def group_is_candidate(frames, ranges):
    return any(start <= frame.timestamp_ms < end
               for frame in frames for start, end in ranges)


def consume_groups(frames, predict, variant, ranges):
    executed, skipped, tail, total = [], 0, [], 0
    group = []

    def process(rows):
        nonlocal skipped, total
        if [frame.frame_id for frame in rows] != list(range(total, total + 3)):
            raise ValueError("source frames are not consecutive native three-frame groups")
        start_id = rows[0].frame_id
        total += 3
        if variant == "candidate" and not group_is_candidate(rows, ranges):
            skipped += 1
            return
        points = predict([frame.image for frame in rows])
        if len(points) != 3:
            raise RuntimeError("TrackNet did not return three points for an executed group")
        executed.append(start_id)

    for frame in frames:
        group.append(frame)
        if len(group) == 3:
            process(group)
            group = []
    if group:
        tail = [{"frame_id": frame.frame_id, "timestamp_ms": frame.timestamp_ms} for frame in group]
        if [frame.frame_id for frame in group] != list(range(total, total + len(group))):
            raise ValueError("source tail frame IDs are not consecutive")
    return total, executed, skipped, tail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True, choices=("full", "candidate"))
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError(f"Run from worktree root: {ROOT}")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "case_id": "A-short", "variant": args.variant}
    try:
        sys.path.insert(0, str(ROOT))
        manifest = json.loads(args.inputs.read_text())
        case = next((row for row in manifest["cases"] if row["case_id"] == "A-short"), None)
        if case is None or case["status"] != "passed":
            raise ValueError("A-short input is missing or not passed")
        video = Path(case["video"])
        video_sha = sha256(video)
        if video_sha != case["sha256"]:
            raise ValueError("A-short media SHA-256 does not match inputs manifest")

        candidate_path = ROOT / "apps/video-clipper/reports/opt06-scan/candidate-coverage.json"
        candidate_hash, candidate_ranges = None, None
        if args.variant == "candidate":
            candidate_hash = sha256(candidate_path)
            coverage = json.loads(candidate_path.read_text())
            candidate_ranges = next(row["candidate_ranges_ms"] for row in coverage["cases"]["A-short"]["variants"]
                                    if row["padding_each_side_ms"] == 3000)
            candidate_ranges = [(float(start), float(end)) for start, end in candidate_ranges]

        from modules.media.video_input import FileFrameSource
        from modules.models.assets import ASSETS
        from modules.models.tracknet import TrackNetPredictor
        from modules.models.tracknet.model import TrackNet
        from modules.rally.statistics import Statistics
        import av
        import cv2
        import numpy
        import torch
        import torchvision

        module_paths = {name: str(Path(sys.modules[module.__module__].__file__).resolve())
                        for name, module in (("FileFrameSource", FileFrameSource),
                                             ("TrackNetPredictor", TrackNetPredictor), ("TrackNet", TrackNet))}
        module_paths["scan_helpers"] = str(Path(sys.modules["scan"].__file__).resolve())
        for name, path in module_paths.items():
            if not Path(path).is_relative_to(ROOT):
                raise RuntimeError(f"module imported outside worktree: {name}: {path}")
        asset = ASSETS["ball_track.pt"]
        weight = args.models / "ball_track.pt"
        if not weight.is_file() or weight.stat().st_size != asset["bytes"] or sha256(weight) != asset["sha256"]:
            raise ValueError("cached ball_track.pt is missing or does not match ASSETS")
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable; CPU fallback is forbidden")
        torch.set_num_threads(4)
        cv2.setNumThreads(1)
        statistics = Statistics(enabled=True)
        setup_start = time.perf_counter()
        predictor = TrackNetPredictor(weight=weight, device="mps", record_candidates=False,
                                      statistics=statistics)
        model_setup_s = time.perf_counter() - setup_start

        replay_start = time.perf_counter()
        with statistics.mps_sampling():
            with FileFrameSource(video, mode="offline") as source:
                total_frames, executed, skipped, tail = consume_groups(
                    source, predictor, args.variant, candidate_ranges or [])
                source_stats = dict(source.stats)
        replay_wall_s = time.perf_counter() - replay_start
        if not source_stats["frames_decoded"] or source_stats["frames_delivered"] != source_stats["frames_decoded"]:
            raise RuntimeError("FileFrameSource did not deliver every decoded frame")
        if source_stats.get("expected_frames") and source_stats["frames_decoded"] != source_stats["expected_frames"]:
            raise RuntimeError("FileFrameSource frame count differs from container expectation")
        if source_stats["frames_decoded"] != total_frames + len(tail):
            raise RuntimeError("native frame grouping count does not match full decoded source")
        statistics.source("tracknet_replay", source_stats)
        report.update({
            "status": "completed", "worktree": str(ROOT),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "input": {"manifest": str(args.inputs.resolve()), "video": str(video.resolve()),
                      "video_sha256": video_sha},
            "weight": {"path": str(weight.resolve()), "bytes": asset["bytes"], "sha256": asset["sha256"]},
            "modules": module_paths,
            "code_sha256": {name: sha256(ROOT / name) for name in (
                "docs/ai/opt06-scan/replay_tracknet.py", "docs/ai/opt06-scan/scan.py",
                "modules/media/video_input.py",
                "modules/models/tracknet/predictor.py", "modules/models/tracknet/model.py",
                "modules/models/assets.py", "modules/rally/statistics.py")},
            "candidate_rule": None if args.variant == "full" else {
                "source": str(candidate_path), "source_sha256": candidate_hash,
                "expansion_each_side_ms": 3000, "ranges_ms": candidate_ranges,
                "gate": "call TrackNet if any actual timestamp in native group is in [start,end)"},
            "config": {"device": "mps", "torch_threads": torch.get_num_threads(),
                       "opencv_threads": cv2.getNumThreads(), "model_input_size": [288, 512],
                       "python": platform.python_version(), "torch": torch.__version__,
                       "opencv": cv2.__version__, "av": av.__version__, "numpy": numpy.__version__,
                       "torchvision": torchvision.__version__},
            "source_stats": source_stats, "source_frames": source_stats["frames_decoded"],
            "complete_grouped_frames": total_frames,
            "native_three_frame_windows": total_frames // 3,
            "executed_windows": len(executed), "skipped_windows": skipped,
            "executed_window_start_frame_ids": executed, "incomplete_tail": tail,
            "statistics": {"seconds": dict(statistics.seconds), "counts": dict(statistics.counts),
                           "mps_samples": statistics.mps},
            "timing": {"model_setup_s": model_setup_s, "replay_wall_s": replay_wall_s,
                       "accounting": "setup is separate; replay wall covers full EOF source iteration and inference; predictor timings nest within replay"},
            "max_rss": {"value": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        "unit": "bytes on macOS"},
            "scope": "Optimistic TrackNet cost only; omits rally decisions and person/action analysis, produces no rally output, and measures no accuracy or product skipping.",
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        raise
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
