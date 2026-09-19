"""Automatic display markers in original sensor coordinates; no workspace mutation."""
import numpy as np
from .imaging import sensor_to_view


def extrema(values,width=256,height=192):
    data=np.asarray(values,dtype=float)
    if data.size!=width*height:raise ValueError('Temperature grid dimensions do not match')
    data=data.reshape(-1);valid=np.isfinite(data)
    if not valid.any():return []
    low=int(np.argmin(np.where(valid,data,np.inf)))
    high=int(np.argmax(np.where(valid,data,-np.inf)))
    def item(label,index,color):
        return dict(label=label,x=index%width+.5,y=index//width+.5,value=float(data[index]),color=color)
    if data[low]==data[high]:return [item('Hot / Cold',low,'#b9e4ff')]
    return [item('Hot',high,'#ffb389'),item('Cold',low,'#81d7ff')]


def draw_extrema(canvas,markers,viewport,rotation,tag='extrema'):
    x,y,scale,_,_,left,right,top,bottom=viewport
    boxes=[]
    for marker in markers:
        sx,sy=sensor_to_view(marker['x'],marker['y'],rotation);px=x+sx*scale;py=y+sy*scale
        if not(left<=px<right and top<=py<bottom):continue
        color=marker['color']
        canvas.create_oval(px-6,py-6,px+6,py+6,outline='#0c1626',width=5,tags=tag)
        canvas.create_oval(px-6,py-6,px+6,py+6,outline=color,width=2,tags=tag)
        for coords in [(px-10,py,px+10,py),(px,py-10,px,py+10)]:canvas.create_line(*coords,fill=color,width=2,tags=tag)
        text=f"{marker['label']}  {marker['value']:.1f} °C"
        label=canvas.create_text(0,0,text=text,fill=color,font=('Segoe UI',10,'bold'),anchor='nw',tags=tag,width=max(1,right-left-20))
        bounds=canvas.bbox(label);w=bounds[2]-bounds[0]+16;h=bounds[3]-bounds[1]+10
        if w>right-left or h>bottom-top:
            canvas.delete(label);continue
        def overlap(location):
            lx,ly=location
            return sum(max(0,min(lx+w,b[2])-max(lx,b[0]))*max(0,min(ly+h,b[3])-max(ly,b[1])) for b in boxes)
        candidates=[]
        for cy in [py-h-9,py+14]+[edge for b in boxes for edge in (b[3]+6,b[1]-h-6)]:
            for cx in (px+13,px-w-13):
                location=(max(left,min(cx,right-w)),max(top,min(cy,bottom-h)))
                candidates.append(location)
                if not overlap(location):break
            if not overlap(candidates[-1]):break
        lx,ly=min(candidates,key=overlap)
        canvas.create_line(px,py,max(lx,min(px,lx+w)),max(ly,min(py,ly+h)),fill=color,width=1,tags=tag)
        canvas.coords(label,lx+8,ly+5)
        box=canvas.create_rectangle(lx,ly,lx+w,ly+h,fill='#14243a',outline=color,width=1,tags=tag)
        canvas.tag_raise(label,box);boxes.append((lx,ly,lx+w,ly+h))
