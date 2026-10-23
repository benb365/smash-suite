from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INPUTS = ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json"
MODEL_DIR = ROOT / "apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models"
VARIANTS = ("color9", "gray9", "gray3")
TARGETS_MS = (4000.0, 25000.0, 50000.0)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_paths(root: Path, modules):
    result = {}
    for name, module in modules.items():
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(root.resolve()):
            raise RuntimeError(f"{name} loaded outside this worktree: {path}")
        result[name] = {"path": str(path), "sha256": sha256_file(path)}
    return result


def take_sample_groups(frames, targets_ms=TARGETS_MS):
    groups = []
    target_index = 0
    active = None
    for frame in frames:
        if active is None:
            if frame.timestamp_ms >= targets_ms[target_index] and frame.frame_id % 3 == 0:
                active = [frame]
        else:
            if frame.frame_id != active[-1].frame_id + 1:
                raise RuntimeError("sample frames are not consecutive")
            active.append(frame)
            if len(active) == 3:
                groups.append((targets_ms[target_index], active))
                target_index += 1
                active = None
                if target_index == len(targets_ms):
                    return groups
    raise RuntimeError(f"video prefix ended before sample group {target_index + 1} completed")


def tensor_digest(tensor) -> str:
    return sha256_bytes(tensor.detach().cpu().contiguous().numpy().tobytes())


def compare_tensors(torch, left, right):
    diff = (left - right).abs()
    return {
        "shape": list(left.shape),
        "allclose_default": bool(torch.allclose(left, right)),
        "exact_equal_elements": int(torch.count_nonzero(left == right).item()),
        "total_elements": left.numel(),
        "max_abs_diff": float(diff.max().item()) if diff.numel() else 0.0,
        "mean_abs_diff": float(diff.mean().item()) if diff.numel() else 0.0,
    }


def state_hashes(model):
    return {name: tensor_digest(value) for name, value in model.state_dict().items()}


def import_module_source(name: str, source: str):
    module = types.ModuleType(name)
    module.__file__ = f"<{name}>"
    module.__package__ = "modules.models.tracknet"
    module.OPT08C_SOURCE_SHA256 = sha256_bytes(source.encode("utf-8"))
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def load_variants(source_path: Path):
    from run import derive_predictor_source
    source = source_path.read_text(encoding="utf-8")
    return {
        name: import_module_source(
            f"modules.models.tracknet._opt08c_{name}",
            derive_predictor_source(source, name),
        )
        for name in VARIANTS
    }


def verify_weights(models_dir: Path, scene: str):
    from modules.models.assets import ASSETS
    from modules.rally.scenarios import required_models
    result = {}
    for name in required_models(scene):
        path = models_dir / name
        asset = ASSETS[name]
        if not path.is_file() or path.stat().st_size != asset["bytes"]:
            raise AssertionError(f"cached model missing or wrong size: {path}")
        digest = sha256_file(path)
        if digest != asset["sha256"]:
            raise AssertionError(f"cached model SHA256 mismatch: {path}")
        result[name] = {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}
    return result


def make_hooks(predictor):
    observed = {}

    def input_hook(module, inputs):
        observed["input"] = inputs[0].detach().cpu().clone()

    def conv_hook(module, inputs, output):
        observed["conv1"] = output.detach().cpu().clone()

    def heatmap_hook(module, inputs, output):
        observed["heatmaps"] = output.detach().cpu().clone()

    handles = [
        predictor.model.register_forward_pre_hook(input_hook),
        predictor.model.conv2d_1.conv.register_forward_hook(conv_hook),
        predictor.model.register_forward_hook(heatmap_hook),
    ]
    return observed, handles


