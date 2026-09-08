"""Audit linked real-camera archives against Power Lab's exported simulation run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thermal_lab.playback import Recording
from thermal_lab.media_export import export_png
from thermal_lab.tc001_max import decode_frame
from thermal_lab.optical_recording import OPTICAL_OFFSET


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(8*1024*1024):value.update(chunk)
    return value.hexdigest()


def main():
    if not __debug__:raise SystemExit('Assertions must be enabled')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('powerlab_export',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    with ZipFile(args.powerlab_export) as archive:
        run=json.loads(archive.read('run.json'));link=json.loads(archive.read('thermal-lab-link.json'))
    assert run['status']=='completed' and link['status']=='COMPLETE' and run['id']==link['run_id']
    assert run['snapshot']['source']=='SIMULATION' and all(s['source']=='SIMULATION' for s in run['samples'])
    maps={};summaries=[]
    for camera in link['cameras']:
        recording=Recording(camera['path']);identity=camera['camera_id'];rows={}
        before={p.name:digest(p) for p in recording.path.iterdir() if p.is_file()}
        assert recording.manifest['run_id']==run['id'] and recording.manifest['source']=='HARDWARE'
        assert recording.manifest['run_origin_monotonic']==run['snapshot']['monotonic_origin']
        assert recording.manifest['optical_codec']=='lz4-yuyv422-v1'
        previous=None
        for i in range(len(recording.entries)):
            frame=recording.read(i);plane=recording.optical.read(i,frame)
            assert frame['run_id']==run['id'] and frame['camera_id']==identity and frame['source']=='HARDWARE'
            host=recording.manifest['camera_origin_monotonic']+frame['camera_elapsed_s']
            assert frame['run_elapsed_s']==host-run['snapshot']['monotonic_origin']
            sequence=frame['arrival_sequence']
            if previous is not None:assert sequence==previous+1
            previous=sequence
            rows[sequence]=dict(measurements=frame['measurements'],host_monotonic=host)
            if i in (0,len(recording.entries)-1):
                raw=(recording.path/('first.frame' if i==0 else 'last.frame')).read_bytes()
                decoded=decode_frame(raw,camera_id=identity,elapsed_s=frame['elapsed_s'],sequence=sequence)
                assert decoded['temperatures']==frame['temperatures'] and plane==raw[OPTICAL_OFFSET:]
        for label,i in [('first',0),('middle',len(recording.entries)//2),('last',len(recording.entries)-1)]:
            export_png(recording,i,args.output/(recording.path.name+'-'+label+'.png'),dict(mode='Blend',labels=True,rotation=180))
        assert before=={p.name:digest(p) for p in recording.path.iterdir() if p.is_file()}
        maps[identity]=rows
        duration=recording.times[-1]-recording.times[0]
        summaries.append(dict(camera_id=identity,frames=len(rows),temperature_values_checked=len(rows)*49152,
            fps=(len(rows)-1)/duration,duration_s=duration,optical_hashes_checked=len(rows),source_hashes=before))
        print(json.dumps(summaries[-1]),flush=True)
    comparisons=0
    for sample in run['samples']:
        for camera in sample['thermal_lab']['cameras']:
            assert camera['source']=='HARDWARE' and camera['fresh'] and camera['run_id']==run['id']
            row=maps[camera['camera_id']][camera['arrival_sequence']]
            assert camera['measurements']==row['measurements'] and camera['host_monotonic']==row['host_monotonic']
            assert 0<=camera['age_s']<=1
            comparisons+=1
    result=dict(status='PASS',run_id=run['id'],electrical_source='SIMULATION',electrical_samples=len(run['samples']),
                camera_sample_comparisons=comparisons,cameras=summaries,source_files_unchanged=True)
    (args.output/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
