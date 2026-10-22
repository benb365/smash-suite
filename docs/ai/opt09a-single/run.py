from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
INPUTS = ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json"
VARIANTS = ("native", "shifted")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_helper():
    path = ROOT / "docs/ai/opt07a/recognition.py"
    spec = importlib.util.spec_from_file_location("_opt09a_opt07a_recognition", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, path


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError(f"expected one observe derivation point: {old!r}")
    return source.replace(old, new)


def derive_observe_source(source: str, variant: str) -> str:
    if variant not in VARIANTS:
        raise ValueError(f"unsupported candidate: {variant}")
    source = replace_once(
        source,
        'if phase == 0 or (phase == 1 and camera_type == "courtside"):\n',
        "if phase == 0:\n" if variant == "native" else "if phase == 1 or queue[0].frame_id == 0:\n",
    )
    old_return = (
        '    stats.add("native_observations", len(native))\n'
        '    stats.add("shifted_observations", len(shifted))\n'
        "    return [native[k] for k in sorted(native)], [shifted[k] for k in sorted(shifted)], features\n"
    )
    selection = "chosen = {**shifted, **native}" if variant == "native" else "chosen = shifted"
    new_return = (
        '    stats.add("native_observations", len(native))\n'
        '    stats.add("shifted_observations", len(shifted))\n'
        f"    {selection}\n"
        "    rows = [chosen[k] for k in sorted(chosen)]\n"
        "    return rows, rows, features\n"
    )
    return replace_once(source, old_return, new_return)


def canonical_json_sha(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--inputs", type=Path, default=INPUTS)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")

    package = importlib.import_module("modules.models.tracknet")
    parent_predictor = package.TrackNetPredictor
    instances = []

    class RecordingPredictor(parent_predictor):
        def __init__(self, *values, **options):
            super().__init__(*values, **options)
            self.calls = []
            instances.append(self)

        def __call__(self, frames, *, frame_ids=None):
            points = super().__call__(frames, frame_ids=frame_ids)
            self.calls.append({
                "frame_ids": list(frame_ids) if frame_ids is not None else None,
                "points": [dict(x=point.x, y=point.y, confidence=point.confidence) for point in points],
                "candidate_count_by_frame": [len(row["peaks"]) for row in self.last_candidates],
            })
            return points

    package.TrackNetPredictor = RecordingPredictor
    recognize = importlib.import_module("modules.rally.recognize")
    recognize.TrackNetPredictor = RecordingPredictor
    source_path = Path(inspect.getsourcefile(recognize.observe)).resolve()
    if source_path != (ROOT / "modules/rally/recognize.py").resolve():
        raise AssertionError(f"recognize loaded outside task worktree: {source_path}")
    derived = derive_observe_source(inspect.getsource(recognize.observe), args.variant)
    derived_path = args.output / "derived_observe.py"
    namespace = recognize.__dict__
    exec(compile(derived, str(derived_path), "exec"), namespace)
    derived_observe = recognize.observe
    capture = {}

    def recording_observe(*values, **options):
        first, second, features = derived_observe(*values, **options)
        stream_a = [(row["frame_id"], row["timestamp_ms"]) for row in first]
        stream_b = [(row["frame_id"], row["timestamp_ms"]) for row in second]
        if stream_a != stream_b:
            raise AssertionError("downstream observation streams differ")
        predictor = instances[-1]
        by_id = {row["frame_id"]: row for row in first}
        windows = [{
            "frame_ids": call["frame_ids"],
            "timestamps_ms": [by_id[index]["timestamp_ms"] for index in call["frame_ids"]],
            "points": call["points"],
            "candidate_count_by_frame": call["candidate_count_by_frame"],
        } for call in predictor.calls]
        capture.update(
            selected_observations=first,
            selected_frame_ids=[row["frame_id"] for row in first],
            selected_timestamps_ms=[row["timestamp_ms"] for row in first],
            downstream_streams_equal=True,
            people_features_sha256=canonical_json_sha(features),
            people_feature_count=len(features),
            model_windows=windows,
            model_call_count=len(predictor.calls),
            actual_predictor_class=f"{RecordingPredictor.__module__}.{RecordingPredictor.__qualname__}",
            parent_predictor_class=f"{parent_predictor.__module__}.{parent_predictor.__qualname__}",
        )
        return first, second, features

    recognize.observe = recording_observe
    helper, helper_path = load_helper()
    production_predictor = ROOT / "modules/models/tracknet/predictor.py"
    helper_args = [
        "recognition.py", "--variant", "candidate", "--case", "C-short",
        "--inputs", str(args.inputs), "--models", str(args.models),
        "--reference-source", str(production_predictor), "--output", str(args.output),
    ]
    original_argv = sys.argv
    try:
        sys.argv = helper_args
        helper.main()
    finally:
        sys.argv = original_argv
        if args.output.is_dir():
            derived_path.write_text(derived, encoding="utf-8")
            if capture:
                helper.write_json(args.output / "observations.json", capture)
            run_path = args.output / "run.json"
            if run_path.is_file():
                run = json.loads(run_path.read_text(encoding="utf-8"))
                run.update(
                    opt09a_variant=args.variant,
                    opt09a_runner_path=str(Path(__file__).resolve()),
                    opt09a_runner_sha256=sha256(Path(__file__)),
                    helper_runner_path=str(helper_path.resolve()),
                    helper_runner_sha256=sha256(helper_path),
                    derived_observe_path=str(derived_path),
                    derived_observe_sha256=sha256(derived_path),
                    actual_predictor_class=capture.get("actual_predictor_class"),
                    parent_predictor_class=capture.get("parent_predictor_class"),
                )
                helper.write_json(run_path, run)


if __name__ == "__main__":
    main()
