"""Offline thermal recording player; never opens a camera."""
import argparse
import copy
import uuid
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

from PIL import Image,ImageTk

from .playback import Recording,export_history
from . import ui_theme
from .extrema import extrema, draw_extrema
from .review_ui import build
from .analysis import Analysis
from .workspace import measurement_values
from .media_export import export_png,export_mp4,ExportCancelled
from .imaging import thermal_image,rotate_image,sensor_to_view,view_to_sensor,optical_plane_image,aligned_optical
from .regions import area_contains,moved,vertex_at,with_vertex
from .polygon_tool import draw_region
from .tracking import add_tracker, remove_measurement, positioned, markers, overview_markers
from . import __version__


class Review:
    def __init__(self,root,args):
        self.root=root;self.args=args;self.recording=None;self.frame=None;self.index=0;self.optical=None
        self.series={};self.keys=[];self.playing=False;self.cancel=threading.Event()
        self.messages=queue.Queue();self.generation=0;self.position=None;self.photo=None
        self.analysis=None;self.drag=None;self.chosen=None;self.scan_after=None
        self.media_messages=queue.Queue();self.media_cancel=threading.Event();self.media_busy=False;self.media_closing=False
        root.title('Thermal Lab · Recording review');root.geometry('1400x940');root.minsize(1180,850)
        ui_theme.install(root);root.protocol('WM_DELETE_WINDOW',self.close)
        self.status=tk.StringVar(value='Open a finalized recording folder to begin')
        self.info=tk.StringVar(value='OFFLINE · numerical thermal playback · no camera connection')
        self.palette=tk.StringVar(value='Iron');self.rotation=tk.StringVar(value='180')
        self.mode=tk.StringVar(value='Thermal');self.archive_info=tk.StringVar(value='Measurements and geometry follow the original recording.')
        self.speed=tk.StringVar(value='1');self.position_var=tk.DoubleVar();self.selected=tk.StringVar()
        self.basis=tk.StringVar(value='Recorded');self.tool=tk.StringVar(value='Select');self.edit_name=tk.StringVar()
        self.show_extrema=tk.BooleanVar(value=True)
        self.export_labels=tk.BooleanVar(value=True);self.media_status=tk.StringVar(value='Export uses current view · MP4: full recording at 1×, 25 fps')
        build(self)
        root.after(40,self.tick)
        if args.session:root.after(100,lambda:self.open(args.session))

    def browse(self):
        path=filedialog.askdirectory(title='Select a finalized thermal recording folder',initialdir=self.args.recordings)
        if path:self.open(path)

    def open(self,path):
        self.polygon.cancel()
        self.pause();self.cancel.set();self.cancel=threading.Event();self.generation+=1
        self.recording=None;self.frame=None;self.optical=None;self.series={};self.keys=[];self.position=None
        self.analysis=None;self.basis.set('Recorded');self.chosen=None;self.drag=None
        self.tracking_panel.pack_forget();self.edit_tools.pack_forget()
        self.analysis_note.set('Recorded measurements · select Analysis to add or move points and regions')
        self.mode.set('Thermal');self.mode_box.configure(values=['Thermal'])
        self.history_ready=False
        for item in self.table.get_children():self.table.delete(item)
        self.info.set('OFFLINE · no frame selected')
        self.series_box.configure(values=[]);self.selected.set('');self.export.configure(state='disabled');self.play_button.configure(state='disabled')
        self.render();self.plot()
        try:
            recording=Recording(path);self.recording=recording
            self.camera_label=recording.read(0).get('workspace',{}).get('camera_name') or recording.manifest['camera_id']
            self.mode_box.configure(values=['Thermal','Optical','Blend'] if recording.optical else ['Thermal'])
            self.archive_info.set(self.camera_label+'\n'+recording.manifest['camera_id']+'\n\n'+('Lossless optical video paired with each thermal frame. Exposure synchronization is unqualified.' if recording.optical else 'Thermal frames only. This archive has no continuous optical video.')+'\n\nOptical alignment follows the original recording. Blend uses 55% thermal opacity. Choose Recorded or Analysis for measurements.')
            self.timeline.configure(to=max(1,len(recording.entries)-1));self.show(0)
            self.play_button.configure(state='normal');self.root.title('Thermal Lab · Review · '+self.camera_label+' · '+recording.path.name+' · '+__version__)
            self.status.set(f"{recording.path.name} · {self.camera_label} · Loading histories…")
            self.start_histories()
        except Exception as exc:
            self.recording=None;self.status.set('Cannot open recording: '+str(exc))

    def invalidate_histories(self):
        self.cancel.set();self.cancel=threading.Event();self.generation+=1
        if self.scan_after:self.root.after_cancel(self.scan_after);self.scan_after=None
        self.series={};self.keys=[];self.history_ready=False;self.series_box.configure(values=[]);self.selected.set('')
        self.export.configure(state='disabled');self.plot()

    def start_histories(self):
        self.invalidate_histories()
        if not self.recording:return
        recording=self.recording;generation=self.generation;cancel=self.cancel
        settings=copy.deepcopy(self.analysis.settings) if self.basis.get()=='Analysis' and self.analysis else None
        def scan():
            try:
                series=recording.histories(lambda n,total:self.messages.put((generation,'progress',(n,total))),cancel.is_set,settings=settings)
                if series is not None:self.messages.put((generation,'history',series))
            except Exception as exc:self.messages.put((generation,'error',str(exc)))
        threading.Thread(target=scan,daemon=True,name='Measurement histories').start()

    def change_basis(self):
        self.polygon.cancel()
        self.pause();self.drag=None;self.chosen=None;self.edit_name.set('')
        try:
            if self.basis.get()=='Analysis':
                if not self.recording:raise ValueError('Open a recording first')
                if self.analysis is None:self.analysis=Analysis(self.recording)
                self.analysis_note.set('ANALYSIS · definitions apply to all frames · edits autosave separately · trackers follow the extreme pixel')
            else:self.analysis_note.set('ORIGINAL RECORDED measurements · geometry follows each recorded frame')
        except Exception as exc:
            self.basis.set('Recorded');self.status.set('Analysis unavailable: '+str(exc))
        if self.basis.get()=='Analysis':
            self.tracking_panel.pack(fill='x',before=self.measurement_table_frame)
            self.edit_tools.pack(fill='x',pady=8,before=self.measurement_table_frame)
        else:self.tracking_panel.pack_forget();self.edit_tools.pack_forget()
        self.render();self.rows();self.start_histories()

    def layout(self):
        if self.basis.get()=='Analysis' and self.analysis:return self.analysis.settings
        return self.frame.get('workspace',{}) if self.frame else {}

    def values(self):
        if not self.frame:return {}
        return measurement_values(self.frame,self.layout()) if self.basis.get()=='Analysis' else self.frame.get('measurements',{})

    def edited(self,settings):
        try:self.analysis.update(settings)
        except Exception as exc:self.status.set('Analysis not saved: '+str(exc));return False
        self.render();self.rows();self.invalidate_histories()
        self.status.set('Analysis autosaved; recalculating histories…')
        self.scan_after=self.root.after(400,self.start_histories)
        return True

    def polygon_viewports(self):
        if not self.position:return []
        return [(*self.position,0,self.canvas.winfo_width(),20,self.canvas.winfo_height())]

    def add_polygon(self,geometry):
        settings=copy.deepcopy(self.analysis.settings)
        identifier=uuid.uuid4().hex
        settings['areas'].append(dict(id=identifier,name='Polygon '+str(len(settings['areas'])+1),**geometry))
        if not self.edited(settings):raise ValueError(self.status.get())
        self.chosen=identifier;self.edit_name.set(settings['areas'][-1]['name']);self.rows();self.render()

    def sensor(self,event):
        if not self.position:return None
        x,y,scale,w,h=self.position;vx=(event.x-x)/scale;vy=(event.y-y)/scale
        if not (0<=vx<w and 0<=vy<h):return None
        sx,sy=view_to_sensor(vx,vy,int(self.rotation.get()))
        return min(.999999999,max(0,sx/256)),min(.999999999,max(0,sy/192))

    def add_tracking(self,tracking):
        if self.basis.get()!='Analysis' or not self.analysis:
            self.status.set('Choose Analysis in the Layout menu to add trackers to this recording');return
        self.pause()
        try:
            settings,item=add_tracker(self.analysis.settings,tracking,self.chosen,self.tracking_scope.get()=='Selected region')
            self.chosen=item['id'];self.edit_name.set(item['name']);self.tool.set('Select')
            self.edited(settings)
        except Exception as exc:self.status.set(str(exc))

    def press(self,event):
        if self.basis.get()!='Analysis' or not self.analysis or not self.frame:return
        self.pause()
        if self.polygon.click(event):return
        point=self.sensor(event)
        if point is None:return
        self.pause();self.drag=None;x,y=point
        if self.tool.get()=='Point':
            settings=copy.deepcopy(self.analysis.settings);self.chosen=uuid.uuid4().hex
            settings['points'].append(dict(id=self.chosen,name='Point '+str(len(settings['points'])+1),x=x,y=y))
            self.edited(settings)
        elif self.tool.get()=='Rectangle':self.drag=('rectangle',point,None)
        else:
            values=self.values()
            candidates=[positioned(v,values) for kind in ('points','areas') for v in self.analysis.settings[kind]]
            candidates=[v for v in candidates if v is not None]
            item=next((v for v in reversed(candidates) if 'x2' in v and (area_contains(v,x,y) or (v['id']==self.chosen and vertex_at(v,x,y) is not None))),None)
            near=[v for v in candidates if 'x2' not in v and ((v['x']-x)*256)**2+((v['y']-y)*192)**2<64]
            if near:item=min(near,key=lambda v:((v['x']-x)*256)**2+((v['y']-y)*192)**2)
            corner=vertex_at(item,x,y) if item and item['id']==self.chosen else None
            self.chosen=item['id'] if item else None
            if item:
                if not item.get('tracking'):self.drag=('move',point,copy.deepcopy(item),corner)
                self.edit_name.set(item['name'])
            self.rows();self.render()

    def motion(self,event):
        if self.drag and self.drag[0]=='move' and self.drag[2].get('shape')=='polygon':
            point=self.sensor(event)
            if point:
                old=self.drag[2]
                try:candidate=with_vertex(old,self.drag[3],*point) if self.drag[3] is not None else moved(old,point[0]-self.drag[1][0],point[1]-self.drag[1][1])
                except ValueError as exc:self.status.set(str(exc));return
                self.render();draw_region(self.canvas,candidate,self.polygon_viewports()[0],int(self.rotation.get()),True)
            return
        if not self.drag or self.drag[0]!='rectangle' or not self.position:return
        self.canvas.delete('draft');point=self.sensor(event)
        if point:
            x,y,scale,_,_=self.position
            a=sensor_to_view(self.drag[1][0]*256,self.drag[1][1]*192,int(self.rotation.get()))
            b=sensor_to_view(point[0]*256,point[1]*192,int(self.rotation.get()))
            self.canvas.create_rectangle(x+a[0]*scale,y+a[1]*scale,x+b[0]*scale,y+b[1]*scale,outline='#ffbe69',width=2,tags='draft')

    def release(self,event):
        drag=self.drag;self.drag=None;self.canvas.delete('draft')
        if not drag:return
        point=self.sensor(event)
        if point is None:return
        settings=copy.deepcopy(self.analysis.settings);x,y=point;start=drag[1]
        if drag[0]=='rectangle':
            if abs(x-start[0])*256<1 or abs(y-start[1])*192<1:return
            self.chosen=uuid.uuid4().hex
            settings['areas'].append(dict(id=self.chosen,name='Region '+str(len(settings['areas'])+1),x=min(x,start[0]),y=min(y,start[1]),x2=max(x,start[0]),y2=max(y,start[1])))
        else:
            old=drag[2]
            corner=drag[3] if len(drag)>3 else None
            try:candidate=with_vertex(old,corner,x,y) if corner is not None else moved(old,x-start[0],y-start[1])
            except ValueError as exc:self.render();self.status.set(str(exc));return
            for kind in ('points','areas'):
                for item in settings[kind]:
                    if item['id']==old['id']:item.update(candidate)
        self.edited(settings)

    def select_row(self,event=None):
        selected=self.table.selection()
        if not selected:return
        self.chosen=selected[0]
        for kind in ('points','areas'):
            for item in self.layout().get(kind,[]):
                if item['id']==self.chosen:self.edit_name.set(item['name'])
        key=next((k for k in self.keys if k[0]==self.chosen),None)
        if key is not None:self.series_box.current(self.keys.index(key));self.plot()

    def rename(self):
        if self.basis.get()!='Analysis' or not self.analysis or not self.chosen:return
        settings=copy.deepcopy(self.analysis.settings)
        for kind in ('points','areas'):
            for item in settings[kind]:
                if item['id']==self.chosen:item['name']=self.edit_name.get()
        self.edited(settings)

    def remove(self):
        if self.basis.get()!='Analysis' or not self.analysis or not self.chosen:return
        settings=remove_measurement(self.analysis.settings,self.chosen)
        self.chosen=None;self.edited(settings)

    def save_analysis(self):
        if not self.analysis:return
        path=filedialog.asksaveasfilename(title='Save a separate analysis copy',initialdir=self.analysis.path.parent,initialfile=self.recording.path.name+'-analysis.json',defaultextension='.json')
        if path:
            try:self.analysis.save_copy(path);self.status.set('Analysis copy saved: '+path)
            except Exception as exc:messagebox.showerror('Analysis save failed',str(exc))

    def load_analysis(self):
        if not self.recording:return
        path=filedialog.askopenfilename(title='Load analysis for this recording',filetypes=[('Analysis','*.json')])
        if path:
            try:
                if self.analysis is None:self.analysis=Analysis(self.recording)
                settings=self.analysis.read(path);self.analysis.update(settings);self.basis.set('Analysis');self.change_basis()
            except Exception as exc:messagebox.showerror('Analysis load failed',str(exc))

    def pause(self):
        self.playing=False;self.play_button.configure(text='Play')

    def play(self):
        if not self.recording:return
        if self.playing:self.pause();return
        if self.index==len(self.recording.entries)-1:self.show(0)
        self.playing=True;self.anchor_clock=time.monotonic();self.anchor_time=self.recording.times[self.index]
        self.play_button.configure(text='Pause')

    def view_changed(self):
        if self.playing:self.anchor_clock=time.monotonic();self.anchor_time=self.recording.times[self.index]
        self.render()

    def step(self,delta):
        self.pause()
        if self.recording:self.show(max(0,min(len(self.recording.entries)-1,self.index+delta)))

    def seek(self,value):
        if self.recording:
            self.pause();self.show(min(len(self.recording.entries)-1,int(float(value))))

    def show(self,index):
        if not self.recording:return
        try:
            frame=self.recording.read(index)
            self.optical=None
            if self.mode.get()!='Thermal' and self.recording.optical:
                self.optical=optical_plane_image(self.recording.optical.read(index,frame))
            self.frame=frame;self.index=index;self.position_var.set(index)
            self.info.set(f"Frame {index+1:,} / {len(self.recording.entries):,} · {frame['elapsed_s']:.3f} / {self.recording.times[-1]:.3f} s · {frame['source']} · apparent °C · host-arrival timeline")
            self.render();self.rows();self.plot_cursor()
        except Exception as exc:
            self.pause();self.frame=None;self.render();self.status.set('Playback error: '+str(exc))
            for item in self.table.get_children():self.table.delete(item)
            self.info.set('Frame unavailable; no measurements shown')
            self.graph.delete('cursor')

    def render(self):
        self.canvas.delete('all');self.photo=None;self.position=None
        if not self.frame:
            self.canvas.create_text(20,30,text='Open a recording to inspect its thermal frames',fill='#aac0d3',anchor='nw');return
        picture,limits=thermal_image(self.frame['temperatures'],self.palette.get())
        if self.optical is not None and self.mode.get()!='Thermal':
            optical=aligned_optical(self.optical,self.frame.get('workspace',{}).get('alignment',{}))
            picture=optical if self.mode.get()=='Optical' else Image.blend(optical,picture,.55)
        rotation=int(self.rotation.get());picture=rotate_image(picture,rotation)
        width,height=(192,256) if rotation in (90,270) else (256,192)
        cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
        scale=max(.01,min((cw-20)/width,(ch-35)/height));x=(cw-width*scale)/2;y=20+(ch-25-height*scale)/2
        self.position=(x,y,scale,width,height)
        picture=picture.resize((max(1,int(width*scale)),max(1,int(height*scale))),Image.Resampling.NEAREST if self.mode.get()=='Thermal' else Image.Resampling.BILINEAR)
        self.photo=ImageTk.PhotoImage(picture);self.canvas.create_image(x,y,image=self.photo,anchor='nw')
        self.canvas.create_text(10,10,text=f'{limits[0]:.1f} → {limits[1]:.1f} °C · recorded {self.mode.get().lower()}',fill='white',anchor='w')
        for kind in ('points','areas'):
            for item in self.layout().get(kind,[]):
                if item.get('tracking'):continue
                px,py=sensor_to_view(item['x']*256,item['y']*192,rotation);px=x+px*scale;py=y+py*scale
                if item.get('shape')=='polygon':
                    draw_region(self.canvas,item,self.polygon_viewports()[0],rotation,item['id']==self.chosen and self.basis.get()=='Analysis')
                elif 'x2' in item:
                    qx,qy=sensor_to_view(item['x2']*256,item['y2']*192,rotation)
                    self.canvas.create_rectangle(px,py,x+qx*scale,y+qy*scale,outline='#67ffe0',width=2)
                else:self.canvas.create_oval(px-4,py-4,px+4,py+4,outline='#67ffe0',width=2)
                self.canvas.create_text(px+6,py-6,text=item['name'],fill='#67ffe0',anchor='sw')

        self.polygon.draw()
        if self.show_extrema.get() and self.mode.get()!='Optical':
            draw_extrema(self.canvas,overview_markers(extrema(self.frame['temperatures']),self.layout()),(x,y,scale,width,height,0,cw,20,ch),rotation)
        if self.mode.get()!='Optical':
            draw_extrema(self.canvas,markers(self.layout(),self.values()),(x,y,scale,width,height,x,x+width*scale,y,y+height*scale),rotation,tag='trackers')

    def hover(self,event):
        self.polygon.hover(event)
        if not self.frame or not self.position:return
        x,y,scale,width,height=self.position;vx=(event.x-x)/scale;vy=(event.y-y)/scale
        if 0<=vx<width and 0<=vy<height:
            sx,sy=view_to_sensor(vx,vy,int(self.rotation.get()));sx=min(255,max(0,int(sx)));sy=min(191,max(0,int(sy)))
            self.info.set(f"Frame {self.index+1} · {self.frame['elapsed_s']:.3f} s · recorded pixel ({sx}, {sy}): {self.frame['temperatures'][sy*256+sx]:.3f} °C apparent")

    def rows(self):
        for item in self.table.get_children():self.table.delete(item)
        if not self.frame:return
        names={v['id']:v['name'] for kind in ('points','areas') for v in self.layout().get(kind,[])}
        for key,value in self.values().items():
            text=f"{value['value']:.3f}" if 'value' in value else ' · '.join(f'{value[k]:.2f}' for k in ('min','mean','max'))
            if value.get('tracking'):text+=f" · ({value['pixel_x']}, {value['pixel_y']})"
            self.table.insert('','end',iid=key,values=(names.get(key,key),text))
        if self.chosen and self.table.exists(self.chosen):self.table.selection_set(self.chosen)

    def plot(self):
        self.graph.delete('all');w,h=self.graph.winfo_width(),self.graph.winfo_height()
        selection=self.series_box.current()
        if not self.recording or not 0<=selection<len(self.keys):
            text='No points or regions in this measurement view' if getattr(self,'history_ready',False) else 'History appears after all frames have been checked'
            self.graph.create_text(20,30,text=text,fill='#aac0d3',anchor='nw');return
        samples=self.series[self.keys[selection]]['samples'];low=min(v[2] for v in samples);high=max(v[2] for v in samples)
        margin=max(.1,(high-low)*.1);low-=margin;high+=margin
        start,end=self.recording.times[0],self.recording.times[-1];span=max(.001,end-start)
        left,right,top,bottom=65,max(66,w-20),15,max(16,h-30)
        self.graph_bounds=(left,right,top,bottom,start,end)
        for i in range(5):
            y=top+(bottom-top)*i/4;v=high-(high-low)*i/4
            self.graph.create_line(left,y,right,y,fill='#26364a')
            self.graph.create_text(left-8,y,text=f'{v:.2f}',fill='#aac0d3',anchor='e')
        segment=[];previous=None
        for index,elapsed,value,geometry in samples:
            if previous and (index!=previous[0]+1 or geometry!=previous[1]):
                if len(segment)>=4:self.graph.create_line(*segment,fill='#65e3ca',width=2)
                elif segment:self.graph.create_oval(segment[0]-2,segment[1]-2,segment[0]+2,segment[1]+2,fill='#65e3ca')
                segment=[]
            segment.extend((left+(elapsed-start)/span*(right-left),bottom-(value-low)/(high-low)*(bottom-top)))
            previous=(index,geometry)
        if len(segment)>=4:self.graph.create_line(*segment,fill='#65e3ca',width=2)
        elif segment:self.graph.create_oval(segment[0]-2,segment[1]-2,segment[0]+2,segment[1]+2,fill='#65e3ca')
        self.graph.create_text(left,bottom+15,text=f'{start:.2f} s',fill='#aac0d3',anchor='w')
        self.graph.create_text(right,bottom+15,text=f'{end:.2f} s',fill='#aac0d3',anchor='e');self.plot_cursor()

    def plot_cursor(self):
        self.graph.delete('cursor')
        if not self.frame or not self.series or not hasattr(self,'graph_bounds'):return
        left,right,top,bottom,start,end=self.graph_bounds
        x=left+(self.frame['elapsed_s']-start)/max(.001,end-start)*(right-left)
        self.graph.create_line(x,top,x,bottom,fill='#ffbe69',width=2,tags='cursor')

    def graph_seek(self,event):
        if self.recording and self.series and hasattr(self,'graph_bounds'):
            left,right,_,_,start,end=self.graph_bounds
            self.pause();self.show(self.recording.index_at(start+max(0,min(1,(event.x-left)/max(1,right-left)))*(end-start)))

    def export_csv(self):
        if not self.series:return
        path=filedialog.asksaveasfilename(title='Export recorded temperature histories to a new CSV',defaultextension='.csv',filetypes=[('CSV history','*.csv')],initialfile=self.recording.path.name+'-history.csv')
        if path:
            try:
                if self.basis.get()=='Analysis':self.analysis.outside_archive(path)
                export_history(path,self.recording,self.series,self.analysis.fingerprint if self.basis.get()=='Analysis' else None)
                self.status.set('History exported: '+path)
            except Exception as exc:messagebox.showerror('Export failed',str(exc))

    def media_export(self,kind):
        if self.media_busy:
            if kind=='mp4':self.media_cancel.set();self.media_status.set('Cancelling export…')
            return
        if not self.recording or not self.frame:return
        self.pause()
        path=filedialog.asksaveasfilename(title='Export outside the source recording folder',initialdir=self.recording.path.parent,
                  initialfile=self.recording.path.name+('-frame-'+str(self.index+1) if kind=='png' else '')+'.'+kind,
                  defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if not path:return
        recording=self.recording;index=self.index
        options=dict(mode=self.mode.get(),palette=self.palette.get(),rotation=int(self.rotation.get()),labels=self.export_labels.get(),
                     settings=copy.deepcopy(self.analysis.settings) if self.basis.get()=='Analysis' and self.analysis else None)
        self.media_busy=True;self.media_cancel=threading.Event();cancel=self.media_cancel
        self.png_button.configure(state='disabled');self.mp4_button.configure(text='Cancel export',state='normal' if kind=='mp4' else 'disabled')
        self.media_status.set('Exporting '+kind.upper()+'…')
        def work():
            try:
                if kind=='png':export_png(recording,index,path,options)
                else:export_mp4(recording,path,options,cancel.is_set,lambda n,total:self.media_messages.put(('progress',(n,total))))
                self.media_messages.put(('done','Saved '+str(path)))
            except ExportCancelled:self.media_messages.put(('done','Export cancelled; no completed MP4 saved'))
            except Exception as exc:self.media_messages.put(('done','Export failed: '+str(exc)))
        threading.Thread(target=work,name='Media export').start()

    def tick(self):
        try:
            while True:
                kind,data=self.media_messages.get_nowait()
                if kind=='progress':self.media_status.set(f'Exporting MP4: {data[0]:,} / {data[1]:,} frames')
                else:
                    self.media_busy=False;self.media_status.set(data);self.png_button.configure(state='normal');self.mp4_button.configure(text='Export MP4…',state='normal')
                    if self.media_closing:self.root.destroy();return
        except queue.Empty:pass
        try:
            while True:
                generation,kind,data=self.messages.get_nowait()
                if generation!=self.generation:continue
                if kind=='progress':self.status.set(f'{self.basis.get()} histories: {data[0]:,} / {data[1]:,} frames')
                elif kind=='history':
                    self.history_ready=True
                    self.series=data;self.keys=list(data)
                    labels=[f"{data[key]['name']} · {key[1]} · {key[0][:12]}" for key in self.keys]
                    self.series_box.configure(values=labels)
                    if labels:self.series_box.current(0);self.export.configure(state='normal')
                    self.plot();self.status.set(f"{self.recording.path.name} · {self.camera_label} · {self.basis.get()} history checked · apparent temperatures")
                elif kind=='error':self.status.set('History unavailable: '+data)
        except queue.Empty:pass
        if self.playing and self.recording:
            elapsed=self.anchor_time+(time.monotonic()-self.anchor_clock)*float(self.speed.get())
            index=self.recording.index_at(elapsed)
            if index!=self.index:self.show(index)
            if elapsed>=self.recording.times[-1]:self.pause()
        self.root.after(40,self.tick)

    def close(self):
        self.cancel.set()
        if self.media_busy:
            self.media_closing=True;self.media_cancel.set();self.media_status.set('Closing after export cleanup…');return
        self.root.destroy()


def main():
    from lab_update import hold_app_lease
    hold_app_lease('ThermalLab')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path)
    parser.add_argument('--recordings',type=Path,default=Path.home()/'Thermal-Lab-Recordings')
    args=parser.parse_args();root=tk.Tk();Review(root,args);root.mainloop()


if __name__=='__main__':main()
