from __future__ import annotations

import math
from collections import deque
from statistics import median
from typing import Deque, Optional, Tuple

from app.models import TrajectoryPoint


def compute_speed_between(
    previous: TrajectoryPoint,
    current: TrajectoryPoint,
    max_speed_kmh: float = 600.0,
) -> Optional[Tuple[float, float]]:
    if previous.world is None or current.world is None:
        return None
    delta_ms = current.time_ms - previous.time_ms
    if delta_ms <= 0:
        return None

    distance_m = math.hypot(current.world.x - previous.world.x, current.world.y - previous.world.y)
    speed_kmh = (distance_m / (delta_ms / 1000.0)) * 3.6
    if speed_kmh < 0 or speed_kmh > max_speed_kmh:
        return None
    confidence = min(previous.confidence, current.confidence)
    return speed_kmh, confidence


class SpeedSmoother:
    def __init__(self, window_size: int = 3) -> None:
        self.window_size = max(1, window_size)
        self._values: Deque[float] = deque(maxlen=self.window_size)

    def push(self, value: float) -> float:
        self._values.append(value)
        return float(median(self._values))
