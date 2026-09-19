"""Shared native design system: quiet slate surfaces, rounded actions and line icons."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

BG='#101c30'
SURFACE='#192b45'
RAISED='#223955'
TEXT='#eef3fb'
MUTED='#a9bbd2'
ACCENT='#568cf5'
BORDER='#344d6b'
CANVAS='#0c1626'


def install(root):
    root.configure(bg=BG)
    style=ttk.Style(root)
    if 'thermal' in style.theme_names():
        style.theme_use('thermal');return
    style.theme_create('thermal',parent='clam');style.theme_use('thermal')
    # Images belong to the Tcl interpreter for the life of the application.
    root._theme_images=[]
    app_icon=Image.new('RGBA',(64,64),BG);pen=ImageDraw.Draw(app_icon)
    pen.rounded_rectangle((3,3,61,61),radius=15,fill='#3d6dce')
    pen.rounded_rectangle((12,21,52,49),radius=6,outline=TEXT,width=3)
    pen.ellipse((24,26,42,44),outline=TEXT,width=3);pen.line((21,21,25,15,41,15,45,21),fill=TEXT,width=3)
    root._app_icon=ImageTk.PhotoImage(app_icon,master=root);root.iconphoto(True,root._app_icon)
    def rounded(name,fill,outline):
        im=Image.new('RGBA',(192,90))
        d=ImageDraw.Draw(im);d.rounded_rectangle((2,2,189,87),radius=27,fill=fill,outline=outline,width=3)
        photo=ImageTk.PhotoImage(im.resize((64,30),Image.Resampling.LANCZOS),master=root);root._theme_images.append(photo)
        return photo
    def button_style(name,normal,hover,pressed,text=TEXT):
        images=[rounded(name+str(i),c,BORDER if i==0 else c) for i,c in enumerate((normal,hover,pressed))]
        disabled=rounded(name+'disabled',SURFACE,BORDER)
        focus=rounded(name+'focus',normal,'#90bcff')
        element=name+'.surface'
        style.element_create(element,'image',images[0],('disabled',disabled),('pressed',images[2]),('selected',images[2]),('active',images[1]),('focus',focus),border=10,sticky='nsew')
        style.layout(name,[ (element,{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]}) ])
        style.configure(name,padding=(12,8),foreground=text,background=BG,font=('Segoe UI',10),borderwidth=0)
        style.map(name,foreground=[('disabled','#8396ae')])
    style.configure('.',background=BG,foreground=TEXT,fieldbackground=SURFACE,font=('Segoe UI',10),bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER)
    style.configure('TFrame',background=BG)
    style.configure('TLabel',background=BG,foreground=TEXT)
    style.configure('Title.TLabel',font=('Segoe UI',20,'bold'))
    style.configure('Heading.TLabel',font=('Segoe UI',12,'bold'))
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Hot.TLabel',foreground='#ffb389',font=('Segoe UI',17,'bold'))
    style.configure('Cold.TLabel',foreground='#81d7ff',font=('Segoe UI',17,'bold'))
    for name,colors in [('TButton',(RAISED,'#304b6e','#3c6088')),('Primary.TButton',('#3d6dce','#4e82e8','#315cba')),('Danger.TButton',('#593543','#704052','#482c38'))]:
        button_style(name,*colors)
    style.layout('TMenubutton',style.layout('TButton'))
    style.configure('TMenubutton',padding=(14,9))
    style.configure('TEntry',padding=7,insertcolor=TEXT,fieldbackground=SURFACE,selectbackground=ACCENT)
    style.configure('TSpinbox',padding=6,arrowsize=15,fieldbackground=SURFACE,arrowcolor=MUTED)
    style.configure('TCombobox',padding=6,arrowsize=16,fieldbackground=SURFACE,arrowcolor=MUTED)
    style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],foreground=[('readonly',TEXT),('disabled','#70839b')])
    style.configure('TNotebook',background=BG,borderwidth=0,tabmargins=(0,0,0,12))
    style.configure('TNotebook.Tab',padding=(16,10),background=SURFACE,foreground=MUTED)
    style.map('TNotebook.Tab',background=[('selected',RAISED)],foreground=[('selected',TEXT)])
    style.configure('TCheckbutton',padding=(2,5),indicatorbackground=SURFACE,indicatorforeground=ACCENT)
    checks=[]
    for selected in (False,True):
        im=Image.new('RGBA',(48,48));d=ImageDraw.Draw(im)
        d.rounded_rectangle((3,3,45,45),radius=10,fill=ACCENT if selected else SURFACE,outline=ACCENT if selected else MUTED,width=3)
        if selected:d.line((12,24,21,33,36,15),fill=TEXT,width=5,joint='curve')
        checks.append(ImageTk.PhotoImage(im.resize((16,16),Image.Resampling.LANCZOS),master=root))
    root._theme_images.extend(checks)
    style.element_create('SoftCheck.indicator','image',checks[0],('selected',checks[1]),width=23,sticky='w')
    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nswe','children':[('SoftCheck.indicator',{'side':'left','sticky':''}),('Checkbutton.label',{'side':'left','sticky':'nswe'})]})])
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',TEXT)])
    style.configure('TRadiobutton',padding=(8,7),indicatorbackground=SURFACE,indicatorforeground=ACCENT)
    style.map('TRadiobutton',background=[('active',RAISED)],foreground=[('active',TEXT)])
    style.layout('Tool.TRadiobutton',style.layout('TButton'))
    style.configure('Tool.TRadiobutton',padding=(10,8))
    style.map('Tool.TRadiobutton',foreground=[('selected','#87c6ff'),('active',TEXT)])
    style.configure('Horizontal.TScale',troughcolor=SURFACE,background=ACCENT,sliderlength=18,sliderrelief='flat',borderwidth=0)
    knob=Image.new('RGBA',(60,60));d=ImageDraw.Draw(knob);d.ellipse((6,6,54,54),fill='#8db7ff',outline=TEXT,width=3)
    knob=ImageTk.PhotoImage(knob.resize((20,20),Image.Resampling.LANCZOS),master=root);root._theme_images.append(knob)
    style.element_create('SoftScale.slider','image',knob,border=0)
    style.layout('Horizontal.TScale',[('Horizontal.Scale.trough',{'sticky':'we','children':[('SoftScale.slider',{'side':'left','sticky':''})]})])
    style.configure('Treeview',rowheight=34,background=SURFACE,fieldbackground=SURFACE,borderwidth=0,foreground=TEXT)
    style.configure('Treeview.Heading',background=RAISED,foreground=MUTED,padding=(8,9),relief='flat',font=('Segoe UI',9,'bold'))
    style.map('Treeview',background=[('selected','#345883')],foreground=[('selected',TEXT)])
    style.configure('TSeparator',background=BORDER)
    style.configure('Vertical.TScrollbar',background=RAISED,troughcolor=BG,arrowcolor=MUTED,borderwidth=0)
    root.option_add('*TCombobox*Listbox.background',SURFACE)
    root.option_add('*TCombobox*Listbox.foreground',TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground','#345883')
    root.option_add('*TCombobox*Listbox.font',('Segoe UI',10))


class ScrollPanel(ttk.Frame):
    """Inspector content remains reachable on shorter Windows displays."""
    def __init__(self,parent):
        super().__init__(parent)
        self.canvas=tk.Canvas(self,bg=BG,highlightthickness=0,width=400)
        bar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.content=ttk.Frame(self.canvas,padding=(4,6,10,8))
        item=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(item,width=e.width))
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.bind('<Enter>',self._bind_wheel)
    def _bind_wheel(self,_):
        def walk(w):
            if not getattr(w,'_scroll_wheel_bound',False):
                w.bind('<MouseWheel>',self._wheel);w._scroll_wheel_bound=True
            for child in w.winfo_children():walk(child)
        walk(self.content);self.canvas.bind('<MouseWheel>',self._wheel)
    def _wheel(self,event):
        if self.content.winfo_height()>self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta/120),'units')
        return 'break'


def menu(parent):
    return tk.Menu(parent,tearoff=False,bg=SURFACE,fg=TEXT,activebackground='#345883',activeforeground=TEXT,
                   relief='flat',borderwidth=1,font=('Segoe UI',10))


def icon(widget,name,color=TEXT):
    """Small consistent outline symbols; do not depend on an emoji font."""
    im=Image.new('RGBA',(72,72));d=ImageDraw.Draw(im);c=color
    def line(points):d.line(points,fill=c,width=5,joint='curve')
    if name=='point':
        d.ellipse((20,20,52,52),outline=c,width=5);line((36,7,36,22));line((36,50,36,65));line((7,36,22,36));line((50,36,65,36))
    elif name=='area':d.rounded_rectangle((12,14,60,58),radius=5,outline=c,width=5)
    elif name=='polygon':
        points=[(14,19),(48,10),(61,39),(34,60),(10,46)]
        d.line(points+[points[0]],fill=c,width=5,joint='curve')
        for x,y in points:d.ellipse((x-4,y-4,x+4,y+4),fill=c)
    elif name=='select':line((18,9,18,57,31,44,42,62,51,57,39,38,57,35,18,9))
    elif name=='pan':
        line((36,7,36,65));line((7,36,65,36))
        for pts in [(25,18,36,7,47,18),(25,54,36,65,47,54),(18,25,7,36,18,47),(54,25,65,36,54,47)]:line(pts)
    elif name=='align':
        d.rounded_rectangle((7,10,45,48),radius=5,outline=c,width=5);d.rounded_rectangle((27,28,65,66),radius=5,outline=c,width=5)
    elif name=='camera':
        d.rounded_rectangle((7,20,65,60),radius=8,outline=c,width=5);d.ellipse((25,28,47,50),outline=c,width=5);line((22,20,27,11,47,11,52,20))
    elif name=='record':d.ellipse((16,16,56,56),fill=c)
    elif name=='folder':line((8,58,8,16,28,16,35,24,64,24,60,58,8,58))
    elif name=='refresh':
        d.arc((13,13,59,59),35,310,fill=c,width=5);line((48,9,61,14,57,29))
    else:line((16,36,56,36))
    photo=ImageTk.PhotoImage(im.resize((18,18),Image.Resampling.LANCZOS),master=widget)
    widget._line_icon=photo
    widget.configure(image=photo,compound='left')


def polish(window):
    """Keep secondary dialogs on the same typography, contrast and action styles."""
    window.configure(bg=BG)
    primary={'Apply to live','Preview auto-alignment','Preview point fit','Open recording…','Analyze one pair'}
    def walk(w):
        for child in w.winfo_children():
            if isinstance(child,ttk.Button):
                text=str(child.cget('text'))
                if text in primary:child.configure(style='Primary.TButton')
                symbol=next((v for k,v in [('Refresh','refresh'),('Open recording','folder'),('Save PNG','camera'),('Match shared','point')] if text.startswith(k)),None)
                if symbol:icon(child,symbol)
            if isinstance(child,ttk.Label) and str(child.cget('foreground')) in ('#9aafc3','#aac0d3','#8ba4be'):
                child.configure(foreground=MUTED)
            walk(child)
    walk(window)
