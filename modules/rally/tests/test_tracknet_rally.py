import math
import json
import pytest

from modules.media.types import TimestampedFrame
from modules.rally.rally_stream import RallyStream
from modules.models.tracknet import ShuttlePoint
from modules.rally.tracknet_rally import ShuttleRallySegmenter
from modules.trajectory.observations import ObservationLog
from modules.media.types import VideoInfo


def flight(t, scale=1):
    phase = t % 2000
    x = 500 + 400 * (phase if phase <= 1000 else 2000 - phase) / 1000
    return ShuttlePoint(x * scale, 400 * scale, .95)


def run(points, scale=1):
    calls = []

    def predict(images):
        calls.append(len(images))
        return images

    candidate = ShuttleRallySegmenter(predict, width=1920 * scale, height=1080 * scale)
    stream = RallyStream(candidate)
    outputs = []
    for index, point in enumerate(points):
        outputs.extend(stream.process(TimestampedFrame(index, index * 40, point)))
    assert all(count == 3 for count in calls)
    return outputs, candidate


def test_flight_survives_brief_occlusion_and_held_ball_does_not_extend_end():
    points = []
    for t in range(0, 9000, 40):
        if 2000 <= t < 2880:
            points.append(ShuttlePoint(0, 0, .1))
        elif t <= 5000:
            points.append(flight(t))
        else:
            points.append(flight(5000))  # The held shuttle remains confidently visible.
    outputs, _ = run(points)
    assert len(outputs) == 1
    rally = outputs[0]
    assert rally.start_ms < 200
    assert 4800 <= rally.end_ms <= 5240
    assert 1600 <= rally.emitted_at_ms - rally.end_ms <= 1720


def test_short_ball_return_static_detection_and_single_jump_do_not_become_rallies():
    points = [flight(t) if t < 1600 else flight(1600) for t in range(0, 7000, 40)]
    points[120] = ShuttlePoint(1200, 700, .99)
    points[130] = ShuttlePoint(math.nan, 500, .99)
    outputs, _ = run(points)
    assert outputs == []


def test_separate_flights_are_emitted_once_and_eof_does_not_finish_a_rally():
    points = []
    for t in range(0, 15000, 40):
        if t < 5000:
            points.append(flight(t))
        elif 8500 <= t < 12000:
            points.append(flight(t - 8500))
        else:
            points.append(ShuttlePoint(0, 0, 0))
    outputs, _ = run(points)
    assert [row.rally_id for row in outputs] == [1, 2]
    assert outputs[0].end_ms < outputs[1].start_ms
    unfinished, candidate = run([flight(t) for t in range(0, 4000, 40)])
    assert unfinished == []
    assert candidate.active


def test_image_resolution_does_not_change_flight_boundaries():
    normal = [flight(t) if t < 5000 else ShuttlePoint(0, 0, 0) for t in range(0, 8000, 40)]
    small = [ShuttlePoint(row.x / 2, row.y / 2, row.confidence) for row in normal]
    assert run(normal)[0] == run(small, scale=.5)[0]


def test_observation_sink_records_three_frame_outputs_before_rally_observation():
    observed = []

    def predict(images):
        return images

    sink = lambda frame, point: observed.append((frame.frame_id, point))
    segmenter = ShuttleRallySegmenter(predict, width=1920, height=1080, observation_sink=sink)
    for frame_id in range(5):
        segmenter.process(TimestampedFrame(frame_id, frame_id * 40, flight(frame_id * 40)))
    assert [frame_id for frame_id, _ in observed] == [0, 1, 2]


def test_observation_log_masks_low_confidence_points_and_marks_completion(tmp_path):
    source, weight = tmp_path / "source.mp4", tmp_path / "model.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    points = tmp_path / "points.jsonl"
    info = VideoInfo(name="source.mp4", duration_ms=80, width=1920, height=1080,
                     has_audio=False, first_pts_ms=120)
    with ObservationLog(points, source=source, info=info, weight=weight) as sink:
        sink(TimestampedFrame(4, 0, None), ShuttlePoint(12, 34, .59))
        sink(TimestampedFrame(5, 40, None), ShuttlePoint(56, 78, .6))
    rows = [json.loads(line) for line in points.read_text().splitlines()]
    meta = json.loads(points.with_suffix(".meta.json").read_text())
    assert rows[0] == dict(frame_id=4, timestamp_ms=0, x=None, y=None, confidence=.59)
    assert rows[1]["x"] == 56 and rows[1]["y"] == 78
    assert meta["source_sha256"] and meta["model_sha256"]
    assert meta["model_path"] == str(weight)
    assert meta["frame_count"] == 2 and meta["last_timestamp_ms"] == 40
    assert meta["reference_size"] == [1920, 1080] and meta["complete"] is True


def test_observation_log_rejects_non_increasing_source_pts(tmp_path):
    source, weight = tmp_path / "source.mp4", tmp_path / "model.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    info = VideoInfo(name="source.mp4", duration_ms=80, width=1920, height=1080,
                     has_audio=False, first_pts_ms=120)
    log = ObservationLog(tmp_path / "points.jsonl", source=source, info=info, weight=weight)
    with pytest.raises(ValueError, match="strictly increasing"):
        with log:
            log(TimestampedFrame(0, 40, None), ShuttlePoint(1, 2, .8))
            log(TimestampedFrame(1, 40, None), ShuttlePoint(3, 4, .8))
    assert json.loads((tmp_path / "points.meta.json").read_text())["complete"] is False






def test_observation_log_rejects_non_finite_pts_and_invalid_frame_ids(tmp_path):
    source, weight = tmp_path / "source.mp4", tmp_path / "model.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    info = VideoInfo(name="source.mp4", duration_ms=80, width=1920, height=1080,
                     has_audio=False, first_pts_ms=120)
    for frame, message in (
        (TimestampedFrame(2, math.nan, None), "timestamps must be finite"),
        (TimestampedFrame(1, 10, None), "frame IDs must be integers and strictly increasing"),
        (TimestampedFrame(0, 20, None), "frame IDs must be integers and strictly increasing"),
        (TimestampedFrame(1.5, 20, None), "frame IDs must be integers and strictly increasing"),
    ):
        log = ObservationLog(tmp_path / "points.jsonl", source=source, info=info, weight=weight)
        with pytest.raises(ValueError, match=message):
            with log:
                log(TimestampedFrame(1, 0, None), ShuttlePoint(1, 2, .8))
                log(frame, ShuttlePoint(3, 4, .8))
