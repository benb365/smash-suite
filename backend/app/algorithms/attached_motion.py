"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import numpy as np

def bodies(people,t):
 times=np.array([r['timestamp_ms'] for r in people]);k=int(np.searchsorted(times,t));result=[]
 for ident in (0,1):
  if k<len(people) and times[k]==t:
   candidates=[p for p in people[k]['players'] if p['player_id']==ident]
   if candidates:result.append(dict(player_id=ident,box=candidates[0]['box'],person_frame_ids=[people[k]['frame_id']],weight=0))
  elif 0<k<len(people) and times[k]-times[k-1]<=400:
   a=next((p['box'] for p in people[k-1]['players'] if p['player_id']==ident),None);z=next((p['box'] for p in people[k]['players'] if p['player_id']==ident),None)
   if a is not None and z is not None:
    w=(t-times[k-1])/(times[k]-times[k-1]);result.append(dict(player_id=ident,box={key:(1-w)*a[key]+w*z[key] for key in ('x1','y1','x2','y2')},person_frame_ids=[people[k-1]['frame_id'],people[k]['frame_id']],weight=float(w)))
 return result
