"""Audit a finalized sustained recording, histories, snapshots and full MP4."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thermal_lab.playback import Recording,export_history
from thermal_lab.tc001_max import decode_frame
from thermal_lab.optical_recording import OPTICAL_OFFSET
from thermal_lab.media_export import export_png,export_mp4
from PIL import Image
import imageio_ffmpeg


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(8*1024*1024):digest.update(chunk)
    return digest.hexdigest()


def main():
    if not __debug__:raise SystemExit('Run verification without Python -O; assertions are required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--minimum-seconds',type=float,default=1800)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    r=Recording(args.recording);assert r.optical is not None
    count=len(r.entries);duration=r.times[-1]-r.times[0]
    assert duration>=args.minimum_seconds,(duration,args.minimum_seconds)
    original_read=r.read;checked=0;previous=None;sequence_gaps=0;optical_hashes=set();low=math.inf;high=-math.inf
    gaps=[b-a for a,b in zip(r.times,r.times[1:])]
    print(json.dumps(dict(stage='verification_start',frames=count,duration_s=duration)),flush=True)
    before={p.name:file_hash(p) for p in r.path.iterdir() if p.is_file()}
    def audited_read(index):
        nonlocal checked,previous,sequence_gaps,low,high
        frame=original_read(index);plane=r.optical.read(index,frame)
        assert frame['workspace']==r.manifest['initial_workspace']
        assert frame['source']=='HARDWARE' and frame['capture_timestamp'] is None
        assert frame['identity_basis']=='opened_windows_device_object'
        seq=frame['arrival_sequence']
        if previous is not None:
            assert seq>previous
            sequence_gaps+=seq-previous-1
        previous=seq;optical_hashes.add(frame['optical_sha256'])
        pixels=frame['temperatures'];low=min(low,min(pixels));high=max(high,max(pixels))
        # Independent direct-index checks of every recorded point/region statistic.
        for kind in ('points','areas'):
            for item in frame['workspace'][kind]:
                x=min(255,int(item['x']*256));y=min(191,int(item['y']*192));values=frame['measurements'][item['id']]
                if kind=='points':assert values['value']==pixels[y*256+x]
                else:
                    block=[pixels[yy*256+xx] for yy in range(y,min(191,int(item['y2']*192))+1) for xx in range(x,min(255,int(item['x2']*256))+1)]
                    assert values['min']==min(block) and values['max']==max(block)
                    assert abs(values['mean']-sum(block)/len(block))<1e-10
        if index in (0,count-1):
            raw=(r.path/('first.frame' if index==0 else 'last.frame')).read_bytes()
            decoded=decode_frame(raw,camera_id=frame['camera_id'],elapsed_s=frame['elapsed_s'],sequence=seq)
            assert decoded['temperatures']==pixels and decoded['raw_sha256']==frame['raw_sha256']
            assert plane==raw[OPTICAL_OFFSET:]
        checked+=1
        return frame
    r.read=audited_read
    last_log=[0.]
    def progress(n,total):
        if time.monotonic()-last_log[0]>30 or n==total:
            print(json.dumps(dict(stage='verify_histories',checked=n,total=total)),flush=True);last_log[0]=time.monotonic()
    histories=r.histories(progress=progress);r.read=original_read
    assert checked==count and sequence_gaps==0
    export_history(args.output/'history.csv',r,histories)
    csv_rows=0
    with (args.output/'history.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            key=(row['measurement_id'],row['statistic']);index=int(row['frame_index'])
            assert row['camera_id']==r.manifest['camera_id'] and row['source']=='HARDWARE'
            assert float(row['temperature_c'])==histories[key]['samples'][index][2]
            assert float(row['elapsed_s'])==r.times[index]
            assert row['geometry']==histories[key]['samples'][index][3]
            assert row['measurement_basis']=='original_recorded' and row['recording_sha256']==''
            csv_rows+=1
    layout=r.manifest['initial_workspace']
    assert csv_rows==count*(len(layout['points'])+3*len(layout['areas']))
    summary=dict(status='RECORDING_AND_HISTORIES_PASS',camera_id=r.manifest['camera_id'],frames=count,duration_s=duration,
                 fps=(count-1)/duration,max_arrival_gap_s=max(gaps),median_arrival_gap_s=statistics.median(gaps),
                 p99_arrival_gap_s=sorted(gaps)[int(len(gaps)*.99)],accepted_sequence_gaps=sequence_gaps,
                 optical_pairs_checked=checked,unique_optical_frames=len(optical_hashes),temperature_values_checked=count*49152,
                 temperature_range_c=[low,high],history_values_checked=csv_rows,first_last_raw_exact=True)
    (args.output/'verification.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
    for label,index in [('first',0),('middle',count//2),('last',count-1)]:
        export_png(r,index,args.output/(label+'-blend.png'),dict(mode='Blend',labels=True,rotation=180))
    # Exercise the entire production exporter, not a fabricated short archive.
    last_log[0]=0
    def video_progress(n,total):
        if time.monotonic()-last_log[0]>30 or n==total:
            print(json.dumps(dict(stage='mp4_export',frames=n,total=total)),flush=True);last_log[0]=time.monotonic()
    meta=export_mp4(r,args.output/'full-thermal.mp4',dict(mode='Thermal',labels=True,rotation=180),progress=video_progress)
    reader=imageio_ffmpeg.read_frames(str(args.output/'full-thermal.mp4'),pix_fmt='rgb24');header=next(reader);decoded=0;last_log[0]=0
    for decoded,pixels in enumerate(reader,1):
        if decoded in (1,meta['frame_count']//2,meta['frame_count']):
            Image.frombytes('RGB',header['size'],pixels).save(args.output/f'decoded-{decoded}.png')
        if time.monotonic()-last_log[0]>30:
            print(json.dumps(dict(stage='mp4_decode',frames=decoded,total=meta['frame_count'])),flush=True);last_log[0]=time.monotonic()
    assert decoded==meta['frame_count'] and header['size']==(1024,768) and header['fps']==25
    assert abs(header['duration']-meta['duration_s'])<.05
    assert meta['source_frame_indices'][0]==0 and meta['source_frame_indices'][-1]==count-1
    after={p.name:file_hash(p) for p in r.path.iterdir() if p.is_file()};assert before==after
    summary.update(status='PASS',source_files_unchanged=len(before),source_hashes=after,
                   mp4_frames_decoded=decoded,mp4_duration_s=header['duration'],mp4_bytes=(args.output/'full-thermal.mp4').stat().st_size)
    (args.output/'verification.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
