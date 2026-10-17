"""PTS and failure checks through an actual FFmpeg/PyAV container."""
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
import pytest

from app.vision.tracknet_rally import FlightConfig, ShuttlePoint
from app.vision.video_input import FileFrameSource

av = pytest.importorskip("av")


@pytest.fixture
def vfr_video(tmp_path):
    path = tmp_path / "vfr.mkv"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("ffv1", rate=30)
        stream.width = stream.height = 16
        stream.pix_fmt = "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        for index, timestamp in enumerate([0, 10, 50, 100]):
            frame = av.VideoFrame.from_ndarray(np.full((16, 16, 3), 50 * index, np.uint8), format="bgr24")
            frame.pts, frame.time_base = timestamp, Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_real_vfr_frames_and_timestamp_gaps_are_identical(vfr_video):
    decoded = []
    for mode in ("offline", "realtime"):
        with FileFrameSource(vfr_video, mode=mode) as source:
            decoded.append([(frame.frame_id, frame.timestamp_ms, frame.image.tobytes()) for frame in source])
    assert decoded[0] == decoded[1]
    assert [frame[1] for frame in decoded[0]] == [0, 10, 50, 100]


def runner_module():
    folder = Path(__file__).parent / "rally_benchmark"
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location("live_runner_test", folder / "run_live_tracknet.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(folder))


class Predictor:
    device = "cpu"
    last_timing = dict(preprocess_s=0.0, inference_and_transfer_s=0.0, point_decode_s=0.0)

    def __call__(self, frames):
        return [ShuttlePoint(0, 0, 0) for _ in frames]


def test_runner_flushes_logs_keeps_pending_frames_and_limits_label_coverage(vfr_video, tmp_path, monkeypatch):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(dict(segments=[dict(rally_id=1, start_ms=60, end_ms=100,
                                                   review_status="verified")])))
    runner = runner_module()
    monkeypatch.setattr(runner, "memory_sample", lambda predictor: dict(rss_mib=0))
    result = runner.run_file(vfr_video, tmp_path / "out", Predictor(), mode="offline",
                             config=FlightConfig(), limit_s=.07, max_lag_s=5, annotations=labels)
    assert result["status"] == "completed"
    assert result["input"]["frames_delivered"] == 3
    assert result["evaluation"]["truth_count"] == 0
    assert result["evaluation"]["outside_input_coverage_ids"] == [1]
    assert len((tmp_path / "out" / "tracknet-points.jsonl").read_text().splitlines()) == 3
    assert (tmp_path / "out" / "result.json").is_file()
    full = runner.run_file(vfr_video, tmp_path / "full", Predictor(), mode="offline",
                           config=FlightConfig(), limit_s=None, max_lag_s=5, annotations=None)
    assert full["input"]["frames_delivered"] == 4
    assert full["pending_model_frames"] == 1
    assert full["predictions"] == []


def test_runner_overload_and_invalid_media_save_explicit_failures(vfr_video, tmp_path, monkeypatch):
    class SlowPredictor(Predictor):
        def __call__(self, frames):
            time.sleep(.15)
            return super().__call__(frames)

    runner = runner_module()
    monkeypatch.setattr(runner, "memory_sample", lambda predictor: dict(rss_mib=0))
    result = runner.run_file(vfr_video, tmp_path / "overload", SlowPredictor(), mode="realtime",
                             config=FlightConfig(), limit_s=None, max_lag_s=.08, annotations=None)
    assert result["status"] == "failed"
    assert result["error"]["type"] == "InputOverload"
    assert result["predictions"] == []
    assert result["totals"]["process_s"] >= .15
    performance = [json.loads(line) for line in (tmp_path / "overload" / "performance.jsonl").read_text().splitlines()]
    assert performance[-1]["frame_id"] == 2
    assert performance[-1]["process_s"] >= .15
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    result = runner.run_file(broken, tmp_path / "invalid", Predictor(), mode="offline",
                             config=FlightConfig(), limit_s=None, max_lag_s=5, annotations=None)
    assert result["status"] == "failed"
    assert result["input"]["frames_delivered"] == 0
    assert json.loads((tmp_path / "invalid" / "result.json").read_text())["error"]


def test_runner_publishes_intervals_before_source_eof(vfr_video, tmp_path, monkeypatch, capsys):
    from app.vision.rally_stream import RallyInterval

    runner = runner_module()
    output = tmp_path / "publish"

    class Segmenter:
        def __init__(self, *args, **kwargs):
            self.last_diagnostics, self.pending = [], []
            self.start_ms, self.active = None, False

        def process(self, frame):
            if frame.frame_id == 1:
                return [RallyInterval(1, 0, 0, frame.timestamp_ms)]
            if frame.frame_id == 2:
                # Still consuming the source: the earlier result is already
                # readable by an external consumer, without waiting for EOF.
                rows = (output / "rally-intervals.jsonl").read_text().splitlines()
                assert len(rows) == 1 and json.loads(rows[0])["end_ms"] == 0
            return []

    monkeypatch.setattr(runner, "ShuttleRallySegmenter", Segmenter)
    monkeypatch.setattr(runner, "memory_sample", lambda predictor: dict(rss_mib=0))
    result = runner.run_file(vfr_video, output, Predictor(), mode="realtime",
                             config=FlightConfig(), limit_s=None, max_lag_s=5, annotations=None)
    assert result["status"] == "completed"
    assert result["predictions"][0]["emitted_at_ms"] == 10
    stdout = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert stdout[0]["event"] == "rally"
    assert stdout[0]["interval"] == result["predictions"][0]
