from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.media import ffmpeg_exe, probe, render, selected_ranges
from app.product_types import ProcessRequest
from app.runtime import Runtime
from app.sessions import Sessions


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    path = tmp_path_factory.mktemp("product-media") / "input.mp4"
    subprocess.run([ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25",
                    "-itsoffset", "0.25", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000",
                    "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(path)], check=True)
    return path


def test_ranges_clip_sort_merge_and_reject_invalid():
    assert selected_ranges([dict(start_ms=2000, end_ms=3000), dict(start_ms=100, end_ms=1200),
                            dict(start_ms=2500, end_ms=7000)], 6000) == [[0, 6000]]
    with pytest.raises(ValueError):
        selected_ranges([dict(start_ms=float("nan"), end_ms=2)], 6000)
    with pytest.raises(ValueError):
        ProcessRequest(camera_type="courtside", court=[(0, 0), (1, 1), (1, 0), (0, 1)])


def test_session_isolation_host_origin_and_no_history(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        a, b = client.post("/api/sessions").json(), client.post("/api/sessions").json()
        target = f"/api/sessions/{a['id']}"
        assert client.get(target).status_code == 404
        assert client.get(target, headers={"Authorization": f"Bearer {b['token']}"}).status_code == 404
        assert client.get(target, headers={"Authorization": f"Bearer {a['token']}"}).status_code == 200
        assert client.get("/api/sessions").status_code in (404, 405)
        assert client.post("/api/sessions", headers={"Origin": "https://example.com"}).status_code == 403
        assert client.post("/api/sessions", headers={"Host": "attacker.example"}).status_code == 403
        assert client.get("/api/sessions/anything/calibration").status_code == 404
    assert list((tmp_path / "work").iterdir()) == []


def test_upload_auth_frame_and_disconnect_resume(tmp_path, video):
    with TestClient(create_app(tmp_path)) as client:
        a = client.post("/api/sessions").json()
        target = f"/api/sessions/{a['id']}"
        headers = {"Authorization": f"Bearer {a['token']}", "X-File-Name": "training.mp4"}
        with client.websocket_connect(f"/ws/sessions/{a['id']}") as ws:
            ws.send_json({"token": a["token"]})
            assert ws.receive_json()["status"] == "empty"
            result = client.post(target + "/video", content=video.read_bytes(), headers=headers)
            assert result.status_code == 200, result.text
            assert result.json()["video"]["has_audio"] is True
            assert result.json()["video"]["duration_ms"] == pytest.approx(6000, abs=40)
            assert client.get(target + "/frame.jpg", headers=headers).headers["content-type"] == "image/jpeg"
        # The tab may reload and reattach during the lease without a new job.
        assert client.get(target, headers=headers).json()["status"] == "ready"
        with client.websocket_connect(f"/ws/sessions/{a['id']}") as ws:
            ws.send_json({"token": a["token"]})
            assert ws.receive_json()["status"] == "ready"
        bad = client.post(target + "/video", content=b"broken", headers=headers)
        assert bad.status_code == 400
        assert client.get(target, headers=headers).json()["status"] == "failed"


def test_expiry_removes_work_and_preserves_models(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "keep").write_text("model cache")
    with TestClient(create_app(tmp_path, lease_s=.01)) as client:
        a = client.post("/api/sessions").json()
        store = client.app.state.sessions
        directory = store.items[a["id"]].directory
        (directory / "private-video.mp4").write_bytes(b"temporary")
        time.sleep(1.1)
        assert not directory.exists()
        assert client.get(f"/api/sessions/{a['id']}", headers={"Authorization": f"Bearer {a['token']}"}).status_code == 404
    assert (tmp_path / "models" / "keep").read_text() == "model cache"


def test_cancel_during_upload_probe_cannot_publish_ready(tmp_path, video, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow_probe(*args):
        entered.set()
        assert release.wait(5)
        return probe(*args)

    monkeypatch.setattr("app.main.probe", slow_probe)
    with TestClient(create_app(tmp_path)) as client, ThreadPoolExecutor() as pool:
        a = client.post("/api/sessions").json()
        target = f"/api/sessions/{a['id']}"
        headers = {"Authorization": f"Bearer {a['token']}"}
        upload = pool.submit(client.post, target + "/video", content=video.read_bytes(), headers=headers)
        try:
            assert entered.wait(5)
            result = client.post(target + "/cancel", headers=headers)
            assert result.status_code == 200
            assert result.json()["status"] == "cancelled"
        finally:
            release.set()
        assert upload.result(timeout=5).status_code == 409
        assert client.get(target, headers=headers).json()["status"] == "cancelled"
        directory = client.app.state.sessions.items[a["id"]].directory
        assert not (directory / "source.mp4").exists()
        assert not (directory / "upload.part").exists()


def test_cancel_during_worker_creation_terminates_spawned_process(tmp_path, video, monkeypatch):
    async def scenario():
        runtime = Runtime(tmp_path)
        store = Sessions(runtime)
        session = store.create()
        session.state.video, session.state.status = probe(video, video.name), "ready"
        entered, release = asyncio.Event(), asyncio.Event()
        children = []
        original = asyncio.create_subprocess_exec

        async def delayed_spawn(*command, **kwargs):
            entered.set()
            await release.wait()
            process = await original(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
            children.append(process)
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
        try:
            await store.start(session, ProcessRequest(camera_type="high"))
            await entered.wait()
            cancelled = asyncio.create_task(store.cancel(session))
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(cancelled, 5)
            assert session.state.status == "cancelled"
            assert session.task.done()
            assert len(children) == 1 and children[0].returncode is not None
            assert store.busy is None
        finally:
            await store.close(session)
            runtime.close()

    asyncio.run(scenario())


def test_completed_timings_survive_reconnect_and_clear_on_restart(tmp_path, video, monkeypatch):
    original = asyncio.create_subprocess_exec
    script = """
import json, pathlib, shutil, sys, time
directory = pathlib.Path(json.loads(pathlib.Path(sys.argv[1]).read_text())["directory"])
time.sleep(.03)
print(json.dumps(dict(type="progress", stage="识别", progress=.08, phase="recognition")), flush=True)
time.sleep(.05)
print(json.dumps(dict(type="progress", stage="成片", progress=.8, phase="rendering")), flush=True)
time.sleep(.04)
shutil.copyfile(directory / "source.mp4", directory / "output.mp4")
(directory / "result.json").write_text(json.dumps(dict(predictions=[{}], output_duration_ms=6000)))
"""

    async def spawn(*command, **kwargs):
        return await original(sys.executable, "-c", script, command[-1], **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with TestClient(create_app(tmp_path)) as client:
        session = client.post("/api/sessions").json()
        target = f"/api/sessions/{session['id']}"
        headers = {"Authorization": f"Bearer {session['token']}"}
        assert client.post(target + "/video", content=video.read_bytes(), headers=headers).status_code == 200
        with client.websocket_connect(f"/ws/sessions/{session['id']}") as ws:
            ws.send_json({"token": session["token"]})
            assert ws.receive_json()["status"] == "ready"
            assert client.post(target + "/run", json={"camera_type": "high"}, headers=headers).status_code == 202
            while True:
                completed = ws.receive_json()
                if completed["status"] in ("completed", "failed"):
                    break
            assert completed["status"] == "completed", completed
            assert completed["timings"]["preparation_s"] >= .03
            assert completed["timings"]["recognition_s"] >= .04
            assert completed["timings"]["rendering_s"] >= .03
            assert sum(completed["timings"].values()) == pytest.approx(completed["elapsed_s"])
        assert client.get(target, headers=headers).json()["timings"] == completed["timings"]
        with client.websocket_connect(f"/ws/sessions/{session['id']}") as ws:
            ws.send_json({"token": session["token"]})
            restored = ws.receive_json()
            assert restored["timings"] == completed["timings"]
            assert restored["elapsed_s"] == completed["elapsed_s"]
            restarted = client.post(target + "/run", json={"camera_type": "high"}, headers=headers).json()
            assert restarted["status"] == "running"
            assert restarted["timings"] is None and restarted["elapsed_s"] is None
            assert client.post(target + "/cancel", headers=headers).status_code == 200


def test_media_range_and_capability_revoked_on_cleanup(tmp_path, video):
    with TestClient(create_app(tmp_path)) as client:
        a = client.post("/api/sessions").json()
        store = client.app.state.sessions
        session = store.items[a["id"]]
        (session.directory / "output.mp4").write_bytes(video.read_bytes())
        session.state.status = "completed"
        url = f"/media/{session.media_key}/output.mp4"
        response = client.get(url, headers={"Range": "bytes=0-15"})
        assert response.status_code == 206
        assert response.content == video.read_bytes()[:16]
        assert client.get("/media/wrong-key/output.mp4").status_code == 404
        assert client.delete(f"/api/sessions/{a['id']}", headers={"Authorization": f"Bearer {a['token']}"}).status_code == 204
        assert client.get(url).status_code == 404


@pytest.mark.parametrize("quality", ["high", "balanced", "small"])
def test_render_real_cuts_and_original_audio(tmp_path, video, quality):
    info = probe(video, "input.mp4")
    destination = tmp_path / f"{quality}.mp4"
    duration = render(video, destination, [[0, 1000], [4000, 5000]], info, quality, lambda p: None)
    assert duration == 2000
    with av.open(str(destination)) as container:
        frames = list(container.decode(video=0))
        assert len(frames) == 50
        assert frames[0].width == 320 and frames[0].height == 180
        times = [float(f.pts * f.time_base) for f in frames]
        assert np.all(np.diff(times) > 0)
        assert times[-1] == pytest.approx(1.96, abs=.04)
    with av.open(str(destination)) as container:
        audio = np.concatenate([f.to_ndarray().ravel() for f in container.decode(audio=0)])
        # Preserve the source's delayed start instead of moving it to time 0.
        assert np.sqrt(np.mean(audio[3000:6000] ** 2)) < .002
        assert np.sqrt(np.mean(audio[18000:30000] ** 2)) > .03
    with pytest.raises(ValueError, match="没有识别"):
        render(video, destination, [], info, quality, lambda p: None)


def test_render_silent_variable_frame_timestamps(tmp_path):
    source = tmp_path / "vfr.mp4"
    pts = [0, 40, 100, 180, 220, 300, 340, 400, 480, 540, 600]
    with av.open(str(source), "w") as container:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 320, 180, "yuv420p"
        stream.codec_context.time_base = Fraction(1, 1000)
        for i, timestamp in enumerate(pts):
            frame = av.VideoFrame.from_ndarray(np.full((180, 320, 3), i * 20, dtype=np.uint8), format="rgb24")
            frame.pts, frame.time_base = timestamp, Fraction(1, 1000)
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    info = probe(source, source.name)
    assert not info.has_audio
    output = tmp_path / "vfr-cut.mp4"
    render(source, output, [[40, 220], [300, 540]], info, "balanced", lambda p: None)
    with av.open(str(output)) as container:
        assert not container.streams.audio
        stream = container.streams.video[0]
        assert float(stream.duration * stream.time_base * 1000) == pytest.approx(420, abs=1)
        frames = list(container.decode(video=0))
        actual = [float(f.pts * f.time_base * 1000) for f in frames]
        assert actual == pytest.approx([0, 60, 140, 180, 220, 280, 360], abs=1)
        assert [int(np.mean(f.to_ndarray(format="rgb24"))) for f in frames] == pytest.approx([20, 40, 60, 100, 120, 140, 160], abs=3)


def test_render_fractional_frame_boundaries_with_nonzero_origin(tmp_path):
    source = tmp_path / "30fps.mp4"
    with av.open(str(source), "w") as container:
        stream = container.add_stream("libx264", rate=30)
        stream.width, stream.height, stream.pix_fmt = 320, 180, "yuv420p"
        stream.codec_context.time_base = Fraction(1, 15360)
        for i in range(90):
            image = np.full((180, 320, 3), (i * 37) % 240, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            frame.pts, frame.time_base = 1014 + i * 512, Fraction(1, 15360)
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    info = probe(source, source.name)
    assert info.first_pts_ms > 0
    output = tmp_path / "fractional-cut.mp4"
    ranges = [[13 / 30 * 1000, 29 / 30 * 1000], [59 / 30 * 1000, 79 / 30 * 1000]]
    render(source, output, ranges, info, "balanced", lambda p: None)
    with av.open(str(source)) as container:
        originals = [float(f.to_ndarray(format="rgb24").mean()) for f in container.decode(video=0)]
    with av.open(str(output)) as container:
        frames = list(container.decode(video=0))
        selected = list(range(13, 29)) + list(range(59, 79))
        assert len(frames) == len(selected)
        assert [float(f.to_ndarray(format="rgb24").mean()) for f in frames] == pytest.approx(
            [originals[i] for i in selected], abs=3)
        assert [float(f.pts * f.time_base) for f in frames] == pytest.approx(
            [i / 30 for i in range(36)], abs=1 / 15360)
