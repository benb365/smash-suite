"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations


def trim(p,flights):
 a,z=p['start_ms'],p['end_ms'];supported=[q['t'] for f in flights if f['contacts'] for q in f['moving'] if a<=q['t']<min(z,a+2000)]
 start=min(supported,default=a);move=bool(z-a>=5000 and start>a+500)
 return dict(p,start_ms=start if move else a),dict(original=p,new_start_ms=start if move else a,first_supported_ms=start)
