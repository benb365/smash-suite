import math

import pytest

from modules.media.types import TimestampedFrame
from modules.rally.rally_stream import RallyStream
from modules.models.tracknet import ShuttlePoint
from modules.rally.tracknet_rally import ShuttleRallySegmenter
from modules.rally.scenarios.high import (
    TrajectoryConfig, TrajectoryRallySegmenter, analyze_flight, analyze_motion,
)


def replay(points, *, trajectory=True, config=None):
    cls = TrajectoryRallySegmenter if trajectory else ShuttleRallySegmenter
    candidate = cls(lambda frames: frames, width=1920, height=1080,
                    **({'config': config} if config else {}))
    stream, result = RallyStream(candidate), []
    for i, point in enumerate(points):
        result.extend(stream.process(TimestampedFrame(i, i*40, point)))
    return result, candidate


def high_clear(*, reentry_y=20, reentry_x=940, missing_until=2920):
    points = []
    for t in range(0, 9000, 40):
        if t <= 1000:
            p = ShuttlePoint(900, 500-.45*t, .95)
        elif t < missing_until:
            p = ShuttlePoint(0, 0, .05)
        elif t <= missing_until+2800:
            p = ShuttlePoint(reentry_x, reentry_y+.18*(t-missing_until), .95)
        else:
            p = ShuttlePoint(reentry_x, reentry_y+.18*2800, .95)
        points.append(p)
    return points


def test_direction_uses_source_time_and_preserves_resolution_scaling():
    points = [(t, ShuttlePoint(500+.2*t, 400-.4*t, .95)) for t in (0, 53, 121)]
    cfg = TrajectoryConfig()
    normal = analyze_motion(points, width=1920, config=cfg)
    small = analyze_motion([(t, ShuttlePoint(p.x/2, p.y/2, p.confidence)) for t,p in points],
                           width=960, config=cfg)
    assert normal.reliable
    assert normal.vx_px_s == pytest.approx(200)
    assert normal.vy_px_s == pytest.approx(-400)
    assert small == normal
    assert analyze_motion(points[:2], width=1920, config=cfg) is None
    assert analyze_motion([points[0], points[-1]], width=1920, config=cfg).reliable


def test_top_exit_recovers_short_front_group_without_changing_model_points():
    points = high_clear()
    original, _ = replay(points, trajectory=False)
    result, segmenter = replay(points)
    assert len(result) == 1
    assert result[0].start_ms < 200
    assert original[0].start_ms > 2900
    assert 5700 <= result[0].end_ms <= 5920
    assert any(e['type'] == 'top_reconnected' for e in segmenter.events)
    assert segmenter.flight_decisions[0]['classification'] == 'keep'
    assert 'connected_high_clear' in segmenter.flight_decisions[0]['reasons']


@pytest.mark.parametrize('reentry_y,reentry_x', [(600,940), (20,1700)])
def test_wrong_reentry_location_does_not_attach_to_top_exit(reentry_y,reentry_x):
    result, segmenter = replay(high_clear(reentry_y=reentry_y, reentry_x=reentry_x))
    assert result[0].start_ms > 2900
    assert not any(e['type'] == 'top_reconnected' for e in segmenter.events)


def test_top_wait_is_bounded_and_eof_does_not_confirm_a_rally():
    result, segmenter = replay(high_clear(missing_until=5000))
    assert not any(e['type'] == 'top_reconnected' for e in segmenter.events)
    assert any(e['type'] == 'top_wait_expired' for e in segmenter.events)
    assert not result  # Later flight has not ended before EOF.


