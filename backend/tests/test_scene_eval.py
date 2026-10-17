from app.vision.scene_eval import (
    Interval,
    ManualAnnotationNotVerifiedError,
    evaluate_intervals,
    evaluate_rally_boundaries,
    load_manual_rally_annotations,
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


def test_load_manual_rally_annotations_rejects_unreviewed_draft(tmp_path) -> None:
    annotation = tmp_path / "rally-segment-manual.json"
    annotation.write_text(
        """
        {
          "status": "draft_needs_human_review",
          "generation": {"requires_human_review": true},
          "segments": [
            {"start_ms": 1000, "end_ms": 3000, "review_status": "needs_human_review"}
          ]
        }
        """,
        encoding="utf-8",
    )

    try:
        load_manual_rally_annotations(annotation)
    except ManualAnnotationNotVerifiedError as exc:
        assert "not human verified" in str(exc)
    else:
        raise AssertionError("Expected draft manual annotations to be rejected")


def test_load_manual_rally_annotations_accepts_verified_segments(tmp_path) -> None:
    annotation = tmp_path / "rally-segment-manual.json"
    annotation.write_text(
        """
        {
          "status": "verified",
          "segments": [
            {"start_time": "00:01.250", "end_time": "00:03.500", "review_status": "verified"}
          ]
        }
        """,
        encoding="utf-8",
    )

    assert load_manual_rally_annotations(annotation) == [
        Interval(start_ms=1250.0, end_ms=3500.0)
    ]


def test_evaluate_rally_boundaries_reports_containment_and_splits() -> None:
    manual = [
        Interval(start_ms=10_000.0, end_ms=14_000.0),
        Interval(start_ms=20_000.0, end_ms=24_000.0),
    ]
    predicted = [
        Interval(start_ms=9_000.0, end_ms=15_000.0),
        Interval(start_ms=19_500.0, end_ms=22_000.0),
        Interval(start_ms=22_000.0, end_ms=24_500.0),
    ]

    metrics = evaluate_rally_boundaries(predicted, manual, boundary_tolerance_ms=2000.0)

    assert metrics["containment_rate"] == 0.5
    assert metrics["boundary_pass_rate_2s"] == 0.5
    assert metrics["missed_rally_count"] == 1
    assert metrics["false_split_count"] == 1
    assert metrics["false_merge_count"] == 0
