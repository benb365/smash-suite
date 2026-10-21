"""Recover A native data with validated focused instruments; no elevated sampler."""
from pathlib import Path
import json, os, subprocess, time, signal
import psutil
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'apps/video-clipper/.runtime/performance-baseline'
C=B/'profile-control-A'
OUT=B/'profile-native-A'
cmd=[str(ROOT/'.venv/bin/python'),'-m','app.benchmark','--inputs',str(B/'media/inputs.json'),'--cases','A-short','--models',str(B/'prepared-models'),'--output',str(OUT),'--report',str(B/'native-A-report.json'),'--profile-wait','--profile-timeout','300','--mps-signposts','--no-statistics']
log=(C/'native-runner.log').open('w')
runner=subprocess.Popen(cmd,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'apps/video-clipper/backend')),stdout=log,stderr=subprocess.STDOUT)
trace=None
meta={'case_id':'A-short','capture_type':'native-only recovery','application_uid':os.getuid(),'runner_command':cmd,'python_capture':{'target_pid':38406,'recording_metadata':str(C/'recording-python-pass.json'),'flamegraph':str(C/'python-flamegraph.svg'),'case_directory':str(B/'profile-A/A-short'),'note':'Separate completed Python capture of identical frozen source/input; includes attachment wait.'}}
def save(): (C/'recording.json').write_text(json.dumps(meta,indent=2))
try:
    ready_path=OUT/'A-short/profile-ready.json'; deadline=time.monotonic()+120
    while not ready_path.exists():
        if runner.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Native recovery worker not ready')
        time.sleep(.1)
    ready=json.loads(ready_path.read_text());pid=ready['pid'];uid=psutil.Process(pid).uids().real
    assert uid==os.getuid()!=0
    meta.update(target_pid=pid,target_uid=uid,native_case_directory=str(OUT/'A-short'),native_benchmark_clock_path=str(OUT/'A-short/evidence/benchmark-clock.json'))
    trace_cmd=['xcrun','xctrace','record','--template','Time Profiler','--instrument','GPU','--instrument','os_signpost','--attach',str(pid),'--time-limit','21600s','--output',str(C/'native.trace')]
    tpath=C/'native-focused.log';tlog=tpath.open('w');trace=subprocess.Popen(trace_cmd,stdout=tlog,stderr=subprocess.STDOUT);meta['trace_command']=trace_cmd;meta['trace_pid']=trace.pid;save()
    deadline=time.monotonic()+120
    while 'Ctrl-C to stop the recording' not in tpath.read_text():
        if trace.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Native focused attach failed')
        time.sleep(.1)
    meta['release_monotonic_s']=time.monotonic();meta['monotonic_to_epoch_offset_s']=time.time()-time.monotonic();meta['release_epoch_s']=meta['release_monotonic_s']+meta['monotonic_to_epoch_offset_s'];save();Path(ready['release_file']).touch()
    print(json.dumps({'event':'native_A_released','pid':pid,'uid':uid}),flush=True)
    meta['runner_returncode']=runner.wait(timeout=21600)
    if trace.poll() is None and 'ending recording' not in tpath.read_text():trace.send_signal(signal.SIGINT)
    meta['trace_returncode']=trace.wait(timeout=1800);save()
    print(json.dumps({'event':'native_A_saved','runner':meta['runner_returncode'],'trace':meta['trace_returncode']}),flush=True)
    if meta['runner_returncode'] or meta['trace_returncode']:raise RuntimeError('Native recovery failed')
finally:
    save()
    if runner.poll() is None:
        for child in reversed(psutil.Process(runner.pid).children(recursive=True)):
            try: child.terminate()
            except psutil.Error:pass
        runner.terminate()
    if trace and trace.poll() is None:trace.terminate()
