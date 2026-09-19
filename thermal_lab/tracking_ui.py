"""Shared controls for recorded extrema measurements and offline analysis."""
import tkinter as tk
from tkinter import ttk


def build(parent,app,review=False):
    ttk.Label(parent,text='Track a moving extreme',style='Heading.TLabel').pack(anchor='w',pady=(8,4))
    app.tracking_scope=tk.StringVar(value='Whole image')
    row=ttk.Frame(parent);row.pack(fill='x',pady=5)
    ttk.Label(row,text='Search',style='Muted.TLabel').pack(side='left')
    ttk.Combobox(row,textvariable=app.tracking_scope,values=['Whole image','Selected region'],
                 state='readonly',width=18).pack(side='right')
    row=ttk.Frame(parent);row.pack(fill='x',pady=5)
    app.track_buttons={}
    for tracking in ('hottest','coldest'):
        button=ttk.Button(row,text='Track '+tracking,command=lambda value=tracking:app.add_tracking(value))
        button.pack(side='left',fill='x',expand=True,padx=(0,6) if tracking=='hottest' else 0)
        app.track_buttons[tracking]=button
    text=('Choose Analysis to add trackers to any recording. ' if review else 'Add either or both before Record. ')
    text+='Follows the extreme pixel, even when its location changes. Select a region in the list to limit the search.'
    ttk.Label(parent,text=text,wraplength=310 if review else 365,style='Muted.TLabel').pack(anchor='w',pady=(3,10))
