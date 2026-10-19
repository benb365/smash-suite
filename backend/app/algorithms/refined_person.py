"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
from .buffer_actions import padded
from .pose_lk_motion_count import predict as group_actions
from .selected_algorithm import CONFIG
from .trials import RallyInterval
from dataclasses import asdict
from scipy.ndimage import maximum_filter1d
from scipy.ndimage import median_filter
import numpy as np

def predict(d,duration,options):
 ts=d['times'];step=float(np.median(np.diff(ts)));w=max(1,round(CONFIG['opponent_window_ms']/step))|1
 other=(d['lkarm']>=CONFIG['opponent_arm_speed'])|(median_filter(d['speed'],size=(3,1),mode='nearest')>=CONFIG['opponent_body_speed'])
 recent=np.column_stack([maximum_filter1d(other[:,k].astype(int),size=w)>0 for k in (0,1)])
 confirmed=d['lkarm'].copy()
 for k in (0,1):
  ball_support=d['ball'].copy()
  if options.get('ball_only_high'):ball_support&=d['lkhigh'][:,k]>=CONFIG['arm_speed']
  confirmed[:,k]*=recent[:,1-k]|ball_support
 events=[(int(i),int(k)) for i,k in zip(*np.where(confirmed>=CONFIG['arm_speed']))]
 events.sort(key=lambda p:ts[p[0]]);groups=[]
 for e in events:
  if not groups or ts[e[0]]-ts[groups[-1][-1][0]]>CONFIG['action_gap_ms']:groups.append([e])
  else:groups[-1].append(e)
 decisions=[];accepted_groups=[]
 for g in groups:
  players={k for i,k in g}; a=float(ts[max(0,g[0][0]-1)]);z=float(ts[g[-1][0]])
  ai=int(np.searchsorted(ts,a));zi=int(np.searchsorted(ts,z))
  ball_count=sum(bool(d['ball'][i]) for i,k in g)
  high_count=sum(bool(d['lkhigh'][i,k]>=CONFIG['arm_speed']) for i,k in g)
  original_accept=len(g)>=CONFIG['minimum_actions'] and z-a>=800 and (len(players)>=2 or bool(np.any(d['ball'][ai:zi+1])))
  extra_accept=len(players)>=2 or (ball_count>=options.get('min_ball_events',0) and high_count>=options.get('min_high_events',0))
  if not extra_accept:
   for i,k in g:confirmed[i,k]=0
  accepted=original_accept and extra_accept
  row=dict(core=[a,z],players=sorted(players),count=len(g),ball_event_count=ball_count,high_event_count=high_count,
           original_accept=original_accept,accepted=accepted,events=[dict(t=float(ts[i]),player=k) for i,k in g])
  decisions.append(row)
  if accepted:accepted_groups.append(row)
 q=dict(d,confirmed=confirmed)
 core=dict(signal='confirmed',threshold=CONFIG['arm_speed'],gap_ms=CONFIG['action_gap_ms'],ball=True,
           extend=CONFIG['supported_boundary_search_ms'],minimum_actions=CONFIG['minimum_actions'])
 raw=group_actions(q,core)
 # Keep group provenance until after padding; the normal helper otherwise
 # merges overlapping output and loses whether a later group was unilateral.
 buffered=[]
 for p in raw:
  a=max(0,p.start_ms-CONFIG['before_ms']);z=min(duration,p.end_ms+CONFIG['after_ms'])
  sources=[g for g in accepted_groups if g['core'][0]<p.end_ms and g['core'][1]>p.start_ms]
  assert sources
  both=any(len(g['players'])>=2 for g in sources)
  if buffered and a<=buffered[-1]['end_ms']:
   buffered[-1]['end_ms']=max(z,buffered[-1]['end_ms']);buffered[-1]['both_players']|=both
  else:buffered.append(dict(start_ms=a,end_ms=z,both_players=both))
 normal=padded([asdict(p) for p in raw],CONFIG['before_ms'],CONFIG['after_ms'],duration)
 assert [(p['start_ms'],p['end_ms']) for p in buffered]==[(p.start_ms,p.end_ms) for p in normal]
 joined=[];links=[]
 for p in buffered:
  if joined:
   gap=p['start_ms']-joined[-1][1]
   allowed=gap<=CONFIG['join_gap_ms'] and (not options.get('restrict_single_joins') or p['both_players'])
   links.append(dict(gap_ms=gap,later_both_players=p['both_players'],joined=allowed))
  else:allowed=False
  if allowed:joined[-1][1]=max(joined[-1][1],p['end_ms'])
  else:joined.append([p['start_ms'],p['end_ms']])
 pred=[RallyInterval(i+1,a,z,duration) for i,(a,z) in enumerate(joined)]
 return pred,dict(groups=decisions,raw=[asdict(p) for p in raw],buffered=buffered,links=links)
