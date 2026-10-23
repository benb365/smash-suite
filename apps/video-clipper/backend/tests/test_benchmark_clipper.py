"""Export validation checks use no models, weights, or downloaded media."""
import importlib.util
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def benchmark_driver():
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location("benchmark_clipper_for_test", root / "scripts/benchmark_clipper.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("scene", ["high", "courtside", "personal"])
def test_benchmark_records_explicit_input_choices(benchmark_driver, scene):
    assert benchmark_driver.recognition_optimizations(scene, "off") == dict(
        limit_fps=False, small_input=False, grayscale=False, dynamic_scan=False)
    assert benchmark_driver.recognition_optimizations(scene, "default") == dict(
        limit_fps=True, small_input=True, grayscale=True, dynamic_scan=scene == "high")


@pytest.mark.parametrize("has_audio,audio_samples,expected", [
    pytest.param(False, (), True, id="no-audio-track"),
    pytest.param(True, (), False, id="audio-track-with-no-frames"),
    pytest.param(True, (0,), False, id="audio-frame-with-zero-samples"),
    pytest.param(True, (1024,), True, id="nonempty-audio"),
])
def test_export_requires_audio_samples_when_expected(
        benchmark_driver, monkeypatch, has_audio, audio_samples, expected):
    time_base = Fraction(1, 1000)

    class VideoFrame:
        def __init__(self, pts):
            self.pts = pts
            self.time_base = time_base
            self.is_corrupt = False

    video = SimpleNamespace(time_base=time_base, duration=80, start_time=0,
                            average_rate=Fraction(25), width=64, height=36,
                            codec_context=SimpleNamespace(name="h264"))
    audio = SimpleNamespace(time_base=time_base, duration=80,
                            codec_context=SimpleNamespace(name="aac"))

    class Container:
        def __init__(self, *, exported):
            self.exported = exported
            self.streams = SimpleNamespace(video=[video], audio=[audio] if exported and has_audio else [])
            self.decode_calls = []
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def decode(self, **streams):
            self.decode_calls.append(streams)
            yield VideoFrame(0)
            yield VideoFrame(40)
            if self.exported:
                for index, samples in enumerate(audio_samples):
                    yield SimpleNamespace(pts=index * 20, time_base=time_base, samples=samples)

    source_container = Container(exported=False)
    output_container = Container(exported=True)
    containers = {"source.mp4": source_container, "output.mp4": output_container}
    fake_av = SimpleNamespace(VideoFrame=VideoFrame, open=containers.__getitem__)
    monkeypatch.setitem(sys.modules, "av", fake_av)
    info = SimpleNamespace(first_pts_ms=0, has_audio=has_audio, width=64, height=36)

    result = benchmark_driver.decode_and_validate(
        Path("source.mp4"), Path("output.mp4"), [(0, 80)], info, 80)

    assert result["checks"]["audio_decodes"] is expected
    assert result["passed"] is expected
    assert result["decoded"] == dict(video=2, audio=len(audio_samples), audio_samples=sum(audio_samples))
    assert result["expected_output_frames"] == 2
    assert source_container.decode_calls == [dict(video=0)]
    assert output_container.decode_calls == [dict(video=0, audio=0) if has_audio else dict(video=0)]
    assert source_container.closed and output_container.closed
