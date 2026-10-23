"""The product worker forwards explicit pose settings without changing its API."""
import json

import pytest

from app import worker


@pytest.mark.parametrize("device,batch,expected", [
    (None, None, {}),
    ("cpu", "2", {"pose_device": "cpu", "pose_batch_size": 2}),
    ("cuda", "1", {"pose_device": "cuda", "pose_batch_size": 1}),
])
def test_worker_passes_pose_settings_to_recognizer(tmp_path, monkeypatch, device, batch, expected):
    from modules.models import assets
    from modules.media import video
    from modules.rally import recognize
    from modules.rally.statistics import Statistics

    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                "YOLO_CONFIG_DIR", "MPLCONFIGDIR"):
        monkeypatch.setenv(key, "test-original-value")
    for key, value in (("SMASH_SUITE_POSE_DEVICE", device),
                       ("SMASH_SUITE_POSE_BATCH_SIZE", batch)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    calls = []

    def fake_recognize(source, info, scene, weights, progress, directory, **options):
        calls.append(options)
        return [dict(start_ms=100, end_ms=800)], dict(warnings=[], performance={})

    def fake_render(source, destination, ranges, info, quality, progress):
        destination.write_bytes(b"unit-test-output")
        return sum(z - a for a, z in ranges)

    monkeypatch.setattr(assets, "ensure_models", lambda *args: {})
    monkeypatch.setattr(recognize, "recognize", fake_recognize)
    monkeypatch.setattr(video, "render", fake_render)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(dict(directory=str(tmp_path), models=str(tmp_path / "models"),
        options=dict(camera_type="personal", quality="balanced"),
        video=dict(name="测试录像.mp4", duration_ms=1000, width=64, height=36,
                   has_audio=False, first_pts_ms=0))), encoding="utf-8")
    assert worker.main(str(request)) == 0
    defaults = dict(limit_fps=True, small_input=True, grayscale=True, dynamic_scan=False)
    assert len(calls) == 1
    statistics = calls[0]["statistics"]
    assert isinstance(statistics, Statistics)
    assert statistics.enabled is False
    assert calls == [dict(court=None, statistics=statistics, optimizations=defaults, **expected)]
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["predictions"] == [dict(start_ms=100, end_ms=800)]
    assert result["optimizations"] == defaults
    assert (tmp_path / "output.mp4").read_bytes() == b"unit-test-output"
