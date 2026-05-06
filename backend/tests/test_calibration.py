from app.models import CalibrationConfig, Point2D
from app.vision.calibration import CourtProjector, with_default_world_points


def test_default_world_points_are_added() -> None:
    config = CalibrationConfig(
        image_points=[
            Point2D(x=0, y=0),
            Point2D(x=610, y=0),
            Point2D(x=610, y=1340),
            Point2D(x=0, y=1340),
        ]
    )

    normalized = with_default_world_points(config)

    assert len(normalized.world_points) == 4
    assert normalized.world_points[1].x == 6.1
    assert normalized.world_points[2].y == 13.4


def test_projector_maps_rectangular_court_center() -> None:
    config = with_default_world_points(
        CalibrationConfig(
            image_points=[
                Point2D(x=0, y=0),
                Point2D(x=610, y=0),
                Point2D(x=610, y=1340),
                Point2D(x=0, y=1340),
            ]
        )
    )
    projector = CourtProjector(config)

    center = projector.project(Point2D(x=305, y=670))

    assert center is not None
    assert round(center.x, 2) == 3.05
    assert round(center.y, 2) == 6.7
