"""Automatic fixed high-view court fit from persistent line evidence."""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

WIDTH, LENGTH = 5.18, 13.4


def _write_image(path: Path, image):
    # OpenCV's filename writer does not support every Windows Unicode path.
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"无法编码球场诊断图：{path.name}")
    path.write_bytes(encoded.tobytes())


def court_lines():
    lines = [((x, 0), (x, LENGTH)) for x in (-.46, 0, WIDTH, WIDTH + .46)]
    lines += [((-.46, y), (WIDTH + .46, y)) for y in (0, .76, 4.72, 8.68, 12.64, LENGTH)]
    lines += [((WIDTH / 2, a), (WIDTH / 2, b)) for a, b in ((0, 4.72), (8.68, LENGTH))]
    return lines


def transform(matrix, points):
    points = np.asarray(points, float)
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        homogeneous = np.column_stack((points, np.ones(len(points)))) @ np.asarray(matrix).T
        return homogeneous[:, :2] / homogeneous[:, 2:3]


def _samples():
    return np.concatenate([np.linspace(a, b, max(12, int(np.linalg.norm(np.subtract(b, a)) * 14)))
                           for a, b in court_lines()]).astype(np.float32)


def _euclidean_camera(h, net_line):
    """Fit one square-pixel camera to floor geometry and observed raised net.

    The principal point is assumed to be the image center. Net observations
    constrain point-to-line distance, not fabricated vertical image posts.
    """
    world = np.array([[x, y, 0.] for x in (-.46, 2.59, 5.64)
                      for y in (0., 4.72, 6.7, 8.68, 13.4)])
    floor_image = transform(h, world[:, :2])
    net_world = np.array([[-.46, 6.7, 1.55], [5.64, 6.7, 1.55]])
    line = np.cross([*net_line[:2], 1.], [*net_line[2:], 1.])
    line /= np.linalg.norm(line[:2])
    def unpack(params):
        focal = np.exp(params[0])
        k = np.array([[focal, 0., 960.], [0., focal, 540.], [0., 0., 1.]])
        rotation = Rotation.from_rotvec(params[1:4]).as_matrix()
        rotation[:, 2] *= -1
        return k @ np.column_stack((rotation, params[4:7]))
    def project(projection, xyz):
        q = np.column_stack((xyz, np.ones(len(xyz)))) @ projection.T
        return q[:, :2] / q[:, 2:3]
    def residual(params):
        projection = unpack(params)
        floor = (project(projection, world) - floor_image).ravel()
        net = np.column_stack((project(projection, net_world), np.ones(2))) @ line
        return np.r_[floor, net * 3.]
    candidates = []
    for focal in (900., 1600., 2800.):
        k = np.array([[focal, 0., 960.], [0., focal, 540.], [0., 0., 1.]])
        normalized = np.linalg.inv(k) @ h
        scale = 2 / (np.linalg.norm(normalized[:, 0]) + np.linalg.norm(normalized[:, 1]))
        r1, r2 = normalized[:, 0] * scale, normalized[:, 1] * scale
        # x right, y toward camera and z up form a left-handed world frame.
        # Optimize a rotation; unpack explicitly reverses its vertical column.
        rotation = np.column_stack((r1, r2, np.cross(r1, r2)))
        u, _, vt = np.linalg.svd(rotation)
        rotation = u @ vt
        initial = np.r_[np.log(focal), Rotation.from_matrix(rotation).as_rotvec(), normalized[:, 2] * scale]
        fit = least_squares(residual, initial, max_nfev=180,
                            bounds=([np.log(400.), *[-np.inf]*6], [np.log(10000.), *[np.inf]*6]))
        projection = unpack(fit.x)
        # Physical altitude must move image points upwards at the court.
        if projection[1, 2] * projection[2, 3] - projection[1, 3] * projection[2, 2] > 0:
            continue
        candidates.append((float(np.sqrt(np.mean(residual(fit.x)**2))), fit, projection))
    if not candidates:
        return None, dict(reason='height_orientation_unresolved')
    error, fit, projection = min(candidates, key=lambda row: row[0])
    net_error = float(np.max(np.abs(residual(fit.x)[-2:] / 3.)))
    diagnostic = dict(method='square-pixel-centered-principal-point-floor-and-net-v2',
                      focal_px=float(np.exp(fit.x[0])), fit_rmse_px=error,
                      net_line_max_error_px=net_error,
                      assumptions=['square pixels', 'principal point at image center', 'net posts 1.55m'])
    if error > 5. or net_error > 5. or not 410 < np.exp(fit.x[0]) < 9900:
        return None, dict(**diagnostic, reason='floor_and_net_camera_inconsistent')
    return projection, diagnostic

