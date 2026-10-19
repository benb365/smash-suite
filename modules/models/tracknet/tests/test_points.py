def test_candidate_scores_belong_to_their_own_regions_and_retain_weak_peaks():
    import numpy as np
    from modules.models.tracknet import heatmap_candidates

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
    from modules.models.tracknet import heatmap_candidates

    heatmap = np.zeros((80, 80), dtype=np.float32)
    assert heatmap_candidates(heatmap, width=80, height=80)['peaks'] == []
    for i in range(64):
        heatmap[(i//8)*8+2, (i%8)*8+2] = .2+i*.01
    result = heatmap_candidates(heatmap, width=80, height=80)
    assert len(result['peaks']) == 32
    scores = [p['confidence'] for p in result['peaks']]
    assert scores == sorted(scores, reverse=True)
