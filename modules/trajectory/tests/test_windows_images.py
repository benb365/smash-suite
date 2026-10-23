import cv2
import numpy as np
import pytest

from modules.trajectory.court import _write_image


@pytest.mark.parametrize("suffix", [".jpg", ".png"])
def test_court_diagnostic_image_supports_unicode_path(tmp_path, suffix):
    destination = tmp_path / f"球场 标定{suffix}"
    image = np.full((18, 24, 3), 120, dtype=np.uint8)
    _write_image(destination, image)
    decoded = cv2.imdecode(np.fromfile(destination, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == image.shape
    assert np.max(np.abs(decoded.astype(int) - image.astype(int))) <= 1


def test_court_diagnostic_encoding_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(cv2, "imencode", lambda *args: (False, None))
    destination = tmp_path / "球场标定.png"
    with pytest.raises(RuntimeError, match="无法编码球场诊断图"):
        _write_image(destination, np.zeros((2, 2), dtype=np.uint8))
    assert not destination.exists()
