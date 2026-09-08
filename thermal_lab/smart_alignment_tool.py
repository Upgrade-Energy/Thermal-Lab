"""Continuous, confidence-masked preview plus measured stereo calibration workflow."""
import copy
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk,ImageDraw
from .stereo_calibration import camera_path,detect_pair,checked_pair,solve_calibration,read_calibration,save_calibration,projection_maps,object_points,read_session,save_session
from .regional_alignment import similarity_maps,estimate_regions,render_regions
from .imaging import thermal_image,rotate_image


class SmartAlignmentTool:
    def __init__(self,desktop):
        self.desktop=desktop;self.camera_id=desktop.settings['camera_id'];self.path=camera_path(desktop.args.workspace,self.camera_id)
        self.closed=False;self.busy=False;self.continuous=False;self.cancel=threading.Event();self.results=queue.Queue()
        self.frame=None;self.result=None;self.detected=None;self.pairs=[];self.photos=[];self.last_sequence=None;self.generation=0
        try:self.calibration=read_calibration(self.path,self.camera_id);load_error=None
        except Exception as exc:self.calibration=None;load_error=str(exc)
        self.window=tk.Toplevel(desktop.root);self.window.title('Smart overlay · '+self.camera_id.rsplit('\\',1)[-1]);self.window.geometry('1120x850');self.window.minsize(1000,800)
        self.window.transient(desktop.root);self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.message=tk.StringVar();self.details=tk.StringVar();self.calibrating=tk.BooleanVar(value=False);self.hatching=tk.BooleanVar(value=True)
        self.reverse=tk.BooleanVar(value=False);self.square=tk.StringVar(value='25');self.distance=tk.StringVar(value='1.0')
        try:
            self.pairs,self.spacing=read_session(self.path,self.camera_id);self.square.set(str(self.spacing))
        except Exception as exc:load_error=str(exc)
        body=ttk.Frame(self.window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text='SMART OVERLAY · EXPERIMENTAL',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(body,text='Local corrections for different depths. Amber hatching means no trustworthy optical match; numerical thermal pixels stay fixed.',wraplength=1050).pack(anchor='w',pady=6)
        row=ttk.Frame(body);row.pack(fill='x')
        self.once=ttk.Button(row,text='Analyze one pair',command=self.analyze);self.once.pack(side='left')
        self.start=ttk.Button(row,text='Start continuous',command=self.start_continuous);self.start.pack(side='left',padx=5)
        ttk.Button(row,text='Stop',command=self.stop).pack(side='left')
        ttk.Checkbutton(row,text='Show uncertainty',variable=self.hatching,command=self.draw).pack(side='left',padx=8)
        ttk.Checkbutton(row,text='Calibration mode',variable=self.calibrating,command=self.change_mode).pack(side='right')
        row=ttk.Frame(body);row.pack(fill='x',pady=6)
        ttk.Label(row,text='Reference depth · m').pack(side='left');ttk.Entry(row,textvariable=self.distance,width=7).pack(side='left',padx=5)
        ttk.Label(row,textvariable=self.details,wraplength=800).pack(side='left',padx=8)
        self.cal_panel=ttk.Frame(body);self.cal_panel.pack(fill='x')
        ttk.Label(self.cal_panel,text='Use a rigid 8 × 6 square checkerboard (7 × 5 inner corners), visible in BOTH thermal and optical. A printed page alone may have no thermal contrast. Hold it still; capture 12–40 different positions, distances and tilts.',wraplength=1050).pack(anchor='w',pady=4)
        row=ttk.Frame(self.cal_panel);row.pack(fill='x')
        ttk.Label(row,text='Square spacing · mm').pack(side='left');ttk.Entry(row,textvariable=self.square,width=7).pack(side='left',padx=4)
        self.detect=ttk.Button(row,text='Detect frozen pattern',command=self.detect_pattern);self.detect.pack(side='left',padx=4)
        ttk.Checkbutton(row,text='Reverse optical order',variable=self.reverse,command=self.draw).pack(side='left')
        self.add=ttk.Button(row,text='Add verified pair',command=self.add_pair);self.add.pack(side='left',padx=4)
        self.solve_button=ttk.Button(row,text='Solve & save calibration',command=self.solve);self.solve_button.pack(side='right')
        row=ttk.Frame(self.cal_panel);row.pack(fill='x')
        ttk.Button(row,text='Undo last pair',command=self.undo).pack(side='left',pady=4)
        ttk.Button(row,text='New session',command=self.new_session).pack(side='left',padx=4)
        ttk.Label(row,text='Check that corner 1 and 35 identify the SAME physical corners in both views. Captured corners autosave.',wraplength=750).pack(side='left',padx=8)
        self.cal_panel.pack_forget()
        panels=ttk.Frame(body);panels.pack(fill='both',expand=True,pady=8);self.canvases=[]
        for name in ('THERMAL · original coordinates','OPTICAL / SUPPORTED OVERLAY'):
            panel=ttk.Frame(panels);panel.pack(side='left',fill='both',expand=True,padx=3)
            ttk.Label(panel,text=name).pack(anchor='w');c=tk.Canvas(panel,width=510,height=360,bg='#0b1119',highlightthickness=0);c.pack(fill='both',expand=True)
            c.bind('<Configure>',lambda _:self.draw());self.canvases.append(c)
        self.panels=panels
        ttk.Label(body,textvariable=self.message,wraplength=1050).pack(anchor='w',pady=6)
        ttk.Label(body,text='This preview uses the exact pair being analyzed and may update slower than capture. It does not apply a warp to the measurement workspace or recordings. Depth is not measured; perfect alignment of occluded or unrelated features is impossible.',wraplength=1050,foreground='#9aafc3').pack(anchor='w',pady=6)
        self.update_buttons();self.message.set(load_error or 'Choose Analyze one pair, or collect a measured camera calibration first.')
        self.window.after(100,self.poll)

    def update_buttons(self):
        mode=self.calibrating.get()
        for button in (self.once,self.start):button.configure(state='disabled' if self.busy or mode else 'normal')
        self.detect.configure(state='normal' if mode and not self.busy else 'disabled')
        self.add.configure(state='normal' if mode and not self.busy and self.detected is not None else 'disabled')
        self.solve_button.configure(state='normal' if mode and not self.busy and len(self.pairs)>=12 else 'disabled')
        label=f"Calibrated · validation ≤ {max(self.calibration['validation_rms_px']):.2f} thermal px" if self.calibration else 'UNCALIBRATED TRIAL · current manual alignment only'
        self.details.set(label+f' · {len(self.pairs)}/12+ collected poses')

    def fresh_pair(self):
        d=self.desktop
        if d.settings.get('camera_id')!=self.camera_id or d.frame is None or d.optical is None or time.monotonic()-d.received_at>1:
            raise ValueError('STALE / DISCONNECTED: a fresh pair from this camera is required')
        return copy.deepcopy(d.frame),d.optical.copy(),dict(d.settings['alignment'])

    def run(self,kind,operation,context):
        if self.busy:return
        self.busy=True;self.cancel.clear();self.update_buttons();generation=self.generation
        def worker():
            try:self.results.put((generation,kind,True,operation(),context))
            except Exception as exc:self.results.put((generation,kind,False,str(exc),context))
        threading.Thread(target=worker,daemon=True).start()

    def analyze(self):
        if self.busy or self.calibrating.get():return
        try:
            frame,optical,alignment=self.fresh_pair()
            if self.continuous and frame['arrival_sequence']==self.last_sequence:return
            distance=float(self.distance.get())
            maps=projection_maps(self.calibration,distance) if self.calibration else similarity_maps(alignment)
            if not self.continuous or self.frame is None:self.message.set('Analyzing local matches on a fresh pair…')
            context=(frame,optical,maps,time.monotonic());self.last_sequence=frame['arrival_sequence']
            self.run('analysis',lambda:estimate_regions(frame['temperatures'],optical,maps,cancelled=self.cancel.is_set),context)
        except Exception as exc:self.continuous=False;self.message.set(str(exc))

    def start_continuous(self):
        if self.busy or self.calibrating.get():return
        self.continuous=True;self.last_sequence=None;self.analyze()

    def stop(self):
        self.continuous=False;self.cancel.set();self.generation+=1
        self.message.set('Stopped · frozen analyzed pair; the main camera preview continues.')

    def change_mode(self):
        self.stop();self.detected=None;self.result=None;self.frame=None
        if self.calibrating.get():self.cal_panel.pack(fill='x',before=self.panels)
        else:self.cal_panel.pack_forget()
        for c in self.canvases:c.delete('all')
        self.update_buttons()

    def detect_pattern(self):
        if self.busy:return
        try:
            frame,optical,_=self.fresh_pair();self.detected=None;self.reverse.set(False)
            self.message.set('Detecting a stationary calibration pattern in both sensors…')
            self.run('detect',lambda:detect_pair(frame['temperatures'],optical),(frame,optical))
        except Exception as exc:self.message.set(str(exc))

    def add_pair(self):
        if self.busy or self.detected is None:return
        try:
            pair=copy.deepcopy(self.detected)
            if self.reverse.get():pair['optical'].reverse()
            checked_pair(pair)
            if len(self.pairs)>=40:raise ValueError('Maximum 40 poses; undo an unwanted pair first')
            spacing=float(self.square.get())
            object_points(spacing)
            if self.pairs and spacing!=self.spacing:raise ValueError('Square spacing cannot change within one calibration session')
            self.spacing=spacing;pair['arrival_sequence']=self.frame['arrival_sequence']
            save_session(self.path,self.camera_id,self.pairs+[pair],spacing)
            self.pairs.append(pair);self.detected=None
            self.message.set('Pair added. Move and tilt the pattern, hold still, then detect another pair.');self.update_buttons()
        except Exception as exc:self.message.set(str(exc))

    def undo(self):
        if not self.busy and self.pairs:
            try:
                save_session(self.path,self.camera_id,self.pairs[:-1],self.spacing);self.pairs.pop();self.update_buttons()
            except Exception as exc:self.message.set(str(exc))

    def new_session(self):
        if self.busy:return
        try:
            save_session(self.path,self.camera_id,[],float(self.square.get()));self.pairs=[];self.detected=None;self.update_buttons()
            self.message.set('New capture session. The last validated calibration stays available until a replacement passes.')
        except Exception as exc:self.message.set(str(exc))

    def solve(self):
        if self.busy:return
        pairs=copy.deepcopy(self.pairs);spacing=self.spacing
        self.message.set('Solving lens geometry and validating against held-out poses…')
        self.run('solve',lambda:solve_calibration(pairs,self.camera_id,spacing),None)

    def poll(self):
        if self.closed:return
        try:
            generation,kind,ok,value,context=self.results.get_nowait();self.busy=False
            if generation==self.generation:
                if not ok:
                    self.message.set(value);self.continuous=False
                    if kind=='detect':self.frame,self.optical=context;self.result=None;self.detected=None;self.draw()
                elif kind=='analysis':
                    self.frame,self.optical,self.maps,captured=context;self.result=value;self.detected=None
                    age=time.monotonic()-captured
                    if age>2:
                        self.result=None;self.frame=None;self.continuous=False
                        for canvas in self.canvases:canvas.delete('all')
                        self.message.set('Analysis took too long; no outdated warp is shown. Retry on a stationary scene.')
                    else:self.message.set(f"{'CONTINUOUS' if self.continuous else 'FROZEN'} · analyzed frame {self.frame['arrival_sequence']} · {value['coverage']:.0%} supported area · {value['elapsed']:.2f}s matching. Amber = uncertain, not an accuracy percentage.")
                    self.draw()
                elif kind=='detect':
                    self.frame,self.optical=context;self.result=None;self.detected=value
                    self.message.set('Check both numbered corner sequences. Reverse optical order if needed, then Add verified pair.');self.draw()
                else:
                    try:
                        save_calibration(self.path,value);self.calibration=value
                        self.message.set('Measured calibration saved for this camera. Disable Calibration mode and try continuous alignment.')
                    except Exception as exc:self.message.set(str(exc))
            self.update_buttons()
        except queue.Empty:pass
        if self.continuous and not self.busy:self.analyze()
        self.window.after(150,self.poll)

    def draw(self):
        if self.closed or self.frame is None:return
        thermal=thermal_image(self.frame['temperatures'],'Iron')[0]
        right=render_regions(thermal,self.optical,self.maps,self.result,self.hatching.get()) if self.result is not None else self.optical.copy()
        pictures=[thermal,right]
        if self.calibrating.get() and self.detected:
            for i,key in enumerate(('thermal','optical')):
                points=self.detected[key][::-1] if i and self.reverse.get() else self.detected[key]
                draw=ImageDraw.Draw(pictures[i])
                for n,(x,y) in enumerate(points):
                    draw.ellipse((x*4-5,y*4-5,x*4+5,y*4+5),outline='cyan',width=2)
                # Draw labels after rotation so their text stays upright.
        self.photos=[]
        for i,(canvas,picture) in enumerate(zip(self.canvases,pictures)):
            canvas.delete('all');w,h=canvas.winfo_width(),canvas.winfo_height();scale=max(.01,min(w/1024,h/768));pw,ph=max(1,int(1024*scale)),max(1,int(768*scale))
            left,top=(w-pw)/2,(h-ph)/2;photo=ImageTk.PhotoImage(rotate_image(picture,180).resize((pw,ph),Image.Resampling.BILINEAR));self.photos.append(photo)
            canvas.create_image(left,top,image=photo,anchor='nw')
            if self.calibrating.get() and self.detected:
                points=self.detected['optical' if i else 'thermal'];points=points[::-1] if i and self.reverse.get() else points
                for n,(x,y) in enumerate(points):canvas.create_text(left+(1-x/256)*pw,top+(1-y/192)*ph,text=str(n+1),fill='cyan',anchor='sw')

    def close(self):
        self.closed=True;self.cancel.set();self.continuous=False;self.window.destroy()
