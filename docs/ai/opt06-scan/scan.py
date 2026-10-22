"""One-pass diagnostic scan of the first three frames in each source second."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
THRESHOLD = 0.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_frames(frames, predict):
    """Infer on each source second's first three adjacent frames, retaining metadata only."""
    groups, incomplete = [], []
    second, bucket = None, []

    def infer(rows, source_second):
        if [f.frame_id for f in rows] != list(range(rows[0].frame_id, rows[0].frame_id + 3)):
            raise ValueError("sampled frames are not adjacent source frames")
        points = predict([f.image for f in rows])
        groups.append({
            "source_second": source_second,
            "frame_ids": [f.frame_id for f in rows],
            "timestamps_ms": [f.timestamp_ms for f in rows],
            "frames": [{"confidence": float(p.confidence), "positive": float(p.confidence) >= THRESHOLD}
                       for p in points],
        })

    for frame in frames:
        current_second = int(frame.timestamp_ms // 1000)
        if second is not None and current_second != second:
            if len(bucket) < 3:
                incomplete.append([{"frame_id": f.frame_id, "timestamp_ms": f.timestamp_ms} for f in bucket])
            bucket = []
        second = current_second
        if len(bucket) < 3:
            bucket.append(frame)
            if len(bucket) == 3:
                infer(bucket, second)
    if len(bucket) < 3:
        incomplete.append([{"frame_id": f.frame_id, "timestamp_ms": f.timestamp_ms} for f in bucket])
    return groups, incomplete


def interval_coverage(samples, intervals):
    """Count sampled confidence hits in half-open source-time intervals."""
    output = []
    for index, bounds in enumerate(intervals):
        start, end = (float(bounds[0]), float(bounds[1])) if isinstance(bounds, list) else (
            float(bounds["start_ms"]), float(bounds["end_ms"]))
        inside = [sample for sample in samples if start <= sample["timestamp_ms"] < end]
        hits = [sample for sample in inside if sample["confidence"] >= THRESHOLD]
        maximum = max(inside, key=lambda sample: sample["confidence"], default=None)
        output.append({
            "index": index, "start_ms": start, "end_ms": end,
            "sample_count": len(inside), "hit_count": len(hits), "hit": bool(hits),
            "hit_timestamps_ms": [sample["timestamp_ms"] for sample in hits],
            "max_confidence": maximum["confidence"] if maximum else None,
            "max_timestamp_ms": maximum["timestamp_ms"] if maximum else None,
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--case", required=True, choices=("A-short", "C-short", "D-short"))
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError(f"Run from worktree root: {ROOT}")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "case_id": args.case}
    outer_start = time.perf_counter()
    try:
        sys.path.insert(0, str(ROOT))
        manifest = json.loads(args.inputs.read_text())
        item = next((row for row in manifest["cases"] if row["case_id"] == args.case), None)
        if item is None or item["status"] != "passed":
            raise ValueError("input case is missing or not passed")
        video = Path(item["video"])
        reference = json.loads(args.reference.read_text())
        video_hash = sha256(video)
        if video_hash != item["sha256"] or video_hash != reference["video_sha256"]:
            raise ValueError("video SHA-256 does not match manifest and reference")
        if reference["case_id"] != args.case:
            raise ValueError("reference case_id does not match requested case")

        from modules.models.assets import ASSETS
        from modules.rally.statistics import Statistics
        from modules.media.video_input import FileFrameSource
        from modules.models.tracknet import TrackNetPredictor
        from modules.models.tracknet.model import TrackNet
        import cv2
        import torch
        import av
        import numpy
        import torchvision

        module_paths = {name: str(Path(sys.modules[module.__module__].__file__).resolve())
                        for name, module in (("FileFrameSource", FileFrameSource),
                                             ("TrackNetPredictor", TrackNetPredictor), ("TrackNet", TrackNet))}
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

        scan_start = time.perf_counter()
        with statistics.mps_sampling():
            with FileFrameSource(video, mode="offline") as source:
                groups, incomplete = scan_frames(source, predictor)
                source_stats = dict(source.stats)
        scan_wall_s = time.perf_counter() - scan_start
        statistics.source("opt06_scan", source_stats)
        if source_stats["frames_decoded"] == 0 or source_stats["frames_delivered"] != source_stats["frames_decoded"]:
            raise RuntimeError("FileFrameSource did not deliver every decoded frame")
        if source_stats.get("expected_frames") and source_stats["frames_decoded"] != source_stats["expected_frames"]:
            raise RuntimeError("FileFrameSource frame count differs from container expectation")

        samples = [{"timestamp_ms": timestamp, **frame}
                   for group in groups for timestamp, frame in zip(group["timestamps_ms"], group["frames"])]
        raw_coverage = interval_coverage(samples, reference["predictions"])
        export_coverage = interval_coverage(samples, reference["export_ranges"])
        report.update({
            "status": "completed", "case_id": args.case,
            "worktree": str(ROOT), "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "module_paths": module_paths,
            "input": {"manifest": str(args.inputs.resolve()), "video": str(video.resolve()), "video_sha256": video_hash},
            "reference": {"path": str(args.reference.resolve()), "sha256": sha256(args.reference),
                          "provenance": reference["provenance"], "predictions": reference["predictions"],
                          "export_ranges": reference["export_ranges"]},
            "code": {name: sha256(ROOT / name) for name in (
                "docs/ai/opt06-scan/scan.py", "modules/media/video_input.py",
                "modules/models/tracknet/predictor.py", "modules/models/tracknet/model.py",
                "modules/models/assets.py", "modules/rally/statistics.py")},
            "weight": {"path": str(weight.resolve()), "bytes": asset["bytes"], "sha256": asset["sha256"]},
            "config": {"sample_frames_per_second": 3, "model_input_size": [288, 512],
                       "threshold": THRESHOLD, "device": "mps",
                       "torch_threads": torch.get_num_threads(), "opencv_threads": cv2.getNumThreads(),
                       "python": platform.python_version(), "torch": torch.__version__, "opencv": cv2.__version__,
                       "av": av.__version__, "numpy": numpy.__version__, "torchvision": torchvision.__version__},
            "groups": groups, "incomplete_tail": incomplete, "source_stats": source_stats,
            "raw_prediction_coverage": raw_coverage, "export_range_coverage": export_coverage,
            "statistics": {"seconds": dict(statistics.seconds), "counts": dict(statistics.counts),
                           "mps_samples": statistics.mps},
            "timing": {"model_setup_s": model_setup_s, "scan_wall_s": scan_wall_s,
                       "outer_wall_s": time.perf_counter() - outer_start,
                       "outer_wall_boundary": "includes validation, import, model setup, scan and report assembly; excludes final JSON write; scan_wall_s excludes setup"},
            "max_rss": {"value": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        "unit": "bytes on macOS"},
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["outer_wall_s"] = time.perf_counter() - outer_start
        (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        raise
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
