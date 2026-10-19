"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import math
import numpy as np

def contact_points(points,people):
 ts=np.array([r['timestamp_ms'] for r in people]);events=[]
 for p in points:
  k=int(np.searchsorted(ts,p['t']));k=min((max(0,k-1),min(len(ts)-1,k)),key=lambda i:abs(ts[i]-p['t']))
  if abs(ts[k]-p['t'])>110:continue
  choices=[]
  for person in people[k]['players']:
   b=person['box'];h=b['y2']-b['y1'];dx=max(b['x1']-p['x'],p['x']-b['x2'],0);dy=max(b['y1']-p['y'],p['y']-(b['y2']-.15*h),0)
   d=math.hypot(dx,dy)/h
   if d<=.4:choices.append((d,person))
  choices.sort(key=lambda v:v[0])
  # Overlapping projected bodies cannot establish which person is involved.
  if not choices or (len(choices)>1 and choices[1][0]-choices[0][0]<.1):continue
  d,person=choices[0];events.append(dict(t=p['t'],i=p['i'],player_id=person['player_id'],distance_body_heights=d,person_frame_id=people[k]['frame_id'],box_index=person['box_index']))
 return events

def moving_points(path):
 marked=set()
 for end in range(2,len(path)):
  start=max(0,end-7);p=path[start:end+1];xy=np.array([[x['x'],x['y']] for x in p]);span=p[-1]['t']-p[0]['t'];extent=np.linalg.norm(xy.max(0)-xy.min(0))
  if span>=60 and extent>=80 and extent/span*1000>=100:marked.update(range(start,end+1))
 return [p for i,p in enumerate(path) if i in marked]

def fit(points):
 t=np.array([(p['t']-points[0]['t'])/1000 for p in points]);xy=np.array([[p['x'],p['y']] for p in points]);x=np.column_stack([np.ones(len(t)),t,t*t]);c=np.linalg.lstsq(x,xy,rcond=None)[0];e=np.linalg.norm(x@c-xy,axis=1)
 return dict(rms=float(np.sqrt(np.mean(e*e))),maximum=float(e.max()),acceleration=(2*c[2]).tolist(),coefficient=c.tolist())

def split(points):
 pieces=[];part=[]
 for p in points:
  trial=part+[p];good=len(trial)<4 or (p['t']-trial[0]['t']<=3000 and fit(trial)['rms']<=18 and fit(trial)['maximum']<=40)
  if not good:
   if len(part)>=3:pieces.append(part)
   part=part[-1:]+[p]
  else:part=trial
 if len(part)>=3:pieces.append(part)
 return pieces
