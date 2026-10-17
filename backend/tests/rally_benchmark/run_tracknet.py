#!/usr/bin/env python3
"""Local TrackNet experiment: no court detector, training, or downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from collections import deque
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.vision.tracknet_rally import FlightConfig, ShuttlePoint, ShuttleRallySegmenter, TrackNetPredictor
from app.vision.rally_stream import RallyStream, TimestampedFrame
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations


def camera_config(roi_path: Path) -> FlightConfig:
    roi = json.loads(roi_path.read_text())
    if roi["status"] != "verified":
        raise ValueError("This experiment requires the existing verified manual ROI.")
    width, height = roi["image_size"]["width"], roi["image_size"]["height"]
    corners = roi["court_keypoints"]["outer_corners"]
    # Expand upwards for flight; do not test the shuttle against a floor polygon.
    return FlightConfig(field=(
        max(0, min(p["x"] for p in corners) / width - .05),
        max(0, min(p["y"] for p in corners) / height - .4),
        min(1, max(p["x"] for p in corners) / width + .05),
        min(1, max(p["y"] for p in corners) / height + .02),
    ))


def infer(video: Path, output: Path, device: str, limit_s: float | None, roi_path: Path) -> dict:
    weights = ROOT / "models/SoloShuttlePose/src/models/weights/ball_track.pt"
    predictor = TrackNetPredictor(weights.parent.parent, device=device)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {video}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    width = capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise ValueError("Video must supply a valid CFR frame rate and dimensions.")
    segmenter = ShuttleRallySegmenter(predictor, width=width, height=height, config=camera_config(roi_path))
    stream = RallyStream(segmenter)
    intervals = []
    output.mkdir(parents=True, exist_ok=True)
    trace = output / "tracknet-points.jsonl"
    started = time.perf_counter()
    processing_s = 0.0
    index = 0
    try:
        with trace.open("w") as log, (output / "flight-diagnostics.jsonl").open("w") as diagnostic_log:
            while index < count and (limit_s is None or index / fps < limit_s):
                ok, image = capture.read()
                if not ok:
                    raise RuntimeError(f"Unexpected decode failure at frame {index}")
                frame = TimestampedFrame(index, index * 1000 / fps, image)
                tick = time.perf_counter()
                intervals.extend(stream.process(frame))
                processing_s += time.perf_counter() - tick
                for diagnostic in segmenter.last_diagnostics:
                    row = {key: diagnostic[key] for key in ("frame_id", "timestamp_ms", "x", "y", "confidence")}
                    row["available_at_ms"] = frame.timestamp_ms
                    log.write(json.dumps(row) + "\n")
                    diagnostic_log.write(json.dumps(diagnostic) + "\n")
                index += 1
                if index % 750 == 0:
                    print(f"Tracked {index / fps:.0f}s / {count / fps:.0f}s; wall {time.perf_counter() - started:.1f}s", flush=True)
    finally:
        capture.release()
    wall = time.perf_counter() - started
    result = dict(video=str(video), fps=fps, width=width, height=height, source_frame_count=count,
                  frames_processed=index, frames_with_observations=index - len(segmenter.pending),
                  device=device, wall_time_s=wall, processing_time_s=processing_s,
                  realtime_factor=(index / fps) / wall, weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                  preprocessing="RGB float/255, tensor antialiased bilinear 288x512, 3 consecutive frames / 9 channels",
                  decoder="largest >0.6 component box center; argmax retained when no component",
                  trace=str(trace), mode="frame -> model -> flight -> interval; no offline segmentation pass")
    (output / "inference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return save_results(output, result, intervals, segmenter, replay_wall_time_s=None)


def segment(output: Path, roi_path: Path) -> dict:
    metadata = json.loads((output / "inference.json").read_text())
    width, height = metadata["width"], metadata["height"]

    def cached_predict(rows):
        if any(row["available_at_ms"] > rows[-1]["timestamp_ms"] for row in rows):
            raise ValueError("Cache would use future frames.")
        return [ShuttlePoint(row["x"], row["y"], row["confidence"]) for row in rows]

    segmenter = ShuttleRallySegmenter(cached_predict, width=width, height=height, config=camera_config(roi_path))
    stream = RallyStream(segmenter)
    intervals, diagnostics = [], []
    started = time.perf_counter()
    with (output / "tracknet-points.jsonl").open() as log:
        for line in log:
            row = json.loads(line)
            intervals.extend(stream.process(TimestampedFrame(row["frame_id"], row["timestamp_ms"], row)))
            diagnostics.extend(segmenter.last_diagnostics)
    wall = time.perf_counter() - started
    with (output / "flight-diagnostics.jsonl").open("w") as log:
        for row in diagnostics:
            log.write(json.dumps(row) + "\n")
    return save_results(output, metadata, intervals, segmenter, replay_wall_time_s=wall)


def save_results(output, metadata, intervals, segmenter, *, replay_wall_time_s):
    if Path(metadata["video"]).resolve() != (ROOT / "datasets/badminton-v1/local/ysp/test_ysp.ts").resolve():
        raise ValueError("This seed runner's annotations belong to test_ysp.ts; another video needs its own benchmark.")
    annotations = load_rally_annotations(ROOT / "datasets/badminton-v1/annotations/seed/ysp/rally-segment-manual.json")
    result = dict(algorithm="tracknet-flight-v1", config=asdict(segmenter.config), predictions=[asdict(row) for row in intervals],
                  clips=[dict(rally_id=row.rally_id, start_ms=max(0, row.start_ms - 2000),
                              end_ms=min(metadata["source_frame_count"] * 1000 / metadata["fps"], row.end_ms + 1000)) for row in intervals],
                  clip_padding_ms=dict(before=2000, after=1000),
                  metrics=evaluate_rallies(intervals, annotations), replay_wall_time_s=replay_wall_time_s,
                  unfinished_candidate_at_eof=segmenter.start_ms is not None,
                  unfinished_rally_at_eof=segmenter.active,
                  sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (ROOT / "backend/app/vision/tracknet_rally.py", Path(__file__), output / "tracknet-points.jsonl")},
                  note="Observed-flight boundaries; clip padding independent. Existing seed labels unchanged. No EOF flush.")
    (output / "rallies.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    metrics = result["metrics"]
    print(json.dumps(dict(predictions=result["predictions"], missed=metrics["missed_rally_count"],
                         splits=metrics["false_split_count"], merges=metrics["false_merge_count"]), ensure_ascii=False))
    return result


def preview(output: Path, result: dict) -> None:
    metadata = json.loads((output / "inference.json").read_text())
    capture = cv2.VideoCapture(metadata["video"])
    size = (960, 540)
    writer = cv2.VideoWriter(str(output / "trajectory-preview.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), metadata["fps"], size)
    if not capture.isOpened() or not writer.isOpened():
        raise RuntimeError("Could not open preview input/output.")
    clips = result["clips"]
    clip_writers = [cv2.VideoWriter(str(output / f"rally-{row['rally_id']:02}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), metadata["fps"], size) for row in clips]
    if any(not item.isOpened() for item in clip_writers):
        raise RuntimeError("Could not open rally clip output.")
    tail = deque()
    try:
        with (output / "flight-diagnostics.jsonl").open() as log:
            for line in log:
                row = json.loads(line)
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Preview decode failed at {row['frame_id']}")
                frame = cv2.resize(frame, size)
                t = row["timestamp_ms"]
                while tail and t - tail[0][0] > 600:
                    tail.popleft()
                if row["valid"]:
                    pos = (int(row["x"] * size[0] / metadata["width"]), int(row["y"] * size[1] / metadata["height"]))
                    if tail and t - tail[-1][0] <= 120:
                        cv2.line(frame, tail[-1][1], pos, (0, 230, 255), 2)
                    tail.append((t, pos))
                for _, pos in tail:
                    cv2.circle(frame, pos, 3, (0, 230, 255), -1)
                status = "RALLY" if row["active"] else "CANDIDATE" if row["candidate"] else "IDLE"
                color = (0, 255, 0) if row["active"] else (0, 220, 255)
                cv2.rectangle(frame, (0, 0), (960, 52), (20, 20, 20), -1)
                cv2.putText(frame, f"t={t / 1000:.2f}s  {status}  confidence={row['confidence']:.2f}", (12, 34), 0, .8, color, 2)
                writer.write(frame)
                for clip, clip_writer in zip(clips, clip_writers):
                    if clip["start_ms"] <= t < clip["end_ms"]:
                        clip_writer.write(frame)
    finally:
        capture.release()
        writer.release()
        for item in clip_writers:
            item.release()
    print(f"Preview and {len(clips)} clips saved to {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=ROOT / "datasets/badminton-v1/local/ysp/test_ysp.ts")
    parser.add_argument("--output", type=Path, default=ROOT / "models/SoloShuttlePose/.runtime/tracknet-rally")
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument("--limit-s", type=float)
    parser.add_argument("--reuse-trace", action="store_true", help="Replay saved observations; do not run the model again")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--roi", type=Path, default=ROOT / "datasets/badminton-v1/annotations/seed/ysp/ROI.json")
    args = parser.parse_args()
    if args.reuse_trace:
        result = segment(args.output, args.roi)
    else:
        result = infer(args.video, args.output, args.device, args.limit_s, args.roi)
    if args.preview:
        preview(args.output, result)


if __name__ == "__main__":
    main()
