from dataclasses import asdict
from fractions import Fraction
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest

from modules.media.types import TimestampedFrame, VideoInfo
from modules.models.tracknet import ShuttlePoint
from modules.rally.dynamic_scan import DynamicScan
import modules.rally.recognize as recognition


class Predictor:
    def __init__(self, *args, record_candidates=True, small_input=False, grayscale=False, hits=None, **kwargs):
        self.record_candidates = record_candidates
        self.last_candidates = []
        self.calls = []
        self.hits = hits
        self.input_size = (184, 320) if small_input else (288, 512)
        self.content_size = (180, 320) if small_input else (288, 512)
        self.color_mode = "gray" if grayscale else "rgb"

    def clear_preprocessed_cache(self):
        pass

    def __call__(self, images, **kwargs):
        ids = tuple(int(image.flat[0]) for image in images)
        self.calls.append(ids)
        points = [ShuttlePoint(900 + i, 500, .8 if self.hits is None or i in self.hits else .2) for i in ids]
        self.last_candidates = [dict(global_peak=asdict(p), largest_region=asdict(p), peaks=[asdict(p)],
                                     peak_floor=.1, max_peaks=32) for p in points] if self.record_candidates else []
        return points


def frames(count, *, sparse=False):
    return [TimestampedFrame(i * 2 if sparse else i, i * 40., np.full((1, 1, 3), i, dtype=np.int32))
            for i in range(count)]


def scan_groups(starts, hits=()):
    predictor = Predictor(hits=hits)
    scan = DynamicScan(predictor)
    for i, start in enumerate(starts):
        scan.add([TimestampedFrame((3 * i + j) * 2, start + j,
                                  np.full((1, 1, 3), 3 * i + j, dtype=np.int32)) for j in range(3)])
    scan.finish()
    return scan, predictor


def test_scan_stops_on_first_negative_includes_it_and_reuses_windows():
    scan, model = scan_groups([0, 100, 200, 1000, 1100, 1200, 1300], hits=range(6, 15))
    assert [i for i, w in enumerate(scan.windows) if w.candidate] == [1, 2, 3, 4, 5]
    assert scan.windows[0].points is not None  # actual coarse negative
    assert scan.windows[6].points is None
    assert len(model.calls) == len(set(model.calls))
    assert scan.summary()["model_windows"] <= len(scan.windows)
    assert not scan.images
    assert scan.observations()[36]["peaks"] == []


@pytest.mark.parametrize("positive", [False, True])
def test_scan_all_negative_or_positive_keeps_real_time_and_never_exceeds_full_calls(positive):
    scan, model = scan_groups([i * 100 for i in range(31)], hits=range(93) if positive else ())
    assert len(model.calls) == (31 if positive else 4)
    assert scan.summary()["candidate_windows"] == (31 if positive else 0)
    assert [r["timestamp_ms"] for r in scan.observations().values()][:3] == [0, 1, 2]
    assert all(f.image is None for w in scan.windows for f in w.frames)


def test_scan_sparse_source_time_and_expansion_meeting_do_not_drop_unresolved_images():
    scan, model = scan_groups([0, 100, 5000, 5100, 5200, 9000, 9100], hits=range(12, 18))
    assert [i for i, w in enumerate(scan.windows) if w.candidate] == [3, 4, 5, 6]
    assert len(model.calls) == len(set(model.calls))
    assert scan.summary()["image_buffer_peak_frames"] <= 9


def install_observation_fakes(monkeypatch, rows):
    import modules.models.yolo11n as yolo
    from modules.rally.common import player_paths
    selected_caps = []

    class Source:
        def __init__(self, *args, max_fps=None, **kwargs):
            selected_caps.append(max_fps)
            self.stats = dict(frames_decoded=len(rows), frames_delivered=len(rows))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __iter__(self): return iter(rows)

    class Detector:
        def __init__(self, *args, **kwargs): pass
        def __call__(self, images):
            boxes = [dict(x1=300, x2=400, y1=300, y2=600), dict(x1=900, x2=1000, y1=200, y2=500)]
            return [boxes for _ in images]

    monkeypatch.setattr(recognition, "FileFrameSource", Source)
    monkeypatch.setattr(recognition, "normalized", lambda frame: frame)
    monkeypatch.setattr(yolo, "PersonDetector", Detector)
    monkeypatch.setattr(player_paths, "descriptor", lambda image, box: [1.])
    return selected_caps


