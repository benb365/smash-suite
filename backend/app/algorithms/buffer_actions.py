"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .trials import RallyInterval

def padded(pred,before,after,duration):
    out=[]
    for p in pred:
        a=max(0,p['start_ms']-before);z=min(duration,p['end_ms']+after)
        if out and a<=out[-1][1]:out[-1][1]=max(z,out[-1][1])
        else:out.append([a,z])
    return [RallyInterval(i+1,a,z,duration) for i,(a,z) in enumerate(out)]
