"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .check_short_events import decisions
from .connected_flight_filter import decision
from .court_rules import CandidateRallyConfig
from .court_rules import arc_delete
from .court_rules import candidate_intervals
from .court_rules import candidate_motion
from .court_rules import gate
from .high_return import continuation
from .supported_start import trim
from app.vision.rally_stream import RallyInterval
from dataclasses import asdict

CONFIG = {'confidence': 0.5, 'static_fraction': 0.1, 'center_weight': 2, 'max_step_error_px': 48, 'min_track_points': 3, 'min_track_ms': 60, 'min_track_travel_px': 80, 'max_gap_ms': 2400, 'min_span_ms': 1600, 'min_observations': 18, 'min_motion_fraction': 0.45, 'min_motion_ms': 0}

def pipeline(native, shifted, people, flights):
    cfg = CandidateRallyConfig(**CONFIG)
    raw = candidate_motion(shifted,width=1920,config=cfg)
    gated = gate(raw,250,1600,8)
    grouped = candidate_intervals(gated,eof_ms=shifted[-1]['timestamp_ms'],config=cfg)
    arc, arc_dec = arc_delete(raw,grouped)
    dd = decisions([asdict(p) for p in arc],flights,people)
    base = [asdict(p) for p,d in zip(arc,dd) if not d['delete']]
    expanded, extension_dec = continuation(base,flights,people,True)
    long_outputs = [p for p in expanded if p['end_ms']-p['start_ms']>3000]
    short_dec = [decision(p,flights,.2) for p in long_outputs]
    pairs = [trim(p,flights) for p,d in zip(long_outputs,short_dec) if not d['delete']]
    final = [RallyInterval(i+1,p['start_ms'],p['end_ms'],p['emitted_at_ms']) for i,(p,d) in enumerate(pairs)]
    return final,dict(grouped=[asdict(p) for p in grouped],arc=arc_dec,person_short=dd,
                      high_return=extension_dec,short_flight=short_dec,start=[d for p,d in pairs])
