"""C1/C2 comparison using saved observations and the existing D pose model.

Run from the repository root. Historical experiment helpers and observations
must be present. Original outputs, labels, regions and product entry stay intact.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import time
import types
import itertools
import inspect
import copy
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

R = Path.cwd()
B = R / 'models/SoloShuttlePose/.runtime'
OUT = B / 'c-recovery-20261019'
C = B / 'c2-current-algorithm-20261018'
D = B / 'd1-person-motion-20261017'
sys.path[:0] = [str(R/'backend'), str(R/'backend/tests/rally_benchmark'), str(D)]


def read(p):
    return json.loads(Path(p).read_text())


def rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def module(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def cases():
    saved = read(C/'relaxed-selection/comparison.json')['results']
    confirmed = next(r for r in read(R/'docs/experiments/a2-c2-d2-human-reviewed-20261018.json')['results'] if r['clip_id']=='C2')
    result = []
    for old in saved:
        s = dict(old['sample'])
        sid = s['id']
        if sid == 'C2':
            s.update(annotation=confirmed['annotation'], annotation_sha256=confirmed['annotation_sha256'])
            native = C/'observations/native.jsonl'
            shifted = C/'observations/shifted.jsonl'
            people = C/'observations/people.jsonl'
        else:
            native = B/'m1-cd-coordinate-20261017/inference'/s['run_subdirectory']/'shuttle-candidates.jsonl'
            shifted = B/f'c1-weak-tracks-20261017/full-phase1-{sid}/candidates.jsonl'
            people = R/f'models/yolo11n/.runtime/c1-region-support-20261017/{sid}/people.jsonl'
        assert sha(R/s['annotation']) == s['annotation_sha256']
        for p,h in old['input_sha256'].items():
            assert sha(R/p)==h,p
        result.append(dict(sample=s, old=old, native=native, shifted=shifted,
                           people=people, players=C/f'relaxed-selection/{sid}/players.jsonl',
                           flights=C/f'relaxed-selection/{sid}/flights.json'))
    assert len(result)==5
    return result


def adapted(name, argv, root=OUT):
    """Change only paths/manifest selection in the original D observation step."""
    source=D/name
    text=source.read_text()
    old="R/'datasets/badminton-v1/manifests/m1-cd-coordinate-trial-20261017.json'"
    if name!='players_v2.py':
        assert text.count(old)==1
        text=text.replace(old, 'Path('+repr(str(root/'manifest.json'))+')')
    if name=='pose_local_flow.py':
        assert text.count("if s['source_id']=='D1'")==1
        text=text.replace("if s['source_id']=='D1'", "if s['source_id'] in ('C1','C2')")
        old='R/f"models/SoloShuttlePose/.runtime/m1-cd-coordinate-20261017/final-comparison/{s[\'id\']}-d1-retain-motion.jsonl"'
        assert text.count(old)==1
        text=text.replace(old, 'B/f"{s[\'id\']}-motion.jsonl"')
    m=types.ModuleType('c_observe_'+name.replace('.','_'))
    m.__file__=str(source)
    exec(compile(text,str(source),'exec'),m.__dict__)
    m.B=root
    original_argv=sys.argv
    sys.argv=[str(source),*argv]
    tick=time.perf_counter()
    try:
        m.main()
    finally:
        sys.argv=original_argv
    write(root/(name+'.'+('-'.join(argv[1:2]) or 'all')+'.adapter.json'),
          dict(source=str(source.relative_to(R)), source_sha256=sha(source),
               adapted_sha256=hashlib.sha256(text.encode()).hexdigest(), argv=argv,
               wall_s=time.perf_counter()-tick))


def observe_d(only=None):
    from app.vision.candidate_rally import CandidateRallyConfig,candidate_motion
    cc=cases()
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/'manifest.json',dict(samples=[c['sample'] for c in cc]))
    cfg=next(p['config'] for p in read(R/'models/SoloShuttlePose/configs/m1-cd-candidate-20261017.json')['profiles'] if p['name']=='d1-retain')
    if only:
        assert set(only)<={c['sample']['id'] for c in cc}
    for c in [c for c in cc if not only or c['sample']['id'] in only]:
        s=c['sample'];sid=s['id'];dest=OUT/sid
        person_source=c['people']
        if sid=='C2':
            # C2's saved metadata has a file-hash map rather than the original
            # D/C1 metadata shape. Normalize this known input contract only.
            meta=read(person_source.with_name('result.json'))
            assert sha(person_source)==meta['files_sha256']['people.jsonl']
            normalized=OUT/'c2-observation-input'
            normalized.mkdir(exist_ok=True)
            shutil.copyfile(person_source,normalized/'people.jsonl')
            write(normalized/'result.json',dict(sample=s,output_sha256=sha(person_source),
                original_metadata=str(person_source.with_name('result.json').relative_to(R)),
                original_metadata_sha256=sha(person_source.with_name('result.json'))))
            person_source=normalized/'people.jsonl'
        # Original D feature extraction and automatic person selection: no C
        # court restriction or human-selected indices are added to this route.
        if not (dest/'feature-source.json').exists():
            adapted('features.py',['--sample',sid,'--people',str(person_source)])
        if not (dest/'selection-v2.json').exists():
            adapted('players_v2.py',['--sample',sid])
        mp=OUT/f'{sid}-motion.jsonl'
        if not mp.exists():
            observed=candidate_motion(rows(c['native']),width=1920,config=CandidateRallyConfig(**cfg))
            mp.write_text(''.join(json.dumps(q)+'\n' for q in observed))
        if not (OUT/f'pose-dense-{sid}/result.json').exists():
            adapted('pose.py',['--sample',sid,'--output','pose-dense-'+sid,
                              '--device','cpu','--min-size','192','--max-size','384',
                              '--stride','6','--offset','0','--proposals','200'])
    if all((OUT/f"pose-dense-{c['sample']['id']}/result.json").exists() for c in cc) and not (OUT/'flow/source.json').exists():
        adapted('pose_local_flow.py',['--output','flow','--pose-prefix','pose-dense'])


def observe_c_selected():
    """Use C's existing people; infer only crops absent from the D cache."""
    root=OUT/'c-selected';missing=root/'missing';cc=cases()
    for dest in (root,missing):
        write(dest/'manifest.json',dict(samples=[c['sample'] for c in cc]))
    weight=R/'models/SoloShuttlePose/src/models/weights/pose_kpRCNN.pth'
    weight_hash=sha(weight)
    for c in cc:
        sid=c['sample']['id'];out=root/f'pose-dense-{sid}'
        if (out/'result.json').exists():continue
        original=OUT/f'pose-dense-{sid}'
        meta=read(original/'result.json')
        assert sha(original/'pose.jsonl')==meta['output_sha256']
        assert meta['weights_sha256']==weight_hash
        assert meta['settings']==dict(device='cpu',min_size=192,max_size=384,stride=6,offset=0,proposals=200,
            detections_per_crop=3,crop_x_padding_h=.2,crop_y_padding_h=.12)
        cached={r['frame_id']:r for r in rows(original/'pose.jsonl')}
        features={r['frame_id']:r for r in rows(OUT/sid/'features.jsonl')}
        people=rows(c['players']);partial=[];borrowed={};new_count=0
        for r in people:
            f=features[r['frame_id']]
            assert abs(f['timestamp_ms']-r['timestamp_ms'])<.001
            lost=[]
            for p in r['players']:
                assert p['box']==f['boxes'][p['box_index']]
                p['body_motion']=f['body_motion'][p['box_index']]
                source=next((q for q in cached[r['frame_id']]['people'] if q['box']==p['box']),None)
                if source is None:
                    lost.append(p);new_count+=1
                else:
                    borrowed[(r['frame_id'],p['player_id'])]=dict(copy.deepcopy(source),
                        player_id=p['player_id'],box_index=p['box_index'])
            partial.append(dict(r,players=lost))
        def write_rows(p,rr):
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(''.join(json.dumps(r)+'\n' for r in rr))
        write_rows(root/sid/'players-v2.jsonl',people)
        write_rows(missing/sid/'players-v2.jsonl',partial)
        shutil.copyfile(OUT/f'{sid}-motion.jsonl',root/f'{sid}-motion.jsonl')
        print('C selected',sid,'reuse',len(borrowed),'new crops',new_count,flush=True)
        if not (missing/f'pose-dense-{sid}/result.json').exists():
            adapted('pose.py',['--sample',sid,'--output','pose-dense-'+sid,
                '--device','cpu','--min-size','192','--max-size','384','--stride','6','--offset','0','--proposals','200'],missing)
        inferred=rows(missing/f'pose-dense-{sid}/pose.jsonl')
        new={(r['frame_id'],p['player_id']):p for r in inferred for p in r['people']}
        complete=[]
        for r in people:
            pp=[]
            for p in r['players']:
                key=(r['frame_id'],p['player_id'])
                pp.append(borrowed[key] if key in borrowed else new[key])
            complete.append(dict(frame_id=r['frame_id'],timestamp_ms=r['timestamp_ms'],people=pp))
        write_rows(out/'pose.jsonl',complete)
        write(out/'result.json',dict(sample=c['sample'],settings=meta['settings'],weights_sha256=weight_hash,
            output_sha256=sha(out/'pose.jsonl'),source_sha256=sha(root/sid/'players-v2.jsonl'),
            reused_crops=len(borrowed),inferred_crops=new_count,
            original_pose=str((original/'pose.jsonl').relative_to(R)),original_pose_sha256=sha(original/'pose.jsonl'),
            new_pose=str((missing/f'pose-dense-{sid}/pose.jsonl').relative_to(R)),
            new_pose_sha256=sha(missing/f'pose-dense-{sid}/pose.jsonl')))
    if not (root/'flow/source.json').exists():
        adapted('pose_local_flow.py',['--output','flow','--pose-prefix','pose-dense'],root)


