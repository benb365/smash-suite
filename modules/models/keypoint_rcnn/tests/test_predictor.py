"""Pose adapter contracts using real CPU tensors and a weight-free fake model."""
from types import SimpleNamespace

import numpy as np
import pytest

from modules.models import keypoint_rcnn as predictor


@pytest.fixture
def loaded_pose(monkeypatch):
    torch = pytest.importorskip("torch")
    models, loads = [], []

    class FakePose(torch.nn.Module):
        def __init__(self):
            super().__init__()
            # Deliberately use float64 to verify the adapter selects FP32.
            self.anchor = torch.nn.Parameter(torch.zeros(1, dtype=torch.float64))
            self.transform = SimpleNamespace(min_size=(800,), max_size=1333)
            self.roi_heads = SimpleNamespace(detections_per_img=100)
            self.rpn = SimpleNamespace(_pre_nms_top_n={"training": 13, "testing": 1000},
                                       _post_nms_top_n={"training": 17, "testing": 1000})
            self.calls = []
            self.inference_modes = []

        def forward(self, images):
            self.calls.append([image.clone() for image in images])
            self.inference_modes.append(torch.is_inference_mode_enabled())
            outputs = []
            for image in images:
                assert image.device.type == "cpu"
                assert image.dtype == torch.float32
                height, width = image.shape[-2:]
                outputs.append(dict(
                    boxes=image.new_tensor([[0, 0, width, height]]),
                    scores=image[0, 0, 0].reshape(1),
                    labels=torch.ones(1, dtype=torch.int64, device=image.device),
                    keypoints=image.new_zeros((1, 17, 3)),
                    keypoints_scores=image.new_ones((1, 17)),
                ))
            return outputs

    def load(weight, *, map_location, weights_only):
        loads.append(dict(weight=weight, map_location=map_location, weights_only=weights_only))
        model = FakePose()
        models.append(model)
        return model

    monkeypatch.setattr(torch, "load", load)

    def make(**options):
        return predictor.PoseEstimator("unused-checkpoint.pth", **options)

    return SimpleNamespace(make=make, models=models, loads=loads, torch=torch)


def image(height, width, red):
    pixels = np.empty((height, width, 3), dtype=np.uint8)
    pixels[:] = (11, 37, red)  # BGR input; the fake model reads its first RGB channel.
    return pixels


def test_single_image_remains_a_numpy_dictionary_on_default_cpu(loaded_pose):
    model = loaded_pose.make()
    pixels = image(9, 5, 173)
    result = model(pixels)

    assert model.device == "cpu"
    assert isinstance(result, dict)
    assert set(result) == {"boxes", "scores", "labels", "keypoints", "keypoints_scores"}
    assert all(isinstance(value, np.ndarray) for value in result.values())
    np.testing.assert_array_equal(result["boxes"], [[0, 0, 5, 9]])
    assert result["scores"][0] == pytest.approx(173 / 255)
    assert result["scores"].dtype == np.float32
    assert result["labels"].dtype == np.int64
    assert result["keypoints"].shape == (1, 17, 3)
    assert result["keypoints_scores"].shape == (1, 17)
    actual = loaded_pose.models[0].calls[0][0].numpy()
    np.testing.assert_allclose(actual, pixels[:, :, ::-1].transpose(2, 0, 1) / 255,
                               rtol=1e-7, atol=1e-8)
    assert loaded_pose.models[0].inference_modes == [True]


def test_batch_preserves_order_and_each_original_image_shape(loaded_pose):
    model = loaded_pose.make(device="cpu")
    images = [image(9, 5, 31), image(4, 12, 91), image(7, 3, 151)]
    results = model.predict_batch(images)

    assert len(results) == 3
    assert len(loaded_pose.models[0].calls) == 1
    assert [tuple(tensor.shape) for tensor in loaded_pose.models[0].calls[0]] == [
        (3, 9, 5), (3, 4, 12), (3, 7, 3)]
    assert [float(row["scores"][0]) for row in results] == pytest.approx([
        31 / 255, 91 / 255, 151 / 255])
    for pixels, row in zip(images, results):
        height, width = pixels.shape[:2]
        np.testing.assert_array_equal(row["boxes"], [[0, 0, width, height]])
    assert loaded_pose.models[0].inference_modes == [True]


def test_empty_batches_and_cumulative_timings_are_independent_snapshots(loaded_pose, monkeypatch):
    # Deterministic clock values exercise accumulation without wall-clock limits.
    ticks = iter([10, 12, 20, 20.25, 20.75, 30, 30.5, 31.5])
    monkeypatch.setattr(predictor, "perf_counter", lambda: next(ticks))
    model = loaded_pose.make()
    initial = model.timings
    assert initial == dict(initialization_s=2, tensor_preparation_s=0,
                           inference_and_transfer_s=0, batch_count=0, crop_count=0)
    assert model.predict_batch([]) == []
    assert loaded_pose.models[0].calls == []
    assert model.timings == initial

    model.predict_batch([image(9, 5, 31), image(4, 12, 91)])
    first = model.timings
    assert first == dict(initialization_s=2, tensor_preparation_s=.25,
                         inference_and_transfer_s=.5, batch_count=1, crop_count=2)
    assert initial["crop_count"] == 0
    first["crop_count"] = -1
    first["initialization_s"] = -1
    assert model.timings["crop_count"] == 2
    assert model.timings["initialization_s"] == 2
    model(image(7, 3, 151))
    assert model.timings == dict(initialization_s=2, tensor_preparation_s=.75,
                                inference_and_transfer_s=1.5, batch_count=2, crop_count=3)
    assert model.predict_batch([]) == []
    assert len(loaded_pose.models[0].calls) == 2


def test_fp32_and_original_detection_configuration_are_kept(loaded_pose):
    model = loaded_pose.make()
    actual = loaded_pose.models[0]
    assert model.model is actual
    assert not actual.training
    assert actual.anchor.device.type == "cpu"
    assert actual.anchor.dtype == loaded_pose.torch.float32
    assert actual.transform.min_size == (192,)
    assert actual.transform.max_size == 384
    assert actual.roi_heads.detections_per_img == 3
    assert actual.rpn._pre_nms_top_n == {"training": 13, "testing": 200}
    assert actual.rpn._post_nms_top_n == {"training": 17, "testing": 200}
    assert loaded_pose.loads == [dict(weight="unused-checkpoint.pth", map_location="cpu",
                                     weights_only=False)]


@pytest.mark.parametrize("device", ["mps", "meta"])
def test_unsupported_devices_fail_before_loading_weights(loaded_pose, device):
    with pytest.raises(ValueError, match="cpu or cuda"):
        loaded_pose.make(device=device)
    assert loaded_pose.loads == []


def test_malformed_device_is_rejected_before_loading_weights(loaded_pose):
    with pytest.raises((RuntimeError, ValueError)):
        loaded_pose.make(device="not-a-device")
    assert loaded_pose.loads == []


def test_unavailable_cuda_does_not_silently_fall_back_to_cpu(loaded_pose, monkeypatch):
    monkeypatch.setattr(loaded_pose.torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA.*unavailable"):
        loaded_pose.make(device="cuda:0")
    assert loaded_pose.loads == []
