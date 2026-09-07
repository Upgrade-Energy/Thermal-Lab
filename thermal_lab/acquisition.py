"""Spawned camera worker. Native calls never run in the interface process."""
import json
import hashlib
import queue
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .tc001_max import TC001Max, DLL_SHA256
from .thermal import Recorder
from .workspace import validate_settings, measurement_values
from .optical_recording import OpticalRecorder,CODEC


def worker(directory, commands, previews, events, camera_id=None):
    recorder=None; optical=None; destination=None; manifest=None; last_raw=None; record_origin=0
    settings=validate_settings({}); revision=0; camera=None

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
        manifest.update(status='FAILED' if error else 'COMPLETE',error=error,
                        frames_written=recorder.count,finished_utc=datetime.now(timezone.utc).isoformat())
        save_manifest()
        event('recording_finished',path=str(destination),status=manifest['status'],frames=recorder.count,error=error)
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
                        manifest=dict(status='RECORDING',source='HARDWARE',camera_id=camera.camera_id,
                                      dll_sha256=DLL_SHA256,timestamp_basis='host_monotonic_arrival',
                                      temperature_basis='apparent_raw_kelvin_64',optical_video_recorded=False,
                                      device_dropped_frames=None,frames_written=0,
                                      started_utc=datetime.now(timezone.utc).isoformat(),initial_workspace=settings)
                        if command.get('optical',False):
                            manifest.update(optical_video_recorded=True,optical_codec=CODEC,optical_width=1024,
                                            optical_height=768,optical_frames_written=0,
                                            optical_pairing='same_native_buffer; host_arrival; exposure_sync_unqualified')
                        save_manifest();recorder=Recorder([],0,compression_level=1)
                        recorder.start(destination/'thermal.jsonl.gz')
                        if command.get('optical',False):optical=OpticalRecorder(destination)
                        event('recording_started',path=str(destination))
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
                    if optical:recorded['optical_sha256']=optical.ingest(raw,recorded['elapsed_s'],frame['arrival_sequence'])
                    recorder.ingest([recorded])
                    if last_raw is None:(destination/'first.frame').write_bytes(raw)
                    last_raw=raw
                # Preview can drop superseded frames; recording keeps every accepted frame.
                now=time.monotonic()
                if now-last_preview>=.10:
                    message=dict(frame=frame,raw=raw,received_at=now,
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
        event('stopped')
        # A pending display frame must not keep the acquisition process alive.
        previews.cancel_join_thread()
