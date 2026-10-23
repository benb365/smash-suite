from copy import deepcopy

from modules.trajectory.constraints import constrain_shots


def _shot(rally, shot_id, start, end, kind="predicted_landing", start_ms=0):
    return {
        "rally_id": rally,
        "shot_id": shot_id,
        "start_ms": start_ms,
        "end_ms": start_ms + 100,
        "start_xy": start,
        "end_xy": end,
        "end_kind": kind,
    }


def _track(timestamp, **players):
    return {
        "timestamp_ms": timestamp,
        "players": [dict(side=side, xy=xy) for side, xy in players.items()],
    }


def test_court_bounds_include_lines_and_valid_opposite_side_arrow_is_unchanged():
    shots = [
        _shot(1, 1, [0, 0], [5.18, 13.4]),
        _shot(1, 2, [5.18, 13.4], [0, 0], start_ms=100),
    ]
    original = deepcopy(shots)

    result = constrain_shots(shots)

    assert result == original
    assert shots == original


def test_same_side_or_out_of_court_end_uses_next_real_hit_after_unknown_gap():
    shots = [
        _shot(1, 1, [2, 2], [7, 12]),
        _shot(1, 2, None, None, "unresolved", 100),
        _shot(1, 3, [3, 10], None, "unresolved", 200),
    ]

    result = constrain_shots(shots)

    assert result[0]["end_xy"] == [3.0, 10.0]
    assert result[0]["end_kind"] == "next_hit"
    diagnostic = result[0]["diagnostics"]["court_constraint"]
    assert diagnostic["action"] == "replace_end_with_next_hit"
    assert diagnostic["original_end_xy"] == [7, 12]
    assert diagnostic["original_end_kind"] == "predicted_landing"
    assert result[1]["end_kind"] == "unresolved"
    assert result[2]["end_xy"] is None


def test_in_court_same_side_end_is_replaced_with_next_hit():
    shots = [
        _shot(1, 1, [2, 2], [3, 4]),
        _shot(1, 2, [3, 10], None, "unresolved", 100),
    ]

    result = constrain_shots(shots)

    assert result[0]["end_kind"] == "next_hit"
    assert result[0]["end_xy"] == [3.0, 10.0]
    assert result[0]["diagnostics"]["court_constraint"]["reason"] == [
        "end_not_on_opposite_net_side"
    ]


def test_net_line_is_not_a_side_and_failed_replacement_hides_arrow():
    shots = [
        _shot(1, 1, [2, 6.7], [3, 10]),
        _shot(1, 2, [2, 6.7], None, "unresolved", 100),
    ]

    result = constrain_shots(shots)

    assert result[0]["end_kind"] == "unresolved"
    assert result[0]["end_xy"] is None
    assert result[0]["diagnostics"]["court_constraint"]["replacement_rejection_reasons"] == [
        "start_on_net_line", "end_not_on_opposite_net_side"
    ]


def test_outside_start_hides_arrow_even_if_next_hit_is_a_valid_opposite_point():
    shots = [
        _shot(1, 1, [5.19, 2], [1, 3]),
        _shot(1, 2, [2, 10], None, "unresolved", 100),
    ]

    result = constrain_shots(shots)

    assert result[0]["end_kind"] == "unresolved"
    assert result[0]["end_xy"] is None
    diagnostic = result[0]["diagnostics"]["court_constraint"]
    assert diagnostic["reason"] == ["start_out_of_court", "end_not_on_opposite_net_side"]
    assert diagnostic["replacement_rejection_reasons"] == ["start_out_of_court"]


def test_last_real_hit_is_exempt_even_with_trailing_unknown_segment():
    shots = [
        _shot(1, 1, [2, 2], [3, 4]),
        _shot(1, 2, [4, 12], [8, 15], start_ms=100),
        _shot(1, 3, None, None, "unresolved", 200),
    ]
    final_original = deepcopy(shots[1])

    result = constrain_shots(shots)

    assert result[1] == final_original
    assert result[0]["end_kind"] == "next_hit"
    assert result[0]["end_xy"] == [4.0, 12.0]


def test_single_hit_rally_is_naturally_exempt():
    shots = [_shot(1, 1, [7, 1], [8, 15])]

    assert constrain_shots(shots) == shots


def test_real_unresolved_last_hit_does_not_exempt_previous_invalid_arrow():
    shots = [
        _shot(1, 1, [2, 2], [3, 4]),
        _shot(1, 2, [2, 4], None, "unresolved", 100),
    ]

    result = constrain_shots(shots)

    assert result[0]["end_kind"] == "unresolved"
    assert result[0]["end_xy"] is None
    assert result[1]["end_kind"] == "unresolved"


def test_original_unresolved_is_not_revived_and_constraint_is_copy_idempotent():
    shots = [
        _shot(1, 1, [2, 2], None, "unresolved"),
        _shot(1, 2, [2, 10], [3, 3], start_ms=100),
    ]
    original = deepcopy(shots)

    once = constrain_shots(shots)
    twice = constrain_shots(once)

    assert shots == original
    assert once == twice
    assert once[0]["end_kind"] == "unresolved"
    assert once[0]["end_xy"] is None


