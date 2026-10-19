"""Experimental causal rules on TrackNet coordinates; no extra vision model."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np

from modules.media.types import TimestampedFrame
from modules.rally.types import RallyInterval
from modules.rally.tracknet_rally import FlightConfig, ShuttleRallySegmenter
from modules.models.tracknet import ShuttlePoint


@dataclass(frozen=True)
class TrajectoryConfig(FlightConfig):
    direction_window_ms: float = 160
    direction_min_span_ms: float = 40
    direction_max_residual_px: float = 80
    top_fraction: float = .15
    exit_max_y_fraction: float = .4
    exit_horizon_ms: float = 250
    high_clear_gap_ms: float = 2800
    reentry_x_fraction: float = .2
    turn_jump_px_s: float = 1100
    track_gap_ms: float = 120
    return_support_ms: float = 320
    return_travel_px: float = 120
    short_event_ms: float = 5000
    filter_single_flight: bool = False
    filter_uncertain_short: bool = False

    def __post_init__(self):
        if not (0 < self.top_fraction <= self.exit_max_y_fraction < 1):
            raise ValueError("Top and exit fractions must satisfy 0 < top <= exit < 1.")
        if self.high_clear_gap_ms <= self.quiet_ms:
            raise ValueError("High-clear waiting must exceed normal quiet time.")
        if not all(math.isfinite(v) and v > 0 for v in (
            self.direction_window_ms, self.direction_min_span_ms, self.direction_max_residual_px,
            self.exit_horizon_ms, self.high_clear_gap_ms, self.reentry_x_fraction,
            self.turn_jump_px_s, self.track_gap_ms, self.return_support_ms,
            self.return_travel_px, self.short_event_ms,
        )):
            raise ValueError("Trajectory thresholds must be finite and positive.")
        if self.return_support_ms < self.track_gap_ms:
            raise ValueError("Return support must cover at least one allowed track gap.")


@dataclass(frozen=True)
class MotionDirection:
    vx_px_s: float
    vy_px_s: float
    residual_px: float
    reliable: bool


def analyze_motion(points: Sequence[tuple[float, ShuttlePoint]], *, width: float,
                   config: TrajectoryConfig) -> MotionDirection | None:
    """Fit up to three valid points in source time; speeds use 1920px width.

    Two points need at least 80ms of support, matching the base motion window;
    this also handles a low-confidence frame between two valid reentry points.
    """
    if len(points) < 2:
        return None
    rows = list(points)[-3:]
    if rows[-1][0] - rows[0][0] > config.direction_window_ms:
        return None
    minimum_span = max(80, config.direction_min_span_ms) if len(rows) == 2 else config.direction_min_span_ms
    if rows[-1][0] - rows[0][0] < minimum_span:
        return None
    times = np.array([(t - rows[0][0]) / 1000 for t, _ in rows])
    positions = np.array([(p.x, p.y) for _, p in rows]) * 1920 / width
    centered = times - times.mean()
    velocity = centered @ positions / (centered @ centered)
    residual = float(np.sqrt(np.mean((positions - positions.mean(axis=0)
                                      - centered[:, None] * velocity) ** 2)))
    vx, vy = map(float, velocity)
    return MotionDirection(vx, vy, residual, residual <= config.direction_max_residual_px
                           and math.hypot(vx, vy) <= 2 * config.max_speed_px_s)


def analyze_flight(rows: list[dict], *, width: float, config: TrajectoryConfig,
                   connected_high_clear: bool, trailing_rows: list[dict]) -> dict:
    """Separate local impacts from sustained returns, using only received rows.

    Gaps remain unknown. A short, sparse track is an experimental deletion
    candidate, never proof of a ball-return or a human evaluation exclusion.
    """
    valid = [r for r in rows if r['valid']]
    xy = np.array([(r['x'], r['y']) for r in valid], dtype=float).reshape(-1, 2) * 1920 / width
    times = np.array([r['timestamp_ms'] for r in valid])
    gaps = np.diff(times)
    speeds = np.linalg.norm(np.diff(xy, axis=0), axis=1) * 1000 / gaps
    # Split at missing observations or impossible jumps; never draw a flight
    # through these breaks. Brief gaps retain their actual elapsed time.
    cuts = np.flatnonzero((gaps > config.track_gap_ms) | (speeds > 2*config.max_speed_px_s)) + 1
    runs = np.split(np.arange(len(valid)), cuts)
    runs = [r for r in runs if len(r) >= 2]
    flight_runs = []
    for run in runs:
        span = float(times[run[-1]] - times[run[0]])
        extent = float(np.linalg.norm(np.ptp(xy[run], axis=0)))
        if span >= config.return_support_ms and extent >= config.return_travel_px:
            flight_runs.append(dict(start_ms=float(times[run[0]]), end_ms=float(times[run[-1]]),
                                    span_ms=span, extent_px=extent))
    changes = []
    for run in runs:
        for offset in range(4, len(run) - 4):
            i = int(run[offset])
            center = times[i]
            velocities, residuals = [], []
            for side in (run[offset-4:offset], run[offset+1:offset+5]):
                seconds = (times[side] - center) / 1000
                curve = np.polynomial.polynomial.polyfit(seconds, xy[side], 2)
                fitted = np.polynomial.polynomial.polyval(seconds, curve).T
                residuals.append(float(np.sqrt(np.mean((xy[side] - fitted) ** 2))))
                velocities.append(curve[1])
            incoming, outgoing = velocities
            jump = float(np.linalg.norm(outgoing - incoming))
            step_in = (xy[i]-xy[i-1]) * 1000/(times[i]-times[i-1])
            step_out = (xy[i+1]-xy[i]) * 1000/(times[i+1]-times[i])
            local_jump = float(np.linalg.norm(step_out-step_in))
            speed_before, speed_after = map(float, map(np.linalg.norm, velocities))
            if (max(residuals) > 12 or min(speed_before, speed_after) < config.min_speed_px_s
                    or max(speed_before, speed_after) > 2 * config.max_speed_px_s
                    or min(jump, local_jump) < config.turn_jump_px_s):
                continue
            cosine = float(incoming @ outgoing / (speed_before * speed_after))
            # Require observed displacement to agree with the fitted reversal.
            # A1-02 at 80s had two downward displacements but opposite fitted slopes.
            observed_in, observed_out = xy[i]-xy[i-4], xy[i+4]-xy[i]
            lengths = float(np.linalg.norm(observed_in)*np.linalg.norm(observed_out))
            observed_cosine = float(observed_in @ observed_out / lengths) if lengths else 1.
            reversal = cosine < -.2 and observed_cosine < -.2
            before = run[(times[run] >= center-2*config.return_support_ms) & (times[run] < center)]
            after = run[(times[run] > center) & (times[run] <= center+2*config.return_support_ms)]
            incoming_span = float(center-times[before[0]])
            outgoing_span = float(times[after[-1]]-center)
            incoming_travel = float(np.linalg.norm(xy[i]-xy[before[0]]))
            outgoing_travel = float(np.linalg.norm(xy[after[-1]]-xy[i]))
            supported = (reversal and min(incoming_span, outgoing_span) >= config.return_support_ms
                         and min(incoming_travel, outgoing_travel) >= config.return_travel_px)
            changes.append(dict(timestamp_ms=float(center), available_at_ms=float(times[after[-1]]),
                              kind='sustained_return' if supported else
                                   'local_reversal' if reversal else 'speed_change',
                              incoming_px_s=incoming.tolist(), outgoing_px_s=outgoing.tolist(),
                              velocity_jump_px_s=jump, observed_cosine=observed_cosine,
                              incoming_span_ms=incoming_span, outgoing_span_ms=outgoing_span,
                              incoming_travel_px=incoming_travel, outgoing_travel_px=outgoing_travel))
    turns = [r for r in changes if r['kind'] == 'sustained_return']
    duration = rows[-1]['timestamp_ms']-rows[0]['timestamp_ms'] if rows else 0
    short = 0 < duration <= config.short_event_ms
    # A stop after the flight is useful; observing the launch at rest is not
    # required. Only use the already received 320ms immediately after its end.
    tail = [r for r in trailing_rows if r['valid'] and rows
            and r['timestamp_ms'] <= rows[-1]['timestamp_ms']+config.return_support_ms]
    stop_spread_px = 16
    settled = (len(tail) >= 4 and tail[-1]['timestamp_ms']-tail[0]['timestamp_ms'] >= 200
               and max(b['timestamp_ms']-a['timestamp_ms'] for a,b in zip(tail,tail[1:])) <= config.track_gap_ms
               and float(np.linalg.norm(np.ptp([(r['x'],r['y']) for r in tail],axis=0)))*1920/width <= stop_spread_px)
    for change in changes:
        if change['kind'] != 'local_reversal':
            continue
        index = int(np.searchsorted(times, change['timestamp_ms']))
        excursion = float(max(np.linalg.norm(xy[index:] - xy[index],axis=1)))
        change['remaining_excursion_px'] = excursion
        # A1-03's landing jitter stayed within 14px, then stopped. A tiny
        # terminal deflection must not veto an otherwise supported single flight.
        if settled and excursion <= stop_spread_px:
            change['kind'] = 'small_end_deflection'
    interior_reversals = [r for r in changes if r['kind'] == 'local_reversal'
                         and min(r['timestamp_ms']-rows[0]['timestamp_ms'],
                                 rows[-1]['timestamp_ms']-r['timestamp_ms']) >= config.return_support_ms]
    reasons = []
    if connected_high_clear:
        classification = 'keep'
        reasons.append('connected_high_clear')
    elif turns:
        classification = 'keep'
        reasons.append('sustained_return_observed')
    elif (short and len(flight_runs) == 1 and len(cuts) == 0 and settled and not interior_reversals):
        classification = 'single_flight_candidate'
        reasons.append('short_continuous_flight_then_stop')
    else:
        classification = 'uncertain'
        reasons.append('no_sustained_return_proven')
    if len(cuts):
        reasons.append('unexplained_track_breaks')
    if not settled:
        reasons.append('stop_not_observed')
    if interior_reversals:
        reasons.append('local_reversal_without_sustained_support')
    if any(r['kind'] == 'small_end_deflection' for r in changes):
        reasons.append('small_end_deflection_then_stop')
    return dict(classification=classification, reasons=reasons, duration_ms=duration,
                short_event=short, uncertain_short_candidate=short and classification == 'uncertain',
                settled_after_flight=bool(settled), flight_runs=flight_runs,
                valid_fraction=len(valid) / len(rows) if rows else 0,
                max_valid_gap_ms=float(max(gaps)) if len(gaps) else None, return_candidates=turns,
                track_breaks=[dict(start_ms=float(times[i-1]), end_ms=float(times[i]),
                                   kind='missing' if gaps[i-1] > config.track_gap_ms else 'jump') for i in cuts],
                motion_changes=changes,
                note='Experimental coordinate evidence; missing returns remain unknown, not evaluation exclusions.')


class TrajectoryRallySegmenter(ShuttleRallySegmenter):
    def __init__(self, predict, *, width, height, config=None):
        super().__init__(predict, width=width, height=height, config=config or TrajectoryConfig())
        self.history: deque[dict] = deque()
        self.recent: list[tuple[float, ShuttlePoint]] = []
        self.direction: MotionDirection | None = None
        self.exit_hint: dict | None = None
        self.reentry_until_ms = -math.inf
        self.awaiting_reentry = False
        self.connected_high_clear = False
        self.events: list[dict] = []
        self.flight_decisions: list[dict] = []

    def _quiet_expired(self, now, point):
        self.awaiting_reentry = False
        if not super()._quiet_expired(now, point):
            return False
        cfg = self.config
        if now <= self.reentry_until_ms:
            return False
        hint = self.exit_hint
        if hint is None or self.last_motion_ms - hint['timestamp_ms'] > cfg.exit_horizon_ms:
            return True
        if now - self.last_motion_ms > cfg.high_clear_gap_ms:
            self.events.append(dict(type='top_wait_expired', timestamp_ms=now))
            return True
        if self.direction and self.direction.reliable and self.recent[-1][0] == now:
            if (point.y / self.height <= cfg.top_fraction and self.direction.vy_px_s > 100
                    and abs(point.x - hint['exit_x']) / self.width <= cfg.reentry_x_fraction):
                self.events.append(dict(type='top_reconnected', timestamp_ms=now,
                                        gap_ms=now-self.last_motion_ms, exit_hint=hint))
                self.reentry_until_ms = now + cfg.motion_window_ms
                self.connected_high_clear = True
                self.exit_hint = None
                return False
            # Reliable motion elsewhere cannot be attached to a top exit.
            if math.hypot(self.direction.vx_px_s, self.direction.vy_px_s) >= cfg.min_speed_px_s:
                return True
        self.awaiting_reentry = True
        return False

    def _allow_motion(self):
        # Visible points may build direction support while waiting, but must not
        # advance the rally end before the reentry location/direction is checked.
        return not self.awaiting_reentry

    def _observe(self, source, point, emitted_at):
        cfg, now = self.config, source.timestamp_ms
        left, top, right, bottom = cfg.field
        valid = (all(math.isfinite(v) for v in (point.x, point.y, point.confidence))
                 and point.confidence >= cfg.confidence
                 and left <= point.x / self.width <= right
                 and top <= point.y / self.height <= bottom)
        self.recent = [(t,p) for t,p in self.recent if now-t <= cfg.direction_window_ms]
        if valid:
            self.recent.append((now, point))
        self.direction = analyze_motion(self.recent, width=self.width, config=cfg) if valid else None
        if self.direction and self.direction.reliable and self.direction.vy_px_s < -100:
            vx = self.direction.vx_px_s * self.width / 1920
            vy = self.direction.vy_px_s * self.width / 1920
            to_top_ms = -point.y / vy * 1000
            if (point.y / self.height <= cfg.exit_max_y_fraction
                    and (point.y / self.height <= cfg.top_fraction or to_top_ms <= cfg.exit_horizon_ms)):
                self.exit_hint = dict(timestamp_ms=now, exit_x=point.x+vx*to_top_ms/1000,
                                      y_fraction=point.y/self.height,
                                      direction=asdict(self.direction))
        intervals = super()._observe(source, point, emitted_at)
        outputs = []
        for interval in intervals:
            rows = [r for r in self.history if interval.start_ms <= r['timestamp_ms'] <= interval.end_ms]
            decision = analyze_flight(rows, width=self.width, config=cfg,
                                      connected_high_clear=self.connected_high_clear,
                                      trailing_rows=[r for r in self.history if r['timestamp_ms'] > interval.end_ms])
            reject = ((cfg.filter_single_flight and decision['classification'] == 'single_flight_candidate')
                      or (cfg.filter_uncertain_short and decision['uncertain_short_candidate']))
            self.flight_decisions.append(dict(interval=asdict(interval), **decision, filtered=reject))
            if not reject:
                outputs.append(interval)
        # A timeout also clears unconfirmed short candidates, which emit no interval.
        if self.start_ms is None:
            self.exit_hint = None
            self.connected_high_clear = False
            self.reentry_until_ms = -math.inf
        diagnostic = self.last_diagnostics[-1]
        diagnostic.update(direction=asdict(self.direction) if self.direction else None,
                          top_wait_possible=self.exit_hint is not None,
                          connected_high_clear=self.connected_high_clear)
        self.history.append(dict(timestamp_ms=now, x=point.x, y=point.y, valid=valid))
        cutoff = self.start_ms-cfg.motion_window_ms if self.start_ms is not None else now-2*cfg.motion_window_ms
        # Store only the current candidate; no future frames or full-video access.
        while self.history and self.history[0]['timestamp_ms'] < cutoff:
            self.history.popleft()
        return outputs
