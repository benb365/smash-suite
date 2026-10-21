"""Select actual detector crops for numeric probes; these are not rally labels."""
from pathlib import Path
import json
import av, cv2, torch
from modules.models.yolo11n import PersonDetector
TASK=Path('/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite')
OUT=TASK/'apps/video-clipper/.runtime/performance-first-round/probes'
cases=json.loads((TASK/'apps/video-clipper/reports/performance-first-round/inputs.json').read_text())['cases']
case=next(c for c in cases if c['case_id']=='D-short')
wanted=[0,300,3600,7524];frames=[]
with av.open(case['video']) as container:
 for fid,frame in enumerate(container.decode(video=0)):
  if fid in wanted:frames.append((fid,frame.to_ndarray(format='bgr24')))
  if fid==wanted[-1]:break
detector=PersonDetector('/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/prepared-models/yolo11n.pt',device='mps')
boxes=detector([image for _,image in frames]);samples=[];diagnostics=[]
for (fid,image),found in zip(frames,boxes):
 selected=sorted(enumerate(found),key=lambda pair:pair[1]['y2']-pair[1]['y1'],reverse=True)[:2]
 diagnostics.append({'frame_id':fid,'detected_boxes':len(found),'chosen_detector_indices':[i for i,b in selected]})
 if selected:samples.append({'frame_id':fid,'players':[{'player_id':k,'box_index':i,'box':b} for k,(i,b) in enumerate(selected)]})
(OUT/'d-samples.json').write_text(json.dumps(samples,indent=2)+'\n')
(OUT/'d-samples-source.json').write_text(json.dumps({'input_sha256':case['sha256'],'video':case['video'],'selection':'two tallest actual detector boxes for numerical probe only; not principal-player truth or rally annotations','requested_frame_ids':wanted,'observations':diagnostics},indent=2)+'\n')
print(json.dumps({'samples':len(samples),'frames':diagnostics}))
