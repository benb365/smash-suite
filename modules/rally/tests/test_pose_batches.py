"""Real native-PTS video with a fake pose model verifies batch integration."""
from copy import deepcopy
from fractions import Fraction

import numpy as np
import pytest

from modules.media.types import VideoInfo
from modules.models import keypoint_rcnn
from modules.rally.common import pose_context
from modules.rally.recognize import person_signals
from modules.rally.statistics import Statistics


@pytest.fixture
def native_pose_video(tmp_path):
    av = pytest.importorskip("av")
    source = tmp_path / "pose-input.mkv"
    relative_ms = [0, 40, 90, 120, 170, 210, 250, 290, 350, 390, 450, 500, 560]
    with av.open(str(source), "w") as container:
        stream = container.add_stream("ffv1", rate=25)
        stream.width, stream.height, stream.pix_fmt = 64, 36, "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        for index, timestamp in enumerate(relative_ms):
            pixels = np.full((36, 64, 3), 30 + index, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="bgr24")
            frame.pts, frame.time_base = 5000 + timestamp, Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(source)) as container:
        actual = [frame.pts * frame.time_base * 1000 for frame in container.decode(video=0)]
    assert len(actual) == len(relative_ms)
    np.testing.assert_allclose([float(pts - actual[0]) for pts in actual], relative_ms)
    info = VideoInfo(name=source.name, duration_ms=600, width=64, height=36,
                     has_audio=False, first_pts_ms=float(actual[0]))
    return source, info, relative_ms


def tracked_people(relative_ms):
    near = dict(player_id=1, box_index=9,
                box=dict(x1=1200, y1=400, x2=1500, y2=900))
    far = dict(player_id=0, box_index=4,
               box=dict(x1=300, y1=200, x2=500, y2=600))
    return [dict(frame_id=fid, timestamp_ms=relative_ms[fid], players=deepcopy(players))
            for fid, players in ((0, [near, far]), (6, [far, near]), (12, [near, far]))]