def run_probe_variant(name, module, groups, weight_path, torch):
    predictor = module.TrackNetPredictor(weight_path, device="mps", record_candidates=True)
    model_hashes = state_hashes(predictor.model)
    rows = []
    captured = []
    observed, handles = make_hooks(predictor)
    try:
        for target_ms, group in groups:
            observed.clear()
            points = predictor([frame.image for frame in group])
            if set(observed) != {"input", "conv1", "heatmaps"}:
                raise AssertionError(f"model hooks did not capture expected tensors for {name}")
            input_tensor, conv1, heatmaps = (observed[key] for key in ("input", "conv1", "heatmaps"))
            tensor_rows = {
                "input": input_tensor,
                "conv1": conv1,
                "heatmaps": heatmaps,
            }
            candidates = predictor.last_candidates
            rows.append({
                "target_timestamp_ms": target_ms,
                "frames": [
                    {
                        "frame_id": frame.frame_id,
                        "timestamp_ms": frame.timestamp_ms,
                        "image_sha256": sha256_bytes(frame.image.tobytes()),
                    }
                    for frame in group
                ],
                "input": {"shape": list(input_tensor.shape), "dtype": str(input_tensor.dtype),
                          "sha256": tensor_digest(input_tensor)},
                "first_layer_output": {"shape": list(conv1.shape), "dtype": str(conv1.dtype),
                                       "sha256": tensor_digest(conv1)},
                "heatmaps": {"shape": list(heatmaps.shape), "dtype": str(heatmaps.dtype),
                             "sha256": tensor_digest(heatmaps)},
                "points": [dict(x=p.x, y=p.y, confidence=p.confidence) for p in points],
                "candidates": candidates,
            })
            captured.append(tensor_rows)
    finally:
        for handle in handles:
            handle.remove()
    return {"rows": rows, "tensors": captured, "state_hashes": model_hashes,
            "first_layer_in_channels": predictor.model.conv2d_1.conv.in_channels,
            "derived_predictor_sha256": module.OPT08C_SOURCE_SHA256,
            "actual_predictor_class": f"{module.TrackNetPredictor.__module__}.{module.TrackNetPredictor.__qualname__}"}


def point_candidate_diff(left, right):
    if len(left["points"]) != len(right["points"]):
        raise AssertionError("point counts differ across predictor variants")
    point_count = 0
    point_deltas = {"x": [], "y": [], "confidence": []}
    for a, b in zip(left["points"], right["points"]):
        for key in point_deltas:
            delta = abs(float(a[key]) - float(b[key]))
            point_deltas[key].append(delta)
        if any(a[key] != b[key] for key in point_deltas):
            point_count += 1
    left_candidates, right_candidates = left["candidates"], right["candidates"]
    if len(left_candidates) != len(right_candidates):
        raise AssertionError("candidate frame counts differ across predictor variants")
    changed_candidate_frames = sum(a != b for a, b in zip(left_candidates, right_candidates))
    return {
        "changed_point_count": point_count,
        "point_count": len(left["points"]),
        "point_max_abs_diff": {key: max(values, default=0.0) for key, values in point_deltas.items()},
        "candidate_lists_equal": left_candidates == right_candidates,
        "changed_candidate_frame_count": changed_candidate_frames,
        "candidate_frame_count": max(len(left_candidates), len(right_candidates)),
    }


