import numpy as np
import torch
import pytest

from modules.models.tracknet.predictor import TrackNetPredictor


class RecordingModel:
    def __init__(self):
        self.inputs = []

    def __call__(self, batch):
        self.inputs.append(batch[0].detach().clone())
        return torch.zeros((1, 3, 288, 512))


class Counts:
    def __init__(self):
        self.values = {}

    def add(self, name, value=1):
        self.values[name] = self.values.get(name, 0) + value

    def timing(self, name, value):
        pass

    def phase(self, name):
        from contextlib import nullcontext
        return nullcontext()

    def source(self, name, values):
        pass


def predictor():
    instance = TrackNetPredictor.__new__(TrackNetPredictor)
    instance.torch = torch
    instance.device = "cpu"
    instance.record_candidates = False
    instance.statistics = Counts()
    instance.small_input = False
    instance.grayscale = False
    instance.input_size = (288, 512)
    instance.content_size = (288, 512)
    instance.color_mode = "rgb"
    instance.last_candidates = []
    instance._preprocessed_cache = __import__("collections").OrderedDict()
    instance._cache_peak_items = 0
    instance.model = RecordingModel()
    return instance


def test_overlapping_windows_reuse_only_explicit_frame_ids():
    model = predictor()
    frames = [np.full((12, 16, 3), i, dtype=np.uint8) for i in range(7)]
    windows = [(0, 1, 2), (1, 2, 3), (3, 4, 5), (4, 5, 6)]
    expected = {}

    for window in windows:
        model([frames[i] for i in window], frame_ids=list(window))
        actual = model.model.inputs[-1]
        assert actual.shape[0] == 9
        for slot, frame_id in enumerate(window):
            tensor = actual[slot * 3:(slot + 1) * 3]
            if frame_id in expected:
                assert torch.equal(tensor, expected[frame_id])
            else:
                expected[frame_id] = tensor.clone()
        assert len(model._preprocessed_cache) <= 3

    assert model._cache_peak_items == 3
    assert model.statistics.values["tracknet_cache_hits"] == 5
    assert model.statistics.values["tracknet_cache_misses"] == 7
    assert model.statistics.values["tracknet_cache_prepared_frames"] == 7

    # The legacy call path recomputes all inputs and leaves the cache disabled.
    model([frames[4], frames[5], frames[6]])
    assert model.statistics.values["tracknet_cache_misses"] == 7
    assert len(model._preprocessed_cache) == 3

    model.clear_preprocessed_cache()
    assert not model._preprocessed_cache


@pytest.mark.parametrize("use_cache", [False, True], ids=["no-cache", "overlapping-cache"])
def test_preprocessing_matches_original_formula_and_preserves_input(use_cache):
    import cv2
    from torchvision.transforms.functional import resize

    pixels = np.arange(14 * 19 * 3, dtype=np.uint32).reshape(14, 19, 3)
    bases = [((pixels + index * 37) % 256).astype(np.uint8) for index in range(4)]
    frames = [base[1:-1, 2:-1, :] for base in bases]
    snapshots = [frame.copy() for frame in frames]
    model = predictor()
    windows = [(0, 1, 2), (1, 2, 3)] if use_cache else [(0, 1, 2)]

    for window in windows:
        selected = [frames[index] for index in window]
        if use_cache:
            model(selected, frame_ids=list(window))
        else:
            model(selected)

        expected = []
        for frame in selected:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255
            expected.append(resize(tensor, [288, 512], antialias=True))
        assert torch.equal(model.model.inputs[-1], torch.cat(expected))

    for frame, snapshot in zip(frames, snapshots):
        assert np.array_equal(frame, snapshot)
    assert all(not frame.flags.c_contiguous for frame in frames)


def test_observe_keeps_window_and_tail_groups_then_releases_cache(monkeypatch):
    from types import SimpleNamespace

    from modules.media.types import TimestampedFrame
    import modules.rally.recognize as recognize

    class FrameSource:
        def __init__(self, source, mode, max_fps=None):
            self.frames = [TimestampedFrame(i, i * 40, np.zeros((16, 24, 3), dtype=np.uint8))
                           for i in range(8)]
            self.stats = {"frames_delivered": len(self.frames), "frames_decoded": len(self.frames)}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return iter(self.frames)

    class Detector:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, images):
            return [[] for _ in images]

    class Predictor:
        def __init__(self):
            self.calls = []
            self.last_candidates = []
            self._cache_peak_items = 3
            self.cleared = False

        def __call__(self, images, *, frame_ids=None):
            self.calls.append(None if frame_ids is None else tuple(frame_ids))
            self.last_candidates = [dict(frame_id=i) for i in (frame_ids or range(len(images)))]

        def clear_preprocessed_cache(self):
            self.cleared = True

    monkeypatch.setattr(recognize, "FileFrameSource", FrameSource)
    monkeypatch.setattr(recognize, "normalized", lambda frame: frame)
    monkeypatch.setitem(__import__("sys").modules, "modules.models.yolo11n",
                        SimpleNamespace(PersonDetector=Detector))
    predictor = Predictor()
    native, shifted, _ = recognize.observe("unused", SimpleNamespace(duration_ms=1000), "courtside", None,
                                           predictor, "unused", "cpu", lambda *args: None, Counts())

    assert predictor.calls == [(0, 1, 2), (1, 2, 3), (3, 4, 5), (4, 5, 6), (5, 6, 7)]
    assert [row["frame_id"] for row in shifted] == list(range(8))
    assert len(native) == 6
    assert predictor.cleared

    personal = Predictor()
    recognize.observe("unused", SimpleNamespace(duration_ms=1000), "personal", None,
                      personal, "unused", "cpu", lambda *args: None, Counts())
    assert personal.calls == [None, None]
    assert not personal.cleared
