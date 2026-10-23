from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.benchmark import ResourceSampler, run_case, sha256, work_bytes
from modules.media.video import ffmpeg_exe, probe
from modules.models.tracknet import ShuttlePoint
from modules.rally.recognize import recognize
from modules.rally.statistics import Statistics


@pytest.mark.parametrize("outcome", ["success", "missing", "nonzero", "timeout"])
def test_windows_backend_tree_termination_is_bounded_and_reports_failures(tmp_path, monkeypatch, outcome):
    from app import benchmark

    system_root = tmp_path / "Windows"
    monkeypatch.setattr(benchmark, "os", SimpleNamespace(name="nt", environ={"SystemRoot": str(system_root)}))
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    class Backend:
        pid = 12345
        returncode = None
        terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15

    backend = Backend()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if outcome == "missing":
            raise FileNotFoundError("synthetic missing taskkill")
        if outcome == "nonzero":
            raise subprocess.CalledProcessError(1, command)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 5)
        backend.returncode = 0
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    error = benchmark.terminate_backend(backend)

    assert calls == [([str(system_root / "System32" / "taskkill.exe"), "/PID", "12345", "/T", "/F"],
                     dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          creationflags=0x08000000, check=True, timeout=5))]
    assert backend.terminated is (outcome != "success")
    assert backend.poll() is not None
    if outcome == "success":
        assert error is None
    else:
        assert "tree termination unverified" in error
        assert {"missing": "FileNotFoundError", "nonzero": "CalledProcessError",
                "timeout": "TimeoutExpired"}[outcome] in error


@pytest.mark.parametrize("teardown", [False, True])
def test_lease_disconnect_is_only_suppressed_after_teardown_starts(monkeypatch, teardown):
    import threading
    from app.benchmark import keep_lease

    stop, errors, sent = threading.Event(), [], []

    class Socket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def send(self, message): sent.append(message)

        def recv(self, timeout):
            assert timeout == .5
            if teardown:
                # The runner marks teardown before DELETE closes this socket.
                stop.set()
            raise RuntimeError("received 1001 going away")

    monkeypatch.setattr("websockets.sync.client.connect", lambda *args, **kwargs: Socket())
    keep_lease("ws://unused", "unit-token", stop, errors)
    assert sent == [json.dumps(dict(token="unit-token"))]
    assert errors == ([] if teardown else ["received 1001 going away"])


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
            self.input_size = self.content_size = (288, 512)
            self.color_mode = "rgb"
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
            assert "rally_decision" in stats.seconds
            assert stats.seconds["rally_decision"] >= 0
            assert "video_observation" in stats.seconds
            assert stats.seconds["video_observation"] >= 0
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
@pytest.mark.parametrize("optimizations", [None, dict(limit_fps=False, small_input=False, grayscale=False, dynamic_scan=False)])
def test_runner_uses_product_http_lease_archive_and_original_timings(
        tmp_path, monkeypatch, profile_wait, fail, optimizations):
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
    if optimizations is not None:
        case["optimizations"] = optimizations
    args = Namespace(output=output, models=tmp_path, profile_wait=profile_wait, profile_timeout=10,
                     mps_signposts=False, no_statistics=profile_wait, py_spy_path=None, timeout=30)
    original_lease, original_request = benchmark.keep_lease, benchmark.request
    lease_stops = []

    def recorded_lease(url, token, stop, errors):
        lease_stops.append(stop)
        return original_lease(url, token, stop, errors)

    def checked_request(method, url, **kwargs):
        if method == "DELETE":
            assert lease_stops and lease_stops[0].is_set()
            assert (output / "synthetic/evidence/benchmark-clock.json").is_file()
        return original_request(method, url, **kwargs)

    monkeypatch.setattr(benchmark, "keep_lease", recorded_lease)
    monkeypatch.setattr(benchmark, "request", checked_request)
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
    assert result["lease_errors"] == []
    assert "cleanup_error" not in result
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
    expected = optimizations or dict(limit_fps=True, small_input=True, grayscale=True, dynamic_scan=True)
    assert spec["options"]["optimizations"] == expected
    assert spec["options"]["show_shot_paths"] is False
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
    from types import SimpleNamespace
    monkeypatch.setattr("modules.rally.recognize.TrackNetPredictor", lambda *a, **kw:
                        SimpleNamespace(input_size=(288, 512), content_size=(288, 512), color_mode="rgb"))
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
        def person_signals(*args, metrics, pose_device, **kwargs):
            metrics.update(pose_device=pose_device, pose_model=dict(
                initialization_s=0., tensor_preparation_s=0., inference_and_transfer_s=0.,
                batch_count=0, crop_count=0))
            return dict(times=np.array([0., 1000.]))
        monkeypatch.setattr("modules.rally.recognize.person_signals", person_signals)
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
    monkeypatch.setenv("SMASH_SUITE_POSE_DEVICE", "cuda")
    monkeypatch.setenv("SMASH_SUITE_POSE_BATCH_SIZE", "2")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr("modules.models.assets.ensure_models", lambda *a, **kw: {})
    enabled = []
    def fake_recognize(*args, statistics, **kwargs):
        assert kwargs["pose_device"] == "cuda"
        assert kwargs["pose_batch_size"] == 2
        assert kwargs["optimizations"] == dict(limit_fps=True, small_input=True, grayscale=True, dynamic_scan=True)
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
        options=dict(camera_type="high", quality="balanced", show_shot_paths=False),
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


