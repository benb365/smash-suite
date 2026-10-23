"""Compare saved output against an explicit reference and fully decode saved MP4."""
from pathlib import Path
import argparse, json, time
import av, numpy as np

def inspect(path):
 out={'path':str(path),'streams':[]}
 with av.open(str(path)) as container:
  for s in container.streams:
   item={'type':s.type,'codec':s.codec_context.name,'time_base':str(s.time_base),'start_time':s.start_time,'duration':s.duration}
   if s.type=='video':item.update(width=s.width,height=s.height,average_rate=str(s.average_rate))
   elif s.type=='audio':item.update(sample_rate=s.codec_context.sample_rate,channels=s.codec_context.channels)
   out['streams'].append(item)
 out['decoded']={}
 # Full decode per stream so audio and video validity are both checked.
 for kind in ['video','audio']:
  with av.open(str(path)) as container:
   streams=[s for s in container.streams if s.type==kind]
   if not streams:continue
   count=0;pts=[]
   for frame in container.decode(streams[0]):
    count+=1
    if frame.pts is not None:pts.append(float(frame.pts*frame.time_base))
   out['decoded'][kind]={'frames':count,'first_pts_s':pts[0] if pts else None,'last_pts_s':pts[-1] if pts else None,'strictly_increasing_pts':all(a<b for a,b in zip(pts,pts[1:]))}
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('candidate',type=Path);ap.add_argument('reference',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
 a=args.candidate/'evidence';b=args.reference/'evidence';x=json.loads((a/'result.json').read_text());y=json.loads((b/'result.json').read_text())
 fields=['predictions','export_ranges','output_duration_ms','quality','padding_ms','warnings']
 out={'candidate':str(args.candidate),'reference':str(args.reference),'equal':{k:x.get(k)==y.get(k) for k in fields},'candidate_media':inspect(a/'output.mp4')}
 # Reference media inspected once per explicit comparison; no new inference.
 out['reference_media']=inspect(b/'output.mp4')
 out['media_structure_equal']=out['candidate_media']['streams']==out['reference_media']['streams'] and out['candidate_media']['decoded']==out['reference_media']['decoded']
 out['range_sum_ms']=sum(z-v for v,z in x['export_ranges']);out['declared_minus_sum_ms']=x['output_duration_ms']-out['range_sum_ms']
 for kind in ['candidate_media','reference_media']:
  for stream in out[kind]['decoded'].values():
   if not stream['frames'] or not stream['strictly_increasing_pts']:raise ValueError('Invalid decoded media '+kind)
 if (a/'person-signals.npz').exists() and (b/'person-signals.npz').exists():
  with np.load(a/'person-signals.npz') as aa,np.load(b/'person-signals.npz') as bb:
   out['signals']={k:{'equal':np.array_equal(aa[k],bb[k],equal_nan=True),'shape_equal':aa[k].shape==bb[k].shape,'max_abs_difference':float(np.max(np.abs(aa[k].astype(float)-bb[k].astype(float)))) if aa[k].shape==bb[k].shape and aa[k].size else None} for k in aa.files if k in bb.files}
 out['passed_equivalence']=all(out['equal'].values()) and out['media_structure_equal'] and abs(out['declared_minus_sum_ms'])<1e-6
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'output':str(args.output),'passed_equivalence':out['passed_equivalence'],'equal':out['equal'],'media_structure_equal':out['media_structure_equal']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
