from candidate_windows import interval_coverage, merge_candidates


def test_candidate_windows_clip_and_merge_touching_or_overlapping_points():
    samples = [
        {"timestamp_ms": 0, "confidence": .5},
        {"timestamp_ms": 2000, "confidence": .9},
        {"timestamp_ms": 4000, "confidence": .6},
        {"timestamp_ms": 2500, "confidence": .49},
    ]

    assert merge_candidates(samples, 4500, 1000) == [[0.0, 4500.0]]


def test_coverage_reports_complete_cover_and_exact_uncovered_gap():
    candidates = [[0.0, 2000.0], [3000.0, 4500.0]]

    result = interval_coverage([[500, 1500], [1500, 3500]], candidates)

    assert result == [
        {"index": 0, "start_ms": 500.0, "end_ms": 1500.0,
         "fully_covered": True, "uncovered_subintervals": []},
        {"index": 1, "start_ms": 1500.0, "end_ms": 3500.0,
         "fully_covered": False, "uncovered_subintervals": [[2000.0, 3000.0]]},
    ]
