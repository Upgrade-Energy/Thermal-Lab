"""Versioned loopback service; camera ownership stays entirely in Thermal Lab."""
import argparse
import copy
import hmac
import json
import math
import multiprocessing as mp
from pathlib import Path
import queue
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .acquisition import worker
from .camera_diagnostics import pnp_devices
from .connection_guidance import connection_guidance
from .workspace import validate_settings, measurement_values
from .service_lease import service_lease


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):raise ValueError('Expected a 32-character hexadecimal ID')
    return value


class CameraService:
    def __init__(self,directory,recordings,*,discover=pnp_devices,worker_target=worker,lease_seconds=8):
        self.directory=str(directory);self.recordings=Path(recordings).resolve()
        self.discover=discover;self.worker_target=worker_target;self.lease_seconds=lease_seconds
        self.ctx=mp.get_context('spawn');self.lock=threading.RLock();self.quit=threading.Event()
        self.owner=None;self.config=None;self.cameras=[];self.runs={};self.active=None;self.error=None
        self.thread=threading.Thread(target=self._loop,daemon=True);self.thread.start()

    def devices(self):
        devices=self.discover()
        return dict(schema=1,cameras=devices,guidance=connection_guidance(devices))

    def connect(self,body):
        owner=identifier(body.get('session_id'));configs=body.get('cameras')
        if not isinstance(configs,list) or not 1<=len(configs)<=3:raise ValueError('Select one to three cameras; only two-camera capture is qualified')
        prepared=[];seen=set()
        for config in configs:
            camera_id=config['camera_id']
            if not isinstance(camera_id,str) or camera_id.casefold() in seen:raise ValueError('Camera identities must be unique')
            seen.add(camera_id.casefold())
            settings=validate_settings(config.get('settings',{}))
            if settings['camera_id'] and settings['camera_id'].casefold()!=camera_id.casefold():raise ValueError('Workspace camera identity mismatch')
            prepared.append(dict(camera_id=camera_id,settings=dict(settings,camera_id=camera_id)))
        with self.lock:
            if self.owner:
                if owner==self.owner and prepared==self.config:return self.state()
                raise ValueError('Cameras already owned by another integration session; disconnect it first')
            if any(c['process'].is_alive() for c in self.cameras):raise ValueError('Previous camera workers are still stopping')
            healthy={d['instance_id'].casefold() for d in self.discover() if d.get('problem_code')==0}
            if not seen<=healthy:raise ValueError('Selected camera is not connected and healthy')
            for camera in self.cameras:
                camera['process'].join(0)
                for key in ('commands','events','previews'):camera[key].cancel_join_thread();camera[key].close()
            self.owner=owner;self.config=prepared;self.error=None;self.cameras=[];self.heartbeat_at=time.monotonic()
            try:
                for config in prepared:
                    commands=self.ctx.Queue(32);previews=self.ctx.Queue(1);events=self.ctx.Queue()
                    process=self.ctx.Process(target=self.worker_target,args=(self.directory,commands,previews,events,config['camera_id']),daemon=True)
                    item=dict(**config,process=process,commands=commands,previews=previews,events=events,
                              connected=False,sample=None,error=None,started=time.monotonic(),deadline=None)
                    process.start();self.cameras.append(item)
                    commands.put_nowait(dict(action='settings',settings=config['settings']))
            except Exception:
                self._abort('Camera worker startup failed');raise
            return self.state()

    def require_owner(self,body):
        if not self.owner or body.get('session_id')!=self.owner:raise ValueError('Integration session is not connected')

    def heartbeat(self,body):
        with self.lock:
            self.require_owner(body);self.heartbeat_at=time.monotonic();return self.state()

    def start(self,body):
        run_id=identifier(body.get('run_id'));origin=body.get('run_origin_monotonic')
        if isinstance(origin,bool) or not isinstance(origin,(int,float)) or not math.isfinite(origin):
            raise ValueError('Run origin must use this host monotonic clock within 60 seconds')
        with self.lock:
            self.require_owner(body)
            if run_id in self.runs:
                run=self.runs[run_id]
                if run['session_id']!=self.owner or run['run_origin_monotonic']!=origin:raise ValueError('Run ID already used with different parameters')
                return copy.deepcopy(run)
            if abs(time.monotonic()-origin)>60:raise ValueError('New run origin must use this host monotonic clock within 60 seconds')
            if self.active:raise ValueError('A camera run is already active')
            if not all(c['fresh'] for c in self.state()['cameras']):raise ValueError('Fresh frames from every selected camera are required')
            if len(self.runs)>=1000:raise ValueError('Service run limit reached; restart after disconnecting')
            folder=self.recordings/run_id;folder.mkdir(parents=True,exist_ok=False)
            run=dict(run_id=run_id,session_id=self.owner,run_origin_monotonic=origin,status='STARTING',error=None,cameras=[])
            self.runs[run_id]=run;self.active=run_id
            for i,camera in enumerate(self.cameras):
                path=folder/f'camera{i}'
                run['cameras'].append(dict(camera_id=camera['camera_id'],path=str(path),status='STARTING',frames=0))
                camera['commands'].put_nowait(dict(action='record',path=str(path),optical=True,run_id=run_id,run_origin_monotonic=origin))
            return copy.deepcopy(run)

    def stop(self,body):
        with self.lock:
            self.require_owner(body);run=self.runs.get(identifier(body.get('run_id')))
            if not run or run['session_id']!=self.owner:raise ValueError('Unknown run')
            if run['status'] not in ('COMPLETE','FAILED','STOPPING'):
                run['status']='STOPPING';run['stop_deadline']=time.monotonic()+10
                for camera in self.cameras:camera['commands'].put_nowait(dict(action='finish'))
            return copy.deepcopy(run)

    def disconnect(self,body):
        with self.lock:
            self.require_owner(body)
            if self.active:raise ValueError('Finalize the camera recording before disconnecting')
            for camera in self.cameras:
                camera['commands'].put_nowait(dict(action='stop'));camera['deadline']=time.monotonic()+7
                camera['connected']=False;camera['sample']=None
            self.owner=None
            return dict(disconnected=True)

    def state(self):
        with self.lock:
            now=time.monotonic();items=[]
            for camera in self.cameras:
                sample=camera['sample'];age=now-sample['received_at'] if sample else None
                fresh=bool(camera['connected'] and camera['process'].is_alive() and sample and 0<=age<=1 and not camera['error'])
                items.append(dict(camera_id=camera['camera_id'],connected=camera['connected'],fresh=fresh,
                    unit='C',run_id=sample.get('run_id') if sample else None,
                    age_s=age,error=camera['error'],source=sample['frame']['source'] if sample else None,
                    arrival_sequence=sample['frame']['arrival_sequence'] if sample else None,
                    host_monotonic=sample['received_at'] if sample else None,
                    measurements=measurement_values(sample['frame'],camera['settings']) if fresh else {},
                    definitions=camera['settings'],temperature_basis='apparent_raw_kelvin_64'))
            return dict(schema=1,session_id=self.owner,error=self.error,cameras=items,
                        run=copy.deepcopy(self.runs.get(self.active)),runs=copy.deepcopy(list(self.runs.values())[-10:]))

    def _abort(self,reason):
        self.error=reason
        if self.active:
            run=self.runs[self.active];run.update(status='FAILED',error=reason)
        for camera in self.cameras:
            camera.update(connected=False,sample=None,error=reason)
            if camera['deadline'] is None:
                camera['deadline']=time.monotonic()+7
                try:camera['commands'].put_nowait(dict(action='abort',reason=reason))
                except queue.Full:camera['process'].terminate()

    def _poll(self):
        now=time.monotonic()
        if self.owner and now-self.heartbeat_at>self.lease_seconds:self._abort('Integration heartbeat expired')
        run=self.runs.get(self.active)
        for i,camera in enumerate(self.cameras):
            try:
                while True:
                    event=camera['events'].get_nowait();kind=event['kind']
                    if kind=='connected' and not camera['deadline']:camera['connected']=True
                    if kind=='error':self._abort(event['message'])
                    if kind=='stopped':camera.update(connected=False,sample=None)
                    if run and kind in ('recording_started','recording_finished'):
                        item=run['cameras'][i]
                        if Path(event['path']).resolve()!=Path(item['path']):continue
                        item.update(status='RECORDING' if kind=='recording_started' else event['status'],frames=event.get('frames',0),error=event.get('error'))
                        if item['status']=='FAILED':self._abort(item['error'] or 'Camera recording failed')
            except queue.Empty:pass
            try:
                sample=camera['previews'].get_nowait()
                if camera['connected'] and not camera['deadline']:
                    if sample['frame']['camera_id']!=camera['camera_id']:self._abort('Camera identity mismatch')
                    else:camera['sample']=sample
            except queue.Empty:pass
            if camera['deadline'] and now>camera['deadline'] and camera['process'].is_alive():camera['process'].terminate()
            if not camera['process'].is_alive():
                camera['process'].join(0)
                if not camera['deadline']:self._abort('Camera worker exited')
            elif not camera['deadline']:
                sample=camera['sample']
                if sample and now-sample['received_at']>8:self._abort('Camera stream timed out')
                elif not sample and now-camera['started']>40:self._abort('Camera startup timed out')
        if run:
            if run['status']=='STARTING' and all(c['status']=='RECORDING' for c in run['cameras']) and all(c['sample'] and c['sample'].get('run_id')==self.active for c in self.cameras):run['status']='RECORDING'
            if run['status']=='STOPPING' and now>run['stop_deadline']:self._abort('Camera recording finalization timed out')
            if run['status']=='STOPPING' and all(c['status']=='COMPLETE' for c in run['cameras']):run['status']='COMPLETE';self.active=None
            elif run['status']=='FAILED' and all(not c['process'].is_alive() for c in self.cameras):self.active=None;self.owner=None
        elif self.error and all(not c['process'].is_alive() for c in self.cameras):self.owner=None

    def _loop(self):
        while not self.quit.wait(.05):
            with self.lock:
                try:self._poll()
                except Exception as exc:self._abort(str(exc))

    def close(self):
        with self.lock:self._abort('Thermal Lab service shutdown')
        deadline=time.monotonic()+8
        while any(c['process'].is_alive() for c in self.cameras) and time.monotonic()<deadline:time.sleep(.05)
        self.quit.set();self.thread.join(1)
        for camera in self.cameras:
            if camera['process'].is_alive():camera['process'].terminate()
            camera['process'].join(2)
            for key in ('commands','events','previews'):
                camera[key].cancel_join_thread();camera[key].close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,value):
        data=json.dumps(value,allow_nan=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def handle_request(self):
        self.connection.settimeout(3)
        if self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token):
            self.reply(403,dict(error='Local integration token required; browser origins are not accepted'));return
        try:
            service=self.server.service
            if self.command=='GET':
                if self.path=='/v1/cameras':result=service.devices()
                elif self.path=='/v1/state':result=service.state()
                else:self.reply(404,dict(error='Unknown endpoint'));return
            else:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=65536:raise ValueError('Request must be at most 64 KiB')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('JSON object required')
                if self.path=='/v1/view':
                    from .integration_review import camera_view
                    self.reply(200,camera_view(service,body));return
                if self.path=='/v1/shutdown':
                    with service.lock:
                        if service.owner or service.active:raise ValueError('Disconnect cameras before shutting down the service')
                    self.reply(200,dict(shutting_down=True))
                    threading.Thread(target=self.server.shutdown,daemon=True).start();return
                actions={'/v1/connect':service.connect,'/v1/heartbeat':service.heartbeat,'/v1/runs/start':service.start,'/v1/runs/stop':service.stop,'/v1/disconnect':service.disconnect}
                if self.path not in actions:self.reply(404,dict(error='Unknown endpoint'));return
                result=actions[self.path](body)
            self.reply(200,result)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        except (ValueError,KeyError,TypeError) as exc:self.reply(400,dict(error=str(exc)))
        except Exception as exc:self.reply(503,dict(error=str(exc)))
    do_GET=handle_request
    do_POST=handle_request


def make_server(service,token,port=0):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    server.service=service;server.token=token
    return server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topview-directory',required=True,type=Path)
    parser.add_argument('--recordings',type=Path,default=Path.home()/'Thermal-Lab-Recordings')
    parser.add_argument('--connection-file',type=Path,default=Path.home()/'.thermal-lab/integration.json')
    args=parser.parse_args()
    with service_lease(args.connection_file):serve(args)


def serve(args):
    service=CameraService(args.topview_directory,args.recordings)
    token=secrets.token_urlsafe(32);server=make_server(service,token)
    args.connection_file.parent.mkdir(parents=True,exist_ok=True)
    descriptor=dict(schema=1,url=f'http://127.0.0.1:{server.server_port}',token=token)
    # The file is a local credential, never included in run archives or logs.
    temporary=args.connection_file.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        temporary.chmod(0o600);json.dump(descriptor,stream)
    temporary.replace(args.connection_file)
    print('Thermal Lab integration listening on loopback; connection file: '+str(args.connection_file),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();service.close()
        if args.connection_file.exists() and json.loads(args.connection_file.read_text()).get('token')==token:args.connection_file.unlink()


if __name__=='__main__':main()
