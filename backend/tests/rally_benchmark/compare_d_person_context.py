"""Compare D person-context rules on saved D1/D2 observations.

No model inference or annotation edits. The original D experiment is replayed
and verified before comparison. Run from the repository root in the existing
SoloShuttlePose environment; original runtime observations must be present.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d

R = Path.cwd()
B = R / 'models/SoloShuttlePose/.runtime'
OLD = B / 'd1-person-motion-20261017'
OUT = B / 'd-refinement-20261018/final'
sys.path[:0] = [str(R/'backend'), str(R/'backend/tests/rally_benchmark'), str(OLD)]
from app.vision.rally_stream import RallyInterval
from app.vision.rally_eval import load_rally_annotations, load_rally_exclusions, evaluate_rallies
from compare_m1 import retained_time

spec = importlib.util.spec_from_file_location('d_original_refine', OLD/'d1-refined-person-20261018/refine.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
from duration_profiles import breakdown
BASE = original.CONFIG.copy()
OPTIONS = dict(ball_only_high=True, min_ball_events=2, min_high_events=1)
CONFIG = dict(context_ms=1600, continue_arm=.3, phase_foot=.2,
              filter_context=True, recover=True, recover_foot=.12,
              extend_ms=6000, support_gap_ms=1000, bridge_ms=3000,
              bridge_fraction=.5, recover_max_ms=2000, recover_both_count=3,
              recover_min_high=1, stable_ms=1400, minimum_missing_ms=400,
              continue_single=True, continue_recovered=True,
              single_gap_ms=2800, single_support_fraction=.65, single_ready_fraction=.3)

def read(p):return json.loads(Path(p).read_text())

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load_cases():
 old=read(R/'docs/experiments/d1-refined-person-20261018.json');variant=next(v for v in old['variants'] if v['name']==old['selected']);cases=[]
 for s in old['samples']:
  path=OLD/f"pose-local-flow-dense-01/{s['id']}-signals.npz"
  prior=next(r for r in variant['results'] if r['sample_id']==s['id'])
  with np.load(path) as z:d={k:z[k] for k in z.files}
  cases.append(dict(sample=s,data=d,path=path,old=prior['predictions']))
 source=read(B/'d2-current-algorithm-20261018/result.json');review=next(r for r in read(R/'docs/experiments/a2-c2-d2-human-reviewed-20261018.json')['results'] if r['clip_id']=='D2');s=copy.deepcopy(source['sample']);s.update(annotation=review['annotation'],annotation_sha256=review['annotation_sha256']);path=B/'d2-current-algorithm-20261018/flow/D2-01-signals.npz'
 with np.load(path) as z:d={k:z[k] for k in z.files}
 assert sha(path)==source['files_sha256']['flow/D2-01-signals.npz']
 s['annotation_status']=read(R/s['annotation'])['status']
 cases.append(dict(sample=s,data=d,path=path,old=review['predictions']))
 for c in cases:
  p,t=original.predict(c['data'],c['sample']['duration_ms'],OPTIONS)
  assert [asdict(q) for q in p]==c['old'],c['sample']['id']
  assert sha(R/c['sample']['annotation'])==c['sample']['annotation_sha256']
 return cases

def evaluate(p,s):
 truth=load_rally_annotations(R/s['annotation']);ex=load_rally_exclusions(R/s['annotation']);m=evaluate_rallies(p,truth,excluded_events=ex);t=retained_time(p,truth,ex,s['duration_ms']);target=[q for q in truth if q.review_status=='verified']
 def covered(q):return sum(max(0,min(a.end_ms,q.end_ms)-max(a.start_ms,q.start_ms)) for a in p)
 return dict(metrics=m,retained_time=t,outside_ms=sum(q.end_ms-q.start_ms for q in p)-t['retained_target_ms'],subsets={str(k):breakdown(p,truth,m,k) for k in (3000,5000)},details=[dict(id=q.rally_id,start_ms=q.start_ms,end_ms=q.end_ms,retained_ms=covered(q)) for q in target])

def summary(rows):
 out={}
 for group in ('D1','D2'):
  rr=[r for r in rows if r['source_id']==group];total=sum(r['retained_time']['target_ms'] for r in rr);kept=sum(r['retained_time']['retained_target_ms'] for r in rr)
  out[group]=dict(retention=kept/total,outside_s=sum(r['outside_ms'] for r in rr)/1000,miss=sum(r['metrics']['missed_rally_count'] for r in rr),both=sum(r['metrics']['boundary_acceptance']['both_acceptable_count'] for r in rr),split=sum(r['metrics']['false_split_count'] for r in rr),merge=sum(r['metrics']['false_merge_count'] for r in rr),long_retention=sum(r['subsets']['5000']['retained_target_ms'] for r in rr)/sum(r['subsets']['5000']['target_ms'] for r in rr),long_miss=sum(len(r['subsets']['5000']['missed_ids']) for r in rr))
 return out

def add_feet(case):
 s=case['sample'];d=case['data'];ts=d['times'];path=(OLD/s['id']/'players-v2.jsonl') if s['source_id']=='D1' else B/f"d2-current-algorithm-20261018/{s['id']}/players-v2.jsonl"
 rows=[json.loads(l) for l in path.read_text().splitlines()];assert len(rows)==len(ts) and max(abs(r['timestamp_ms']-t) for r,t in zip(rows,ts))<.001
 pos=np.full((len(ts),2,2),np.nan);height=np.full((len(ts),2),np.nan)
 for i,r in enumerate(rows):
  for p in r['players']:
   k=p['player_id'];b=p['box'];pos[i,k]=[(b['x1']+b['x2'])/2,b['y2']];height[i,k]=b['y2']-b['y1']
 smooth=np.full_like(pos,np.nan);v=np.zeros((len(ts),2))
 for i in range(len(ts)):
  for k in (0,1):
   if not np.isfinite(pos[i,k]).all():continue
   valid=pos[max(0,i-2):i+3,k];valid=valid[np.isfinite(valid).all(axis=1)]
   if len(valid)>=3:smooth[i,k]=np.median(valid,axis=0)
 for i in range(1,len(ts)):
  for k in (0,1):
   if np.isfinite(smooth[i-1:i+1,k]).all():
    v[i,k]=np.linalg.norm(smooth[i,k]-smooth[i-1,k])/np.mean(height[i-1:i+1,k])/(ts[i]-ts[i-1])*1000
 d['foot_speed']=v;d['foot_valid']=np.isfinite(smooth).all(axis=2)
 return path

def predict_candidate(d,duration,c):
 original.CONFIG=BASE.copy()
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
 _,trace=original.predict(observed,duration,OPTIONS)
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

def make_viewer(cases, variants, out):
    spec = importlib.util.spec_from_file_location('d_viewer', R/'.agents/skills/review-video-results/scripts/review.py')
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)
    reserve = read(B/'reserve-human-reviewed-20261018/review.json')
    d1 = read(OLD/'d1-refined-person-20261018/review.json')
    saved = {c['id']:c for c in reserve['clips'] + d1['clips']}
    actual = {c['sample']['id']:c for c in cases}
    rows = {v['id']:{r['sample_id']:r for r in v['results']} for v in variants}
    issues = {
        'D2': [('第12回合：原尾部少3.633秒 → 补到207.800秒',198000,210000),
               ('第13回合：断开与尾部多留 → 连续保留到233.000秒',214000,239000),
               ('第11回合：原整段漏掉 → 186.300–191.600秒',183000,194000),
               ('第14回合：原整段漏掉 → 241.300–246.200秒',239000,249000),
               ('第6回合：原留到95秒 → 留到90秒，仍多留1.3秒',85000,98000),
               ('第13回合尾部：原多留5.6秒 → 多留1秒',229000,240000)],
        'D1-04': [('49.756–57.456秒还球：新方案删除',47000,61000)]}
    data = dict(schema_version=1,title='D组七处问题：改进前后对照',primary_track='candidate',
        note='绿色为已确认回合，蓝色为本轮候选，灰色为原方案，橙色为已确认排除事件。七处问题已尝试优化，D1也有边界退步，全部四段仍列出；先前最后两项不再作为问题入口。没有改标注或重新运行模型。',
        tracks=[dict(id='truth',label='已确认回合',role='truth'),
                dict(id='candidate',label='本轮候选',role='prediction'),
                dict(id='baseline',label='改进前',role='prediction'),
                dict(id='excluded',label='已确认可排除事件',role='excluded')],clips=[])
    sm = {v['id']:v['summary'] for v in variants}
    data['summary'] = [dict(label='D2对打保留',value=f"{sm['baseline']['D2']['retention']:.2%} → {sm['candidate']['D2']['retention']:.2%}"),
        dict(label='D2标注外保留（含排除事件）',value=f"{sm['baseline']['D2']['outside_s']:.2f} → {sm['candidate']['D2']['outside_s']:.2f}秒"),
        dict(label='D1起止同时合格',value=f"{sm['baseline']['D1']['both']}/32 → {sm['candidate']['D1']['both']}/32",note='总对打保留提高，但边界有退步，不能只看汇总保留率')]
    for cid in ['D2','D1-04','D1-01','D1-02','D1-03']:
        sid = 'D2-01' if cid=='D2' else cid
        clip = copy.deepcopy(saved[cid])
        clip['intervals'] = {k:clip['intervals'][k] for k in ['truth','excluded']}
        for key in ['candidate','baseline']:
            clip['intervals'][key] = [dict(id=str(p['rally_id']),start_ms=p['start_ms'],end_ms=p['end_ms']) for p in rows[key][sid]['predictions']]
        clip['issues'] = [dict(label=label,start_ms=a,end_ms=z) for label,a,z in issues.get(cid,[])]
        a,z = rows['baseline'][sid],rows['candidate'][sid]
        clip['summary'] = [dict(label='对打保留',value=f"{a['retained_time']['retained_target_ms']/a['retained_time']['target_ms']:.2%} → {z['retained_time']['retained_target_ms']/z['retained_time']['target_ms']:.2%}"),
            dict(label='标注外保留（含排除事件）',value=f"{a['outside_ms']/1000:.2f} → {z['outside_ms']/1000:.2f}秒"),
            dict(label='起止同时合格',value=f"{a['metrics']['boundary_acceptance']['both_acceptable_count']} → {z['metrics']['boundary_acceptance']['both_acceptable_count']}")]
        clip['note'] = '本段时间从首帧开始，原视频播放偏移保持原记录。用户先前确认的标注及排除规则不变。'
        data['clips'].append(clip)
    viewer.prepare(data,out)
    (out/'review.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cases = load_cases()
    inputs = {}
    for case in cases:
        p = add_feet(case)
        for path in [case['path'],p,R/case['sample']['annotation']]:
            inputs[str(path.relative_to(R))] = sha(path)
    variants = []
    configs = [('baseline',None),
        ('short_context_only',dict(CONFIG,stable_ms=0,recover=False,extend_ms=0,bridge_ms=0,continue_single=False,continue_recovered=False)),
        ('candidate',CONFIG)]
    for name,cfg in configs:
        rows = []
        for case in cases:
            sample = case['sample']
            if cfg is None:
                original.CONFIG=BASE.copy()
                pred,trace=original.predict(case['data'],sample['duration_ms'],OPTIONS)
                assert [asdict(p) for p in pred]==case['old']
            else:
                pred,trace=predict_candidate(case['data'],sample['duration_ms'],cfg)
            assert all(0<=p.start_ms<p.end_ms<=sample['duration_ms'] for p in pred)
            assert all(a.end_ms<b.start_ms for a,b in zip(pred,pred[1:]))
            rows.append(dict(sample_id=sample['id'],source_id=sample['source_id'],predictions=[asdict(p) for p in pred],trace=trace,**evaluate(pred,sample)))
        variants.append(dict(id=name,config=cfg,results=rows,summary=summary(rows)))
    old,new=variants[0],variants[-1]
    d2=new['results'][-1]
    target={r['id']:r for r in d2['details']}
    checks={f'D2_R{i}_complete_coverage':abs(target[i]['retained_ms']-(target[i]['end_ms']-target[i]['start_ms']))<.001 for i in [11,12,13,14]}
    for i in [6,13]:
        truth=target[i]
        before=[p for p in old['results'][-1]['predictions'] if p['start_ms']<truth['end_ms'] and p['end_ms']>truth['start_ms']]
        after=[p for p in d2['predictions'] if p['start_ms']<truth['end_ms'] and p['end_ms']>truth['start_ms']]
        checks[f'D2_R{i}_less_tail']=max(p['end_ms'] for p in after)<max(p['end_ms'] for p in before)
    checks['D2_R13_complete_coverage'] &= sum(p['start_ms']<target[13]['end_ms'] and p['end_ms']>target[13]['start_ms'] for p in d2['predictions'])==1
    r=next(r for r in new['results'] if r['sample_id']=='D1-04')
    checks['D1_return_removed']=not any(p['start_ms']<57455.875 and p['end_ms']>49755.875 for p in r['predictions'])
    assert all(checks.values()),checks
    attempts=[]
    for filename in ['simple-trials.json','context-trials.json','hybrid-trials.json','controlled-trials.json','stable-trials.json','reacquire-trials.json','continuation-trials.json','attachment-trials.json','ready-trials.json']:
        path=OUT.parent/filename
        trials=read(path)
        attempts.append(dict(file=str(path.relative_to(R)),sha256=sha(path),count=len(trials),trials=[dict(id=t.get('id',t.get('policy',{}).get('id')),config=t.get('config',t.get('policy')),summary=t['summary']) for t in trials]))
    code=[Path(__file__),Path(original.__file__),R/'backend/app/vision/rally_eval.py']
    code += [Path(sys.modules[n].__file__) for n in ['trials','selected_algorithm','pose_lk_motion_count','buffer_actions','players','pose_context','duration_profiles']]
    report=dict(date='2026-10-18',status='D1_D2_development_comparison',model_inference=False,annotation_changed=False,
        selected='candidate',base_config=BASE,base_options=OPTIONS,candidate_config=CONFIG,
        samples=[c['sample'] for c in cases],variants=variants,seven_issue_checks=checks,
        input_sha256=inputs,code_sha256={str(p.relative_to(R)):sha(p) for p in code},
        attempts=attempts,attempt_count=sum(a['count'] for a in attempts),
        limits=['用户排除最后两个问题入口，本轮只检查原前七处；全D1/D2评分用于记录影响。',
                '两份来源、全部五段都已用于比较和调参，不是独立验收。',
                '全部依赖保存的真实观测；没有新模型推理或新的完整流程速度结果。',
                '人物选择、邻近时刻活动窗口和脚点平滑使用后续观测，仍是离线候选。',
                '动作观测不是击球计数，缺失不是静止；姿态重新出现后延迟用于建立回合也可能损失正常动作。',
                '标注外保留包含已确认排除事件；评估器可能忽略的事件仍会增加成片内容。',
                f"{sum(a['count'] for a in attempts)}项尝试包含重复对照与等效配置，不能解释为独立验证；保存各轮参数、汇总和原结果哈希。",
                '候选保留率改善同时存在D1边界退步，原方案保留，正式产品入口未替换。'])
    for p in [args.output/'comparison.json',R/'docs/experiments/d-person-context-20261018.json']:
        p.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    make_viewer(cases,variants,args.output)
    print(json.dumps({v['id']:v['summary'] for v in variants},ensure_ascii=False,indent=2))
    print('Seven target checks:',checks)
    print('Viewer data:',args.output/'review.json')

if __name__=='__main__':
    main()
