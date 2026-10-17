#!/usr/bin/env python3
"""Run the existing TrackNet candidate through offline or paced file input."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions
from app.vision.rally_stream import RallyStream
from app.vision.tracknet_rally import FlightConfig, ShuttleRallySegmenter, TrackNetPredictor
from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
from app.vision.video_input import FileFrameSource
from run_tracknet import camera_config


class BatchLog:
    def __init__(self, path: Path):
        self.file = path.open("w", encoding="utf-8")
        self.rows: list[str] = []

    def write(self, row: dict) -> None:
        self.rows.append(json.dumps(row) + "\n")
        if len(self.rows) >= 300:
            self.flush()

    def flush(self) -> None:
        self.file.writelines(self.rows)
        self.rows.clear()
        self.file.flush()

    def close(self) -> None:
        self.flush()
        self.file.close()


def memory_sample(predictor) -> dict:
    rss = int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True))
    row = dict(rss_mib=rss / 1024)
    if predictor.device == "mps":
        row["mps_allocated_mib"] = predictor.torch.mps.current_allocated_memory() / 2**20
        row["mps_driver_mib"] = predictor.torch.mps.driver_allocated_memory() / 2**20
    return row


def run_file(video: Path, output: Path, predictor, *, mode: str, config: FlightConfig,
             limit_s: float | None, max_lag_s: float, annotations: Path | None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = FileFrameSource(video, mode=mode, limit_s=limit_s, max_lag_s=max_lag_s)
    logs = {name: BatchLog(output / f"{name}.jsonl")
            for name in ("tracknet-points", "flight-diagnostics", "performance", "rally-intervals")}
    if getattr(predictor, "record_candidates", False):
        logs["shuttle-candidates"] = BatchLog(output / "shuttle-candidates.jsonl")
    digest = hashlib.sha256()
    predictions, emissions, memory = [], [], []
    segmenter = None
    status, error = "completed", None
    totals = dict(process_s=0.0, preprocess_s=0.0, inference_and_transfer_s=0.0,
                  point_decode_s=0.0, max_batch_process_s=0.0, queue_wait_s=0.0)
    started = time.monotonic()
    last_report = started - 30
    try:
        with source:
            for frame in source:
                if segmenter is None:
                    height, width = frame.image.shape[:2]
                    segmenter_type = (TrajectoryRallySegmenter if isinstance(config, TrajectoryConfig)
                                      else ShuttleRallySegmenter)
                    segmenter = segmenter_type(predictor, width=width, height=height, config=config)
                    stream = RallyStream(segmenter)
                digest.update(struct.pack("!qd", frame.frame_id, frame.timestamp_ms))
                tick = time.monotonic()
                intervals = stream.process(frame)
                processed_at = time.monotonic()
                process_s = processed_at - tick
                totals["process_s"] += process_s
                totals["queue_wait_s"] += source.last_delivery["queue_wait_s"]
                wall_ms = (processed_at - source.started_at) * 1000
                if segmenter.last_diagnostics:
                    timing = predictor.last_timing
                    for key in timing:
                        totals[key] += timing[key]
                    totals["max_batch_process_s"] = max(totals["max_batch_process_s"], process_s)
                    logs["performance"].write(dict(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms,
                                                   wall_ms=wall_ms, process_s=process_s,
                                                   **source.last_delivery, **timing))
                    for point_index, diagnostic in enumerate(segmenter.last_diagnostics):
                        row = {key: diagnostic[key] for key in ("frame_id", "timestamp_ms", "x", "y", "confidence")}
                        row["available_at_ms"] = frame.timestamp_ms
                        logs["tracknet-points"].write(row)
                        logs["flight-diagnostics"].write(diagnostic)
                        if "shuttle-candidates" in logs:
                            logs["shuttle-candidates"].write(dict(
                                frame_id=diagnostic['frame_id'], timestamp_ms=diagnostic['timestamp_ms'],
                                **predictor.last_candidates[point_index]))
                # Keep the failed batch's timings/points for diagnosis, but do
                # not publish an interval after the input deadline was violated.
                source.check_health()
                predictions.extend(intervals)
                for interval in intervals:
                    # Intervals are the result, so flush each immediately; only
                    # frame diagnostics use the larger log batch.
                    logs["rally-intervals"].write(asdict(interval))
                    logs["rally-intervals"].flush()
                    published_ms = (time.monotonic() - source.started_at) * 1000
                    emissions.append(dict(rally_id=interval.rally_id, wall_ms=published_ms,
                                          observed_end_to_output_ms=published_ms - interval.end_ms if mode == "realtime" else None,
                                          confirmation_source_ms=interval.emitted_at_ms - interval.end_ms))
                    print(json.dumps(dict(event="rally", interval=asdict(interval), wall_ms=published_ms)), flush=True)
                if processed_at - last_report >= 30:
                    memory.append(dict(wall_s=processed_at - started, **memory_sample(predictor)))
                    print(f"{video.name}: {frame.timestamp_ms / 1000:.1f}s, {mode}, "
                          f"lag={source.stats['max_lag_s']:.3f}s, RSS={memory[-1]['rss_mib']:.0f}MiB", flush=True)
                    last_report = processed_at
    except Exception as exc:
        status, error = "failed", dict(type=type(exc).__name__, message=str(exc))
    finally:
        for log in logs.values():
            log.close()
    wall_s = time.monotonic() - started
    memory.append(dict(wall_s=wall_s, **memory_sample(predictor)))
    result = dict(video=str(video.resolve()), mode=mode, status=status, error=error,
                  config=asdict(config), input=source.stats, timestamp_digest=digest.hexdigest(),
                  wall_time_s=wall_s, totals=totals, memory_samples=memory,
                  predictions=[asdict(row) for row in predictions], emissions=emissions,
                  unfinished_candidate=segmenter is not None and segmenter.start_ms is not None,
                  unfinished_rally=segmenter is not None and segmenter.active,
                  pending_model_frames=len(segmenter.pending) if segmenter else 0)
    if isinstance(segmenter, TrajectoryRallySegmenter):
        result.update(segmenter="trajectory-top-v1", trajectory_events=segmenter.events,
                      flight_decisions=segmenter.flight_decisions)
    if mode == "offline":
        result["realtime_factor"] = source.stats.get("last_timestamp_ms", 0) / 1000 / wall_s
    if annotations is not None:
        truth = load_rally_annotations(annotations)
        covered_until = source.stats.get("last_delivered_timestamp_ms", -1)
        covered_truth = [row for row in truth if 0 <= row.start_ms <= row.end_ms <= covered_until]
        evaluation = evaluate_rallies(predictions, covered_truth,
                                      excluded_events=load_rally_exclusions(annotations))
        evaluation["outside_input_coverage_ids"] = [row.rally_id for row in truth if row not in covered_truth]
        emission_by_id = {row["rally_id"]: row for row in emissions}
        actual_by_id = {row.rally_id: row for row in covered_truth}
        evaluation["wall_latency_from_truth_end_ms"] = [dict(
            truth_id=row["truth_id"], prediction_id=row["prediction_id"],
            latency_ms=emission_by_id[row["prediction_id"]]["wall_ms"] - actual_by_id[row["truth_id"]].end_ms,
        ) for row in evaluation["matches"]] if mode == "realtime" else []
        result["evaluation"] = evaluation
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), status=status, error=error,
                          frames=source.stats["frames_delivered"], rallies=len(predictions), wall_s=wall_s)), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("offline", "realtime"), default="realtime")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--limit-s", type=float)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-lag-s", type=float, default=5)
    parser.add_argument("--config", type=Path, help="Explicit config JSON for the selected segmenter and one source")
    parser.add_argument("--segmenter", choices=("baseline", "trajectory"), default="baseline")
    parser.add_argument("--annotations", type=Path, help="Matching human annotations for one source")
    parser.add_argument("--record-candidates", action="store_true",
                        help="Record alternative heatmap peaks without changing original points")
    args = parser.parse_args()
    if args.repeat < 1 or ((args.config or args.annotations) and len(args.video) != 1):
        parser.error("repeat must be positive; explicit config/annotations require one video")
    weights = ROOT / "models/SoloShuttlePose/src/models/weights/ball_track.pt"
    predictor = TrackNetPredictor(weights.parent.parent, device=args.device,
                                  record_candidates=args.record_candidates)
    import numpy as np
    warmup = time.monotonic()
    predictor([np.zeros((288, 512, 3), dtype=np.uint8) for _ in range(3)])
    warmup_s = time.monotonic() - warmup
    results = []
    args.output.mkdir(parents=True, exist_ok=True)
    for repeat in range(args.repeat):
        for index, video in enumerate(args.video):
            seed = video.resolve() == (ROOT / "datasets/badminton-v1/local/ysp/test_ysp.ts").resolve()
            config_type = TrajectoryConfig if args.segmenter == "trajectory" else FlightConfig
            config = (config_type(**json.loads(args.config.read_text())) if args.config else
                      TrajectoryConfig() if args.segmenter == "trajectory" else
                      camera_config(ROOT / "datasets/badminton-v1/annotations/seed/ysp/ROI.json") if seed else FlightConfig())
            annotations = args.annotations or (ROOT / "datasets/badminton-v1/annotations/seed/ysp/rally-segment-manual.json" if seed else None)
            output = args.output / f"{repeat + 1:02d}-{index + 1:02d}-{video.stem}"
            result = run_file(video, output, predictor, mode=args.mode, config=config,
                              limit_s=args.limit_s, max_lag_s=args.max_lag_s, annotations=annotations)
            results.append(dict(result_path=str(output / "result.json"), status=result["status"],
                                wall_s=result["wall_time_s"], memory=result["memory_samples"][-1]))
            summary = dict(device=args.device, mode=args.mode, warmup_s=warmup_s,
                           weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(), runs=results)
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            if result["status"] != "completed":
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
