"""Named extrema measurements. Positions always refer to original thermal pixels."""
import copy
import uuid
import numpy as np
from .regions import polygon_pixels, vertices


def tracked_values(frame, points, areas):
    """Evaluate each search region once; ties choose the first row-major pixel."""
    w,h=frame['width'],frame['height']
    data=np.asarray(frame['temperatures'],dtype=float).reshape(-1)
    regions={a['id']:a for a in areas};cache={};result={}
    for item in points:
        if not item.get('tracking'):continue
        region_id=item.get('region_id')
        if region_id not in cache:
            if region_id is None:indices=np.arange(w*h)
            else:
                area=regions[region_id]
                if area.get('shape')=='polygon':indices=np.asarray(polygon_pixels(tuple(vertices(area)),w,h),dtype=int)
                else:
                    x,y=min(w-1,int(area['x']*w)),min(h-1,int(area['y']*h))
                    x2,y2=min(w-1,int(area['x2']*w)),min(h-1,int(area['y2']*h))
                    indices=(np.arange(y,y2+1)[:,None]*w+np.arange(x,x2+1)).reshape(-1)
            if not len(indices) or not np.isfinite(data[indices]).all():
                raise ValueError('Tracking region must contain finite thermal pixels')
            block=data[indices]
            cache[region_id]={'hottest':int(indices[np.argmax(block)]),'coldest':int(indices[np.argmin(block)])}
        index=cache[region_id][item['tracking']];px,py=index%w,index//w
        value=dict(kind='point',value=float(data[index]),tracking=item['tracking'],
                   x=(px+.5)/w,y=(py+.5)/h,pixel_x=px,pixel_y=py)
        if region_id is not None:value['region_id']=region_id
        result[item['name']]=value
    return result


def add_tracker(settings, tracking, selected=None, selected_region=False):
    """Create or select a tracker, without mutating a live or recorded layout."""
    from .workspace import validate_settings
    if tracking not in ('hottest','coldest'):raise ValueError('Choose hottest or coldest')
    region=None
    if selected_region:
        # Selecting an existing tracker retains its region when adding its counterpart.
        target=next((p.get('region_id') for p in settings['points'] if p['id']==selected),None) or selected
        region=next((a for a in settings['areas'] if a['id']==target),None)
        if region is None:raise ValueError('Select a rectangle or polygon in the measurement list first')
    region_id=region['id'] if region else None
    existing=next((p for p in settings['points'] if p.get('tracking')==tracking and p.get('region_id')==region_id),None)
    if existing:return settings,existing
    item=dict(id=uuid.uuid4().hex,name=(tracking.title()+' · '+(region['name'] if region else 'whole image'))[:80],
              x=.5,y=.5,tracking=tracking)
    if region:item['region_id']=region_id
    result=validate_settings(dict(settings,points=settings['points']+[item]))
    return result,item


def remove_measurement(settings, identifier):
    result=copy.deepcopy(settings)
    for group in ('points','areas'):
        result[group]=[item for item in result[group] if item['id']!=identifier and item.get('region_id')!=identifier]
    return result


def positioned(item, values):
    """Resolve a dynamic point for display; never substitute its placeholder position."""
    if not item.get('tracking'):return item
    value=values.get(item['id'],{})
    if 'pixel_x' not in value:return None
    return dict(item,x=value['x'],y=value['y'])


def markers(settings, values, width=256, height=192):
    result=[]
    for item in settings.get('points',[]):
        if not item.get('tracking'):continue
        point=positioned(item,values)
        if point is not None:
            result.append(dict(label=item['name'],x=point['x']*width,y=point['y']*height,
                               value=values[item['id']]['value'],color='#ffb389' if item['tracking']=='hottest' else '#81d7ff'))
    return result


def geometry_for_history(definition, definitions):
    geometry={k:v for k,v in definition.items() if k not in ('name','id')}
    if definition.get('region_id'):
        region=definitions[definition['region_id']]
        geometry['search_region']={k:v for k,v in region.items() if k not in ('name','id')}
    return geometry


def overview_markers(extremes, settings):
    """Avoid putting a duplicate overview label under a named full-image tracker."""
    active={p.get('tracking') for p in settings.get('points',[]) if not p.get('region_id')}
    result=[]
    for marker in extremes:
        kinds=('hottest','coldest') if marker['label']=='Hot / Cold' else ('hottest',) if marker['label']=='Hot' else ('coldest',)
        remaining=[k for k in kinds if k not in active]
        if remaining:
            label='Hot / Cold' if len(remaining)==2 else 'Hot' if remaining[0]=='hottest' else 'Cold'
            result.append(dict(marker,label=label))
    return result
