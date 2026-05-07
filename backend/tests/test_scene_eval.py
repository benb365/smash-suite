from app.vision.scene_eval import (
    Interval,
    evaluate_intervals,
    parse_manual_scene_intervals,
    scene_gate_rally_intervals,
)


def test_parse_manual_scene_intervals_ignores_header() -> None:
    intervals = parse_manual_scene_intervals(
        """
        rally invervals
        0:01 - 0:03
        1:08 - 1:10
        """
    )

    assert intervals == [
        Interval(start_ms=1000.0, end_ms=3000.0),
        Interval(start_ms=68000.0, end_ms=70000.0),
    ]


def test_evaluate_intervals_uses_boundary_tolerance() -> None:
    manual = [Interval(start_ms=10_000.0, end_ms=15_000.0)]
    predicted = [Interval(start_ms=9_500.0, end_ms=15_500.0)]

    metrics = evaluate_intervals(predicted, manual, tolerance_ms=1000.0)

    assert metrics["manual_hit_rate"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["precision"] == 1.0


def test_scene_gate_rally_intervals_extracts_only_primary_rally_segments() -> None:
    scene_gate = {
        "segments": [
            {"category": "idle", "start_ms": 0.0, "end_ms": 1000.0},
            {"category": "rally", "start_ms": 1000.0, "end_ms": 3000.0},
        ]
    }

    assert scene_gate_rally_intervals(scene_gate) == [Interval(start_ms=1000.0, end_ms=3000.0)]
