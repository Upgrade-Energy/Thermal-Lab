"""Region-based multimodal registration. Estimates display geometry, never depth."""
import math
import time
import numpy as np
from PIL import Image, ImageFilter
from .workspace import validate_settings


class AlignmentCancelled(Exception): pass


def valid_region(region):
    if not isinstance(region,(list,tuple)) or len(region)!=4:
        raise ValueError('Select a rectangular target region')
    r=[float(x) for x in region]
    if not all(math.isfinite(x) and 0<=x<=1 for x in r) or r[2]-r[0]<.1 or r[3]-r[1]<.1:
        raise ValueError('Select a target at least one tenth of the image width and height')
    return r


def alignment_from_regions(thermal_region,optical_region,angle=0):
    """Initialize from the same object's bounding boxes in untransformed sensors."""
    t=valid_region(thermal_region);o=valid_region(optical_region)
    scale=math.sqrt((t[2]-t[0])*(t[3]-t[1])/((o[2]-o[0])*(o[3]-o[1])))
    tx,ty=(t[0]+t[2])*128,(t[1]+t[3])*96
    ox,oy=(o[0]+o[2])*128-128,(o[1]+o[3])*96-96
    a=math.radians(angle);c,s=math.cos(a)*scale,math.sin(a)*scale
    return validate_settings(dict(alignment=dict(dx=tx-128-c*ox+s*oy,dy=ty-96-s*ox-c*oy,scale=scale,angle=angle)))['alignment']


