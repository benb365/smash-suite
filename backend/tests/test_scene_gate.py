from app.models import SceneCandidate, SceneSegment
from app.vision.scene_gate import FrameMetric, SceneGateConfig, build_scene_timeline


def test_scene_gate_contract_covers_required_fields() -> None:
    candidate = SceneCandidate(
        start_ms=200.0,
        end_ms=320.0,
        confidence=0.9,
        reason="motion_ratio>=0.080",
        source_frame_range=[3, 3],
        parent_segment_index=1,
    )
    segment = SceneSegment(
        category="rally",
        start_ms=100.0,
        end_ms=500.0,
        confidence=0.82,
        reason="motion_ratio>=0.010",
        source_frame_range=[12, 24],
        smash_candidates=[candidate],
    )

    assert segment.category == "rally"
    assert segment.source_frame_range == [12, 24]
    assert segment.smash_candidates[0].category == "smash_candidate"


def test_build_scene_timeline_nests_smash_candidates_inside_rally() -> None:
    config = SceneGateConfig(
        idle_motion_ratio=0.01,
        smash_motion_ratio=0.08,
        smash_component_area_ratio=0.04,
        smash_pre_roll_ms=0.0,
        smash_post_roll_ms=0.0,
        min_segment_ms=0.0,
        min_rally_ms=0.0,
        min_idle_ms=0.0,
        min_candidate_ms=0.0,
    )
    metrics = [
        FrameMetric(frame_id=1, time_ms=0.0, motion_ratio=0.001, max_component_area_ratio=0.0),
        FrameMetric(frame_id=2, time_ms=100.0, motion_ratio=0.02, max_component_area_ratio=0.0),
        FrameMetric(frame_id=3, time_ms=200.0, motion_ratio=0.09, max_component_area_ratio=0.0),
        FrameMetric(frame_id=4, time_ms=300.0, motion_ratio=0.02, max_component_area_ratio=0.0),
    ]

    segments, candidates = build_scene_timeline(metrics, config, duration_ms=400.0)

    assert [segment.category for segment in segments] == ["idle", "rally"]
    assert len(candidates) == 1
    assert candidates[0].category == "smash_candidate"
    assert candidates[0].parent_segment_index == 1
    assert segments[1].smash_candidates == candidates


def test_large_foreground_motion_is_suppressed_as_idle() -> None:
    config = SceneGateConfig(
        idle_motion_ratio=0.01,
        occlusion_motion_ratio=0.2,
        occlusion_component_area_ratio=0.1,
        min_segment_ms=0.0,
        min_rally_ms=0.0,
        min_idle_ms=0.0,
        min_candidate_ms=0.0,
    )
    metrics = [
        FrameMetric(frame_id=1, time_ms=0.0, motion_ratio=0.001, max_component_area_ratio=0.0),
        FrameMetric(frame_id=2, time_ms=100.0, motion_ratio=0.25, max_component_area_ratio=0.15),
        FrameMetric(frame_id=3, time_ms=200.0, motion_ratio=0.02, max_component_area_ratio=0.0),
    ]

    segments, candidates = build_scene_timeline(metrics, config, duration_ms=300.0)

    assert segments[0].category == "idle"
    assert "large_foreground_motion_suppressed" in segments[0].reason
    assert candidates == []
