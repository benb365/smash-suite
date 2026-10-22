"""Compute candidate windows from saved OPT-06 scan positives; never runs inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CASES = ("A-short", "C-short", "D-short")
PADDINGS_MS = (1000, 2000, 3000, 5000)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def merge_candidates(samples, duration_ms, padding_ms):
    ranges = []
    for sample in samples:
        if sample["confidence"] >= 0.5:
            at = float(sample["timestamp_ms"])
            ranges.append([max(0.0, at - padding_ms), min(float(duration_ms), at + padding_ms)])
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def uncovered_ranges(start_ms, end_ms, candidates):
    gaps, cursor = [], float(start_ms)
    for start, end in candidates:
        if end <= cursor or start >= end_ms:
            continue
        if start > cursor:
            gaps.append([cursor, min(start, end_ms)])
        cursor = max(cursor, end)
        if cursor >= end_ms:
            break
    if cursor < end_ms:
        gaps.append([cursor, float(end_ms)])
    return gaps


def interval_coverage(intervals, candidates):
    rows = []
    for index, bounds in enumerate(intervals):
        start, end = (float(bounds[0]), float(bounds[1])) if isinstance(bounds, list) else (
            float(bounds["start_ms"]), float(bounds["end_ms"]))
        gaps = uncovered_ranges(start, end, candidates)
        rows.append({"index": index, "start_ms": start, "end_ms": end,
                     "fully_covered": not gaps, "uncovered_subintervals": gaps})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "apps/video-clipper/reports/opt06-scan/candidate-coverage.json")
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise RuntimeError(f"Run from worktree root: {ROOT}")
    output = args.output.resolve()
    report_dir = output.parent
    inputs = {case: ROOT / "apps/video-clipper/.runtime/opt06-scan" / case / "report.json"
              for case in CASES}
    copied = {case: report_dir / f"{case}.json" for case in CASES}
    targets = [output, *copied.values()]
    if any(path.exists() for path in targets):
        raise FileExistsError("candidate output or copied scan report already exists")
    for path in inputs.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    sys.path.insert(0, str(ROOT))
    from modules.media.video import probe

    case_reports = {}
    source_hashes = {}
    for case, source in inputs.items():
        scan = json.loads(source.read_text())
        if scan.get("status") != "completed" or scan.get("case_id") != case:
            raise ValueError(f"scan report is incomplete or mismatched: {source}")
        source_hashes[case] = sha256(source)
        video_path = Path(scan["input"]["video"])
        video_info = probe(video_path, video_path.name)
        samples = [{"timestamp_ms": timestamp, **frame}
                   for group in scan["groups"]
                   for timestamp, frame in zip(group["timestamps_ms"], group["frames"])]
        positives = [sample for sample in samples if sample["confidence"] >= 0.5]
        positive_groups = sum(any(frame["confidence"] >= 0.5 for frame in group["frames"])
                              for group in scan["groups"])
        variants = []
        for padding in PADDINGS_MS:
            ranges = merge_candidates(positives, video_info.duration_ms, padding)
            kept_ms = sum(end - start for start, end in ranges)
            variants.append({
                "padding_each_side_ms": padding, "candidate_ranges_ms": ranges,
                "kept_duration_ms": kept_ms, "kept_duration_ratio": kept_ms / video_info.duration_ms,
                "skippable_source_duration_ms": video_info.duration_ms - kept_ms,
                "prediction_coverage": interval_coverage(scan["reference"]["predictions"], ranges),
                "export_range_coverage": interval_coverage(scan["reference"]["export_ranges"], ranges),
            })
        case_reports[case] = {
            "scan_report": {"path": str(source), "sha256": source_hashes[case]},
            "video": {"path": str(video_path), "duration_ms": video_info.duration_ms,
                      "first_pts_ms": video_info.first_pts_ms, "width": video_info.width,
                      "height": video_info.height, "metadata_source": "modules.media.video.probe"},
            "scan_cost_observation": scan["timing"],
            "sampled_groups": len(scan["groups"]), "positive_groups": positive_groups,
            "sampled_frames": len(samples), "positive_frames": len(positives),
            "variants": variants,
        }

    report = {
        "schema_version": 1, "purpose": "candidate-window calculation only; no analysis frames skipped",
        "worktree": str(ROOT), "git_head": __import__("subprocess").check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "rule": {"positive_sample": "confidence >= 0.5", "expansion_each_side_ms": list(PADDINGS_MS),
                 "clip_to": "[0, probed duration_ms]", "merge": "overlapping or touching intervals",
                 "coverage": "whole interval must lie in candidate union; uncovered gaps listed"},
        "interpretation": "Intervals and retained-time ratios are candidate geometry only; low-confidence gaps are unknown, not negatives, and ratios are not runtime savings or accuracy.",
        "cases": case_reports,
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    for case, source in inputs.items():
        shutil.copyfile(source, copied[case])
        if sha256(source) != sha256(copied[case]):
            raise RuntimeError(f"byte-for-byte scan report copy failed: {case}")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
