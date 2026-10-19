"""Derive the reviewed D foot-motion signals from actual tracked boxes."""
import numpy as np

def add_foot_signals(d, rows):
 ts=d['times']
 if len(rows)!=len(ts) or any(abs(r['timestamp_ms']-t)>=.001 for r,t in zip(rows,ts)):
  raise ValueError("Foot observations must match pose timestamps.")
 pos=np.full((len(ts),2,2),np.nan);height=np.full((len(ts),2),np.nan)
 for i,r in enumerate(rows):
  for p in r['players']:
   k=p['player_id'];b=p['box'];pos[i,k]=[(b['x1']+b['x2'])/2,b['y2']];height[i,k]=b['y2']-b['y1']
 smooth=np.full_like(pos,np.nan);v=np.zeros((len(ts),2))
 for i in range(len(ts)):
  for k in (0,1):
   if not np.isfinite(pos[i,k]).all():continue
   valid=pos[max(0,i-2):i+3,k];valid=valid[np.isfinite(valid).all(axis=1)]
   if len(valid)>=3:smooth[i,k]=np.median(valid,axis=0)
 for i in range(1,len(ts)):
  for k in (0,1):
   if np.isfinite(smooth[i-1:i+1,k]).all():
    v[i,k]=np.linalg.norm(smooth[i,k]-smooth[i-1,k])/np.mean(height[i-1:i+1,k])/(ts[i]-ts[i-1])*1000
 d['foot_speed']=v;d['foot_valid']=np.isfinite(smooth).all(axis=2)

 return d
