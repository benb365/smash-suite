from __future__ import annotations

import contextlib
import inspect
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import derive_observe_source

from modules.rally import recognize


@dataclass
class Frame:
    frame_id: int
    timestamp_ms: float
    image: object


class Stats:
    def __init__(self):
        self.counts = {}

    @contextlib.contextmanager
    def phase(self, name):
        yield

    def source(self, name, values):
        self.source_values = values

    def add(self, name, value=1):
        self.counts[name] = self.counts.get(name, 0) + value

    def timing(self, name, value):
        pass


class FrameSource:
    count = 0

    def __init__(self, path, *, mode):
        self.frames = [Frame(i, 1000.0 + i * 40.0, object()) for i in range(self.count)]
        self.stats = {
            "frames_delivered": self.count,
            "frames_decoded": self.count,
            "last_delivered_timestamp_ms": self.frames[-1].timestamp_ms if self.frames else None,
        }

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
        self.cleared = False

    def __call__(self, images, *, frame_ids=None):
        ids = list(frame_ids)
        self.calls.append(ids)
        self.last_candidates = [
            {"frame_id": i, "peaks": [{"x": float(i), "y": float(i), "confidence": 0.9,
                                        "window_start": ids[0], "window_slot": slot}]}
            for slot, i in enumerate(ids)
        ]
        return [SimpleNamespace(x=float(i), y=float(i), confidence=0.9) for i in ids]

    def clear_preprocessed_cache(self):
        self.cleared = True


def derived_observe(monkeypatch, variant, frame_count):
    namespace = dict(vars(recognize))
    source = derive_observe_source(inspect.getsource(recognize.observe), variant)
    exec(compile(source, f"<opt09a-{variant}>", "exec"), namespace)
    FrameSource.count = frame_count
    namespace["FileFrameSource"] = FrameSource
    namespace["normalized"] = lambda frame: frame
    monkeypatch.setitem(sys.modules, "modules.models.yolo11n", types.SimpleNamespace(PersonDetector=Detector))
    predictor = Predictor()
    result = namespace["observe"](
        "unused", SimpleNamespace(duration_ms=2000), "courtside", None, predictor,
        "unused", "mps", lambda *args: None, Stats(),
    )
    return result, predictor


def assert_selected_streams(result, count):
    native, shifted, features = result
    assert [(row["frame_id"], row["timestamp_ms"]) for row in native] == [
        (i, 1000.0 + i * 40.0) for i in range(count)
    ]
    assert native == shifted
    assert len(features) == (count + 5) // 6
    assert all("peaks" in row for row in native)


def test_derived_observe_has_one_explicit_selection_condition_and_compiles():
    source = inspect.getsource(recognize.observe)
    native = derive_observe_source(source, "native")
    shifted = derive_observe_source(source, "shifted")
    assert native.count("if phase == 0:") == 1
    assert shifted.count("if phase == 1 or queue[0].frame_id == 0:") == 1
    assert "if phase == 0 or (phase == 1 and camera_type == \"courtside\")" not in native
    assert "if phase == 0 or (phase == 1 and camera_type == \"courtside\")" not in shifted
    assert "chosen = {**shifted, **native}" in native
    assert "chosen = shifted" in shifted
    assert "_OPT09A_VARIANT" not in native
    assert "_OPT09A_VARIANT" not in shifted
    compile(native, "<native>", "exec")
    compile(shifted, "<shifted>", "exec")


@pytest.mark.parametrize(
    ("count", "native_calls", "shifted_calls"),
    [
        (9, [[0, 1, 2], [3, 4, 5], [6, 7, 8]], [[0, 1, 2], [1, 2, 3], [4, 5, 6], [6, 7, 8]]),
        (10, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [7, 8, 9]], [[0, 1, 2], [1, 2, 3], [4, 5, 6], [7, 8, 9]]),
        (11, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [8, 9, 10]], [[0, 1, 2], [1, 2, 3], [4, 5, 6], [7, 8, 9], [8, 9, 10]]),
    ],
)
def test_single_phase_streams_cover_full_odd_and_even_eof_tails(monkeypatch, count, native_calls, shifted_calls):
    native_result, native_predictor = derived_observe(monkeypatch, "native", count)
    assert_selected_streams(native_result, count)
    assert native_predictor.calls == native_calls
    assert native_predictor.cleared
    native_rows = native_result[0]
    assert native_rows[0]["peaks"][0]["window_start"] == 0
    assert native_rows[0]["peaks"][0]["window_slot"] == 0
    if count >= 10:
        assert native_rows[-1]["peaks"][0]["window_start"] == native_calls[-1][0]
        assert native_rows[-1]["peaks"][0]["window_slot"] == count - 1 - native_calls[-1][0]
        if count == 10:
            # EOF recovery must preserve frame 8 from the ordinary group, not its tail rerun.
            assert native_rows[8]["peaks"][0]["window_start"] == 6

    shifted_result, shifted_predictor = derived_observe(monkeypatch, "shifted", count)
    assert_selected_streams(shifted_result, count)
    assert shifted_predictor.calls == shifted_calls
    assert shifted_predictor.cleared
    shifted_rows = shifted_result[0]
    assert shifted_rows[0]["peaks"][0]["window_start"] == 0
    assert shifted_rows[0]["peaks"][0]["window_slot"] == 0
    if count >= 4:
        assert shifted_rows[1]["peaks"][0]["window_start"] == 1
        assert shifted_rows[1]["peaks"][0]["window_slot"] == 0
    assert shifted_rows[-1]["peaks"][0]["window_start"] == shifted_calls[-1][0]
    assert shifted_rows[-1]["peaks"][0]["window_slot"] == count - 1 - shifted_calls[-1][0]


@pytest.mark.parametrize("count", [1, 2])
def test_fewer_than_three_frames_produce_no_fabricated_track_observations(monkeypatch, count):
    for variant in ("native", "shifted"):
        result, predictor = derived_observe(monkeypatch, variant, count)
        assert result[0] == []
        assert result[1] == []
        assert [row["frame_id"] for row in result[2]] == [i for i in range(count) if i % 6 == 0]
        assert predictor.calls == []
        assert predictor.cleared
