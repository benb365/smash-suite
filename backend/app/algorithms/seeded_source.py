"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import numpy as np

def predict(path,t,method):
    last=path[-1];xy=np.array([last['x'],last['y']]);dt=(t-last['t'])/1000
    if len(path)<2:return xy
    h=path[-8:];ts=np.array([(p['t']-last['t'])/1000 for p in h]);ys=np.array([[p['x'],p['y']] for p in h])
    if method=='quadratic' and len(h)>=4:
        X=np.column_stack([np.ones(len(h)),ts,ts*ts]);w=np.ones(len(h))
        # Huber reweighting: large deviations have less influence. A short local
        # curve is a predictor, not a claim that an entire shuttle flight is parabolic.
        for _ in range(3):
            coef=np.linalg.lstsq(X*w[:,None],ys*w[:,None],rcond=None)[0]
            error=np.linalg.norm(X@coef-ys,axis=1);w=np.sqrt(np.minimum(1,12/np.maximum(error,.001)))
        return np.array([1,dt,dt*dt])@coef
    elapsed=(h[-1]['t']-h[-2]['t'])/1000
    return xy+(ys[-1]-ys[-2])/elapsed*dt
