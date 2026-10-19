from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
SceneTimelineCategory = Literal['idle', 'rally']
SceneCandidateCategory = Literal['smash_candidate']

class SceneCandidate(BaseModel):
    category: SceneCandidateCategory = 'smash_candidate'
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
