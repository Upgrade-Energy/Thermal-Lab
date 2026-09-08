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


class Desktop:
    def __init__(self, root, args):
        self.root=root;self.args=args;self.process=None;self.closing=False;self.stop_deadline=None
        self.frame=None;self.optical=None;self.received_at=0;self.drag=None;self.viewports=[]
        self.stream_active=False;self.record_pending=False
        self.settings=validate_settings({});self.recording=False;self.record_path=None
        self.selected=None;self.zoom=1;self.pan=[0,0];self.photos=[]
        self.ctx=mp.get_context('spawn');self.commands=None
        self.workspace_path=args.workspace
        self.camera_choice=tk.StringVar(value=args.camera_id or '')
        root.title('Thermal Lab · Live inspection');root.geometry('1440x960');root.minsize(1080,900)
        root.configure(bg='#111923');root.protocol('WM_DELETE_WINDOW',self.close)
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',background='#172331',foreground='#e3ebf5',fieldbackground='#233448',font=('Segoe UI',10))
        style.configure('TButton',padding=(10,7));style.map('TButton',background=[('active','#345575')])
        style.configure('Treeview',rowheight=30,background='#172331',fieldbackground='#172331',foreground='#e3ebf5')
        style.map('Treeview',background=[('selected','#305b77')])
        style.map('TCombobox',fieldbackground=[('readonly','#233448')],foreground=[('readonly','#e3ebf5')])
        for widget in ('TRadiobutton','TCheckbutton'):
            style.map(widget,background=[('active','#233448')],foreground=[('active','#e3ebf5')])
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
        header=ttk.Frame(root,padding=(18,12));header.pack(fill='x')
        ttk.Label(header,text='THERMAL LAB',font=('Segoe UI',17,'bold')).pack(side='left')
        ttk.Label(header,text='LIVE INSPECTION  /  DEV11',foreground='#8ba4be').pack(side='left',padx=22)
        self.connect_button=ttk.Button(header,text='Connect camera',command=self.connect);self.connect_button.pack(side='right')
        self.record_button=ttk.Button(header,text='Record session',command=self.toggle_record,state='disabled');self.record_button.pack(side='right',padx=8)
        self.optical_check=ttk.Checkbutton(header,text='Optical video · lossless',variable=self.record_optical)
        self.optical_check.pack(side='right',padx=8)
        connection=ttk.Frame(root,padding=(18,0,18,10));connection.pack(fill='x')
        ttk.Label(connection,text='TopView installation').pack(side='left')
        ttk.Entry(connection,textvariable=self.path).pack(side='left',fill='x',expand=True,padx=10)
        ttk.Button(connection,text='Browse…',command=self.browse).pack(side='left')
        cameras=ttk.Frame(root,padding=(18,0,18,6));cameras.pack(fill='x')
        ttk.Label(cameras,text='Camera').pack(side='left')
        self.camera_box=ttk.Combobox(cameras,textvariable=self.camera_choice,state='readonly',width=65)
        self.camera_box.pack(side='left',fill='x',expand=True,padx=10)
        self.camera_box.bind('<<ComboboxSelected>>',lambda e:self.select_camera_layout())
        self.refresh_button=ttk.Button(cameras,text='Refresh',command=self.refresh_cameras);self.refresh_button.pack(side='left')
        ttk.Button(cameras,text='Review recordings',command=self.review_recordings).pack(side='left',padx=5)
        ttk.Button(cameras,text='Open another camera window',command=self.another_camera).pack(side='left',padx=8)
        self.connection_info=tk.StringVar(value='Checking camera connections…')
        ttk.Label(root,textvariable=self.connection_info,padding=(18,4),foreground='#d7c991',wraplength=1350).pack(fill='x')
        ttk.Label(root,textvariable=self.status,padding=(18,9),foreground='#72d7c5').pack(fill='x')
        body=ttk.Panedwindow(root,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body);right=ttk.Frame(body,padding=12);body.add(left,weight=4);body.add(right,weight=1)
        toolbar=ttk.Frame(left,padding=(4,4));toolbar.pack(fill='x')
        for variable,values,width in [(self.mode,['Thermal','Optical','Blend','Side by side'],14),
                                      (self.palette,['Iron','Rainbow','White hot','Black hot'],11),
                                      (self.rotation,['0','90','180','270'],5)]:
            box=ttk.Combobox(toolbar,textvariable=variable,values=values,width=width,state='readonly')
            box.pack(side='left',padx=3);box.bind('<<ComboboxSelected>>',lambda e:self.render())
        ttk.Button(toolbar,text='Fit',command=self.fit).pack(side='right')
        tools=ttk.Frame(left,padding=4);tools.pack(fill='x')
        for label in ['Select','Point','Rectangle','Align optical','Pan']:
            ttk.Radiobutton(tools,text=label,variable=self.tool,value=label).pack(side='left',padx=5)
        self.canvas=tk.Canvas(left,bg='#0b1119',highlightthickness=0,cursor='crosshair');self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.render());self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Motion>',self.hover);self.canvas.bind('<MouseWheel>',self.wheel)
        ttk.Label(left,textvariable=self.cursor,padding=8).pack(fill='x')
        ttk.Label(right,text='OPTICAL ALIGNMENT',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(right,text='Moves the optical layer; thermal pixels stay fixed.',wraplength=320,foreground='#9aafc3').pack(anchor='w',pady=(4,8))
        ttk.Label(right,text='Thermal opacity').pack(anchor='w')
        ttk.Scale(right,from_=0,to=1,variable=self.opacity,command=lambda _:self.render()).pack(fill='x')
        for key,label in [('dx','X offset · px'),('dy','Y offset · px'),('scale','Optical scale'),('angle','Rotation · °')]:
            low,high,step={'dx':(-512,512,1),'dy':(-384,384,1),'scale':(.1,8,.02),'angle':(-180,180,1)}[key]
            row=ttk.Frame(right);row.pack(fill='x',pady=3)
            ttk.Label(row,text=label,width=17).pack(side='left')
            spin=ttk.Spinbox(row,textvariable=self.alignment[key],from_=low,
                             to=high,increment=step,width=8,command=self.apply_alignment)
            spin.pack(side='right');spin.bind('<Return>',lambda e:self.apply_alignment());spin.bind('<FocusOut>',lambda e:self.apply_alignment())
            ttk.Scale(row,from_=low,to=high,variable=self.alignment_sliders[key],
                      command=lambda value,k=key:self.slide_alignment(k,value)).pack(side='left',fill='x',expand=True,padx=5)
        row=ttk.Frame(right);row.pack(fill='x',pady=6)
        ttk.Checkbutton(row,text='Lock alignment',variable=self.locked).pack(side='left')
        ttk.Button(row,text='Auto-align / distance…',command=self.open_alignment_tool).pack(side='left',padx=5)
        ttk.Button(row,text='Reset',command=self.reset_alignment).pack(side='right')
        ttk.Separator(right).pack(fill='x',pady=10)
        row=ttk.Frame(right);row.pack(fill='x')
        ttk.Label(row,text='TEMPERATURE SCALE',font=('Segoe UI',11,'bold')).pack(side='left')
        ttk.Checkbutton(right,text='Automatic range',variable=self.automatic,command=self.render).pack(anchor='w')
        row=ttk.Frame(right);row.pack(fill='x')
        for label,var in [('Low °C',self.low),('High °C',self.high)]:
            ttk.Label(row,text=label).pack(side='left');entry=ttk.Entry(row,textvariable=var,width=6);entry.pack(side='left',padx=4)
            entry.bind('<Return>',lambda e:self.render());entry.bind('<FocusOut>',lambda e:self.render())
        ttk.Separator(right).pack(fill='x',pady=10)
        ttk.Label(right,text='MEASUREMENTS · °C',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,6))
        self.table=ttk.Treeview(right,columns=('name','value'),show='headings',height=2,selectmode='browse')
        self.table.heading('name',text='Name');self.table.heading('value',text='Value / min · mean · max')
        self.table.column('name',width=110,minwidth=70);self.table.column('value',width=195,minwidth=150)
        self.table.pack(fill='both',expand=True);self.table.bind('<<TreeviewSelect>>',self.select_row)
        ttk.Entry(right,textvariable=self.name).pack(fill='x',pady=(7,3))
        row=ttk.Frame(right);row.pack(fill='x')
        ttk.Button(row,text='Rename',command=self.rename).pack(side='left')
        ttk.Button(row,text='Remove',command=self.remove).pack(side='right')
        ttk.Label(right,text='Select and drag a point or region to move it. Draw a new rectangle to change its size.',wraplength=320,foreground='#9aafc3').pack(anchor='w',pady=7)
        row=ttk.Frame(right);row.pack(fill='x')
        ttk.Button(row,text='Save layout…',command=self.save).pack(side='left')
        ttk.Button(row,text='Load layout…',command=self.load).pack(side='right')
        ttk.Label(root,textvariable=self.info,padding=(18,8),foreground='#b2c2d2').pack(side='bottom',fill='x',before=body)
        if args.workspace.exists():
            try:self.settings=read_settings(args.workspace);self.sync_alignment();self.refresh_rows()
            except Exception as exc:self.status.set(f'Layout not loaded: {exc}')
        root.after(80,self.poll)
        self.refresh_cameras()

    def refresh_cameras(self):
        if self.process and self.process.is_alive():return
        try:
            discovered=pnp_devices()
            self.connection_info.set(connection_guidance(discovered))
            devices=[d['instance_id'] for d in discovered if d.get('problem_code')==0]
            self.camera_box.configure(values=devices)
            if self.camera_choice.get() not in devices:self.camera_choice.set(devices[0] if devices else '')
            if self.camera_choice.get():self.select_camera_layout()
            if not devices:self.status.set('No healthy TC001 Max detected; connect it and press Refresh')
        except Exception as exc:self.status.set('Camera discovery failed: '+str(exc))

    def select_camera_layout(self):
        if self.process and self.process.is_alive():return
        try:
            self.prepare_camera_layout(self.camera_choice.get())
            self.frame=None;self.optical=None;self.received_at=0;self.render()
        except Exception as exc:self.status.set('Layout error: '+str(exc))

    def another_camera(self):
        others=[d for d in self.camera_box['values'] if d!=self.camera_choice.get()]
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

    def prepare_camera_layout(self, camera_id):
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
        self.root.title('Thermal Lab · '+camera_id.rsplit('\\',1)[-1])

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
                        self.record_button.configure(text='Stop recording',state='normal')
                    elif kind=='recording_finished':
                        self.record_pending=False
                        self.recording=False;self.record_button.configure(text='Record session',state='normal')
                        self.optical_check.configure(state='normal')
                        self.status.set(f"Recording {event['status']}: {event['frames']} frames · {event['path']}")
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
                self.info.set(f"Frame {self.frame['arrival_sequence']} · {self.frame['elapsed_s']:.1f} s · 256 × 192 thermal / 1024 × 768 optical · apparent °C · "
                              +(f"RECORDING {sample['recording_frames']} frames" if self.recording else 'preview; exposure timing unqualified'))
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
        self.root.after(80,self.poll)

    def current_limits(self):
        if self.automatic.get():return None
        low=float(self.low.get());high=float(self.high.get())
        if not (-100<=low<high<=1000):raise ValueError('Color scale needs -100 ≤ low < high ≤ 1000 °C')
        return low,high

    def render(self):
        self.canvas.delete('all');self.photos=[];self.viewports=[]
        cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
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
                px,py=sensor_to_view(item['x']*256,item['y']*192,rotation);px=x+px*scale;py=y+py*scale
                color='#ffffff' if item['id']==self.selected else '#67ffe0'
                if 'x2' in item:
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
        point=self.locate(event)
        if point and self.frame and time.monotonic()-self.received_at<=1:
            x,y=map(int,point);value=self.frame['temperatures'][y*256+x]
            self.cursor.set(f'Thermal pixel ({x}, {y})  ·  {value:.2f} °C apparent')
        else:self.cursor.set('Outside thermal coverage or no fresh frame')

    def press(self,event):
        point=self.locate(event)
        if not point or not self.frame or time.monotonic()-self.received_at>1:return
        self.drag=dict(point=point,start=(event.x,event.y),alignment=dict(self.settings['alignment']),pan=list(self.pan))
        if self.tool.get()=='Select':
            candidates=self.settings['points']+self.settings['areas'];found=None
            for item in reversed(candidates):
                x,y=item['x']*256,item['y']*192
                if ('x2' in item and x<=point[0]<=item['x2']*256 and y<=point[1]<=item['y2']*192) or ('x2' not in item and abs(x-point[0])<5 and abs(y-point[1])<5):
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
            original=self.drag['item'];item=next(v for v in self.settings['points']+self.settings['areas'] if v['id']==original['id'])
            dx=max(-original['x'],min(dx/256,.999999-original.get('x2',original['x'])))
            dy=max(-original['y'],min(dy/192,.999999-original.get('y2',original['y'])))
            for key in ('x','x2'):
                if key in item:item[key]=original[key]+dx
            for key in ('y','y2'):
                if key in item:item[key]=original[key]+dy
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

    def sync_alignment(self):
        for key,var in self.alignment.items():
            var.set(f"{self.settings['alignment'][key]:.3f}")
            self.alignment_sliders[key].set(self.settings['alignment'][key])

    def open_alignment_tool(self):
        if getattr(self,'alignment_tool',None) and not self.alignment_tool.closed:
            self.alignment_tool.window.lift();return
        try:
            from .alignment_tool import AlignmentTool
            self.alignment_tool=AlignmentTool(self)
        except Exception as exc:self.status.set('Alignment tool: '+str(exc))

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
        if self.selected and self.table.exists(self.selected):self.table.selection_set(self.selected)
        self.refresh_values()

    def refresh_values(self):
        valid=self.frame is not None and time.monotonic()-self.received_at<=1
        values=measurement_values(self.frame,self.settings) if valid else {}
        for item in self.settings['points']+self.settings['areas']:
            value=values.get(item['id']);text='—'
            if value:text=f"{value['value']:.2f}" if 'value' in value else f"{value['min']:.1f} · {value['mean']:.1f} · {value['max']:.1f}"
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
        for kind in ('points','areas'):self.settings[kind]=[v for v in self.settings[kind] if v['id']!=self.selected]
        self.selected=None;self.name.set('');self.changed();self.refresh_rows();self.render()

    def save(self):
        path=filedialog.asksaveasfilename(title='Save alignment and measurement layout',defaultextension='.json',filetypes=[('Thermal layout','*.json')])
        if path:
            try:save_settings(path,self.settings)
            except Exception as exc:messagebox.showerror('Save failed',str(exc))

    def load(self):
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