def fit_alignment(temperatures, optical, initial, region=(0,0,1,1), *, guided=False,cancelled=lambda:False):
    """Bounded similarity search using normalized mutual information.

    Thermal and optical brightness need not agree. Scores are relative evidence,
    not a probability, calibration accuracy, or distance measurement.
    """
    region=valid_region(region);initial=validate_settings(dict(alignment=initial))['alignment']
    thermal=np.asarray(temperatures,dtype=np.float32).reshape(192,256)
    if not np.isfinite(thermal).all():raise ValueError('Non-finite thermal frame')
    optical=np.asarray(optical.convert('L').resize((256,192),Image.Resampling.BOX).filter(ImageFilter.GaussianBlur(1)),dtype=np.float32)
    x0,y0,x1,y1=region
    yy,xx=np.mgrid[int(y0*192):min(192,int(y1*192)),int(x0*256):min(256,int(x1*256))]
    x=xx.ravel().astype(float);y=yy.ravel().astype(float);fixed=thermal[yy,xx].ravel()
    if np.percentile(fixed,95)-np.percentile(fixed,5)<.5 or np.std(optical)<2:
        raise ValueError('Too little thermal or optical detail. Use a stationary target with visible and thermal edges.')
    rng=np.random.default_rng(841);ids=rng.permutation(len(x))
    train=ids[:min(2200,len(ids)//2)];held=ids[len(train):][:3500]
    lo,hi=np.percentile(fixed,[2,98]);bins=24
    fixed_bins=np.clip((fixed-lo)/max(hi-lo,.01)*(bins-1),0,bins-1).astype(int)
    olo,ohi=np.percentile(optical,[1,99]);optical=np.clip((optical-olo)/max(ohi-olo,1)*(bins-1),0,bins-1)
    start=time.monotonic();calls=0
    def score(p, indices=train):
        nonlocal calls
        calls+=1
        if cancelled():raise AlignmentCancelled('Alignment cancelled')
        if time.monotonic()-start>25:raise ValueError('Alignment search timed out. Select a smaller target region.')
        dx,dy,scale,angle=p
        if not (-512<=dx<=512 and -384<=dy<=384 and .1<=scale<=8 and -180<=angle<=180):return -1.
        if guided and (abs(dx-initial['dx'])>8 or abs(dy-initial['dy'])>8 or abs(scale/initial['scale']-1)>.12 or abs(angle-initial['angle'])>3):return -1.
        a=math.radians(angle);c,s=math.cos(a)/scale,math.sin(a)/scale
        u=x[indices]-128-dx;v=y[indices]-96-dy
        ox=c*u+s*v+128;oy=-s*u+c*v+96
        good=(ox>=0)&(ox<255)&(oy>=0)&(oy<191)
        overlap=float(good.mean())
        if overlap<.9:return -1.
        ox=ox[good];oy=oy[good];ix=ox.astype(int);iy=oy.astype(int);fx=ox-ix;fy=oy-iy
        moving=(optical[iy,ix]*(1-fx)*(1-fy)+optical[iy,ix+1]*fx*(1-fy)+
                optical[iy+1,ix]*(1-fx)*fy+optical[iy+1,ix+1]*fx*fy).astype(int)
        joint=np.bincount(fixed_bins[indices][good]*bins+moving,minlength=bins*bins).reshape(bins,bins).astype(float)
        joint/=joint.sum();a1=joint.sum(axis=1);a2=joint.sum(axis=0)
        def entropy(p):return -float(np.sum(p[p>0]*np.log(p[p>0])))
        h1,h2=entropy(a1),entropy(a2)
        if min(h1,h2)<.4:return -1.
        mi=h1+h2-entropy(joint)
        # Correct the leading finite-sample bias; penalize losing target coverage.
        bias=(np.count_nonzero(a1)-1)*(np.count_nonzero(a2)-1)/(2*len(moving))
        return (mi-bias)/math.sqrt(h1*h2)-.5*(1-overlap)
    base=np.array([initial[k] for k in ('dx','dy','scale','angle')]);initial_score=score(base)
    proposals=[(initial_score,base.copy())]
    # Search around the current working-distance setting; identity is also a seed.
    for scale in sorted(set([base[2]*(.94 if guided else .8),base[2],base[2]*(1.06 if guided else 1.2),1.])):
        for angle in (base[3]-(2 if guided else 8),base[3],base[3]+(2 if guided else 8)):
            for dx in ((-6,0,6) if guided else (-48,-24,0,24,48)):
                for dy in ((-6,0,6) if guided else (-48,-24,0,24,48)):
                    p=base+np.array([dx,dy,scale-base[2],angle-base[3]])
                    proposals.append((score(p),p))
    proposals.append((score(np.array([0.,0.,1.,0.])),np.array([0.,0.,1.,0.])))
    seeds=[]
    for value,p in sorted(proposals,key=lambda item:item[0],reverse=True):
        if all(np.linalg.norm((p-q)/[12,12,.12,5])>1 for _,q in seeds):seeds.append((value,p))
        if len(seeds)==5:break
    fitted=[]
    for value,p in seeds:
        p=p.copy()
        for step in (np.array([12,12,.08,4]),np.array([4,4,.025,1]),np.array([1,1,.008,.3]),np.array([.25,.25,.002,.1])):
            for _ in range(14):
                options=[(value,p)]
                for axis in range(4):
                    for direction in (-1,1):
                        candidate=p.copy();candidate[axis]+=direction*step[axis];options.append((score(candidate),candidate))
                best,q=max(options,key=lambda item:item[0])
                if best<=value+1e-5:break
                value,p=best,q
        fitted.append((value,p))
    value,p=max(fitted,key=lambda item:item[0]);validation=score(p,held);baseline_validation=score(base,held)
    alternatives=[v for v,q in fitted if np.linalg.norm((p-q)/[8,8,.08,4])>1]
    margin=value-max(alternatives) if alternatives else value
    # A high information score alone can favor unrelated hot/visible structures.
    # Near/far parallax should not require a large change in sensor rotation.
    plausible=bool(abs(p[3]-base[3])<=8 and .65<=p[2]/base[2]<=1.5 and max(abs(p[0]-base[0]),abs(p[1]-base[1]))<=64)
    reliable=bool(plausible and value>.10 and validation>.08 and margin>.015 and validation>=baseline_validation-.01)
    return dict(alignment={k:float(v) for k,v in zip(('dx','dy','scale','angle'),p)},
        region=region,score=float(value),validation_score=float(validation),initial_score=float(initial_score),
        margin=float(margin),plausible_geometry=plausible,reliable=reliable,evaluations=calls,
        message='Candidate found. Check the target outline in the preview before applying.' if reliable else
                'Uncertain match. Try a tighter region with shared edges, or enable optical target guidance and box the same object.')
