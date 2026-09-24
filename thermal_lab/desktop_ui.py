"""Live workspace layout. Capture and measurement behavior remain in Desktop."""
import tkinter as tk
from tkinter import ttk
from . import ui_theme as ui
from .polygon_tool import PolygonTool
from .tracking_ui import build as tracking_controls
from . import __version__
import time


def build(app):
    a=app;root=a.root
    a.camera_display=tk.StringVar();a.camera_name=tk.StringVar();a.camera_identity=tk.StringVar()
    a.show_extrema=tk.BooleanVar(value=True)
    a.hot_value=tk.StringVar(value='—');a.cold_value=tk.StringVar(value='—')
    header=ttk.Frame(root,padding=(22,14));header.pack(fill='x')
    brand=ttk.Frame(header);brand.pack(side='left')
    ttk.Label(brand,text='Thermal Lab',style='Title.TLabel').pack(anchor='w')
    ttk.Label(brand,text='Live inspection  /  '+__version__,style='Muted.TLabel').pack(anchor='w')
    a.connect_button=ttk.Button(header,text='Connect camera',command=a.connect);a.connect_button.pack(side='right')
    ui.icon(a.connect_button,'camera')
    a.record_button=ttk.Button(header,text='Record session',style='Primary.TButton',command=a.toggle_record,state='disabled')
    a.record_button.pack(side='right',padx=10);ui.icon(a.record_button,'record')
    a.record_clock=tk.StringVar(value=a.clock.text())
    ttk.Label(header,textvariable=a.record_clock,font=('Segoe UI',12,'bold'),foreground='#8cbcff').pack(side='right',padx=12)
    workspace=ttk.Menubutton(header,text='Workspace  ▾');workspace.pack(side='right',padx=8)
    actions=ui.menu(workspace);workspace.configure(menu=actions)
    for text,command in [('Review recordings…',a.review_recordings),('Open another camera window',a.another_camera),
                         ('Power Lab service…',a.open_service),
                         ('Save layout…',a.save),('Load layout…',a.load)]:actions.add_command(label=text,command=command)
    from lab_update import open_updates
    actions.add_separator();actions.add_command(label='Check for updates…',command=open_updates)
    actions.add_command(label='Close window',command=a.close)
    connection=ttk.Frame(root,padding=(22,0,22,10));connection.pack(fill='x')
    ttk.Label(connection,text='Camera',style='Muted.TLabel').pack(side='left',padx=(0,10))
    a.camera_box=ttk.Combobox(connection,textvariable=a.camera_display,state='readonly',width=34,postcommand=a.update_camera_choices)
    a.camera_box.pack(side='left',fill='x',expand=True)
    a.camera_box.bind('<<ComboboxSelected>>',a.choose_camera)
    a.refresh_button=ttk.Button(connection,text='Refresh',command=a.refresh_cameras);a.refresh_button.pack(side='left',padx=8);ui.icon(a.refresh_button,'refresh')
    review=ttk.Button(connection,text='Recordings',command=a.review_recordings);review.pack(side='left');ui.icon(review,'folder')
    a.csv_path=None
    a.csv_button=ttk.Button(connection,text='Show CSV',command=a.open_measurement_csv,state='disabled')
    a.csv_button.pack(side='left',padx=(8,0));ui.icon(a.csv_button,'folder')
    a.connection_info=tk.StringVar(value='Checking camera connections…')
    status=ttk.Frame(root,padding=(22,0,22,10));status.pack(fill='x')
    ttk.Label(status,textvariable=a.status,foreground='#8dd9c1',wraplength=1250).pack(anchor='w')
    body=ttk.Panedwindow(root,orient='horizontal');body.pack(fill='both',expand=True,padx=18,pady=(0,8))
    left=ttk.Frame(body);right=ttk.Frame(body,width=430,padding=(16,0,0,0));body.add(left,weight=4);body.add(right,weight=0)
    toolbar=ttk.Frame(left,padding=(0,5));toolbar.pack(fill='x')
    for title,variable,values,width in [('View',a.mode,['Thermal','Optical','Blend','Side by side'],12),
                                     ('Palette',a.palette,['Iron','Rainbow','White hot','Black hot'],10),
                                     ('Rotate',a.rotation,['0','90','180','270'],4)]:
        ttk.Label(toolbar,text=title,style='Muted.TLabel').pack(side='left',padx=(0,6))
        box=ttk.Combobox(toolbar,textvariable=variable,values=values,width=width,state='readonly')
        box.pack(side='left',padx=(0,12));box.bind('<<ComboboxSelected>>',lambda e:a.render())
    ttk.Button(toolbar,text='Fit',command=a.fit).pack(side='right')
    tools=ttk.Frame(left,padding=(0,6));tools.pack(fill='x')
    for text,symbol in [('Select','select'),('Point','point'),('Rectangle','area'),('Polygon','polygon'),('Align optical','align'),('Pan','pan')]:
        button=ttk.Radiobutton(tools,text=text,variable=a.tool,value=text,style='Tool.TRadiobutton')
        button.pack(side='left',padx=(0,5));ui.icon(button,symbol)
    a.canvas=tk.Canvas(left,bg=ui.CANVAS,highlightthickness=0,cursor='crosshair');a.canvas.pack(fill='both',expand=True)
    a.polygon=PolygonTool(a.canvas,left,a.canvas,a.tool,a.status,
        lambda e:tuple(v/d for v,d in zip(a.locate(e),(256,192))) if a.locate(e) is not None else None,
        lambda:a.viewports,a.rotation,lambda:a.frame is not None and time.monotonic()-a.received_at<=1,a.add_polygon)
    for event,action in [('<Configure>',lambda e:a.render()),('<ButtonPress-1>',a.press),('<B1-Motion>',a.motion),
                         ('<ButtonRelease-1>',a.release),('<Motion>',a.hover),('<MouseWheel>',a.wheel)]:a.canvas.bind(event,action)
    ttk.Label(left,textvariable=a.cursor,style='Muted.TLabel',padding=(4,8)).pack(fill='x')
    a.inspector=ttk.Notebook(right);a.inspector.pack(fill='both',expand=True)
    pages=[ui.ScrollPanel(a.inspector) for _ in range(3)]
    for frame,title in zip(pages,['Measure','Alignment','Camera']):a.inspector.add(frame,text=title)
    measures,alignment,camera=[p.content for p in pages]
    ttk.Label(measures,text='Temperature extremes',style='Heading.TLabel').pack(anchor='w')
    ttk.Label(measures,text='Hottest and coldest pixels in the full frame',style='Muted.TLabel').pack(anchor='w',pady=(4,10))
    extremes=ttk.Frame(measures);extremes.pack(fill='x')
    for title,var,style in [('HOTTEST',a.hot_value,'Hot.TLabel'),('COLDEST',a.cold_value,'Cold.TLabel')]:
        frame=ttk.Frame(extremes);frame.pack(side='left',fill='x',expand=True)
        ttk.Label(frame,text=title,style='Muted.TLabel',font=('Segoe UI',9,'bold')).pack(anchor='w')
        ttk.Label(frame,textvariable=var,style=style).pack(anchor='w',pady=4)
    ttk.Checkbutton(measures,text='Show hot / cold markers',variable=a.show_extrema,command=a.render).pack(anchor='w',pady=(4,10))
    ttk.Separator(measures).pack(fill='x',pady=8)
    tracking_controls(measures,a)
    ttk.Label(measures,text='Points & regions',style='Heading.TLabel').pack(anchor='w',pady=(6,8))
    ttk.Label(measures,text='All named points and regions save to CSV with Record / Stop.',wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=(0,8))
    table_frame=ttk.Frame(measures);table_frame.pack(fill='both',expand=True)
    a.table=ttk.Treeview(table_frame,columns=('name','value'),show='headings',height=5,selectmode='browse')
    a.table.heading('name',text='Name');a.table.heading('value',text='°C · pixel / region stats')
    a.table.column('name',width=135,minwidth=80);a.table.column('value',width=235,minwidth=160)
    scroll=ttk.Scrollbar(table_frame,orient='vertical',command=a.table.yview);a.table.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');a.table.pack(side='left',fill='both',expand=True);a.table.bind('<<TreeviewSelect>>',a.select_row)
    ttk.Label(measures,text='Selected measurement name',style='Muted.TLabel').pack(anchor='w',pady=(12,4))
    rename=ttk.Frame(measures);rename.pack(fill='x')
    entry=ttk.Entry(rename,textvariable=a.name,width=20);entry.pack(side='left',fill='x',expand=True);entry.bind('<Return>',lambda e:a.rename())
    ttk.Button(rename,text='Rename',command=a.rename).pack(side='right',padx=(8,0))
    row=ttk.Frame(measures);row.pack(fill='x',pady=8)
    ttk.Button(row,text='Remove selected',command=a.remove).pack(side='left')
    ttk.Button(row,text='Clear all points',command=a.clear_points).pack(side='right')
    ttk.Label(measures,text='Choose Point, Rectangle or Polygon above the image. Select to move a shape or drag its polygon corners.',wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=7)
    row=ttk.Frame(measures);row.pack(fill='x',pady=6)
    ttk.Button(row,text='Save layout…',command=a.save).pack(side='left')
    ttk.Button(row,text='Load layout…',command=a.load).pack(side='right')
    ttk.Label(alignment,text='Optical alignment',style='Heading.TLabel').pack(anchor='w')
    ttk.Label(alignment,text='Align the optical layer to your selected thermal subject.',wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=(5,12))
    align=ttk.Button(alignment,text='Align selected area…',style='Primary.TButton',command=a.open_alignment_tool);align.pack(fill='x');ui.icon(align,'align')
    ttk.Label(alignment,text='Thermal opacity',style='Muted.TLabel').pack(anchor='w',pady=(18,5))
    ttk.Scale(alignment,from_=0,to=1,variable=a.opacity,command=lambda _:a.render()).pack(fill='x')
    for key,label in [('dx','X offset · thermal px'),('dy','Y offset · thermal px'),('scale','Optical scale'),('angle','Rotation · degrees')]:
        low,high,step={'dx':(-512,512,1),'dy':(-384,384,1),'scale':(.1,8,.02),'angle':(-180,180,1)}[key]
        ttk.Label(alignment,text=label,style='Muted.TLabel').pack(anchor='w',pady=(14,4))
        row=ttk.Frame(alignment);row.pack(fill='x')
        spin=ttk.Spinbox(row,textvariable=a.alignment[key],from_=low,to=high,increment=step,width=9,command=a.apply_alignment)
        spin.pack(side='right',padx=(10,0));spin.bind('<Return>',lambda e:a.apply_alignment());spin.bind('<FocusOut>',lambda e:a.apply_alignment())
        ttk.Scale(row,from_=low,to=high,variable=a.alignment_sliders[key],command=lambda value,k=key:a.slide_alignment(k,value)).pack(side='left',fill='x',expand=True)
    row=ttk.Frame(alignment);row.pack(fill='x',pady=16)
    ttk.Checkbutton(row,text='Lock alignment',variable=a.locked).pack(side='left')
    ttk.Button(row,text='Reset',command=a.reset_alignment).pack(side='right')
    ttk.Separator(alignment).pack(fill='x',pady=8)
    ttk.Label(alignment,text='Advanced tools',style='Heading.TLabel').pack(anchor='w',pady=8)
    ttk.Button(alignment,text='Experimental overlay / calibration…',command=a.open_smart_alignment_tool).pack(fill='x')
    ttk.Label(alignment,text='Alignment affects the optical display. Numerical thermal pixels stay fixed.',wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=12)
    ttk.Label(camera,text='Camera identity',style='Heading.TLabel').pack(anchor='w')
    ttk.Label(camera,text='Give this camera a useful name, such as Pack front.',wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=(5,8))
    ttk.Entry(camera,textvariable=a.camera_name).pack(fill='x')
    ttk.Button(camera,text='Save camera name',command=a.rename_camera).pack(anchor='e',pady=8)
    ttk.Label(camera,textvariable=a.camera_identity,wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=8)
    ttk.Separator(camera).pack(fill='x',pady=12)
    ttk.Label(camera,text='Capture',style='Heading.TLabel').pack(anchor='w')
    a.optical_check=ttk.Checkbutton(camera,text='Record lossless optical video',variable=a.record_optical);a.optical_check.pack(anchor='w',pady=8)
    ttk.Label(camera,textvariable=a.connection_info,wraplength=375,style='Muted.TLabel').pack(anchor='w',pady=8)
    ttk.Button(camera,text='Open another camera window',command=a.another_camera).pack(fill='x',pady=8)
    ttk.Separator(camera).pack(fill='x',pady=12)
    ttk.Label(camera,text='Temperature color scale',style='Heading.TLabel').pack(anchor='w')
    ttk.Checkbutton(camera,text='Automatic range',variable=a.automatic,command=a.render).pack(anchor='w',pady=8)
    row=ttk.Frame(camera);row.pack(fill='x')
    for label,var in [('Low °C',a.low),('High °C',a.high)]:
        ttk.Label(row,text=label,style='Muted.TLabel').pack(side='left');entry=ttk.Entry(row,textvariable=var,width=6);entry.pack(side='left',padx=8)
        entry.bind('<Return>',lambda e:a.render());entry.bind('<FocusOut>',lambda e:a.render())
    ttk.Separator(camera).pack(fill='x',pady=16)
    ttk.Label(camera,text='TOPDON runtime folder',style='Muted.TLabel').pack(anchor='w',pady=4)
    ttk.Entry(camera,textvariable=a.path).pack(fill='x')
    runtime_buttons=ttk.Frame(camera);runtime_buttons.pack(fill='x',pady=8)
    ttk.Button(runtime_buttons,text='Find TopView',command=a.detect_topview).pack(side='left')
    ttk.Button(runtime_buttons,text='Browse…',command=a.browse).pack(side='right')
    ttk.Label(camera,text='Detected automatically for this Windows account. Close TopView before connecting.',wraplength=375,style='Muted.TLabel').pack(anchor='w')
    ttk.Label(root,textvariable=a.info,style='Muted.TLabel',padding=(22,6),wraplength=1250).pack(fill='x')
    root.after_idle(lambda:body.sashpos(0,max(580,root.winfo_width()-450)))
