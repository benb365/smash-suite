"""Court, player and shot evidence; never invokes the shuttle model."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .constraints import constrain_shots

import cv2
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares, minimize_scalar

from modules.media.video_input import FileFrameSource
from modules.models.yolo11n import PersonDetector
from .court import calibrate, transform
from .observations import _sha256 as file_sha256


def _device():
    import torch
    return 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'


def _load_observations(path, source):
    meta=json.loads(path.with_suffix('.meta.json').read_text())
    if not meta.get('complete') or meta.get('source_sha256') != file_sha256(source):
        raise ValueError('球观测缓存未完成或与当前视频不匹配，请先采集真实观测。')
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    times=[row['timestamp_ms'] for row in rows]
    if (not rows or len(rows) != meta.get('frame_count')
            or times[-1] != meta.get('last_timestamp_ms')):
        raise ValueError('球观测缓存行数或末时间与完整记录不匹配，请重新检查缓存。')
    if any(not math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('球观测时间必须有限且严格递增。')
    return rows,meta


def _video_evidence(source, info, weights, directory, progress, source_hash):
    cache=directory/'people-observations.json'
    model_hash=file_sha256(weights['yolo11n.pt'])
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved.get('source_sha256') == source_hash and saved.get('model_sha256') == model_hash:
            samples=[]
            with FileFrameSource(source,mode='offline') as source_frames:
                next_sample=0.
                for frame in source_frames:
                    if frame.timestamp_ms>=next_sample:
                        samples.append(cv2.resize(frame.image,(960,540)))
                        next_sample+=700
                    if len(samples)>=12:break
            court=calibrate(samples,directory)
            (directory/'court.json').write_text(json.dumps(court,indent=2))
            return court,saved['frames']
    detector=PersonDetector(weights['yolo11n.pt'],device=_device())
    samples,people,batch=[],[],[]
    next_person=next_court=0.
    last=time.monotonic()
    def flush():
        if not batch:return
        boxes=detector([f.image for f in batch],image_size=960)
        people.extend(dict(timestamp_ms=f.timestamp_ms,boxes=b) for f,b in zip(batch,boxes))
        batch.clear()
    with FileFrameSource(source,mode='offline') as frames:
        for f in frames:
            if f.timestamp_ms >= next_court and len(samples)<12:
                samples.append(cv2.resize(f.image,(960,540)))
                next_court+=700
            if f.timestamp_ms >= next_person:
                from modules.media.types import TimestampedFrame
                batch.append(TimestampedFrame(f.frame_id,f.timestamp_ms,cv2.resize(f.image,(1920,1080))))
                next_person=f.timestamp_ms+110
                if len(batch)>=8:flush()
            if time.monotonic()-last>1:
                progress('正在标定球场并检测球员',min(.55,.55*f.timestamp_ms/info.duration_ms))
                last=time.monotonic()
    flush()
    court=calibrate(samples,directory)
    (directory/'court.json').write_text(json.dumps(court,indent=2))
    cache.write_text(json.dumps(dict(source_sha256=source_hash,model_sha256=model_hash,frames=people)))
    return court,people


def _players(people, inverse):
    result=[]
    previous={}
    for row in people:
        choices={}
        for box in row['boxes']:
            xy=transform(inverse,[[(box['x1']+box['x2'])/2,box['y2']]])[0]
            if not (-1.8<xy[0]<7 and -1.8<xy[1]<15.2):continue
            side='far' if xy[1]<6.7 else 'near'
            score=box['confidence']
            if side in previous:score-=.025*np.linalg.norm(xy-previous[side])
            if side not in choices or score>choices[side][0]:choices[side]=(score,dict(box=box,xy=xy.tolist(),side=side))
        selected=[v[1] for v in choices.values()]
        previous.update({p['side']:np.array(p['xy']) for p in selected})
        result.append(dict(timestamp_ms=row['timestamp_ms'],players=selected))
    return result


def _near_player(row, people, times):
    if not len(times):return None,math.inf
    k=int(np.argmin(abs(times-row['timestamp_ms'])))
    if abs(times[k]-row['timestamp_ms'])>220:return None,math.inf
    best,distance=None,math.inf
    for player in people[k]['players']:
        b=player['box'];h=b['y2']-b['y1'];cx=(b['x1']+b['x2'])/2
        # Crouching shrinks a detector box, but does not shorten the racket.
        # Estimate body scale from the same side's nearby actual detections.
        heights=[p['box']['y2']-p['box']['y1'] for j in np.flatnonzero(abs(times-row['timestamp_ms'])<=600)
                 for p in people[j]['players'] if p['side']==player['side']]
        if heights:h=max(h,float(np.median(heights)))
        # Racket can reach above or beside the body. Distance is relative to
        # observed body height, so far and near players use the same rule.
        dx=max(0,abs(row['x']-cx)-(b['x2']-b['x1'])/2)/h
        dy=max(b['y1']-row['y'],0,row['y']-b['y2'])/h
        low=max(0,(row['y']-b['y1'])/h-.5)
        d=math.sqrt(dx*dx+dy*dy+low*low)
        if d<distance:best,distance=player,d
    return best,distance


def _gap_contacts(valid, people, pt):
    """Recover contacts from observed turns and two independently fitted arcs.

    No hit is inserted merely to satisfy alternation. Every candidate carries
    its actual observation support and the interval hiding the contact.
    """
    t=np.array([r['timestamp_ms'] for r in valid])
    xy=np.array([[r['x'],r['y']] for r in valid])
    result=[]
    def add(ms, point, score, reason, bounds):
        row=dict(timestamp_ms=float(ms),x=float(point[0]),y=float(point[1]),confidence=.6)
        player,reach=_near_player(row,people,pt)
        if player is None or reach>.6:return
        result.append(dict(timestamp_ms=float(ms),row=row,player=player,score=score/(1+reach),reach=reach,
                           reason=reason,contact_interval_ms=list(map(float,bounds))))
    for i in range(1,len(valid)-1):
        a,b=(t[i]-t[i-1])/1000,(t[i+1]-t[i])/1000
        if min(a,b)>.18 and max(a,b)<=.8 and a+b<=1.2:
            va=(xy[i]-xy[i-1])/a;vb=(xy[i+1]-xy[i])/b
            na,nb=np.linalg.norm(va),np.linalg.norm(vb)
            player,reach=_near_player(valid[i],people,pt)
            if player and reach<.4 and min(na,nb)>100 and va@vb/max(na*nb,1)<.1:
                add(t[i],xy[i],1.5,'observed_contact_between_occluded_arcs',(t[i-1],t[i+1]))
    for i in np.flatnonzero((np.diff(t)>180)&(np.diff(t)<=800)):
        a,b=t[i],t[i+1]
        before=np.flatnonzero((t>=a-200)&(t<=a))
        after=np.flatnonzero((t>=b)&(t<=b+200))
        if len(before)<3 or len(after)<3:continue
        curves=[]
        for ids in (before,after):
            dt=(t[ids]-a)/1000
            curve=np.polynomial.polynomial.polyfit(dt,xy[ids],2)
            if np.sqrt(np.mean((np.polynomial.polynomial.polyval(dt,curve).T-xy[ids])**2))>6:break
            curves.append(curve)
        if len(curves)!=2:continue
        def position(c,ms):return np.polynomial.polynomial.polyval((ms-a)/1000,c)
        fit=minimize_scalar(lambda ms:np.linalg.norm(position(curves[0],ms)-position(curves[1],ms)),bounds=(a,b),method='bounded')
        if fit.fun>60 or not a+40<fit.x<b-40:continue
        velocities=[c[1]+2*c[2]*(fit.x-a)/1000 for c in curves]
        if np.linalg.norm(velocities[1]-velocities[0])<350:continue
        point=(position(curves[0],fit.x)+position(curves[1],fit.x))/2
        add(fit.x,point,1.8,'occluded_contact_arc_intersection',(a,b))
    return result


def _hits(rows, people):
    valid=[r for r in rows if r.get('x') is not None and r.get('y') is not None and r['confidence']>=.6]
    if len(valid)<6:return [],valid
    t=np.array([r['timestamp_ms'] for r in valid]);xy=np.array([[r['x'],r['y']] for r in valid])
    pt=np.array([p['timestamp_ms'] for p in people])
    candidates=[]
    for i in range(2,len(valid)-2):
        before=np.arange(max(0,i-4),i);after=np.arange(i+1,min(len(valid),i+5))
        velocities=[];residuals=[];contact_extrapolations=[]
        for ids in (before,after):
            seconds=(t[ids]-t[i])/1000
            curve=np.polynomial.polynomial.polyfit(seconds,xy[ids],min(2,len(ids)-1))
            fitted=np.polynomial.polynomial.polyval(seconds,curve).T
            contact_extrapolations.append(curve[0])
            velocities.append(curve[1]);residuals.append(float(np.sqrt(np.mean((fitted-xy[ids])**2))))
        local=np.flatnonzero(abs(t-t[i])<=220)
        dt=(t[local]-t[i])/1000
        hinge_supported=sum(dt<0)>=3 and sum(dt>0)>=3
        hinge=False;hinge_jump=gain=0.
        if hinge_supported:
            base=np.column_stack((np.ones(len(dt)),dt,dt**2))
            design=np.column_stack((base,np.maximum(dt,0),np.maximum(dt,0)**2))
            coefficients=np.linalg.lstsq(design,xy[local],rcond=None)[0]
            hinge_error=float(np.sqrt(np.mean((design@coefficients-xy[local])**2)))
            smooth_error=float(np.sqrt(np.mean((base@np.linalg.lstsq(base,xy[local],rcond=None)[0]-xy[local])**2)))
            hinge_jump=float(np.linalg.norm(coefficients[3]));gain=smooth_error-hinge_error
            hinge=hinge_error<15 and gain>2 and hinge_jump>350
        a,b=velocities;sa,sb=np.linalg.norm(a),np.linalg.norm(b)
        jump=float(np.linalg.norm(b-a));cosine=float(a@b/max(sa*sb,1))
        seam=float(np.linalg.norm(contact_extrapolations[0]-contact_extrapolations[1]))
        max_gap=float(max(np.diff(t[np.r_[before,i,after]])))
        smooth=((max_gap<=80 or seam<80) and max(residuals)<=14 and min(sa,sb)>=75 and max(sa,sb)<=6500
                and max(np.diff(t[np.r_[before,i,after]]))<=180
                and jump>=350 and (cosine<=.65 or jump>=.9*max(sa,sb)))
        # A short missing stretch around racket contact must not erase that
        # shot and merge two opponents' flights. Use the observed turn vertex
        # when both immediate segments support a sharp change; long gaps stay
        # unresolved rather than manufacturing a hit at a fixed interval.
        ta=(t[i]-t[i-1])/1000;tb=(t[i+1]-t[i])/1000
        va=(xy[i]-xy[i-1])/ta;vb=(xy[i+1]-xy[i])/tb
        na,nb=np.linalg.norm(va),np.linalg.norm(vb)
        turn_cos=float(va@vb/max(na*nb,1))
        turn_jump=float(np.linalg.norm(vb-va))
        vertex=(max(ta,tb)<=.4 and min(na,nb)>100 and max(na,nb)<6500
                and turn_cos<.25 and turn_jump>450)
        stable=np.flatnonzero((t>=t[i]-160)&(t<=t[i]))
        stalled=(hinge and hinge_error<6 and np.linalg.norm(coefficients[1])<100
                 and np.linalg.norm(coefficients[1]+coefficients[3])>300
                 and len(stable)>=3 and t[i]-t[stable[0]]>=120
                 and np.linalg.norm(np.ptp(xy[stable],axis=0))<=6)
        if not (smooth or vertex or stalled):continue
        player,reach=_near_player(valid[i],people,pt)
        if player is None or reach>.7:continue
        box=player['box']
        if valid[i]['y']>box['y2']-.04*(box['y2']-box['y1']):continue
        if stalled:score=1.8/(1+reach)
        elif smooth:score=jump/(250+max(sa,sb))/(1+reach)
        else:score=turn_jump/(250+max(na,nb))/(1+reach)
        if score<.5:continue
        candidates.append(dict(timestamp_ms=float(t[i]),row=valid[i],player=player,score=score,reach=reach,velocity_jump_px_s=jump,cosine=cosine,vertex_supported=vertex,direct_turn_supported=bool(hinge and hinge_error<6),reason='contact_after_observation_stall' if stalled else 'observed_velocity_turn'))
    candidates.extend(_gap_contacts(valid,people,pt))
    source_times=np.array([row['timestamp_ms'] for row in rows])
    for event in candidates:
        if event.get('reason')=='occluded_contact_arc_intersection':
            event['timestamp_ms']=float(source_times[np.argmin(abs(source_times-event['timestamp_ms']))])
            event['row']['timestamp_ms']=event['timestamp_ms']
    # Merge responses to the same velocity discontinuity, measured in frames;
    # there is no assumed shots-per-second or half-second interval constraint.
    clusters=[]
    for event in sorted(candidates,key=lambda e:e['timestamp_ms']):
        if clusters and event['timestamp_ms']-clusters[-1][0]['timestamp_ms']<=120:clusters[-1].append(event)
        else:clusters.append([event])
    # Direct motion/contact evidence outranks an inferred arc intersection.
    # A local vertex agreeing with both fitted velocities outranks jitter.
    # Alternation never changes which player owns an observed contact.
    priority=lambda event:(event.get('reason')!='occluded_contact_arc_intersection',
                           bool(event.get('vertex_supported') and event.get('cosine',1)<=.65),event['score'])
    hits=[max(group,key=priority) for group in clusters]
    filtered=[]
    for hit in hits:
        if filtered and hit['player']['side']==filtered[-1]['player']['side']:
            # A continuous single-player cluster cannot prove a new opponent
            # shot; keep the stronger event and report candidate counts below.
            between=t[(t>=filtered[-1]['timestamp_ms'])&(t<=hit['timestamp_ms'])]
            if hit.get('direct_turn_supported') and not filtered[-1].get('direct_turn_supported'):
                filtered[-1]=hit
            elif ((len(between)>1 and np.max(np.diff(between))>180)
                    or (hit.get('direct_turn_supported') and filtered[-1].get('direct_turn_supported')
                        and hit['timestamp_ms']-filtered[-1]['timestamp_ms']>440)):
                # Missing opponent evidence cannot erase this observed contact.
                # The analyzer separately marks the unsupported gap unresolved.
                hit=dict(hit,missing_opponent_before=True)
                filtered.append(hit)
            elif filtered[-1].get('direct_turn_supported') and not hit.get('direct_turn_supported'):
                continue
            elif priority(hit)>priority(filtered[-1]):filtered[-1]=hit
        else:filtered.append(hit)
    if valid:
        player,reach=_near_player(valid[0],people,pt)
        if player and reach<.7 and (not filtered or filtered[0]['player']['side']!=player['side']) and (not filtered or filtered[0]['timestamp_ms']-t[0]>160):
            filtered.insert(0,dict(timestamp_ms=float(t[0]),row=valid[0],player=player,score=None,reach=reach,reason='first_observed_flight_near_player'))
    if filtered:
        tail=[r for r in valid if r['timestamp_ms']>=filtered[-1]['timestamp_ms']]
        if len(tail)>=4 and tail[-1]['timestamp_ms']-tail[0]['timestamp_ms']>=120:
            positions=np.array([[r['x'],r['y']] for r in tail])
            if np.max(np.linalg.norm(positions-positions[0],axis=1))<25:
                filtered.pop()
    return filtered,valid


def _camera(court):
    projection=court.get('projection')
    return np.asarray(projection,float) if projection is not None else None


def _landing(flight, start, projection, receiver=None):
    if projection is None:return None,dict(reason='net_height_reference_unavailable')
    if len(flight)<9:return None,dict(reason='insufficient_flight_observations')
    times=np.array([(r['timestamp_ms']-flight[0]['timestamp_ms'])/1000 for r in flight])
    if times[-1]<.28 or np.max(np.diff(times))>.3:return None,dict(reason='sparse_flight_observations')
    observed=np.array([[r['x'],r['y']] for r in flight])
    def integrate(params,end,times_out):
        def rhs(t,state):
            velocity=state[3:];acc=np.array([0,0,-9.81])-params[6]*np.linalg.norm(velocity)*velocity
            return np.r_[velocity,acc]
        initial=[start[0]+params[0],start[1]+params[1],params[2],*params[3:6]]
        return solve_ivp(rhs,(0,max(end,.01)),initial,t_eval=times_out,rtol=2e-4,atol=1e-5,max_step=.04).y[:3].T
    def residual(params):
        xyz=integrate(params,times[-1],times)
        q=np.column_stack((xyz,np.ones(len(xyz))))@projection.T
        reprojection=q[:,:2]/q[:,2:3]
        # The racket contact may lie beside the feet, but cannot float freely
        # to compensate for a wrong shot boundary or a poor camera fit.
        receiver_prior=[] if receiver is None else ((xyz[-1,:2]-receiver)/.8).tolist()
        return np.r_[(reprojection-observed).ravel()/6,params[0]/.7,params[1]/.8,(params[2]-1.6)/1.2,receiver_prior]
    best=None
    for vz in (2,9,17):
        fit=least_squares(residual,[0,0,1.6,0,(-9 if start[1]>6.7 else 9),vz,.2],bounds=([-1.2,-1.5,.3,-35,-45,-25,.03],[1.2,1.5,3.5,35,45,35,.6]),loss='soft_l1',max_nfev=80)
        cost=float(np.mean(residual(fit.x)**2))
        if best is None or cost<best[0]:best=(cost,fit)
    _,fit=best
    future=np.arange(0,4.01,.02);xyz=integrate(fit.x,4.,future)
    below=np.flatnonzero(xyz[:,2]<=0)
    fitted=integrate(fit.x,times[-1],times)
    q=np.column_stack((fitted,np.ones(len(fitted))))@projection.T
    rmse=float(np.sqrt(np.mean((q[:,:2]/q[:,2:3]-observed)**2)))
    if len(below)==0 or rmse>10:return None,dict(reason='physical_fit_not_supported',reprojection_rmse_px=rmse)
    landing=xyz[below[0],:2];ground_time=float(future[below[0]])
    if receiver is not None and np.linalg.norm(fitted[-1,:2]-receiver)>2.:
        return None,dict(reason='receiver_contact_not_supported',reprojection_rmse_px=rmse)
    if np.min(fitted[:,2]) < -.1:
        return None,dict(reason='observed_flight_below_floor',reprojection_rmse_px=rmse)
    if ground_time<times[-1]-.04:return None,dict(reason='fit_reaches_floor_before_observed_flight',reprojection_rmse_px=rmse)
    if not np.isfinite(landing).all() or np.linalg.norm(landing-start)>25:return None,dict(reason='unstable_physical_extrapolation',reprojection_rmse_px=rmse)
    return landing.tolist(),dict(reason='gravity_quadratic_drag_fit',reprojection_rmse_px=rmse,flight_to_ground_s=ground_time,drag_per_m=float(fit.x[6]),fitted_contact_xy=[start[0]+float(fit.x[0]),start[1]+float(fit.x[1])],receiver_xy_prior=receiver)


def _detected_landing(flight, inverse, end_ms):
    if len(flight)<5:return None
    # A landing may bounce or slide after the first brief dwell. Look for the
    # first sharp deceleration in the final 700 ms, not only a perfectly still
    # final sample. Reject an airborne apex that resumes a long fast flight.
    for i in range(1,len(flight)-2):
        row=flight[i]
        if row['timestamp_ms']<end_ms-700:continue
        local=[r for r in flight[i:] if r['timestamp_ms']<=row['timestamp_ms']+140]
        if len(local)<3 or local[-1]['timestamp_ms']-row['timestamp_ms']<80:continue
        xy=np.array([[r['x'],r['y']] for r in local])
        if np.linalg.norm(np.ptp(xy,axis=0))>18:continue
        before=[r for r in flight[:i] if r['timestamp_ms']>=row['timestamp_ms']-200]
        if not before:continue
        prior=np.array([before[0]['x'],before[0]['y']])
        approach=np.linalg.norm(prior-xy[0])
        if approach<25:continue
        remaining=np.array([[r['x'],r['y']] for r in flight[i:]])
        if np.max(np.linalg.norm(remaining-xy[0],axis=1))>80:continue
        return transform(inverse,[xy[0]])[0].tolist()
    return None


def analyze(source, info, predictions, point_path, weights, directory, progress):
    source,point_path,directory=Path(source),Path(point_path),Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    rows,meta=_load_observations(point_path,source)
    if meta.get('reference_size')!=[1920,1080] or meta.get('model_sha256')!=file_sha256(weights['ball_track.pt']):
        raise ValueError('球点缓存参考尺寸或TrackNet权重哈希与本次分析不匹配。')
    court,people=_video_evidence(source,info,weights,directory,progress,meta['source_sha256'])
    inverse=np.linalg.inv(np.asarray(court['image_from_court']))
    players=_players(people,inverse)
    projection=_camera(court)
    court['diagnostics']['height_projection']='euclidean_floor_and_observed_net_tape' if projection is not None else 'unidentified'
    if projection is not None:court['projection']=projection.tolist()
    shots=[];rally_stats=[]
    for index,rally in enumerate(predictions):
        rally_id=rally.get('rally_id',index+1)
        selected=[r for r in rows if rally['start_ms']<=r['timestamp_ms']<=rally['end_ms']]
        hits,valid=_hits(selected,players)
        for j,hit in enumerate(hits):
            end_ms=hits[j+1]['timestamp_ms'] if j+1<len(hits) else rally['end_ms']
            flight=[r for r in valid if hit['timestamp_ms']<=r['timestamp_ms']<end_ms]
            next_hit=hits[j+1] if j+1<len(hits) else None
            next_opponent=next_hit is not None and next_hit['player']['side']!=hit['player']['side']
            supported_end=end_ms
            gap_reason=None
            for left,right in zip(flight,flight[1:]):
                if right['timestamp_ms']-left['timestamp_ms']>800:
                    following=[r['timestamp_ms'] for r in selected if r['timestamp_ms']>left['timestamp_ms']]
                    supported_end=min(supported_end,following[0] if following else end_ms)
                    gap_reason='unobserved_flight_may_contain_opponent_contact'
                    break
            if next_hit and next_hit.get('reason')=='occluded_contact_arc_intersection':
                left=next_hit['contact_interval_ms'][0]
                following=[r['timestamp_ms'] for r in selected if r['timestamp_ms']>left]
                if following and following[0]<supported_end:
                    supported_end=following[0];gap_reason='contact_hidden_between_observations'
            if next_hit and next_hit.get('missing_opponent_before'):
                opponents=[dict(timestamp_ms=p['timestamp_ms'],players=[q for q in p['players'] if q['side']!=hit['player']['side']]) for p in players]
                for row in flight:
                    if row['timestamp_ms']<=hit['timestamp_ms']:continue
                    player,reach=_near_player(row,opponents,np.array([p['timestamp_ms'] for p in opponents]))
                    if player and reach<.7:
                        supported_end=min(supported_end,row['timestamp_ms']);break
                gap_reason='opponent_contact_missing_between_same_side_hits'
            flight=[r for r in flight if r['timestamp_ms']<supported_end]
            start=hit['player']['xy']
            landing=_detected_landing(flight,inverse,end_ms) if j+1==len(hits) else None
            diagnostic=dict(reason='visible_stationary_flight_tail') if landing is not None else {}
            kind='detected_landing' if landing is not None else 'predicted_landing'
            if landing is None:landing,diagnostic=_landing(flight,start,projection,next_hit['player']['xy'] if next_opponent and supported_end==end_ms else None)
            start_source='player_foot_proxy'
            if 'fitted_contact_xy' in diagnostic:
                start=diagnostic['fitted_contact_xy'];start_source='fitted_racket_contact_projection'
            if landing is None and next_opponent:
                landing=next_hit['player']['xy'];kind='next_hit'
                diagnostic['fallback_reason']='next_opponent_hit_player_foot_position'
            elif landing is None:
                landing=_detected_landing(flight,inverse,end_ms) if next_hit is None else None
                kind='detected_landing' if landing is not None else 'unresolved'
                diagnostic['fallback_reason']='visible_stationary_flight_tail' if landing is not None else 'no_next_hit_or_ground_evidence'
            shots.append(dict(rally_id=rally_id,shot_id=0,start_ms=hit['timestamp_ms'],end_ms=supported_end,start_xy=start,end_xy=landing,end_kind=kind,diagnostics=dict(**diagnostic,start_source=start_source,hit_side=hit['player']['side'],hit_score=hit['score'],hit_method=hit.get('reason','observed_velocity_turn'),direct_turn_supported=hit.get('direct_turn_supported',False),contact_interval_ms=hit.get('contact_interval_ms',[hit['timestamp_ms'],hit['timestamp_ms']]),hit_reach_body_heights=hit['reach'],observations=len(flight),supported_until_ms=supported_end)))
            if supported_end<end_ms:
                shots.append(dict(rally_id=rally_id,shot_id=0,start_ms=supported_end,end_ms=end_ms,start_xy=None,end_xy=None,end_kind='unresolved',diagnostics=dict(reason=gap_reason,hit_side=None,observations=0)))
        for shot_id,shot in enumerate([s for s in shots if s['rally_id']==rally_id],1):shot['shot_id']=shot_id
        rally_stats.append(dict(rally_id=rally_id,observations=len(selected),valid_observations=len(valid),hits=len(hits)))
        progress('正在分析逐拍球路',.55+.44*(index+1)/max(1,len(predictions)))
    shots=constrain_shots(shots,players)
    constraint_actions={action:sum(s.get('diagnostics',{}).get('court_constraint',{}).get('action')==action for s in shots) for action in ('replace_end_with_next_hit','hide_arrow')}
    result=dict(schema_version=1,coordinate_system=dict(unit='m',width_m=5.18,length_m=13.4,x_direction='left_to_right',y_direction='far_to_near'),court=court,shots=shots,diagnostics=dict(observations=len(rows),valid_observations=sum(r.get('x') is not None for r in rows),person_frames=len(people),person_frames_with_both_players=sum(len(r['players'])==2 for r in players),end_kind_counts={kind:sum(s['end_kind']==kind for s in shots) for kind in ('predicted_landing','next_hit','detected_landing','unresolved')},court_constraint_actions=constraint_actions,court_constraint_start_estimates=sum('start_estimate' in s.get('diagnostics',{}).get('court_constraint',{}) for s in shots),court_constraint_start_repairs=sum(bool(s.get('diagnostics',{}).get('court_constraint',{}).get('start_repaired')) for s in shots),rallies=rally_stats,method='observed_contact_identity_before_inferred_arcs_v3',limitations=['Hit timing and contact positions are inferred, not annotated racket contact.','Floor homography is never applied to an airborne shuttle as a landing.']))
    (directory/'shot-paths.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (directory/'player-tracks.json').write_text(json.dumps(players))
    progress('球路分析完成',1.)
    return result