def evaluate(pred, sample):
    from app.vision.rally_eval import evaluate_rallies,load_rally_annotations,load_rally_exclusions
    from compare_m1 import retained_time
    from duration_profiles import breakdown
    truth=load_rally_annotations(R/sample['annotation'])
    ex=load_rally_exclusions(R/sample['annotation'])
    ann=read(R/sample['annotation'])
    incomplete=[e['visible_range_ms'] for e in ann.get('incomplete_events',[])]
    def overlap(a,z,parts):
        return sum(max(0,min(z,y)-max(a,x)) for x,y in parts)
    partial_only=[p for p in pred if any(a<=p.start_ms<p.end_ms<=z for a,z in incomplete)]
    m=evaluate_rallies([p for p in pred if p not in partial_only],truth,excluded_events=ex)
    t=retained_time(pred,truth,ex,sample['duration_ms'])
    partial=sum(overlap(p.start_ms,p.end_ms,incomplete) for p in pred)
    t['retained_non_target_ms']-=partial
    t['non_target_ms']-=sum(z-a for a,z in incomplete)
    t['non_target_retention']=t['retained_non_target_ms']/t['non_target_ms']
    details=[dict(id=q.rally_id,start_ms=q.start_ms,end_ms=q.end_ms,
                  retained_ms=sum(max(0,min(q.end_ms,p.end_ms)-max(q.start_ms,p.start_ms)) for p in pred))
             for q in truth if q.review_status=='verified']
    return dict(metrics=m,retained_time=t,
                outside_ms=sum(p.end_ms-p.start_ms for p in pred)-t['retained_target_ms']-partial,
                incomplete_visible_ms=sum(z-a for a,z in incomplete),incomplete_kept_ms=partial,
                details=details,subsets={str(k):breakdown(pred,truth,m,k) for k in (3000,5000)})


