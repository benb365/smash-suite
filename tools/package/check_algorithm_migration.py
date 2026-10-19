"""Check promoted prediction functions against saved, real experiment results."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def main():
    from app.algorithms.court_pipeline import pipeline
    from app.algorithms.refined_person import predict
    from app.algorithms import player_paths
    from app.vision.rally_stream import RallyStream, TimestampedFrame
    from app.vision.tracknet_rally import ShuttlePoint
    from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
    base = ROOT / "models/SoloShuttlePose/.runtime"
    report = {}
    profiles = json.loads((ROOT / "backend/app/algorithms/profiles.json").read_text())
    high = json.loads((ROOT / "docs/experiments/m1-a-return-threshold-20261016.json").read_text())
    report["high"] = {}
    for item in high["results"]:
        old = next(v for v in item["variants"] if v["name"] == "trajectory-uncertain-short-trial")
        assert profiles["high"] == old["config"], "A configuration drift"
        run = Path(item["run_result"])
        run = ROOT.joinpath(*run.parts[run.parts.index("models"):])
        segmenter = TrajectoryRallySegmenter(lambda points: points, width=1920, height=1080,
                                             config=TrajectoryConfig(**profiles["high"]))
        stream, predictions = RallyStream(segmenter), []
        for row in rows(run.parent / "flight-diagnostics.jsonl"):
            point = ShuttlePoint(row["x"], row["y"], row["confidence"])
            predictions.extend(asdict(p) for p in stream.process(TimestampedFrame(row["frame_id"], row["timestamp_ms"], point)))
        assert predictions == old["metrics"]["predictions"], "A prediction drift"
        assert segmenter.flight_decisions == old["flight_decisions"], "A decision drift"
        report["high"][item["sample"]["id"]] = dict(predictions=len(predictions), predictions_exact=True, decisions_exact=True)
    c = base / "c2-current-algorithm-20261018"
    people = rows(c / "relaxed-selection/C2/players.jsonl")
    native = rows(c / "observations/native.jsonl")
    shifted = rows(c / "observations/shifted.jsonl")
    flights = json.loads((c / "relaxed-selection/C2/flights.json").read_text())
    old = json.loads((c / "relaxed-selection/C2/predictions-before-scoring.json").read_text())
    predictions, trace = pipeline(native, shifted, people, flights)
    assert [asdict(p) for p in predictions] == old["predictions"], "C prediction drift"
    assert trace == old["decisions"], "C decision drift"
    features = rows(c / "replay/person-features.jsonl")
    seeds = player_paths.main_players(features[0]["boxes"])
    floor = min(b["y2"] - .5 * player_paths.height(b) for b in seeds)
    filtered, maps = [], []
    for row in features:
        ids = [i for i, b in enumerate(row["boxes"]) if b["y2"] >= floor]
        maps.append(ids)
        filtered.append(dict(row, boxes=[row["boxes"][i] for i in ids], features=[row["features"][i] for i in ids]))
    selected = player_paths.tracks(filtered, "appearance")
    for row, ids in zip(selected, maps):
        for person in row["players"]:
            person["box_index"] = ids[person["box_index"]]
    assert selected == people, "C player association drift"
    report["courtside"] = dict(predictions=len(predictions), predictions_exact=True, decisions_exact=True, people_exact=True)
    d = base / "d2-current-algorithm-20261018"
    old = json.loads((d / "result.json").read_text())
    with np.load(d / "flow/D2-01-signals.npz") as data:
        signals = {k: data[k] for k in data.files}
    predictions, trace = predict(signals, old["sample"]["duration_ms"], dict(ball_only_high=True, min_ball_events=2, min_high_events=1))
    assert [asdict(p) for p in predictions] == old["predictions"], "D prediction drift"
    assert trace == old["trace"], "D decision drift"
    report["personal"] = dict(predictions=len(predictions), predictions_exact=True, decisions_exact=True)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
