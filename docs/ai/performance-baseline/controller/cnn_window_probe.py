from pathlib import Path
import os,time,json,sys
import torch
from modules.models.tracknet import TrackNetPredictor
from modules.media.video_input import FileFrameSource
root=Path(__file__).resolve().parents[4];out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
model=TrackNetPredictor(root/'apps/video-clipper/.runtime/performance-baseline/prepared-models/ball_track.pt',device='mps')
source=Path('/Users/bytedance/workspace/experiments/smash-suite/datasets/badminton-v1/local/rally/m1-short-a1-01-20261015/clip.mp4')
with FileFrameSource(source,mode='offline') as frames:
    batch=[]
    for frame in frames:
        batch.append(frame.image)
        if len(batch)==3:break
(out/'ready.json').write_text(json.dumps({'pid':os.getpid(),'uid':os.getuid()}))
limit=time.monotonic()+90
while not (out/'go').exists():
    if time.monotonic()>limit:raise TimeoutError('probe gate')
    time.sleep(.05)
started=time.monotonic();n=0
with torch.mps.profiler.profile(mode='interval,event',wait_until_completed=False):
    while time.monotonic()-started<12:
        model(batch);n+=1
(out/'result.json').write_text(json.dumps({'iterations':n,'wall_s':time.monotonic()-started,'uid':os.getuid()}))
time.sleep(2)