@pytest.mark.parametrize("count", range(2, 12))
@pytest.mark.parametrize("scene", ["courtside", "personal"])
def test_scan_full_positive_matches_original_observations_people_and_tail(monkeypatch, count, scene):
    rows = frames(count, sparse=True)
    install_observation_fakes(monkeypatch, rows)
    info = SimpleNamespace(duration_ms=count * 40)
    original, dynamic = Predictor(), Predictor()
    baseline = recognition.observe("unused", info, scene, None, original, "unused", "cpu", lambda *a: None)
    scans = {}
    actual = recognition.observe("unused", info, scene, None, dynamic, "unused", "cpu", lambda *a: None,
                                 scans=scans, max_fps=35)
    cleaned = [[{k: v for k, v in row.items() if k != "skip"} for row in group] for group in actual[:2]]
    assert cleaned == list(baseline[:2])
    assert actual[2] == baseline[2]
    assert len(dynamic.calls) == len(original.calls)
    assert len(dynamic.calls) == len(set(dynamic.calls))
    if scene == "courtside" and count >= 3:
        assert [r["frame_id"] for r in actual[1]][:len(actual[0])] == [r["frame_id"] for r in actual[0]]


@pytest.mark.parametrize("scene", ["high", "courtside", "personal"])
@pytest.mark.parametrize("flags", list(product([False, True], repeat=4)))
def test_all_product_combinations_reach_each_scene_without_overriding_flags(monkeypatch, tmp_path, scene, flags):
    rows = frames(18, sparse=True)
    caps = install_observation_fakes(monkeypatch, rows)
    monkeypatch.setattr(recognition, "TrackNetPredictor", Predictor)
    from modules.rally.common import player_paths, players_v2, shuttle_paths, feet
    from modules.rally.scenarios import courtside, personal
    seeds = [dict(x1=300, x2=400, y1=300, y2=600, track_id=1),
             dict(x1=900, x2=1000, y1=200, y2=500, track_id=2)]
    people = lambda features, *args: [dict(row, players=[]) for row in features]
    monkeypatch.setattr(player_paths, "main_players", lambda *a: seeds)
    monkeypatch.setattr(player_paths, "tracks", people)
    monkeypatch.setattr(players_v2, "track_all", lambda features: features)
    monkeypatch.setattr(players_v2, "select", lambda *a: (seeds, {}))
    monkeypatch.setattr(players_v2, "follow", people)
    monkeypatch.setattr(shuttle_paths, "associate", lambda *a: [])
    monkeypatch.setattr(courtside, "predict", lambda *a: ([], {}))
    monkeypatch.setattr(personal, "predict", lambda *a: ([], {}))
    monkeypatch.setattr(feet, "add_foot_signals", lambda *a: None)
    pose_options = []

    def signals(*args, **kwargs):
        pose_options.append(kwargs)
        return dict(times=np.array([0., 240., 480.]))
    monkeypatch.setattr(recognition, "person_signals", signals)
    options = dict(zip(("limit_fps", "small_input", "grayscale", "dynamic_scan"), flags))
    info = VideoInfo(name="test.mp4", duration_ms=720, width=1920, height=1080, has_audio=False, first_pts_ms=0)
    _, details = recognition.recognize("unused", info, scene,
        {"ball_track.pt": "unused", "yolo11n.pt": "unused", "pose_kpRCNN.pth": "unused"},
        lambda *a: None, tmp_path, optimizations=options)
    actual = details["recognition"]
    assert actual["optimizations"] == options
    assert caps == [35 if flags[0] else None]
    assert actual["tracknet_input_size"] == ([184, 320] if flags[1] else [288, 512])
    assert actual["tracknet_color_mode"] == ("gray" if flags[2] else "rgb")
    assert ("dynamic_scan" in actual) == flags[3]
    if scene == "personal":
        assert pose_options[0]["max_fps"] == (35 if flags[0] else None)
        assert (pose_options[0]["candidate_ids"] is not None) == flags[3]


