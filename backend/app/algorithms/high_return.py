"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .attached_motion import bodies
import math

def near_top(f,person,people,side):
 p=f['moving'][0 if side=='start' else -1]
 for b in bodies(people,p['t']):
  if b['player_id']==person:
   box=b['box'];h=box['y2']-box['y1']
   return p['y']<=box['y1']+.15*h
 return False

def mean_velocity(f):
 a,z=f['moving'][0],f['moving'][-1];dt=(z['t']-a['t'])/1000
 return [(z[k]-a[k])/dt for k in ('x','y')]

def continuation(pred,flights,people,high_return):
 output=[];decisions=[]
 for index,p in enumerate(pred):
  original=p['end_ms'];cap=min(original+4000,pred[index+1]['start_ms'] if index+1<len(pred) else math.inf);end=original;links=[]
  # This does not start or rescue a short output. A base interval of at least 5s
  # is required before adding evidence to its right edge.
  if p['end_ms']-p['start_ms']>=5000:
   for f in flights:
    ps=f['moving'];a,z=ps[0]['t'],ps[-1]['t']
    if f['contacts'] and a<=original<z<cap and any(original-500<=q['t']<=original for q in ps):
     end=max(end,z);links.append(dict(type='same_observed_flight',flight_id=f['flight_id'],end_ms=z))
   if high_return:
    outgoing=[f for f in flights if f['contacts'] and original-1500<=f['moving'][-1]['t']<=original and mean_velocity(f)[1]<=-100]
    incoming=[f for f in flights if f['contacts'] and original<f['moving'][-1]['t']<cap and f['moving'][0]['t']>original and mean_velocity(f)[1]>=100]
    for a in outgoing:
     for z in incoming:
      aa,zz=a['moving'][-1],z['moving'][0];gap=zz['t']-aa['t'];common={q['player_id'] for q in a['contacts']} & {q['player_id'] for q in z['contacts']}
      if not 0<gap<=4000 or abs(zz['x']-aa['x'])>576:continue
      valid=[ident for ident in common if near_top(a,ident,people,'end') and near_top(z,ident,people,'start')]
      if not valid:continue
      last=z['moving'][-1]['t'];end=max(end,last);links.append(dict(type='up_then_down_same_selected_person',outgoing_flight=a['flight_id'],incoming_flight=z['flight_id'],common_player_ids=valid,gap_ms=gap,endpoint_dx_px=abs(zz['x']-aa['x']),end_ms=last))
  output.append(dict(p,end_ms=end));decisions.append(dict(original=p,new_end_ms=end,links=links))
 return output,decisions
