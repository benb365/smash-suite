"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import numpy as np

def body_motion(flow,b,dt):
    h=(b['y2']-b['y1'])/2
    x1,x2=np.clip(np.round(np.array([b['x1'],b['x2']])/2).astype(int),0,flow.shape[1])
    y1,y2=np.clip(np.round(np.array([b['y1'],b['y2']])/2).astype(int),0,flow.shape[0])
    p=flow[y1:y2,x1:x2]; hh,ww=p.shape[:2]
    if hh<8 or ww<4:return None
    upper=p[int(.08*hh):int(.68*hh)]
    core=p[int(.25*hh):int(.65*hh),int(.3*ww):max(int(.7*ww),int(.3*ww)+1)]
    torso=np.median(core.reshape(-1,2),axis=0)
    return dict(upper=float(np.percentile(np.linalg.norm(upper,axis=2),85)/h/dt),
                articulation=float(np.percentile(np.linalg.norm(upper-torso,axis=2),85)/h/dt),
                lower=float(np.percentile(np.linalg.norm(p[int(.65*hh):],axis=2),80)/h/dt),
                torso=(torso/h/dt).tolist())
