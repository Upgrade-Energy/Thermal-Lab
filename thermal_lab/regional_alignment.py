"""Conservative region-wise registration; unsupported regions never gain optical pixels."""
import time
import cv2
import numpy as np
from PIL import Image
from .auto_alignment import AlignmentCancelled
from .imaging import alignment_matrix


def similarity_maps(alignment):
    yy,xx=np.mgrid[:192,:256];p=np.stack([xx,yy,np.ones_like(xx)],axis=-1)@np.linalg.inv(alignment_matrix(alignment)).T
    return p[:,:,0].astype(np.float32),p[:,:,1].astype(np.float32)


def correlation(a,b):
    a=a-a.mean();b=b-b.mean()
    return float(np.sum(a*b)/max(1e-9,np.linalg.norm(a)*np.linalg.norm(b)))


def match_patch(fixed,moving,x,y,radius=12):
    half=12;patch=fixed[y-half:y+half,x-half:x+half]
    if patch.shape!=(24,24) or np.std(patch)<.12:return None
    x0,y0=x-half-radius,y-half-radius;x1,y1=x+half+radius,y+half+radius
    if x0<0 or y0<0 or x1>256 or y1>192:return None
    search=moving[y0:y1,x0:x1]
    scores=np.abs(cv2.matchTemplate(search,patch,cv2.TM_CCOEFF_NORMED))
    iy,ix=np.unravel_index(np.argmax(scores),scores.shape);best=float(scores[iy,ix])
    if best<.90:return None
    competing=scores.copy();competing[max(0,iy-3):iy+4,max(0,ix-3):ix+4]=-1
    if best-float(competing.max())<.06:return None
    dx,dy=int(ix-radius),int(iy-radius)
    if max(abs(dx),abs(dy))>=radius:return None  # Do not accept a clipped search optimum.
    matched=moving[y+dy-half:y+dy+half,x+dx-half:x+dx+half]
    polarity=1 if correlation(patch,matched)>=0 else -1
    if min(correlation(patch[:12],matched[:12])*polarity,correlation(patch[12:],matched[12:])*polarity)<.75:return None
    gy,gx=np.gradient(patch);my,mx=np.gradient(matched)
    tensor=np.array([[np.sum(gx*gx),np.sum(gx*gy)],[np.sum(gx*gy),np.sum(gy*gy)]])
    eig=np.linalg.eigvalsh(tensor)
    if eig[0]<.06*max(eig[1],1e-9):return None  # A single edge cannot constrain 2-D motion.
    orientation=correlation(np.stack([gx,gy]),np.stack([mx,my]))*polarity
    if orientation<.65:return None
    return dx,dy,best


def estimate_regions(temperatures,optical,maps,*,cancelled=lambda:False):
    start=time.monotonic();thermal=np.asarray(temperatures,np.float32).reshape(192,256)
    if not np.isfinite(thermal).all():raise ValueError('Invalid numerical thermal frame')
    mx,my=maps
    if mx.shape!=(192,256) or my.shape!=(192,256) or not np.isfinite(mx).all() or not np.isfinite(my).all():raise ValueError('Invalid registration map')
    gray=np.asarray(optical.convert('L').resize((256,192),Image.Resampling.BOX),np.float32)
    moving=cv2.remap(gray,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    valid=(mx>=1)&(mx<254)&(my>=1)&(my<190)
    # Blur both modalities consistently; matching accepts either contrast polarity.
    fixed=cv2.GaussianBlur(thermal,(3,3),.7);moving=cv2.GaussianBlur(moving,(3,3),.7)
    shift=np.zeros((192,256,2),np.float32);support=np.zeros((192,256),np.float32);cells=[]
    for y in range(24,169,16):
        for x in range(24,233,16):
            if cancelled():raise AlignmentCancelled('Regional alignment cancelled')
            if time.monotonic()-start>8:raise ValueError('Regional alignment exceeded its time budget')
            if not valid[y-24:y+24,x-24:x+24].all():continue
            found=match_patch(fixed,moving,x,y)
            if found is None:continue
            dx,dy,score=found
            reverse=match_patch(moving,fixed,x+dx,y+dy)
            if reverse is None or np.hypot(dx+reverse[0],dy+reverse[1])>1.5:continue
            # Small tiles avoid smoothing a displacement across an object boundary.
            shift[y-8:y+8,x-8:x+8]=[dx,dy];support[y-8:y+8,x-8:x+8]=1
            cells.append(dict(x=x,y=y,dx=dx,dy=dy,score=score))
    return dict(shift=shift,support=support,cells=cells,coverage=float(support.mean()),elapsed=time.monotonic()-start)


def render_regions(thermal_image,optical,maps,result,show_uncertainty=True):
    """Return a display image only. Never writes source images, temperatures or layouts."""
    h,w=768,1024;yy,xx=np.mgrid[:h,:w].astype(np.float32);shift=cv2.resize(result['shift'],(w,h),interpolation=cv2.INTER_NEAREST)
    sx=xx/4+shift[:,:,0];sy=yy/4+shift[:,:,1]
    mx=cv2.remap(maps[0],sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-1000)*4
    my=cv2.remap(maps[1],sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-1000)*4
    image=cv2.remap(np.asarray(optical),mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    support=cv2.resize(result['support'],(w,h),interpolation=cv2.INTER_NEAREST)>0
    support&=(mx>=0)&(mx<w-1)&(my>=0)&(my<h-1)
    thermal=np.asarray(thermal_image);output=thermal.copy()
    output[support]=np.uint8(.5*thermal[support].astype(float)+.5*image[support].astype(float))
    if show_uncertainty:
        hatch=(~support)&((xx.astype(int)+yy.astype(int))%32<2)
        output[hatch]=np.uint8(.4*output[hatch]+.6*np.array([244,174,58]))
    return Image.fromarray(output)