def calibrate(images, directory):
    """Fit all standard floor lines; no annotations or source identity are used."""
    if len(images) < 3:
        raise ValueError('自动标定需要至少三张真实视频图像。')
    image = np.median(np.stack([cv2.resize(i, (960, 540)) for i in images]), axis=0).astype(np.uint8)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] < 95) & (hsv[:, :, 2] > 145)).astype(np.uint8) * 255
    # Persistent thin bright structures distinguish floor lines from people.
    strokes = cv2.HoughLinesP(white, 1, np.pi / 1800, 65, minLineLength=95, maxLineGap=12)
    if strokes is None:
        raise ValueError('自动球场标定未发现足够的白色线条。')
    hs, vs = [], []
    for x1, y1, x2, y2 in strokes.reshape(-1, 4):
        dx, dy = x2-x1, y2-y1
        if abs(dy) < abs(dx) * .12 and abs(dx) > 180 and min(y1, y2) > 140:
            hs.append(np.array([x1, y1, x2, y2], float))
        if abs(dy) > abs(dx) * 1.5 and abs(dy) > 110:
            vs.append(np.array([x1, y1, x2, y2], float))
    def y_at(l, x):
        x1,y1,x2,y2=l
        return y1+(x-x1)*(y2-y1)/(x2-x1)
    def x_at(l, y):
        x1,y1,x2,y2=l
        return x1+(y-y1)*(x2-x1)/(y2-y1)
    def unique(lines, fn, gap):
        rows=[]
        for line in sorted(lines, key=lambda l: -np.linalg.norm(l[2:]-l[:2])):
            if all(abs(fn(line)-fn(old)) > gap for old in rows): rows.append(line)
        return rows
    net_candidates=list(hs)
    hs=unique(hs, lambda l:y_at(l,480),5)
    vs=unique(vs, lambda l:x_at(l,500),6)
    hs=sorted(hs,key=lambda l:y_at(l,480))[:16]
    left=[l for l in vs if 130 < x_at(l,500) < 450]
    right=[l for l in vs if 510 < x_at(l,500) < 850]
    samples=_samples()
    distance=cv2.distanceTransform(255-white,cv2.DIST_L2,3)
    def residual(corners):
        h=cv2.getPerspectiveTransform(np.array([[-.46,0],[5.64,0],[5.64,13.4],[-.46,13.4]],np.float32),np.asarray(corners,np.float32).reshape(4,2))
        xy=transform(h,samples)
        if not np.isfinite(xy).all():return np.full(len(samples),30.)
        return map_coordinates(distance,[xy[:,1],xy[:,0]],order=1,mode='constant',cval=30)
    def intersection(a,b):
        p=np.cross(np.cross([*a[:2],1],[*a[2:],1]),np.cross([*b[:2],1],[*b[2:],1]))
        return p[:2]/p[2]
    candidates=[]
    for a in hs:
      for b in hs:
       top,bottom=y_at(a,480),y_at(b,480)
       if not (160<top<330 and 400<bottom<535 and bottom-top>140):continue
       for l in left:
        for r in right:
         corners=np.array([intersection(a,l),intersection(a,r),intersection(b,r),intersection(b,l)])
         if not (250<corners[1,0]-corners[0,0]<550 and 350<corners[2,0]-corners[3,0]<800):continue
         d=residual(corners)
         score=float(np.mean(np.minimum(d,12)))
         candidates.append((score,corners))
    if not candidates:raise ValueError('自动球场标定未找到合理的标准场地线组合。')
    score,corners=min(candidates,key=lambda row:row[0])
    # Refine only around observed line intersections, so logos cannot pull the fit far away.
    fit=least_squares(residual,corners.ravel(),bounds=(corners.ravel()-8,corners.ravel()+8),diff_step=.002,loss='soft_l1',f_scale=2,max_nfev=70)
    if np.mean(np.minimum(residual(fit.x),12)) < score:corners=fit.x.reshape(4,2)
    d=residual(corners)
    floor_distance=d.copy()
    support=float(np.mean(d<3))
    floor_support=support
    if support < .62:raise ValueError(f'自动球场标定白线支持不足 ({support:.1%})。')
    corners*=2
    h=cv2.getPerspectiveTransform(np.array([[-.46,0],[5.64,0],[5.64,13.4],[-.46,13.4]],np.float32),corners.astype(np.float32))
    # The net tape is above the floor, spans the two posts, and extends wider
    # than the far baseline. Its known 1.55 m post height supplies an observable
    # height scale; a centered-camera focal estimate from floor lines does not.
    bases=transform(h,[[-.46,6.7],[5.64,6.7]])/2
    x=np.linspace(bases[0,0],bases[1,0],150)
    edge=np.r_[np.arange(10,35),np.arange(115,140)]
    net_fits=[]
    for line in net_candidates:
        y=np.array([y_at(line,v) for v in x])
        if abs((y[-1]-y[0])/(x[-1]-x[0])-(bases[1,1]-bases[0,1])/(bases[1,0]-bases[0,0]))>.006:continue
        if not (corners[:2,1].mean()/2-20 < y.mean() < bases[:,1].mean()-55):continue
        d=map_coordinates(distance,[y,x],order=1,mode='constant',cval=30)
        support=float(np.mean(d<2)+.5*np.mean(d[edge]<2))
        net_fits.append((support,line))
    controls=[]
    projection=None
    camera_diagnostic=dict(reason='net_tape_not_observed')
    net_support=None
    if net_fits:
        net_score,net_line=max(net_fits,key=lambda row:row[0])
        net_support=net_score/1.5
        if net_score>1.1:
            projection,camera_diagnostic=_euclidean_camera(h,net_line*2)
            if projection is not None:
                net_world=np.array([[-.46,6.7,1.55],[5.64,6.7,1.55]])
                q=np.column_stack((net_world,np.ones(2)))@projection.T
                controls=[dict(world=world.tolist(),image=(pixel[:2]/pixel[2]).tolist()) for world,pixel in zip(net_world,q)]
    overlay=cv2.resize(image,(1920,1080))
    for a,b in court_lines():
        xy=np.rint(transform(h,[a,b])).astype(int)
        cv2.line(overlay,tuple(xy[0]),tuple(xy[1]),(0,0,255),2,cv2.LINE_AA)
    directory.mkdir(parents=True,exist_ok=True)
    if controls:
        cv2.line(overlay,tuple(np.rint(controls[0]['image']).astype(int)),tuple(np.rint(controls[1]['image']).astype(int)),(0,255,255),3,cv2.LINE_AA)
    _write_image(directory/'court-calibration.jpg',overlay)
    _write_image(directory/'court-line-mask.png',white)
    return dict(image_from_court=h.tolist(),reference_size=[1920,1080],projection=projection.tolist() if projection is not None else None,controls=controls,diagnostics=dict(method='temporal-median-white-lines-standard-template-v2',sample_frames=len(images),line_support_fraction=floor_support,mean_line_distance_reference_px=float(np.mean(floor_distance)*2),net_line_support_fraction=net_support,camera=camera_diagnostic,doubles_corners=corners.tolist(),overlay='court-calibration.jpg'))