def summarize(results):
    out={}
    for group in ('C1','C2'):
        rr=[r for r in results if r['source_id']==group]
        target=sum(r['retained_time']['target_ms'] for r in rr)
        out[group]=dict(retention=sum(r['retained_time']['retained_target_ms'] for r in rr)/target,
            outside_s=sum(r['outside_ms'] for r in rr)/1000,
            miss=sum(r['metrics']['missed_rally_count'] for r in rr),
            split=sum(r['metrics']['false_split_count'] for r in rr),
            merge=sum(r['metrics']['false_merge_count'] for r in rr),
            both=sum(r['metrics']['boundary_acceptance']['both_acceptable_count'] for r in rr),
            long_retention=sum(r['subsets']['5000']['retained_target_ms'] for r in rr)/sum(r['subsets']['5000']['target_ms'] for r in rr),
            incomplete_kept_s=sum(r['incomplete_kept_ms'] for r in rr)/1000)
    return out


def c_predict(a, raw, shifted, people, flights, cfg):
    """Keep existing region geometry; vary temporal support and short filtering."""
    config=replace(a.CandidateRallyConfig(**a.CONFIG),max_gap_ms=cfg['gap_ms'],
                   min_span_ms=cfg['span_ms'],min_observations=cfg['observations'])
    gated=a.gate(raw,250,1600,cfg['region_points'])
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
    grouped=a.candidate_intervals(gated,eof_ms=shifted[-1]['timestamp_ms'],config=config)
    if cfg.get('internal_only'):
        outer=a.candidate_intervals(original_gated,eof_ms=shifted[-1]['timestamp_ms'],config=config)
        pieces=[]
        for p in outer:
            children=[q for q in grouped if p.start_ms<=q.start_ms<q.end_ms<=p.end_ms]
            # Weak evidence at an outside edge alone does not move that edge.
            # Only a gap separating multiple sustained groups triggers a split.
            if len(children)<2:
                pieces.append(p)
            else:
                for i,q in enumerate(children):
                    pieces.append(a.RallyInterval(0,p.start_ms if i==0 else q.start_ms,
                        p.end_ms if i==len(children)-1 else q.end_ms,p.emitted_at_ms))
        grouped=[replace(p,rally_id=i+1) for i,p in enumerate(pieces)]
        # Short-event continuity is measured in the original real observations.
        gated=original_gated
    arc, arc_dec=a.arc_delete(raw,grouped)
    checks=a.decisions([asdict(p) for p in arc],flights,people)
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
    expanded,extensions=a.continuation(kept,flights,people,True)
    eligible=[p for p in expanded if p['end_ms']-p['start_ms']>3000 or cfg['short']=='all' or (cfg['short']=='continuous' and continuous(p))]
    final=[]
    for p in eligible:
        d=a.decision(p,flights,.2)
        if d['delete']:continue
        trimmed,detail=a.trim(p,flights)
        final.append(a.RallyInterval(len(final)+1,trimmed['start_ms'],trimmed['end_ms'],trimmed['emitted_at_ms']))
    return final,dict(grouped=[asdict(p) for p in grouped],short=decisions,arc=arc_dec,extension=extensions)