def run(args):
    import cv2
    import numpy as np
    import torch
    import torchvision
    from modules.media.video_input import FileFrameSource
    from modules.models.tracknet import predictor as production_predictor
    from modules.models.tracknet import model as tracknet_model
    from modules.models import assets as assets_module

    production_sources = verify_source_paths(ROOT, {
        "FileFrameSource": sys.modules[FileFrameSource.__module__],
        "production_predictor": production_predictor,
        "TrackNet": tracknet_model,
        "assets": assets_module,
    })
    expected_predictor = (ROOT / "modules/models/tracknet/predictor.py").resolve()
    if Path(production_predictor.__file__).resolve() != expected_predictor:
        raise RuntimeError(
            f"production predictor is not this worktree's source: {production_predictor.__file__}"
        )

    manifest = json.loads(args.inputs.read_text(encoding="utf-8"))
    case = next(row for row in manifest["cases"] if row["case_id"] == "A-short")
    if case["status"] != "passed":
        raise ValueError("input case not passed: A-short")
    video = Path(case["video"])
    video_sha = sha256_file(video)
    if video_sha != case["sha256"]:
        raise AssertionError(f"video SHA256 mismatch: {video}")
    weights = verify_weights(args.models, case["scene"])
    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable; refusing to use another device")

    with FileFrameSource(video, mode="offline") as source:
        groups = take_sample_groups(iter(source))
        source_prefix = dict(source.stats)
    if len(groups) != 3:
        raise AssertionError("expected exactly three complete sample groups")
    original_images = {
        (frame.frame_id, frame.timestamp_ms): sha256_bytes(frame.image.tobytes())
        for _, group in groups for frame in group
    }

    source_path = ROOT / "modules/models/tracknet/predictor.py"
    modules = load_variants(source_path)
    results = {}
    for name, module in modules.items():
        result = run_probe_variant(name, module, groups, weights["ball_track.pt"]["path"], torch)
        results[name] = result
        del result
        torch.mps.empty_cache()

    reference = results["color9"]
    gray9, gray3 = results["gray9"], results["gray3"]
    comparisons = []
    for index, (r9, r3, c9) in enumerate(zip(gray9["tensors"], gray3["tensors"], reference["tensors"])):
        input_copy_equal = torch.equal(
            r9["input"].reshape(1, 3, 3, 288, 512),
            r3["input"].unsqueeze(2).expand(1, 3, 3, 288, 512),
        )
        comparisons.append({
            "sample_index": index,
            "gray9_gray3_input_copy_exact": bool(input_copy_equal),
            "first_layer_gray9_vs_gray3": compare_tensors(torch, r9["conv1"], r3["conv1"]),
            "heatmap_gray9_vs_gray3": compare_tensors(torch, r9["heatmaps"], r3["heatmaps"]),
            "gray9_vs_gray3_points_and_candidates": point_candidate_diff(
                gray9["rows"][index], gray3["rows"][index]),
            "color9_vs_gray9_points_and_candidates": point_candidate_diff(
                reference["rows"][index], gray9["rows"][index]),
            "color9_vs_gray3_points_and_candidates": point_candidate_diff(
                reference["rows"][index], gray3["rows"][index]),
        })
    for variant in VARIANTS:
        for _, group in groups:
            for frame in group:
                if sha256_bytes(frame.image.tobytes()) != original_images[(frame.frame_id, frame.timestamp_ms)]:
                    raise AssertionError("source image was mutated")

    non_first_key_match = {}
    baseline_hashes = reference["state_hashes"]
    for name in VARIANTS:
        hashes = results[name]["state_hashes"]
        if name == "gray9" and hashes != baseline_hashes:
            raise AssertionError("gray9 changed model state")
        if name == "gray3" and hashes["conv2d_1.conv.weight"] == baseline_hashes["conv2d_1.conv.weight"]:
            raise AssertionError("gray3 first-layer weight was not folded")
        non_first_key_match[name] = {
            key: hashes[key] == baseline_hashes[key]
            for key in baseline_hashes if key != "conv2d_1.conv.weight"
        }
        if not all(non_first_key_match[name].values()):
            raise AssertionError(f"unexpected non-first-layer parameter change: {name}")
    if not all(row["gray9_gray3_input_copy_exact"] for row in comparisons):
        raise AssertionError("gray9 and gray3 model inputs differ beyond channel replication")

    return {
        "status": "completed",
        "scope": "Prefix-only numeric probe; not EOF and not a speed test.",
        "case": "A-short",
        "python_version": sys.version,
        "platform": platform.platform(),
        "video": str(video),
        "video_sha256": video_sha,
        "source_predictor_path": str(source_path),
        "source_predictor_sha256": sha256_file(source_path),
        "production_predictor_sha256": sha256_file(Path(production_predictor.__file__)),
        "tracknet_model_source_sha256": sha256_file(ROOT / "modules/models/tracknet/model.py"),
        "production_source_files": production_sources,
        "inputs_manifest_path": str(args.inputs),
        "inputs_manifest_sha256": sha256_file(args.inputs),
        "probe_runner_sha256": sha256_file(Path(__file__)),
        "git_commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                     check=True, capture_output=True, text=True).stdout.strip(),
        "weights": weights,
        "device": "mps",
        "mps_available": torch.backends.mps.is_available(),
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "numpy_version": np.__version__,
        "opencv_version": cv2.__version__,
        "torch_threads": torch.get_num_threads(),
        "opencv_threads": cv2.getNumThreads(),
        "sample_selection": {
            "target_timestamps_ms": list(TARGETS_MS),
            "rule": "first frame at or after each target with frame_id divisible by 3, then the next two consecutive frame ids",
            "groups": {
                name: rows["rows"]
                for name, rows in results.items()
            },
            "decode_prefix_stats_at_stop": source_prefix,
            "eof_status": "not checked; decoder iteration stops after the third sample window",
        },
        "model_input_channels": {name: rows["rows"][0]["input"]["shape"][1] for name, rows in results.items()},
        "first_layer_in_channels": {name: rows["first_layer_in_channels"] for name, rows in results.items()},
        "state_key_sha256": {name: rows["state_hashes"] for name, rows in results.items()},
        "derived_predictor_sha256": {name: rows["derived_predictor_sha256"] for name, rows in results.items()},
        "actual_predictor_class": {name: rows["actual_predictor_class"] for name, rows in results.items()},
        "non_first_layer_state_matches_color9": non_first_key_match,
        "gray9_gray3_comparisons": comparisons,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=INPUTS)
    parser.add_argument("--models", type=Path, default=MODEL_DIR)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    try:
        value = run(args)
    except Exception as exc:
        (args.output / "failure.json").write_text(
            json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    (args.output / "probe.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
