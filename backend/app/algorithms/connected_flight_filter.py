"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import math

def decision(p,flights,distance=.2):
 a,z=p['start_ms'],p['end_ms'];pieces=[];strong=[]
 for f in flights:
  ps=[q for q in f['moving'] if a<=q['t']<=z];cs=[c for c in f['contacts'] if a<=c['t']<=z];close={c['i'] for c in cs if c['distance_body_heights']<=distance}
  if len(ps)>=3 and cs:pieces.append(dict(flight=f,points=ps,player_ids={c['player_id'] for c in cs}))
  if len(close)>=2 and len(ps)>=8 and ps[-1]['t']-ps[0]['t']>=300:strong.append(f)
 candidate=bool(z-a<=5000 and len(strong)==1 and strong[0]['fit']['rms']<=18 and strong[0]['fit']['acceleration'][1]>0);links=[]
 if candidate:
  primary=next(q for q in pieces if q['flight']['flight_id']==strong[0]['flight_id'])
  for other in pieces:
   if other is primary or not primary['player_ids'] & other['player_ids']:continue
   for left,right in ((primary,other),(other,primary)):
    end,start=left['points'][-1],right['points'][0];gap=start['t']-end['t'];delta=math.hypot(end['x']-start['x'],end['y']-start['y'])
    if 0<=gap<=400 and delta<=150:links.append(dict(from_flight=left['flight']['flight_id'],to_flight=right['flight']['flight_id'],from_point=end,to_point=start,gap_ms=gap,distance_px=delta,common_player_ids=sorted(left['player_ids'] & right['player_ids'])))
 return dict(prediction=p,strong_flight_ids=[f['flight_id'] for f in strong],single_flight_candidate=candidate,connected_flight_veto=links,delete=bool(candidate and not links))