def compare_c(adaptive=False,contact=False,density=False,edges=False,internal=False,short=False):
    a=module('c_original_replay',B/'a1-c-parameters-20261017/replay.py')
    cc=cases();loaded=[]
    for c in cc:
        s=c['sample'];native=rows(c['native']);shifted=rows(c['shifted'])
        people=rows(c['players']);flights=read(c['flights'])
        pred,trace=a.pipeline(native,shifted,people,flights)
        assert [asdict(p) for p in pred]==c['old']['predictions'],s['id']
        raw=a.candidate_motion(shifted,width=1920,config=a.CandidateRallyConfig(**a.CONFIG))
        loaded.append(dict(case=c,shifted=shifted,people=people,flights=flights,raw=raw))
    trials=[]
    choices=[dict(gap_ms=gap,region_points=points,span_ms=span,observations=obs,short=short)
             for gap,points,(span,obs),short in itertools.product(
                 (1200,1600,2000,2400),(4,8),((1600,18),(800,12)),('old','continuous','all'))]
    if adaptive:
        choices=[dict(gap_ms=2400,region_points=points,span_ms=800,observations=12,
                      short=short,person_speed=speed,person_window_ms=window)
                 for points,short,speed,window in itertools.product(
                     (4,8),('continuous','all'),(.04,.08,.12,.2),(1200,2000,3000))]
    if contact:
        choices=[dict(gap_ms=2400,region_points=8,span_ms=800,observations=12,
                      short=short,contact_window_ms=window,contact_distance=distance,fit_rms=rms)
                 for short,window,distance,rms in itertools.product(
                     ('continuous','all'),(2400,4000,6000),(0.2,0.4,0.6),(18,30))]
    if density:
        choices=[dict(gap_ms=2400,region_points=8,span_ms=800,observations=12,
                      short=short,density_window_ms=window,density=level)
                 for short,window,level in itertools.product(
                     ('continuous','all'),(1000,2000,3000,4000),(.2,.3,.4,.5,.6))]
    if edges:
        choices=[dict(gap_ms=2400,region_points=8,span_ms=800,observations=12,
                      short=short,density_window_ms=window,density=level,density_edge_ms=edge)
                 for short,window,level,edge in itertools.product(
                     ('continuous','all'),(1000,2000),(.2,.3,.4),(400,800,1200))]
    if internal:
        choices=[dict(gap_ms=2400,region_points=8,span_ms=800,observations=12,
                      short=short,density_window_ms=window,density=level,internal_only=True)
                 for short,window,level in itertools.product(
                     ('old','continuous','all'),(1000,2000),(.2,.3,.4))]
    if short:
        choices=[dict(gap_ms=2400,region_points=8,span_ms=800,observations=12,
                      short='continuous',density_window_ms=2000,density=.4,internal_only=True,
                      continuous_fraction=fraction,continuous_gap_ms=gap)
                 for fraction,gap in itertools.product((.65,.75,.85,.95),(100,200,400))]
    for i,cfg in enumerate(choices):
        results=[]
        for d in loaded:
            s=d['case']['sample']
            pred,trace=c_predict(a,d['raw'],d['shifted'],d['people'],d['flights'],cfg)
            assert all(p.start_ms<p.end_ms for p in pred)
            assert all(x.end_ms<z.start_ms for x,z in zip(pred,pred[1:]))
            results.append(dict(sample_id=s['id'],source_id=s['source_id'],predictions=[asdict(p) for p in pred],trace=trace,**evaluate(pred,s)))
        trials.append(dict(id=i,config=cfg,results=results,summary=summarize(results)))
        if i%12==0:print('C trial',i,flush=True)
    write(OUT/('c-short-trials.json' if short else 'c-internal-trials.json' if internal else 'c-edge-trials.json' if edges else 'c-density-trials.json' if density else 'c-contact-trials.json' if contact else 'c-person-trials.json' if adaptive else 'c-trials.json'),trials)
    for t in sorted(trials,key=lambda t:(t['summary']['C2']['miss'],t['summary']['C2']['merge'],t['summary']['C2']['outside_s']))[:8]:
        print(t['id'],t['config'],t['summary'],flush=True)


