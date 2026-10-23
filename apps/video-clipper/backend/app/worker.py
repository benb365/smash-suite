from __future__ import annotations

import json
import os
import sys
import traceback
import time
from contextlib import nullcontext
from pathlib import Path


def event(stage, progress, *, phase=None):
    message = dict(type="progress", stage=stage, progress=min(1, max(0, progress)))
    if phase:
        message["phase"] = phase
    print(json.dumps(message, ensure_ascii=False), flush=True)


def main(request_path: str):
    # Set before importing numerical libraries. A single local job should not
    # create an unbounded CPU thread pool alongside the GPU workload.
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    spec = json.loads(Path(request_path).read_text())
    directory = Path(spec["directory"])
    from modules.rally.statistics import Statistics
    benchmark = spec.get("benchmark")
    statistics = Statistics(bool(benchmark) and benchmark.get("statistics_enabled", True))
    failure = None
    resolved_optimizations = None
    try:
        # Third-party imports otherwise write settings outside the workspace.
        # YOLO appends its own subdirectory and requires this parent to exist.
        for name, path in (("YOLO_CONFIG_DIR", directory), ("MPLCONFIGDIR", directory / "matplotlib")):
            path.mkdir(exist_ok=True)
            os.environ[name] = str(path)
        from modules.models.assets import ensure_models
        from modules.rally.scenarios import required_models
        from modules.media.video import render, selected_ranges
        from app.product_types import ProcessRequest
        from modules.media.types import VideoInfo
        options = ProcessRequest(**spec["options"])
        resolved_optimizations = options.optimizations.model_dump()
        info = VideoInfo(**spec["video"])
        from modules.rally.recognize import recognize
        if benchmark and benchmark.get("profile_wait"):
            ready = dict(type="profile_ready", pid=os.getpid(), monotonic_s=time.monotonic())
            (directory / "profile-ready.json").write_text(json.dumps(ready))
            print(json.dumps(ready), flush=True)
            deadline = time.monotonic() + benchmark.get("profile_timeout_s", 300)
            while not (directory / "profile-release").exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Profiler did not release worker within handshake timeout")
                time.sleep(.05)
        if benchmark:
            print(json.dumps(dict(type="benchmark_start", monotonic_s=time.monotonic())), flush=True)
        model_names = required_models(options.camera_type)
        if options.camera_type == "high" and options.show_shot_paths and "yolo11n.pt" not in model_names:
            model_names.append("yolo11n.pt")
        weights = ensure_models(model_names, Path(spec["models"]),
                                lambda stage, fraction: event(stage, .08 * fraction))
        event("正在识别对打回合", .08, phase="recognition")
        # Profiler attachment happens after imports and before normal model work.
        # Profiling runs include this pause and must never be used as baseline timings.
        signposts = nullcontext()
        if benchmark and benchmark.get("mps_signposts"):
            import torch
            signposts = torch.mps.profiler.profile(mode="interval,event", wait_until_completed=False)
        source = directory / "source.mp4"
        shot_paths = None
        overlay_ass = None
        show_shot_paths = options.camera_type == "high" and options.show_shot_paths
        if show_shot_paths:
            from modules.trajectory import ObservationLog, analyze
            point_path = directory / "ball-observations.jsonl"
            with statistics.mps_sampling(), signposts, ObservationLog(
                    point_path, source=source, info=info, weight=weights["ball_track.pt"]) as observation_sink:
                predictions, details = recognize(source, info, options.camera_type, weights,
                                                  lambda stage, fraction: event(stage, .08 + .72 * fraction),
                                                  directory, court=options.court, statistics=statistics,
                                                  observation_sink=observation_sink, optimizations=resolved_optimizations)
            shot_paths = analyze(source, info, predictions, point_path, weights, directory,
                                 lambda stage, fraction: event(stage, .08 + .72 * fraction))
            (directory / "shot-paths.json").write_text(json.dumps(shot_paths, ensure_ascii=False), encoding="utf-8")
        else:
            # A previous run in this leased session may have had the option enabled.
            for name in ("ball-observations.jsonl", "ball-observations.meta.json", "shot-paths.json", "trajectory-overlay.ass"):
                (directory / name).unlink(missing_ok=True)
        with statistics.mps_sampling(), signposts:
            if not show_shot_paths:
                predictions, details = recognize(source, info, options.camera_type, weights,
                                                 lambda stage, fraction: event(stage, .08 + .72 * fraction),
                                                 directory, court=options.court, statistics=statistics,
                                                 optimizations=resolved_optimizations)
        ranges = selected_ranges(predictions, info.duration_ms, padding_ms=500)
        event("正在生成带原声音的成片", .8, phase="rendering")
        if shot_paths is not None:
            from app.trajectory_overlay import write_overlay
            overlay_ass = directory / "trajectory-overlay.ass"
            write_overlay(shot_paths, ranges, overlay_ass, info.width, info.height)
        render_args = (source, directory / "output.mp4", ranges, info, options.quality,
                       lambda fraction: event("正在生成带原声音的成片", .8 + .2 * fraction))
        duration_ms = (render(*render_args, overlay_ass=overlay_ass) if overlay_ass is not None
                       else render(*render_args))
        result = dict(predictions=predictions, export_ranges=ranges, output_duration_ms=duration_ms,
                      quality=options.quality, padding_ms=500,
                      optimizations=resolved_optimizations, **details)
        (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    except Exception as exc:
        failure = str(exc)
        traceback.print_exc(file=sys.stderr)
        (directory / "result.json").write_text(json.dumps(dict(error=str(exc),
                                    optimizations=resolved_optimizations), ensure_ascii=False), encoding="utf-8")
        return 1
    finally:
        statistics.write(directory / "statistics.json", error=failure)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
