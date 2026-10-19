"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations


def decisions(pred,flights,people):
 result=[]
 for p in pred:
  a,z=p['start_ms'],p['end_ms'];fs=[f for f in flights if f['contacts'] and any(a<=q['t']<=z for q in f['moving'])];contacts=[c for f in fs for c in f['contacts'] if a<=c['t']<=z];frames={c['i'] for c in contacts};ids={c['player_id'] for c in contacts};samples=[r for r in people if a<=r['timestamp_ms']<=z];coverage=sum(len(r['players'])==2 for r in samples)/max(1,len(samples));contactspan=max((c['t'] for c in contacts),default=0)-min((c['t'] for c in contacts),default=0)
  # Missing ball points alone never trigger removal. Positive observed flight
  # support near just one selected player is the hypothesis being tested.
  drop=bool(z-a<=5000 and coverage>=.8 and len(frames)>=8 and contactspan>=250 and len(ids)==1)
  result.append(dict(prediction=p,short_ms=z-a,selected_both_people_fraction=coverage,contact_observation_count=len(frames),contact_span_ms=contactspan,player_ids=sorted(ids),delete=drop,flight_ids=[f['flight_id'] for f in fs]))
 return result
