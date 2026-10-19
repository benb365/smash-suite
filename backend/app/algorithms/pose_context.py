"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .player_paths import height
from .trials import series
import numpy as np

def angle(a,b,c):
    u=a-b;v=c-b;return float(np.degrees(np.arccos(np.clip(u@v/max(1e-6,np.linalg.norm(u)*np.linalg.norm(v)),-1,1))))

def extract(rows,people,ball):
    ts=np.array([r['timestamp_ms'] for r in rows]);n=len(ts);arm=np.zeros((n,2));high=np.zeros((n,2));ready=np.zeros((n,2),bool);pickup=np.zeros((n,2),bool);speed=np.zeros((n,2));present=np.zeros((n,2),bool);last={}
    for i,row in enumerate(rows):
        for p in row['people']:
            if p['selected'] is None:continue
            k=p['player_id'];q=p['selected'];xy=np.array(q['keypoints'])[:,:2];conf=np.array(q['joint_scores']);h=height(p['box']);hips=(xy[11]+xy[12])/2;shoulders=(xy[5]+xy[6])/2
            valid=np.array([min(conf[5],conf[9]),min(conf[6],conf[10])])>=4
            wrists=xy[[9,10]];rel=wrists-xy[[5,6]]
            raised=(wrists[:,1]<shoulders[1]+.12*h)|(np.abs(rel[:,0])>.18*h)
            hands=bool(np.any(valid&(wrists[:,1]<hips[1]-.04*h)))
            feet=bool(min(conf[15:17])>=3 and abs(xy[15,0]-xy[16,0])>.14*h)
            knees=bool(min(conf[11:17])>=3 and max(angle(xy[11],xy[13],xy[15]),angle(xy[12],xy[14],xy[16]))<165)
            ready[i,k]=hands and (feet or knees or bool(np.any(valid&raised)))
            pickup[i,k]=bool(hips[1]-shoulders[1]<.12*h and not hands)
            present[i,k]=True
            if k in last:
                old=last[k];dt=(row['timestamp_ms']-old['t'])/1000;hh=(h+old['h'])/2
                if dt<=.6:
                    values=np.linalg.norm(rel-old['rel'],axis=1)/hh/dt;ok=valid&old['valid']&(values<3)
                    arm[i,k]=float(np.max(np.where(ok,values,0)))
                    high[i,k]=float(np.max(np.where(ok&(raised|old['raised']),values,0)))
                    speed[i,k]=float(np.linalg.norm(hips-old['hips']))/hh/dt
            last[k]=dict(t=row['timestamp_ms'],h=h,rel=rel,valid=valid,raised=raised,hips=hips)
    s=series(people,ball);idx=np.array([int(np.argmin(abs(s['times']-t))) for t in ts]);assert np.max(abs(s['times'][idx]-ts))<.001
    return dict(times=ts,arm=arm,high=high,ready=ready,pickup=pickup,speed=speed,present=present,ball=s['ball'][idx])
