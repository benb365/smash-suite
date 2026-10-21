from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from app.benchmark import ResourceSampler, run_case, sha256, work_bytes
from modules.media.video import ffmpeg_exe, probe
from modules.models.tracknet import ShuttlePoint
from modules.rally.recognize import recognize
from modules.rally.statistics import Statistics


def test_nested_primary_times_are_exclusive_and_failure_is_saved(tmp_path, monkeypatch):
    ticks = iter([0., 2., 5., 9.])
    monkeypatch.setattr("modules.rally.statistics.time.monotonic", lambda: next(ticks))
    stats = Statistics(True)
    with pytest.raises(ValueError):
        with stats.phase("video_observation"):
            with stats.phase("rally_decision"):
                raise ValueError("synthetic failure")
    stats.write(tmp_path / "statistics.json", error="synthetic failure")
    data = json.loads((tmp_path / "statistics.json").read_text())
    assert data["seconds"] == {"video_observation": 6., "rally_decision": 3.}
    assert sum(data["seconds"].values()) == 9.
    assert data["error"] == "synthetic failure"
    disabled = Statistics()
    with disabled.phase("unused"):
        disabled.add("unused")
    disabled.write(tmp_path / "disabled.json")
    assert not (tmp_path / "disabled.json").exists()


def test_high_statistics_switch_preserves_predictions_and_decode(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    subprocess.run([ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12",
                    "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    class Predictor:
        def __init__(self, *args, statistics=None, **kwargs):
            self.statistics = statistics
        def __call__(self, images):
            self.statistics.add("tracknet_calls")
            return [ShuttlePoint(0., 0., 0.) for _ in images]
    monkeypatch.setattr("modules.rally.recognize.TrackNetPredictor", Predictor)
    import torch
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    info = probe(source, source.name)
    outputs = []
    for enabled in (False, True):
        stats = Statistics(enabled)
        predictions, details = recognize(source, info, "high", {"ball_track.pt": "fake"},
                                         lambda *args: None, tmp_path, statistics=stats)
        details.pop("recognition_wall_s")
        outputs.append((predictions, details))
        if enabled:
            assert stats.counts["frames_decoded"] == 12
            assert stats.counts["decode_passes"] == 1
            assert stats.counts["tracknet_calls"] == 4
            assert stats.seconds["rally_decision"] > 0
            assert stats.seconds["video_observation"] > 0
    assert outputs[0] == outputs[1]


def test_recursive_process_coverage_and_work_bytes(tmp_path):
    (tmp_path / "source.mp4").write_bytes(b"12345")
    (tmp_path / "result.json").write_bytes(b"123")
    assert work_bytes(tmp_path) == (8, 3)
    code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(4)']);time.sleep(4)"
    process = subprocess.Popen([sys.executable, "-c", code])
    try:
        sampler = ResourceSampler(process.pid, tmp_path, tmp_path / "samples.jsonl")
        deadline = time.monotonic() + 3
        while True:
            row = sampler.snapshot()
            if len(row["processes"]) >= 2:
                break
            assert time.monotonic() < deadline
            time.sleep(.05)
        assert process.pid in [p["pid"] for p in row["processes"]]
        assert len(row["processes"]) == 2
        assert row["rss_bytes"] > 0
        assert row["disk_free_bytes"] > 0
        assert not row["errors"]
    finally:
        for child in sampler.psutil.Process(process.pid).children(recursive=True):
            child.terminate()
        process.terminate()
        process.wait()


@pytest.mark.parametrize("profile_wait, fail", [(False, False), (True, False), (False, True)])
def test_runner_uses_product_http_lease_archive_and_original_timings(tmp_path, monkeypatch, profile_wait, fail):
    """Synthetic worker tests orchestration; it does not claim real model acceptance."""
    import shutil
    import threading
    from argparse import Namespace
    from app import benchmark
    original_root = benchmark.ROOT
    root = tmp_path / "fixture"
    backend = root / "apps/video-clipper/backend"
    shutil.copytree(original_root / "apps/video-clipper/backend/app", backend / "app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "modules").symlink_to(original_root / "modules", target_is_directory=True)
    (backend / "app/worker.py").write_text('''
import json, os, sys, time
from pathlib import Path
from modules.media.types import VideoInfo
from modules.media.video import render
spec=json.loads(Path(sys.argv[1]).read_text())
directory=Path(spec['directory'])
ready=dict(type='profile_ready',pid=os.getpid(),monotonic_s=time.monotonic())
(directory/'profile-ready.json').write_text(json.dumps(ready))
print(json.dumps(ready),flush=True)
if spec['benchmark']['profile_wait']:
    while not (directory/'profile-release').exists(): time.sleep(.01)
print(json.dumps(dict(type='benchmark_start',monotonic_s=time.monotonic())),flush=True)
time.sleep(.03)
print(json.dumps(dict(type='progress',stage='synthetic recognition',progress=.1,phase='recognition')),flush=True)
time.sleep(.03)
print(json.dumps(dict(type='progress',stage='synthetic rendering',progress=.8,phase='rendering')),flush=True)
info=VideoInfo(**spec['video'])
duration=render(directory/'source.mp4',directory/'output.mp4',[[100,900]],info,'balanced',lambda f:None)
(directory/'result.json').write_text(json.dumps(dict(predictions=[dict(start_ms=100,end_ms=900)],
    output_duration_ms=duration,export_ranges=[[100,900]],synthetic=True)))
''')
    if fail:
        worker_path = backend / "app/worker.py"
        worker_path.write_text(worker_path.read_text().replace("info=VideoInfo(**spec['video'])", "raise RuntimeError('synthetic worker failure')"))
    video = tmp_path / "input.mp4"
    subprocess.run([ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12",
                    "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    monkeypatch.setattr(benchmark, "ROOT", root)
    monkeypatch.setattr("modules.rally.scenarios.required_models", lambda scene: [])
    output = tmp_path / "run"
    output.mkdir()
    case = dict(case_id="synthetic", scene="high", video=str(video), court=None, sha256=sha256(video), status="passed")
    args = Namespace(output=output, models=tmp_path, profile_wait=profile_wait, profile_timeout=10,
                     mps_signposts=False, no_statistics=profile_wait, py_spy_path=None, timeout=30)
    errors = []
    def release():
        try:
            ready = output / "synthetic/profile-ready.json"
            deadline = time.monotonic() + 20
            while not ready.exists():
                assert time.monotonic() < deadline
                time.sleep(.01)
            payload = json.loads(ready.read_text())
            assert payload["type"] == "profile_ready"
            Path(payload["release_file"]).touch()
        except Exception as exc:
            errors.append(exc)
    releaser = threading.Thread(target=release)
    if profile_wait:
        releaser.start()
    result = run_case(case, args)
    if profile_wait:
        releaser.join(2)
    assert not errors
    if fail:
        assert result["status"] == "failed"
        assert "意外退出" in result["error"]
        evidence = output / "synthetic/evidence"
        assert "synthetic worker failure" in (evidence / "worker.log").read_text()
        assert (evidence / "benchmark-clock.json").exists()
        assert list((output / "synthetic/home/work").iterdir()) == []
        return
    assert result["status"] == "completed", result
    assert result["kind"] == ("profile" if profile_wait else "baseline")
    assert result["timings"] == dict(**result["state"]["timings"], total_s=result["state"]["elapsed_s"])
    assert sum(result["state"]["timings"].values()) == pytest.approx(result["timings"]["total_s"])
    evidence = output / "synthetic/evidence"
    assert (evidence / "output.mp4").stat().st_size > 0
    assert (evidence / "benchmark-clock.json").exists()
    spec = json.loads((evidence / "request.json").read_text())
    assert spec["benchmark"]["statistics_enabled"] is not profile_wait
    assert result["statistics_enabled"] is not profile_wait
    assert not (evidence / "source.mp4").exists()
    assert result["artifacts"]["output.mp4"]["sha256"] == sha256(evidence / "output.mp4")
    assert result["resources"]["pids"]
    assert list((output / "synthetic/home/work").iterdir()) == []


@pytest.mark.parametrize("scene", ["courtside", "personal"])
def test_file_scenario_statistics_switch_preserves_results(tmp_path, monkeypatch, scene):
    """Deterministic observations isolate the newly instrumented phase boundaries."""
    from modules.media.types import VideoInfo
    from modules.rally.types import RallyInterval
    import torch
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr("modules.rally.recognize.TrackNetPredictor", lambda *a, **kw: object())
    boxes = [dict(x1=0, y1=0, x2=10, y2=20), dict(x1=20, y1=20, x2=30, y2=40)]
    features = [dict(boxes=boxes, features=[[], []])] * 2
    monkeypatch.setattr("modules.rally.recognize.observe", lambda *a, **kw: ([{}] * 3, [{}] * 3, features))
    predicted = [RallyInterval(1, 100., 900., 950.)]
    if scene == "courtside":
        monkeypatch.setattr("modules.rally.common.player_paths.main_players", lambda *a: boxes)
        monkeypatch.setattr("modules.rally.common.player_paths.tracks", lambda *a:
                            [dict(players=[dict(box_index=0), dict(box_index=1)])])
        monkeypatch.setattr("modules.rally.common.shuttle_paths.observed_candidates", lambda *a: [])
        monkeypatch.setattr("modules.rally.common.shuttle_paths.associate", lambda *a: [])
        monkeypatch.setattr("modules.rally.scenarios.courtside.predict", lambda *a: (predicted, {"synthetic": True}))
    else:
        monkeypatch.setattr("modules.rally.common.players_v2.track_all", lambda *a: [])
        monkeypatch.setattr("modules.rally.common.players_v2.select", lambda *a: ([dict(track_id=1), dict(track_id=2)], None))
        monkeypatch.setattr("modules.rally.common.players_v2.follow", lambda *a: [])
        monkeypatch.setattr("modules.rally.candidate_rally.candidate_motion", lambda *a, **kw: [])
        monkeypatch.setattr("modules.rally.recognize.person_signals", lambda *a: dict(times=np.array([0., 1000.])))
        monkeypatch.setattr("modules.rally.common.feet.add_foot_signals", lambda *a: None)
        monkeypatch.setattr("modules.rally.scenarios.personal.predict", lambda *a: (predicted, {"synthetic": True}))
    outputs = []
    info = VideoInfo(name="synthetic.mp4", duration_ms=1000, width=1920, height=1080, has_audio=False, first_pts_ms=0)
    for enabled in (False, True):
        directory = tmp_path / str(enabled)
        directory.mkdir()
        stats = Statistics(enabled)
        result, details = recognize(Path("synthetic.mp4"), info, scene,
            {"ball_track.pt": "fake", "yolo11n.pt": "fake", "pose_kpRCNN.pth": "fake"},
            lambda *a: None, directory, statistics=stats)
        details.pop("recognition_wall_s")
        outputs.append((result, details, json.loads((directory / "decisions.json").read_text())))
        if enabled:
            assert stats.seconds["rally_decision"] >= 0
            assert stats.seconds["intermediate_writes"] >= 0
    assert outputs[0] == outputs[1]


def test_statistics_off_requires_profiling_mode(tmp_path):
    from app.benchmark import main
    with pytest.raises(SystemExit) as exc:
        main(["--inputs", str(tmp_path / "unused.json"), "--cases", "unused", "--models", str(tmp_path),
              "--output", str(tmp_path / "output"), "--report", str(tmp_path / "report.json"), "--no-statistics"])
    assert exc.value.code == 2
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("statistics_enabled", [False, True])
def test_worker_statistics_switch_keeps_profile_handshake_and_signposts(tmp_path, monkeypatch, capsys, statistics_enabled):
    from contextlib import contextmanager
    import torch
    from app.worker import main
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "YOLO_CONFIG_DIR", "MPLCONFIGDIR"):
        monkeypatch.setenv(name, "test-before-worker")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr("modules.models.assets.ensure_models", lambda *a, **kw: {})
    enabled = []
    def fake_recognize(*args, statistics, **kwargs):
        enabled.append(statistics.enabled)
        statistics.add("synthetic_calls")
        return [dict(start_ms=100, end_ms=900)], {}
    monkeypatch.setattr("modules.rally.recognize.recognize", fake_recognize)
    def fake_render(source, destination, *args):
        destination.write_bytes(b"synthetic-output")
        return 800
    monkeypatch.setattr("modules.media.video.render", fake_render)
    signpost_calls = []
    @contextmanager
    def signposts(**kwargs):
        signpost_calls.append(kwargs)
        yield
    monkeypatch.setattr(torch.mps.profiler, "profile", signposts)
    (tmp_path / "profile-release").touch()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(dict(directory=str(tmp_path), models=str(tmp_path),
        options=dict(camera_type="high", quality="balanced"),
        video=dict(name="synthetic.mp4", duration_ms=1000, width=320, height=180, has_audio=False, first_pts_ms=0),
        benchmark=dict(statistics_enabled=statistics_enabled, profile_wait=True, mps_signposts=True))))
    assert main(str(request_path)) == 0
    assert enabled == [statistics_enabled]
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(event["type"] == "profile_ready" for event in events)
    assert any(event["type"] == "benchmark_start" for event in events)
    assert signpost_calls == [dict(mode="interval,event", wait_until_completed=False)]
    assert (tmp_path / "profile-ready.json").exists()
    assert (tmp_path / "statistics.json").exists() is statistics_enabled
    assert json.loads((tmp_path / "result.json").read_text())["predictions"] == [dict(start_ms=100, end_ms=900)]
