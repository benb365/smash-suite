"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .seeded_source import predict
from collections import Counter
import math
import numpy as np

def moving(path):
 if len(path)<3 or path[-1]['t']-path[0]['t']<60:return False
 xy=np.array([[p['x'],p['y']] for p in path]);return np.linalg.norm(xy.max(0)-xy.min(0))>=80

def quality(path):
 span=path[-1]['t']-path[0]['t'];return len(path)-.35*max(0,span/33.36-len(path))+.2*sum(p['confidence'] for p in path)

def associate(rows,method,gap):
 active=[];finished=[]
 for ps in rows:
  if not ps:continue
  now=ps[0]['t'];old=[h for h in active if now-h[-1]['t']>gap];finished.extend(h for h in old if moving(h));active=[h for h in active if now-h[-1]['t']<=gap];new=[]
  for p in ps:
   options=[[p]]
   for h in active:
    dt=(now-h[-1]['t'])/1000
    if dt<=0:continue
    d=math.hypot(p['x']-h[-1]['x'],p['y']-h[-1]['y'])
    if d>4000*dt:continue
    if len(h)>1:
     guess=predict(h,now,method)
     if np.linalg.norm(np.array([p['x'],p['y']])-guess)>48+max(0,dt-.034)*150:continue
    options.append(h+[p])
   options.sort(key=quality,reverse=True);new.extend(options[:3])
  active.extend(new)
 finished.extend(h for h in active if moving(h));finished.sort(key=quality,reverse=True)
 used=set();out=[]
 for h in finished:
  keys={(p['i'],p['j']) for p in h}
  if keys&used:continue
  out.append(dict(track_id=len(out),points=h));used|=keys
 return out

def observed_candidates(a,b):
 counts=Counter()
 for r in a:counts.update({(round(p['x']/32)+dx,round(p['y']/32)+dy) for p in r['peaks'] for dx in (-1,0,1) for dy in (-1,0,1)})
 out=[]
 for i,(r,s) in enumerate(zip(a,b)):
  assert r['frame_id']==s['frame_id'] and r['timestamp_ms']==s['timestamp_ms']
  pp=[]
  for phase,row in enumerate((r,s)):
   for j,p in enumerate(row['peaks']):
    if p['confidence']<.5 or p['confidence']-2*abs(p['x']/1920-.5)<=0:continue
    if counts[(round(p['x']/32),round(p['y']/32))]/len(a)>=.1:continue
    pp.append(dict(p,i=i,t=r['timestamp_ms'],phase=phase,source_peak_index=j))
  pp.sort(key=lambda p:p['confidence'],reverse=True);kept=[]
  for p in pp:
   if not any(math.hypot(p['x']-q['x'],p['y']-q['y'])<=15 for q in kept):kept.append(p)
  out.append([dict(p,j=j) for j,p in enumerate(kept)])
 return out
