#!/usr/bin/env python3
"""Compare frozen M1 trial candidates using native-PTS TrackNet run artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions
from app.vision.rally_stream import RallyInterval

# Fixed before opening the held-out clip predictions. These are trial candidates,
# not an accepted architecture or a claim that detected flight equals a rally.
CANDIDATES = [
    dict(name="streaming-flight-v1", mode="streaming"),
    dict(name="offline-motion-v1-gap1600", mode="offline", gap_ms=1600,
         min_span_ms=2200, min_observations=3),
    dict(name="offline-motion-v1-gap2400", mode="offline", gap_ms=2400,
         min_span_ms=2200, min_observations=3),
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def offline_intervals(diagnostics: list[dict], config: dict, eof_ms: float) -> list[RallyInterval]:
    """Group observed motion with whole-file context; retain only supported spans.

    The online candidate requires a consecutive three-observation streak. This
    experiment admits sparse motion across a bounded gap and finalizes at EOF.
    It never fills a position or extrapolates a landing after the last motion.
    """
    groups: list[list[dict]] = []
    for row in diagnostics:
        if not row["motion"]:
            continue
        if not groups or row["timestamp_ms"] - groups[-1][-1]["timestamp_ms"] > config["gap_ms"]:
            groups.append([])
        groups[-1].append(row)
    intervals = []
    for rows in groups:
        if len(rows) < config["min_observations"]:
            continue
        start, end = rows[0]["timestamp_ms"], rows[-1]["timestamp_ms"]
        if end - start >= config["min_span_ms"]:
            intervals.append(RallyInterval(len(intervals) + 1, start, end, eof_ms))
    return intervals


def retained_time(predictions, truth, exclusions, duration_ms: float) -> dict:
    """Measure unions once, masking confirmed excluded time from both sides."""
    intervals = [(r.start_ms, r.end_ms) for r in predictions]
    targets = [(r.start_ms, r.end_ms) for r in truth if r.review_status == "verified"]
    ignored = [tuple(e["range_ms"]) for e in exclusions]
    breaks = sorted({0.0, duration_ms, *(max(0.0, min(duration_ms, x))
                     for row in intervals + targets + ignored for x in row)})
    totals = dict(target_ms=0.0, retained_target_ms=0.0, non_target_ms=0.0,
                  retained_non_target_ms=0.0, ignored_ms=0.0)
    for start, end in zip(breaks, breaks[1:]):
        midpoint = (start + end) / 2
        target = any(a <= midpoint < b for a, b in targets)
        prediction = any(a <= midpoint < b for a, b in intervals)
        excluded = not target and any(a <= midpoint < b for a, b in ignored)
        span = end - start
        if excluded:
            totals["ignored_ms"] += span
        elif target:
            totals["target_ms"] += span
            totals["retained_target_ms"] += span * prediction
        else:
            totals["non_target_ms"] += span
            totals["retained_non_target_ms"] += span * prediction
    return dict(**totals,
                target_retention=(totals["retained_target_ms"] / totals["target_ms"]
                                  if totals["target_ms"] else None),
                non_target_retention=(totals["retained_non_target_ms"] / totals["non_target_ms"]
                                      if totals["non_target_ms"] else None))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--stage", choices=("tuning", "check"), required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lock", type=Path, help="Required candidate lock from tuning for check stage")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; use a fresh path to preserve evidence")
    manifest = json.loads(args.manifest.read_text())
    code_sha = sha(Path(__file__))
    evaluator_sha = sha(ROOT / "backend/app/vision/rally_eval.py")
    if args.stage == "check":
        if args.lock is None:
            parser.error("Check stage requires --lock from tuning")
        lock = json.loads(args.lock.read_text())
        if (lock["candidates"] != CANDIDATES or lock["code_sha256"] != code_sha
                or lock["evaluator_sha256"] != evaluator_sha
                or lock["manifest_sha256"] != sha(args.manifest)):
            parser.error("Candidate, code, evaluator or manifest changed since tuning lock")
    results = []
    for sample in manifest["samples"]:
        if sample["split"] != args.stage:
            continue
        video, annotation = ROOT / sample["video"], ROOT / sample["annotation"]
        if sha(video) != sample["video_sha256"] or sha(annotation) != sample["annotation_sha256"]:
            raise ValueError(f"Input changed: {sample['id']}")
        directory = args.runs / sample["id"] / "01-01-clip"
        run_path = directory / "result.json"
        run = json.loads(run_path.read_text())
        provenance_path = args.runs / sample["id"] / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        if (provenance["sha256"]["video"] != sample["video_sha256"]
                or any(provenance["sha256"][key] != value
                       for key, value in manifest["inference_sha256"].items())
                or run["config"] != manifest["baseline_config"]):
            raise ValueError("Inference provenance or configuration differs from frozen trial")
        diagnostics_path = directory / "flight-diagnostics.jsonl"
        diagnostics = [json.loads(line) for line in diagnostics_path.read_text().splitlines()]
        if run["status"] != "completed" or Path(run["video"]) != video.resolve():
            raise ValueError("Run failed or belongs to another video")
        if run["input"]["frames_delivered"] != sample["native_frame_count"]:
            raise ValueError("Run did not consume the full native input")
        # Verified on A1-04: input can end with 1/2 real frames buffered by the
        # existing three-frame model. Keep this gap visible, never invent points.
        pending = run["pending_model_frames"]
        if (pending not in (0, 1, 2)
                or len(diagnostics) != sample["native_frame_count"] - pending
                or [row["frame_id"] for row in diagnostics] != list(range(len(diagnostics)))):
            raise ValueError("Observation coverage differs from the recorded three-frame buffer")
        truth, exclusions = load_rally_annotations(annotation), load_rally_exclusions(annotation)
        variants = []
        for config in CANDIDATES:
            tick = time.perf_counter()
            if config["mode"] == "streaming":
                predictions = [RallyInterval(**row) for row in run["predictions"]]
            else:
                predictions = offline_intervals(diagnostics, config, run["input"]["last_timestamp_ms"])
            postprocess_s = time.perf_counter() - tick
            metrics = evaluate_rallies(predictions, truth, excluded_events=exclusions)
            variants.append(dict(candidate=config, metrics=metrics,
                                 retained_time=retained_time(predictions, truth, exclusions, sample["duration_ms"]),
                                 postprocess_wall_s=postprocess_s,
                                 output_latency_applicable=config["mode"] == "streaming"))
        results.append(dict(sample=sample, run_result=str(run_path), run_sha256=sha(run_path),
                            provenance=provenance, provenance_sha256=sha(provenance_path),
                            diagnostics_sha256=sha(diagnostics_path), inference_config=run["config"],
                            observation_count=len(diagnostics), unobserved_tail_frames=pending,
                            unobserved_tail_ms=(run["input"]["last_timestamp_ms"]
                                                - diagnostics[-1]["timestamp_ms"]),
                            inference_wall_s=run["wall_time_s"], memory_samples=run["memory_samples"],
                            realtime_factor=sample["duration_ms"] / 1000 / run["wall_time_s"],
                            variants=variants))
    report = dict(status="same_source_diagnostic_not_independent_acceptance", stage=args.stage,
                  manifest=str(args.manifest), manifest_sha256=sha(args.manifest),
                  code_sha256=code_sha, evaluator_sha256=evaluator_sha, candidates=CANDIDATES,
                  inference_reused=True, latency_note="Offline emitted_at is EOF bookkeeping, not live latency.",
                  coverage_note="Uses conservative representative boundaries; non-target complement is provisional.",
                  check_lock_sha256=sha(args.lock) if args.lock else None, results=results)
    args.output.mkdir(parents=True)
    (args.output / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.stage == "tuning":
        (args.output / "candidate-lock.json").write_text(json.dumps({key: report[key] for key in
            ("manifest_sha256", "code_sha256", "evaluator_sha256", "candidates")}, indent=2) + "\n")
    for sample in results:
        print(sample["sample"]["id"], [(row["candidate"]["name"], row["metrics"]["prediction_count"],
              row["metrics"]["missed_rally_count"], row["metrics"]["false_positive_count"])
              for row in sample["variants"]])


if __name__ == "__main__":
    main()
