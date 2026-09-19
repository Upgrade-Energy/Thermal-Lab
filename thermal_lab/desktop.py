"""Native standalone live inspection workspace."""
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import uuid
import hashlib
import subprocess
import sys

from PIL import Image, ImageTk

from .acquisition import worker
from .imaging import optical_image, aligned_optical, thermal_image, rotate_image, sensor_to_view, canvas_to_sensor
from .workspace import validate_settings, read_settings, save_settings, measurement_values
from .camera_diagnostics import pnp_devices
from .connection_guidance import connection_guidance
from . import ui_theme
from .desktop_ui import build
from .extrema import extrema, draw_extrema
from .camera_names import read_names, save_name, display_name
from .recording_clock import RecordingClock
from .regions import area_contains, moved, vertex_at, with_vertex
from .polygon_tool import draw_region
from .tracking import add_tracker, remove_measurement, positioned, markers, overview_markers


class Desktop:
    def __init__(self, root, args):
        self.root=root;self.args=args;self.process=None;self.closing=False;self.stop_deadline=None
        self.frame=None;self.optical=None;self.received_at=0;self.drag=None;self.viewports=[]
        self.stream_active=False;self.record_pending=False
        self.settings=validate_settings({});self.recording=False;self.record_path=None
        self.clock=RecordingClock()
        self.selected=None;self.zoom=1;self.pan=[0,0];self.photos=[]
        self.ctx=mp.get_context('spawn');self.commands=None
        self.workspace_path=args.workspace
        self.camera_choice=tk.StringVar(value=args.camera_id or '')
        root.title('Thermal Lab · Live inspection');root.geometry('1440x940');root.minsize(1180,850)
        ui_theme.install(root);root.protocol('WM_DELETE_WINDOW',self.close)
        self.names_path=Path.home()/'.thermal-lab/camera-names.json'
        try:self.camera_names=read_names(self.names_path)
        except Exception:self.camera_names={}
        self.camera_ids=[]
        self.mode=tk.StringVar(value='Blend');self.palette=tk.StringVar(value='Iron');self.rotation=tk.StringVar(value='180')
        self.record_optical=tk.BooleanVar(value=True)
        self.tool=tk.StringVar(value='Select');self.opacity=tk.DoubleVar(value=.55);self.automatic=tk.BooleanVar(value=True)
        self.low=tk.StringVar(value='20');self.high=tk.StringVar(value='40');self.locked=tk.BooleanVar(value=False)
        self.path=tk.StringVar(value=str(args.topview_directory or ''))
        self.status=tk.StringVar(value='DISCONNECTED · Select a TopView installation and connect')
        self.info=tk.StringVar(value='Apparent temperature · absolute accuracy unqualified')
        self.cursor=tk.StringVar(value='Choose Point or Rectangle, then mark the image')
        self.name=tk.StringVar();self.alignment={k:tk.StringVar(value=str(v)) for k,v in self.settings['alignment'].items()}
        self.alignment_sliders={k:tk.DoubleVar(value=v) for k,v in self.settings['alignment'].items()}
        build(self)
        if args.workspace.exists():
            try:self.settings=read_settings(args.workspace);self.sync_alignment();self.refresh_rows()
            except Exception as exc:self.status.set(f'Layout not loaded: {exc}')
        root.after(80,self.poll)
        self.refresh_cameras()

    def reload_camera_names(self):
        try:self.camera_names=read_names(self.names_path)
        except Exception as exc:self.status.set('Camera names could not be refreshed: '+str(exc))

    def update_camera_choices(self):
        # Other camera windows share the registry, not this process's cached map.
        self.reload_camera_names()
        labels=[display_name(c,self.camera_names)+'  ·  '+str(i+1) for i,c in enumerate(self.camera_ids)]
        self.camera_box.configure(values=labels)
        current=self.camera_choice.get()
        if current in self.camera_ids:self.camera_display.set(labels[self.camera_ids.index(current)])
        else:self.camera_display.set(display_name(current,self.camera_names))
        self.camera_name.set(self.camera_names.get(current.casefold(),''))
        self.camera_identity.set(current or 'Connect a TC001 Max, then choose Refresh.')
        self.root.title('Thermal Lab · '+display_name(current,self.camera_names))

    def choose_camera(self,_=None):
        index=self.camera_box.current()
        if 0<=index<len(self.camera_ids):
            self.camera_choice.set(self.camera_ids[index]);self.select_camera_layout()

    def rename_camera(self):
        try:
            self.camera_names=save_name(self.names_path,self.camera_choice.get(),self.camera_name.get())
            self.settings['camera_name']=self.camera_name.get().strip()
            self.changed();self.update_camera_choices()
            self.status.set('Camera name saved · '+display_name(self.camera_choice.get(),self.camera_names))
        except Exception as exc:self.status.set(str(exc))

    def refresh_cameras(self):
        if self.process and self.process.is_alive():return
        try:
            discovered=pnp_devices()
            self.connection_info.set(connection_guidance(discovered))
            devices=[d['instance_id'] for d in discovered if d.get('problem_code')==0]
            self.camera_ids=devices
            if self.camera_choice.get() not in devices:self.camera_choice.set(devices[0] if devices else '')
            self.update_camera_choices()
            if self.camera_choice.get():self.select_camera_layout()
            if not devices:self.status.set('No healthy TC001 Max detected; connect it and press Refresh')
        except Exception as exc:self.status.set('Camera discovery failed: '+str(exc))

    def select_camera_layout(self):
        if self.process and self.process.is_alive():return
        try:
            self.prepare_camera_layout(self.camera_choice.get())
            self.update_camera_choices()
            self.frame=None;self.optical=None;self.received_at=0;self.render()
        except Exception as exc:self.status.set('Layout error: '+str(exc))

    def another_camera(self):
        others=[d for d in self.camera_ids if d!=self.camera_choice.get()]
        command=[sys.executable,'-m','thermal_lab.desktop','--topview-directory',self.path.get(),
                 '--recordings',str(self.args.recordings),'--workspace',str(self.args.workspace)]
        if others:command+=['--camera-id',others[0]]
        subprocess.Popen(command,cwd=str(Path(__file__).resolve().parents[1]),
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def review_recordings(self):
        command=[sys.executable,'-m','thermal_lab.review','--recordings',str(self.args.recordings)]
        if self.record_path and not self.recording:command+=['--session',str(self.record_path)]
        subprocess.Popen(command,cwd=str(Path(__file__).resolve().parents[1]),
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def open_measurement_csv(self):
        if not self.csv_path:return
        try:subprocess.Popen(['explorer.exe','/select,',str(self.csv_path)])
        except OSError as exc:messagebox.showerror('Show CSV failed',str(exc))

    def prepare_camera_layout(self, camera_id):
        if hasattr(self,'polygon'):self.polygon.cancel()
        if hasattr(self,'names_path'):self.reload_camera_names()
        key=hashlib.sha256(camera_id.casefold().encode()).hexdigest()[:16]
        self.workspace_path=self.args.workspace.with_name(self.args.workspace.stem+'-'+key+'.json')
        if self.workspace_path.exists():
            candidate=read_settings(self.workspace_path)
            if candidate['camera_id'].casefold()!=camera_id.casefold():raise ValueError('Saved camera layout identity mismatch')
        elif self.settings.get('camera_id','').casefold()==camera_id.casefold():candidate=self.settings
        else:
            legacy=read_settings(self.args.workspace) if self.args.workspace.exists() else validate_settings({})
            candidate=legacy if legacy.get('camera_id','').casefold()==camera_id.casefold() else validate_settings({})
        self.settings=dict(candidate,camera_id=camera_id);self.selected=None;self.name.set('')
        if hasattr(self,'camera_names'):self.settings['camera_name']=self.camera_names.get(camera_id.casefold(),'')
        self.sync_alignment();self.refresh_rows()

    def browse(self):
        path=filedialog.askdirectory(title='Select TopView installation')
        if path:self.path.set(path)

    def send(self, action, **data):
        if self.process and self.process.is_alive():
            try:self.commands.put_nowait(dict(action=action,**data))
            except queue.Full:self.status.set('Camera command queue is full; retry after it responds')

    def connect(self):
        if self.process and self.process.is_alive():
            self.send('stop');self.stop_deadline=time.monotonic()+7
            self.invalidate_stream()
            self.status.set('Stopping camera and finalizing any recording…');return
        if self.process:self.process.join(timeout=0)
        camera_id=self.camera_choice.get()
        if not camera_id:self.status.set('Select a connected camera first');return
        try:self.prepare_camera_layout(camera_id)
        except Exception as exc:self.status.set('Layout error: '+str(exc));return
        self.commands=self.ctx.Queue(32);self.previews=self.ctx.Queue(1);self.events=self.ctx.Queue()
        self.frame=None;self.optical=None;self.received_at=0;self.stop_deadline=None
        self.stream_active=False
        self.exit_reported=False
        self.process=self.ctx.Process(target=worker,args=(self.path.get(),self.commands,self.previews,self.events,camera_id),daemon=True)
        self.process.start();self.send('settings',settings=self.settings)
        self.start_deadline=time.monotonic()+30
        self.connect_button.configure(text='Disconnect');self.status.set('CONNECTING · Opening TC001 Max…');self.render()
        self.camera_box.configure(state='disabled');self.refresh_button.configure(state='disabled')
        self.root.title('Thermal Lab · '+display_name(camera_id,self.camera_names))

    def toggle_record(self):
        if self.record_pending:return
        if self.recording:
            self.record_pending=True;self.send('finish');self.record_button.configure(state='disabled');return
        if not self.stream_active or not self.frame or time.monotonic()-self.received_at>1:
            self.status.set('Fresh camera frames are required to start recording');return
        name=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.record_pending=True
        self.send('record',path=str((self.args.recordings/name).resolve()),optical=self.record_optical.get())
        self.optical_check.configure(state='disabled')
        self.record_button.configure(state='disabled')

    def invalidate_stream(self):
        if hasattr(self,'polygon'):self.polygon.cancel()
        if hasattr(self,'clock'):self.clock.interrupt()
        self.record_pending=False
        self.stream_active=False;self.frame=None;self.optical=None;self.received_at=0;self.drag=None
        self.record_button.configure(text='Record session',state='disabled')
        self.cursor.set('Camera disconnected · measurements unavailable')
        self.info.set('No live frame · reconnect the selected camera to start a new session')
        self.render();self.refresh_values()

    def poll(self):
        if self.process:
            try:
                while True:
                    event=self.events.get_nowait();kind=event['kind']
                    if kind=='connected':
                        self.start_deadline=None
                        self.stream_active=True;self.received_at=time.monotonic()
                        previous=self.settings.get('camera_id')
                        if previous and previous!=event['camera_id']:
                            self.status.set('Layout belongs to another camera; verify alignment before use')
                        else:self.status.set('CONNECTED · TC001 Max · waiting for frames')
                        self.settings['camera_id']=event['camera_id'];self.changed()
                    elif kind=='recording_started':
                        self.record_pending=False
                        self.recording=True;self.record_path=Path(event['path'])
                        self.clock.start(event.get('origin_monotonic',time.monotonic()))
                        self.status.set('RECORDING · '+str(self.record_path))
                        self.csv_path=None;self.csv_button.configure(state='disabled')
                        self.record_button.configure(text='Stop recording',state='normal')
                    elif kind=='recording_finished':
                        self.record_pending=False
                        self.recording=False;self.record_button.configure(text='Record session',state='normal')
                        self.clock.finish(event.get('duration_s',0),event['status']=='COMPLETE')
                        self.optical_check.configure(state='normal')
                        self.status.set(f"Recording {event['status']}: {event['frames']} frames · {event['path']}")
                        self.csv_path=Path(event['measurement_csv']) if event.get('measurement_csv') else None
                        self.csv_button.configure(state='normal' if self.csv_path else 'disabled')
                        if self.csv_path:self.status.set(self.status.get()+' · Measurement CSV saved')
                    elif kind=='error':
                        self.status.set('CAMERA ERROR · '+event['message']+' · Reconnect to start a new session')
                        self.invalidate_stream()
                    elif kind=='stopped':
                        self.invalidate_stream()
                        self.record_button.configure(state='disabled');self.connect_button.configure(text='Connect camera')
                        if self.status.get().startswith('Stopping'):self.status.set('DISCONNECTED · camera released')
            except queue.Empty:pass
            try:
                sample=self.previews.get_nowait()
                if not self.stream_active:raise queue.Empty
                was_stale=self.frame is None or time.monotonic()-self.received_at>1
                self.frame=sample['frame'];self.received_at=sample['received_at']
                if was_stale:self.cursor.set('Choose Point or Rectangle, then mark the image')
                if not self.record_pending:self.record_button.configure(state='normal')
                if 'waiting for frames' in self.status.get():self.status.set('LIVE · TC001 Max · thermal and optical preview')
                self.optical=optical_image(sample['raw'])
                self.info.set(f"Frame {self.frame['arrival_sequence']} · camera uptime {self.frame['elapsed_s']:.1f} s · 256 × 192 thermal / 1024 × 768 optical · apparent °C · "
                              +(f"RECORDING {sample['recording_frames'] or 0} frames" if self.recording else 'preview; exposure timing unqualified'))
                self.render();self.refresh_values()
            except queue.Empty:pass
            except Exception as exc:self.status.set('DISPLAY ERROR · '+str(exc))
            if self.stop_deadline and time.monotonic()>self.stop_deadline and self.process.is_alive():
                self.process.terminate();self.exit_reported=True;self.stop_deadline=None
                self.invalidate_stream()
                self.status.set('Camera stop timed out; worker terminated. Recording is incomplete.')
            if self.start_deadline and time.monotonic()>self.start_deadline and self.process.is_alive():
                self.process.terminate();self.start_deadline=None;self.exit_reported=True
                self.invalidate_stream()
                self.status.set('Camera startup timed out; worker terminated. Reconnect to retry.')
            if self.stream_active and time.monotonic()-self.received_at>8 and self.process.is_alive():
                self.process.terminate();self.exit_reported=True
                self.invalidate_stream()
                self.status.set('Camera stream timed out; worker terminated. Recording is incomplete. Reconnect to retry.')
            if not self.process.is_alive():
                if self.stream_active:self.invalidate_stream()
                self.camera_box.configure(state='readonly');self.refresh_button.configure(state='normal')
                self.process.join(timeout=0);self.connect_button.configure(text='Connect camera');self.record_button.configure(state='disabled')
                if not self.exit_reported and self.process.exitcode:
                    self.status.set(f'Camera worker exited unexpectedly ({self.process.exitcode}); reconnect to retry')
                self.exit_reported=True
                if self.recording:
                    self.recording=False;self.status.set('Camera worker exited during recording; session is incomplete')
                self.optical_check.configure(state='normal')
                if self.closing:self.root.destroy();return
            if self.frame and time.monotonic()-self.received_at>1:
                self.record_button.configure(state='disabled')
                self.cursor.set('No fresh frame · measurements unavailable');self.render();self.refresh_values()
        if self.closing and not self.process:self.root.destroy();return
        if hasattr(self,'record_clock'):self.record_clock.set(self.clock.text())
        self.root.after(80,self.poll)

    def current_limits(self):
        if self.automatic.get():return None
        low=float(self.low.get());high=float(self.high.get())
        if not (-100<=low<high<=1000):raise ValueError('Color scale needs -100 ≤ low < high ≤ 1000 °C')
        return low,high

    def render(self):
        self.canvas.delete('all');self.photos=[];self.viewports=[]
        cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
        if hasattr(self,'hot_value'):
            marks=extrema(self.frame['temperatures']) if self.frame and time.monotonic()-self.received_at<=1 else []
            self.hot_value.set(f"{marks[0]['value']:.1f} °C" if marks else '—')
            self.cold_value.set(f"{marks[-1]['value']:.1f} °C" if marks else '—')
        if not self.frame or not self.optical:
            self.canvas.create_text(cw/2,ch/2,text='Connect your TC001 Max to begin',fill='#8ba4be',font=('Segoe UI',17));return
        try:
            thermal,limits=thermal_image(self.frame['temperatures'],self.palette.get(),self.current_limits())
            optical=aligned_optical(self.optical,self.settings['alignment'])
        except Exception as exc:self.status.set(str(exc));return
        mode=self.mode.get();rotation=int(self.rotation.get())
        current_values=measurement_values(self.frame,self.settings) if time.monotonic()-self.received_at<=1 else {}
        layers=[('THERMAL',thermal),('OPTICAL · aligned',optical)] if mode=='Side by side' else [(mode.upper(),
                thermal if mode=='Thermal' else optical if mode=='Optical' else Image.blend(optical,thermal,self.opacity.get()))]
        width,height=(192,256) if rotation in (90,270) else (256,192)
        panel=cw/len(layers)
        for index,(label,picture) in enumerate(layers):
            scale=max(.01,min((panel-20)/width,(ch-58)/height))*self.zoom
            x=index*panel+(panel-width*scale)/2+self.pan[0];y=30+(ch-50-height*scale)/2+self.pan[1]
            clip_left,clip_right,clip_top,clip_bottom=index*panel,(index+1)*panel,28,ch-22
            self.viewports.append((x,y,scale,width,height,clip_left,clip_right,clip_top,clip_bottom))
            picture=rotate_image(picture,rotation).resize((max(1,int(width*scale)),max(1,int(height*scale))),Image.Resampling.BILINEAR)
            # Clip each panel before drawing; zoomed optical pixels must never
            # cover a neighboring thermal panel with a different hit-test map.
            crop_left=max(0,int(clip_left-x));crop_top=max(0,int(clip_top-y))
            crop_right=min(picture.width,int(clip_right-x));crop_bottom=min(picture.height,int(clip_bottom-y))
            if crop_right<=crop_left or crop_bottom<=crop_top:continue
            picture=picture.crop((crop_left,crop_top,crop_right,crop_bottom))
            photo=ImageTk.PhotoImage(picture);self.photos.append(photo)
            self.canvas.create_image(x+crop_left,y+crop_top,image=photo,anchor='nw')
            self.canvas.create_text(index*panel+12,12,text=label,fill='#e3ebf5',anchor='w',font=('Segoe UI',10,'bold'))
            for item in self.settings['points']+self.settings['areas']:
                if item.get('tracking'):continue
                px,py=sensor_to_view(item['x']*256,item['y']*192,rotation);px=x+px*scale;py=y+py*scale
                color='#ffffff' if item['id']==self.selected else '#67ffe0'
                if item.get('shape')=='polygon':
                    draw_region(self.canvas,item,self.viewports[-1],rotation,item['id']==self.selected)
                elif 'x2' in item:
                    qx,qy=sensor_to_view(item['x2']*256,item['y2']*192,rotation)
                    left_edge,right_edge=sorted((px,x+qx*scale));top_edge,bottom_edge=sorted((py,y+qy*scale))
                    left_edge=max(clip_left,left_edge);right_edge=min(clip_right,right_edge)
                    top_edge=max(clip_top,top_edge);bottom_edge=min(clip_bottom,bottom_edge)
                    if left_edge>=right_edge or top_edge>=bottom_edge:continue
                    self.canvas.create_rectangle(left_edge,top_edge,right_edge,bottom_edge,outline=color,width=2)
                else:
                    if not (clip_left+9<=px<clip_right-9 and clip_top+9<=py<clip_bottom-9):continue
                    self.canvas.create_oval(px-5,py-5,px+5,py+5,outline=color,width=2)
                    self.canvas.create_line(px-9,py,px+9,py,fill=color)
                    self.canvas.create_line(px,py-9,px,py+9,fill=color)
                label_text=item['name'];value=current_values.get(item['id'],{})
                if 'value' in value:label_text+=f"  {value['value']:.1f} °C"
                if clip_left<=px<clip_right-10 and clip_top+20<=py<clip_bottom:
                    self.canvas.create_text(px+8,py-10,text=label_text,fill=color,anchor='sw',font=('Segoe UI',10,'bold'),width=max(1,clip_right-px-10))
            if getattr(self,'show_extrema',None) is not None and self.show_extrema.get() and time.monotonic()-self.received_at<=1 and label!='OPTICAL · aligned' and mode!='Optical':
                draw_extrema(self.canvas,overview_markers(extrema(self.frame['temperatures']),self.settings),self.viewports[-1],rotation)
            if label!='OPTICAL · aligned' and mode!='Optical':
                draw_extrema(self.canvas,markers(self.settings,current_values),self.viewports[-1],rotation,tag='trackers')
        if hasattr(self,'polygon'):self.polygon.draw()
        self.canvas.create_text(12,ch-12,text=f'{limits[0]:.1f} → {limits[1]:.1f} °C  ·  {self.palette.get()}',fill='#ffffff',anchor='w')
        if time.monotonic()-self.received_at>1:
            self.canvas.create_rectangle(0,28,cw,60,fill='#792f34',outline='')
            self.canvas.create_text(cw/2,44,text='STALE / DISCONNECTED — frozen image, measurements unavailable',fill='white')

    def locate(self,event):
        for viewport in self.viewports:
            point=canvas_to_sensor(event.x,event.y,viewport,int(self.rotation.get()))
            if point is not None:return point
        return None

    def hover(self,event):
        self.polygon.hover(event)
        point=self.locate(event)
        if point and self.frame and time.monotonic()-self.received_at<=1:
            x,y=map(int,point);value=self.frame['temperatures'][y*256+x]
            self.cursor.set(f'Thermal pixel ({x}, {y})  ·  {value:.2f} °C apparent')
        else:self.cursor.set('Outside thermal coverage or no fresh frame')

    def press(self,event):
        if self.polygon.click(event):return
        point=self.locate(event)
        if not point or not self.frame or time.monotonic()-self.received_at>1:return
        self.drag=dict(point=point,start=(event.x,event.y),alignment=dict(self.settings['alignment']),pan=list(self.pan))
        if self.tool.get()=='Select':
            candidates=self.settings['points']+self.settings['areas'];found=None
            values=measurement_values(self.frame,self.settings)
            for item in reversed(candidates):
                point_item=positioned(item,values)
                if point_item is None:continue
                x,y=point_item['x']*256,point_item['y']*192
                corner=vertex_at(item,point[0]/256,point[1]/192) if item['id']==self.selected else None
                if ('x2' in item and (corner is not None or area_contains(item,point[0]/256,point[1]/192))) or ('x2' not in item and abs(x-point[0])<5 and abs(y-point[1])<5):
                    self.drag['corner']=corner
                    found=item;break
            if found:
                self.selected=found['id'];self.drag['item']=dict(found);self.table.selection_set(self.selected)
                self.name.set(found['name']);self.render()

    def motion(self,event):
        if not self.drag:return
        point=self.locate(event)
        if self.tool.get()=='Pan':
            self.pan=[self.drag['pan'][0]+event.x-self.drag['start'][0],self.drag['pan'][1]+event.y-self.drag['start'][1]];self.render();return
        if point is None:return
        dx=point[0]-self.drag['point'][0];dy=point[1]-self.drag['point'][1]
        if self.tool.get()=='Align optical' and not self.locked.get():
            self.settings['alignment']['dx']=max(-512,min(512,self.drag['alignment']['dx']+dx))
            self.settings['alignment']['dy']=max(-384,min(384,self.drag['alignment']['dy']+dy))
            self.sync_alignment();self.render()
        elif self.tool.get()=='Select' and 'item' in self.drag:
            if self.drag['item'].get('tracking'):
                self.status.set('This tracker follows the extreme pixel; move its search region to change where it looks');return
            original=self.drag['item'];item=next(v for v in self.settings['points']+self.settings['areas'] if v['id']==original['id'])
            try:
                candidate=with_vertex(original,self.drag['corner'],point[0]/256,point[1]/192) if self.drag.get('corner') is not None else moved(original,dx/256,dy/192)
            except ValueError as exc:self.status.set(str(exc));return
            item.update(candidate)
            self.render();self.refresh_values()
        elif self.tool.get()=='Rectangle':
            self.render();self.canvas.create_rectangle(*self.drag['start'],event.x,event.y,outline='#ffffff',dash=(5,3),width=2)

    def release(self,event):
        if not self.drag:return
        point=self.locate(event);tool=self.tool.get()
        if point and tool in ('Point','Rectangle'):
            kind='points' if tool=='Point' else 'areas';number=len(self.settings[kind])+1
            if number>64:
                self.status.set('Maximum 64 points or regions');self.drag=None;return
            item=dict(id=uuid.uuid4().hex,name=f'{"Point" if kind=="points" else "Region"} {number}',x=point[0]/256,y=point[1]/192)
            if tool=='Rectangle':
                start=self.drag['point'];item.update(x=min(start[0],point[0])/256,y=min(start[1],point[1])/192,x2=max(start[0],point[0])/256,y2=max(start[1],point[1])/192)
            self.settings[kind].append(item);self.selected=item['id'];self.name.set(item['name']);self.refresh_rows()
        self.drag=None;self.changed();self.render()

    def wheel(self,event):
        self.zoom=max(.5,min(4,self.zoom*(1.1 if event.delta>0 else 1/1.1)));self.render()

    def fit(self):self.zoom=1;self.pan=[0,0];self.render()

    def add_polygon(self,geometry):
        number=len(self.settings['areas'])+1
        if number>64:raise ValueError('Maximum 64 regions')
        item=dict(id=uuid.uuid4().hex,name=f'Polygon {number}',**geometry)
        candidate=validate_settings(dict(self.settings,areas=self.settings['areas']+[item]))
        self.settings=candidate;self.selected=item['id'];self.name.set(item['name'])
        self.changed();self.refresh_rows();self.render()

    def add_tracking(self,tracking):
        try:
            self.settings,item=add_tracker(self.settings,tracking,self.selected,self.tracking_scope.get()=='Selected region')
            self.selected=item['id'];self.name.set(item['name']);self.tool.set('Select')
            self.changed();self.refresh_rows();self.render()
            self.status.set(item['name']+' · tracking temperature and pixel position · saves with Record / Stop')
        except Exception as exc:self.status.set(str(exc))

    def sync_alignment(self):
        for key,var in self.alignment.items():
            var.set(f"{self.settings['alignment'][key]:.3f}")
            self.alignment_sliders[key].set(self.settings['alignment'][key])

    def open_alignment_tool(self):
        if getattr(self,'alignment_tool',None) and not self.alignment_tool.closed:
            self.alignment_tool.use_current_selection()
            self.alignment_tool.window.lift();return
        try:
            from .alignment_tool import AlignmentTool
            self.alignment_tool=AlignmentTool(self)
        except Exception as exc:self.status.set('Alignment tool: '+str(exc))

    def open_smart_alignment_tool(self):
        if getattr(self,'smart_alignment_tool',None) and not self.smart_alignment_tool.closed:
            self.smart_alignment_tool.window.lift();return
        try:
            from .smart_alignment_tool import SmartAlignmentTool
            self.smart_alignment_tool=SmartAlignmentTool(self)
        except Exception as exc:self.status.set('Smart alignment tool: '+str(exc))

    def slide_alignment(self,key,value):
        if self.locked.get():self.sync_alignment();return
        self.settings['alignment'][key]=float(value)
        self.sync_alignment();self.changed();self.render()

    def apply_alignment(self):
        if self.locked.get():self.sync_alignment();return
        try:
            candidate=dict(self.settings,alignment={key:var.get() for key,var in self.alignment.items()})
            self.settings=validate_settings(candidate);self.sync_alignment();self.changed();self.render()
        except Exception as exc:self.status.set(str(exc))

    def reset_alignment(self):
        if self.locked.get():return
        self.settings['alignment']=dict(dx=0,dy=0,scale=1,angle=0);self.sync_alignment();self.changed();self.render()

    def changed(self):
        try:
            self.settings=validate_settings(self.settings);save_settings(self.workspace_path,self.settings)
            self.send('settings',settings=self.settings)
        except Exception as exc:self.status.set('Layout error: '+str(exc))

    def refresh_rows(self):
        for identifier in self.table.get_children():self.table.delete(identifier)
        for item in self.settings['points']+self.settings['areas']:
            self.table.insert('', 'end',iid=item['id'],values=(item['name'],'—'))
        if self.selected and self.table.exists(self.selected):
            self.table.selection_set(self.selected);self.table.see(self.selected)
        self.refresh_values()

    def refresh_values(self):
        valid=self.frame is not None and time.monotonic()-self.received_at<=1
        values=measurement_values(self.frame,self.settings) if valid else {}
        for item in self.settings['points']+self.settings['areas']:
            value=values.get(item['id']);text='—'
            if value:text=f"{value['value']:.2f}" if 'value' in value else f"{value['min']:.1f} · {value['mean']:.1f} · {value['max']:.1f}"
            if value and value.get('tracking'):text+=f" · ({value['pixel_x']}, {value['pixel_y']})"
            if self.table.exists(item['id']):self.table.item(item['id'],values=(item['name'],text))

    def select_row(self,_):
        selected=self.table.selection()
        if selected:
            self.selected=selected[0]
            item=next((v for v in self.settings['points']+self.settings['areas'] if v['id']==self.selected),None)
            if item:self.name.set(item['name'])

    def rename(self):
        name=self.name.get().strip()
        if not name or len(name)>80:self.status.set('Enter a measurement name of 1–80 characters');return
        for item in self.settings['points']+self.settings['areas']:
            if item['id']==self.selected:item['name']=name
        self.changed();self.refresh_rows();self.render()

    def remove(self):
        self.settings=remove_measurement(self.settings,self.selected)
        self.selected=None;self.name.set('');self.changed();self.refresh_rows();self.render()

    def clear_points(self):
        if not self.settings['points']:return
        self.settings['points']=[]
        self.selected=None;self.drag=None;self.name.set('')
        self.tool.set('Select')
        self.changed();self.refresh_rows();self.render()

    def save(self):
        path=filedialog.asksaveasfilename(title='Save alignment and measurement layout',defaultextension='.json',filetypes=[('Thermal layout','*.json')])
        if path:
            try:save_settings(path,self.settings)
            except Exception as exc:messagebox.showerror('Save failed',str(exc))

    def load(self):
        self.polygon.cancel()
        path=filedialog.askopenfilename(title='Load alignment and measurement layout',filetypes=[('Thermal layout','*.json')])
        if path:
            try:
                value=read_settings(path)
                target=self.camera_choice.get()
                if target and value.get('camera_id') and value['camera_id'].casefold()!=target.casefold():
                    raise ValueError('This layout belongs to another camera')
                if target:value['camera_id']=target
                self.settings=value;self.selected=None;self.sync_alignment();self.changed();self.refresh_rows();self.render()
            except Exception as exc:messagebox.showerror('Load failed',str(exc))

    def close(self):
        if getattr(self,'alignment_tool',None) and not self.alignment_tool.closed:self.alignment_tool.close()
        if getattr(self,'smart_alignment_tool',None) and not self.smart_alignment_tool.closed:self.smart_alignment_tool.close()
        self.closing=True
        if self.process and self.process.is_alive():
            self.send('stop');self.stop_deadline=time.monotonic()+7;self.status.set('Closing camera and finalizing recording…')
        else:self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topview-directory',type=Path)
    parser.add_argument('--recordings',type=Path,default=Path.home()/'Thermal-Lab-Recordings')
    parser.add_argument('--workspace',type=Path,default=Path.home()/'.thermal-lab/workspace.json')
    parser.add_argument('--camera-id',help='Windows PnP camera identity; indexes are never persisted')
    args=parser.parse_args();root=tk.Tk();Desktop(root,args);root.mainloop()


if __name__=='__main__':main()
