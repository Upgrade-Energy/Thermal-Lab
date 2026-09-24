"""Visible local launcher for the optional Power Lab camera service."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.request
import urllib.parse
from .topview_setup import resolve_topview

UI_FONT = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
PREFERENCES = Path.home() / '.thermal-lab' / 'desktop-preferences.json'
DESCRIPTOR = Path.home() / '.thermal-lab' / 'integration.json'


def preferences():
    try:
        value = json.loads(PREFERENCES.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_preferences(directory, recordings):
    PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
    temp = PREFERENCES.with_suffix('.tmp')
    temp.write_text(json.dumps(dict(topview_directory=str(directory), recordings=str(recordings))), encoding='utf-8')
    temp.replace(PREFERENCES)


def service_request(path, body=None):
    descriptor = json.loads(DESCRIPTOR.read_text())
    address = urllib.parse.urlsplit(descriptor['url'])
    if address.scheme != 'http' or address.hostname != '127.0.0.1' or not address.port or address.path not in ('','/') or address.username or address.query or address.fragment:
        raise ValueError('Invalid local service address')
    headers = {'Authorization': 'Bearer ' + descriptor['token']}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode();headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(descriptor['url'] + path, data=payload, headers=headers)
    # No redirects: the service token belongs only to the exact local endpoint.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):return None
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=2) as response:
        return json.loads(response.read(1024*1024))


def main():
    from lab_update import hold_app_lease, open_updates
    hold_app_lease('ThermalLab')
    root = tk.Tk();root.title('Thermal Lab · Power Lab service');root.geometry('760x450');root.minsize(760,450)
    style=ttk.Style();style.theme_use('clam');style.configure('.',font=(UI_FONT,11),background='#f3f6f9',foreground='#172b40');root.configure(bg='#f3f6f9');style.configure('TButton',padding=10)
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Connect Thermal Lab to Power Lab',font=(UI_FONT,21,'bold')).pack(anchor='w')
    ttk.Label(frame,text='This service lets Power Lab receive camera data and start or stop grouped recordings. Close TopView and disconnect cameras in live inspection before starting.',wraplength=700).pack(anchor='w',pady=15)
    saved=preferences();directory=tk.StringVar(value=saved.get('topview_directory',''));recordings=tk.StringVar(value=saved.get('recordings',str(Path.home()/'Thermal-Lab-Recordings')))
    for title,variable in [('TopView installation',directory),('Recording folder',recordings)]:
        row=ttk.Frame(frame);row.pack(fill='x',pady=6);ttk.Label(row,text=title,width=20).pack(side='left')
        ttk.Entry(row,textvariable=variable).pack(side='left',fill='x',expand=True,padx=8)
        def browse(v=variable):
            selected=filedialog.askdirectory(parent=root)
            if selected:v.set(selected)
        ttk.Button(row,text='Browse',command=browse).pack(side='left')
    status=tk.StringVar(value='Checking local service...');ttk.Label(frame,textvariable=status,wraplength=700).pack(fill='x',pady=20)
    events=queue.Queue();pending=False;child=None;log=None
    def start():
        nonlocal child,log
        try:
            directory.set(str(resolve_topview(directory.get())))
            if child and child.poll() is None:raise ValueError('The service is already starting or running.')
            save_preferences(directory.get(),recordings.get())
            log=PREFERENCES.parent.joinpath('service.log').open('a',encoding='utf-8')
            child=subprocess.Popen([sys.executable,'-m','thermal_lab.integration','--topview-directory',directory.get(),'--recordings',recordings.get()],cwd=str(Path(__file__).resolve().parents[1]),stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            status.set('Starting the local service...')
        except (OSError,ValueError) as exc:messagebox.showerror('Service could not start',str(exc),parent=root)
    def stop():
        def run():
            try:service_request('/v1/shutdown',{});events.put(('stop','Service stopping.'))
            except Exception:events.put(('stop','Stop recording and disconnect the camera group in Power Lab first. Active camera sessions are never forced closed.'))
        threading.Thread(target=run,daemon=True).start()
    buttons=ttk.Frame(frame);buttons.pack(fill='x')
    start_button=ttk.Button(buttons,text='Start service',command=start);start_button.pack(side='left')
    ttk.Button(buttons,text='Stop service',command=stop).pack(side='left',padx=8)
    ttk.Button(buttons,text='Check for updates',command=open_updates).pack(side='left')
    ttk.Label(frame,text='Closing this window leaves the service running. Use Stop service before installing an update.',wraplength=700).pack(anchor='w',pady=20)
    def poll():
        nonlocal pending
        try:
            kind,value=events.get_nowait()
            if kind=='state':
                pending=False;start_button.configure(state='disabled' if value else 'normal')
                status.set('Service running · available to Power Lab on this computer.' if value else 'Service stopped. Start it when you want Power Lab to use cameras.')
            else:status.set(value)
        except queue.Empty:pass
        root.after(200,poll)
    def refresh():
        nonlocal pending
        if not pending:
            pending=True
            def run():
                try:service_request('/v1/state');events.put(('state',True))
                except Exception:events.put(('state',False))
            threading.Thread(target=run,daemon=True).start()
        root.after(4000,refresh)
    root.after(100,poll);root.after(200,refresh);root.mainloop()
    if log:log.close()


if __name__=='__main__':main()
