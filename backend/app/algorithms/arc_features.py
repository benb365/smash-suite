"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import numpy as np

def features(points):
 if len(points)<3:return dict(count=len(points),fit=None)
 ts=np.array([p['timestamp_ms'] for p in points]);xy=np.array([[p['point']['x'],p['point']['y']] for p in points]);t=(ts-ts.mean())/1000
 # A short image-space parabola is a hypothesis, not physical 3D reconstruction.
 X=np.column_stack([np.ones(len(t)),t,t*t]);coeff=np.linalg.lstsq(X,xy,rcond=None)[0];errors=np.linalg.norm(X@coeff-xy,axis=1)
 # Linear horizontal + quadratic vertical is a stricter independent diagnostic.
 lin=np.linalg.lstsq(X[:,:2],xy[:,0],rcond=None)[0];strict=np.column_stack([X[:,:2]@lin,(X@coeff)[:,1]]);se=np.linalg.norm(strict-xy,axis=1)
 gaps=np.diff(ts)
 return dict(count=len(points),start_ms=float(ts[0]),end_ms=float(ts[-1]),span_ms=float(ts[-1]-ts[0]),max_gap_ms=float(max(gaps)),extent_px=float(np.linalg.norm(np.ptp(xy,axis=0))),fit=dict(rms_px=float(np.sqrt(np.mean(errors**2))),max_px=float(max(errors)),strict_rms_px=float(np.sqrt(np.mean(se**2))),acceleration_px_s2=(2*coeff[2]).tolist(),coefficients=coeff.tolist()))