def test_sparse_reentry_points_cannot_extend_end_without_direction_support():
    points = high_clear()
    for t in range(2920, 3160, 40):
        points[t//40] = ShuttlePoint(940, 20+.2*(t-2920), .95) if t in (2920,3120) else ShuttlePoint(0,0,0)
    # Batch processing also observes 3160/3200ms; inspect the earlier decision.
    _, waiting = replay(points[:81])
    row = next(r for r in waiting.last_diagnostics if r['timestamp_ms'] == 3120)
    assert row['valid'] and not row['motion']
    assert not any(e['type'] == 'top_reconnected' and e['timestamp_ms'] <= 3120 for e in waiting.events)


def rows_for(path):
    return [dict(timestamp_ms=t, x=path(t/1000)[0], y=path(t/1000)[1], valid=True)
            for t in range(0, 2400, 40)]


def stopped_tail(rows):
    return [dict(timestamp_ms=rows[-1]['timestamp_ms']+t, x=rows[-1]['x'], y=rows[-1]['y'], valid=True)
            for t in range(40, 400, 40)]


def test_natural_arc_is_not_a_return_and_missing_track_is_not_one_way():
    rows = rows_for(lambda t:(300+100*t, 600-400*t+200*t*t))
    result = analyze_flight(rows, width=1920, config=TrajectoryConfig(),
                            connected_high_clear=False, trailing_rows=stopped_tail(rows))
    assert result['classification'] == 'single_flight_candidate'
    assert result['return_candidates'] == []
    rows[25]['valid'] = rows[26]['valid'] = rows[27]['valid'] = False
    assert analyze_flight(rows, width=1920, config=TrajectoryConfig(),
                          connected_high_clear=False, trailing_rows=stopped_tail(rows))['classification'] == 'uncertain'


def test_sharp_return_has_support_on_both_sides_without_fixed_hit_regions():
    rows = rows_for(lambda t:(200+600*t if t<=1 else 800-600*(t-1), 400))
    result = analyze_flight(rows, width=1920, config=TrajectoryConfig(), connected_high_clear=False, trailing_rows=[])
    assert result['classification'] == 'keep'
    assert any(abs(r['timestamp_ms']-1000)<=40 for r in result['return_candidates'])
    assert all(r['available_at_ms'] > r['timestamp_ms'] for r in result['return_candidates'])


def test_single_bad_coordinate_does_not_become_a_return_or_complete_flight():
    rows = rows_for(lambda t:(300+100*t,400))
    rows[25]['x'] += 1000
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,
                            trailing_rows=stopped_tail(rows))
    assert result['classification'] == 'uncertain'
    assert result['return_candidates'] == []


def test_speed_change_without_direction_reversal_does_not_veto_one_way():
    rows = rows_for(lambda t:(200+200*t if t<=1 else 400+1200*(t-1),400))[:50]
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(turn_jump_px_s=700),connected_high_clear=False,
                            trailing_rows=stopped_tail(rows))
    assert result['classification'] == 'single_flight_candidate'
    assert any(r['kind'] == 'speed_change' for r in result['motion_changes'])


@pytest.mark.parametrize('threshold,expected_return', [(500,True),(700,False)])
def test_return_requires_the_configured_velocity_change(threshold,expected_return):
    rows = rows_for(lambda t:(200+300*t if t<=1 else 500-300*(t-1),400))
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(turn_jump_px_s=threshold),
                            connected_high_clear=False,trailing_rows=[])
    assert bool(result['return_candidates']) is expected_return


def test_explicit_single_flight_filter_needs_stop_but_not_static_launch():
    points = [ShuttlePoint(300+max(0,min(t-400,3000))*.2,400,.95) for t in range(0,8000,40)]
    kept, _ = replay(points)
    filtered, segmenter = replay(points, config=TrajectoryConfig(filter_single_flight=True))
    assert len(kept) == 1
    assert filtered == []
    assert segmenter.flight_decisions[0]['settled_after_flight']
    assert segmenter.flight_decisions[0]['filtered']
    # Starting in flight no longer requires observing a shuttle at rest first.
    clipped = points[20:]
    assert replay(clipped, config=TrajectoryConfig(filter_single_flight=True))[0] == []


def test_a102_downward_points_cannot_become_fitted_reversal():
    # Actual 79.84–80.16s coordinates: quadratic extrapolation previously
    # invented an upward incoming velocity at 80.00s despite downward motion.
    coords = [(935.625,571.875),(933.75,611.25),(931.875,650.625),(931.875,648.75),
              (928.125,733.125),(926.25,772.5),(922.5,813.75),(922.5,828.75),(924.375,817.5)]
    rows = [dict(timestamp_ms=79840+i*40,x=x,y=y,valid=True) for i,(x,y) in enumerate(coords)]
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,trailing_rows=[])
    assert result['return_candidates'] == []
    assert result['motion_changes'][0]['kind'] == 'speed_change'
    assert result['motion_changes'][0]['observed_cosine'] > 0


