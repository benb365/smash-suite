"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .arc_features import features
from .region_gate import gate
from app.vision.candidate_rally import CandidateRallyConfig
from app.vision.candidate_rally import candidate_intervals
from app.vision.candidate_rally import candidate_motion
from app.vision.rally_stream import RallyInterval
from dataclasses import asdict
import cv2
import numpy as np

def arc_delete(motion,predictions):
 poly=np.array([(600,250),(1450,250),(1920,1080),(0,1080)],np.float32);strong=[a for a in motion if a['motion'] and cv2.pointPolygonTest(poly,(a['point']['x'],a['point']['y']),False)>=0];ts=np.array([a['timestamp_ms'] for a in strong]);qual=[a for a in strong if np.searchsorted(ts,a['timestamp_ms']+200,side='right')-np.searchsorted(ts,a['timestamp_ms']-200,side='left')>=8];kept=[];decisions=[]
 for p in predictions:
  f=features([a for a in qual if p.start_ms<=a['timestamp_ms']<=p.end_ms]);fit=f['fit'];drop=bool(fit and 1000<=f['span_ms']<=5000 and fit['acceleration_px_s2'][1]>0 and fit['strict_rms_px']<=48);decisions.append(dict(prediction=asdict(p),features=f,delete=drop))
  if not drop:kept.append(RallyInterval(len(kept)+1,p.start_ms,p.end_ms,p.emitted_at_ms))
 return kept,decisions
