"""Friendly local camera names indexed by stable Windows identity."""
import json
from pathlib import Path


def read_names(path):
    path=Path(path)
    if not path.exists():return {}
    if path.stat().st_size>1024*1024:raise ValueError('Camera name file is too large')
    names=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(names,dict):raise ValueError('Invalid camera names')
    return {str(k).casefold():str(v)[:60] for k,v in names.items()}


def display_name(camera_id,names):
    return names.get(camera_id.casefold()) or ('TC001 Max · '+camera_id.rsplit('\\',1)[-1] if camera_id else 'No camera selected')


def save_name(path,camera_id,name):
    name=name.strip()
    if not camera_id:raise ValueError('Select a camera first')
    if not name or len(name)>60 or any(ord(c)<32 for c in name):raise ValueError('Use a camera name of 1–60 characters')
    names=read_names(path);names[camera_id.casefold()]=name
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(names,indent=2),encoding='utf-8');temp.replace(path)
    return names
