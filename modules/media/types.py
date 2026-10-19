from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel

@dataclass(frozen=True)
class TimestampedFrame:
    frame_id: int
    timestamp_ms: float
    image: Any

class VideoInfo(BaseModel):
    name: str
    duration_ms: float
    width: int
    height: int
    has_audio: bool
    first_pts_ms: float
