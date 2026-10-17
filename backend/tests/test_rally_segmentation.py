from __future__ import annotations

from app.vision.rally_segmentation import (
    PlayerDetection,
    RallyFrameSignal,
    RallySegmentationConfig,
    RallySignalBuilder,
    SimpleOnlineTracker,
    UltralyticsByteTrackProvider,
    build_rally_segments_from_trace,
    build_rally_scene_gate_result,
    build_rally_segments_from_signals,
)


def test_state_machine_emits_rally_after_end_confirmation_without_future_frames() -> None:
    config = RallySegmentationConfig(
        start_guard_ms=1000.0,
        end_guard_ms=1000.0,
        end_confirm_ms=3000.0,
        active_window_ms=500.0,
        merge_gap_ms=0.0,
        min_rally_ms=1000.0,
    )
    signals = [
        _signal(frame_id=1, time_ms=1000.0, active=True),
        _signal(frame_id=2, time_ms=1600.0, active=True),
        _signal(frame_id=3, time_ms=2200.0, active=True),
        _signal(frame_id=4, time_ms=2800.0, active=False),
        _signal(frame_id=5, time_ms=3600.0, active=False),
        _signal(frame_id=6, time_ms=5300.0, active=False),
    ]

    segments = build_rally_segments_from_signals(signals, config)

    assert len(segments) == 1
    assert segments[0].start_ms == 0.0
    assert segments[0].end_ms == 3200.0
    assert segments[0].emitted_at_ms == 5300.0
    assert segments[0].latency_ms == 2100.0
    assert segments[0].boundary_reason == "end_confirmed_after_low_activity"


def test_tracker_and_signal_builder_detect_active_opposing_main_players() -> None:
    config = RallySegmentationConfig(
        roi_polygon=((0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)),
        stable_visible_ms=0.0,
        active_speed_px_s=80.0,
        active_acceleration_px_s2=1000.0,
        hit_like_speed_px_s=300.0,
        min_detection_confidence=0.1,
    )
    tracker = SimpleOnlineTracker(config)
    builder = RallySignalBuilder(config)

    tracks = tracker.update(
        [
            PlayerDetection(40.0, 20.0, 70.0, 60.0, confidence=0.9, track_id=1),
            PlayerDetection(130.0, 130.0, 160.0, 170.0, confidence=0.9, track_id=2),
        ],
        frame_id=1,
        time_ms=0.0,
    )
    first_signal = builder.build(frame_id=1, time_ms=0.0, tracks=tracks)

    tracks = tracker.update(
        [
            PlayerDetection(90.0, 20.0, 120.0, 60.0, confidence=0.9, track_id=1),
            PlayerDetection(130.0, 130.0, 160.0, 170.0, confidence=0.9, track_id=2),
        ],
        frame_id=2,
        time_ms=500.0,
    )
    second_signal = builder.build(frame_id=2, time_ms=500.0, tracks=tracks)

    assert first_signal.active is False
    assert second_signal.main_track_ids == (1, 2)
    assert second_signal.pair_stable is True
    assert second_signal.opposite_halves is True
    assert second_signal.active is True
    assert second_signal.reason == "main_players_active"


def test_build_rally_scene_gate_result_uses_rally_retained_ratio() -> None:
    config = RallySegmentationConfig()
    segments = [
        _scene_signal_segment(start_ms=1000.0, end_ms=3000.0),
        _scene_signal_segment(start_ms=6000.0, end_ms=8000.0),
    ]

    result = build_rally_scene_gate_result(
        video_path="datasets/badminton-v1/local/ysp/test_ysp.ts",
        fps=25.0,
        frame_count=250,
        duration_ms=10_000.0,
        analyzed_frame_count=50,
        sample_stride=5,
        segments=segments,
        config=config,
        detector_name="synthetic",
    )

    assert result.retained_ms == 4000.0
    assert result.retained_ratio == 0.4
    assert result.category_durations_ms == {"rally": 4000.0}
    assert result.config["algorithm"] == "person_tracking_state_machine"


def test_ultralytics_bytetrack_provider_parses_person_tracks_only() -> None:
    model = _FakeYoloModel(
        [
            _FakeBoxes(
                xyxy=[
                    [10.0, 20.0, 30.0, 60.0],
                    [40.0, 20.0, 60.0, 60.0],
                    [70.0, 20.0, 90.0, 60.0],
                ],
                conf=[0.9, 0.8, 0.7],
                cls=[0, 1, 0],
                ids=[5, 6, None],
            )
        ]
    )
    provider = UltralyticsByteTrackProvider(
        model_path="fake.pt",
        tracker_config="bytetrack.yaml",
        model=model,
    )

    detections, tracks = provider.detect_and_track(frame=object(), frame_id=10, time_ms=400.0)

    assert len(detections) == 2
    assert detections[0].track_id == 5
    assert detections[1].track_id is None
    assert [track.track_id for track in tracks] == [5]
    assert model.calls[0]["tracker"] == "bytetrack.yaml"
    assert model.calls[0]["persist"] is True
    assert model.calls[0]["classes"] == [0]