def compare_d(c_selected=False):
    d=module('frozen_d_person_context',R/'backend/tests/rally_benchmark/compare_d_person_context.py')
    expected=read(R/'docs/experiments/d-person-context-20261018.json')
    assert d.CONFIG==expected['candidate_config']
    assert d.BASE==expected['base_config'] and d.OPTIONS==expected['base_options']
    for path,wanted in expected['code_sha256'].items():
        assert sha(R/path)==wanted,path
    # Reuse the exact D foot calculation, changing only its input path lookup.
    foot=inspect.getsource(d.add_feet)
    old=next(l for l in foot.splitlines() if 'path=(OLD/' in l)
    foot=foot.replace(old," s=case['sample'];d=case['data'];ts=d['times'];path=case['players_path']")
    exec(compile(foot,str(R/'backend/tests/rally_benchmark/compare_d_person_context.py'),'exec'),d.__dict__)
    results=[]
    root=OUT/'c-selected' if c_selected else OUT
    for c in cases():
        s=c['sample'];path=root/f"flow/{s['id']}-signals.npz"
        with np.load(path) as z:data={k:z[k] for k in z.files}
        d.add_feet(dict(sample=s,data=data,players_path=root/s['id']/'players-v2.jsonl'))
        pred,trace=d.predict_candidate(data,s['duration_ms'],d.CONFIG)
        assert all(0<=p.start_ms<p.end_ms<=s['duration_ms'] for p in pred)
        assert all(a.end_ms<b.start_ms for a,b in zip(pred,pred[1:]))
        results.append(dict(sample_id=s['id'],source_id=s['source_id'],predictions=[asdict(p) for p in pred],
                            trace=trace,**evaluate(pred,s)))
    report=dict(config=d.CONFIG,base_config=d.BASE,results=results,summary=summarize(results),
                adapted_foot_sha256=hashlib.sha256(foot.encode()).hexdigest(),
                original_d_script_sha256=sha(R/'backend/tests/rally_benchmark/compare_d_person_context.py'),
                original_d_result_sha256=sha(R/'docs/experiments/d-person-context-20261018.json'))
    write(OUT/('d-c-selected.json' if c_selected else 'd-direct.json'),report)
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2),flush=True)


