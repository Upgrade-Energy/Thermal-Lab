"""Offline thermal recording player; never opens a camera."""
import argparse
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

from PIL import Image,ImageTk

from .playback import Recording,export_history
from .imaging import thermal_image,rotate_image,sensor_to_view,view_to_sensor


class Review:
    def __init__(self,root,args):
        self.root=root;self.args=args;self.recording=None;self.frame=None;self.index=0
        self.series={};self.keys=[];self.playing=False;self.cancel=threading.Event()
        self.messages=queue.Queue();self.generation=0;self.position=None;self.photo=None
        root.title('Thermal Lab · Recording review');root.geometry('1280x900');root.minsize(1000,750)
        root.configure(bg='#111923');root.protocol('WM_DELETE_WINDOW',self.close)
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',background='#172331',foreground='#e3ebf5',fieldbackground='#233448',font=('Segoe UI',10))
        style.configure('TButton',padding=(10,7));style.configure('Treeview',rowheight=27,background='#172331',fieldbackground='#172331',foreground='#e3ebf5')
        style.map('TButton',background=[('active','#345575'),('pressed','#345575')],foreground=[('active','#ffffff')])
        style.map('TCombobox',fieldbackground=[('readonly','#233448')],foreground=[('readonly','#e3ebf5')])
        self.status=tk.StringVar(value='Open a finalized recording folder to begin')
        self.info=tk.StringVar(value='OFFLINE · numerical thermal playback · no camera connection')
        self.palette=tk.StringVar(value='Iron');self.rotation=tk.StringVar(value='180')
        self.speed=tk.StringVar(value='1');self.position_var=tk.DoubleVar();self.selected=tk.StringVar()
        top=ttk.Frame(root,padding=12);top.pack(fill='x')
        ttk.Label(top,text='THERMAL LAB  /  RECORDING REVIEW',font=('Segoe UI',15,'bold')).pack(side='left')
        ttk.Button(top,text='Open recording…',command=self.browse).pack(side='right')
        self.export=ttk.Button(top,text='Export history…',command=self.export_csv,state='disabled');self.export.pack(side='right',padx=8)
        ttk.Label(root,textvariable=self.status,padding=(12,4),wraplength=1200).pack(fill='x')
        controls=ttk.Frame(root,padding=8);controls.pack(fill='x')
        self.play_button=ttk.Button(controls,text='Play',command=self.play,state='disabled');self.play_button.pack(side='left')
        ttk.Button(controls,text='Previous',command=lambda:self.step(-1)).pack(side='left',padx=4)
        ttk.Button(controls,text='Next',command=lambda:self.step(1)).pack(side='left')
        for label,var,values in [('Speed',self.speed,['0.25','0.5','1','2','4']),('Palette',self.palette,['Iron','Rainbow','White hot','Black hot']),('Rotation',self.rotation,['0','90','180','270'])]:
            ttk.Label(controls,text=label).pack(side='left',padx=(15,4))
            box=ttk.Combobox(controls,textvariable=var,values=values,width=10,state='readonly');box.pack(side='left')
            box.bind('<<ComboboxSelected>>',lambda e:self.view_changed())
        body=ttk.Frame(root,padding=(12,4));body.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(body,bg='#0b1119',highlightthickness=0);self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.render());self.canvas.bind('<Motion>',self.hover)
        side=ttk.Frame(body,padding=(12,0,0,0));side.pack(side='right',fill='y')
        ttk.Label(side,text='RECORDED MEASUREMENTS · °C').pack(anchor='w')
        self.table=ttk.Treeview(side,columns=('name','value'),show='headings',height=7)
        self.table.heading('name',text='Name');self.table.heading('value',text='Value / min · mean · max')
        self.table.column('name',width=110);self.table.column('value',width=180);self.table.pack(fill='both',expand=True,pady=8)
        ttk.Label(side,text='Thermal frames only. This archive does not contain continuous optical video.\n\nMeasurements and geometry follow the original recording.',wraplength=290,foreground='#aac0d3').pack(anchor='w',pady=8)
        self.timeline=ttk.Scale(root,variable=self.position_var,from_=0,to=1,command=self.seek);self.timeline.pack(fill='x',padx=12,pady=4)
        ttk.Label(root,textvariable=self.info,padding=(12,3)).pack(fill='x')
        row=ttk.Frame(root,padding=(12,3));row.pack(fill='x')
        ttk.Label(row,text='TEMPERATURE HISTORY · °C').pack(side='left')
        self.series_box=ttk.Combobox(row,textvariable=self.selected,state='readonly',width=55);self.series_box.pack(side='left',padx=15)
        self.series_box.bind('<<ComboboxSelected>>',lambda e:self.plot())
        ttk.Label(row,text='Click graph to seek · gaps mark missing or moved measurements').pack(side='left')
        self.graph=tk.Canvas(root,bg='#0b1119',height=220,highlightthickness=0);self.graph.pack(fill='x',padx=12,pady=(4,12))
        self.graph.bind('<Configure>',lambda e:self.plot());self.graph.bind('<Button-1>',self.graph_seek)
        root.after(40,self.tick)
        if args.session:root.after(100,lambda:self.open(args.session))

    def browse(self):
        path=filedialog.askdirectory(title='Select a finalized thermal recording folder',initialdir=self.args.recordings)
        if path:self.open(path)

    def open(self,path):
        self.pause();self.cancel.set();self.cancel=threading.Event();self.generation+=1
        self.recording=None;self.frame=None;self.series={};self.keys=[];self.position=None
        self.history_ready=False
        for item in self.table.get_children():self.table.delete(item)
        self.info.set('OFFLINE · no frame selected')
        self.series_box.configure(values=[]);self.selected.set('');self.export.configure(state='disabled');self.play_button.configure(state='disabled')
        self.render();self.plot()
        try:
            recording=Recording(path);self.recording=recording
            self.timeline.configure(to=max(1,len(recording.entries)-1));self.show(0)
            self.play_button.configure(state='normal');self.root.title('Thermal Lab · Review · '+recording.path.name)
            self.status.set(f"{recording.path.name} · {recording.manifest['camera_id']} · {recording.manifest['source']} · Loading histories…")
            generation=self.generation;cancel=self.cancel
            def scan():
                try:
                    series=recording.histories(lambda n,total:self.messages.put((generation,'progress',(n,total))),cancel.is_set)
                    if series is not None:self.messages.put((generation,'history',series))
                except Exception as exc:self.messages.put((generation,'error',str(exc)))
            threading.Thread(target=scan,daemon=True,name='Recording histories').start()
        except Exception as exc:
            self.recording=None;self.status.set('Cannot open recording: '+str(exc))

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
        rotation=int(self.rotation.get());picture=rotate_image(picture,rotation)
        width,height=(192,256) if rotation in (90,270) else (256,192)
        cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
        scale=max(.01,min((cw-20)/width,(ch-35)/height));x=(cw-width*scale)/2;y=20+(ch-25-height*scale)/2
        self.position=(x,y,scale,width,height)
        picture=picture.resize((max(1,int(width*scale)),max(1,int(height*scale))),Image.Resampling.NEAREST)
        self.photo=ImageTk.PhotoImage(picture);self.canvas.create_image(x,y,image=self.photo,anchor='nw')
        self.canvas.create_text(10,10,text=f'{limits[0]:.1f} → {limits[1]:.1f} °C · recorded thermal',fill='white',anchor='w')
        for kind in ('points','areas'):
            for item in self.frame.get('workspace',{}).get(kind,[]):
                px,py=sensor_to_view(item['x']*256,item['y']*192,rotation);px=x+px*scale;py=y+py*scale
                if 'x2' in item:
                    qx,qy=sensor_to_view(item['x2']*256,item['y2']*192,rotation)
                    self.canvas.create_rectangle(px,py,x+qx*scale,y+qy*scale,outline='#67ffe0',width=2)
                else:self.canvas.create_oval(px-4,py-4,px+4,py+4,outline='#67ffe0',width=2)
                self.canvas.create_text(px+6,py-6,text=item['name'],fill='#67ffe0',anchor='sw')

    def hover(self,event):
        if not self.frame or not self.position:return
        x,y,scale,width,height=self.position;vx=(event.x-x)/scale;vy=(event.y-y)/scale
        if 0<=vx<width and 0<=vy<height:
            sx,sy=view_to_sensor(vx,vy,int(self.rotation.get()));sx=min(255,max(0,int(sx)));sy=min(191,max(0,int(sy)))
            self.info.set(f"Frame {self.index+1} · {self.frame['elapsed_s']:.3f} s · recorded pixel ({sx}, {sy}): {self.frame['temperatures'][sy*256+sx]:.3f} °C apparent")

    def rows(self):
        for item in self.table.get_children():self.table.delete(item)
        names={v['id']:v['name'] for kind in ('points','areas') for v in self.frame.get('workspace',{}).get(kind,[])}
        for key,value in self.frame.get('measurements',{}).items():
            text=f"{value['value']:.3f}" if 'value' in value else ' · '.join(f'{value[k]:.2f}' for k in ('min','mean','max'))
            self.table.insert('','end',values=(names.get(key,key),text))

    def plot(self):
        self.graph.delete('all');w,h=self.graph.winfo_width(),self.graph.winfo_height()
        selection=self.series_box.current()
        if not self.recording or not 0<=selection<len(self.keys):
            text='No recorded points or regions in this session' if getattr(self,'history_ready',False) else 'History appears after all frames have been checked'
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
            try:export_history(path,self.recording,self.series);self.status.set('History exported: '+path)
            except Exception as exc:messagebox.showerror('Export failed',str(exc))

    def tick(self):
        try:
            while True:
                generation,kind,data=self.messages.get_nowait()
                if generation!=self.generation:continue
                if kind=='progress':self.status.set(f'Checking recorded measurements: {data[0]:,} / {data[1]:,} frames')
                elif kind=='history':
                    self.history_ready=True
                    self.series=data;self.keys=list(data)
                    labels=[f"{data[key]['name']} · {key[1]} · {key[0][:12]}" for key in self.keys]
                    self.series_box.configure(values=labels)
                    if labels:self.series_box.current(0);self.export.configure(state='normal')
                    self.plot();self.status.set(f"{self.recording.path.name} · {self.recording.manifest['camera_id']} · {self.recording.manifest['source']} · History checked · apparent temperatures")
                elif kind=='error':self.status.set('History unavailable: '+data)
        except queue.Empty:pass
        if self.playing and self.recording:
            elapsed=self.anchor_time+(time.monotonic()-self.anchor_clock)*float(self.speed.get())
            index=self.recording.index_at(elapsed)
            if index!=self.index:self.show(index)
            if elapsed>=self.recording.times[-1]:self.pause()
        self.root.after(40,self.tick)

    def close(self):
        self.cancel.set();self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path)
    parser.add_argument('--recordings',type=Path,default=Path.home()/'Thermal-Lab-Recordings')
    args=parser.parse_args();root=tk.Tk();Review(root,args);root.mainloop()


if __name__=='__main__':main()
