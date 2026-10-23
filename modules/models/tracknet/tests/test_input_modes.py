from collections import OrderedDict

import cv2
import numpy as np
import pytest
import torch
from torch import nn

from modules.models.tracknet.model import TrackNet
from modules.models.tracknet.predictor import TrackNetPredictor, _fold_grayscale_first_layer


class ShapeModel:
    def __init__(self, channels=9):
        self.channels = channels
        self.inputs = []

    def __call__(self, batch):
        self.inputs.append(batch.detach().clone())
        return torch.zeros((1, 3, batch.shape[-2], batch.shape[-1]))


def make_predictor(*, small_input=False, grayscale=False, record_candidates=False):
    predictor = TrackNetPredictor.__new__(TrackNetPredictor)
    predictor.torch = torch
    predictor.device = "cpu"
    predictor.record_candidates = record_candidates
    predictor.statistics = None
    predictor.small_input = small_input
    predictor.grayscale = grayscale
    predictor.input_size = (288, 512)
    predictor.content_size = (288, 512)
    predictor.color_mode = "gray" if grayscale else "rgb"
    predictor.last_candidates = []
    predictor._preprocessed_cache = OrderedDict()
    predictor._cache_peak_items = 0
    predictor.model = ShapeModel(3 if grayscale else 9)
    return predictor


def test_default_input_is_original_rgb_path_and_exposes_actual_metadata():
    frames = [np.full((12, 16, 3), (20 + i, 80, 210), dtype=np.uint8) for i in range(3)]
    predictor = make_predictor()
    predictor(frames)

    expected = []
    from torchvision.transforms.functional import resize

    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255)
        expected.append(resize(tensor, [288, 512], antialias=True))
    assert torch.equal(predictor.model.inputs[-1], torch.cat(expected).unsqueeze(0))
    assert predictor.input_size == predictor.content_size == (288, 512)
    assert predictor.color_mode == "rgb"


@pytest.mark.parametrize("grayscale", [False, True])
def test_small_input_pads_to_eight_and_decodes_only_content_with_correct_mapping(grayscale):
    predictor = make_predictor(small_input=True, grayscale=grayscale, record_candidates=True)

    class EdgeModel:
        def __call__(self, batch):
            assert tuple(batch.shape) == (1, 3 if grayscale else 9, 184, 320)
            result = torch.zeros((1, 3, 184, 320))
            result[:, :, 182, 319] = 1.0
            result[:, :, 90, 160] = .8
            self.batch = batch.detach().clone()
            return result

    predictor.model = EdgeModel()
    frames = [np.zeros((1080, 1920, 3), dtype=np.uint8) for _ in range(3)]
    points = predictor(frames)

    assert predictor.input_size == (184, 320)
    assert predictor.content_size == (180, 320)
    assert predictor.color_mode == ("gray" if grayscale else "rgb")
    assert [(round(point.x), round(point.y)) for point in points] == [(963, 543)] * 3
    assert all(row["global_peak"]["confidence"] == pytest.approx(.8)
               for row in predictor.last_candidates)
    if grayscale:
        expected = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)[0, 0] / 255
        assert predictor.model.batch[0, 0, 0, 0].item() == pytest.approx(expected)


def test_small_grayscale_cache_reuses_one_configuration_and_reports_shapes():
    predictor = make_predictor(small_input=True, grayscale=True)
    frames = [np.full((1080, 1920, 3), index, dtype=np.uint8) for index in range(4)]
    predictor(frames[:3], frame_ids=[0, 1, 2])
    prepared = {frame_id: tensor.clone() for frame_id, tensor in
                zip((0, 1, 2), predictor.model.inputs[-1][0].split(1, dim=0))}
    predictor(frames[1:], frame_ids=[1, 2, 3])

    assert predictor.statistics is None
    assert predictor.input_size == (184, 320)
    assert predictor.content_size == (180, 320)
    assert predictor.color_mode == "gray"
    assert all(torch.equal(tensor, cached) for tensor, cached in
               zip(predictor.model.inputs[-1][0].split(1, dim=0)[:2], (prepared[1], prepared[2])))
    assert len(predictor._preprocessed_cache) == 3


def test_grayscale_fold_combines_each_frames_rgb_kernels_and_keeps_other_state():
    model = TrackNet()
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    conv = model.conv2d_1.conv
    weight_requires_grad = conv.weight.requires_grad
    original_weight = conv.weight.detach().clone()
    original_bias = conv.bias.detach().clone()
    gray = torch.randn(1, 3, 24, 32)
    expected = conv(gray.repeat_interleave(3, dim=1))

    _fold_grayscale_first_layer(model)

    actual = model.conv2d_1.conv(gray)
    assert conv.in_channels == 3
    assert conv.weight.shape == (64, 3, 3, 3)
    assert conv.weight.requires_grad is weight_requires_grad
    assert torch.equal(conv.bias, original_bias)
    assert torch.allclose(actual, expected, rtol=1e-4, atol=1e-5)
    assert torch.equal(conv.weight, original_weight.reshape(64, 3, 3, 3, 3).sum(dim=2))
    for name, value in model.state_dict().items():
        if name not in ("conv2d_1.conv.weight",):
            assert torch.equal(value, before[name]), name


def test_gray_fold_rejects_nonstandard_first_layer():
    model = nn.Module()
    model.conv2d_1 = nn.Module()
    model.conv2d_1.conv = nn.Conv2d(3, 4, 3)
    with pytest.raises(ValueError, match="9-channel"):
        _fold_grayscale_first_layer(model)
