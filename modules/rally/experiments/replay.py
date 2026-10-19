"""Replay retained observations through the selected scenarios, without running models."""
import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def diagnostic_rows(case, path):
    observations = rows(path)
    if 'window' not in case:
        return observations
    window = case['window']
    first, last = window['source_frame_start'], window['source_frame_end_exclusive']
    offset = window['clip_time_start_ms']
    if not 0 <= first < last <= len(observations):
        raise ValueError(f"Invalid saved-input window: {case['sample_id']}")
    selected = observations[first:last]
    if (selected[0]['timestamp_ms'] != offset
            or any(row['frame_id'] != first + i for i, row in enumerate(selected))
            or selected[-1]['timestamp_ms'] - offset >= case['duration_ms']):
        raise ValueError(f"Saved input does not match window: {case['sample_id']}")
    # A shared cache keeps source-video times; each test clip starts at frame/time zero.
    return [dict(row, frame_id=i, timestamp_ms=row['timestamp_ms'] - offset,
                 available_at_ms=row['available_at_ms'] - offset)
            for i, row in enumerate(selected)]


def replay(case):
    inputs = {k: ROOT / p for k, p in case['inputs'].items()}
    for key, path in inputs.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != case['input_sha256'][key]:
            raise ValueError(f"Saved input changed: {path}")
    if case['scene'] == 'high':
        from modules.media.types import TimestampedFrame
        from modules.models.tracknet import ShuttlePoint
        from modules.rally.rally_stream import RallyStream
        from modules.rally.scenarios.high import TrajectoryConfig, TrajectoryRallySegmenter
        profile = json.loads((ROOT/'modules/rally/scenarios/profiles.json').read_text())['high']
        segmenter = TrajectoryRallySegmenter(lambda points: points, width=1920, height=1080,
                                             config=TrajectoryConfig(**profile))
        stream, predicted = RallyStream(segmenter), []
        for row in diagnostic_rows(case, inputs['diagnostics']):
            predicted.extend(stream.process(TimestampedFrame(row['frame_id'], row['timestamp_ms'],
                ShuttlePoint(row['x'], row['y'], row['confidence']))))
    elif case['scene'] == 'courtside':
        from modules.rally.scenarios.courtside import predict
        predicted, _ = predict(rows(inputs['native']), rows(inputs['shifted']), rows(inputs['people']),
                               json.loads(inputs['flights'].read_text()), case['duration_ms'])
    else:
        import numpy as np
        from modules.rally.common.feet import add_foot_signals
        from modules.rally.scenarios.personal import predict
        with np.load(inputs['signals']) as archive:
            signals = {k: archive[k] for k in archive.files}
        add_foot_signals(signals, rows(inputs['people']))
        predicted, _ = predict(signals, case['duration_ms'])
    predictions = [asdict(p) for p in predicted]
    return dict(sample_id=case['sample_id'], scene=case['scene'], predictions=predictions,
                expected=case['expected'], exact=predictions == case['expected'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', choices=('high', 'courtside', 'personal'))
    parser.add_argument('--sample')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name('cases.json').read_text())['cases']
    cases = [c for c in cases if (not args.scene or c['scene']==args.scene)
             and (not args.sample or c['sample_id']==args.sample)]
    if not cases:
        parser.error('No matching saved-input case')
    results = [replay(c) for c in cases]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(results=results, exact=all(r['exact'] for r in results)),
                                      ensure_ascii=False, indent=2)+'\n')
    raise SystemExit(0 if all(r['exact'] for r in results) else 1)


if __name__ == '__main__':
    main()
