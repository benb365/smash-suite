"""Accepted person-context scenario; configuration from the reviewed D experiment."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from modules.rally.types import RallyInterval
from modules.rally.common import refined_person as original
PROFILES = json.loads(Path(__file__).with_name("profiles.json").read_text())
CONFIG, OPTIONS = PROFILES["personal"], PROFILES["personal_options"]

def predict(d,duration,c=CONFIG):
 observed=d
 if c['stable_ms']:
  # A pose reacquired after occlusion may jump. Delay using its arm motion as
  # a new start, while continuation still sees the original observations.
  stable=np.ones_like(d['present'],bool)
  step0=float(np.median(np.diff(d['times'])))
  for k in (0,1):
   last_missing=None;missing_since=None;recovering=False
   for i,t in enumerate(d['times']):
    if not d['present'][i,k]:
     if missing_since is None:missing_since=t
     last_missing=t
     if t-missing_since+step0>=c['minimum_missing_ms']:recovering=True
    else:missing_since=None
    if recovering and d['present'][i,k] and t-last_missing>=c['stable_ms']:recovering=False
    stable[i,k]=bool(d['present'][i,k] and not recovering)
  observed=dict(d,lkarm=d['lkarm']*stable,lkhigh=d['lkhigh']*stable)
 _,trace=original.predict(observed,duration,OPTIONS,PROFILES["personal_base"])
 ts=d['times'];step=float(np.median(np.diff(ts)));n=len(ts);win=max(1,round(c['context_ms']/step))|1
 weak=(d['lkarm']>=.35)|(d['speed']>=.6)
 counts=uniform_filter1d(weak.astype(float),size=win,axis=0,mode='constant')*win
 qualified=(d['lkarm']>=.7)&(counts[:,::-1]>=2-.001)
 footavg=uniform_filter1d(d['foot_speed'],size=5,axis=0,mode='nearest')
 high=maximum_filter1d(np.max(d['lkarm'],axis=1),size=3,mode='constant')>=c['continue_arm']
 phase=np.all(footavg>=c['phase_foot'],axis=1)&high&np.all(d['present'],axis=1)
 rescue_phase=np.all(footavg>=.1,axis=1)&high&np.all(d['present'],axis=1)
 oldsupport=(np.max(d['arm'],axis=1)>=.35)|(np.min(d['ready'],axis=1)&(np.max(d['speed'],axis=1)>=.15))|d['ball']
 groups=[[(int(np.searchsorted(ts,e['t'])),e['player']) for e in parent['events']] for parent in trace['groups']]
 outputs=[];decisions=[]
 for g in groups:
  ai=max(0,g[0][0]-1);zi=g[-1][0];a=ts[ai];z=ts[zi];players={k for i,k in g};bc=sum(bool(d['ball'][i]) for i,k in g);hc=sum(d['lkhigh'][i,k]>=.7 for i,k in g)
  ok=len(g)>=2 and z-a>=800 and(len(players)>=2 or bool(np.any(d['ball'][ai:zi+1]))) and(len(players)>=2 or(bc>=2 and hc>=1))
  oldok=bool(ok);reason=None
  q=[(i,k) for i,k in g if qualified[i,k]]
  qplayers={k for i,k in q};qspan=ts[q[-1][0]]-ts[max(0,q[0][0]-1)] if q else 0
  if ok and c['filter_context'] and z-a<=5000 and not(len(q)>=2 and(qspan>=800 or(len(qplayers)>=2 and qspan>=400))):ok=False;reason='short_group_lacks_repeated_opponent_support'
  if c['recover'] and not oldok and len(g)>=2 and z-a>=400:
   left=max(0,ai-round(1000/step));right=min(n,zi+round(1000/step)+1)
   physical=np.min(np.mean(d['foot_speed'][left:right],axis=0))>=c['recover_foot']
   supported=len(q)>=2 and(qspan>=800 or(len(qplayers)>=2 and qspan>=400))
   ballinside=np.sum(d['ball'][left:right])>=2
   ok=physical and z-a<=c['recover_max_ms'] and ((len(players)>=2 and supported and len(g)>=c['recover_both_count']) or(supported and ballinside and hc>=c['recover_min_high']))
   if ok:reason='recovered_compressed_or_unilateral_group'
  core=[float(a),float(z)]
  attach=False;attachment_fraction=None;attachment_ready_fraction=None
  if not ok and c['continue_single'] and len(g)==1 and hc>=1 and outputs:
   gap=float(a)-outputs[-1][1];between=(ts>=outputs[-1][1])&(ts<=a)
   attachment_fraction=float(np.mean(rescue_phase[between])) if np.any(between) else None
   attachment_ready_fraction=float(np.mean(np.all(d['ready'][between],axis=1))) if np.any(between) else None
   attach=0<gap<=c['single_gap_ms'] and attachment_fraction is not None and attachment_fraction>=c['single_support_fraction'] and attachment_ready_fraction>=c['single_ready_fraction']
  if ok or attach:
   for i in range(ai-1,-1,-1):
    if ts[i]<core[0]-1200 or not oldsupport[i]:break
    a=ts[i]
   for i in range(zi+1,n):
    if ts[i]>ts[zi]+1200 or not oldsupport[i]:break
    z=ts[i]
   recovered_context=bool(c['continue_recovered'] and ok and not oldok)
   if recovered_context:
    last=ai;blank=0
    for j in range(ai-1,-1,-1):
     if ts[j]<ts[ai]-1200:break
     if rescue_phase[j]:last=j;blank=0
     else:blank+=step
     if blank>c['support_gap_ms']:break
    a=min(a,ts[last])
   if c['extend_ms'] and (len(g)>=4 or recovered_context):
    last=zi;blank=0
    continuation=rescue_phase if recovered_context else phase
    for j in range(zi+1,n):
     if ts[j]>ts[zi]+(1200 if recovered_context else c['extend_ms']):break
     if continuation[j]:last=j;blank=0
     else:blank+=step
     if blank>c['support_gap_ms']:break
    z=max(z,ts[last])
   if attach:outputs[-1][1]=max(outputs[-1][1],min(duration,float(z)+800));reason='single_observation_continues_existing_play'
   else:outputs.append([max(0,float(a)-1500),min(duration,float(z)+800)])
  decisions.append(dict(core=core,count=len(g),players=sorted(players),qualified_count=len(q),qualified_players=sorted(qplayers),qualified_span_ms=float(qspan),accepted=bool(ok),attached_as_continuation=bool(attach),attachment_support_fraction=attachment_fraction,attachment_ready_fraction=attachment_ready_fraction,old_accepted=oldok,reason=reason,extended=[float(a),float(z)]))
 merged=[]
 for a,z in outputs:
  gap=a-merged[-1][1] if merged else None
  link=gap is not None and gap<=1000
  if merged and c['bridge_ms'] and 1000<gap<=c['bridge_ms']:
   ii=(ts>=merged[-1][1])&(ts<=a);link=bool(np.any(ii) and np.mean(phase[ii])>=c['bridge_fraction'])
  if link:merged[-1][1]=max(z,merged[-1][1])
  else:merged.append([a,z])
 return [RallyInterval(i+1,a,z,duration) for i,(a,z) in enumerate(merged)],dict(groups=decisions)
