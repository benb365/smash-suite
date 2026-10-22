from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import numpy as np
import pytest
import torch
from torch import nn

from probe import take_sample_groups
from run import FOLD_CALL, LOAD_BLOCK, derive_predictor_source, load_helper


def load_source(name, source):
    module = types.ModuleType(name)
    module.__package__ = "modules.models.tracknet"
    sys.modules[name] = module
    exec(compile(source, name, "exec"), module.__dict__)
    return module


def test_source_derivation_keeps_color9_and_builds_only_the_selected_gray_path():
    source = open("modules/models/tracknet/predictor.py", encoding="utf-8").read()
    helper = load_helper("_opt08c_test_helper_fold")
    color9 = derive_predictor_source(source, "color9", helper)
    gray9 = derive_predictor_source(source, "gray9", helper)
    gray3 = derive_predictor_source(source, "gray3", helper)
    rgb_line = "rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)"
    assert color9.count(rgb_line) == 1
    assert "cv2.COLOR_BGR2GRAY" in gray9 and "cv2.COLOR_GRAY2RGB" in gray9
    assert "cv2.COLOR_BGR2GRAY" in gray3 and "from_numpy(gray).unsqueeze(0)" in gray3
    assert gray3.count("_opt08c_fold_first_layer(self.model)") == 1
    assert gray9.count("_opt08c_fold_first_layer(self.model)") == 0
    assert "def _opt08c_fold_first_layer(model):" in gray3
    assert gray3.count(FOLD_CALL) == 1
    assert LOAD_BLOCK not in gray3


@pytest.mark.parametrize("requires_grad", [True, False])
def test_first_layer_fold_helper_preserves_bias_properties_and_other_parameters(requires_grad):
    source = open("modules/models/tracknet/predictor.py", encoding="utf-8").read()
    helper = load_helper("_opt08c_test_helper_source")
    derived = load_source(
        "_opt08c_fold_test",
        derive_predictor_source(source, "gray3", helper),
    )

    class FirstLayer(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Conv2d(9, 64, 3, padding=1, bias=True)

    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv2d_1 = FirstLayer()
            self.tail = nn.Linear(5, 2)

    model = Model()
    model.conv2d_1.conv.weight.requires_grad_(requires_grad)
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    conv = model.conv2d_1.conv
    properties = (conv.stride, conv.padding, conv.dilation, conv.groups, conv.padding_mode)
    old_weight = conv.weight.detach().clone()
    old_bias = conv.bias.detach().clone()
    gray3 = torch.randn(2, 3, 12, 14)
    gray9 = gray3.repeat_interleave(3, dim=1)
    expected = torch.nn.functional.conv2d(gray9, old_weight, old_bias, padding=1)

    derived._opt08c_fold_first_layer(model)

    actual = conv(gray3)
    assert conv.in_channels == 3
    assert conv.weight.shape == (64, 3, 3, 3)
    assert conv.weight.requires_grad is requires_grad
    assert (conv.stride, conv.padding, conv.dilation, conv.groups, conv.padding_mode) == properties
    assert torch.equal(conv.bias, old_bias)
    assert torch.allclose(actual, expected, rtol=1e-4, atol=1e-5)
    for name, value in model.state_dict().items():
        if name != "conv2d_1.conv.weight":
            assert torch.equal(value, before[name]), name
    assert torch.equal(conv.weight, old_weight.reshape(64, 3, 3, 3, 3).sum(dim=2))


@dataclass
class Frame:
    frame_id: int
    timestamp_ms: float


def test_prefix_sample_windows_choose_post_target_frame_id_multiple_of_three_and_are_adjacent():
    frames = [Frame(index, index * 40.0) for index in range(20)]
    windows = take_sample_groups(frames, (100.0, 200.0, 400.0))
    assert [[frame.frame_id for frame in group] for _, group in windows] == [
        [3, 4, 5], [6, 7, 8], [12, 13, 14]
    ]
    assert [target for target, _ in windows] == [100.0, 200.0, 400.0]


def test_gray9_and_gray3_real_preprocessing_match_by_frame_without_mutating_source():
    import cv2

    source = open("modules/models/tracknet/predictor.py", encoding="utf-8").read()
    helper = load_helper("_opt08c_test_helper_preprocess")
    modules = {
        variant: load_source(
            f"_opt08c_preprocess_{variant}",
            derive_predictor_source(source, variant, helper),
        )
        for variant in ("color9", "gray9", "gray3")
    }

    class CaptureModel(nn.Module):
        def forward(self, tensor):
            self.input = tensor.detach().cpu().clone()
            return torch.zeros((1, 3, 288, 512), dtype=tensor.dtype)

    frames = [
        np.full((12, 16, 3), (5, 30, 220), dtype=np.uint8),
        np.full((12, 16, 3), (50, 80, 160), dtype=np.uint8),
        np.full((12, 16, 3), (100, 120, 80), dtype=np.uint8),
    ]
    originals = [frame.copy() for frame in frames]
    captured = {}
    for variant, module in modules.items():
        predictor = module.TrackNetPredictor.__new__(module.TrackNetPredictor)
        predictor.torch = torch
        predictor.device = "cpu"
        predictor.record_candidates = False
        predictor.statistics = None
        predictor.last_candidates = []
        predictor._preprocessed_cache = {}
        predictor._cache_peak_items = 0
        predictor.model = CaptureModel()
        predictor(frames)
        captured[variant] = predictor.model.input

    color9 = captured["color9"]
    gray9 = captured["gray9"].reshape(1, 3, 3, 288, 512)
    gray3 = captured["gray3"]
    assert color9.shape == (1, 9, 288, 512)
    assert captured["gray9"].shape == (1, 9, 288, 512)
    assert gray3.shape == (1, 3, 288, 512)
    assert torch.equal(gray9, gray3.unsqueeze(2).expand(1, 3, 3, 288, 512))
    expected_gray = [
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[0, 0] / 255
        for frame in originals
    ]
    assert [float(gray3[0, i].mean()) for i in range(3)] == pytest.approx(expected_gray)
    assert torch.equal(color9[0, 0], torch.full((288, 512), 220 / 255, dtype=color9.dtype))
    assert all(np.array_equal(frame, original) for frame, original in zip(frames, originals))
