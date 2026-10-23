from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

PREDICTOR = ROOT / "modules/models/tracknet/predictor.py"
RECOGNITION = ROOT / "docs/ai/opt07a/recognition.py"
SIZES = {"288x512": (288, 512), "216x384": (216, 384), "144x256": (144, 256)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_source(source: str, size: str) -> str:
    height, width = SIZES[size]
    old_resize = "resize(tensor, [288, 512], antialias=True)"
    new_resize = f"resize(tensor, [{height}, {width}], antialias=True)"
    old_scale = "x * frame.shape[1] / 512, y * frame.shape[0] / 288"
    new_scale = "x * frame.shape[1] / heatmap.shape[1], y * frame.shape[0] / heatmap.shape[0]"
    for old in (old_resize, old_scale):
        if source.count(old) != 1:
            raise AssertionError(f"expected exactly one derivation point {old!r}, got {source.count(old)}")
    derived = source.replace(old_resize, new_resize).replace(old_scale, new_scale)
    return derived + '''\n\n# Lightweight per-call observations for the size experiment.\nOPT08A_OBSERVATIONS = []\n_Opt08ABasePredictor = TrackNetPredictor\nclass TrackNetPredictor(_Opt08ABasePredictor):\n    def __call__(self, frames, *, frame_ids=None):\n        points = super().__call__(frames, frame_ids=frame_ids)\n        OPT08A_OBSERVATIONS.append({\n            "call_index": len(OPT08A_OBSERVATIONS),\n            "frame_ids": list(frame_ids) if frame_ids is not None else None,\n            "input_frames": len(frames),\n            "points": [dict(x=p.x, y=p.y, confidence=p.confidence) for p in points],\n        })\n        return points\n'''


def import_helper():
    spec = importlib.util.spec_from_file_location("_opt07a_recognition", RECOGNITION)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=tuple(SIZES), required=True)
    parser.add_argument("--case", choices=("A-short",), default="A-short")
    parser.add_argument("--inputs", type=Path, default=ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output directory already exists: {args.output}")

    source = PREDICTOR.read_text(encoding="utf-8")
    derived = derive_source(source, args.size)
    helper = import_helper()
    original_argv = sys.argv
    helper_error = None
    try:
        with tempfile.TemporaryDirectory(prefix="opt08a-derived-") as temp_dir:
            derived_path = Path(temp_dir) / "predictor.py"
            derived_path.write_text(derived, encoding="utf-8")
            sys.argv = [str(RECOGNITION), "--variant", "baseline", "--case", args.case,
                        "--inputs", str(args.inputs), "--models", str(args.models),
                        "--reference-source", str(derived_path), "--output", str(args.output)]
            try:
                helper.main()
            except Exception as exc:
                helper_error = exc
            finally:
                sys.argv = original_argv

        if args.output.is_dir() and (args.output / "run.json").exists():
            module = sys.modules.get("modules.models.tracknet._opt07a_reference")
            run_path = args.output / "run.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            derived_file = args.output / "derived_predictor.py"
            derived_file.write_text(derived, encoding="utf-8")
            run.update({
                "variant": "size_candidate",
                "input_size": {"height": SIZES[args.size][0], "width": SIZES[args.size][1]},
                "predictor_class": f"{module.TrackNetPredictor.__module__}.{module.TrackNetPredictor.__qualname__}" if module else None,
                "derived_predictor_source": str(derived_file),
                "derived_predictor_sha256": sha256(derived_file),
                "source_predictor_sha256": sha256(PREDICTOR),
                "runner_sha256": sha256(Path(__file__)),
                "predictor_observations": getattr(module, "OPT08A_OBSERVATIONS", None) if module else None,
                "helper_reported_variant": run.get("variant"),
            })
            run["variant"] = "size_candidate"
            run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if helper_error is not None:
            raise helper_error


if __name__ == "__main__":
    main()
