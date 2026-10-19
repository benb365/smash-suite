"""Restore C short filtering and compare observed-point recovery at split ends.

Requires the saved C observations and historical helpers used by compare_c_recovery.
No model inference, annotation changes, fabricated positions, or export padding.
Run from the repository root with the SoloShuttlePose Python environment.
"""
import math
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

import compare_c_recovery as c

OUT = c.B / 'c-pause-boundaries-20261019'
CONFIG = dict(gap_ms=2400, region_points=8, span_ms=1600, observations=18,
              short='old', density_window_ms=2000, density=.4, internal_only=True)
SELECTED = 'tail_gap800_growth300'


def recover_end(prediction, candidates, flights, cap_ms, gap_ms, error_growth):
    """Follow real candidates from an already accepted, newly split end only.

    A short dropout widens the position gate; it never supplies a ball point.
    Reuse original confidence/static rejection and linear position prediction.
    Competing paths remain separate, and a one-point jump cannot extend an end.
    """
    from seeded_source import predict
    from shuttle_paths import quality

    end = prediction.end_ms
    seeds = []
    for flight in flights:
        points = [p for p in flight['moving'] if end - 600 <= p['t'] <= end]
        if flight['contacts'] and len(points) >= 5 and end - points[-1]['t'] <= 110:
            seeds.append((points, flight['flight_id']))
    if not seeds:
        return prediction, dict(old_end_ms=end, new_end_ms=end, reason='no_supported_seed')
    seeds.sort(key=lambda q: (q[0][-1]['t'], len(q[0])), reverse=True)
    seed, flight_id = seeds[0]
    active = [seed]
    finished = []
    for row in candidates:
        if not row or not end < row[0]['t'] <= cap_ms:
            continue
        now = row[0]['t']
        finished.extend(p for p in active if now - p[-1]['t'] > gap_ms)
        active = [p for p in active if now - p[-1]['t'] <= gap_ms]
        added = []
        for point in row:
            options = []
            for path in active:
                dt = (now - path[-1]['t']) / 1000
                if dt <= 0 or math.hypot(point['x'] - path[-1]['x'], point['y'] - path[-1]['y']) > 4000 * dt:
                    continue
                expected = predict(path, now, 'linear')
                error = float(np.linalg.norm(np.array([point['x'], point['y']]) - expected))
                if error <= 48 + max(0, dt - .034) * error_growth:
                    options.append(path + [point])
            added.extend(sorted(options, key=quality, reverse=True)[:3])
        # Keep bounded alternatives through a missing observation; never start
        # an unrelated path after the seed or repeatedly widen the time limit.
        active = sorted(active + added, key=quality, reverse=True)[:64]
    finished.extend(active)
    eligible = []
    for path in finished:
        extra = [p for p in path if p['t'] > end]
        if len(extra) >= 3 and extra[-1]['t'] - extra[0]['t'] >= 60:
            eligible.append(path)
    best = max(eligible, key=quality, default=seed)
    new_end = max(end, best[-1]['t'])
    return replace(prediction, end_ms=new_end), dict(
        old_end_ms=end, new_end_ms=new_end, seed_flight_id=flight_id,
        points=best, reason='observed_path' if new_end > end else 'no_supported_extension')