def test_small_contact_deflection_is_not_a_sustained_return():
    rows = rows_for(lambda t:(200+600*t if t<=1 else 800-600*min(t-1,.1),400))
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,
                            trailing_rows=stopped_tail(rows))
    assert result['return_candidates'] == []
    assert any(r['kind'] == 'local_reversal' for r in result['motion_changes'])
    assert result['classification'] == 'uncertain'


def test_missing_launch_observations_do_not_require_95_percent_coverage():
    rows = rows_for(lambda t:(300+200*t,400))
    for row in rows[:10]:
        row['valid'] = False
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,
                            trailing_rows=stopped_tail(rows))
    assert result['valid_fraction'] < .95
    assert result['classification'] == 'single_flight_candidate'


def test_small_terminal_reversal_followed_by_stop_does_not_veto_single_flight():
    # Quantized descent/landing pattern from A1-03, including repeated points.
    ys = [480,478.125,541.875,538.125,607.5,607.5,675,673.125,712.5,710.625,
          701.25,699.375,699.375,699.375,706.875,708.75,716.25,716.25,723.75]
    rows = [dict(timestamp_ms=i*40,x=400,y=y,valid=True) for i,y in enumerate(ys)]
    result = analyze_flight(rows,width=1920,config=TrajectoryConfig(turn_jump_px_s=700),connected_high_clear=False,
                            trailing_rows=stopped_tail(rows))
    assert result['return_candidates'] == []
    assert result['classification'] == 'single_flight_candidate'
    assert any(r['kind'] == 'small_end_deflection' for r in result['motion_changes'])
    # The stronger default can reject this weak jitter before it becomes a
    # change record; it must still permit the same single-flight decision.
    assert analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,
                          trailing_rows=stopped_tail(rows))['classification'] == 'single_flight_candidate'


def test_analysis_handles_empty_and_invalid_observations_without_fake_flights():
    for rows in ([],[dict(timestamp_ms=t,x=0,y=0,valid=False) for t in range(0,1000,40)]):
        result = analyze_flight(rows,width=1920,config=TrajectoryConfig(),connected_high_clear=False,trailing_rows=[])
        assert result['classification'] == 'uncertain'
        assert result['return_candidates'] == [] and result['flight_runs'] == []


def test_uncertain_short_deletion_is_explicit_and_high_clear_is_protected():
    points = [ShuttlePoint(300+max(0,min(t-400,3000))*.2,400,.95) for t in range(0,8000,40)]
    for t in range(1400,1800,40):
        points[t//40] = ShuttlePoint(0,0,.05)
    kept, candidate = replay(points,config=TrajectoryConfig(filter_single_flight=True))
    assert kept and candidate.flight_decisions[0]['uncertain_short_candidate']
    deleted, candidate = replay(points,config=TrajectoryConfig(filter_single_flight=True,filter_uncertain_short=True))
    assert deleted == [] and candidate.flight_decisions[0]['filtered']
    # Even an unusually generous short-duration limit must not delete a
    # connected high-clear rally; short/missing evidence cannot override it.
    kept, candidate = replay(high_clear(),config=TrajectoryConfig(filter_single_flight=True,
                            filter_uncertain_short=True,short_event_ms=10000))
    assert kept and not candidate.flight_decisions[0]['filtered']
    kept, _ = replay(points,config=TrajectoryConfig(filter_uncertain_short=True,short_event_ms=1000))
    assert kept


def test_invalid_trajectory_config_is_rejected():
    with pytest.raises(ValueError):
        TrajectoryConfig(top_fraction=.5)
    with pytest.raises(ValueError):
        TrajectoryConfig(high_clear_gap_ms=1000)
    with pytest.raises(ValueError):
        TrajectoryConfig(reentry_x_fraction=math.nan)
    with pytest.raises(ValueError):
        TrajectoryConfig(return_support_ms=40,track_gap_ms=120)
