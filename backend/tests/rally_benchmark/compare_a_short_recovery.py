"""A1/A2 short-candidate experiment on saved coordinates, with unchanged labels."""
import copy
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'models/SoloShuttlePose/.runtime/a-short-recovery-20261018'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests/rally_benchmark')]
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions
from app.vision.rally_stream import RallyInterval
from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
from compare_trajectory import replay_points
from compare_m1 import retained_time

spec = importlib.util.spec_from_file_location('viewer', ROOT / '.agents/skills/review-video-results/scripts/review.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)

def read(path):
    return json.loads((ROOT / path).read_text())

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def write(path, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def ranges(rows):
    return [(r.start_ms, r.end_ms) for r in rows]

def duration(rows):
    return viewer.duration(rows)

def intersection(a, b):
    return duration(viewer.intersection(a, b))

def compare_saved(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for k in expected:
            compare_saved(actual[k], expected[k])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            compare_saved(a, b)
    elif isinstance(expected, float):
        assert abs(actual - expected) <= 1e-8, (actual, expected)
    else:
        assert actual == expected, (actual, expected)

# A small, declared grid; all six clips are development material for this trial.
# This rule only rescues uncertain candidates. It cannot establish a real hit,
# alter the original boundary, or override the existing single-flight deletion.
policies = [dict(id='current', label='原过滤', mode='current'),
            dict(id='keep_uncertain', label='保留所有不确定短片段', mode='keep_uncertain')]
policies += [dict(id=f'quality_{int(fraction*100)}_{gap}',
                 label=f'有效球点至少{fraction:.0%}，最长缺失不超过{gap}毫秒',
                 mode='quality', min_valid_fraction=fraction, max_gap_ms=gap)
             for fraction in (.7, .8, .9) for gap in (240, 480, 960)]

a1_path = 'docs/experiments/m1-a-return-threshold-20261016.json'
a2_path = 'models/SoloShuttlePose/.runtime/a2-current-algorithm-20261018/clean-windows/comparison.json'
a1, a2 = read(a1_path), read(a2_path)
cases = []
for old in a1['results']:
    sample = copy.deepcopy(old['sample'])
    assert sha(sample['annotation']) == sample['annotation_sha256']
    prior = next(v for v in old['variants'] if v['name'] == 'trajectory-uncertain-short-trial')
    run = read(old['run_result'])
    cache = Path(old['run_result']).parent / 'flight-diagnostics.jsonl'
    rows = [json.loads(line) for line in cache.read_text().splitlines()]
    cases.append(dict(sample=sample, cache=str(cache), rows=rows,
                      media_offset_ms=run['input']['first_pts_ms'], config=prior['config'],
                      saved_decisions=prior['flight_decisions'], saved_events=prior['events'],
                      saved_predictions=[d['interval'] for d in prior['flight_decisions'] if not d['filtered']]))
for path, expected in a2['sha256'].items():
    assert sha(path) == expected, path
a2_cache = next(p for p in a2['sha256'] if p.endswith('tracknet-points.jsonl'))
a2_rows = [json.loads(line) for line in Path(a2_cache).read_text().splitlines()]
for window in a2['windows']:
    cid = window['id']
    sample = dict(id=cid, source_id='A2', duration_ms=window['duration_ms'],
                  video=window['video'], source_original_window_ms=window['source_original_window_ms'],
                  annotation=f'datasets/badminton-v1/annotations/reviewed/rally/reserve-{cid.lower()}-20261018/full-v1.json')
    first, last = window['source_frame_start'], window['source_frame_end_exclusive']
    offset = window['clip_time_start_ms']
    rows = [dict(r, frame_id=i, timestamp_ms=r['timestamp_ms']-offset,
                 available_at_ms=r['available_at_ms']-offset)
            for i, r in enumerate(a2_rows[first:last])]
    assert rows[0]['timestamp_ms'] == 0 and first % 3 == last % 3 == 0
    cases.append(dict(sample=sample, cache=a2_cache, rows=rows, media_offset_ms=0,
                      config=a2['config'], saved_decisions=window['flight_decisions'],
                      saved_events=window['events'], saved_predictions=window['predictions']))

assert all(c['config'] == cases[0]['config'] for c in cases)
results = []
for case in cases:
    sample = case['sample']
    seg = TrajectoryRallySegmenter(lambda p:p, width=1920, height=1080,
                                  config=TrajectoryConfig(**case['config']))
    baseline, _, replay_wall = replay_points(case['rows'], seg)
    assert [asdict(p) for p in baseline] == case['saved_predictions']
    compare_saved(seg.flight_decisions, case['saved_decisions'])
    compare_saved(seg.events, case['saved_events'])
    # Check that choosing the saved candidates is equivalent to the existing
    # switch, rather than accidentally changing segmentation state upstream.
    unfiltered = TrajectoryRallySegmenter(lambda p:p, width=1920, height=1080,
                                         config=TrajectoryConfig(**dict(case['config'], filter_uncertain_short=False)))
    no_unknown_filter, _, _ = replay_points(case['rows'], unfiltered)
    expected = [d['interval'] for d in seg.flight_decisions if d['classification'] != 'single_flight_candidate']
    assert [asdict(p) for p in no_unknown_filter] == expected
    truth = load_rally_annotations(ROOT / sample['annotation'])
    exclusions = load_rally_exclusions(ROOT / sample['annotation'])
    targets = [t for t in truth if t.review_status == 'verified']
    variants = []
    for policy in policies:
        predictions, rescued = [], []
        for d in seg.flight_decisions:
            keep = not d['filtered']
            if d['filtered'] and d['uncertain_short_candidate']:
                if policy['mode'] == 'keep_uncertain':
                    keep = True
                elif policy['mode'] == 'quality':
                    keep = (d['valid_fraction'] >= policy['min_valid_fraction']
                            and d['max_valid_gap_ms'] is not None
                            and d['max_valid_gap_ms'] <= policy['max_gap_ms'])
            if keep:
                predictions.append(RallyInterval(**d['interval']))
                if d['filtered']:
                    rescued.append(d['interval']['rally_id'])
        metrics = evaluate_rallies(predictions, truth, excluded_events=exclusions)
        times = retained_time(predictions, truth, exclusions, sample['duration_ms'])
        subsets = {}
        for threshold in (3000, 5000):
            selected = [t for t in targets if t.end_ms-t.start_ms > threshold]
            total = duration(ranges(selected))
            retained = intersection(ranges(predictions), ranges(selected))
            subsets[str(threshold)] = dict(count=len(selected), target_ms=total, retained_ms=retained,
                wholly_missed_ids=[t.rally_id for t in selected if not intersection(ranges(predictions), ranges([t]))])
        details = [dict(rally_id=t.rally_id, start_ms=t.start_ms, end_ms=t.end_ms,
                        retained_ms=intersection(ranges(predictions), ranges([t])),
                        wholly_missed=not intersection(ranges(predictions), ranges([t]))) for t in targets]
        outside = duration(ranges(predictions)) - intersection(ranges(predictions), ranges(targets))
        variants.append(dict(id=policy['id'], predictions=[asdict(p) for p in predictions],
                             rescued_prediction_ids=rescued, metrics=metrics, retained_time=times,
                             retained_outside_target_ms=outside, subsets=subsets, rally_details=details))
    results.append(dict(sample=sample, annotation_sha256=sha(sample['annotation']), cache=case['cache'],
                        cache_sha256=sha(case['cache']), media_offset_ms=case['media_offset_ms'],
                        baseline_reproduced=True, keep_uncertain_switch_reproduced=True,
                        coordinate_replay_wall_s=replay_wall, decisions=seg.flight_decisions,
                        variants=variants))
    print(sample['id'], 'baseline and switch exactly reproduced', flush=True)

summaries = []
for policy in policies:
    aggregate = dict(id=policy['id'], groups={})
    for group in ('A1', 'A2'):
        vv = [next(v for v in r['variants'] if v['id'] == policy['id']) for r in results if r['sample']['source_id'] == group]
        totals = {k:sum(v['retained_time'][k] for v in vv) for k in ('target_ms','retained_target_ms','retained_non_target_ms')}
        totals['retained_fraction'] = totals['retained_target_ms']/totals['target_ms']
        totals.update({k:sum(v['metrics'][k] for v in vv) for k in ('truth_count','missed_rally_count','false_positive_count','false_split_count','false_merge_count')})
        totals.update(retained_outside_target_ms=sum(v['retained_outside_target_ms'] for v in vv),
                      **{k:sum(v['metrics']['boundary_acceptance'][k] for v in vv) for k in ('start_acceptable_count', 'end_acceptable_count', 'both_acceptable_count')})
        totals['subsets'] = {}
        for threshold in ('3000', '5000'):
            subsets = [v['subsets'][threshold] for v in vv]
            total = sum(s['target_ms'] for s in subsets)
            totals['subsets'][threshold] = dict(count=sum(s['count'] for s in subsets),
                target_ms=total, retained_ms=sum(s['retained_ms'] for s in subsets),
                retained_fraction=sum(s['retained_ms'] for s in subsets)/total,
                missed_count=sum(len(s['wholly_missed_ids']) for s in subsets))
        aggregate['groups'][group] = totals
    summaries.append(aggregate)
    print(policy['id'], [(g, round(s['retained_fraction']*100,2), s['missed_rally_count'], s['retained_outside_target_ms']) for g,s in aggregate['groups'].items()], flush=True)

report = dict(date='2026-10-18', status='A1_A2_development_comparison_not_independent_acceptance',
              model_rerun=False, annotation_changed=False, base_config=cases[0]['config'],
              policies=policies, results=results, summaries=summaries,
              source_reports={p:sha(p) for p in (a1_path, a2_path)},
              current_code_sha256={p:sha(p) for p in ('backend/app/vision/trajectory_rally.py','backend/app/vision/tracknet_rally.py','backend/app/vision/rally_eval.py','backend/tests/rally_benchmark/compare_trajectory.py')},
              script=str(Path(__file__).relative_to(ROOT)), script_sha256=sha(Path(__file__)),
              historical_A1_code_differences=[dict(path=p, historical_sha256=h, current_sha256=sha(p)) for p,h in a1['code_sha256'].items() if sha(p) != h],
              limits=['同一规则用于A1四段与A2两段；六段都用于本次改进，不作独立验收。',
                      '只改变不确定短片段是否保留；原始候选、起止、高球连接和较明确单向飞行过滤不变。',
                      '高有效球点比例、较短缺失不证明发生回击，也可能保留还球。',
                      'A2确认的是所列条目，标注外时长与额外输出用于诊断。',
                      '复用历史球点；一帧未完成模型分组仍不补造，回放耗时不是模型性能。'])
report['candidate_policy'] = 'quality_80_480'
report['candidate_status'] = '用于比较保住对打与增加还球的取舍；未替换正式入口或原方案。'
report['candidate_selection_reason'] = '80%有效球点、最长间隔480毫秒可找回三个A2回合，同时保留A1一段3.92秒还球；并非唯一最优门槛，70%/480和80%/960在本批输出相同。'
write(OUT / 'comparison.json', report)
write('docs/experiments/a1-a2-short-filter-20261018.json', report)

# Feed saved intervals to the canonical viewer; no experiment-specific HTML.
shown = ['quality_80_480', 'current', 'keep_uncertain', 'quality_80_240']
labels = ['保住较完整短片段（80%，480毫秒）', '原过滤', '保留所有不确定短片段', '更严格的缺失限制（80%，240毫秒）']
page = dict(schema_version=1, title='A组：找回被误删的对打，会增加多少还球',
    note='直接复用已确认标注，无需重新人审。蓝色为候选方案。橙色事件允许不计分，但保留它仍会增加成片内容；下面单独报告这项代价。',
    primary_track=shown[0], tracks=[dict(id='truth', label='已确认正常回合', role='truth')]
        + [dict(id=i, label=label, role='prediction') for i,label in zip(shown,labels)]
        + [dict(id='excluded', label='已确认可排除事件', role='excluded')], clips=[],
    summary=[dict(label='A2对打时间保留', value='72.88% → 95.83%', note='三个整段漏掉的回合均找回，起止同时合格仍0/6'),
             dict(label='A1新增还球', value='3.92秒', note='第3段115.400–119.320秒，已确认还球，不隐去此代价'),
             dict(label='A2新增标注外内容', value='0.40秒', note='总量2.12 → 2.52秒；A2标注外仅作诊断')])
for result in results:
    sample = result['sample']
    truth = load_rally_annotations(ROOT / sample['annotation'])
    exclusions = load_rally_exclusions(ROOT / sample['annotation'])
    vv = {v['id']:v for v in result['variants']}
    def display(rows):
        return [dict(id=str(p['rally_id']), start_ms=p['start_ms'], end_ms=p['end_ms']) for p in rows]
    intervals = {key:display(vv[key]['predictions']) for key in shown}
    intervals['truth'] = [dict(id=str(t.rally_id), label=f'第{t.rally_id}回合', start_ms=t.start_ms,
                               end_ms=t.end_ms, review_status=t.review_status) for t in truth if t.review_status=='verified']
    intervals['excluded'] = [dict(id=str(e['event_id']), start_ms=e['range_ms'][0], end_ms=e['range_ms'][1],
                                  review_status=e['review_status']) for e in exclusions]
    before, after = vv['current'], vv[shown[0]]
    issues = [dict(label='重新保留的片段：正常对打或还球见时间轴',
                   start_ms=max(0,p['start_ms']-2000), end_ms=min(sample['duration_ms'],p['end_ms']+2000))
              for p in after['predictions'] if p['rally_id'] in after['rescued_prediction_ids']]
    page['clips'].append(dict(id=sample['id'], title=sample['id'], video=str((ROOT/sample['video']).resolve()),
        duration_ms=sample['duration_ms'], media_offset_ms=result['media_offset_ms'],
        note='所有时间为本段内时间。正式起点可提前1.5秒、终点可延后1.5秒；向内裁切不合格。标注和原始候选起止未改。',
        summary=[dict(label='对打保留',value=f"{before['retained_time']['retained_target_ms']/before['retained_time']['target_ms']:.2%} → {after['retained_time']['retained_target_ms']/after['retained_time']['target_ms']:.2%}"),
                 dict(label='整回合漏掉',value=f"{before['metrics']['missed_rally_count']} → {after['metrics']['missed_rally_count']}"),
                 dict(label='标注外保留（包括排除事件）', value=f"{before['retained_outside_target_ms']/1000:.2f} → {after['retained_outside_target_ms']/1000:.2f}秒")],
        intervals=intervals, issues=issues))
viewer.prepare(page, OUT)
write(OUT/'review.json', page)
print('Fixed viewer data validated:', OUT/'review.json', flush=True)
