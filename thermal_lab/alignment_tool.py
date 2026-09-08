"""Frozen-pair alignment assistant; expensive matching runs outside Tk's thread."""
import copy
import hashlib
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from .auto_alignment import fit_alignment, valid_region, alignment_from_regions
from .alignment_profiles import read_profiles, save_profiles, at_distance
from .imaging import thermal_image, aligned_optical, rotate_image


class AlignmentTool:
    def __init__(self,desktop):
        self.desktop=desktop;self.camera_id=desktop.settings['camera_id'];self.region=[.1,.1,.9,.9]
        self.closed=False;self.searching=False;self.cancel=threading.Event();self.results=queue.Queue();self.photos=[]
        key=hashlib.sha256(self.camera_id.casefold().encode()).hexdigest()[:16]
        self.profile_path=desktop.args.workspace.parent/'alignment-profiles'/f'{key}.json'
        self.profiles=read_profiles(self.profile_path,self.camera_id)
        self.window=tk.Toplevel(desktop.root);self.window.title('Auto alignment · '+self.camera_id.rsplit('\\',1)[-1])
        self.window.geometry('1050x780');self.window.minsize(900,700);self.window.transient(desktop.root)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.message=tk.StringVar();self.name=tk.StringVar(value='Near target');self.distance=tk.StringVar()
        self.preview_mode=tk.StringVar(value='Blend');self.profile_choice=tk.StringVar()
        self.guide=tk.BooleanVar(value=False);self.optical_region=None;self.guided_seed=None
        body=ttk.Frame(self.window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text='AUTO ALIGNMENT · CHOOSE THE TARGET',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(body,text='Draw a box on the frozen thermal image around ONE object or surface. Nearby and distant objects may need different alignments.',wraplength=980).pack(anchor='w',pady=6)
        row=ttk.Frame(body);row.pack(fill='x')
        ttk.Button(row,text='Refresh pair',command=self.capture).pack(side='left')
        self.auto_button=ttk.Button(row,text='Auto-align selected target',command=self.auto);self.auto_button.pack(side='left',padx=8)
        ttk.Button(row,text='Cancel search',command=self.cancel.set).pack(side='left')
        ttk.Checkbutton(row,text='Guide with optical target box',variable=self.guide,command=self.draw).pack(side='left',padx=8)
        box=ttk.Combobox(row,textvariable=self.preview_mode,values=['Blend','Optical'],state='readonly',width=10);box.pack(side='right');box.bind('<<ComboboxSelected>>',lambda _:self.draw())
        panels=ttk.Frame(body);panels.pack(fill='both',expand=True,pady=10)
        self.canvases=[]
        for label in ('THERMAL · draw target box','CANDIDATE · inspect the same target'):
            panel=ttk.Frame(panels);panel.pack(side='left',fill='both',expand=True,padx=3)
            ttk.Label(panel,text=label).pack(anchor='w')
            canvas=tk.Canvas(panel,bg='#0b1119',highlightthickness=0,width=480,height=360);canvas.pack(fill='both',expand=True)
            canvas.bind('<Configure>',lambda _:self.draw());self.canvases.append(canvas)
        self.canvases[0].bind('<ButtonPress-1>',self.press);self.canvases[0].bind('<B1-Motion>',self.drag)
        self.canvases[0].bind('<ButtonRelease-1>',self.release)
        self.canvases[1].bind('<ButtonPress-1>',lambda e:self.press(e,True))
        self.canvases[1].bind('<B1-Motion>',lambda e:self.drag(e,True))
        self.canvases[1].bind('<ButtonRelease-1>',lambda e:self.release(e,True))
        ttk.Label(body,textvariable=self.message,wraplength=980).pack(anchor='w',pady=5)
        row=ttk.Frame(body);row.pack(fill='x',pady=4)
        ttk.Label(row,text='Target profile').pack(side='left');ttk.Entry(row,textvariable=self.name,width=22).pack(side='left',padx=5)
        ttk.Label(row,text='Distance · metres (optional)').pack(side='left');ttk.Entry(row,textvariable=self.distance,width=9).pack(side='left',padx=5)
        self.save_button=ttk.Button(row,text='Save verified profile',command=self.save_profile);self.save_button.pack(side='right')
        row=ttk.Frame(body);row.pack(fill='x',pady=4)
        self.profile_box=ttk.Combobox(row,textvariable=self.profile_choice,values=[p['name'] for p in self.profiles['profiles']],state='readonly',width=24);self.profile_box.pack(side='left')
        ttk.Button(row,text='Preview profile',command=self.load_profile).pack(side='left',padx=5)
        ttk.Button(row,text='Predict at distance',command=self.predict).pack(side='left')
        self.apply_button=ttk.Button(row,text='Apply reviewed alignment',command=self.apply);self.apply_button.pack(side='right')
        ttk.Label(body,text='Distance is entered by you, not measured by the camera. Prediction uses your saved near/far settings within their calibrated range. This aligns one depth plane; it cannot align all depths at once or change thermal measurements.',wraplength=980,foreground='#9aafc3').pack(anchor='w',pady=7)
        self.frame=None;self.verified=False;self.start=None;self.capture();self.buttons();self.window.after(100,self.poll)

    def capture(self):
        if self.searching:self.message.set('Cancel or finish the current search first.');return
        d=self.desktop
        if d.settings.get('camera_id')!=self.camera_id or d.frame is None or d.optical is None or time.monotonic()-d.received_at>1:
            self.message.set('A fresh frame from this camera is required. Connect it and Refresh pair.');return
        self.frame=copy.deepcopy(d.frame);self.optical=d.optical.copy();self.base=dict(d.settings['alignment'])
        self.candidate=dict(self.base);self.verified=False;self.start=None;self.optical_region=None;self.guided_seed=None;self.guide.set(False)
        self.thermal=thermal_image(self.frame['temperatures'],'Iron')[0]
        self.message.set(f"Frozen frame {self.frame['arrival_sequence']}. Draw a target box, then Auto-align. Refresh if the target moves.")
        self.buttons();self.draw()

    def buttons(self):
        ready=bool(self.frame is not None and not self.searching)
        self.auto_button.configure(state='normal' if ready else 'disabled')
        for b in (self.apply_button,self.save_button):b.configure(state='normal' if ready and self.verified else 'disabled')

    def draw(self):
        if self.closed or self.frame is None:return
        optical=aligned_optical(self.optical,self.candidate)
        pictures=[self.thermal,self.optical if self.guide.get() else optical if self.preview_mode.get()=='Optical' else Image.blend(optical,self.thermal,.5)]
        self.photos=[];self.bounds=[]
        for index,(canvas,picture) in enumerate(zip(self.canvases,pictures)):
            canvas.delete('all');w,h=canvas.winfo_width(),canvas.winfo_height();scale=max(.01,min(w/1024,h/768))
            pw,ph=max(1,int(1024*scale)),max(1,int(768*scale));left,top=(w-pw)/2,(h-ph)/2
            photo=ImageTk.PhotoImage(rotate_image(picture,180).resize((pw,ph),Image.Resampling.BILINEAR));self.photos.append(photo)
            canvas.create_image(left,top,image=photo,anchor='nw');self.bounds.append((left,top,pw,ph))
            selected=self.optical_region if index==1 and self.guide.get() else self.region
            if selected:
                x,y,x2,y2=selected;canvas.create_rectangle(left+(1-x2)*pw,top+(1-y2)*ph,left+(1-x)*pw,top+(1-y)*ph,outline='#67ffe0',width=2)
            if index==1 and self.guide.get():canvas.create_text(12,12,anchor='nw',text='RAW OPTICAL · box the SAME target',fill='#67ffe0')

    def point(self,e,optical=False):
        left,top,w,h=self.bounds[int(optical)]
        return (max(0,min(1,1-(e.x-left)/w)),max(0,min(1,1-(e.y-top)/h)))

    def press(self,e,optical=False):
        if self.searching or self.frame is None or (optical and not self.guide.get()):return
        self.start=self.point(e,optical);self.drag_optical=optical;self.old_region=copy.copy(self.optical_region if optical else self.region)

    def drag(self,e,optical=False):
        if self.searching or self.start is None or self.drag_optical!=optical:return
        p=self.point(e,optical);region=[min(self.start[0],p[0]),min(self.start[1],p[1]),max(self.start[0],p[0]),max(self.start[1],p[1])]
        if optical:self.optical_region=region
        else:self.region=region
        self.draw()

    def release(self,e,optical=False):
        if self.searching or self.start is None or self.drag_optical!=optical:return
        self.drag(e,optical);self.start=None;self.verified=False
        try:
            valid_region(self.optical_region if optical else self.region)
            if optical:
                self.candidate=alignment_from_regions(self.region,self.optical_region,self.base['angle']);self.guided_seed=dict(self.candidate)
                self.guide.set(False);self.verified=True
                self.message.set('Box-based alignment estimate. Inspect the target, or Auto-align to refine locally. No distance was inferred.')
            else:
                self.guided_seed=None;self.optical_region=None
                self.message.set('Target selected. Auto-align, or enable optical target guidance and box the same object on the right.')
        except ValueError as exc:
            if optical:self.optical_region=self.old_region
            else:self.region=self.old_region
            self.message.set(str(exc))
        self.buttons();self.draw()

    def auto(self):
        if self.searching or self.frame is None:return
        self.searching=True;self.verified=False;self.cancel.clear();self.buttons();self.message.set('Matching frozen thermal and optical detail…')
        values=list(self.frame['temperatures']);optical=self.optical.copy();initial=dict(self.guided_seed or self.base);region=list(self.region);guided=self.guided_seed is not None
        def work():
            try:self.results.put((True,fit_alignment(values,optical,initial,region,guided=guided,cancelled=self.cancel.is_set)))
            except Exception as exc:self.results.put((False,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        if self.closed:return
        try:
            ok,result=self.results.get_nowait();self.searching=False
            if ok:
                self.candidate=result['alignment'];self.verified=result['reliable'];self.draw()
                self.message.set(result['message']+f" Match {result['score']:.3f}; validation {result['validation_score']:.3f}. These are relative scores, not accuracy percentages.")
                if not result['reliable'] and self.guided_seed:
                    self.candidate=dict(self.guided_seed);self.verified=True;self.draw()
                    self.message.set('Automatic refinement was uncertain; retained your paired-box estimate. Inspect before applying or saving.')
            else:self.message.set(result)
            self.buttons()
        except queue.Empty:pass
        self.window.after(100,self.poll)

    def save_profile(self):
        if not self.verified or self.searching:return
        try:
            p=dict(name=self.name.get().strip(),distance_m=float(self.distance.get()) if self.distance.get().strip() else None,region=self.region,alignment=self.candidate)
            value=copy.deepcopy(self.profiles);value['profiles']=[x for x in value['profiles'] if x['name'].casefold()!=p['name'].casefold()]+[p]
            save_profiles(self.profile_path,value);self.profiles=read_profiles(self.profile_path,self.camera_id)
            self.profile_box.configure(values=[x['name'] for x in self.profiles['profiles']]);self.profile_choice.set(p['name'])
            self.message.set('Profile saved for this camera. Use separate profiles for near and far targets.')
        except Exception as exc:self.message.set(str(exc))

    def load_profile(self):
        if self.searching or self.frame is None:return
        p=next((p for p in self.profiles['profiles'] if p['name']==self.profile_choice.get()),None)
        if p:
            self.guided_seed=None;self.optical_region=None;self.guide.set(False)
            self.candidate=dict(p['alignment']);self.region=list(p['region']);self.name.set(p['name']);self.distance.set('' if p['distance_m'] is None else str(p['distance_m']))
            self.verified=True;self.buttons();self.draw();self.message.set('Saved profile preview. Check the target and distance before applying.')

    def predict(self):
        if self.searching or self.frame is None:return
        try:
            self.candidate=at_distance(self.profiles,self.distance.get())
            self.guided_seed=None;self.optical_region=None;self.guide.set(False)
            self.verified=True;self.buttons();self.draw()
            self.message.set('Estimated from your distance profiles. Check this target before applying; actual depth is not measured.')
        except Exception as exc:self.message.set(str(exc))

    def apply(self):
        if not self.verified or self.searching:return
        d=self.desktop
        if d.locked.get():self.message.set('Unlock alignment in the live window first.');return
        if d.settings.get('camera_id')!=self.camera_id or d.settings['alignment']!=self.base:
            self.message.set('The camera or live alignment changed. Refresh pair before applying.');return
        d.settings['alignment']=dict(self.candidate);d.sync_alignment();d.changed();d.render();self.base=dict(self.candidate)
        self.message.set('Alignment applied and saved. Thermal pixels and measurement coordinates are unchanged.')

    def close(self):self.closed=True;self.cancel.set();self.window.destroy()
