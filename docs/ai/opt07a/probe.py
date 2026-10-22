from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import importlib
import json
import platform
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import torch
import torchvision

from modules.media.video_input import FileFrameSource
from modules.rally.recognize import normalized
from modules.models.tracknet import TrackNetPredictor as CurrentPredictor
from modules.models.tracknet.predictor import heatmap_candidates


EXPECTED_REFERENCE_SHA256 = "df737b3bac7ae2ecba2a8ce6337cb56d7350cc053de54f4b950d997a634679aa"
CACHE_WINDOWS = ((0, 1, 2), (1, 2, 3), (3, 4, 5), (4, 5, 6))
CASES = ("A-short", "C-short", "D-short")


class RecordingModel:
    def __init__(self, model):
        self.model = model
        self.batches = []
        self.heatmaps = []

    def __call__(self, batch):
        self.batches.append(batch.detach().cpu().clone())
        output = self.model(batch)
        self.heatmaps.append(output.detach().cpu().clone())
        return output


class Counts:
    def __init__(self):
        self.counts = {}
        self.timings = {}

    def add(self, name, value=1):
        self.counts[name] = self.counts.get(name, 0) + value

    def timing(self, name, value):
        self.timings[name] = self.timings.get(name, 0.0) + value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source_class(source: str, name: str):
    module = types.ModuleType(name)
    module.__package__ = "modules.models.tracknet"
    sys.modules[name] = module
    exec(compile(source, name, "exec"), module.__dict__)
    return module.TrackNetPredictor


def preprocessing_formula(source: str) -> str:
    lines = [line.strip() for line in source.splitlines()
             if ("rgb =" in line and ("cvtColor" in line or "astype" in line))
             or ("tensor =" in line and "resize(" not in line
                 and any(token in line for token in ("from_numpy", ".float()", ".div_(", "/ 255")))]
    return "\n".join(lines)


def build_variants(reference: Path):
    base_source = reference.read_text(encoding="utf-8")
    if source_hash(reference) != EXPECTED_REFERENCE_SHA256:
        raise AssertionError("frozen predictor source SHA256 differs from the approved baseline")
    old = "tensor = self.torch.from_numpy(rgb).permute(2, 0, 1).float() / 255"
    inplace = "tensor = self.torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255)"
    fused = "tensor = self.torch.from_numpy(rgb).permute(2, 0, 1).div_(255)"
    old_rgb = "rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)"
    fused_rgb = "rgb = frame[:, :, ::-1].astype(np.float32)"
    if base_source.count(old) != 1 or base_source.count(old_rgb) != 1:
        raise AssertionError("frozen baseline preprocessing lines were not found exactly once")
    intermediate_source = base_source.replace(old, inplace, 1)
    fused_source = base_source.replace(old_rgb, fused_rgb, 1).replace(old, fused, 1)
    current_source_path = ROOT / "modules/models/tracknet/predictor.py"
    current_source = current_source_path.read_text(encoding="utf-8")
    formulas = {"baseline": preprocessing_formula(base_source),
                "inplace": preprocessing_formula(intermediate_source),
                "fused": preprocessing_formula(fused_source),
                "current": preprocessing_formula(current_source)}
    if len({formulas[name] for name in ("baseline", "inplace", "fused")}) != 3:
        raise AssertionError(f"the three experimental preprocessing formulas are not distinct: {formulas}")
    if formulas["current"] != formulas["inplace"]:
        raise AssertionError(f"production candidate differs from the retained inplace formula: {formulas}")
    baseline_class = load_source_class(base_source, "_opt07a_baseline_predictor")
    intermediate_class = load_source_class(intermediate_source, "_opt07a_inplace_predictor")
    fused_class = load_source_class(fused_source, "_opt07a_fused_predictor")
    return {
        "baseline": (baseline_class, source_hash(reference), formulas["baseline"]),
        "inplace": (intermediate_class, hashlib.sha256(intermediate_source.encode()).hexdigest(), formulas["inplace"]),
        "fused": (fused_class, hashlib.sha256(fused_source.encode()).hexdigest(), formulas["fused"]),
        "current": (CurrentPredictor, source_hash(current_source_path), formulas["current"]),
    }


