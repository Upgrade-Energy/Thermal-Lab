"""Measured stereo calibration from paired views of a known planar target.

All image coordinates use native thermal units (256x192); optical coordinates
are divided by four. Calibration never changes the recorded sensor arrays.
"""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

SIZE=(256,192)
PATTERN=(7,5)


def camera_path(workspace,camera_id):
    key=hashlib.sha256(camera_id.casefold().encode()).hexdigest()[:16]
    return Path(workspace).parent/'stereo-calibration'/f'{key}.json'


def detect_pair(temperatures,optical):
    t=np.asarray(temperatures,np.float32).reshape(192,256)
    if not np.isfinite(t).all() or np.ptp(t)<.5:raise ValueError('Thermal pattern has too little contrast')
    lo,hi=np.percentile(t,[1,99]);gray=np.uint8(np.clip((t-lo)/max(hi-lo,.1)*255,0,255))
    visible=np.asarray(optical.convert('L'))
    found=[]
    for image,scale in ((gray,1),(visible,4)):
        ok,corners=cv2.findChessboardCornersSB(image,PATTERN,flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            ok,corners=cv2.findChessboardCorners(image,PATTERN,flags=cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
            if ok:corners=cv2.cornerSubPix(image,corners,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,30,.01))
        if not ok:raise ValueError('The 7 × 5 inner-corner pattern must be clearly visible in BOTH cameras')
        found.append((corners.reshape(-1,2)/scale).tolist())
    return dict(thermal=found[0],optical=found[1])


def object_points(square_mm):
    if not np.isfinite(square_mm) or not 2<=square_mm<=200:raise ValueError('Square spacing must be 2–200 mm')
    obj=np.zeros((35,3),np.float32);obj[:,:2]=np.mgrid[:7,:5].T.reshape(-1,2)*square_mm/1000
    return obj


def checked_pair(pair):
    values=[]
    for name in ('thermal','optical'):
        p=np.asarray(pair[name],np.float32)
        if p.shape!=(35,2) or not np.isfinite(p).all() or np.any(p<0) or np.any(p>np.array(SIZE)):
            raise ValueError('Invalid calibration corners')
        if cv2.contourArea(cv2.convexHull(p))<1000:raise ValueError('Move the pattern closer: it occupies too little of the image')
        values.append(p)
    return values


def solve_calibration(pairs,camera_id,square_mm):
    if not isinstance(camera_id,str) or not camera_id:raise ValueError('Camera identity is required')
    if not 12<=len(pairs)<=40:raise ValueError('Capture 12–40 varied target poses first')
    obj=object_points(square_mm);checked=[checked_pair(p) for p in pairs]
    for i,(t,_) in enumerate(checked):
        if any(np.linalg.norm(t-u,axis=1).mean()<3 for u,_ in checked[:i]):
            raise ValueError('Repeated target poses: move and tilt the pattern between captures')
    centers=np.array([t.mean(axis=0) for t,_ in checked])
    if np.any(np.ptp(centers,axis=0)<[25,18]):raise ValueError('Move the target across more of the image, horizontally and vertically')
    # Keep every fourth view entirely out of fitting for independent validation.
    train=[p for i,p in enumerate(checked) if i%4!=3];held=[p for i,p in enumerate(checked) if i%4==3]
    objects=[obj.copy() for _ in train];thermal=[p[0] for p in train];optical=[p[1] for p in train]
    flags=cv2.CALIB_FIX_K3
    rt,kt,dt,rvecs,_=cv2.calibrateCamera(objects,thermal,SIZE,None,None,flags=flags)
    ro,ko,do,_,_=cv2.calibrateCamera(objects,optical,SIZE,None,None,flags=flags)
    normals=np.array([cv2.Rodrigues(r)[0][:,2] for r in rvecs])
    if np.any(np.ptp(normals[:,:2],axis=0)<.12):raise ValueError('Tilt the pattern in both directions; front-facing views alone cannot calibrate the lenses')
    rms,kt,dt,ko,do,rotation,translation,_,_=cv2.stereoCalibrate(objects,thermal,optical,kt,dt,ko,do,SIZE,
        flags=cv2.CALIB_FIX_INTRINSIC,criteria=(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,100,1e-7))
    errors=[]
    for t,o in held:
        ok,r,v=cv2.solvePnP(obj,t,kt,dt)
        if not ok:raise ValueError('Validation pose could not be recovered')
        points=(rotation@(cv2.Rodrigues(r)[0]@obj.T+v)+translation).T
        predicted=cv2.projectPoints(points,np.zeros(3),np.zeros(3),ko,do)[0].reshape(-1,2)
        errors.append(float(np.sqrt(np.mean(np.sum((predicted-o)**2,axis=1)))))
    if max(rt,ro,rms)>1.2 or max(errors)>2:
        raise ValueError(f'Calibration rejected: fit {rms:.2f}px; held-out max {max(errors):.2f}px. Check corner ordering, target flatness, motion and coverage.')
    result=dict(schema=1,camera_id=camera_id,pattern=list(PATTERN),square_mm=float(square_mm),image_size=list(SIZE),
        thermal_matrix=kt.tolist(),thermal_distortion=dt.ravel().tolist(),optical_matrix=ko.tolist(),optical_distortion=do.ravel().tolist(),
        rotation=rotation.tolist(),translation_m=translation.ravel().tolist(),fit_rms_px=float(rms),validation_rms_px=errors,
        poses=len(pairs),pairs=pairs)
    return validate_calibration(result,camera_id)


def validate_calibration(value,camera_id):
    if not isinstance(value,dict) or value.get('schema')!=1 or value.get('camera_id')!=camera_id or value.get('image_size')!=list(SIZE):
        raise ValueError('Calibration does not match this camera or resolution')
    for key,shape in (('thermal_matrix',(3,3)),('optical_matrix',(3,3)),('rotation',(3,3)),('translation_m',(3,))):
        a=np.asarray(value[key],float)
        if a.shape!=shape or not np.isfinite(a).all():raise ValueError('Invalid calibration geometry')
    for key in ('thermal_matrix','optical_matrix'):
        k=np.array(value[key])
        if not 30<k[0,0]<3000 or not 30<k[1,1]<3000 or not np.allclose(k[2],[0,0,1]):raise ValueError('Implausible camera intrinsics')
    r=np.array(value['rotation'])
    if not np.allclose(r.T@r,np.eye(3),atol=1e-5) or np.linalg.det(r)<.99:raise ValueError('Invalid stereo rotation')
    if not .0001<np.linalg.norm(value['translation_m'])<.5:raise ValueError('Implausible sensor separation')
    for key in ('thermal_distortion','optical_distortion'):
        a=np.asarray(value[key],float)
        if a.shape!=(5,) or not np.isfinite(a).all() or np.max(np.abs(a))>10:raise ValueError('Invalid lens distortion')
    errors=np.asarray(value.get('validation_rms_px',[]),float)
    fit=float(value.get('fit_rms_px',float('inf')))
    if not np.isfinite(fit) or not 0<=fit<=1.2 or errors.size<3 or not np.isfinite(errors).all() or np.any(errors<0) or errors.max()>2:
        raise ValueError('Calibration has not passed held-out validation')
    return value


def save_calibration(path,value):
    validate_calibration(value,value['camera_id']);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(path)


def read_calibration(path,camera_id):
    path=Path(path)
    if not path.exists():return None
    if path.stat().st_size>512000:raise ValueError('Calibration file exceeds size limit')
    return validate_calibration(json.loads(path.read_text(encoding='utf-8')),camera_id)


def save_session(path,camera_id,pairs,square_mm):
    object_points(square_mm)
    if len(pairs)>40:raise ValueError('Too many calibration poses')
    for pair in pairs:checked_pair(pair)
    path=Path(path).with_suffix('.draft.json');path.parent.mkdir(parents=True,exist_ok=True)
    value=dict(schema=1,camera_id=camera_id,square_mm=float(square_mm),pairs=pairs)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value),encoding='utf-8');temporary.replace(path)


