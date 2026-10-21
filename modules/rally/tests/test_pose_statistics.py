import time

import numpy as np
import pytest
import torch

from modules.models.keypoint_rcnn import PoseEstimator
from modules.rally.statistics import Statistics


def test_single_image_statistics_do_not_change_output_or_read_clock_when_disabled(monkeypatch):
    class FakeModel:
        def __init__(self):
            self.calls = 0

        def __call__(self, images):
            assert len(images) == 1
            self.calls += 1
            return [dict(boxes=torch.tensor([[12.0, 24.0]]))]

    estimator = object.__new__(PoseEstimator)
    estimator.torch = torch
    estimator.model = FakeModel()
    image = np.zeros((8, 12, 3), dtype=np.uint8)

    enabled = Statistics(enabled=True)
    enabled_result = estimator(image, statistics=enabled)
    assert {"pose_input_preparation_s", "pose_model_call_s", "pose_result_conversion_s"} <= enabled.seconds.keys()

    monkeypatch.setattr(time, "monotonic", lambda: pytest.fail("disabled statistics must not read the clock"))
    disabled = Statistics(enabled=False)
    disabled_result = estimator(image, statistics=disabled)

    assert np.array_equal(enabled_result["boxes"], disabled_result["boxes"])
    assert estimator.model.calls == 2
    assert dict(disabled.seconds) == {}
