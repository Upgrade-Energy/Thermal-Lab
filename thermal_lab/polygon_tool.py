"""Shared live/review polygon controls and clipped outlines."""
import tkinter as tk
from tkinter import ttk
from .imaging import sensor_to_view
from .regions import polygon_geometry, vertices


def clipped_line(a,b,bounds):
    left,right,top,bottom=bounds;dx=b[0]-a[0];dy=b[1]-a[1];lo=0.;hi=1.
    for p,q in ((-dx,a[0]-left),(dx,right-a[0]),(-dy,a[1]-top),(dy,bottom-a[1])):
        if p==0:
            if q<0:return None
        elif p<0:lo=max(lo,q/p)
        else:hi=min(hi,q/p)
        if lo>hi:return None
    return (a[0]+lo*dx,a[1]+lo*dy,a[0]+hi*dx,a[1]+hi*dy)


def projected(points,viewport,rotation):
    x,y,scale,*_=viewport
    return [(x+px*scale,y+py*scale) for px,py in (sensor_to_view(a*256,b*192,rotation) for a,b in points)]


def outline(canvas,points,viewport,rotation,*,color='#67ffe0',closed=True,handles=False,draft=False):
    xy=projected(points,viewport,rotation);bounds=viewport[5:9]
    tag='polygon-draft' if draft else 'polygon';segments=list(zip(xy,xy[1:]))
    if closed and len(xy)>2:segments.append((xy[-1],xy[0]))
    for a,b in segments:
        segment=clipped_line(a,b,bounds)
        if segment:canvas.create_line(*segment,fill=color,width=2,dash=(5,3) if draft else (),tags=tag)
    if handles:
        for i,(x,y) in enumerate(xy):
            if bounds[0]+5<=x<bounds[1]-5 and bounds[2]+5<=y<bounds[3]-5:
                canvas.create_oval(x-4,y-4,x+4,y+4,outline=color,fill='#13263c',width=2,tags=tag)
                if draft:canvas.create_text(x+7,y+8,text=str(i+1),fill=color,anchor='nw',tags=tag)


class PolygonTool:
    def __init__(self,canvas,parent,before,tool,status,locate,viewports,rotation,can_draw,commit,compact=False):
        self.canvas=canvas;self.tool=tool;self.status=status;self.locate=locate
        self.viewports=viewports;self.rotation=rotation;self.can_draw=can_draw;self.commit=commit
        self.points=[];self.pointer=None;self.before=before
        self.panel=ttk.Frame(parent,padding=(0,4));self.note=tk.StringVar()
        ttk.Label(self.panel,textvariable=self.note,style='Muted.TLabel',wraplength=300 if compact else 580).pack(anchor='w',pady=(0,5))
        row=ttk.Frame(self.panel);row.pack(anchor='w')
        self.finish_button=ttk.Button(row,text='Finish polygon',command=self.finish);self.finish_button.pack(side='left',padx=(0,5))
        self.undo_button=ttk.Button(row,text='Undo corner',command=self.undo);self.undo_button.pack(side='left',padx=(0,5))
        cancel_button=ttk.Button(self.panel if compact else row,text='Cancel',command=self.cancel)
        if compact:cancel_button.pack(anchor='w',pady=(4,0))
        else:cancel_button.pack(side='left')
        for key,action in (('<Return>',self.finish),('<BackSpace>',self.undo),('<Escape>',self.cancel),('<Button-3>',self.undo)):
            canvas.bind(key,lambda e,fn=action:self.key(fn),add='+')
        tool.trace_add('write',lambda *_:self.changed());self.changed()

    def changed(self):
        self.points=[];self.pointer=None;self.canvas.delete('polygon-draft')
        if self.tool.get()=='Polygon':
            self.panel.pack(fill='x',before=self.before) if self.before else self.panel.pack(fill='x')
        else:self.panel.pack_forget()
        self.refresh()

    def refresh(self):
        self.note.set(f'{len(self.points)} corners · Click outline corners. Click the first to close, or Enter. Backspace undoes; Esc cancels.')
        self.finish_button.configure(state='normal' if len(self.points)>=3 else 'disabled')
        self.undo_button.configure(state='normal' if self.points else 'disabled')

    def key(self,action):
        if self.tool.get()=='Polygon':action();return 'break'

    def click(self,event):
        if self.tool.get()!='Polygon':return False
        self.canvas.focus_set()
        if not self.can_draw():self.status.set('A fresh frame and editable measurement layout are required');return True
        point=self.locate(event)
        if point is None:return True
        if len(self.points)>=3:
            for viewport in self.viewports():
                x,y=projected(self.points[:1],viewport,int(self.rotation.get()))[0]
                if (event.x-x)**2+(event.y-y)**2<=100:self.finish();return True
        if len(self.points)>=64:self.status.set('Maximum 64 corners; finish the polygon or undo a corner');return True
        if self.points and ((point[0]-self.points[-1][0])*256)**2+((point[1]-self.points[-1][1])*192)**2<.25:return True
        self.points.append(point);self.pointer=None;self.refresh();self.draw();return True

    def hover(self,event):
        if self.tool.get()=='Polygon' and self.points:self.pointer=self.locate(event);self.draw()

    def draw(self):
        self.canvas.delete('polygon-draft')
        if not self.points:return
        for viewport in self.viewports():
            outline(self.canvas,self.points,viewport,int(self.rotation.get()),color='#ffbe69',closed=False,handles=True,draft=True)
            if self.pointer:
                outline(self.canvas,[self.points[-1],self.pointer],viewport,int(self.rotation.get()),color='#ffbe69',closed=False,draft=True)

    def finish(self):
        if self.tool.get()!='Polygon' or len(self.points)<3:return
        if not self.can_draw():self.status.set('Wait for a fresh frame before finishing the polygon');return
        try:
            geometry=polygon_geometry([dict(x=x,y=y) for x,y in self.points])
            self.commit(geometry)
        except Exception as exc:self.status.set(str(exc));return
        self.tool.set('Select');self.status.set('Polygon saved · drag its outline to move it, or a corner to reshape it')

    def undo(self):
        if self.points:self.points.pop()
        self.pointer=None;self.refresh();self.draw();self.canvas.focus_set()

    def cancel(self):
        if self.tool.get()=='Polygon':self.tool.set('Select')


def draw_region(canvas,item,viewport,rotation,selected=False):
    outline(canvas,vertices(item),viewport,rotation,color='#ffffff' if selected else '#67ffe0',handles=selected)
