#!/usr/bin/env python3
"""Replay existing A1 coordinates causally; all A1 clips are now diagnostic data."""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions, _summary
from app.vision.rally_stream import RallyStream, TimestampedFrame
from app.vision.tracknet_rally import FlightConfig, ShuttlePoint, ShuttleRallySegmenter
from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
from compare_m1 import retained_time, sha


def replay_points(rows, segmenter):
    stream, predictions, diagnostics = RallyStream(segmenter), [], []
    tick = time.perf_counter()
    for row in rows:
        point = ShuttlePoint(row['x'], row['y'], row['confidence'])
        predictions.extend(stream.process(TimestampedFrame(row['frame_id'], row['timestamp_ms'], point)))
        diagnostics.extend(segmenter.last_diagnostics)
    return predictions, diagnostics, time.perf_counter()-tick


def summarize_results(results):
    summaries=[]
    for name in [v['name'] for v in results[0]['variants']]:
        variants=[next(v for v in s['variants'] if v['name']==name) for s in results]
        metrics=[v['metrics'] for v in variants]
        counts={k:sum(m[k] for m in metrics) for k in ('truth_count','prediction_count','missed_rally_count',
                'false_positive_count','false_split_count','false_merge_count')}
        matches=[r for m in metrics for r in m['matches']]
        acceptance=dict(truth_count=counts['truth_count'],matched_count=len(matches))
        for b in ('start','end','both'):
            count=sum(m['boundary_acceptance'][f'{b}_acceptable_count'] for m in metrics)
            acceptance[f'{b}_acceptable_count']=count
            acceptance[f'{b}_acceptable_rate']=count/counts['truth_count'] if counts['truth_count'] else None
        time_totals={k:sum(v['retained_time'][k] for v in variants) for k in
                     ('target_ms','retained_target_ms','non_target_ms','retained_non_target_ms','ignored_ms')}
        summaries.append(dict(name=name,**counts,boundary_acceptance=acceptance,retained_time=time_totals,
                              start_error_ms=_summary([r['start_error_ms'] for r in matches if r['start_error_ms']>0]),
                              end_error_ms=_summary([r['end_error_ms'] for r in matches if r['end_error_ms']>0])))
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path,
                        default=ROOT/'docs/experiments/m1-a-boundary-reevaluation-20261016.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--return-travel-px', type=float, default=TrajectoryConfig().return_travel_px,
                        help='Required travel on both sides of a return, normalized to 1920px width.')
    parser.add_argument('--turn-jump-px-s', type=float, default=TrajectoryConfig().turn_jump_px_s,
                        help='Required fitted and adjacent-step velocity change, normalized to 1920px width.')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; use a fresh directory.')
    source = json.loads(args.source_report.read_text())
    previous_trial_path = ROOT/'docs/experiments/m1-a-trajectory-20261016.json'
    previous_trial = json.loads(previous_trial_path.read_text())
    results = []
    args.output.mkdir(parents=True)
    for stage in source['stages'].values():
        for previous in stage['report']['results']:
            sample = previous['sample']
            if sample['source_id'] != 'A1':
                raise ValueError('This trial is scoped to already-seen A1 data.')
            video, annotation = ROOT/sample['video'], ROOT/sample['annotation']
            for path, expected in [(video,sample['video_sha256']), (annotation,sample['annotation_sha256'])]:
                if sha(path) != expected:
                    raise ValueError(f'Input changed: {path}')
            run_path = ROOT/previous['run_result']
            diagnostics_path = run_path.parent/'flight-diagnostics.jsonl'
            if sha(run_path) != previous['run_sha256'] or sha(diagnostics_path) != previous['diagnostics_sha256']:
                raise ValueError('Cached inference no longer matches the source report.')
            run = json.loads(run_path.read_text())
            rows = [json.loads(line) for line in diagnostics_path.read_text().splitlines()]
            if (run['status'] != 'completed' or len(rows) != sample['native_frame_count']-run['pending_model_frames']
                    or [r['frame_id'] for r in rows] != list(range(len(rows)))
                    or len(rows) % 3):
                raise ValueError('Unexpected cached three-frame coverage.')
            truth, exclusions = load_rally_annotations(annotation), load_rally_exclusions(annotation)
            trajectory_config = dict(previous['inference_config'],return_travel_px=args.return_travel_px,
                                     turn_jump_px_s=args.turn_jump_px_s)
            variants = []
            duration_trials = []
            for name, cls, config in [
                ('streaming-flight-v1', ShuttleRallySegmenter, FlightConfig(**previous['inference_config'])),
                ('trajectory-record-only', TrajectoryRallySegmenter, TrajectoryConfig(**trajectory_config)),
                ('trajectory-single-flight', TrajectoryRallySegmenter,
                 TrajectoryConfig(**trajectory_config,filter_single_flight=True)),
                ('trajectory-uncertain-short-trial', TrajectoryRallySegmenter,
                 TrajectoryConfig(**trajectory_config,filter_single_flight=True,filter_uncertain_short=True)),
            ]:
                segmenter = cls(lambda points:points,width=run['input']['width'],
                                height=run['input']['height'],config=config)
                predictions, diagnostics, wall = replay_points(rows,segmenter)
                if cls is ShuttleRallySegmenter:
                    assert [asdict(r) for r in predictions] == run['predictions'], 'Baseline replay changed'
                    assert diagnostics == rows, 'Baseline observation rules changed'
                variant = dict(name=name,config=asdict(config),replay_wall_s=wall,
                               metrics=evaluate_rallies(predictions,truth,excluded_events=exclusions),
                               retained_time=retained_time(predictions,truth,exclusions,sample['duration_ms']))
                if isinstance(segmenter,TrajectoryRallySegmenter):
                    old = next(r for r in previous_trial['results'] if r['sample']['id'] == sample['id'])['variants'][1]
                    assert segmenter.events == old['events'], 'High-clear connections changed'
                    assert [d['interval'] for d in segmenter.flight_decisions] == [d['interval'] for d in old['flight_decisions']], 'Unfiltered intervals changed'
                    variant.update(events=segmenter.events,flight_decisions=segmenter.flight_decisions,
                                   unfinished_candidate=segmenter.start_ms is not None,
                                   unfinished_rally=segmenter.active)
                    if not config.filter_single_flight:
                        path=args.output/f"{sample['id']}-trajectory-diagnostics.jsonl"
                        path.write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in diagnostics))
                        variant.update(diagnostics=str(path),diagnostics_sha256=sha(path))
                        # Equivalent to the explicit uncertain-short trial for
                        # each duration limit; all keep decisions override it.
                        for limit_ms in (3000,4000,5000,6000):
                            kept = [p for p,d in zip(predictions,segmenter.flight_decisions)
                                    if d['classification'] == 'keep' or d['duration_ms'] > limit_ms]
                            dropped = [d['interval'] for d in segmenter.flight_decisions
                                       if d['classification'] != 'keep' and d['duration_ms'] <= limit_ms]
                            duration_trials.append(dict(limit_ms=limit_ms,filtered_intervals=dropped,
                                metrics=evaluate_rallies(kept,truth,excluded_events=exclusions),
                                retained_time=retained_time(kept,truth,exclusions,sample['duration_ms'])))
                    if config.filter_uncertain_short:
                        trial = next(t for t in duration_trials if t['limit_ms'] == config.short_event_ms)
                        assert variant['metrics'] == trial['metrics'], 'Duration-trial evaluation differs from actual filter'
                        assert variant['retained_time'] == trial['retained_time'], 'Duration-trial retention differs from actual filter'
                variants.append(variant)
            results.append(dict(sample=sample,run_result=str(run_path),run_sha256=sha(run_path),
                                cached_diagnostics_sha256=sha(diagnostics_path),
                                observed_frame_count=len(rows),unobserved_tail_frames=run['pending_model_frames'],
                                variants=variants,duration_trials=duration_trials))
            print(sample['id'],[(v['name'],v['metrics']['missed_rally_count'],
                  v['metrics']['false_positive_count'],v['metrics']['boundary_acceptance']['both_acceptable_count'])
                  for v in variants],flush=True)
    summaries=summarize_results(results)
    report=dict(status='all_A1_seen_diagnostic_not_independent_acceptance',model_rerun=False,
                timing_note='Coordinate replay only; not video decoding or model inference speed.',
                tail_note='Only existing model observations replayed; no fabricated pending-frame coordinates or EOF flush.',
                source_report=str(args.source_report),source_report_sha256=sha(args.source_report),
                previous_trial=str(previous_trial_path),previous_trial_sha256=sha(previous_trial_path),
                validation=dict(original_baseline_exact=True,unfiltered_intervals_exact=True,high_clear_events_exact=True),
                code_sha256={str(p):sha(p) for p in [Path(__file__),ROOT/'backend/app/vision/trajectory_rally.py',
                    ROOT/'backend/app/vision/tracknet_rally.py',ROOT/'backend/app/vision/rally_eval.py',
                    ROOT/'backend/app/vision/rally_stream.py',ROOT/'backend/tests/rally_benchmark/compare_m1.py']},
                summary=summaries,results=results)
    (args.output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
