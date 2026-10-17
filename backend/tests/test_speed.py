from app.models import Point2D, TrajectoryPoint
from app.vision.speed import SpeedSmoother, compute_speed_between


def test_compute_speed_between_world_points() -> None:
    previous = TrajectoryPoint(
        frame_id=1,
        time_ms=0.0,
        pixel=Point2D(x=0, y=0),
        world=Point2D(x=0, y=0),
        confidence=0.9,
    )
    current = TrajectoryPoint(
        frame_id=2,
        time_ms=100.0,
        pixel=Point2D(x=10, y=0),
        world=Point2D(x=10, y=0),
        confidence=0.8,
    )

    computed = compute_speed_between(previous, current)

    assert computed is not None
    speed_kmh, confidence = computed
    assert speed_kmh == 360.0
    assert confidence == 0.8


def test_compute_speed_filters_impossible_values() -> None:
    previous = TrajectoryPoint(
        frame_id=1,
        time_ms=0.0,
        pixel=Point2D(x=0, y=0),
        world=Point2D(x=0, y=0),
        confidence=1.0,
    )
    current = TrajectoryPoint(
        frame_id=2,
        time_ms=1.0,
        pixel=Point2D(x=100, y=0),
        world=Point2D(x=100, y=0),
        confidence=1.0,
    )

    assert compute_speed_between(previous, current) is None


def test_speed_smoother_uses_median_window() -> None:
    smoother = SpeedSmoother(window_size=3)

    assert smoother.push(100.0) == 100.0
    assert smoother.push(120.0) == 110.0
    assert smoother.push(500.0) == 120.0