def test_invalid_start_uses_exact_same_side_player_and_preserves_source_diagnostics():
    shots = [
        _shot(1, 1, [5.4, 11], [1, 2], start_ms=120),
        _shot(1, 2, [1, 2], None, "unresolved", 300),
    ]
    shots[0]["diagnostics"] = {"hit_side": "near", "start_source": "fitted_racket_contact_projection"}

    result = constrain_shots(shots, [_track(120, near=[2.1, 10.2], far=[4.0, 2.0])])

    constrained = result[0]
    assert constrained["start_xy"] == [2.1, 10.2]
    assert constrained["end_xy"] == [1, 2]
    assert constrained["diagnostics"]["start_source"] == "player_track_exact"
    constraint = constrained["diagnostics"]["court_constraint"]
    assert constraint["original_start_xy"] == [5.4, 11]
    assert constraint["original_start_source"] == "fitted_racket_contact_projection"
    assert constraint["start_estimate"] == {"xy": [2.1, 10.2], "method": "exact", "source_times_ms": [120.0]}
    assert constraint["action"] == "keep_after_start_repair"
    assert shots[0]["start_xy"] == [5.4, 11]


def test_invalid_start_uses_bounded_same_side_interpolation():
    shots = [
        _shot(1, 1, [3, 10], [2, 12], start_ms=100),
        _shot(1, 2, [2, 2], None, "unresolved", 200),
    ]
    shots[0]["diagnostics"] = {"hit_side": "far", "start_source": "player_foot_proxy"}
    tracks = [
        _track(0, far=[1, 2], near=[4, 11]),
        _track(200, far=[3, 4], near=[4, 10]),
    ]

    result = constrain_shots(shots, tracks)

    assert result[0]["start_xy"] == [2.0, 3.0]
    estimate = result[0]["diagnostics"]["court_constraint"]["start_estimate"]
    assert estimate["method"] == "interpolated"
    assert estimate["source_times_ms"] == [0.0, 200.0]


def test_start_estimation_never_crosses_sides_or_extrapolates_or_exceeds_220ms():
    shots = [_shot(1, 1, [2, 3], [2, 2], start_ms=100), _shot(1, 2, [2, 2], None, "unresolved", 200)]
    shots[0]["diagnostics"] = {"hit_side": "near"}
    for tracks in (
        [_track(0, far=[2, 10]), _track(200, far=[2, 11])],
        [_track(0, near=[2, 10])],
        [_track(-121, near=[2, 10]), _track(321, near=[2, 11])],
    ):
        result = constrain_shots(shots, tracks)
        assert result[0]["end_kind"] == "unresolved"
        assert result[0]["start_xy"] == [2, 3]
        assert result[0]["diagnostics"]["court_constraint"]["action"] == "hide_arrow"


def test_start_repair_then_next_hit_replacement_or_hiding():
    shots = [
        _shot(1, 1, [5.3, 10], [2, 12], start_ms=100),
        _shot(1, 2, [3, 2], None, "unresolved", 200),
    ]
    shots[0]["diagnostics"] = {"hit_side": "near", "start_source": "fitted_racket_contact_projection"}
    repaired = constrain_shots(shots, [_track(100, near=[2, 10])])
    assert repaired[0]["start_xy"] == [2, 10]
    assert repaired[0]["end_xy"] == [3.0, 2.0]
    assert repaired[0]["end_kind"] == "next_hit"
    assert repaired[0]["diagnostics"]["court_constraint"]["start_repaired"] is True

    outside_tracks = [_track(100, near=[5.3, 10])]
    hidden = constrain_shots(shots, outside_tracks)
    assert hidden[0]["end_xy"] is None
    assert hidden[0]["end_kind"] == "unresolved"


def test_next_final_hit_player_position_can_replace_invalid_fitted_start_without_changing_final():
    shots = [
        _shot(1, 1, [2, 2], [2, 5], start_ms=100),
        _shot(1, 2, [6, 10], [7, 15], "predicted_landing", 200),
    ]
    shots[0]["diagnostics"] = {"hit_side": "far"}
    shots[1]["diagnostics"] = {"hit_side": "near", "start_source": "fitted_racket_contact_projection"}
    final_before = deepcopy(shots[1])
    tracks = [_track(200, near=[3, 10])]

    result = constrain_shots(shots, tracks)

    assert result[0]["end_xy"] == [3.0, 10.0]
    assert result[0]["end_kind"] == "next_hit"
    assert result[0]["diagnostics"]["court_constraint"]["replacement_source"] == "next_hit_player_track_exact"
    assert result[1] == final_before


def test_already_valid_start_is_preserved_and_processed_output_is_idempotent():
    shots = [
        _shot(1, 1, [2, 3], [2, 10]),
        _shot(1, 2, [2, 10], [8, 15], "predicted_landing", 100),
    ]
    shots[0]["diagnostics"] = {"hit_side": "far", "start_source": "fitted_racket_contact_projection"}
    original_start = deepcopy(shots[0]["start_xy"])

    once = constrain_shots(shots, [_track(0, far=[4, 2]), _track(100, near=[2, 10])])
    twice = constrain_shots(once)

    assert once == twice
    assert once[0]["start_xy"] == original_start
    assert once[0]["end_kind"] == "predicted_landing"
