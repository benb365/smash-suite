from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from modules.media.types import VideoInfo


CameraType = Literal["high", "courtside", "personal"]
Quality = Literal["high", "balanced", "small"]


class ProcessRequest(BaseModel):
    camera_type: CameraType
    quality: Quality = "balanced"
    show_shot_paths: bool = True
    court: Optional[list[tuple[float, float]]] = None
    optimizations: Optional["Optimizations"] = None

    @model_validator(mode="after")
    def resolve_optimizations(self):
        defaults = dict(limit_fps=True, small_input=True, grayscale=True,
                        dynamic_scan=self.camera_type == "high")
        requested = self.optimizations or Optimizations()
        self.optimizations = Optimizations(**{
            name: getattr(requested, name) if getattr(requested, name) is not None else default
            for name, default in defaults.items()
        })
        return self

    @field_validator("court")
    @classmethod
    def valid_court(cls, points):
        if points is None:
            return None
        if len(points) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for p in points for v in p):
            raise ValueError("请按顺序选择球场的四个角。")
        area = sum(points[i][0] * points[(i + 1) % 4][1] - points[(i + 1) % 4][0] * points[i][1]
                   for i in range(4))
        cross = [(points[(i + 1) % 4][0] - points[i][0]) * (points[(i + 2) % 4][1] - points[(i + 1) % 4][1])
                 - (points[(i + 1) % 4][1] - points[i][1]) * (points[(i + 2) % 4][0] - points[(i + 1) % 4][0])
                 for i in range(4)]
        if abs(area) < .002 or not (all(c > 0 for c in cross) or all(c < 0 for c in cross)):
            raise ValueError("球场区域必须是四角依次相连的有效四边形。")
        return points


class Optimizations(BaseModel):
    limit_fps: Optional[bool] = None
    small_input: Optional[bool] = None
    grayscale: Optional[bool] = None
    dynamic_scan: Optional[bool] = None


class ProcessingTimings(BaseModel):
    preparation_s: float = Field(ge=0)
    recognition_s: float = Field(ge=0)
    rendering_s: float = Field(ge=0)


class JobState(BaseModel):
    status: Literal["empty", "uploading", "ready", "running", "completed", "failed", "cancelled"] = "empty"
    stage: str = "选择一份 MP4 录像开始"
    progress: float = 0
    video: Optional[VideoInfo] = None
    output_url: Optional[str] = None
    output_bytes: Optional[int] = None
    output_duration_ms: Optional[float] = None
    rally_count: int = 0
    elapsed_s: Optional[float] = None
    timings: Optional[ProcessingTimings] = None
    error: Optional[str] = None
    camera_type: Optional[CameraType] = None
    quality: Quality = "balanced"
    optimizations: Optional[Optimizations] = None
    warnings: list[str] = Field(default_factory=list)