def report():
    a=module('c_report_replay',B/'a1-c-parameters-20261017/replay.py')
    selected=read(OUT/'c-short-trials.json')[2]
    baseline=[];candidate=[];cc=cases()
    for c in cc:
        s=c['sample'];native=rows(c['native']);shifted=rows(c['shifted'])
        people=rows(c['players']);flights=read(c['flights'])
        old,trace=a.pipeline(native,shifted,people,flights)
        assert [asdict(p) for p in old]==c['old']['predictions']
        raw=a.candidate_motion(shifted,width=1920,config=a.CandidateRallyConfig(**a.CONFIG))
        new,decisions=c_predict(a,raw,shifted,people,flights,selected['config'])
        expected=next(r for r in selected['results'] if r['sample_id']==s['id'])
        assert [asdict(p) for p in new]==expected['predictions']
        for dest,pred,details in [(baseline,old,trace),(candidate,new,decisions)]:
            dest.append(dict(sample_id=s['id'],source_id=s['source_id'],predictions=[asdict(p) for p in pred],trace=details,**evaluate(pred,s)))
    direct=read(OUT/'d-direct.json')
    selected_people=read(OUT/'d-c-selected.json')
    variants=[dict(id='baseline',label='C原方案',results=baseline,summary=summarize(baseline)),
              dict(id='candidate',label='C本轮候选',config=selected['config'],results=candidate,summary=summarize(candidate)),
              dict(id='d_direct',label='D整套原样使用',config=direct['config'],results=direct['results'],summary=direct['summary']),
              dict(id='d_c_selected',label='C选人＋D判断',config=selected_people['config'],results=selected_people['results'],summary=selected_people['summary'])]
    files=[];attempts=[]
    for name in ('c-trials','c-person-trials','c-contact-trials','c-density-trials','c-edge-trials','c-internal-trials','c-short-trials'):
        path=OUT/(name+'.json');tt=read(path);files.append(path)
        attempts.append(dict(path=str(path.relative_to(R)),sha256=sha(path),count=len(tt),
                             trials=[dict(id=t['id'],config=t['config'],summary=t['summary']) for t in tt]))
    for c in cc:
        s=c['sample'];sid=s['id']
        files += [R/s['annotation'],c['native'],c['shifted'],c['people'],c['players'],c['flights'],
                  OUT/sid/'players-v2.jsonl',OUT/sid/'selection-v2.json',OUT/sid/'feature-source.json',
                  OUT/f'pose-dense-{sid}/pose.jsonl',OUT/f'pose-dense-{sid}/result.json',OUT/f'flow/{sid}-signals.npz']
        files += [OUT/f'c-selected/{sid}/players-v2.jsonl',OUT/f'c-selected/pose-dense-{sid}/pose.jsonl',
                  OUT/f'c-selected/pose-dense-{sid}/result.json',OUT/f'c-selected/flow/{sid}-signals.npz']
    result=dict(date='2026-10-19',status='C1_C2_tuning_and_frozen_D_transfer',selected_c_config=selected['config'],
                samples=[c['sample'] for c in cc],variants=variants,attempts=attempts,
                attempt_count=sum(t['count'] for t in attempts),annotation_changed=False,
                d_rule_tuned=False,new_model_weights=False,
                model_inference=dict(c_rule=False,d_original_people=True,d_c_people_missing_crops=True),
                input_sha256={str(p.relative_to(R)):sha(p) for p in files},
                code_sha256={str(p.relative_to(R)):sha(p) for p in [Path(__file__),R/'backend/tests/rally_benchmark/compare_d_person_context.py',B/'a1-c-parameters-20261017/replay.py',D/'pose.py',D/'pose_local_flow.py',D/'features.py',D/'players_v2.py']},
                limits=['C1/C2均已参与本轮调试，不是独立验收。','D路线补跑已有CPU关节模型及画面运动；原C路线只复用缓存。',
                        'D原样自动选人可能选入背景球员；本轮未用人工回合标签纠正选人。',
                        'C2只确认所列条目，标注外时长用于诊断；片尾未完可见时间单列，不猜真实终点。',
                        '多次尝试含等效配置，不是独立验证；最终C候选重新复现后计分。',
                        '两条路线均为离线实验，使用后续观测，不宣称实时或完整处理性能。'])
    write(OUT/'comparison.json',result)
    write(R/'docs/experiments/c2-recovery-and-d-transfer-20261019.json',result)
    viewer=module('c_fixed_viewer',R/'.agents/skills/review-video-results/scripts/review.py')
    shown=[v for v in variants if v['id']!='d_direct']
    data=dict(schema_version=1,title='C组：原方案、C改进与沿用C选人的D判断',primary_track='candidate',
        note='同一批已确认标注。蓝色为C本轮候选，灰色为C原方案，紫色为沿用C选人的D判断（D参数不变）；青色仅为C2已确认片尾对打的可见范围，真实终点未知。C2标注外内容未全部确认，不自动当成误报。',
        tracks=[dict(id='truth',label='人工确认完整回合',role='truth'),
                dict(id='candidate',label='C本轮候选',role='prediction'),
                dict(id='baseline',label='C原方案',role='prediction'),
                dict(id='d_c_selected',label='C选人＋D判断',role='prediction'),
                dict(id='incomplete',label='已确认片尾对打可见范围（非算法）',role='prediction'),
                dict(id='excluded',label='已确认可排除事件',role='excluded')],clips=[],summary=[])
    data['summary']=[dict(label='C2 '+v['label']+'对打保留',value=f"{v['summary']['C2']['retention']:.2%}") for v in shown]
    for c in sorted(cc,key=lambda c:(c['sample']['id']!='C2',c['sample']['id'])):
        s=c['sample'];sid=s['id'];ann=read(R/s['annotation'])
        offset=c['old']['media_time_offset_ms']
        if offset is None:
            v=read(R/s['validation'])
            assert sha(R/s['validation'])==s['validation_sha256']
            offset=v['first_decoded_clip_pts_s']*1000
        truth=[dict(id=str(q['rally_id']),label=f"第{q['rally_id']}回合",start_ms=q['start_ms'],end_ms=q['end_ms'],review_status='verified') for q in ann['segments'] if q['review_status']=='verified']
        exclusions=[dict(id=e['event_id'],start_ms=e['range_ms'][0],end_ms=e['range_ms'][1],review_status='human_confirmed') for e in ann.get('excluded_events',[]) if e['review_status']=='human_confirmed']
        intervals=dict(truth=truth,excluded=exclusions,
            incomplete=[dict(id=e['event_id'],start_ms=e['visible_range_ms'][0],end_ms=e['visible_range_ms'][1]) for e in ann.get('incomplete_events',[])])
        cards=[]
        for variant in shown:
            r=next(r for r in variant['results'] if r['sample_id']==sid)
            intervals[variant['id']]=[dict(id=str(p['rally_id']),start_ms=p['start_ms'],end_ms=p['end_ms']) for p in r['predictions']]
            cards.append(dict(label=variant['label']+'对打保留',value=f"{r['retained_time']['target_retention']:.2%}"))
        issues=[]
        if sid=='C2':
            issues=[dict(label='第3至5回合：检查是否拆开间歇',start_ms=22000,end_ms=90000),
                    dict(label='第1回合：起止仍少留',start_ms=0,end_ms=7000),
                    dict(label='第7回合：短候选保留情况',start_ms=109000,end_ms=117000),
                    dict(label='第9/10回合：漏掉及少留',start_ms=144000,end_ms=164000),
                    dict(label='片尾对打：真实终点未知',start_ms=166000,end_ms=180000)]
        elif sid=='C1-02':
            issues=[dict(label='C候选新增的标注外短输出',start_ms=29000,end_ms=41000)]
        elif sid=='C1-04':
            issues=[dict(label='C候选新增的标注外短输出',start_ms=49000,end_ms=55000)]
        data['clips'].append(dict(id=sid,title=sid,video=str(R/s['video']),duration_ms=s['duration_ms'],
            media_offset_ms=offset,intervals=intervals,issues=issues,summary=cards,
            note='同一份人工确认标注，原始视频及首帧偏移不变。查看不代表确认新方案。'))
    viewer.prepare(data,OUT)
    write(OUT/'review.json',data)
    raw=copy.deepcopy(data)
    raw['title']='C组：D整套原样使用的对照'
    raw['note']='紫色是D整套原样使用，包含D原有自动选人；在部分C镜头中选入了主场之外的人。其余颜色、人工标注和C方案与主对照页相同。'
    raw['summary'][-1]=dict(label='C2 D整套原样对打保留',value=f"{direct['summary']['C2']['retention']:.2%}")
    next(t for t in raw['tracks'] if t['id']=='d_c_selected').update(id='d_direct',label='D整套原样使用')
    for clip in raw['clips']:
        clip['intervals'].pop('d_c_selected')
        r=next(r for r in direct['results'] if r['sample_id']==clip['id'])
        clip['intervals']['d_direct']=[dict(id=str(p['rally_id']),start_ms=p['start_ms'],end_ms=p['end_ms']) for p in r['predictions']]
        clip['summary'][-1]=dict(label='D整套原样对打保留',value=f"{r['retained_time']['target_retention']:.2%}")
    viewer.prepare(raw,OUT)
    write(OUT/'review-d-direct.json',raw)
    print(json.dumps({v['id']:v['summary'] for v in variants},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['observe-d','observe-c-selected','compare-c','compare-c-person','compare-c-contact','compare-c-density','compare-c-edges','compare-c-internal','compare-c-short','compare-d','compare-d-c-selected','report'])
    p.add_argument('--samples',nargs='+',help='Observe only these clips; score still requires all five.')
    a=p.parse_args()
    if a.stage=='observe-d':observe_d(a.samples)
    elif a.stage=='observe-c-selected':observe_c_selected()
    elif a.stage=='compare-c':compare_c()
    elif a.stage=='compare-c-person':compare_c(True)
    elif a.stage=='compare-c-contact':compare_c(contact=True)
    elif a.stage=='compare-c-density':compare_c(density=True)
    elif a.stage=='compare-c-edges':compare_c(edges=True)
    elif a.stage=='compare-c-internal':compare_c(internal=True)
    elif a.stage=='compare-c-short':compare_c(short=True)
    elif a.stage=='compare-d':compare_d()
    elif a.stage=='compare-d-c-selected':compare_d(True)
    elif a.stage=='report':report()