def groups_for(frame_count: int, scene: str):
    if frame_count < 7:
        raise ValueError(f"need at least seven frames, got {frame_count}")
    middle = max(0, (frame_count // 2) - 1)
    tail = frame_count - 3
    starts = [0, middle, tail]
    groups = [tuple(range(start, start + 3)) for start in starts]
    if scene == "courtside":
        groups = [*CACHE_WINDOWS, groups[1], groups[2]]
    return groups


def capture_frames(case, *, expected_frames, scene):
    selected = set(range(7)) if scene == "courtside" else set()
    groups = groups_for(expected_frames, scene)
    selected.update(index for group in groups for index in group)
    kept = {}
    delivered = 0
    with FileFrameSource(case["video"], mode="offline") as source:
        for frame in source:
            if frame.frame_id in selected:
                kept[frame.frame_id] = normalized(frame)
            delivered += 1
        source_stats = dict(source.stats)
    if delivered != expected_frames or set(kept) != selected:
        raise AssertionError(f"decoded frame count/selection mismatch: {delivered}, expected {expected_frames}")
    if any(frame.image.dtype != np.uint8 or frame.image.ndim != 3 or frame.image.shape[2] != 3
           for frame in kept.values()):
        raise AssertionError("selected FileFrameSource inputs must be three-channel uint8 BGR frames")
    return groups, kept, source_stats


def run_variant(name, predictor_class, frames, groups, *, scene, weight, device):
    statistics = Counts()
    predictor = predictor_class(weight, device=device, record_candidates=True, statistics=statistics)
    recorder = RecordingModel(predictor.model)
    predictor.model = recorder
    frame_digests = {fid: hashlib.sha256(frame.image.tobytes()).hexdigest() for fid, frame in frames.items()}
    results = []
    for index, window in enumerate(groups):
        ids = list(window)
        print(f"{name}: frames {ids} started", flush=True)
        points = predictor([frames[fid].image for fid in ids], frame_ids=ids if scene == "courtside" else None)
        results.append({
            "frame_ids": ids,
            "pts_ms": [frames[fid].timestamp_ms for fid in ids],
            "images": [{"shape": list(frames[fid].image.shape), "dtype": str(frames[fid].image.dtype),
                        "sha256": frame_digests[fid]} for fid in ids],
            "input": recorder.batches[-1],
            "heatmap": recorder.heatmaps[-1],
            "points": [asdict(point) if is_dataclass(point) else point for point in points],
            "candidates": predictor.last_candidates,
            "cache_after_call": {
                "items": len(predictor._preprocessed_cache),
                "hits": statistics.counts.get("tracknet_cache_hits", 0),
                "misses": statistics.counts.get("tracknet_cache_misses", 0),
                "prepared_frames": statistics.counts.get("tracknet_cache_prepared_frames", 0),
            },
        })
        print(f"{name}: frames {ids} complete", flush=True)
    unchanged = all(hashlib.sha256(frame.image.tobytes()).hexdigest() == frame_digests[fid]
                    for fid, frame in frames.items())
    cache_before_clear = len(predictor._preprocessed_cache)
    predictor.clear_preprocessed_cache()
    cache_after_clear = len(predictor._preprocessed_cache)
    return results, {
        "counts": statistics.counts,
        "cache_peak_items": predictor._cache_peak_items,
        "cache_items_before_clear": cache_before_clear,
        "cache_items_after_clear": cache_after_clear,
        "source_frames_unchanged": unchanged,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json")
    parser.add_argument("--reference-source", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"output directory already exists: {args.output}")
    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; refusing to run on another device")
    from modules.models.assets import ASSETS
    weight = args.models / "ball_track.pt"
    if not weight.is_file() or sha256(weight) != ASSETS["ball_track.pt"]["sha256"]:
        raise AssertionError(f"cached TrackNet weight is missing or has the wrong SHA256: {weight}")
    modules = importlib.import_module("modules")
    source_modules = [modules, importlib.import_module("modules.models.tracknet"),
                      importlib.import_module("modules.models.tracknet.predictor"),
                      importlib.import_module("modules.rally.recognize")]
    if any(not Path(module.__file__).resolve().is_relative_to(ROOT) for module in source_modules):
        raise AssertionError(f"production modules imported outside task worktree: {[m.__file__ for m in source_modules]}")
    variants = build_variants(args.reference_source)
    manifest = json.loads(args.inputs.read_text(encoding="utf-8"))
    cases = {row["case_id"]: row for row in manifest["cases"]}
    report = {
        "reference_source_sha256": source_hash(args.reference_source),
        "current_source_sha256": variants["current"][1],
        "environment": {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__,
                        "torchvision": torchvision.__version__, "numpy": np.__version__, "opencv": cv2.__version__,
                        "device": "mps", "mps_available": torch.backends.mps.is_available(),
                        "torch_threads": torch.get_num_threads(), "opencv_threads": cv2.getNumThreads(),
                        "modules_source": modules.__file__},
        "weight_sha256": sha256(weight),
        "cases": {},
    }
    args.output.mkdir(parents=True)
    evidence = {}
    for case_id in CASES:
        case = cases[case_id]
        if case["status"] != "passed":
            raise AssertionError(f"input {case_id} is not passed")
        video_path = Path(case["video"])
        video_sha = sha256(video_path)
        if video_sha != case["sha256"]:
            raise AssertionError(f"video SHA256 mismatch for {case_id}")
        groups, frames, source_stats = capture_frames(case, expected_frames=case["metadata"]["container_frames"],
                                                       scene=case["scene"])
        case_result = {"video_sha256": video_sha, "video_path": str(video_path), "file_frame_source": source_stats,
                       "groups": [list(group) for group in groups], "variants": {}}
        recordings = {}
        for name, (predictor_class, code_sha, formula) in variants.items():
            print(f"{case_id}: {name} started", flush=True)
            recordings[name], cache = run_variant(name, predictor_class, frames, groups, scene=case["scene"],
                                                   weight=weight, device="mps")
            case_result["variants"][name] = {
                "source_sha256": code_sha, "formula": formula, "cache": cache,
                "windows": [{"frame_ids": row["frame_ids"], "pts_ms": row["pts_ms"],
                             "images": row["images"], "cache_after_call": row["cache_after_call"]}
                            for row in recordings[name]],
            }
        evidence[case_id] = {name: [{"input": row["input"], "heatmap": row["heatmap"]}
                                    for row in rows] for name, rows in recordings.items()}
        baseline = recordings["baseline"]
        for name in ("inplace", "fused", "current"):
            comparisons = []
            for left, right in zip(baseline, recordings[name]):
                comparisons.append({
                    "frame_ids_equal": left["frame_ids"] == right["frame_ids"],
                    "pts_equal": left["pts_ms"] == right["pts_ms"],
                    "image_metadata_equal": left["images"] == right["images"],
                    "model_input_equal": bool(torch.equal(left["input"], right["input"])),
                    "heatmap_equal": bool(torch.equal(left["heatmap"], right["heatmap"])),
                    "points_equal": left["points"] == right["points"],
                    "candidates_equal": left["candidates"] == right["candidates"],
                    "cache_stats_equal": left["cache_after_call"] == right["cache_after_call"],
                })
            case_result["variants"][name]["strict_comparison_to_baseline"] = comparisons
        if case["scene"] == "courtside":
            expected_cache = ((0, 3, 3), (2, 4, 4), (3, 6, 6), (5, 7, 7))
            if tuple(tuple(group) for group in groups[:4]) != CACHE_WINDOWS:
                raise AssertionError("C cache windows do not match the approved sequence")
            for name in variants:
                observed = tuple((row["cache_after_call"]["hits"], row["cache_after_call"]["misses"],
                                  row["cache_after_call"]["prepared_frames"])
                                 for row in recordings[name][:4])
                if observed != expected_cache:
                    raise AssertionError(f"unexpected C cache statistics for {name}: {observed}")
        report["cases"][case_id] = case_result
        print(f"{case_id}: complete", flush=True)
    torch.save(evidence, args.output / "model-io.pt")
    report["model_io_file"] = "model-io.pt"
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if any(not all(row.values()) for case in report["cases"].values()
           for name, variant in case["variants"].items() if name != "baseline"
           for row in variant["strict_comparison_to_baseline"]):
        raise SystemExit("strict equivalence failed")
    if any(not variant["cache"]["source_frames_unchanged"] or variant["cache"]["cache_items_after_clear"]
           for case in report["cases"].values() for variant in case["variants"].values()):
        raise SystemExit("source frame mutation or cache clear failure")
    print(args.output / "report.json", flush=True)


if __name__ == "__main__":
    main()
