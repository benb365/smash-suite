from __future__ import annotations

from typing import Optional

from app.models import CalibrationConfig, Point2D


def default_world_points(width_m: float = 6.1, length_m: float = 13.4) -> list[Point2D]:
    return [
        Point2D(x=0.0, y=0.0),
        Point2D(x=width_m, y=0.0),
        Point2D(x=width_m, y=length_m),
        Point2D(x=0.0, y=length_m),
    ]


def with_default_world_points(config: CalibrationConfig) -> CalibrationConfig:
    if config.world_points:
        return config
    return CalibrationConfig(
        image_points=config.image_points,
        world_points=default_world_points(config.court_width_m, config.court_length_m),
        fps=config.fps,
        court_profile=config.court_profile,
        court_width_m=config.court_width_m,
        court_length_m=config.court_length_m,
    )


class CourtProjector:
    def __init__(self, config: CalibrationConfig) -> None:
        self.config = with_default_world_points(config)
        self._homography = None
        self._cv2 = None
        self._np = None
        self._try_build_homography()

    def project(self, point: Point2D) -> Optional[Point2D]:
        if len(self.config.image_points) < 4 or len(self.config.world_points) < 4:
            return None
        if self._homography is not None and self._cv2 is not None and self._np is not None:
            source = self._np.array([[[point.x, point.y]]], dtype="float32")
            mapped = self._cv2.perspectiveTransform(source, self._homography)[0][0]
            return Point2D(x=float(mapped[0]), y=float(mapped[1]))
        return self._linear_project(point)

    def _try_build_homography(self) -> None:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            return

        src = np.array([[p.x, p.y] for p in self.config.image_points[:4]], dtype="float32")
        dst = np.array([[p.x, p.y] for p in self.config.world_points[:4]], dtype="float32")
        matrix, _ = cv2.findHomography(src, dst)
        if matrix is not None:
            self._homography = matrix
            self._cv2 = cv2
            self._np = np

    def _linear_project(self, point: Point2D) -> Optional[Point2D]:
        image_points = self.config.image_points[:4]
        world_points = self.config.world_points[:4]
        x_min = min(p.x for p in image_points)
        x_max = max(p.x for p in image_points)
        y_min = min(p.y for p in image_points)
        y_max = max(p.y for p in image_points)
        if x_max == x_min or y_max == y_min:
            return None

        world_x_min = min(p.x for p in world_points)
        world_x_max = max(p.x for p in world_points)
        world_y_min = min(p.y for p in world_points)
        world_y_max = max(p.y for p in world_points)

        x_ratio = (point.x - x_min) / (x_max - x_min)
        y_ratio = (point.y - y_min) / (y_max - y_min)
        return Point2D(
            x=world_x_min + x_ratio * (world_x_max - world_x_min),
            y=world_y_min + y_ratio * (world_y_max - world_y_min),
        )