def test_signal_builder_selects_stable_bytetrack_main_players() -> None:
    config = RallySegmentationConfig(
        roi_polygon=((0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)),
        stable_visible_ms=0.0,
        active_speed_px_s=80.0,
        active_acceleration_px_s2=1000.0,
        min_detection_confidence=0.1,
    )
    model = _FakeYoloModel(
        [
            _FakeBoxes(
                xyxy=[[40.0, 20.0, 70.0, 60.0], [130.0, 130.0, 160.0, 170.0]],
                conf=[0.9, 0.9],
                cls=[0, 0],
                ids=[10, 20],
            ),
            _FakeBoxes(
                xyxy=[[90.0, 20.0, 120.0, 60.0], [130.0, 130.0, 160.0, 170.0]],
                conf=[0.9, 0.9],
                cls=[0, 0],
                ids=[10, 20],
            ),
        ]
    )
    provider = UltralyticsByteTrackProvider(model_path="fake.pt", model=model)
    builder = RallySignalBuilder(config)

    provider.detect_and_track(frame=object(), frame_id=1, time_ms=0.0)
    _, tracks = provider.detect_and_track(frame=object(), frame_id=2, time_ms=500.0)
    signal = builder.build(frame_id=2, time_ms=500.0, tracks=tracks)

    assert signal.main_track_ids == (10, 20)
    assert signal.pair_stable is True
    assert signal.opposite_halves is True
    assert signal.active is True


def test_build_rally_segments_from_trace_replays_state_machine(tmp_path) -> None:
    trace = tmp_path / "trace.jsonl"
    signals = [
        _signal(frame_id=1, time_ms=1000.0, active=True),
        _signal(frame_id=2, time_ms=1600.0, active=True),
        _signal(frame_id=3, time_ms=5300.0, active=False),
    ]
    trace.write_text(
        "\n".join(
            '{"signal": ' + _json_signal(signal) + "}"
            for signal in signals
        )
        + "\n",
        encoding="utf-8",
    )

    segments = build_rally_segments_from_trace(
        trace,
        RallySegmentationConfig(
            start_guard_ms=1000.0,
            end_guard_ms=1000.0,
            end_confirm_ms=3000.0,
            active_window_ms=500.0,
            merge_gap_ms=0.0,
            min_rally_ms=1000.0,
        ),
    )

    assert len(segments) == 1
    assert segments[0].start_ms == 0.0
    assert segments[0].end_ms == 2600.0


def _signal(frame_id: int, time_ms: float, active: bool) -> RallyFrameSignal:
    return RallyFrameSignal(
        frame_id=frame_id,
        time_ms=time_ms,
        visible_player_count=2,
        main_track_ids=(1, 2),
        main_feet=((50.0, 50.0), (150.0, 150.0)),
        pair_stable=True,
        opposite_halves=True,
        active=active,
        hit_like=False,
        max_foot_speed_px_s=140.0 if active else 0.0,
        max_foot_acceleration_px_s2=0.0,
        confidence=0.8 if active else 0.55,
        reason="synthetic_active" if active else "synthetic_low_motion",
    )


def _json_signal(signal: RallyFrameSignal) -> str:
    import json
    from dataclasses import asdict

    return json.dumps(asdict(signal))


def _scene_signal_segment(start_ms: float, end_ms: float):
    from app.models import SceneSegment

    return SceneSegment(
        category="rally",
        start_ms=start_ms,
        end_ms=end_ms,
        confidence=0.8,
        reason="person_tracking_state_machine",
        source_frame_range=[1, 2],
        emitted_at_ms=end_ms + 2000.0,
        latency_ms=2000.0,
        boundary_reason="end_confirmed_after_low_activity",
        signal_source="person_detection_tracking",
    )


class _FakeYoloModel:
    def __init__(self, boxes_by_call):
        self.boxes_by_call = list(boxes_by_call)
        self.calls = []

    def track(self, frame, **kwargs):
        del frame
        self.calls.append(kwargs)
        return [_FakeResult(self.boxes_by_call.pop(0))]


class _FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeBoxes:
    def __init__(self, xyxy, conf, cls, ids):
        self.xyxy = xyxy
        self.conf = conf
        self.cls = cls
        self.id = ids
