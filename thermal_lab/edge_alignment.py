"""Selected-target outline registration, independent of visible/thermal brightness."""
import math
import time
import cv2
import numpy as np
from PIL import Image
from .workspace import validate_settings


def fit_edges(temperatures,optical,initial,region,*,guided=False,cancelled=lambda:False):
    from .auto_alignment import AlignmentCancelled,valid_region
    region=valid_region(region);initial=validate_settings(dict(alignment=initial))['alignment']
    t=np.asarray(temperatures,np.float32).reshape(192,256)
    if not np.isfinite(t).all():raise ValueError('Non-finite thermal frame')
    x0,y0,x1,y1=region;left,top,right,bottom=int(x0*256),int(y0*192),int(x1*256),int(y1*192)
    roi=t[top:bottom,left:right];lo,hi=np.percentile(roi,[2,98])
    if hi-lo<.5:raise ValueError('Too little thermal detail. Include the object outline and some surrounding background.')
    thermal=np.uint8(np.clip((t-lo)/(hi-lo)*255,0,255))
    visible=np.asarray(optical.convert('L').resize((256,192),Image.Resampling.BOX))
    def edges(image):
        smooth=cv2.GaussianBlur(image,(5,5),1)
        gx=cv2.Sobel(smooth,cv2.CV_32F,1,0);gy=cv2.Sobel(smooth,cv2.CV_32F,0,1)
        return cv2.Canny(smooth,25,65),np.mod(np.arctan2(gy,gx),np.pi),np.hypot(gx,gy)
    te,ta,tm=edges(thermal);oe,oa,om=edges(visible)
    # Recover a silhouette when the rectangle encloses a thermally distinct object.
    candidates=[];crop=cv2.GaussianBlur(thermal[top:bottom,left:right],(5,5),1)
    h,w=crop.shape
    for threshold in np.percentile(crop,np.arange(15,90,5)):
        for polarity in (False,True):
            mask=np.uint8(crop>threshold if polarity else crop<threshold)
            count,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
            for label in range(1,count):
                bx,by,bw,bh,area=stats[label]
                if area<.15*w*h or area>.93*w*h or bw<.8*w or bh<.8*h:continue
                foreground=labels==label
                border=[]
                if left>1:border.extend(foreground[:,0])
                if right<255:border.extend(foreground[:,-1])
                if top>1:border.extend(foreground[0])
                if bottom<191:border.extend(foreground[-1])
                touching=np.mean(border) if border else 0
                quality=(bw/w+bh/h)/2-2*touching-.2*np.linalg.norm((centers[label]-[w/2,h/2])/[w,h])
                candidates.append((quality,foreground))
    silhouette=False;quality=0
    if candidates:
        quality,mask=max(candidates,key=lambda item:item[0])
        if quality>.55:
            binary=np.zeros_like(thermal);binary[top:bottom,left:right]=np.uint8(mask)*255
            te,ta,tm=edges(binary);silhouette=True
    selected=np.zeros_like(te,bool);selected[top:bottom,left:right]=True
    selected[:2]=False;selected[-2:]=False;selected[:,:2]=False;selected[:,-2:]=False
    y,x=np.where((te>0)&selected)
    # The selected rectangle describes the object's extent. Interior hotspots and
    # printed labels need not correspond across modalities; emphasize its outline.
    boundary=np.minimum.reduce([(x-left)/max(1,right-left),(right-1-x)/max(1,right-left),
                                (y-top)/max(1,bottom-top),(bottom-1-y)/max(1,bottom-top)])
    outer=boundary<.20
    if not silhouette and np.count_nonzero(outer)>=25:x,y=x[outer],y[outer]
    if len(x)<25 or np.count_nonzero(oe)<25:raise ValueError('Too few shared outlines. Include the full target and a little background.')
    # Strong isolated thermal noise is not a useful object outline.
    if len(x)/max(1,roi.size)>.22:raise ValueError('Thermal target is too noisy for outline matching')
    if len(x)>1000:
        ids=np.linspace(0,len(x)-1,1000,dtype=int);x,y=x[ids],y[ids]
    angles=ta[y,x];weights=np.clip(tm[y,x]/max(1,np.median(tm[y,x])),.4,1.5)
    bins=12;ob=np.int32(oa/np.pi*bins)%bins;fields=[]
    for b in range(bins):
        difference=np.minimum((ob-b)%bins,(b-ob)%bins)
        field=np.uint8(~((oe>0)&(difference<=1)))
        fields.append(cv2.distanceTransform(field,cv2.DIST_L2,3))
    fields=np.stack(fields);base=np.array([initial[k] for k in ('dx','dy','scale','angle')],float)
    thermal_edges=np.zeros_like(te);thermal_edges[y,x]=255
    thermal_fields=[];tb=np.int32(ta/np.pi*bins)%bins
    for b in range(bins):
        difference=np.minimum((tb-b)%bins,(b-tb)%bins)
        thermal_fields.append(cv2.distanceTransform(np.uint8(~((thermal_edges>0)&(difference<=1))),cv2.DIST_L2,3))
    thermal_fields=np.stack(thermal_fields)
    all_distances=cv2.distanceTransform(np.uint8(thermal_edges==0),cv2.DIST_L2,3)
    vy,vx=np.where(oe>0);va=oa[vy,vx]
    started=time.monotonic();evaluations=0
    def evaluate(p,details=False):
        nonlocal evaluations
        evaluations+=1
        if cancelled():raise AlignmentCancelled('Alignment cancelled')
        if time.monotonic()-started>15:raise ValueError('Outline search timed out; try a smaller target')
        dx,dy,scale,angle=p
        if not (-512<=dx<=512 and -384<=dy<=384 and .1<=scale<=8 and -180<=angle<=180):return (-1,0) if details else -1
        if abs(angle-base[3])>(3 if guided else 5) or abs(dx-base[0])>(8 if guided else 64) or abs(dy-base[1])>(8 if guided else 64) or not ((.88 if guided else .6)<=scale/base[2]<=(1.12 if guided else 1.8)):
            return (-1,0) if details else -1
        a=math.radians(angle);c,s=math.cos(a)/scale,math.sin(a)/scale
        u=x-128-dx;v=y-96-dy;ox=c*u+s*v+128;oy=-s*u+c*v+96
        good=(ox>=0)&(ox<255)&(oy>=0)&(oy<191)
        if good.mean()<.9:return (-1,0) if details else -1
        bx=np.clip(ox,0,254.999);by=np.clip(oy,0,190.999);ix=bx.astype(int);iy=by.astype(int);fx=bx-ix;fy=by-iy
        b=np.int32(np.mod(angles-a,np.pi)/np.pi*bins)%bins
        distance=(fields[b,iy,ix]*(1-fx)*(1-fy)+fields[b,iy,ix+1]*fx*(1-fy)+fields[b,iy+1,ix]*(1-fx)*fy+fields[b,iy+1,ix+1]*fx*fy)*scale
        closeness=np.exp(-.5*(distance/2)**2);closeness[~good]=0
        value=float(np.average(closeness,weights=weights))
        fc,fs=math.cos(a)*scale,math.sin(a)*scale
        px=fc*(vx-128)-fs*(vy-96)+128+dx;py=fs*(vx-128)+fc*(vy-96)+96+dy
        selected=(px>=left)&(px<right)&(py>=top)&(py<bottom)
        boundary=np.minimum.reduce([(px-left)/max(1,right-left),(right-px)/max(1,right-left),(py-top)/max(1,bottom-top),(bottom-py)/max(1,bottom-top)])
        selected&=boundary<.20
        if np.count_nonzero(selected)<15:return (-1,0) if details else -1
        tx=np.clip(px[selected],0,255).astype(int);ty=np.clip(py[selected],0,191).astype(int)
        vb=np.int32(np.mod(va[selected]+a,np.pi)/np.pi*bins)%bins
        reverse_distance=np.minimum(thermal_fields[vb,ty,tx],100)
        nearby=all_distances[ty,tx]<5
        precision=float(np.mean(np.exp(-.5*(reverse_distance[nearby]/2)**2))) if nearby.any() else 0
        value=.7*value+.3*precision
        # A weak prior breaks ties without rewarding a visually unrelated rotation.
        value-=.002*abs(angle-base[3])+.0001*(abs(dx-base[0])+abs(dy-base[1]))
        return (value,float(np.mean((distance<2.5)&good))) if details else value
    baseline=evaluate(base);proposals=[(baseline,base.copy())]
    shifts=(-6,-3,0,3,6) if guided else tuple(range(-48,49,8))
    scales=(.94,1,1.06) if guided else (.75,.9,1,1.15,1.3,1.5,1.7)
    for scale in scales:
        for dx in shifts:
            for dy in shifts:
                p=base+np.array([dx,dy,base[2]*(scale-1),0]);proposals.append((evaluate(p),p))
    seeds=[]
    for score,p in sorted(proposals,key=lambda item:item[0],reverse=True):
        if all(np.linalg.norm((p-q)/[10,10,.12,3])>1 for _,q in seeds):seeds.append((score,p))
        if len(seeds)==18:break
    for scale in scales:
        p=base.copy();p[2]*=scale;seeds.append((evaluate(p),p))
    fitted=[]
    for score,p in seeds:
        for step in ([3,3,.025,1],[1,1,.01,.3],[.25,.25,.002,.1]):
            for _ in range(20):
                choices=[(score,p)]
                for axis in range(4):
                    for sign in (-1,1):
                        q=p.copy();q[axis]+=step[axis]*sign;choices.append((evaluate(q),q))
                value,q=max(choices,key=lambda item:item[0])
                if value<=score+1e-5:break
                score,p=value,q
        fitted.append((score,p))
    score,p=max(fitted,key=lambda item:item[0]);score,support=evaluate(p,True)
    alternatives=[v for v,q in fitted if np.linalg.norm((p-q)/[6,6,.08,3])>1]
    margin=score-max(alternatives) if alternatives else score
    orientation_bins=len(np.unique(np.int32(angles/(np.pi/4))))
    supported=(score>.50 and support>.60) or (score>.62 and support>.50)
    reliable=bool(supported and margin>.015 and orientation_bins>=2)
    return dict(alignment={k:float(v) for k,v in zip(('dx','dy','scale','angle'),p)},region=region,
        score=score,validation_score=support,initial_score=baseline,margin=margin,reliable=reliable,
        evaluations=evaluations,method='outlines',edge_count=len(x),silhouette=silhouette,silhouette_quality=float(quality),outline_points=np.stack([x,y],axis=1).tolist(),
        message='Target outlines matched. Inspect the preview, then Apply to live.' if reliable else 'Outline match is ambiguous. Box the same target in the optical image to guide it.')
