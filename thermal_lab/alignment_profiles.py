"""Camera-bound target/distance presets. Distances are supplied by the operator."""
import json
import math
from pathlib import Path
from .auto_alignment import valid_region
from .workspace import validate_settings


def validate_profiles(value,camera_id):
    if not isinstance(value,dict):raise ValueError('Invalid alignment profile file')
    if value.get('schema')!=1 or value.get('camera_id')!=camera_id:raise ValueError('Alignment profiles belong to another camera')
    profiles=value.get('profiles',[])
    if not isinstance(profiles,list) or len(profiles)>24:raise ValueError('Maximum 24 alignment profiles per camera')
    result=[];names=set()
    for p in profiles:
        if not isinstance(p,dict) or not isinstance(p.get('alignment'),dict) or set(p['alignment'])!={'dx','dy','scale','angle'}:
            raise ValueError('Each profile requires a complete alignment')
        name=str(p.get('name','')).strip()
        if not name or len(name)>60 or name.casefold() in names:raise ValueError('Profile names must be unique and at most 60 characters')
        names.add(name.casefold());distance=p.get('distance_m')
        if distance is not None:
            if isinstance(distance,bool):raise ValueError('Invalid working distance')
            distance=float(distance)
            if not math.isfinite(distance) or not .05<=distance<=1000:raise ValueError('Working distance must be 0.05–1000 metres')
        result.append(dict(name=name,distance_m=distance,region=valid_region(p.get('region',[0,0,1,1])),
            alignment=validate_settings(dict(alignment=p.get('alignment',{})))['alignment']))
    return dict(schema=1,camera_id=camera_id,profiles=result)


def read_profiles(path,camera_id):
    path=Path(path)
    if not path.exists():return dict(schema=1,camera_id=camera_id,profiles=[])
    if path.stat().st_size>65536:raise ValueError('Profile file is too large')
    return validate_profiles(json.loads(path.read_text(encoding='utf-8')),camera_id)


def save_profiles(path,value):
    value=validate_profiles(value,value['camera_id']);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(path)


def at_distance(value,distance):
    value=validate_profiles(value,value['camera_id']);distance=float(distance)
    if not math.isfinite(distance) or not .05<=distance<=1000:raise ValueError('Working distance must be 0.05–1000 metres')
    points=sorted((p for p in value['profiles'] if p['distance_m'] is not None),key=lambda p:p['distance_m'])
    if len(points)<2:raise ValueError('Save verified profiles at two different distances first')
    if len({p['distance_m'] for p in points})!=len(points):raise ValueError('Distance prediction needs unique distances; rename/update duplicate profiles')
    if not points[0]['distance_m']<=distance<=points[-1]['distance_m']:raise ValueError('Distance is outside your calibrated range. Auto-align this target and save another profile.')
    for p in points:
        if distance==p['distance_m']:return dict(p['alignment'])
    a,b=next((a,b) for a,b in zip(points,points[1:]) if a['distance_m']<distance<b['distance_m'])
    t=(1/distance-1/a['distance_m'])/(1/b['distance_m']-1/a['distance_m'])
    result={k:a['alignment'][k]+t*(b['alignment'][k]-a['alignment'][k]) for k in ('dx','dy','scale')}
    delta=(b['alignment']['angle']-a['alignment']['angle']+180)%360-180
    result['angle']=(a['alignment']['angle']+t*delta+180)%360-180
    return validate_settings(dict(alignment=result))['alignment']
