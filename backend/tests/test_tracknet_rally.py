import math

from app.vision.rally_stream import RallyStream, TimestampedFrame
from app.vision.tracknet_rally import ShuttlePoint, ShuttleRallySegmenter


def flight(t, scale=1):
    phase = t % 2000
    x = 500 + 400 * (phase if phase <= 1000 else 2000 - phase) / 1000
    return ShuttlePoint(x * scale, 400 * scale, .95)


def run(points, scale=1):
    calls = []

    def predict(images):
        calls.append(len(images))
        return images

    candidate = ShuttleRallySegmenter(predict, width=1920 * scale, height=1080 * scale)
    stream = RallyStream(candidate)
    outputs = []
    for index, point in enumerate(points):
        outputs.extend(stream.process(TimestampedFrame(index, index * 40, point)))
    assert all(count == 3 for count in calls)
    return outputs, candidate


def test_flight_survives_brief_occlusion_and_held_ball_does_not_extend_end():
    points = []
    for t in range(0, 9000, 40):
        if 2000 <= t < 2880:
            points.append(ShuttlePoint(0, 0, .1))
        elif t <= 5000:
            points.append(flight(t))
        else:
            points.append(flight(5000))  # The held shuttle remains confidently visible.
    outputs, _ = run(points)
    assert len(outputs) == 1
    rally = outputs[0]
    assert rally.start_ms < 200
    assert 4800 <= rally.end_ms <= 5240
    assert 1600 <= rally.emitted_at_ms - rally.end_ms <= 1720


def test_short_ball_return_static_detection_and_single_jump_do_not_become_rallies():
    points = [flight(t) if t < 1600 else flight(1600) for t in range(0, 7000, 40)]
    points[120] = ShuttlePoint(1200, 700, .99)
    points[130] = ShuttlePoint(math.nan, 500, .99)
    outputs, _ = run(points)
    assert outputs == []


def test_separate_flights_are_emitted_once_and_eof_does_not_finish_a_rally():
    points = []
    for t in range(0, 15000, 40):
        if t < 5000:
            points.append(flight(t))
        elif 8500 <= t < 12000:
            points.append(flight(t - 8500))
        else:
            points.append(ShuttlePoint(0, 0, 0))
    outputs, _ = run(points)
    assert [row.rally_id for row in outputs] == [1, 2]
    assert outputs[0].end_ms < outputs[1].start_ms
    unfinished, candidate = run([flight(t) for t in range(0, 4000, 40)])
    assert unfinished == []
    assert candidate.active


def test_image_resolution_does_not_change_flight_boundaries():
    normal = [flight(t) if t < 5000 else ShuttlePoint(0, 0, 0) for t in range(0, 8000, 40)]
    small = [ShuttlePoint(row.x / 2, row.y / 2, row.confidence) for row in normal]
    assert run(normal)[0] == run(small, scale=.5)[0]


def test_candidate_scores_belong_to_their_own_regions_and_retain_weak_peaks():
    import numpy as np
    from app.vision.tracknet_rally import heatmap_candidates

    heatmap = np.zeros((12, 20), dtype=np.float32)
    heatmap[2:6, 2:6] = .7
    heatmap[8, 16] = .95
    heatmap[8, 8] = .4
    candidates = heatmap_candidates(heatmap, width=200, height=120)
    assert candidates['largest_region']['x'] == 40
    assert candidates['largest_region']['y'] == 40
    assert abs(candidates['largest_region']['confidence'] - .7) < 1e-6
    assert candidates['global_peak']['x'] == 160
    assert any(abs(p['confidence']-.4) < 1e-6 for p in candidates['peaks'])


def test_candidate_plateaus_are_not_duplicated_and_background_is_not_a_peak():
    import numpy as np
    from app.vision.tracknet_rally import heatmap_candidates

    heatmap = np.zeros((80, 80), dtype=np.float32)
    assert heatmap_candidates(heatmap, width=80, height=80)['peaks'] == []
    for i in range(64):
        heatmap[(i//8)*8+2, (i%8)*8+2] = .2+i*.01
    result = heatmap_candidates(heatmap, width=80, height=80)
    assert len(result['peaks']) == 32
    scores = [p['confidence'] for p in result['peaks']]
    assert scores == sorted(scores, reverse=True)
