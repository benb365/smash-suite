"""Selected prediction code, preserved from the recorded experiment."""
from __future__ import annotations
import cv2
import itertools
import math
import numpy as np

COURT = np.array([[700,400],[1380,400],[1920,1080],[0,1080]], np.float32)

def main_players(boxes):
    eligible = [b for b in boxes if b['y2']-b['y1'] >= 60 and
                cv2.pointPolygonTest(COURT, ((b['x1']+b['x2'])/2, b['y2']), False) >= 0]
    selected = sorted(eligible, key=lambda b: b['y2']-b['y1'], reverse=True)[:2]
    return sorted(selected, key=lambda b: b['y2'])

def tracks(rows,mode):
 seed=main_players(rows[0]['boxes']);assert len(seed)==2
 ids=[next(i for i,b in enumerate(rows[0]['boxes']) if b==s) for s in seed]
 states=[dict(box=s,t=rows[0]['timestamp_ms'],template=rows[0]['features'][i],seed=rows[0]['features'][i]) for i,s in zip(ids,seed)]
 output=[]
 for r in rows:
  options=[]
  for st in states:
   dt=(r['timestamp_ms']-st['t'])/1000;poss=[(1.8,-1,None)]
   for j,(b,f) in enumerate(zip(r['boxes'],r['features'])):
    if height(b)<55:continue
    dist=float(np.linalg.norm(foot(b)-foot(st['box'])))/height(st['box'])
    ratio=height(b)/height(st['box']);ad=min(appearance(st['template'],f),appearance(st['seed'],f))
    if not .25<=ratio<=3 or dist>.6+min(dt,6)*1.8:continue
    if mode=='appearance' and ad>.65:continue
    cost=.25*dist/max(.25,math.sqrt(dt+.04))+.12*abs(math.log(ratio))-.1*b['confidence']
    if mode=='appearance':cost+=2.0*ad
    poss.append((cost,j,dict(box=b,appearance_error=ad,normalized_displacement=dist)))
   options.append(poss)
  pairs=[(a[0]+b[0],a,b) for a,b in itertools.product(*options) if a[1]<0 or b[1]<0 or a[1]!=b[1]]
  _,a,b=min(pairs,key=lambda v:v[0]);selected=[]
  for ident,c in enumerate((a,b)):
   if c[1]<0:continue
   st=states[ident];obs=c[2];obs.update(player_id=ident,box_index=c[1],association_cost=c[0]);selected.append(obs)
   f=r['features'][c[1]]
   if obs['appearance_error']<.4:
    st['template']=[(.9*np.array(x)+.1*np.array(y)).tolist() for x,y in zip(st['template'],f)]
   st.update(box=obs['box'],t=r['timestamp_ms'])
  output.append(dict(frame_id=r['frame_id'],timestamp_ms=r['timestamp_ms'],players=selected))
 return output

def height(b):return b['y2']-b['y1']

def foot(b):return np.array([(b['x1']+b['x2'])/2,b['y2']])

def appearance(a,b):return sum(cv2.compareHist(np.asarray(x,np.float32),np.asarray(y,np.float32),cv2.HISTCMP_BHATTACHARYYA) for x,y in zip(a,b))/len(a)

def descriptor(im,b):
 h,w=im.shape[:2];bw=b['x2']-b['x1'];bh=b['y2']-b['y1'];parts=[]
 for lo,hi in ((.18,.55),(.55,.8)):
  x1,x2=round(b['x1']+.2*bw),round(b['x1']+.8*bw)
  y1,y2=round(b['y1']+lo*bh),round(b['y1']+hi*bh)
  crop=im[max(0,y1):min(h,y2),max(0,x1):min(w,x2)];assert crop.size
  hist=cv2.calcHist([cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)],[0,1,2],None,[8,4,4],[0,180,0,256,0,256]).flatten()
  parts.append((hist/hist.sum()).tolist())
 return parts
