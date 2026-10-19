"""Experimental OFFLINE grouping of observed TrackNet peaks; no human labels.

Full-clip recurrence statistics and backdated path support read future frames.
This experiment is not the streaming segmenter or the selected architecture.
Distances use the existing 1920px reference width. Missing points stay missing.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .types import RallyInterval


@dataclass(frozen=True)
class CandidateRallyConfig:
    confidence: float = .5
    static_fraction: float | None = .1
    center_weight: float = 2
    max_step_error_px: float = 48
    min_track_points: int = 4
    min_track_ms: float = 160
    min_track_travel_px: float = 80
    max_gap_ms: float = 2400
    min_span_ms: float = 1600
    min_observations: int = 18
    min_motion_fraction: float = .45
    min_motion_ms: float = 0

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError('Confidence must be between zero and one.')
        if self.static_fraction is not None and not 0 < self.static_fraction <= 1:
            raise ValueError('Static fraction must be in (0, 1], or None.')
        if not 3 <= self.min_track_points <= 8 or self.min_observations < 1:
            raise ValueError('A path needs 3–8 points; groups need positive observation counts.')
        if not 0 <= self.min_motion_fraction <= 1:
            raise ValueError('Motion fraction must be between zero and one.')
        if any(not math.isfinite(v) or v < 0 for v in (
            self.center_weight, self.max_step_error_px, self.min_track_ms,
            self.min_track_travel_px, self.max_gap_ms, self.min_span_ms, self.min_motion_ms,
        )):
            raise ValueError('Candidate thresholds must be finite and nonnegative.')


def candidate_motion(rows: list[dict], *, width: float, config: CandidateRallyConfig) -> list[dict]:
    """Mark native observations supported by short, smooth candidate paths.

    Retain three possible histories per endpoint, up to eight points each.
    A turn can start a new path; grouping may join it across missing observations.
    Recurrence suppresses fixed background responses. The optional center bias
    favours a centered main court, without a hand-specified court polygon.
    """
    if not math.isfinite(width) or width <= 0:
        raise ValueError('Width must be positive and finite.')
    scale = 1920 / width
    normalized, counts = [], Counter()
    for i, row in enumerate(rows):
        if (not math.isfinite(row['timestamp_ms']) or (i and (
            row['timestamp_ms'] <= rows[i-1]['timestamp_ms'] or row['frame_id'] <= rows[i-1]['frame_id']
        ))):
            raise ValueError('Observations must retain increasing native ids and timestamps.')
        peaks = [dict(p, x=p['x']*scale, y=p['y']*scale,
                      timestamp_ms=row['timestamp_ms'], frame_id=row['frame_id']) for p in row['peaks']]
        if any(not all(math.isfinite(p[k]) for k in ('x', 'y', 'confidence')) for p in peaks):
            raise ValueError('Candidate coordinates and scores must be finite.')
        normalized.append(peaks)
        # Count presence once per frame, including neighbouring 32px cells.
        counts.update({(round(p['x']/32)+dx, round(p['y']/32)+dy)
                       for p in peaks for dx in (-1, 0, 1) for dy in (-1, 0, 1)})

    def score(p):
        return p['confidence'] - config.center_weight * abs(p['x']/1920-.5)

    paths, marked = [], {}
    for row, candidates in zip(rows, normalized):
        now = row['timestamp_ms']
        paths = [p for p in paths if now-p[-1]['timestamp_ms'] <= 100]
        peaks = [p for p in candidates if p['confidence'] >= config.confidence and score(p) > 0
                 and (config.static_fraction is None or
                      counts[(round(p['x']/32), round(p['y']/32))]/len(rows) < config.static_fraction)]
        extended = []
        for p in peaks:
            options = [[p]]
            for path in paths:
                last = path[-1]
                dt = (now-last['timestamp_ms'])/1000
                if math.hypot(p['x']-last['x'], p['y']-last['y'])/dt > 4000:
                    continue
                if len(path) >= 2:
                    previous = path[-2]
                    elapsed = (last['timestamp_ms']-previous['timestamp_ms'])/1000
                    x = last['x'] + (last['x']-previous['x'])/elapsed*dt
                    y = last['y'] + (last['y']-previous['y'])/elapsed*dt
                    # The extrapolated point only tests an observed candidate;
                    # it is never emitted as a new coordinate.
                    if math.hypot(p['x']-x, p['y']-y) > config.max_step_error_px:
                        continue
                options.append((path+[p])[-8:])
            options.sort(key=lambda q: (len(q), sum(map(score, q))), reverse=True)
            extended.extend(options[:3])
        paths += extended
        for path in extended:
            span = path[-1]['timestamp_ms']-path[0]['timestamp_ms']
            extent = math.hypot(max(p['x'] for p in path)-min(p['x'] for p in path),
                                max(p['y'] for p in path)-min(p['y'] for p in path))
            if (len(path) < config.min_track_points or span < config.min_track_ms
                    or extent < config.min_track_travel_px):
                continue
            quality = sum(map(score, path))/len(path)
            for p in path:
                if p['frame_id'] not in marked or quality > marked[p['frame_id']][0]:
                    marked[p['frame_id']] = quality, p
    return [dict(frame_id=r['frame_id'], timestamp_ms=r['timestamp_ms'],
                 motion=r['frame_id'] in marked,
                 point=({k: marked[r['frame_id']][1][k] / (scale if k in ('x', 'y') else 1)
                         for k in ('x', 'y', 'confidence')} if r['frame_id'] in marked else None))
            for r in rows]


def candidate_intervals(motion: list[dict], *, eof_ms: float,
                        config: CandidateRallyConfig) -> list[RallyInterval]:
    """Group observed support; EOF emission is bookkeeping, not live latency.

    Supported duration sums observation gaps capped at the 100ms path limit.
    This is a density heuristic, not measured shuttle airtime or interpolation.
    Boundaries are actual support timestamps, with no scoring/export padding.
    """
    if not math.isfinite(eof_ms) or (motion and eof_ms < motion[-1]['timestamp_ms']):
        raise ValueError('EOF must be at or after the last observation.')
    groups = []
    for r in (r for r in motion if r['motion']):
        if not groups or r['timestamp_ms']-groups[-1][-1]['timestamp_ms'] > config.max_gap_ms:
            groups.append([])
        groups[-1].append(r)
    kept = []
    for g in groups:
        span = g[-1]['timestamp_ms']-g[0]['timestamp_ms']
        supported = sum(min(100, b['timestamp_ms']-a['timestamp_ms']) for a, b in zip(g, g[1:]))
        if (len(g) >= config.min_observations and span >= config.min_span_ms and span > 0
                and supported >= config.min_motion_ms and supported/span >= config.min_motion_fraction):
            kept.append(RallyInterval(len(kept)+1, g[0]['timestamp_ms'], g[-1]['timestamp_ms'], eof_ms))
    return kept
