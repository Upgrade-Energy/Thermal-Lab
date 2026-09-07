"""Validated measurement layouts and display presets."""
import json
from pathlib import Path
from .validation import finite, ValidationError


def validate_settings(value):
    result = dict(schema=1, alignment={}, points=[], areas=[])
    if not isinstance(value, dict): raise ValidationError('Workspace must be an object')
    alignment = value.get('alignment', {})
    for key, default, low, high in [('dx',0,-512,512),('dy',0,-384,384),('scale',1,.1,8),('angle',0,-180,180)]:
        result['alignment'][key] = finite(alignment.get(key,default), key,low,high)
    result['camera_id'] = str(value.get('camera_id',''))[:256]
    ids=set()
    for kind in ('points','areas'):
        items=value.get(kind,[])
        if not isinstance(items,list) or len(items)>64: raise ValidationError('Maximum 64 measurements per type')
        for item in items:
            if not isinstance(item,dict): raise ValidationError('Invalid measurement')
            name=str(item.get('name','')).strip()
            identifier=str(item.get('id','')).strip()
            if not name or len(name)>80 or not identifier or identifier in ids:
                raise ValidationError('Each measurement needs a name and unique ID')
            ids.add(identifier)
            entry=dict(id=identifier,name=name)
            for key in (('x','y') if kind=='points' else ('x','y','x2','y2')):
                entry[key]=finite(item.get(key),key,0,.999999999)
            if kind=='areas' and (entry['x2']<entry['x'] or entry['y2']<entry['y']):
                raise ValidationError('Rectangle corners are reversed')
            result[kind].append(entry)
    return result


def save_settings(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(validate_settings(value),indent=2),encoding='utf-8')
    temp.replace(path)


def read_settings(path):
    path=Path(path)
    if path.stat().st_size>1024*1024: raise ValidationError('Workspace exceeds 1 MiB')
    return validate_settings(json.loads(path.read_text(encoding='utf-8')))


def measurement_values(frame, settings):
    from .thermal import measurements
    # IDs avoid collisions when two user-facing names are the same.
    camera={key:[dict(item,name=item['id']) for item in settings[key]] for key in ('points','areas')}
    return measurements(frame,camera)
