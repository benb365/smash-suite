#!/usr/bin/env python3
"""Replay native TrackNet candidates with explicit diagnostic camera profiles."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'backend'))
from app.vision.candidate_rally import CandidateRallyConfig, candidate_motion, candidate_intervals
from app.vision.rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions
from app.vision.rally_stream import RallyInterval
from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
from compare_m1 import sha, retained_time
from compare_trajectory import summarize_results, replay_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--infer', action='store_true', help='Create new native runs before replay')
    parser.add_argument('--device', choices=('mps', 'cpu', 'cuda'), default='mps')
    args = parser.parse_args()
    if args.output.exists() or (args.infer and args.runs.exists()):
        parser.error('Use new output directories; existing runs can be replayed without --infer.')
    manifest = json.loads(args.manifest.read_text())
    profiles = json.loads(args.profiles.read_text())
    for path, expected in manifest['files_sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError(f'Frozen inference code/weights changed: {path}')
    for sample in manifest['samples']:
        # The earlier A1 manifest has no validation-file reference; C1/D1 do.
        for key in ('video', 'annotation') + (('validation',) if 'validation' in sample else ()):
            if sha(ROOT/sample[key]) != sample[key+'_sha256']:
                raise ValueError(f'Input changed: {sample[key]}')
    if args.infer:
        # Reuse the exact maintained decoder/model entry point. No second model
        # implementation, guessed frame rate, or new default camera selection.
        if manifest['inference_config'] != json.loads(json.dumps(asdict(TrajectoryConfig()))):
            raise ValueError('The multi-file native runner requires its frozen default trajectory config.')
        subprocess.run([sys.executable, str(ROOT/'backend/tests/rally_benchmark/run_live_tracknet.py'),
                        '--segmenter', 'trajectory', '--mode', 'offline', '--record-candidates',
                        '--device', args.device, '--output', str(args.runs),
                        *[arg for s in manifest['samples'] for arg in ('--video', str(ROOT/s['video']))]],
                       check=True)
    args.output.mkdir(parents=True)
    results = []
    for sample in manifest['samples']:
        directory = args.runs/sample['run_subdirectory']
        rp, cp, dp = (directory/p for p in ('result.json', 'shuttle-candidates.jsonl', 'tracknet-points.jsonl'))
        run = json.loads(rp.read_text())
        rows = [json.loads(x) for x in cp.read_text().splitlines()]
        original = [json.loads(x) for x in dp.read_text().splitlines()]
        pending = run['pending_model_frames']
        if (run['status'] != 'completed' or run['error'] is not None
                or Path(run['video']).resolve() != (ROOT/sample['video']).resolve()
                or run['config'] != manifest['inference_config']
                or run['input']['frames_delivered'] != sample['native_frame_count']
                or pending not in (0, 1, 2)
                or len(rows) != sample['native_frame_count']-pending
                or [r['frame_id'] for r in rows] != list(range(len(rows)))
                or [(r['frame_id'], r['timestamp_ms']) for r in rows]
                != [(r['frame_id'], r['timestamp_ms']) for r in original]):
            raise ValueError(f'Wrong native run or incomplete candidate coverage: {sample["id"]}')
        truth = load_rally_annotations(ROOT/sample['annotation'])
        excluded = load_rally_exclusions(ROOT/sample['annotation'])
        variants = []

        def evaluate(name, predictions, wall_s):
            variants.append(dict(name=name, metrics=evaluate_rallies(predictions, truth, excluded_events=excluded),
                                 retained_time=retained_time(predictions, truth, excluded, sample['duration_ms']),
                                 cached_analysis_wall_s=wall_s))

        evaluate('original-unfiltered', [RallyInterval(**r) for r in run['predictions']], 0)
        config = TrajectoryConfig(**(manifest['inference_config'] | dict(
            filter_single_flight=True, filter_uncertain_short=True)))
        segmenter = TrajectoryRallySegmenter(lambda images: images,
                                            width=run['input']['width'], height=run['input']['height'], config=config)
        control, _, wall_s = replay_points(original, segmenter)
        evaluate('a1-original-selected-control', control, wall_s)
        for profile in profiles['profiles']:
            tick = time.perf_counter()
            config = CandidateRallyConfig(**profile['config'])
            motion = candidate_motion(rows, width=run['input']['width'], config=config)
            predictions = candidate_intervals(motion, eof_ms=run['input']['last_timestamp_ms'], config=config)
            evaluate(profile['name'], predictions, time.perf_counter()-tick)
            (args.output/f'{sample["id"]}-{profile["name"]}-motion.jsonl').write_text(
                ''.join(json.dumps(r)+'\n' for r in motion))
        results.append(dict(sample=sample, run_result=str(rp), run_sha256=sha(rp),
                            candidates=str(cp), candidates_sha256=sha(cp), original_points_sha256=sha(dp),
                            pending_model_frames=pending, observation_count=len(rows),
                            native_wall_s=run['wall_time_s'], variants=variants))
        print(sample['id'], [(v['name'], v['metrics']['missed_rally_count'],
                               v['metrics']['false_positive_count']) for v in variants], flush=True)
    files = [Path(__file__), ROOT/'backend/app/vision/candidate_rally.py',
             ROOT/'backend/tests/rally_benchmark/compare_m1.py',
             ROOT/'backend/tests/rally_benchmark/compare_trajectory.py']
    report = dict(status='C1_D1_tuning_with_A1_control_not_independent_acceptance',
                  manifest=str(args.manifest), manifest_sha256=sha(args.manifest),
                  profiles=str(args.profiles), profiles_sha256=sha(args.profiles),
                  analysis_files_sha256={str(p.relative_to(ROOT)): sha(p) for p in files},
                  primary=profiles['primary'], results=results,
                  source_summaries={source: summarize_results([r for r in results if r['sample']['source_id']==source])
                                    for source in sorted({r['sample']['source_id'] for r in results})},
                  offline_note='Full-clip recurrence and retrospective candidate paths; EOF is not streaming latency.',
                  performance_note='Native model/decode wall time and cached analysis wall time are separate.')
    (args.output/'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