def test_person_signals_reselects_source_frames_and_keeps_lk_context_for_skipped_anchor(monkeypatch):
    from modules.media.video_input import PtsFrameSelector
    from modules.rally.statistics import Statistics

    converted = []
    source_frames = [SimpleNamespace(
        pts=index * 1500, time_base=Fraction(1, 90000), is_corrupt=False,
        width=2, height=2,
        to_ndarray=lambda format, index=index: converted.append(index) or
        np.full((2, 2, 3), index, np.uint8),
    ) for index in range(18)]

    class Container:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def decode(self, video=0): return iter(source_frames)

    monkeypatch.setitem(__import__("sys").modules, "av", SimpleNamespace(open=lambda path: Container()))
    selected = []

    class RecordingSelector:
        def __init__(self, cap):
            self.inner = PtsFrameSelector(cap)
            self.index = 0

        def select(self, pts, time_base):
            result = self.inner.select(pts, time_base)
            if result:
                selected.append(self.index)
            self.index += 1
            return result

    monkeypatch.setattr("modules.media.video_input.PtsFrameSelector", RecordingSelector)

    class PoseEstimator:
        def __init__(self, *args, **kwargs): pass
        def __call__(self, crop):
            keypoints = np.zeros((17, 3), dtype=float)
            keypoints[:, 2] = 1
            keypoints[5, :2] = [70, 50]; keypoints[6, :2] = [90, 50]
            keypoints[9, :2] = [70, 60]; keypoints[10, :2] = [90, 60]
            keypoints[11, :2] = [75, 120]; keypoints[12, :2] = [85, 120]
            return dict(boxes=np.array([[40, 24, 140, 224]], dtype=float),
                        keypoints=np.array([keypoints]), keypoints_scores=np.ones((1, 17)) * 5)

    monkeypatch.setattr("modules.models.keypoint_rcnn.PoseEstimator", PoseEstimator)
    flow_pairs = []
    def optical_flow(previous, current, points, next_points, **kwargs):
        prev_id, cur_id = int(previous[0, 0]), int(current[0, 0])
        flow_pairs.append((prev_id, cur_id))
        return points.copy(), np.ones((4, 1), np.uint8), np.zeros((4, 1), np.float32)
    monkeypatch.setattr("modules.rally.recognize.cv2.calcOpticalFlowPyrLK", optical_flow)

    source_selector = PtsFrameSelector(35)
    selected_fids = [i for i in range(18) if source_selector.select(i * 1500, Fraction(1, 90000))]
    assert selected_fids == [0, 2, 4, 6, 7, 9, 11, 12, 14, 16]
    people = [
        dict(frame_id=0, timestamp_ms=0., players=[dict(player_id=0, box_index=0,
             box=dict(x1=100, y1=100, x2=200, y2=300))]),
        dict(frame_id=11, timestamp_ms=183.33333333333334, players=[dict(player_id=1, box_index=0,
             box=dict(x1=100, y1=100, x2=200, y2=300))]),
    ]
    captured = {}
    monkeypatch.setattr("modules.rally.common.pose_context.extract",
                        lambda rows, people, ball: captured.update(rows=rows) or dict(times=np.array([0., 1.])))
    info = SimpleNamespace(width=2, height=2, duration_ms=300, first_pts_ms=0)

    signals = recognition.person_signals("unused", info, people, [], "unused", lambda *args: None,
                                         Statistics(), max_fps=35, candidate_ids={0})

    assert selected == selected_fids  # the pose pass applies the same PTS selector to every decoded frame
    assert [row["frame_id"] for row in captured["rows"]] == [0, 11]
    assert captured["rows"][1]["skip"] is True
    assert captured["rows"][1]["people"][0]["selected"] is None
    # The first anchor still uses analysis-index +1/+3/+5 contexts (source IDs 2, 6, 9),
    # even though those frames are absent from the candidate-window set.
    assert flow_pairs == [(0, 2), (2, 0), (0, 6), (6, 0), (0, 9), (9, 0)]
    assert signals["lk_valid"].tolist() == [[3, 0], [0, 0]]
    assert converted.count(11) == 0
