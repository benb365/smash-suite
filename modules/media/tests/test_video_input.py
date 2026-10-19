from fractions import Fraction
from types import SimpleNamespace
import sys
import time

import numpy as np
import pytest

from modules.media.video_input import FileFrameSource, InputOverload


def fake_video(monkeypatch, timestamps, *, expected_frames=0, decode_error=None):
    closed = []

    class Container:
        def __init__(self):
            self.streams = SimpleNamespace(video=[SimpleNamespace(
                average_rate=30, frames=expected_frames,
                codec_context=SimpleNamespace(width=8, height=6))])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def decode(self, stream):
            for index, pts in enumerate(timestamps):
                yield SimpleNamespace(pts=pts, time_base=Fraction(1, 1000), is_corrupt=False,
                                      to_ndarray=lambda format, index=index: np.full((6, 8, 3), index, np.uint8))
            if decode_error:
                raise decode_error

    monkeypatch.setitem(sys.modules, "av", SimpleNamespace(open=lambda path: Container()))
    return closed


def consume(source):
    with source:
        return [(row.frame_id, row.timestamp_ms, row.image.tobytes()) for row in source]


def test_vfr_pacing_preserves_pts_images_and_absolute_schedule(monkeypatch):
    fake_video(monkeypatch, [7000, 7010, 7050, 7100])
    offline = consume(FileFrameSource("test", mode="offline"))
    realtime = FileFrameSource("test", mode="realtime")
    observed_at = []
    with realtime:
        live = []
        for frame in realtime:
            observed_at.append(time.monotonic() - realtime.started_at)
            live.append((frame.frame_id, frame.timestamp_ms, frame.image.tobytes()))
            time.sleep(.015)  # processing must not be added to every frame period
    assert live == offline
    assert [row[1] for row in live] == [0, 10, 50, 100]
    assert all(wall >= timestamp / 1000 for wall, (_, timestamp, _) in zip(observed_at, live))
    assert observed_at[-1] < .25
    assert realtime.stats["queue_peak"] <= 6


@pytest.mark.parametrize("timestamps, message", [
    ([1, None], "PTS"), ([10, 10], "strictly increasing"),
    ([10, 9], "strictly increasing"), ([], "no decodable"),
])
def test_invalid_source_times_are_reported_and_decoder_closed(monkeypatch, timestamps, message):
    closed = fake_video(monkeypatch, timestamps)
    with pytest.raises(ValueError, match=message):
        consume(FileFrameSource("test"))
    assert closed


def test_decode_failure_and_known_premature_eof_are_not_normal_end(monkeypatch):
    fake_video(monkeypatch, [0, 10], decode_error=RuntimeError("broken packet"))
    with pytest.raises(RuntimeError, match="broken packet"):
        consume(FileFrameSource("test"))
    fake_video(monkeypatch, [0, 10], expected_frames=3)
    with pytest.raises(RuntimeError, match="Premature EOF"):
        consume(FileFrameSource("test"))


def test_slow_realtime_consumer_stops_without_dropping_or_retiming(monkeypatch):
    closed = fake_video(monkeypatch, list(range(0, 1000, 10)))
    source = FileFrameSource("test", mode="realtime", max_lag_s=.08)
    with pytest.raises(InputOverload):
        with source:
            for frame in source:
                assert frame.frame_id == 0
                time.sleep(.15)
    assert closed
    assert source.stats["queue_peak"] <= 6
    assert source.stats["frames_delivered"] == 1
    assert source._thread is not None and not source._thread.is_alive()


def test_offline_backpressure_never_uses_realtime_deadline(monkeypatch):
    fake_video(monkeypatch, list(range(12)))
    source = FileFrameSource("test", mode="offline", max_lag_s=.01)
    with source:
        frames = []
        for frame in source:
            frames.append(frame.frame_id)
            if frame.frame_id == 0:
                time.sleep(.05)
    assert frames == list(range(12))
    assert source.stats["queue_peak"] <= 6


def test_limit_and_early_close_release_full_queue(monkeypatch):
    closed = fake_video(monkeypatch, list(range(100)))
    limited = FileFrameSource("test", limit_s=.01)
    assert len(consume(limited)) == 10
    source = FileFrameSource("test")
    with source:
        assert next(iter(source)).frame_id == 0
    assert source._queue.empty()
    assert closed


@pytest.mark.parametrize("kwargs", [dict(mode="bad"), dict(max_lag_s=0),
                                   dict(max_lag_s=float("nan")), dict(limit_s=-1)])
def test_invalid_options(kwargs):
    with pytest.raises(ValueError):
        FileFrameSource("test", **kwargs)