def main():
    a = c.module('c_pause_original', c.B / 'a1-c-parameters-20261017/replay.py')
    historical_path = c.R / 'docs/experiments/c2-recovery-and-d-transfer-20261019.json'
    historical = c.read(historical_path)
    variants = [dict(id='baseline', label='C原方案', results=[]),
                dict(id='previous', label='上一轮：放宽短过滤', results=[]),
                dict(id='split_only', label='恢复原短过滤，仅拆间歇', config=CONFIG, results=[])]
    for gap in (800, 1200):
        for growth in (150, 300, 450):
            variants.append(dict(id=f'tail_gap{gap}_growth{growth}',
                                 label=f'原短过滤＋尾部观测连接 {gap}/{growth}',
                                 config=dict(CONFIG, tail_gap_ms=gap,
                                             tail_error_growth_px_s=growth,
                                             tail_limit_ms=1600), results=[]))
    inputs = [historical_path]
    for case in c.cases():
        sample = case['sample']
        sid = sample['id']
        native, shifted = c.rows(case['native']), c.rows(case['shifted'])
        people, flights = c.rows(case['players']), c.read(case['flights'])
        original, _ = a.pipeline(native, shifted, people, flights)
        assert [asdict(p) for p in original] == case['old']['predictions']
        old = next(v for v in historical['variants'] if v['id'] == 'candidate')
        previous = next(r for r in old['results'] if r['sample_id'] == sid)
        raw = a.candidate_motion(shifted, width=1920, config=a.CandidateRallyConfig(**a.CONFIG))
        split, trace = c.c_predict(a, raw, shifted, people, flights, CONFIG)
        outer = a.candidate_intervals(a.gate(raw, 250, 1600, 8),
                                     eof_ms=shifted[-1]['timestamp_ms'],
                                     config=a.CandidateRallyConfig(**a.CONFIG))
        # Only new internal ends may change. Original end boundaries and every
        # short-event decision remain untouched. Labels do not choose the ends.
        internal = {}
        for i, p in enumerate(split):
            group = next((g for g in trace['grouped']
                          if g['start_ms'] <= p.start_ms < g['end_ms']
                          and abs(g['end_ms'] - p.end_ms) <= 4000), None)
            parent = next((q for q in outer if q.start_ms <= p.start_ms < q.end_ms), None)
            if group and parent and group['end_ms'] < parent.end_ms:
                cap = min(group['end_ms'] + 1600, parent.end_ms,
                          split[i + 1].start_ms if i + 1 < len(split) else sample['duration_ms'])
                internal[i] = cap
        candidates = a.observed_candidates(native, shifted[:len(native)])
        for v in variants:
            decisions = []
            if v['id'] == 'baseline':
                pred = original
            elif v['id'] == 'previous':
                pred = [a.RallyInterval(**p) for p in previous['predictions']]
            else:
                pred = list(split)
                if v['id'] != 'split_only':
                    for i, cap in internal.items():
                        pred[i], d = recover_end(pred[i], candidates, flights, cap,
                                                 v['config']['tail_gap_ms'],
                                                 v['config']['tail_error_growth_px_s'])
                        decisions.append(dict(rally_id=pred[i].rally_id, cap_ms=cap, **d))
            assert all(0 <= p.start_ms < p.end_ms <= sample['duration_ms'] for p in pred)
            assert all(p.end_ms < q.start_ms for p, q in zip(pred, pred[1:]))
            v['results'].append(dict(sample_id=sid, source_id=sample['source_id'],
                                     predictions=[asdict(p) for p in pred],
                                     internal_end_caps_ms=internal, end_recovery=decisions,
                                     **c.evaluate(pred, sample)))
        inputs.extend([c.R / sample['annotation'], case['native'], case['shifted'], case['players'], case['flights']])
        print('completed', sid, 'internal ends', internal, flush=True)
    for v in variants:
        v['summary'] = c.summarize(v['results'])
        print(v['id'], v['summary'], flush=True)
    next(v for v in variants if v['id'] == SELECTED)['label'] = '本轮：原短过滤＋尾部连接'
    code = [Path(__file__).resolve(), Path(c.__file__).resolve(), c.B / 'a1-c-parameters-20261017/replay.py']
    # Include imported historical helpers and actual scoring code, not just the
    # small driver, so a later change cannot silently reuse these results.
    import sys
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).suffix == '.py' and (
                Path(path).is_relative_to(c.R / 'backend') or Path(path).is_relative_to(c.B)):
            code.append(Path(path))
    result = dict(date='2026-10-19', status='C1_C2_tuning_original_short_filter',
                  selected_variant=SELECTED,
                  samples=[q['sample'] for q in c.cases()], variants=variants,
                  annotation_changed=False, model_inference=False, product_entry_changed=False,
                  input_sha256={str(p.relative_to(c.R)): c.sha(p) for p in inputs},
                  code_sha256={str(p.relative_to(c.R)): c.sha(p) for p in set(code)},
                  limits=['All five clips are tuning material, not independent acceptance.',
                          'Observed paths are candidate associations, not verified shuttle identity.',
                          'No output/export padding; recovered ends are actual observed timestamps.'])
    c.write(OUT / 'comparison.json', result)
    c.write(c.R / 'docs/experiments/c-pause-boundaries-20261019.json', result)
    # Change saved data, not the canonical viewer or its HTML. The historical
    # four-way C/D page remains available and retains its original predictions.
    data = c.read(c.OUT / 'review.json')
    data.update(title='C组：恢复原短过滤、拆开间歇并补回尾部',
                note='蓝色为本轮候选，灰色为C原方案，紫色为上一轮已否决候选；人工标注不变。尾部仅连接真实候选点，没有固定补时。C2短回合恢复原过滤，片尾真实终点未知。')
    data['tracks'] = [t for t in data['tracks'] if t['id'] != 'd_c_selected']
    data['tracks'].insert(3, dict(id='previous', label='上一轮：放宽短过滤', role='prediction'))
    next(t for t in data['tracks'] if t['id'] == 'candidate')['label'] = '本轮：原短过滤＋尾部连接'
    selected = next(v for v in variants if v['id'] == SELECTED)
    data['summary'] = [dict(label='C2 '+v['label']+'对打保留', value=f"{v['summary']['C2']['retention']:.2%}")
                       for v in (variants[0], selected)]
    for clip in data['clips']:
        sid = clip['id']
        clip['intervals'].pop('d_c_selected')
        clip['intervals']['previous'] = clip['intervals']['candidate']
        r = next(r for r in selected['results'] if r['sample_id'] == sid)
        clip['intervals']['candidate'] = [dict(id=str(p['rally_id']), start_ms=p['start_ms'], end_ms=p['end_ms'])
                                         for p in r['predictions']]
        clip['summary'] = [dict(label=v['label']+'对打保留',
                                value=f"{next(r for r in v['results'] if r['sample_id'] == sid)['retained_time']['target_retention']:.2%}")
                           for v in (variants[0], selected, variants[1])]
        if sid == 'C2':
            clip['issues'] = [dict(label='第4回合结尾：67.367延续到68.933秒', start_ms=65000, end_ms=71000),
                              dict(label='第3至5回合：间歇仍拆开', start_ms=22000, end_ms=90000)]
        elif sid == 'C1-02':
            clip['issues'] = [dict(label='三处新增内容已随原短过滤删除', start_ms=29000, end_ms=46000)]
        elif sid == 'C1-04':
            clip['issues'] = [dict(label='新增短输出已删除', start_ms=49000, end_ms=55000)]
    viewer = c.module('pause_fixed_viewer', c.R / '.agents/skills/review-video-results/scripts/review.py')
    viewer.prepare(data, OUT)
    c.write(OUT / 'review.json', data)


if __name__ == '__main__':
    main()