def test_same_anchor_batches_preserve_rows_signals_sampling_and_coordinates(native_pose_video,
                                                                           monkeypatch):
    source, info, relative_ms = native_pose_video
    people = tracked_people(relative_ms)
    original_people = deepcopy(people)
    ball = [dict(frame_id=0, timestamp_ms=0, motion=False)]
    captured, models, flow_calls = [], [], []

    class FakePose:
        def __init__(self, weight, *, device):
            assert weight == "unused-pose.pth"
            assert device == "cpu"
            self.device = device
            self.batch_sizes, self.crop_shapes = [], []
            models.append(self)

        @property
        def timings(self):
            return dict(initialization_s=0, tensor_preparation_s=0,
                        inference_and_transfer_s=0, batch_count=len(self.batch_sizes),
                        crop_count=sum(self.batch_sizes))

        def predict_batch(self, images):
            self.batch_sizes.append(len(images))
            self.crop_shapes.extend([pixels.shape[:2] for pixels in images])
            outputs = []
            for pixels in images:
                height, width = pixels.shape[:2]
                xy = np.column_stack((np.arange(17) + width // 20,
                                      2 * np.arange(17) + height // 4, np.ones(17)))
                outputs.append(dict(boxes=np.array([[0, 0, width, height]], dtype=np.float32),
                                    keypoints=xy[np.newaxis].astype(np.float32),
                                    keypoints_scores=np.full((1, 17), 7 if width > 400 else 6,
                                                            dtype=np.float32)))
            return outputs

    def extract(rows, actual_people, actual_ball):
        assert actual_people is people
        assert actual_ball is ball
        captured.append(deepcopy(rows))
        return dict(times=np.array([row["timestamp_ms"] for row in rows]),
                    identities=np.array([[p["player_id"] for p in row["people"]] for row in rows]),
                    first_keypoints=np.array([[p["selected"]["keypoints"][0] for p in row["people"]]
                                              for row in rows]))

    def failed_flow(previous, current, points, unused, **options):
        assert previous.shape == current.shape == (540, 960)
        assert points.shape == (4, 1, 2)
        flow_calls.append(points.copy())
        return None, None, None

    monkeypatch.setattr(keypoint_rcnn, "PoseEstimator", FakePose)
    monkeypatch.setattr(pose_context, "extract", extract)
    monkeypatch.setattr("cv2.calcOpticalFlowPyrLK", failed_flow)
    signals, statistics, shared_statistics = [], [], []
    for batch_size in (1, 2):
        metrics = {}
        shared = Statistics(enabled=True)
        signals.append(person_signals(source, info, people, ball, "unused-pose.pth",
                                      lambda stage, fraction: None, shared, pose_device="cpu",
                                      pose_batch_size=batch_size, metrics=metrics))
        statistics.append(metrics)
        shared_statistics.append(shared)

    assert models[0].batch_sizes == [1, 1, 1, 1, 1, 1]
    assert models[1].batch_sizes == [2, 2, 2]
    expected_shapes = [(620, 500), (496, 360), (496, 360), (620, 500), (620, 500), (496, 360)]
    assert models[0].crop_shapes == models[1].crop_shapes == expected_shapes
    assert captured[0] == captured[1]
    assert [row["frame_id"] for row in captured[0]] == [0, 6, 12]
    assert [row["timestamp_ms"] for row in captured[0]] == [0, 250, 560]
    assert [[person["player_id"] for person in row["people"]] for row in captured[0]] == [
        [1, 0], [0, 1], [1, 0]]
    assert [[person["box_index"] for person in row["people"]] for row in captured[0]] == [
        [9, 4], [4, 9], [9, 4]]
    # Crop-local model coordinates must be shifted back to the 1080p image.
    near, far = captured[0][0]["people"]
    np.testing.assert_array_equal(near["selected"]["keypoints"][0], [1125, 495, 1])
    np.testing.assert_array_equal(far["selected"]["keypoints"][0], [238, 276, 1])
    assert near["selected"]["joint_scores"] == [7] * 17
    assert far["selected"]["joint_scores"] == [6] * 17
    assert people == original_people
    assert set(signals[0]) == set(signals[1])
    for key in signals[0]:
        np.testing.assert_array_equal(signals[0][key], signals[1][key])
    for key in ("lkarm", "lkhigh", "lk_valid"):
        np.testing.assert_array_equal(signals[0][key], np.zeros((3, 2)))
    assert len(flow_calls) == 24  # Six sampled flow frames, two people, two runs.
    np.testing.assert_array_equal(flow_calls[0], flow_calls[12])
    for batch_size, metrics, model, shared in zip((1, 2), statistics, models, shared_statistics):
        assert metrics["decoded_frames"] == 13
        assert metrics["anchor_frames"] == 3
        assert metrics["flow_frames"] == 6
        assert metrics["pose_batch_size"] == batch_size
        assert metrics["pose_device"] == "cpu"
        assert metrics["pose_model"]["crop_count"] == 6
        assert metrics["pose_model"]["batch_count"] == len(model.batch_sizes)
        assert shared.counts["pose_calls"] == len(model.batch_sizes)
        assert shared.counts["person_crops"] == 6
        assert shared.counts["pose_anchor_frames"] == 3
        assert shared.counts["pose_flow_frames"] == 6
        assert shared.sources == [dict(pass_name="pose", frames_decoded=13,
                                       frames_selected=13, frames_skipped=0)]
        assert shared.seconds["pose_tensor_preparation_s"] == 0
        assert shared.seconds["pose_model_inference_and_transfer_s"] == 0
        assert all(metrics[key] >= 0 for key in ("model_setup_s", "decode_s", "frame_prepare_s",
                                               "crop_prepare_s", "pose_wall_s", "pose_selection_s",
                                               "flow_s", "extract_s", "total_s"))


@pytest.mark.parametrize("batch_size", [0, -1, 1.5, "2", None, False, True])
def test_invalid_batch_size_is_rejected_before_loading_pose_model(tmp_path, monkeypatch, batch_size):
    def unexpected_model(*args, **kwargs):
        pytest.fail("Invalid batch size must fail before pose model loading")

    monkeypatch.setattr(keypoint_rcnn, "PoseEstimator", unexpected_model)
    info = VideoInfo(name="unused.mp4", duration_ms=100, width=64, height=36,
                     has_audio=False, first_pts_ms=0)
    with pytest.raises(ValueError, match="positive integer"):
        person_signals(tmp_path / "does-not-exist.mp4", info, [], [], "unused-pose.pth",
                       lambda stage, fraction: None, pose_batch_size=batch_size)
