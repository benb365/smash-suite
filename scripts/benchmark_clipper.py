"""Benchmark one local clip with cached weights and verify the exported MP4.

Run from a repository root. An explicit repository on PYTHONPATH takes priority,
so this same script can measure another checkout without copying the driver.
No inputs or models are downloaded. Use a new output directory for each run.
This entry measures recognition and plain MP4 export, without shot-path overlays.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


CORE_SOURCES = (
    "modules/rally/recognize.py",
    "modules/models/keypoint_rcnn/__init__.py",
    "modules/models/tracknet/predictor.py",
    "modules/models/yolo11n/__init__.py",
    "modules/media/video.py",
    "modules/media/video_input.py",
    "modules/rally/scenarios/profiles.json",
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def core_source_hashes(root):
    hashes = {}
    for name in CORE_SOURCES:
        try:
            hashes[name] = digest(root / name)
        except OSError:
            hashes[name] = None
    return hashes


def json_value(value):
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                     default=json_value, allow_nan=False) + "\n", encoding="utf-8")


def repository_root():
    candidates = [Path(entry).resolve() for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep) if entry]
    candidates.append(Path.cwd().resolve())
    for root in candidates:
        if (root / "modules/rally/recognize.py").is_file():
            return root
    raise ValueError("Run from the repository root, or put the intended checkout root on PYTHONPATH.")


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_info(root):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    try:
        return dict(head=git("rev-parse", "HEAD"), tracked_changes=git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        return dict(head=None, tracked_changes=None)


def intervals(rows, *, predictions):
    if not isinstance(rows, list):
        raise ValueError("Reference intervals must be a list.")
    pairs = [[float(row["start_ms"]), float(row["end_ms"])] if predictions else [float(row[0]), float(row[1])]
             for row in rows]
    if any(not all(math.isfinite(number) for number in pair) or pair[0] >= pair[1] for pair in pairs):
        raise ValueError("Reference contains an invalid time interval.")
    return pairs


def recognition_optimizations(scene, profile):
    """Resolve input choices explicitly; standalone and product defaults differ."""
    if profile == "off":
        return dict(limit_fps=False, small_input=False, grayscale=False, dynamic_scan=False)
    if profile == "default":
        from app.product_types import ProcessRequest
        return ProcessRequest(camera_type=scene).optimizations.model_dump()
    raise ValueError(f"Unknown optimization profile: {profile}")


def compare_intervals(current, reference):
    rows = [dict(index=i, current_ms=a, reference_ms=b,
                 start_delta_ms=a[0] - b[0], end_delta_ms=a[1] - b[1], exact=a == b)
            for i, (a, b) in enumerate(zip(current, reference))]
    deltas = [abs(value) for row in rows for value in (row["start_delta_ms"], row["end_delta_ms"])]
    return dict(current_count=len(current), reference_count=len(reference), compared_count=len(rows),
                same_order_exact=len(current) == len(reference) and all(row["exact"] for row in rows),
                max_abs_boundary_delta_ms=max(deltas, default=0),
                mean_abs_boundary_delta_ms=sum(deltas) / len(deltas) if deltas else 0,
                paired_intervals=rows, unpaired_current=current[len(rows):], unpaired_reference=reference[len(rows):])


def decode_and_validate(source, output, ranges, info, expected_duration_ms):
    """Decode the complete input video and all exported audio/video frames."""
    import av
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        base = stream.time_base
        origin = round(info.first_pts_ms / 1000 / base)
        ticks = [(math.ceil(a / 1000 / base - 1e-6), math.ceil(z / 1000 / base - 1e-6)) for a, z in ranges]
        decoded_source = selected_source = index = 0
        previous = None
        for frame in container.decode(video=0):
            if frame.is_corrupt:
                raise RuntimeError("Source video decoder marked a corrupt frame.")
            if frame.pts is None:
                raise RuntimeError("Source frame is missing its presentation timestamp.")
            timestamp = frame.pts * frame.time_base / base - origin
            if previous is not None and timestamp <= previous:
                raise RuntimeError("Source video timestamps are not strictly increasing.")
            previous = timestamp
            decoded_source += 1
            while index < len(ticks) and timestamp >= ticks[index][1]:
                index += 1
            if index < len(ticks) and ticks[index][0] <= timestamp < ticks[index][1]:
                selected_source += 1
    with av.open(str(output)) as container:
        videos, audios = list(container.streams.video), list(container.streams.audio)
        if len(videos) != 1 or bool(audios) != info.has_audio or len(audios) > 1:
            raise RuntimeError("Exported audio/video tracks differ from the expected tracks.")
        video = videos[0]
        duration_ms = float(video.duration * video.time_base * 1000) if video.duration is not None else None
        stream_start_ms = float((video.start_time or 0) * video.time_base * 1000)
        presentation_end_ms = stream_start_ms + duration_ms if duration_ms is not None else None
        frame_period_ms = 1000 / float(video.average_rate) if video.average_rate else 40
        counts = dict(video=0, audio=0, audio_samples=0)
        first, last = {}, {}
        for frame in container.decode(**(dict(video=0, audio=0) if audios else dict(video=0))):
            kind = "video" if isinstance(frame, av.VideoFrame) else "audio"
            if kind == "video" and frame.is_corrupt:
                raise RuntimeError("Exported video decoder marked a corrupt frame.")
            if frame.pts is None:
                raise RuntimeError(f"Exported {kind} frame is missing its timestamp.")
            timestamp_ms = float(frame.pts * frame.time_base * 1000)
            if kind in last and timestamp_ms <= last[kind]:
                raise RuntimeError(f"Exported {kind} timestamps are not strictly increasing.")
            first.setdefault(kind, timestamp_ms)
            last[kind] = timestamp_ms
            counts[kind] += 1
            if kind == "audio":
                counts["audio_samples"] += frame.samples
        tolerance_ms = max(2, frame_period_ms)
        checks = dict(frame_count_matches_selected_source=counts["video"] == selected_source and selected_source > 0,
                      audio_decodes=not info.has_audio or (counts["audio"] > 0 and counts["audio_samples"] > 0),
                      original_dimensions=video.width == info.width and video.height == info.height,
                      duration_matches_selected_ranges=presentation_end_ms is not None and abs(presentation_end_ms - expected_duration_ms) <= tolerance_ms)
        record = dict(passed=all(checks.values()), checks=checks, source_decoded_frames=decoded_source,
                      video_corrupt_flags_checked=True, audio_video_sync_verified=False,
                      audio_validation_scope="Complete exported audio decoding, nonempty samples when expected, and monotonic PTS; does not establish audio/video synchronization or waveform correspondence to the source.",
                      expected_output_frames=selected_source, decoded=counts, video_tracks=len(videos), audio_tracks=len(audios),
                      width=video.width, height=video.height, video_codec=video.codec_context.name,
                      audio_codec=audios[0].codec_context.name if audios else None,
                      first_pts_ms=first, last_pts_ms=last, video_duration_ms=duration_ms,
                      video_start_ms=stream_start_ms, video_presentation_end_ms=presentation_end_ms,
                      audio_duration_ms=(float(audios[0].duration * audios[0].time_base * 1000)
                                         if audios and audios[0].duration is not None else None),
                      requested_duration_ms=expected_duration_ms, duration_tolerance_ms=tolerance_ms)
    return record


def main(argv=None, *, exclusive_process=False):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="Absolute path to the existing source video")
    parser.add_argument("--scene", choices=("high", "courtside", "personal"), required=True)
    parser.add_argument("--models", type=Path, required=True, help="Existing flat cache containing the required model filenames")
    parser.add_argument("--output", type=Path, required=True, help="New run directory; existing benchmark artifacts are never overwritten")
    parser.add_argument("--reference", type=Path, help="Existing result JSON to compare without changing it")
    parser.add_argument("--pose-device", choices=("cpu", "cuda"), help="Personal-scene pose device; omitted means recognize's default")
    parser.add_argument("--pose-batch-size", type=int, default=1)
    parser.add_argument("--optimizations", choices=("off", "default"), default="off",
                        help="Explicit recognition input choices; default=off. Shot-path overlays are excluded.")
    args = parser.parse_args(argv)
    if not args.source.is_absolute() or not args.source.is_file():
        parser.error("--source must be an absolute path to an existing video.")
    if not args.models.is_dir() or args.pose_batch_size < 1:
        parser.error("--models must exist and --pose-batch-size must be positive.")
    if args.scene != "personal" and (args.pose_device == "cuda" or args.pose_batch_size != 1):
        parser.error("Pose CUDA/batching options only apply to the personal scene.")
    try:
        root = repository_root()
    except ValueError as exc:
        parser.error(str(exc))
    source, models, destination = args.source.resolve(), args.models.resolve(), args.output.resolve()
    if any((destination / name).exists() for name in ("result.json", "performance.json", "events.jsonl", "output.mp4", "rendering.mp4")):
        parser.error("--output already contains benchmark artifacts; choose a new run directory.")
    if args.reference is not None and not args.reference.is_file():
        parser.error("--reference does not exist.")
    destination.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root))
    started = time.perf_counter()
    report = dict(schema_version=1, status="running", started_at_utc=datetime.now(timezone.utc).isoformat(),
                  pid=os.getpid(), source=dict(path=str(source), bytes=source.stat().st_size),
                  repository=dict(path=str(root), core_sources_sha256=core_source_hashes(root), **git_info(root)),
                  driver=dict(path=str(Path(__file__).resolve()), sha256=digest(__file__)),
                  options=dict(scene=args.scene, quality="balanced", padding_ms=500,
                               pose_device=args.pose_device, pose_batch_size=args.pose_batch_size,
                               optimization_profile=args.optimizations, show_shot_paths=False),
                  scope="Recognition plus plain MP4 export; not the full HTTP product or shot-path overlay workload.",
                  stage_timings_s={})
    torch = None
    cuda_devices = []
    phase, phase_start = "preparation", started
    with (destination / "events.jsonl").open("w", encoding="utf-8") as events:
        def event(kind, stage, **values):
            events.write(json.dumps(dict(type=kind, stage=stage, elapsed_s=time.perf_counter() - started,
                                         at_utc=datetime.now(timezone.utc).isoformat(), **values),
                                    default=json_value, allow_nan=False) + "\n")
            events.flush()

        def sync():
            if torch is not None:
                for device in cuda_devices:
                    torch.cuda.synchronize(device)

        def threads(cv2):
            return dict(torch_intraop=torch.get_num_threads(), torch_interop=torch.get_num_interop_threads(),
                        opencv=cv2.getNumThreads(), environment={key: os.environ.get(key) for key in
                            ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")})

        try:
            event("stage_start", "preparation")
            # Match the product worker's limits before numerical libraries load.
            report["inherited_thread_environment"] = {key: os.environ.get(key) for key in
                                                      ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
            for key in report["inherited_thread_environment"]:
                os.environ[key] = "1"
            for key, folder in (("YOLO_CONFIG_DIR", destination / "ultralytics"), ("MPLCONFIGDIR", destination / "matplotlib")):
                folder.mkdir(exist_ok=True)
                os.environ[key] = str(folder)
            from modules.media.video import probe, render, selected_ranges, ffmpeg_exe
            from modules.models.assets import ASSETS
            from modules.rally.scenarios import required_models
            from modules.rally.recognize import recognize
            import cv2
            import torch as torch_module
            torch = torch_module
            report["module_paths"] = dict(recognize=str(Path(inspect.getfile(recognize)).resolve()),
                                          probe=str(Path(inspect.getfile(probe)).resolve()), render=str(Path(inspect.getfile(render)).resolve()))
            if any(not Path(path).is_relative_to(root) for path in report["module_paths"].values()):
                raise RuntimeError("Imported project modules from outside the selected repository.")
            signature = inspect.signature(recognize)
            pose_kwargs = {}
            resolved_optimizations = recognition_optimizations(args.scene, args.optimizations)
            report["options"]["resolved_optimizations"] = resolved_optimizations
            if "optimizations" in signature.parameters:
                pose_kwargs["optimizations"] = resolved_optimizations
            elif args.optimizations != "off":
                raise ValueError("This checkout cannot resolve the requested product optimization profile.")
            statistics = None
            if "statistics" in signature.parameters:
                from modules.rally.statistics import Statistics
                statistics = Statistics(True)
                pose_kwargs["statistics"] = statistics
            for name, value in (("pose_device", args.pose_device), ("pose_batch_size", args.pose_batch_size)):
                if name in signature.parameters:
                    if value is not None:
                        pose_kwargs[name] = value
                elif value not in ((None, "cpu") if name == "pose_device" else (1,)):
                    raise ValueError(f"This checkout's recognize does not support {name}={value!r}; baseline permits CPU / batch 1 only.")
            report["recognize_signature"] = str(signature)
            report["recognize_pose_kwargs"] = {key: value for key, value in pose_kwargs.items() if key != "statistics"}
            if args.pose_device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("--pose-device cuda was requested but CUDA is unavailable.")
            cuda_devices = list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []
            sync()
            if exclusive_process:
                for device in cuda_devices:
                    torch.cuda.reset_peak_memory_stats(device)
            report["cuda_peak_stats_reset"] = bool(cuda_devices and exclusive_process)
            report["cuda_peak_scope"] = "This process only; reset only for a dedicated CLI invocation."
            report["hardware"] = dict(platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                                      logical_cpu_count=os.cpu_count(), cuda_available=bool(cuda_devices),
                                      cuda_runtime=torch.version.cuda, threads_before=threads(cv2),
                                      gpus=[dict(index=i, name=torch.cuda.get_device_name(i),
                                                 total_memory_bytes=torch.cuda.get_device_properties(i).total_memory,
                                                 compute_capability=list(torch.cuda.get_device_capability(i))) for i in cuda_devices])
            report["versions"] = dict(python=platform.python_version(), **{name: version(name) for name in
                                      ("torch", "torchvision", "numpy", "opencv-python", "av", "scipy", "ultralytics", "imageio-ffmpeg")})
            ffmpeg = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=10, check=True)
            report["versions"]["ffmpeg"] = ffmpeg.stdout.splitlines()[0]
            report["source"]["sha256"] = digest(source)
            info = probe(source, source.name)
            report["source"]["video"] = info.model_dump()
            weights = {}
            report["models"] = {}
            for name in required_models(args.scene):
                path = models / name
                asset = ASSETS[name]
                if not path.is_file() or path.stat().st_size != asset["bytes"] or digest(path) != asset["sha256"]:
                    raise ValueError(f"Missing or invalid cached model {path}; this driver never downloads models.")
                weights[name] = path
                report["models"][name] = dict(path=str(path), bytes=asset["bytes"], sha256=asset["sha256"])
            reference = None
            if args.reference:
                reference = json.loads(args.reference.read_text(encoding="utf-8"))
                intervals(reference["predictions"], predictions=True)
                if "export_ranges" in reference:
                    intervals(reference["export_ranges"], predictions=False)
                report["reference"] = dict(path=str(args.reference.resolve()), sha256=digest(args.reference))
            sync()
            report["stage_timings_s"]["preparation"] = time.perf_counter() - started
            event("stage_end", "preparation")
            phase_start = time.perf_counter()
            phase = "recognition"
            event("stage_start", "recognition")
            predictions, details = recognize(source, info, args.scene, weights,
                lambda message, progress: event("progress", "recognition", message=message, progress=progress),
                destination, **pose_kwargs)
            sync()
            report["stage_timings_s"]["recognition"] = time.perf_counter() - phase_start
            report["recognition_performance"] = details.get("performance")
            if statistics is not None:
                statistics.write(destination / "statistics.json")
                report["recognition_statistics"] = json.loads((destination / "statistics.json").read_text(encoding="utf-8"))
            report["recognition_device"] = details.get("device")
            report["hardware"]["threads_after_recognition"] = threads(cv2)
            event("stage_end", "recognition")
            phase_start = time.perf_counter()
            phase = "select_ranges"
            ranges = selected_ranges(predictions, info.duration_ms, padding_ms=500)
            report["stage_timings_s"]["select_ranges"] = time.perf_counter() - phase_start
            phase_start = time.perf_counter()
            phase = "render"
            event("stage_start", "render")
            output = destination / "output.mp4"
            duration_ms = render(source, output, ranges, info, "balanced",
                                 lambda progress: event("progress", "render", progress=progress))
            sync()
            report["stage_timings_s"]["render"] = time.perf_counter() - phase_start
            report["pipeline_wall_s"] = time.perf_counter() - started
            event("stage_end", "render")
            result = dict(predictions=predictions, export_ranges=ranges, output_duration_ms=duration_ms,
                          quality="balanced", padding_ms=500, benchmark_source=dict(report["source"]),
                          benchmark_scene=args.scene, benchmark_optimizations=resolved_optimizations, **details)
            save_json(destination / "result.json", result)
            phase_start = time.perf_counter()
            phase = "validation_and_reference"
            event("stage_start", "validation")
            report["validation"] = decode_and_validate(source, output, ranges, info, duration_ms)
            if not report["validation"]["passed"]:
                raise RuntimeError("Full output validation failed; see validation.checks.")
            report["output"] = dict(path=str(output), bytes=output.stat().st_size, sha256=digest(output))
            if reference is not None:
                comparison = dict(predictions=compare_intervals(intervals(predictions, predictions=True),
                                                                intervals(reference["predictions"], predictions=True)))
                if "export_ranges" in reference:
                    comparison["export_ranges"] = compare_intervals(ranges, intervals(reference["export_ranges"], predictions=False))
                if "output_duration_ms" in reference:
                    comparison["output_duration_delta_ms"] = duration_ms - float(reference["output_duration_ms"])
                try:
                    comparison["reference_unchanged"] = digest(args.reference) == report["reference"]["sha256"]
                except OSError:
                    comparison["reference_unchanged"] = False
                reference_sha = (reference.get("benchmark_source") or {}).get("sha256")
                reference_scene = reference.get("benchmark_scene")
                comparison["same_source_sha256"] = reference_sha == report["source"]["sha256"] if reference_sha is not None else None
                comparison["same_scene"] = reference_scene == args.scene if reference_scene is not None else None
                reference_options = reference.get("benchmark_optimizations")
                comparison["same_optimizations"] = (reference_options == resolved_optimizations
                                                      if reference_options is not None else None)
                identity_checks = ("same_source_sha256", "same_scene", "reference_unchanged")
                failed_checks = [name for name in identity_checks if comparison[name] is False]
                comparison["identity_verification"] = ("failed" if failed_checks else
                    "verified" if all(comparison[name] is True for name in identity_checks) else "unverified")
                comparison["performance_comparison_compatible"] = (
                    comparison["identity_verification"] == "verified" and comparison["same_optimizations"] is True)
                report["reference_comparison"] = comparison
                if failed_checks:
                    raise RuntimeError("Reference identity validation failed: " + ", ".join(failed_checks))
            report["stage_timings_s"]["validation_and_reference"] = time.perf_counter() - phase_start
            event("stage_end", "validation")
            report["status"] = "passed"
        except Exception as exc:
            report["stage_timings_s"][phase] = time.perf_counter() - phase_start
            report["status"] = "failed"
            report["error"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
            event("error", phase, message=str(exc))
        finally:
            repository = report["repository"]
            repository["core_sources_sha256_at_end"] = core_source_hashes(root)
            repository["core_sources_unchanged"] = repository["core_sources_sha256"] == repository["core_sources_sha256_at_end"]
            if not repository["core_sources_unchanged"]:
                repository["changed_core_sources"] = [name for name in CORE_SOURCES
                    if repository["core_sources_sha256"][name] != repository["core_sources_sha256_at_end"][name]]
                report["status"] = "failed"
                report.setdefault("error", dict(type="CoreSourcesChanged",
                    message="Core execution sources changed during this run; performance results are not reproducible."))
                event("error", "source_integrity", changed_files=repository["changed_core_sources"])
            if torch is not None:
                report["cuda_memory"] = []
                for device in cuda_devices:
                    try:
                        report["cuda_memory"].append(dict(index=device,
                            peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
                            peak_reserved_bytes=torch.cuda.max_memory_reserved(device),
                            allocated_bytes_at_end=torch.cuda.memory_allocated(device),
                            reserved_bytes_at_end=torch.cuda.memory_reserved(device)))
                    except Exception as exc:
                        report["cuda_memory"].append(dict(index=device, error=str(exc)))
                        report["status"] = "failed"
            report["total_wall_s"] = time.perf_counter() - started
            report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            save_json(destination / "performance.json", report)
    print(json.dumps(dict(status=report["status"], output=str(destination),
                          pipeline_wall_s=report.get("pipeline_wall_s"), total_wall_s=report["total_wall_s"])))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main(exclusive_process=True))
