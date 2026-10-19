"""Accepted courtside scenario: original short filtering, internal splits and observed tail recovery."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import math
import numpy as np
from modules.rally.types import RallyInterval
from modules.rally.common.court_rules import CandidateRallyConfig, arc_delete, candidate_intervals, candidate_motion, gate
from modules.rally.common.check_short_events import decisions as short_decisions
from modules.rally.common.connected_flight_filter import decision
from modules.rally.common.high_return import continuation
from modules.rally.common.supported_start import trim
from modules.rally.common.shuttle_paths import observed_candidates

PROFILES = json.loads(Path(__file__).with_name("profiles.json").read_text())
CONFIG, BASE_CONFIG = PROFILES["courtside"], PROFILES["courtside_base"]

def split_intervals(raw, shifted, people, flights, cfg):
    """Keep existing region geometry; vary temporal support and short filtering."""
    config=replace(CandidateRallyConfig(**BASE_CONFIG),max_gap_ms=cfg['gap_ms'],
                   min_span_ms=cfg['span_ms'],min_observations=cfg['observations'])
    gated=gate(raw,250,1600,cfg['region_points'])
    original_gated=[dict(r) for r in gated]
    if cfg.get('density_window_ms'):
        from scipy.ndimage import uniform_filter1d
        step=float(np.median(np.diff([r['timestamp_ms'] for r in gated])))
        win=max(1,round(cfg['density_window_ms']/step))|1
        density=uniform_filter1d(np.array([r['motion'] for r in gated],float),size=win,mode='constant')
        times=np.array([r['timestamp_ms'] for r in gated])
        seeds=times[(density>=cfg['density']) & np.array([r['motion'] for r in gated])]
        for r,f in zip(gated,density):
            supported=f>=cfg['density']
            if len(seeds) and cfg.get('density_edge_ms'):
                i=int(np.searchsorted(seeds,r['timestamp_ms']))
                supported=min(abs(t-r['timestamp_ms']) for t in seeds[max(0,i-1):i+1])<=cfg['density_edge_ms']
            r['motion']=bool(r['motion'] and supported)
    if cfg.get('contact_window_ms'):
        contacts=[sorted(c['t'] for f in flights if f['fit']['rms']<=cfg['fit_rms']
                         for c in f['contacts'] if c['player_id']==k and c['distance_body_heights']<=cfg['contact_distance'])
                  for k in (0,1)]
        for r in gated:
            t=r['timestamp_ms'];near=[]
            for values in contacts:
                i=int(np.searchsorted(values,t));neighbors=values[max(0,i-1):i+1]
                near.append(bool(neighbors and min(abs(x-t) for x in neighbors)<=cfg['contact_window_ms']/2))
            r['motion']=bool(r['motion'] and all(near))
    if cfg.get('person_speed') is not None:
        # Both people may move at different instants within the window. A
        # missing box never supplies activity; no missing position is filled.
        from scipy.ndimage import maximum_filter1d,median_filter
        ts=np.array([r['timestamp_ms'] for r in people]);speed=np.zeros((len(ts),2));last={}
        for i,row in enumerate(people):
            for p in row['players']:
                k=p['player_id'];b=p['box'];xy=np.array([(b['x1']+b['x2'])/2,b['y2']]);h=b['y2']-b['y1']
                if k in last:
                    t0,xy0,h0=last[k];dt=(ts[i]-t0)/1000
                    if dt<=.5:speed[i,k]=np.linalg.norm(xy-xy0)/((h+h0)/2)/dt
                last[k]=(ts[i],xy,h)
        step=float(np.median(np.diff(ts)))
        win=max(1,round(cfg['person_window_ms']/step))|1
        speed=median_filter(speed,size=(3,1),mode='nearest')
        both=np.all(maximum_filter1d(speed,size=win,axis=0,mode='constant')>=cfg['person_speed'],axis=1)
        for r in gated:
            i=min(len(ts)-1,int(np.searchsorted(ts,r['timestamp_ms'])))
            r['motion']=bool(r['motion'] and both[i])
    grouped=candidate_intervals(gated,eof_ms=shifted[-1]['timestamp_ms'],config=config)
    if cfg.get('internal_only'):
        outer=candidate_intervals(original_gated,eof_ms=shifted[-1]['timestamp_ms'],config=config)
        pieces=[]
        for p in outer:
            children=[q for q in grouped if p.start_ms<=q.start_ms<q.end_ms<=p.end_ms]
            # Weak evidence at an outside edge alone does not move that edge.
            # Only a gap separating multiple sustained groups triggers a split.
            if len(children)<2:
                pieces.append(p)
            else:
                for i,q in enumerate(children):
                    pieces.append(RallyInterval(0,p.start_ms if i==0 else q.start_ms,
                        p.end_ms if i==len(children)-1 else q.end_ms,p.emitted_at_ms))
        grouped=[replace(p,rally_id=i+1) for i,p in enumerate(pieces)]
        # Short-event continuity is measured in the original real observations.
        gated=original_gated
    arc, arc_dec=arc_delete(raw,grouped)
    checks=short_decisions([asdict(p) for p in arc],flights,people)
    def continuous(p):
        ps=[q for q in gated if p['start_ms']<=q['timestamp_ms']<=p['end_ms'] and q['motion']]
        if len(ps)<12:return False
        ts=[q['timestamp_ms'] for q in ps]
        span=ts[-1]-ts[0]
        support=sum(min(100,z-x) for x,z in zip(ts,ts[1:]))
        return span>=800 and support/span>=cfg.get('continuous_fraction',.6) and max(z-x for x,z in zip(ts,ts[1:]))<=cfg.get('continuous_gap_ms',400)
    kept=[];decisions=[]
    for p,d in zip(arc,checks):
        pp=asdict(p)
        veto=bool(cfg['short']=='continuous' and continuous(pp))
        drop=d['delete'] and cfg['short']!='all' and not veto
        decisions.append(dict(prediction=pp,original_delete=d['delete'],continuous=veto,delete=drop))
        if not drop:kept.append(pp)
    expanded,extensions=continuation(kept,flights,people,True)
    eligible=[p for p in expanded if p['end_ms']-p['start_ms']>3000 or cfg['short']=='all' or (cfg['short']=='continuous' and continuous(p))]
    final=[]
    for p in eligible:
        d=decision(p,flights,.2)
        if d['delete']:continue
        trimmed,detail=trim(p,flights)
        final.append(RallyInterval(len(final)+1,trimmed['start_ms'],trimmed['end_ms'],trimmed['emitted_at_ms']))
    return final,dict(grouped=[asdict(p) for p in grouped],short=decisions,arc=arc_dec,extension=extensions)

def recover_end(prediction, candidates, flights, cap_ms, gap_ms, error_growth):
    """Follow real candidates from an already accepted, newly split end only.

    A short dropout widens the position gate; it never supplies a ball point.
    Reuse original confidence/static rejection and linear position prediction.
    Competing paths remain separate, and a one-point jump cannot extend an end.
    """
    from modules.rally.common.seeded_source import predict
    from modules.rally.common.shuttle_paths import quality

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

def predict(native, shifted, people, flights, duration_ms, config=CONFIG):
    raw = candidate_motion(shifted, width=1920, config=CandidateRallyConfig(**BASE_CONFIG))
    split, trace = split_intervals(raw, shifted, people, flights, config)
    outer = candidate_intervals(gate(raw, 250, 1600, 8), eof_ms=shifted[-1]["timestamp_ms"],
                                config=CandidateRallyConfig(**BASE_CONFIG))
    candidates = observed_candidates(native, shifted[:len(native)])
    recovery = []
    for i, p in enumerate(split):
        group = next((g for g in trace["grouped"] if g["start_ms"] <= p.start_ms < g["end_ms"]
                      and abs(g["end_ms"] - p.end_ms) <= 4000), None)
        parent = next((q for q in outer if q.start_ms <= p.start_ms < q.end_ms), None)
        if group and parent and group["end_ms"] < parent.end_ms:
            cap = min(group["end_ms"] + config["tail_limit_ms"], parent.end_ms,
                      split[i + 1].start_ms if i + 1 < len(split) else duration_ms)
            split[i], detail = recover_end(p, candidates, flights, cap, config["tail_gap_ms"],
                                            config["tail_error_growth_px_s"])
            recovery.append(dict(rally_id=p.rally_id, cap_ms=cap, **detail))
    return split, dict(trace, end_recovery=recovery)
