from modules.rally.evaluation.rally_eval import RallyAnnotation
from modules.rally.types import RallyInterval

from modules.rally.evaluation.retention import offline_intervals, retained_time


def test_offline_finalizes_supported_sparse_flight_at_eof_without_extrapolation():
    observations = [dict(timestamp_ms=t, motion=True) for t in (100, 1100, 2500)]
    observations.append(dict(timestamp_ms=2600, motion=False))
    config = dict(gap_ms=1600, min_span_ms=2200, min_observations=3)
    result = offline_intervals(observations, config, eof_ms=2700)
    assert result == [RallyInterval(1, 100, 2500, 2700)]


def test_offline_gap_bound_prevents_gluing_separate_events():
    rows = [dict(timestamp_ms=t, motion=True) for t in (0, 1000, 2300, 5000, 6000, 7300)]
    config = dict(gap_ms=1600, min_span_ms=2200, min_observations=3)
    assert len(offline_intervals(rows, config, 7400)) == 2
    # A brief pair alone is not sufficient evidence, even at EOF.
    assert offline_intervals(rows[:2], config, 7400) == []


def test_retained_time_counts_unions_and_masks_only_non_target_excluded_time():
    truth = [RallyAnnotation(1, 10, 20, "verified")]
    predictions = [RallyInterval(1, 0, 15, 30), RallyInterval(2, 12, 25, 30)]
    result = retained_time(predictions, truth, [dict(range_ms=[0, 12])], 30)
    assert result["target_ms"] == result["retained_target_ms"] == 10
    assert result["ignored_ms"] == 10
    assert result["non_target_ms"] == 10
    assert result["retained_non_target_ms"] == 5
    assert result["target_retention"] == 1
    assert result["non_target_retention"] == 0.5
