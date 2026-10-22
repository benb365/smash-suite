from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_reference(path: Path, package):
    name = "modules.models.tracknet._opt07a_reference"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = "modules.models.tracknet"
    sys.modules[name] = module
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    package.TrackNetPredictor = module.TrackNetPredictor
    return module


class ProcessSampler:
    def __init__(self):
        import psutil
        self.process = psutil.Process(os.getpid())
        self.samples = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, name="opt07a-process-sampler", daemon=True)

    def _record(self):
        self.samples.append(dict(monotonic_s=time.monotonic(), rss_bytes=self.process.memory_info().rss,
                                 cpu_percent=self.process.cpu_percent(interval=None)))

    def _sample(self):
        self._record()
        while not self.stop.wait(1):
            self._record()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self._record()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--case", choices=("A-short", "C-short"), required=True)
    parser.add_argument("--inputs", type=Path, default=ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--reference-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output directory already exists: {args.output}")
    args.output.mkdir(parents=True)

    started = time.monotonic()
    stats = None
    sampler = None
    run = {"variant": args.variant, "case": args.case, "status": "failed", "output": str(args.output)}
    try:
        manifest = json.loads(args.inputs.read_text(encoding="utf-8"))
        case = next(row for row in manifest["cases"] if row["case_id"] == args.case)
        if case["status"] != "passed":
            raise ValueError(f"input is not passed: {args.case}")
        video = Path(case["video"])
        video_sha = sha256(video)
        if video_sha != case["sha256"]:
            raise AssertionError(f"video SHA256 mismatch: {video}")

        import cv2
        import numpy as np
        import torch
        import torchvision
        import psutil
        from modules.media.video import probe, selected_ranges
        from modules.models.assets import ASSETS
        from modules.rally.scenarios import required_models
        from modules.rally.statistics import Statistics

        torch.set_num_threads(4)
        cv2.setNumThreads(1)
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable; refusing to run on another device")
        weights = {}
        weight_hashes = {}
        for name in required_models(case["scene"]):
            path = args.models / name
            asset = ASSETS[name]
            if not path.is_file() or path.stat().st_size != asset["bytes"]:
                raise AssertionError(f"cached model is missing or has the wrong size: {path}")
            digest = sha256(path)
            if digest != asset["sha256"]:
                raise AssertionError(f"cached model SHA256 mismatch: {path}")
            weights[name] = path
            weight_hashes[name] = digest

        package = importlib.import_module("modules.models.tracknet")
        reference_sha = sha256(args.reference_source)
        if args.variant == "baseline":
            load_reference(args.reference_source, package)
        recognize_module = importlib.import_module("modules.rally.recognize")
        modules = importlib.import_module("modules")
        source_paths = {
            "modules": Path(modules.__file__).resolve(),
            "tracknet_package": Path(package.__file__).resolve(),
            "recognize": Path(recognize_module.__file__).resolve(),
            "predictor": Path(importlib.import_module("modules.models.tracknet.predictor").__file__).resolve(),
            "tracknet_model": ROOT / "modules/models/tracknet/model.py",
            "scenario_profiles": ROOT / "modules/rally/scenarios/profiles.json",
        }
        if any(not path.is_relative_to(ROOT) for path in source_paths.values()):
            raise AssertionError(f"production modules were imported outside task worktree: {source_paths}")
        code_hashes = {name: sha256(path) for name, path in source_paths.items() if path.is_file()}
        if args.variant == "baseline":
            code_hashes["frozen_predictor"] = reference_sha

        info = probe(video, video.name)
        preflight_wall = time.monotonic() - started
        stats = Statistics(enabled=True)
        last_progress = [None, -1]

        def progress(stage, fraction):
            decile = int(fraction * 10)
            if stage != last_progress[0] or decile != last_progress[1]:
                print(json.dumps({"stage": stage, "progress": fraction}, ensure_ascii=False), flush=True)
                last_progress[:] = [stage, decile]

        process = psutil.Process(os.getpid())
        run.update({
            "status": "running",
            "started_monotonic_s": time.monotonic(),
            "preflight_wall_s": preflight_wall,
            "git_commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                          check=True, capture_output=True, text=True).stdout.strip(),
            "git_status": subprocess.run(["git", "-C", str(ROOT), "status", "--short"],
                                          check=True, capture_output=True, text=True).stdout.splitlines(),
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "psutil": psutil.__version__,
            "device": "mps",
            "mps_available": torch.backends.mps.is_available(),
            "torch_threads": torch.get_num_threads(),
            "opencv_threads": cv2.getNumThreads(),
            "video": str(video),
            "video_sha256": video_sha,
            "weights": {name: {"path": str(weights[name]), "sha256": value} for name, value in weight_hashes.items()},
            "inputs_sha256": sha256(args.inputs),
            "reference_source": str(args.reference_source),
            "reference_source_sha256": reference_sha,
            "source_paths": {name: str(path) for name, path in source_paths.items()},
            "code_sha256": code_hashes,
        })
        sampler = ProcessSampler()
        outer_started = time.monotonic()
        with sampler, stats.mps_sampling():
            predictions, details = recognize_module.recognize(
                video, info, case["scene"], weights, progress, args.output,
                court=case.get("court"), statistics=stats)
        outer_wall = time.monotonic() - outer_started
        export_ranges = selected_ranges(predictions, info.duration_ms, padding_ms=500)
        write_json(args.output / "result.json", dict(predictions=predictions, details=details,
                                                       export_ranges=export_ranges, padding_ms=500))
        run.update(status="completed", recognition_wall_s=details["recognition_wall_s"],
                   outer_recognition_wall_s=outer_wall, completed_monotonic_s=time.monotonic(),
                   parent_rss_bytes=process.memory_info().rss)
    except Exception as exc:
        run.update(status="failed", error=str(exc), traceback=traceback.format_exc(),
                   failed_monotonic_s=time.monotonic())
        write_json(args.output / "failure.json", {"error": str(exc), "traceback": run["traceback"]})
        raise
    finally:
        if stats is not None:
            stats.write(args.output / "statistics.json", error=run.get("error"))
        else:
            write_json(args.output / "statistics.json", {"error": run.get("error"), "mps_samples": []})
        write_json(args.output / "resources.json", {
            "process_samples": sampler.samples if sampler else [],
            "mps_samples": stats.mps if stats else [],
            "scope": "This process only; MPS memory is reported separately from process RSS.",
        })
        run.setdefault("preflight_wall_s", time.monotonic() - started)
        write_json(args.output / "run.json", run)


if __name__ == "__main__":
    main()
