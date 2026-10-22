import importlib.util
import sys
import types
from pathlib import Path

import numpy as np

from run import PREDICTOR, derive_source


class FakeTensor:
    def __init__(self, value=None):
        self.value = value

    def permute(self, *args):
        return self

    def float(self):
        return self

    def div_(self, value):
        return self

    def unsqueeze(self, dim):
        return self

    def to(self, device):
        return self


class FakeTorch:
    @staticmethod
    def from_numpy(array):
        return FakeTensor(array)

    @staticmethod
    def cat(tensors):
        return FakeTensor()

    @staticmethod
    def inference_mode():
        from contextlib import nullcontext
        return nullcontext()


class FakeModel:
    def __init__(self, shape):
        self.shape = shape

    def __call__(self, tensor):
        heatmaps = np.zeros((3, *self.shape), dtype=np.float32)
        heatmaps[:, self.shape[0] // 2, self.shape[1] // 2] = 1
        return FakeBatch(heatmaps)


class FakeBatch:
    def __init__(self, heatmaps):
        self.heatmaps = heatmaps

    def __getitem__(self, index):
        return FakeHeatmaps(self.heatmaps)


class FakeHeatmaps:
    def __init__(self, heatmaps):
        self.heatmaps = heatmaps

    def cpu(self):
        return self

    def numpy(self):
        return self.heatmaps


def load_class(source, name):
    module = types.ModuleType(name)
    module.__package__ = "modules.models.tracknet"
    sys.modules[name] = module
    exec(compile(source, name, "exec"), module.__dict__)
    return module.TrackNetPredictor


def predictor_call(predictor_class, frame, heatmap_shape):
    import cv2
    old = (cv2.cvtColor, cv2.findContours)
    cv2.cvtColor = lambda frame, code: frame[:, :, ::-1].copy()
    cv2.findContours = lambda *args: ([], None)
    try:
        instance = predictor_class.__new__(predictor_class)
        instance.torch = FakeTorch()
        instance.device = "cpu"
        instance.record_candidates = False
        instance.statistics = None
        instance.last_candidates = []
        instance._preprocessed_cache = {}
        instance._cache_peak_items = 0
        instance.model = FakeModel(heatmap_shape)
        instance.last_resized_size = None

        import torchvision.transforms.functional as functional
        old_resize = functional.resize
        def resize(tensor, size, antialias=True):
            instance.last_resized_size = (tuple(size), antialias)
            return tensor
        functional.resize = resize
        try:
            return instance([frame]), instance.last_resized_size
        finally:
            functional.resize = old_resize
    finally:
        cv2.cvtColor, cv2.findContours = old


def test_source_derivation_has_only_one_resize_and_mapping_edit_for_each_legal_size():
    source = PREDICTOR.read_text(encoding="utf-8")
    for size, target in (("288x512", [288, 512]), ("216x384", [216, 384]), ("144x256", [144, 256])):
        derived = derive_source(source, size)
        assert f"resize(tensor, {target}, antialias=True)" in derived
        assert "x * frame.shape[1] / heatmap.shape[1]" in derived
        assert "y * frame.shape[0] / heatmap.shape[0]" in derived


def test_288_control_matches_original_predictor_and_uses_original_resize():
    source = PREDICTOR.read_text(encoding="utf-8")
    original = load_class(source, "_opt08a_test_original")
    derived = load_class(derive_source(source, "288x512"), "_opt08a_test_288")
    frame = np.arange(108 * 192 * 3, dtype=np.uint8).reshape(108, 192, 3)
    old_points, old_size = predictor_call(original, frame, (288, 512))
    new_points, new_size = predictor_call(derived, frame, (288, 512))
    assert old_size == new_size == ((288, 512), True)
    assert [(p.x, p.y, p.confidence) for p in old_points] == [
        (p.x, p.y, p.confidence) for p in new_points
    ]


def test_nondefault_heatmap_shape_controls_mapping_back_to_frame():
    source = PREDICTOR.read_text(encoding="utf-8")
    derived = load_class(derive_source(source, "216x384"), "_opt08a_test_216")
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    points, resized = predictor_call(derived, frame, (90, 120))
    assert resized == ((216, 384), True)
    assert points[0].x == 960
    assert points[0].y == 540
