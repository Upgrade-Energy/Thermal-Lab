"""Polygon geometry and cached thermal-pixel masks, independent of the display."""
from functools import lru_cache
import math
from .validation import finite, ValidationError


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _on_segment(p,a,b):
    return abs(_cross(a,b,p))<1e-12 and min(a[0],b[0])-1e-12<=p[0]<=max(a[0],b[0])+1e-12 and min(a[1],b[1])-1e-12<=p[1]<=max(a[1],b[1])+1e-12


def contains(vertices,x,y):
    """Even/odd inclusion, with boundary points included; supports concave shapes."""
    inside=False
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        if _on_segment((x,y),a,b):return True
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def vertices(item):
    return [(p['x'],p['y']) for p in item['vertices']]


@lru_cache(maxsize=128)
def polygon_pixels(points,width,height):
    # Include a pixel exactly when its center lies inside/on the polygon.
    low_x=max(0,math.ceil(min(p[0] for p in points)*width-.5))
    high_x=min(width-1,math.floor(max(p[0] for p in points)*width-.5))
    low_y=max(0,math.ceil(min(p[1] for p in points)*height-.5))
    high_y=min(height-1,math.floor(max(p[1] for p in points)*height-.5))
    return tuple(y*width+x for y in range(low_y,high_y+1) for x in range(low_x,high_x+1)
                 if contains(points,(x+.5)/width,(y+.5)/height))


def polygon_geometry(value):
    if not isinstance(value,list) or not 3<=len(value)<=64:raise ValidationError('A polygon needs 3–64 corners')
    if not all(isinstance(p,dict) for p in value):raise ValidationError('Invalid polygon corner')
    points=tuple((finite(p.get('x'),'Corner X',0,.999999999),finite(p.get('y'),'Corner Y',0,.999999999)) for p in value)
    if len(set(points))!=len(points):raise ValidationError('Polygon corners must be distinct')
    edges=list(zip(points,points[1:]+points[:1]))
    for i,(a,b) in enumerate(edges):
        c=points[(i+2)%len(points)]
        if _on_segment(c,a,b) or _on_segment(a,b,c):raise ValidationError('Polygon edges cannot double back')
        for j in range(i+1,len(edges)):
            if j==i+1 or (i==0 and j==len(edges)-1):continue
            c,d=edges[j]
            if (_cross(a,b,c)*_cross(a,b,d)<0 and _cross(c,d,a)*_cross(c,d,b)<0) or any(
                    (_on_segment(c,a,b),_on_segment(d,a,b),_on_segment(a,c,d),_on_segment(b,c,d))):
                raise ValidationError('Polygon edges cannot cross; undo or move a corner')
    if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in edges))<1e-10:raise ValidationError('Polygon corners cannot form a straight line')
    if not polygon_pixels(points,256,192):raise ValidationError('Polygon must cover at least one thermal pixel')
    return dict(shape='polygon',vertices=[dict(x=x,y=y) for x,y in points],
                x=min(p[0] for p in points),y=min(p[1] for p in points),
                x2=max(p[0] for p in points),y2=max(p[1] for p in points))


def area_contains(item,x,y):
    return contains(vertices(item),x,y) if item.get('shape')=='polygon' else item['x']<=x<=item['x2'] and item['y']<=y<=item['y2']


def moved(item,dx,dy):
    dx=max(-item['x'],min(dx,.999999999-item.get('x2',item['x'])))
    dy=max(-item['y'],min(dy,.999999999-item.get('y2',item['y'])))
    result=dict(item)
    for key in ('x','x2'):
        if key in item:result[key]=item[key]+dx
    for key in ('y','y2'):
        if key in item:result[key]=item[key]+dy
    if item.get('shape')=='polygon':result['vertices']=[dict(x=p['x']+dx,y=p['y']+dy) for p in item['vertices']]
    return result


def vertex_at(item,x,y):
    if item.get('shape')!='polygon':return None
    distances=[((p['x']-x)*256)**2+((p['y']-y)*192)**2 for p in item['vertices']]
    index=min(range(len(distances)),key=distances.__getitem__)
    return index if distances[index]<25 else None


def with_vertex(item,index,x,y):
    points=[dict(p) for p in item['vertices']];points[index]=dict(x=x,y=y)
    return dict(item,**polygon_geometry(points))