@pytest.mark.parametrize("mps_signposts", [False, True])
def test_worker_synthetic_shot_path_pipeline_stays_in_recognition(tmp_path, monkeypatch, capsys, mps_signposts):
    from app.worker import main
    import modules.trajectory as trajectory
    import torch
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setenv("SMASH_SUITE_POSE_DEVICE", "cuda")
    monkeypatch.setenv("SMASH_SUITE_POSE_BATCH_SIZE", "2")

    calls = []
    signpost_calls, signpost_events = [], []

    class OneShotSignposts:
        def __init__(self):
            self.entered = False

        def __enter__(self):
            if self.entered:
                raise RuntimeError("Signposts context cannot be entered twice")
            self.entered = True
            signpost_events.append("enter")
            return self

        def __exit__(self, *_):
            signpost_events.append("exit")

    def profile(**kwargs):
        signpost_calls.append(kwargs)
        return OneShotSignposts()

    monkeypatch.setattr(torch.mps.profiler, "profile", profile)

    class ObservationLog:
        def __init__(self, path, **metadata):
            self.path = path
            calls.append(("log-open", metadata))

        def __enter__(self):
            return self

        def __call__(self, frame, point):
            calls.append(("observation", frame, point))

        def __exit__(self, *_):
            self.path.write_text('{"frame_id":1}\n')
            self.path.with_suffix(".meta.json").write_text('{"complete":true}')

    def recognize(*args, observation_sink, **kwargs):
        assert kwargs["pose_device"] == "cuda"
        assert kwargs["pose_batch_size"] == 2
        assert kwargs["optimizations"] == dict(limit_fps=True, small_input=True, grayscale=True, dynamic_scan=True)
        observation_sink({"frame_id": 1}, {"x": 100, "y": 200})
        calls.append(("recognize", kwargs))
        return [dict(start_ms=100, end_ms=900)], {}

    def analyze(*args):
        calls.append(("analyze", args[-1]))
        return {"schema_version": 1, "shots": [dict(start_ms=100, end_ms=900, start_xy=[1, 2],
                                                        end_xy=[4, 10], end_kind="next_hit")]}

    def render(source, output, ranges, info, quality, progress, *, overlay_ass=None):
        assert overlay_ass and overlay_ass.is_file()
        calls.append(("render", ranges, overlay_ass))
        output.write_bytes(b"synthetic-output")
        return sum(end - start for start, end in ranges)

    requested_models = []
    def ensure_models(names, *args, **kwargs):
        requested_models.extend(names)
        return {name: f"fake-{name}" for name in names}

    monkeypatch.setattr("modules.models.assets.ensure_models", ensure_models)
    monkeypatch.setattr("modules.rally.recognize.recognize", recognize)
    monkeypatch.setattr("modules.media.video.render", render)
    monkeypatch.setattr(trajectory, "ObservationLog", ObservationLog)
    monkeypatch.setattr(trajectory, "analyze", analyze)
    request_path = tmp_path / "request.json"
    (tmp_path / "source.mp4").write_bytes(b"synthetic-source")
    spec = dict(directory=str(tmp_path), models=str(tmp_path),
        options=dict(camera_type="high", quality="balanced", show_shot_paths=True),
        video=dict(name="synthetic.mp4", duration_ms=1000, width=320, height=180, has_audio=False, first_pts_ms=0))
    if mps_signposts:
        spec["benchmark"] = dict(mps_signposts=True)
    request_path.write_text(json.dumps(spec))

    assert main(str(request_path)) == 0
    assert requested_models == ["ball_track.pt", "yolo11n.pt"]
    assert [call[0] for call in calls] == ["log-open", "observation", "recognize", "analyze", "render"]
    assert signpost_calls == ([dict(mode="interval,event", wait_until_completed=False)] if mps_signposts else [])
    assert signpost_events == (["enter", "exit"] if mps_signposts else [])
    assert (tmp_path / "ball-observations.jsonl").exists()
    assert (tmp_path / "ball-observations.meta.json").exists()
    assert json.loads((tmp_path / "shot-paths.json").read_text())["shots"][0]["end_kind"] == "next_hit"
    assert (tmp_path / "trajectory-overlay.ass").is_file()
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event.get("phase") for event in events if event.get("phase")] == ["recognition", "rendering"]
