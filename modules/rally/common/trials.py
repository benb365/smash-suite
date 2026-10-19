"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .player_paths import foot
from .player_paths import height
from modules.rally.types import RallyInterval
from scipy.ndimage import median_filter
import math
import numpy as np

def series(people,ball):
    times=np.array([r['timestamp_ms'] for r in people]);n=len(times)
    speed=np.zeros((n,2));upper=np.zeros((n,2));art=np.zeros((n,2));present=np.zeros((n,2),bool);last={}
    ballnear=np.zeros(n,int)
    for i,row in enumerate(people):
        for p in row['players']:
            k=p['player_id'];b=p['box'];present[i,k]=True;m=p['body_motion']
            if m:upper[i,k]=m['upper'];art[i,k]=m['articulation']
            if k in last:
                old=last[k];dt=(row['timestamp_ms']-old['t'])/1000
                if dt<=.5:speed[i,k]=float(np.linalg.norm(foot(b)-foot(old['box'])))/((height(b)+height(old['box']))/2)/dt
            last[k]=dict(t=row['timestamp_ms'],box=b)
    for r in ball:
        if not r['motion']:continue
        p=r['point'];k=int(np.searchsorted(times,r['timestamp_ms']));k=min((max(0,k-1),min(n-1,k)),key=lambda q:abs(times[q]-r['timestamp_ms']))
        if abs(times[k]-r['timestamp_ms'])>110:continue
        for person in people[k]['players']:
            b=person['box'];h=height(b);dx=max(b['x1']-p['x'],p['x']-b['x2'],0);dy=max(b['y1']-p['y'],p['y']-(b['y2']-.1*h),0)
            if math.hypot(dx,dy)/h<=.4:ballnear[k]+=1;break
    # A three-observation median rejects one noisy detection/flow frame.
    speed=np.column_stack([median_filter(speed[:,k],size=3,mode='nearest') for k in range(2)])
    upper=np.column_stack([median_filter(upper[:,k],size=3,mode='nearest') for k in range(2)])
    art=np.column_stack([median_filter(art[:,k],size=3,mode='nearest') for k in range(2)])
    return dict(times=times,speed=speed,upper=upper,articulation=art,present=present,ball=ballnear>=3)
