"""Playback workspace with a reserved timeline and grouped analysis/export tools."""
import tkinter as tk
from tkinter import ttk
from . import ui_theme as ui
from .polygon_tool import PolygonTool
from .tracking_ui import build as tracking_controls


def build(a):
    root=a.root
    top=ttk.Frame(root,padding=(20,14));top.pack(fill='x')
    brand=ttk.Frame(top);brand.pack(side='left')
    ttk.Label(brand,text='Recording review',style='Title.TLabel').pack(anchor='w')
    ttk.Label(brand,text='Thermal Lab  /  Offline analysis',style='Muted.TLabel').pack(anchor='w')
    open_button=ttk.Button(top,text='Open recording…',style='Primary.TButton',command=a.browse);open_button.pack(side='right');ui.icon(open_button,'folder')
    ttk.Label(root,textvariable=a.status,padding=(20,4),wraplength=1100,style='Muted.TLabel').pack(fill='x')
    controls=ttk.Frame(root,padding=(20,8));controls.pack(fill='x')
    a.play_button=ttk.Button(controls,text='Play',style='Primary.TButton',command=a.play,state='disabled');a.play_button.pack(side='left')
    ttk.Button(controls,text='Previous',command=lambda:a.step(-1)).pack(side='left',padx=6)
    ttk.Button(controls,text='Next',command=lambda:a.step(1)).pack(side='left')
    for label,var,values,width in [('Speed',a.speed,['0.25','0.5','1','2','4'],4),('Palette',a.palette,['Iron','Rainbow','White hot','Black hot'],10),('Rotate',a.rotation,['0','90','180','270'],4)]:
        ttk.Label(controls,text=label,style='Muted.TLabel').pack(side='left',padx=(16,6))
        box=ttk.Combobox(controls,textvariable=var,values=values,width=width,state='readonly');box.pack(side='left')
        box.bind('<<ComboboxSelected>>',lambda e:a.view_changed())
    a.mode_box=ttk.Combobox(controls,textvariable=a.mode,values=['Thermal'],state='readonly',width=10)
    a.mode_box.pack(side='right');a.mode_box.bind('<<ComboboxSelected>>',lambda e:a.show(a.index))
    # Pack footer first so playback never consumes the history graph's space.
    footer=ttk.Frame(root,padding=(20,0,20,12));footer.pack(side='bottom',fill='x')
    a.timeline=ttk.Scale(footer,variable=a.position_var,from_=0,to=1,command=a.seek);a.timeline.pack(fill='x',pady=6)
    ttk.Label(footer,textvariable=a.info,style='Muted.TLabel',wraplength=1120).pack(fill='x',pady=(0,6))
    row=ttk.Frame(footer);row.pack(fill='x',pady=5)
    ttk.Label(row,text='Temperature history',style='Heading.TLabel').pack(side='left')
    a.series_box=ttk.Combobox(row,textvariable=a.selected,state='readonly',width=34);a.series_box.pack(side='left',padx=15)
    a.series_box.bind('<<ComboboxSelected>>',lambda e:a.plot())
    ttk.Label(row,text='Click the graph to seek',style='Muted.TLabel').pack(side='left')
    a.graph=tk.Canvas(footer,bg=ui.CANVAS,height=125,highlightthickness=0);a.graph.pack(fill='x',pady=(4,0))
    a.graph.bind('<Configure>',lambda e:a.plot());a.graph.bind('<Button-1>',a.graph_seek)
    body=ttk.Frame(root,padding=(20,4));body.pack(fill='both',expand=True)
    side=ttk.Frame(body,width=380,padding=(16,0,0,0));side.pack(side='right',fill='y');side.pack_propagate(False)
    a.canvas=tk.Canvas(body,bg=ui.CANVAS,highlightthickness=0);a.canvas.pack(side='left',fill='both',expand=True)
    for event,command in [('<Configure>',lambda e:a.render()),('<Motion>',a.hover),('<ButtonPress-1>',a.press),('<B1-Motion>',a.motion),('<ButtonRelease-1>',a.release)]:a.canvas.bind(event,command)
    tabs=ttk.Notebook(side);tabs.pack(fill='both',expand=True)
    measures_page=ui.ScrollPanel(tabs);exports_page=ui.ScrollPanel(tabs)
    tabs.add(measures_page,text='Measurements');tabs.add(exports_page,text='Export')
    measures=measures_page.content;exports=exports_page.content
    ttk.Checkbutton(measures,text='Show hot / cold markers',variable=a.show_extrema,command=a.render).pack(anchor='w')
    row=ttk.Frame(measures);row.pack(fill='x',pady=8)
    ttk.Label(row,text='Layout',style='Muted.TLabel').pack(side='left')
    basis=ttk.Combobox(row,textvariable=a.basis,values=['Recorded','Analysis'],state='readonly',width=14);basis.pack(side='right');basis.bind('<<ComboboxSelected>>',lambda e:a.change_basis())
    a.analysis_note=tk.StringVar(value='Recorded measurements · select Analysis to add or move points and regions')
    ttk.Label(measures,textvariable=a.analysis_note,wraplength=315,style='Muted.TLabel').pack(anchor='w',pady=6)
    a.tracking_panel=ttk.Frame(measures)
    tracking_controls(a.tracking_panel,a,review=True)
    row=ttk.Frame(measures);a.edit_tools=row
    for i,(name,symbol) in enumerate([('Select','select'),('Point','point'),('Rectangle','area'),('Polygon','polygon')]):
        b=ttk.Radiobutton(row,text=name,variable=a.tool,value=name,style='Tool.TRadiobutton');b.grid(row=i//2,column=i%2,sticky='ew',padx=(0,4),pady=3);ui.icon(b,symbol)
    table_frame=ttk.Frame(measures);table_frame.pack(fill='x',pady=6);a.measurement_table_frame=table_frame
    a.polygon=PolygonTool(a.canvas,measures,table_frame,a.tool,a.status,a.sensor,a.polygon_viewports,a.rotation,
        lambda:a.basis.get()=='Analysis' and a.analysis is not None and a.frame is not None,a.add_polygon,compact=True)
    a.table=ttk.Treeview(table_frame,columns=('name','value'),show='headings',height=4,selectmode='browse')
    a.table.heading('name',text='Name');a.table.heading('value',text='°C · pixel / region stats')
    a.table.column('name',width=100,minwidth=60);a.table.column('value',width=210,minwidth=140)
    scroll=ttk.Scrollbar(table_frame,orient='vertical',command=a.table.yview);a.table.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');a.table.pack(side='left',fill='both',expand=True);a.table.bind('<<TreeviewSelect>>',a.select_row)
    ttk.Label(measures,text='Selected measurement',style='Muted.TLabel').pack(anchor='w',pady=(8,4))
    entry=ttk.Entry(measures,textvariable=a.edit_name);entry.pack(fill='x');entry.bind('<FocusIn>',lambda e:a.pause())
    row=ttk.Frame(measures);row.pack(fill='x',pady=8)
    ttk.Button(row,text='Rename',command=a.rename).pack(side='left');ttk.Button(row,text='Remove',command=a.remove).pack(side='right')
    row=ttk.Frame(measures);row.pack(fill='x')
    ttk.Button(row,text='Save analysis…',command=a.save_analysis).pack(side='left');ttk.Button(row,text='Load analysis…',command=a.load_analysis).pack(side='right')
    ttk.Label(exports,text='Export recording',style='Heading.TLabel').pack(anchor='w',pady=6)
    ttk.Label(exports,text='Save the current frame or export the complete recording.',wraplength=310,style='Muted.TLabel').pack(anchor='w',pady=6)
    a.png_button=ttk.Button(exports,text='Save PNG…',command=lambda:a.media_export('png'));a.png_button.pack(fill='x',pady=6);ui.icon(a.png_button,'camera')
    a.mp4_button=ttk.Button(exports,text='Export MP4…',command=lambda:a.media_export('mp4'));a.mp4_button.pack(fill='x',pady=6)
    a.export=ttk.Button(exports,text='Export history CSV…',command=a.export_csv,state='disabled');a.export.pack(fill='x',pady=6)
    ttk.Checkbutton(exports,text='Export temperature labels',variable=a.export_labels).pack(anchor='w',pady=10)
    ttk.Label(exports,textvariable=a.media_status,wraplength=310,style='Muted.TLabel').pack(anchor='w',pady=6)
    ttk.Label(exports,text='Named trackers export temperature and moving pixel coordinates to CSV. PNG / MP4 labels follow their positions. Analysis leaves original recordings unchanged.',wraplength=310,style='Muted.TLabel').pack(anchor='w',pady=6)
    ttk.Separator(exports).pack(fill='x',pady=12)
    ttk.Label(exports,textvariable=a.archive_info,wraplength=310,style='Muted.TLabel').pack(anchor='w')
