"""CLI workflows for collecting and analyzing high-view trajectory inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.media.video import probe
from modules.models.assets import digest


def _progress(message, fraction):
    print(f"{message}: {fraction:.0%}", flush=True)


def _weights(directory):
    directory = Path(directory)
    weights = {name: directory / name for name in ("ball_track.pt", "yolo11n.pt")}
    missing = [str(path) for path in weights.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing model weights: " + ", ".join(missing))
    return weights


def _reusable(point_path, source, model_path, rallies_path):
    meta_path = point_path.with_suffix(".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rallies = json.loads(rallies_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (meta.get("complete") is not True
            or meta.get("source_sha256") != digest(source)
            or meta.get("model_sha256") != digest(model_path)
            or not point_path.is_file()
            or meta.get("frame_count") != sum(1 for line in point_path.open(encoding="utf-8") if line.strip())
            or not isinstance(rallies, dict)
            or not isinstance(rallies.get("predictions"), list)
            or "details" not in rallies):
        return None
    return rallies


def capture(video: Path, output: Path, weights_dir: Path):
    video, output = Path(video), Path(output)
    weights = _weights(weights_dir)
    point_path = output / "ball-observations.jsonl"
    rallies_path = output / "rallies.json"
    reusable = _reusable(point_path, video, weights["ball_track.pt"], rallies_path)
    if reusable is not None:
        print(f"Reusing complete observations and rally results in {output}", flush=True)
        return reusable

    from modules.rally.recognize import recognize
    from .observations import ObservationLog

    output.mkdir(parents=True, exist_ok=True)
    info = probe(video, video.name)
    with ObservationLog(point_path, source=video, info=info, weight=weights["ball_track.pt"]) as sink:
        predictions, details = recognize(
            video, info, "high", weights, _progress, output, observation_sink=sink)
    result = {"predictions": predictions, "details": details}
    rallies_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def analyze(video: Path, observations: Path, rallies: Path, output: Path, weights_dir: Path):
    from modules.trajectory import analyze as analyze_trajectory

    video, observations, rallies, output = map(Path, (video, observations, rallies, output))
    weights = _weights(weights_dir)
    payload = json.loads(rallies.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("predictions"), list):
        raise ValueError("Rally input must contain a predictions list.")
    info = probe(video, video.name)
    output.mkdir(parents=True, exist_ok=True)
    return analyze_trajectory(video, info, payload["predictions"], observations,
                              weights, output, _progress)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture or analyze badminton shuttle trajectories.")
    commands = parser.add_subparsers(dest="command", required=True)
    capture_parser = commands.add_parser("capture", help="Run high-view rally recognition and save TrackNet observations.")
    capture_parser.add_argument("--video", type=Path, required=True)
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--weights-dir", type=Path, required=True)
    analyze_parser = commands.add_parser("analyze", help="Analyze frozen observations without running TrackNet.")
    analyze_parser.add_argument("--video", type=Path, required=True)
    analyze_parser.add_argument("--observations", type=Path, required=True)
    analyze_parser.add_argument("--rallies", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    analyze_parser.add_argument("--weights-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "capture":
        capture(args.video, args.output, args.weights_dir)
    else:
        analyze(args.video, args.observations, args.rallies, args.output, args.weights_dir)


if __name__ == "__main__":
    main()
