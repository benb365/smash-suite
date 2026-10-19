from __future__ import annotations

import json
import os
import sys
import traceback
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
    try:
        # Third-party imports otherwise write settings outside the workspace.
        # YOLO appends its own subdirectory and requires this parent to exist.
        for name, path in (("YOLO_CONFIG_DIR", directory), ("MPLCONFIGDIR", directory / "matplotlib")):
            path.mkdir(exist_ok=True)
            os.environ[name] = str(path)
        from app.model_assets import ensure_models
        from app.media import render, selected_ranges
        from app.product_types import ProcessRequest, VideoInfo
        options = ProcessRequest(**spec["options"])
        info = VideoInfo(**spec["video"])
        weights = ensure_models(options.camera_type, Path(spec["models"]),
                                lambda stage, fraction: event(stage, .08 * fraction))
        from app.recognize import recognize
        event("正在识别对打回合", .08, phase="recognition")
        predictions, details = recognize(directory / "source.mp4", info, options, weights,
                                         lambda stage, fraction: event(stage, .08 + .72 * fraction), directory)
        ranges = selected_ranges(predictions, info.duration_ms)
        event("正在生成带原声音的成片", .8, phase="rendering")
        duration_ms = render(directory / "source.mp4", directory / "output.mp4", ranges, info, options.quality,
                             lambda fraction: event("正在生成带原声音的成片", .8 + .2 * fraction))
        result = dict(predictions=predictions, export_ranges=ranges, output_duration_ms=duration_ms,
                      quality=options.quality, padding_ms=500, **details)
        (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        (directory / "result.json").write_text(json.dumps(dict(error=str(exc)), ensure_ascii=False), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
