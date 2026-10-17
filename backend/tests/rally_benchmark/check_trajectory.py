#!/usr/bin/env python3
"""Check frozen trajectory rules on a new source; never select parameters here."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from compare_trajectory import (
    ROOT, FlightConfig, ShuttleRallySegmenter, TrajectoryConfig, TrajectoryRallySegmenter,
    evaluate_rallies, load_rally_annotations, load_rally_exclusions,
    replay_points, retained_time, sha, summarize_results,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; use a fresh directory.')
    manifest = json.loads(args.manifest.read_text())
    for path, expected in manifest['files_sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError(f'Frozen inference/algorithm/evaluation file changed: {path}')
    if manifest['inference_config']['filter_single_flight'] or manifest['inference_config']['filter_uncertain_short']:
        raise ValueError('Cache must be produced with both filters off.')
    summary_path = args.runs/'summary.json'
    inference_summary = json.loads(summary_path.read_text())
    if (len(inference_summary['runs']) != len(manifest['samples'])
            or any(r['status'] != 'completed' for r in inference_summary['runs'])
            or inference_summary['weights_sha256'] != manifest['files_sha256'][
                'models/SoloShuttlePose/src/models/weights/ball_track.pt']):
        raise ValueError('Inference summary is incomplete or model weights differ.')
    results = []
    for sample in manifest['samples']:
        for key in ('video', 'annotation', 'validation'):
            if sha(ROOT/sample[key]) != sample[f'{key}_sha256']:
                raise ValueError(f'Frozen input changed: {sample["id"]} {key}')
        run_path = args.runs/sample['run_subdirectory']/'result.json'
        run = json.loads(run_path.read_text())
        if (run['status'] != 'completed' or Path(run['video']) != (ROOT/sample['video']).resolve()
                or run['config'] != manifest['inference_config']
                or run['input']['frames_delivered'] != sample['native_frame_count']):
            raise ValueError(f'Run differs from frozen input/config: {sample["id"]}')
        diagnostics_path = run_path.with_name('flight-diagnostics.jsonl')
        rows = [json.loads(line) for line in diagnostics_path.read_text().splitlines()]
        pending = run['pending_model_frames']
        if (pending not in (0,1,2) or len(rows) != sample['native_frame_count']-pending
                or len(rows) % 3 or [r['frame_id'] for r in rows] != list(range(len(rows)))
                or any(b['timestamp_ms'] <= a['timestamp_ms'] for a,b in zip(rows,rows[1:]))):
            raise ValueError(f'Incomplete native observation prefix: {sample["id"]}')
        truth = load_rally_annotations(ROOT/sample['annotation'])
        exclusions = load_rally_exclusions(ROOT/sample['annotation'])
        variants = []
        for name, cls, config in [
            ('streaming-flight-v1', ShuttleRallySegmenter, FlightConfig(**manifest['baseline_config'])),
            ('trajectory-record-only', TrajectoryRallySegmenter, TrajectoryConfig(**manifest['inference_config'])),
            ('trajectory-single-flight', TrajectoryRallySegmenter,
             TrajectoryConfig(**(manifest['inference_config'] | {'filter_single_flight':True}))),
            ('trajectory-uncertain-short-trial', TrajectoryRallySegmenter,
             TrajectoryConfig(**(manifest['inference_config'] | {'filter_single_flight':True,'filter_uncertain_short':True}))),
        ]:
            segmenter = cls(lambda points:points,width=run['input']['width'],height=run['input']['height'],config=config)
            predictions, diagnostics, wall = replay_points(rows,segmenter)
            if name == 'trajectory-record-only':
                assert [asdict(r) for r in predictions] == run['predictions'], 'Native-input predictions changed'
                assert diagnostics == rows, 'Native-input frame diagnostics changed'
                assert segmenter.events == run['trajectory_events'], 'Native-input high-clear events changed'
                assert segmenter.flight_decisions == run['flight_decisions'], 'Native-input decisions changed'
            variant = dict(name=name,config=asdict(config),replay_wall_s=wall,
                           metrics=evaluate_rallies(predictions,truth,excluded_events=exclusions),
                           retained_time=retained_time(predictions,truth,exclusions,sample['duration_ms']))
            if isinstance(segmenter,TrajectoryRallySegmenter):
                variant.update(events=segmenter.events,flight_decisions=segmenter.flight_decisions,
                               unfinished_candidate=segmenter.start_ms is not None,unfinished_rally=segmenter.active)
            variants.append(variant)
        results.append(dict(sample=sample,run_result=str(run_path),run_sha256=sha(run_path),
                            cached_diagnostics_sha256=sha(diagnostics_path),observed_frame_count=len(rows),
                            unobserved_tail_frames=pending,inference_wall_s=run['wall_time_s'],
                            memory_samples=run['memory_samples'],variants=variants))
        print(sample['id'],[(v['name'],v['metrics']['missed_rally_count'],v['metrics']['false_positive_count'])
                            for v in variants],flush=True)
    report = dict(status='new_source_check_not_final_acceptance',model_rerun=True,
                  manifest=str(args.manifest),manifest_sha256=sha(args.manifest),
                  inference_summary=str(summary_path),inference_summary_sha256=sha(summary_path),
                  device=inference_summary['device'],warmup_s=inference_summary['warmup_s'],
                  code_sha256={str(p):sha(p) for p in [Path(__file__),ROOT/'backend/tests/rally_benchmark/compare_trajectory.py',
                    ROOT/'backend/tests/rally_benchmark/compare_m1.py',*(ROOT/p for p in manifest['files_sha256'])]},
                  timing_note='inference_wall_s is actual decoded-video model execution; replay_wall_s is cached-coordinate replay.',
                  tail_note='All truth retained in evaluation; buffered final frames are recorded, never fabricated or flushed.',
                  validation=dict(frozen_inputs_and_code_match=True,native_input_replay_exact=True),
                  summary=summarize_results(results),results=results)
    args.output.mkdir(parents=True)
    (args.output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
