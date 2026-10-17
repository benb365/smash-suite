from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


SessionStatus = Literal["created", "calibrated", "running", "completed", "failed", "stopped"]
SourceType = Literal["video_file", "camera"]
SceneTimelineCategory = Literal["idle", "rally"]
SceneCandidateCategory = Literal["smash_candidate"]


class Point2D(BaseModel):
    x: float
    y: float


class CalibrationConfig(BaseModel):
    image_points: List[Point2D] = Field(default_factory=list)
    world_points: List[Point2D] = Field(default_factory=list)
    fps: Optional[float] = None
    court_profile: str = "badminton_doubles"
    court_width_m: float = 6.1
    court_length_m: float = 13.4


class SessionCreate(BaseModel):
    name: Optional[str] = None


class SourceConfig(BaseModel):
    source_type: SourceType
    path: Optional[str] = None
    camera_index: int = 0
    fps: Optional[float] = None


class RunRequest(BaseModel):
    source: SourceConfig
    max_frames: Optional[int] = 3000
    sample_stride: int = 1
    save_keyframes: bool = True


class TrajectoryPoint(BaseModel):
    frame_id: int
    time_ms: float
    pixel: Point2D
    world: Optional[Point2D] = None
    confidence: float = 0.0
    source: str = "motion_baseline"


class SpeedSample(BaseModel):
    time_ms: float
    speed_kmh: float
    confidence: float
    frame_start: int
    frame_end: int


class KeyframeEvent(BaseModel):
    time_ms: float
    frame_id: int
    reason: str
    confidence: float
    clip_path: Optional[str] = None


class SceneCandidate(BaseModel):
    category: SceneCandidateCategory = "smash_candidate"
    start_ms: float
    end_ms: float
    confidence: float
    reason: str
    source_frame_range: List[int]
    parent_segment_index: Optional[int] = None


class SceneSegment(BaseModel):
    category: SceneTimelineCategory
    start_ms: float
    end_ms: float
    confidence: float
    reason: str
    source_frame_range: List[int]
    smash_candidates: List[SceneCandidate] = Field(default_factory=list)
    emitted_at_ms: Optional[float] = None
    latency_ms: Optional[float] = None
    boundary_reason: Optional[str] = None
    signal_source: Optional[str] = None


class SceneGateResult(BaseModel):
    video_path: str
    fps: float
    frame_count: int
    duration_ms: float
    analyzed_frame_count: int
    sample_stride: int
    retained_ms: float
    retained_ratio: float
    smash_candidate_ms: float = 0.0
    smash_candidate_ratio: float = 0.0
    category_durations_ms: Dict[str, float] = Field(default_factory=dict)
    segments: List[SceneSegment] = Field(default_factory=list)
    smash_candidates: List[SceneCandidate] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    id: str
    name: str
    status: SessionStatus
    created_at: str
    updated_at: str
    calibration: Optional[CalibrationConfig] = None
    source: Optional[SourceConfig] = None
    latest_speed_kmh: Optional[float] = None
    result_count: int = 0
    error: Optional[str] = None


class AnalysisResults(BaseModel):
    session_id: str
    trajectory_points: List[TrajectoryPoint] = Field(default_factory=list)
    speed_samples: List[SpeedSample] = Field(default_factory=list)
    keyframes: List[KeyframeEvent] = Field(default_factory=list)
    exports: Dict[str, str] = Field(default_factory=dict)


class SocketEvent(BaseModel):
    type: str
    payload: Dict[str, Any]
