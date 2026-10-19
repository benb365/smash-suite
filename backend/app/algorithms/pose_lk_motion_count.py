"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .trials import RallyInterval
import numpy as np

def predict(s,c):
    ts=s['times'];motion=s[c['signal']];active=motion>=c['threshold'];ball=s['ball'];events=[]
    for i,k in zip(*np.where(active)):
        events.append(dict(t=float(ts[i]),start=float(ts[max(0,i-1)]),player=int(k)))
    events.sort(key=lambda e:e['t']);groups=[]
    for e in events:
        if not groups or e['t']-groups[-1][-1]['t']>c['gap_ms']:groups.append([e])
        else:groups[-1].append(e)
    support=(np.max(s['arm'],axis=1)>=c['threshold']*.5)|(np.min(s['ready'],axis=1)&(np.max(s['speed'],axis=1)>=.15))
    if c['ball']:support|=ball
    pred=[]
    for g in groups:
        a=g[0]['start'];z=g[-1]['t'];ids={e['player'] for e in g}
        ai=int(np.searchsorted(ts,a));zi=int(np.searchsorted(ts,z));hasball=bool(np.any(ball[ai:zi+1]))
        # Reject isolated arm observations rather than dropping an output by its length.
        # Four observations at 5fps do not imply four hits; simultaneous people count separately.
        if len(g)<c.get('minimum_actions',2) or z-a<800 or (len(ids)<2 and not(c['ball'] and hasball)):continue
        acap=a-c['extend'];zcap=z+c['extend']
        for i in range(ai-1,-1,-1):
            if ts[i]<acap or not support[i]:break
            a=float(ts[i])
        for i in range(zi+1,len(ts)):
            if ts[i]>zcap or not support[i]:break
            z=float(ts[i])
        if pred and a<=pred[-1][1]:pred[-1][1]=max(z,pred[-1][1])
        else:pred.append([a,z])
    return [RallyInterval(i+1,a,z,float(ts[-1])) for i,(a,z) in enumerate(pred)]