def read_session(path,camera_id):
    path=Path(path).with_suffix('.draft.json')
    if not path.exists():return [],25.
    if path.stat().st_size>512000:raise ValueError('Calibration session exceeds size limit')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema')!=1 or value.get('camera_id')!=camera_id or not isinstance(value.get('pairs'),list) or len(value['pairs'])>40:
        raise ValueError('Calibration session does not match this camera')
    object_points(value['square_mm'])
    for pair in value['pairs']:checked_pair(pair)
    return value['pairs'],value['square_mm']


def projection_maps(calibration,distance_m=1):
    """Raw thermal pixel -> raw optical coordinate at a reference depth in metres."""
    validate_calibration(calibration,calibration['camera_id'])
    if not np.isfinite(distance_m) or not .05<=distance_m<=1000:raise ValueError('Reference distance out of range')
    yy,xx=np.mgrid[:192,:256];pixels=np.stack([xx,yy],axis=-1).astype(np.float32).reshape(-1,1,2)
    rays=cv2.undistortPoints(pixels,np.array(calibration['thermal_matrix']),np.array(calibration['thermal_distortion'])).reshape(-1,2)
    points=np.column_stack([rays,np.ones(len(rays))])*distance_m
    points=points@np.array(calibration['rotation']).T+np.array(calibration['translation_m'])
    mapped=cv2.projectPoints(points,np.zeros(3),np.zeros(3),np.array(calibration['optical_matrix']),np.array(calibration['optical_distortion']))[0].reshape(192,256,2)
    mapped[points[:,2].reshape(192,256)<=0]=-1000
    return mapped[:,:,0].astype(np.float32),mapped[:,:,1].astype(np.float32)
