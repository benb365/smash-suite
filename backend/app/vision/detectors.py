from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models import Point2D


@dataclass
class Detection:
    pixel: Point2D
    confidence: float
    area: float


class MotionDetector:
    def __init__(
        self,
        threshold: int = 28,
        min_area: float = 2.0,
        max_area: float = 900.0,
    ) -> None:
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV is required for video analysis. Install backend requirements first."
            ) from exc
        self._cv2 = cv2
        self.threshold = threshold
        self.min_area = min_area
        self.max_area = max_area
        self._previous_gray = None

    def detect(self, frame: object) -> Optional[Detection]:
        cv2 = self._cv2
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self._previous_gray is None:
            self._previous_gray = gray
            return None

        diff = cv2.absdiff(self._previous_gray, gray)
        self._previous_gray = gray
        _, mask = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, None, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best: Optional[Detection] = None
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area or area > self.max_area:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            center_x = moments["m10"] / moments["m00"]
            center_y = moments["m01"] / moments["m00"]
            confidence = max(0.1, min(1.0, area / self.max_area))
            detection = Detection(
                pixel=Point2D(x=float(center_x), y=float(center_y)),
                confidence=confidence,
                area=area,
            )
            if best is None or detection.confidence > best.confidence:
                best = detection
        return best
