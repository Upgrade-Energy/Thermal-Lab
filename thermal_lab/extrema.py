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
        lx=max(left,min(px+13,right-w));ly=max(top,min(py-h-9,bottom-h))
        if any(lx<b[2] and lx+w>b[0] and ly<b[3] and ly+h>b[1] for b in boxes):
            ly=max(top,min(py+14,bottom-h))
        canvas.coords(label,lx+8,ly+5)
        box=canvas.create_rectangle(lx,ly,lx+w,ly+h,fill='#14243a',outline=color,width=1,tags=tag)
        canvas.tag_raise(label,box);boxes.append((lx,ly,lx+w,ly+h))
