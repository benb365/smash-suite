from dataclasses import replace

import pytest

from app.vision.candidate_rally import CandidateRallyConfig, candidate_motion, candidate_intervals


def row(frame_id, timestamp, x, scale=1):
    return dict(frame_id=frame_id, timestamp_ms=timestamp, peaks=[
        dict(x=1400*scale, y=200*scale, confidence=.99),  # Static false model response.
        dict(x=x*scale, y=500*scale, confidence=.7),
    ])


def small_config(**changes):
    return replace(CandidateRallyConfig(), static_fraction=None, center_weight=0,
                   min_track_points=3, min_track_ms=60, min_track_travel_px=20,
                   min_span_ms=60, min_observations=3, min_motion_fraction=0,
                   max_gap_ms=120, **changes)


def test_weaker_moving_candidate_survives_stronger_stationary_response():
    rows = [row(i, i*40, 500+i*30) for i in range(6)]
    config = small_config()
    motion = candidate_motion(rows, width=1920, config=config)
    assert all(r['motion'] for r in motion)
    assert [r['point']['x'] for r in motion] == [500+i*30 for i in range(6)]
    prediction = candidate_intervals(motion, eof_ms=400, config=config)[0]
    assert (prediction.start_ms, prediction.end_ms, prediction.emitted_at_ms) == (0, 200, 400)


def test_native_time_gaps_split_flights_without_inventing_coordinates():
    rows = [row(i, t, x) for i, (t, x) in enumerate(
        [(0, 500), (33, 523.1), (80, 556), (115, 580.5),
         (500, 700), (550, 735), (590, 763), (640, 798)])]
    config = small_config()
    motion = candidate_motion(rows, width=1920, config=config)
    predictions = candidate_intervals(motion, eof_ms=800, config=config)
    assert [(p.start_ms, p.end_ms) for p in predictions] == [(0, 115), (500, 640)]
    assert [r['timestamp_ms'] for r in motion] == [r['timestamp_ms'] for r in rows]
    small = [row(r['frame_id'], r['timestamp_ms'], r['peaks'][1]['x'], scale=.5) for r in rows]
    assert candidate_intervals(candidate_motion(small, width=960, config=config),
                               eof_ms=800, config=config) == predictions


def test_recurrence_rejects_a_fixed_landmark_but_not_a_moving_track():
    rows = [row(i, i*40, 400+i*40) for i in range(12)]
    motion = candidate_motion(rows, width=1920,
                              config=replace(small_config(), static_fraction=.6))
    assert all(r['point'] is None or r['point']['x'] != 1400 for r in motion)
    assert sum(r['motion'] for r in motion) >= 8


def test_impossible_single_jump_and_unknown_observations_do_not_form_a_flight():
    rows = [row(i, i*40, 500) for i in range(6)]
    rows[3]['peaks'][1]['x'] = 1100
    rows[4]['peaks'] = []
    motion = candidate_motion(rows, width=1920, config=small_config())
    assert not any(r['motion'] for r in motion)
    assert all(r['point'] is None for r in motion)
    assert candidate_intervals(motion, eof_ms=400, config=small_config()) == []


def test_three_point_trial_does_not_require_a_fourth_model_observation():
    rows = [row(i, t, 500+t) for i, t in enumerate((0, 33, 67))]
    assert all(r['motion'] for r in candidate_motion(rows, width=1920, config=small_config()))
    assert not any(r['motion'] for r in candidate_motion(
        rows, width=1920, config=replace(small_config(), min_track_points=4)))


def test_sparse_bursts_can_fail_density_even_when_they_can_be_grouped():
    motion = [dict(frame_id=i, timestamp_ms=t, motion=True) for i, t in enumerate((0, 40, 80, 1000, 1040, 1080))]
    config = replace(small_config(), max_gap_ms=1200, min_motion_fraction=.5)
    assert candidate_intervals(motion, eof_ms=1200, config=config) == []
    assert len(candidate_intervals(motion, eof_ms=1200,
                                   config=replace(config, min_motion_fraction=0))) == 1


def test_bad_source_times_or_early_eof_fail_explicitly():
    with pytest.raises(ValueError, match='timestamps'):
        candidate_motion([row(0, 40, 500), row(1, 40, 520)], width=1920, config=small_config())
    with pytest.raises(ValueError, match='EOF'):
        candidate_intervals([dict(timestamp_ms=100, motion=False)], eof_ms=90, config=small_config())
