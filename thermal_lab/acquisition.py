"""Spawned camera worker. Native calls never run in the interface process."""
import json
import hashlib
import queue
import time
import traceback
import math
import re
import multiprocessing
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .tc001_max import TC001Max, DLL_SHA256
from .thermal import Recorder
from .workspace import validate_settings, measurement_values
from .optical_recording import OpticalRecorder,CODEC


def worker(directory, commands, previews, events, camera_id=None):
    from lab_update import hold_app_lease
    hold_app_lease('ThermalLab')
    recorder=None; optical=None; destination=None; manifest=None; last_raw=None; record_origin=0; record_elapsed=0.
    settings=validate_settings({}); revision=0; camera=None
    parent=multiprocessing.parent_process();parent_watch_stop=threading.Event()
    def watch_parent():
        while not parent_watch_stop.wait(.25):
            if not parent.is_alive():os._exit(2) # Release USB ownership; unfinished archives remain incomplete.
    if parent is not None:threading.Thread(target=watch_parent,daemon=True,name='Camera owner watchdog').start()

    def event(kind, **data):
        events.put(dict(kind=kind,**data))

    def save_manifest():
        temp=destination/'session.tmp'
        temp.write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
        temp.replace(destination/'camera-session.json')

    def finish(error=None):
        nonlocal recorder,optical
        if recorder is None:return
        recorder.close()
        error=error or recorder.error
        if optical:
            optical.close();error=error or optical.error
            manifest['optical_frames_written']=optical.count
            if optical.count!=recorder.count:error=error or 'Optical/thermal recorded frame counts differ'
        if recorder.count==0:error=error or 'No frames were recorded'
        if last_raw is not None:(destination/'last.frame').write_bytes(last_raw)
        if recorder.measurement_csv:
            csv=recorder.measurement_csv
            if csv.frames!=recorder.count:error=error or 'Measurement CSV/thermal frame counts differ'
            if not error:
                try:csv.publish()
                except Exception as exc:error='Measurement CSV finalization failed: '+str(exc)
            manifest.update(measurement_csv=csv.path.name,measurement_csv_frames=csv.frames,
                            measurement_csv_rows=csv.rows,measurement_csv_status='INCOMPLETE' if error else 'COMPLETE')
        manifest.update(status='FAILED' if error else 'COMPLETE',error=error,
                        frames_written=recorder.count,duration_s=record_elapsed,finished_utc=datetime.now(timezone.utc).isoformat())
        if error:manifest['measurement_csv_status']='INCOMPLETE'
        save_manifest()
        event('recording_finished',path=str(destination),status=manifest['status'],frames=recorder.count,error=error,
              measurement_csv=str(destination/manifest['measurement_csv']) if not error else None,duration_s=record_elapsed)
        recorder=None
        optical=None

    try:
        with (TC001Max(directory, camera_id=camera_id) if camera_id else TC001Max(directory)) as camera:
            first_sample=camera.read() if camera_id else None
            event('connected',camera_id=camera.camera_id,startup_retries=getattr(camera,'startup_retries',0))
            running=True; last_preview=0; previous_digest=None; last_change=time.monotonic()
            while running:
                while True:
                    try:command=commands.get_nowait()
                    except queue.Empty:break
                    action=command['action']
                    if action=='stop':running=False;break
                    if action=='abort':
                        finish(str(command.get('reason','Integration disconnected')));running=False;break
                    if action=='settings':
                        candidate=validate_settings(command['settings'])
                        if candidate['camera_id'] and candidate['camera_id'].casefold()!=camera.camera_id.casefold():
                            raise ValueError('Measurement layout belongs to another camera')
                        candidate['camera_id']=camera.camera_id
                        settings=candidate;revision+=1
                    elif action=='record':
                        if recorder is not None:continue
                        destination=Path(command['path']);destination.mkdir(parents=True,exist_ok=False)
                        record_origin=first_sample[0]['elapsed_s'] if first_sample else time.monotonic()-camera.origin
                        last_raw=None
                        record_elapsed=0.
                        manifest=dict(status='RECORDING',source='HARDWARE',camera_id=camera.camera_id,
                                      dll_sha256=DLL_SHA256,timestamp_basis='host_monotonic_arrival',
                                      temperature_basis='apparent_raw_kelvin_64',optical_video_recorded=False,
                                      device_dropped_frames=None,frames_written=0,
                                      started_utc=datetime.now(timezone.utc).isoformat(),initial_workspace=settings,
                                      measurement_csv='measurements.partial.csv',measurement_csv_status='RECORDING',
                                      measurement_csv_frames=0,measurement_csv_rows=0)
                        if command.get('run_id') is not None:
                            run_id=command['run_id'];origin=command.get('run_origin_monotonic')
                            if not isinstance(run_id,str) or not re.fullmatch(r'[a-f0-9]{32}',run_id):raise ValueError('Invalid integration run ID')
                            if isinstance(origin,bool) or not isinstance(origin,(int,float)) or not math.isfinite(origin):raise ValueError('Invalid run origin')
                            manifest.update(run_id=run_id,run_origin_monotonic=origin,
                                            camera_origin_monotonic=camera.origin,
                                            run_time_basis='same_host_monotonic_arrival; exposure_sync_unqualified')
                        if command.get('optical',False):
                            manifest.update(optical_video_recorded=True,optical_codec=CODEC,optical_width=1024,
                                            optical_height=768,optical_frames_written=0,
                                            optical_pairing='same_native_buffer; host_arrival; exposure_sync_unqualified')
                        save_manifest();recorder=Recorder([],0,compression_level=1,measurement_csv=True)
                        recorder.start(destination/'thermal.jsonl.gz')
                        if command.get('optical',False):optical=OpticalRecorder(destination)
                        event('recording_started',path=str(destination),origin_monotonic=camera.origin+record_origin)
                    elif action=='finish':finish()
                if not running:break
                frame,raw=first_sample if first_sample else camera.read()
                first_sample=None
                digest=hashlib.sha256(raw[98304:196608]).digest()
                now=time.monotonic()
                if digest!=previous_digest:last_change=now
                elif now-last_change>2:raise OSError('Thermal plane unchanged for over two seconds')
                previous_digest=digest
                if recorder is not None:
                    recorded=dict(frame,camera_elapsed_s=frame['elapsed_s'],
                                  elapsed_s=frame['elapsed_s']-record_origin,workspace_revision=revision,
                                  workspace=settings,measurements=measurement_values(frame,settings))
                    if manifest.get('run_id'):
                        recorded.update(run_id=manifest['run_id'],run_elapsed_s=camera.origin+frame['elapsed_s']-manifest['run_origin_monotonic'])
                    if optical:recorded['optical_sha256']=optical.ingest(raw,recorded['elapsed_s'],frame['arrival_sequence'])
                    recorder.ingest([recorded])
                    record_elapsed=recorded['elapsed_s']
                    if last_raw is None:(destination/'first.frame').write_bytes(raw)
                    last_raw=raw
                # Preview can drop superseded frames; recording keeps every accepted frame.
                now=time.monotonic()
                if now-last_preview>=.10:
                    message=dict(frame=frame,raw=raw,received_at=camera.origin+frame['elapsed_s'],
                                 run_id=manifest.get('run_id') if recorder and manifest else None,
                                 recording_frames=recorder.count if recorder else None)
                    try:previews.put_nowait(message)
                    except queue.Full:pass
                    last_preview=now
            finish()
    except BaseException as exc:
        traceback.print_exc()
        try:finish(str(exc))
        except Exception:traceback.print_exc()
        event('error',message=str(exc))
    finally:
        parent_watch_stop.set()
        event('stopped')
        # A pending display frame must not keep the acquisition process alive.
        previews.cancel_join_thread()
