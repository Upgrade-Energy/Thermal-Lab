"""Explicit two-camera sustained recording test. No instrument control."""
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import queue
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thermal_lab.acquisition import worker
from thermal_lab.camera_diagnostics import pnp_devices
from thermal_lab.imaging import optical_image,thermal_image,rotate_image
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=1800)
    parser.add_argument('--topview-directory',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 60<=args.seconds<=3600:raise SystemExit('Use 60–3600 seconds')
    args.output.mkdir(parents=True,exist_ok=False)
    devices=pnp_devices();(args.output/'devices.json').write_text(json.dumps(devices,indent=2))
    if len(devices)!=2:raise SystemExit(f'Expected two cameras, found {len(devices)}')
    if shutil.disk_usage(args.output).free<args.seconds*90_000_000+10_000_000_000:raise SystemExit('Insufficient disk space for planned test')
    ctx=mp.get_context('spawn');sessions=[];started=time.monotonic();recording_at=None;stop_at=None;last_status=0;failure=None
    def stop(reason=None):
        nonlocal stop_at,failure
        failure=failure or reason
        if stop_at is None:
            stop_at=time.monotonic()
            for s in sessions:s['commands'].put(dict(action='stop'))
    try:
        for i,d in enumerate(devices):
            commands=ctx.Queue(32);previews=ctx.Queue(1);events=ctx.Queue();path=args.output/f'camera{i}'
            process=ctx.Process(target=worker,args=(args.topview_directory,commands,previews,events,d['instance_id']))
            sessions.append(dict(process=process,commands=commands,previews=previews,events=events,path=path,device=d['instance_id'],
                                 connected=False,stopped=False,seen=[],last_preview=None,last_image=0,last_frame=None,frames=0))
            process.start()
            commands.put(dict(action='settings',settings=dict(camera_id=d['instance_id'],
                points=[dict(id='center',name='Center',x=.5,y=.5),dict(id='upper',name='Upper quarter',x=.25,y=.25)],
                areas=[dict(id='region',name='Center region',x=.4,y=.4,x2=.6,y2=.6)])))
        with (args.output/'progress.jsonl').open('x') as progress:
            while True:
                now=time.monotonic()
                for s in sessions:
                    try:
                        while True:
                            e=s['events'].get_nowait();s['seen'].append(e);print(json.dumps(dict(camera=s['path'].name,event=e)),flush=True)
                            if e['kind']=='connected':s['connected']=True
                            if e['kind']=='stopped':s['stopped']=True
                            if e['kind']=='error':stop(e['message'])
                            if e['kind']=='recording_finished' and e['status']!='COMPLETE':stop(e.get('error') or 'Incomplete recording')
                    except queue.Empty:pass
                    try:
                        sample=s['previews'].get_nowait();s['last_preview']=now;s['last_frame']=sample['frame']
                        s['frames']=sample.get('recording_frames') or s['frames']
                        if sample['frame']['camera_id']!=s['device']:stop('Preview camera identity mismatch')
                        if not s['last_image'] or now-s['last_image']>=300:
                            optical=rotate_image(optical_image(sample['raw']),180);thermal=rotate_image(thermal_image(sample['frame']['temperatures'])[0],180)
                            canvas=Image.new('RGB',(2048,768));canvas.paste(optical,(0,0));canvas.paste(thermal,(1024,0))
                            canvas.save(args.output/(s['path'].name+'-preview-'+str(int(now-started))+'.jpg'),quality=90)
                            s['last_image']=now
                    except queue.Empty:pass
                    if stop_at is None and s['connected'] and s['last_preview'] and now-s['last_preview']>8:stop('No fresh preview for eight seconds')
                    if stop_at is None and not s['process'].is_alive():stop('Camera worker exited unexpectedly')
                if recording_at is None and all(s['connected'] for s in sessions) and stop_at is None:
                    recording_at=now
                    for s in sessions:s['commands'].put(dict(action='record',path=str(s['path']),optical=True))
                if recording_at and now-recording_at>=args.seconds+2:stop()
                if recording_at is None and now-started>40:stop('Camera startup deadline exceeded')
                if now-last_status>=30:
                    elapsed=now-recording_at if recording_at else 0
                    data=dict(elapsed_s=round(elapsed,2),free_gb=round(shutil.disk_usage(args.output).free/1e9,2),failure=failure,
                              cameras=[dict(camera=s['path'].name,frames=s['frames'],last_sequence=s['last_frame']['arrival_sequence'] if s['last_frame'] else None,
                                            preview_age_s=round(now-s['last_preview'],2) if s['last_preview'] else None) for s in sessions])
                    progress.write(json.dumps(data)+'\n');progress.flush();print(json.dumps(data),flush=True);last_status=now
                    if shutil.disk_usage(args.output).free<10_000_000_000:stop('Safety stop: less than 10 GB free')
                if all(s['stopped'] for s in sessions):break
                if stop_at and now-stop_at>15:stop('Camera shutdown deadline exceeded');break
                time.sleep(.02)
    finally:
        stop()
        for s in sessions:
            s['process'].join(timeout=2)
            if s['process'].is_alive():s['process'].terminate();s['process'].join(timeout=3);failure=failure or 'Worker forcibly terminated'
            (args.output/(s['path'].name+'-events.json')).write_text(json.dumps(dict(events=s['seen'],exitcode=s['process'].exitcode),indent=2))
    result=dict(status='FAILED' if failure else 'CAPTURE_FINISHED',error=failure,requested_seconds=args.seconds,output=str(args.output.resolve()))
    (args.output/'capture-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    return 1 if failure else 0


if __name__=='__main__':raise SystemExit(main())
