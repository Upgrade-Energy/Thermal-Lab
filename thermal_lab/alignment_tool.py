"""Frozen-pair alignment assistant; expensive matching runs outside Tk's thread."""
import copy
import hashlib
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from .auto_alignment import fit_alignment, valid_region, alignment_from_regions, alignment_from_points
from .alignment_profiles import read_profiles, save_profiles, at_distance
from .imaging import thermal_image, aligned_optical, rotate_image


def selected_region(desktop):
    area=next((a for a in desktop.settings.get('areas',[]) if a['id']==getattr(desktop,'selected',None)),None)
    if area is None:return None
    try:return valid_region([area[k] for k in ('x','y','x2','y2')])
    except ValueError:return None


class AlignmentTool:
    def __init__(self,desktop):
        self.desktop=desktop;self.camera_id=desktop.settings['camera_id'];selection=selected_region(desktop)
        self.region=selection or [.1,.1,.9,.9];self.target_selected=selection is not None
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
        self.point_mode=False;self.point_pairs=[[],[]];self.zoom_target=tk.BooleanVar(value=False)
        body=ttk.Frame(self.window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text='AUTO ALIGNMENT · CHOOSE THE TARGET',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(body,text='1. Box ONE target on the left, with a little background.  2. Preview auto-alignment.  3. Apply to live. No checkerboard is needed for this tool.',wraplength=980).pack(anchor='w',pady=6)
        row=ttk.Frame(body);row.pack(fill='x')
        ttk.Button(row,text='Refresh pair',command=self.capture).pack(side='left')
        self.auto_button=ttk.Button(row,text='Preview auto-alignment',command=self.auto);self.auto_button.pack(side='left',padx=8)
        ttk.Button(row,text='Cancel search',command=self.cancel.set).pack(side='left')
        ttk.Checkbutton(row,text='Guide with optical target box',variable=self.guide,command=self.box_mode).pack(side='left',padx=8)
        box=ttk.Combobox(row,textvariable=self.preview_mode,values=['Blend','Optical'],state='readonly',width=10);box.pack(side='right');box.bind('<<ComboboxSelected>>',lambda _:self.draw())
        row=ttk.Frame(body);row.pack(fill='x',pady=4)
        ttk.Button(row,text='Match shared points',command=self.start_points).pack(side='left')
        ttk.Button(row,text='Undo point',command=self.undo_point).pack(side='left',padx=5)
        self.point_preview=ttk.Button(row,text='Preview point fit',command=self.preview_points);self.point_preview.pack(side='left')
        ttk.Checkbutton(row,text='Zoom selected target',variable=self.zoom_target,command=self.draw).pack(side='right')
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
        self.apply_button=ttk.Button(row,text='Apply to live',command=self.apply);self.apply_button.pack(side='right')
        ttk.Label(body,text='Distance is entered by you, not measured by the camera. Prediction uses your saved near/far settings within their calibrated range. This aligns one depth plane; it cannot align all depths at once or change thermal measurements.',wraplength=980,foreground='#9aafc3').pack(anchor='w',pady=7)
        self.frame=None;self.verified=False;self.start=None;self.capture();self.buttons();self.window.after(100,self.poll)

    def capture(self):
        if self.searching:self.message.set('Cancel or finish the current search first.');return
        d=self.desktop
        if d.settings.get('camera_id')!=self.camera_id or d.frame is None or d.optical is None or time.monotonic()-d.received_at>1:
            self.message.set('A fresh frame from this camera is required. Connect it and Refresh pair.');return
        self.frame=copy.deepcopy(d.frame);self.optical=d.optical.copy();self.base=dict(d.settings['alignment'])
        self.candidate=dict(self.base);self.verified=False;self.start=None;self.optical_region=None;self.guided_seed=None;self.guide.set(False)
        self.point_mode=False;self.point_pairs=[[],[]]
        self.thermal=thermal_image(self.frame['temperatures'],'Iron')[0]
        self.message.set(f"Frozen frame {self.frame['arrival_sequence']}. "+('Target selected; preview auto-alignment.' if self.target_selected else 'Draw a target box on the LEFT first.'))
        self.buttons();self.draw()

    def use_current_selection(self):
        if self.searching:return
        selection=selected_region(self.desktop)
        if selection is not None and (not self.target_selected or selection!=self.region):
            self.region=selection;self.target_selected=True;self.capture()

    def buttons(self):
        ready=bool(self.frame is not None and not self.searching)
        self.auto_button.configure(state='normal' if ready and self.target_selected else 'disabled')
        self.point_preview.configure(state='normal' if ready and len(self.point_pairs[0])==len(self.point_pairs[1])>=3 else 'disabled')
        for b in (self.apply_button,self.save_button):b.configure(state='normal' if ready and self.verified else 'disabled')

    def draw(self):
        if self.closed or self.frame is None:return
        optical=aligned_optical(self.optical,self.candidate)
        raw=self.guide.get() or self.point_mode
        pictures=[self.thermal,self.optical if raw else optical if self.preview_mode.get()=='Optical' else Image.blend(optical,self.thermal,.5)]
        self.photos=[];self.bounds=[];self.view_regions=[]
        for index,(canvas,picture) in enumerate(zip(self.canvases,pictures)):
            crop=[0,0,1,1]
            if self.zoom_target.get() and self.target_selected:
                crop=list(self.region)
                if index==1 and raw:
                    import numpy as np
                    from .imaging import alignment_matrix
                    corners=np.array([[x*256,y*192,1] for x in (crop[0],crop[2]) for y in (crop[1],crop[3])])@np.linalg.inv(alignment_matrix(self.base)).T
                    crop=[corners[:,0].min()/256,corners[:,1].min()/192,corners[:,0].max()/256,corners[:,1].max()/192]
                mx=(crop[2]-crop[0])*.45;my=(crop[3]-crop[1])*.45
                crop=[max(0,crop[0]-mx),max(0,crop[1]-my),min(1,crop[2]+mx),min(1,crop[3]+my)]
                if crop[2]-crop[0]<.02 or crop[3]-crop[1]<.02:crop=[0,0,1,1]
            if self.start is not None:crop=self.drag_view_regions[index]
            pixels=[int(crop[0]*1024),int(crop[1]*768),int(crop[2]*1024),int(crop[3]*768)]
            crop=[pixels[0]/1024,pixels[1]/768,pixels[2]/1024,pixels[3]/768];self.view_regions.append(crop)
            picture=picture.crop(pixels)
            canvas.delete('all');w,h=canvas.winfo_width(),canvas.winfo_height();scale=max(.01,min(w/picture.width,h/picture.height))
            pw,ph=max(1,int(picture.width*scale)),max(1,int(picture.height*scale));left,top=(w-pw)/2,(h-ph)/2
            photo=ImageTk.PhotoImage(rotate_image(picture,180).resize((pw,ph),Image.Resampling.BILINEAR));self.photos.append(photo)
            canvas.create_image(left,top,image=photo,anchor='nw');self.bounds.append((left,top,pw,ph))
            def project(x,y):return left+(crop[2]-x)/(crop[2]-crop[0])*pw,top+(crop[3]-y)/(crop[3]-crop[1])*ph
            selected=self.optical_region if index==1 and raw else self.region
            if selected and (self.target_selected or self.start is not None):
                x,y,x2,y2=selected;canvas.create_rectangle(*project(x2,y2),*project(x,y),outline='#67ffe0',width=2)
            if self.point_mode:
                for n,(x,y) in enumerate(self.point_pairs[index]):
                    px,py=project(x,y);canvas.create_oval(px-4,py-4,px+4,py+4,outline='#67ffe0',width=2)
                    canvas.create_text(px+8,py-8,text=str(n+1),fill='#67ffe0')
            if index==1 and raw:canvas.create_text(12,12,anchor='nw',text='RAW OPTICAL · click matching features' if self.point_mode else 'RAW OPTICAL · box the SAME target',fill='#67ffe0')

    def point(self,e,optical=False):
        left,top,w,h=self.bounds[int(optical)]
        x,y,x2,y2=self.view_regions[int(optical)]
        return (x+max(0,min(1,1-(e.x-left)/w))*(x2-x),y+max(0,min(1,1-(e.y-top)/h))*(y2-y))

    def box_mode(self):
        if self.searching:return
        self.point_mode=False;self.point_pairs=[[],[]];self.buttons();self.draw()

    def start_points(self):
        if self.searching or self.frame is None:return
        if not self.target_selected:
            self.message.set('Select the subject on the LEFT first.');return
        self.point_mode=True;self.point_pairs=[[],[]];self.start=None;self.verified=False
        self.guide.set(False);self.zoom_target.set(True);self.guided_seed=None
        self.message.set('Click feature 1 on the LEFT, then the SAME feature on the RIGHT. Match at least 3 points spread across this subject (for example both eyes and nose).')
        self.buttons();self.draw()

    def add_point(self,e,optical=False):
        if self.searching:return
        side=int(optical);left,top,w,h=self.bounds[side]
        if not (left<=e.x<left+w and top<=e.y<top+h):return
        expected=0 if len(self.point_pairs[0])==len(self.point_pairs[1]) else 1
        if side!=expected:
            self.message.set('Click the matching feature on the '+('LEFT.' if expected==0 else 'RIGHT.'));return
        if len(self.point_pairs[side])>=8:return
        point=self.point(e,optical)
        if not optical and not (self.region[0]<=point[0]<=self.region[2] and self.region[1]<=point[1]<=self.region[3]):
            self.message.set('Choose features inside the selected subject rectangle.');return
        self.point_pairs[side].append(point);self.verified=False
        count=len(self.point_pairs[1])
        self.message.set(f'{count} matched pairs. '+('Click the same feature on the RIGHT.' if side==0 else 'Add another LEFT/RIGHT pair, or Preview point fit after at least 3 pairs.'))
        self.buttons();self.draw()

    def undo_point(self):
        if self.searching or not self.point_pairs[0]:return
        side=1 if len(self.point_pairs[0])==len(self.point_pairs[1]) else 0
        self.point_pairs[side].pop();self.point_mode=True;self.verified=False;self.guide.set(False)
        self.message.set('Last point removed. Continue matching LEFT then RIGHT.');self.buttons();self.draw()

    def preview_points(self):
        if self.searching:return
        try:
            result=alignment_from_points(*self.point_pairs)
            self.candidate=result['alignment'];self.guided_seed=dict(self.candidate)
            self.point_mode=False;self.guide.set(False);self.verified=True
            self.message.set(f"Shared-point preview: RMS {result['rms_pixels']:.2f} thermal pixels at your points. Inspect the selected subject, then Apply to live. No distance setting needed.")
        except ValueError as exc:self.verified=False;self.message.set(str(exc))
        self.buttons();self.draw()

    def press(self,e,optical=False):
        if getattr(self,'point_mode',False):self.add_point(e,optical);return
        if self.searching or self.frame is None or (optical and not self.guide.get()):return
        if optical and not self.target_selected:
            self.message.set('Draw the target box on the LEFT thermal image first.');return
        self.drag_view_regions=copy.deepcopy(self.view_regions)
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
                self.target_selected=True;self.guided_seed=None;self.optical_region=None;self.point_pairs=[[],[]]
                self.message.set('Target selected. Preview auto-alignment, inspect the result, then Apply to live.')
        except ValueError as exc:
            if optical:self.optical_region=self.old_region
            else:self.region=self.old_region
            self.message.set(str(exc))
        self.buttons();self.draw()

    def auto(self):
        if self.searching or self.frame is None or not self.target_selected:return
        # Explicit correspondences take priority over an unconstrained image
        # search. Do not let refinement drift away from the chosen features.
        if len(self.point_pairs[0])>=3:
            self.preview_points();return
        self.point_mode=False;self.point_pairs=[[],[]];self.guide.set(False);self.draw()
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
                self.verified=result['reliable']
                self.candidate=result['alignment'] if self.verified else dict(self.guided_seed or self.base)
                self.draw()
                if self.verified:
                    a=self.candidate
                    self.message.set(f"Preview ready ({result.get('method','texture')}). X {a['dx']:.1f}, Y {a['dy']:.1f}, scale {a['scale']:.3f}, rotation {a['angle']:.1f}°. Check the SELECTED target, then Apply to live.")
                else:
                    self.guide.set(True);self.draw()
                    self.message.set('Automatic match is ambiguous. Use Match shared points for precise feature guidance, or box the same target on the RIGHT for a rough estimate. Live alignment is unchanged.')
                if not result['reliable'] and self.guided_seed:
                    self.candidate=dict(self.guided_seed);self.verified=True;self.draw()
                    self.guide.set(False);self.draw()
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
            self.target_selected=True
            self.point_mode=False;self.point_pairs=[[],[]]
            self.guided_seed=None;self.optical_region=None;self.guide.set(False)
            self.candidate=dict(p['alignment']);self.region=list(p['region']);self.name.set(p['name']);self.distance.set('' if p['distance_m'] is None else str(p['distance_m']))
            self.verified=True;self.buttons();self.draw();self.message.set('Saved profile preview. Check the target and distance before applying.')

    def predict(self):
        if self.searching or self.frame is None:return
        try:
            self.candidate=at_distance(self.profiles,self.distance.get())
            self.point_mode=False;self.point_pairs=[[],[]]
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
