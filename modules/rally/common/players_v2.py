"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .player_paths import appearance
from .player_paths import foot
from .player_paths import height
from scipy.optimize import linear_sum_assignment
import itertools
import math
import numpy as np

def follow(rows,seeds):
    states=[dict(box=None,t=None,template=s['template'],seed=s['template'],height=s['height']) for s in seeds];out=[]
    for row in rows:
        t=row['timestamp_ms'];options=[]
        for st in states:
            choices=[(1.6,-1,None)]
            for j,b in enumerate(row['boxes']):
                ratio=height(b)/st['height']
                if not .45<=ratio<=2.2:continue
                ad=min(appearance(st['seed'],row['appearance'][j]),appearance(st['template'],row['appearance'][j]))
                if ad>.65:continue
                dt=math.inf if st['t'] is None else (t-st['t'])/1000
                dist=0 if st['box'] is None else float(np.linalg.norm(foot(b)-foot(st['box'])))/height(st['box'])
                if dt<=2 and dist>.6+1.8*dt:continue
                travel=0 if dt>2 else .25*dist/max(.3,math.sqrt(dt+.04))
                cost=travel+2*ad+.2*abs(math.log(ratio))-.1*b['confidence']
                choices.append((cost,j,dict(box=b,box_index=j,appearance_error=ad)))
            options.append(choices)
        pairs=[(a[0]+z[0],a,z) for a,z in itertools.product(*options) if a[1]<0 or z[1]<0 or a[1]!=z[1]]
        _,a,z=min(pairs,key=lambda q:q[0]);people=[]
        for i,c in enumerate((a,z)):
            if c[1]<0:continue
            person=dict(c[2],player_id=i);people.append(person);st=states[i]
            if person['appearance_error']<.4:st['template']=[(.9*np.array(x)+.1*np.array(y)).tolist() for x,y in zip(st['template'],row['appearance'][c[1]])]
            st.update(box=person['box'],t=t)
        out.append(dict(frame_id=row['frame_id'],timestamp_ms=t,players=people))
    return out

def select(states,rows):
    candidates=[];byid={r['frame_id']:r for r in rows}
    for s in states:
        ps=s['points']
        if len(ps)<10:continue
        h=float(np.median([height(p['box']) for p in ps]));xy=np.array([foot(p['box']) for p in ps]);extent=float(np.linalg.norm(np.percentile(xy,95,axis=0)-np.percentile(xy,5,axis=0)))/h
        exposure=sum(min(250,b['timestamp_ms']-a['timestamp_ms']) for a,b in zip(ps,ps[1:]))/1000
        if extent<.4:continue
        representatives=[ps[i] for i in np.linspace(0,len(ps)-1,min(32,len(ps))).astype(int)]
        descriptors=[byid[p['frame_id']]['appearance'][p['box_index']] for p in representatives]
        distances=np.array([[appearance(a,z) for z in descriptors] for a in descriptors])
        best=representatives[int(np.argmin(distances.mean(axis=1)))];template=byid[best['frame_id']]['appearance'][best['box_index']]
        candidates.append(dict(track_id=s['track_id'],observations=len(ps),height=h,extent_body_heights=extent,
                               observed_s=exposure,rank=exposure*min(3,extent),template=template,example=best,
                               frame_ids=[p['frame_id'] for p in ps]))
    pairs=[]
    for a,z in itertools.combinations(candidates,2):
        overlap=len(set(a['frame_ids'])&set(z['frame_ids']))
        if overlap<5 or appearance(a['template'],z['template'])<.25:continue
        score=(a['rank']+z['rank'])*math.sqrt(overlap/min(len(a['frame_ids']),len(z['frame_ids'])))
        pairs.append((score,a,z))
    assert pairs,'Cannot select two persistent moving people; no invented pair.'
    _,a,z=max(pairs,key=lambda v:v[0])
    # Identity numbers follow observed median person size, not a fixed image line.
    selected=sorted([a,z],key=lambda p:p['height'])
    return selected,sorted(candidates,key=lambda c:c['rank'],reverse=True)

def track_all(rows):
    states=[]
    for row in rows:
        t=row['timestamp_ms'];valid=[j for j,b in enumerate(row['boxes']) if height(b)>=60]
        active=[s for s in states if t-s['t']<=2000]
        costs=np.full((len(active),len(valid)+len(active)),1e6)
        for i,s in enumerate(active):
            dt=(t-s['t'])/1000;costs[i,len(valid)+i]=1.5
            for k,j in enumerate(valid):
                b=row['boxes'][j];ratio=height(b)/height(s['box']);dist=float(np.linalg.norm(foot(b)-foot(s['box'])))/height(s['box'])
                ad=appearance(s['template'],row['appearance'][j])
                if not .5<=ratio<=2 or dist>.5+1.5*dt or ad>.65:continue
                costs[i,k]=.5*dist/max(.3,math.sqrt(dt))+1.5*ad+.3*abs(math.log(ratio))
        used=set()
        if active:
            ii,jj=linear_sum_assignment(costs)
            for i,k in zip(ii,jj):
                if k>=len(valid) or costs[i,k]>=1.5:continue
                j=valid[k];s=active[i];used.add(j);b=row['boxes'][j]
                s['points'].append(dict(frame_id=row['frame_id'],timestamp_ms=t,box_index=j,box=b))
                s.update(box=b,t=t)
                if appearance(s['template'],row['appearance'][j])<.4:
                    s['template']=[(.9*np.array(a)+.1*np.array(z)).tolist() for a,z in zip(s['template'],row['appearance'][j])]
        for j in valid:
            if j in used:continue
            b=row['boxes'][j]
            states.append(dict(track_id=len(states),box=b,t=t,template=row['appearance'][j],points=[dict(frame_id=row['frame_id'],timestamp_ms=t,box_index=j,box=b)]))
    return states
