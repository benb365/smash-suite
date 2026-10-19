"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import cv2
import numpy as np

def gate(rows,y,near_ms,min_points):
    times=np.array([r['timestamp_ms'] for r in rows]);valid=np.array([r['motion'] for r in rows])
    # Main flight band from C1 reference frame, distinct from the ground court.
    # Upper points may continue existing evidence but cannot renew its timeout.
    poly=np.array([(600,y),(1450,y),(1920,1080),(0,1080)],np.float32)
    strong=np.array([r['motion'] and cv2.pointPolygonTest(poly,(r['point']['x'],r['point']['y']),False)>=0 for r in rows])
    st=times[strong];counts=np.searchsorted(st,times+200,side='right')-np.searchsorted(st,times-200,side='left')
    qualified=st[counts[strong]>=min_points]
    if len(qualified):
        idx=np.searchsorted(qualified,times);left=qualified[np.maximum(0,idx-1)];right=qualified[np.minimum(len(qualified)-1,idx)]
        keep=valid&(np.minimum(abs(times-left),abs(times-right))<=near_ms)
    else:keep=np.zeros(len(rows),bool)
    return [dict(r,motion=bool(k),main_court_observation=bool(s)) for r,k,s in zip(rows,keep,strong)]
