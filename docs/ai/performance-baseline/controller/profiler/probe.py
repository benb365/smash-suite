import json, os, sys, time
from pathlib import Path
import torch
directory=Path(sys.argv[1])
directory.mkdir(parents=True,exist_ok=True)
(directory/"probe-ready.json").write_text(json.dumps(dict(pid=os.getpid(),uid=os.getuid(),mps=torch.backends.mps.is_available(),torch=torch.__version__)))
deadline=time.monotonic()+90
while not (directory/"go").exists():
 if time.monotonic()>deadline: raise TimeoutError("probe start handshake")
 time.sleep(.05)
x=torch.randn((256,256),device="mps")
started=time.monotonic(); count=0
with torch.mps.profiler.profile(mode="interval,event",wait_until_completed=False):
 while time.monotonic()-started<12:
  x=(x@x).clamp(-.01,.01)
  float(x.sum().cpu())
  count+=1
  time.sleep(.005)
(directory/"probe-result.json").write_text(json.dumps(dict(iterations=count,wall_s=time.monotonic()-started,uid=os.getuid(),mps_allocated=torch.mps.current_allocated_memory())))
