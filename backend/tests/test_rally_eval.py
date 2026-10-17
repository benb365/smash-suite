import json

import pytest

from app.vision.rally_eval import (
    RallyAnnotation, evaluate_rallies, load_rally_annotations, load_rally_exclusions,
)
from app.vision.rally_stream import RallyInterval


def test_matching_maximizes_total_iou_instead_of_taking_the_best_pair_first():
    # The best single pair is prediction 1 -> truth 1 (2/3), but the global
    # optimum is prediction 1 -> truth 2 (1/4), prediction 2 -> truth 1 (3/5).
    truth = [RallyAnnotation(1, 0, 10, "verified"), RallyAnnotation(2, 10, 20, "verified")]
    predictions = [RallyInterval(1, 0, 15, 20), RallyInterval(2, 0, 6, 20)]
    result = evaluate_rallies(predictions, truth)
    assert [(row["prediction_id"], row["truth_id"]) for row in result["matches"]] == [(1, 2), (2, 1)]
    assert result["false_merge_count"] == 1
    assert result["false_split_count"] == 1
    assert result["missed_rally_count"] == 0


def test_split_and_merge_count_excess_intervals_without_merging_the_truth():
    truth = [RallyAnnotation(i, (i - 1) * 10, i * 10, "verified") for i in range(1, 4)]
    predictions = [RallyInterval(1, 0, 30, 40), RallyInterval(2, 0, 3, 4), RallyInterval(3, 3, 6, 7)]
    result = evaluate_rallies(predictions, truth)
    assert result["truth_count"] == 3
    assert result["false_merge_count"] == 2
    assert result["false_split_count"] == 2
    assert result["truth_overlaps"][1] == [1, 2, 3]
    assert len(result["matches"]) == 2
    assert result["unmatched_truth_ids"] == [3]
    assert result["boundary_acceptance"]["truth_count"] == 3
    assert result["boundary_acceptance"]["matched_count"] == 2
    assert result["boundary_acceptance"]["start_acceptable_rate"] == 2 / 3
    # All truth intervals have a positive overlap, even the unmatched one.
    assert result["missed_rally_count"] == 0


def test_touching_boundaries_do_not_match_and_unreviewed_rows_are_excluded():
    truth = [RallyAnnotation(1, 10, 20, "verified"), RallyAnnotation(2, 0, 10, "draft")]
    result = evaluate_rallies([RallyInterval(1, 0, 10, 12)], truth)
    assert result["matches"] == []
    assert result["missed_rally_count"] == 1
    assert result["excluded_annotation_ids"] == [2]
    assert result["unmatched_prediction_ids"] == [1]
    assert result["start_error_ms"]["mean"] is None
    assert result["output_latency_ms"]["mean"] == 2


def test_boundary_errors_only_count_distance_outside_one_sided_tolerance():
    result = evaluate_rallies(
        [RallyInterval(1, 12000, 18000, 22000), RallyInterval(2, 29000, 41000, 44000)],
        [RallyAnnotation(1, 10000, 20000, "verified"),
         RallyAnnotation(2, 30000, 40000, "verified")],
    )
    assert result["evaluator_version"] == "rally-iou-v3"
    assert result["start_error_ms"] == {"count": 1, "mean": 2000, "p50": 2000, "p95": 2000, "max": 2000}
    assert result["end_error_ms"]["count"] == 1
    assert result["end_error_ms"]["max"] == 2000
    assert result["matches"][1]["start_offset_ms"] == -1000
    assert result["matches"][1]["end_offset_ms"] == 1000
    assert result["matches"][1]["start_error_ms"] == result["matches"][1]["end_error_ms"] == 0
    assert result["boundary_acceptance"]["both_acceptable_rate"] == 0.5
    assert result["output_latency_ms"]["mean"] == 3500


@pytest.mark.parametrize("start,end,start_error,end_error", [
    (8500, 21500, 0, 0),          # Inclusive outward limits.
    (10000, 20000, 0, 0),        # Exact truth boundaries.
    (8499, 21501, 1, 1),        # Only the excess beyond 1.5 seconds counts.
    (10001, 19999, 1, 1),       # No inward tolerance, even at one millisecond.
    (9000, 19960, 0, 40),       # The two boundaries pass independently.
])
def test_boundary_tolerance_limits_and_inward_cuts(start, end, start_error, end_error):
    result = evaluate_rallies([RallyInterval(1, start, end, 22000)],
                             [RallyAnnotation(1, 10000, 20000, "verified")])
    row = result["matches"][0]
    assert (row["start_error_ms"], row["end_error_ms"]) == (start_error, end_error)
    assert row["both_acceptable"] == (start_error == end_error == 0)
    if row["both_acceptable"]:
        assert result["start_error_ms"]["count"] == result["end_error_ms"]["count"] == 0
        assert result["start_error_ms"]["p95"] is None


def test_empty_inputs_and_duplicate_ids():
    result = evaluate_rallies([], [])
    assert result["matches"] == []
    assert result["output_latency_ms"]["count"] == 0
    assert result["boundary_acceptance"]["both_acceptable_rate"] is None
    with pytest.raises(ValueError, match="unique"):
        evaluate_rallies([RallyInterval(1, 0, 1, 2)] * 2, [])


def test_annotation_loader_rejects_pending_human_review(tmp_path):
    path = tmp_path / "annotations.json"
    path.write_text(json.dumps({"generation": {"requires_human_review": True}, "segments": []}))
    with pytest.raises(ValueError, match="human review"):
        load_rally_annotations(path)
    with pytest.raises(ValueError, match="human review"):
        load_rally_exclusions(path)


def test_confirmed_exclusion_only_ignores_fully_contained_predictions():
    event = dict(event_id="return", range_ms=[10, 20], review_status="human_confirmed")
    predictions = [RallyInterval(1, 10, 20, 21), RallyInterval(2, 9, 15, 21),
                   RallyInterval(3, 15, 21, 22), RallyInterval(4, 5, 25, 26)]
    result = evaluate_rallies(predictions, [], excluded_events=[event])
    assert result["input_prediction_count"] == 4
    assert result["prediction_count"] == result["false_positive_count"] == 3
    assert result["ignored_predictions"] == [dict(prediction=dict(
        rally_id=1, start_ms=10, end_ms=20, emitted_at_ms=21), event_ids=["return"])]
    assert result["unmatched_prediction_ids"] == [2, 3, 4]
    assert result["output_latency_ms"]["count"] == 3


def test_exclusion_cannot_hide_prediction_that_overlaps_a_scored_rally():
    event = dict(event_id="return", range_ms=[0, 30], review_status="human_confirmed")
    result = evaluate_rallies([RallyInterval(1, 5, 25, 30)],
                             [RallyAnnotation(1, 10, 20, "verified")], excluded_events=[event])
    assert result["ignored_predictions"] == []
    assert len(result["matches"]) == 1


def test_exclusion_requires_review_valid_range_and_unique_identity():
    event = dict(event_id="return", range_ms=[10, 20], review_status="needs_review")
    with pytest.raises(ValueError, match="human confirmation"):
        evaluate_rallies([], [], excluded_events=[event])
    event["review_status"] = "human_confirmed"
    with pytest.raises(ValueError, match="unique"):
        evaluate_rallies([], [], excluded_events=[event, event])
    event["range_ms"] = [20, 10]
    with pytest.raises(ValueError, match="positive"):
        evaluate_rallies([], [], excluded_events=[event])
