"""Freeze one approved source variant and call the existing product benchmark."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, time
TASK=Path('/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite')
MEASURE=Path('/Users/bytedance/.codex/worktrees/performance-first-round-measure/smash-suite')
BASE='5c946e9e6186d052624ca6f853a62d40f034f6e8'
SOURCES=['modules/rally/recognize.py','modules/models/keypoint_rcnn/__init__.py','modules/models/tracknet/predictor.py']
CONTROL=TASK/'docs/ai/performance-first-round/controller'
RAW=TASK/'apps/video-clipper/.runtime/performance-first-round'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def call(args,**kwargs): return subprocess.run(args,cwd=MEASURE,check=True,**kwargs)
def save(p,d): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('run_id');ap.add_argument('case',choices=['A-short','C-short','D-short']);ap.add_argument('--patch',action='append',default=[]);ap.add_argument('--tracknet-copy-only',action='store_true');ap.add_argument('--final',action='store_true');ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
 if not args.run_id.replace('-','').replace('_','').isalnum():raise ValueError('Invalid run id')
 run=RAW/args.run_id
 if run.exists():raise FileExistsError(run)
 state=CONTROL/'measurement-source-state.json'
 expected=json.loads(state.read_text()) if state.exists() else {s:hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+s],cwd=MEASURE)).hexdigest() for s in SOURCES}
 for s in SOURCES:
  if sha(MEASURE/s)!=expected[s]:raise RuntimeError('Unexpected measurement edit: '+s)
 for s in SOURCES:(MEASURE/s).write_bytes(subprocess.check_output(['git','show',BASE+':'+s],cwd=MEASURE))
 applied=[]
 if args.final:
  if args.patch or args.tracknet_copy_only:raise ValueError('Final cannot mix patch arguments')
  for s in SOURCES:shutil.copyfile(TASK/s,MEASURE/s)
 else:
  for raw in args.patch:
   p=Path(raw).resolve(); text=p.read_text()
   for line in text.splitlines():
    if line.startswith('+++ b/') and line[6:] not in SOURCES:raise ValueError('Unexpected patch target '+line)
   call(['git','apply','--check',str(p)]);call(['git','apply',str(p)])
   applied.append({'path':str(p),'sha256':sha(p)})
  if args.tracknet_copy_only:
   p=MEASURE/SOURCES[2];text=p.read_text()
   if text.count('rgb.copy()')!=1:raise ValueError('Expected one TrackNet RGB copy')
   p.write_text(text.replace('rgb.copy()','rgb'))
 frozen={s:sha(MEASURE/s) for s in SOURCES}
 save(state,frozen)
 manifest={'run_id':args.run_id,'case':args.case,'base':BASE,'sources':frozen,'patches':applied,'final_sources':args.final,'copy_only':args.tracknet_copy_only,'uid':os.getuid(),'started_monotonic':time.monotonic()}
 save(CONTROL/'freezes'/f'{args.run_id}.json',manifest)
 if args.prepare_only:
  print(json.dumps({'run_id':args.run_id,'status':'prepared','sources':frozen}),flush=True)
  return
 env=dict(os.environ,PYTHONPATH=str(MEASURE/'apps/video-clipper/backend'))
 command=[str(MEASURE/'.venv/bin/python'),'-m','app.benchmark','--inputs',str(TASK/'apps/video-clipper/reports/performance-first-round/inputs.json'),'--cases',args.case,'--models','/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/prepared-models','--output',str(run),'--report',str(RAW/f'{args.run_id}-report.json')]
 result=subprocess.run(command,cwd=MEASURE,env=env)
 manifest.update(returncode=result.returncode,finished_monotonic=time.monotonic(),source_unchanged=all(sha(MEASURE/s)==frozen[s] for s in SOURCES))
 save(CONTROL/'freezes'/f'{args.run_id}.json',manifest)
 if not manifest['source_unchanged']:raise RuntimeError('Source mutated during run')
 if result.returncode:raise SystemExit(result.returncode)
 data=json.loads((run/args.case/'result.json').read_text())
 print(json.dumps({'run_id':args.run_id,'status':data.get('status'),'timings':data.get('timings'),'source_unchanged':manifest['source_unchanged']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
