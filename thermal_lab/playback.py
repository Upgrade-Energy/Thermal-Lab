"""Read-only indexed thermal archives and recorded measurement histories."""
import bisect
import csv
import gzip
import io
import json
import math
from pathlib import Path

from .thermal import FRAME_INDEX, validate_frame
from .workspace import validate_settings, measurement_values
from .optical_recording import OpticalRecording,SUPPORTED_CODECS
from .tracking import geometry_for_history


class Recording:
    def __init__(self, path):
        self.path=Path(path)
        manifest_path=self.path/'camera-session.json'
        if manifest_path.stat().st_size>1024*1024:raise ValueError('Session manifest is too large')
        self.manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(self.manifest,dict) or any(not isinstance(self.manifest.get(key),str) or not self.manifest[key] for key in ('camera_id','source')):
            raise ValueError('Session camera identity and source are required')
        if self.manifest.get('status')!='COMPLETE':
            raise ValueError('Only finalized COMPLETE recordings can be reviewed')
        index_path=self.path/'thermal.idx'
        if index_path.stat().st_size>20_000_000:raise ValueError('Recording index exceeds review limit')
        raw=index_path.read_bytes()
        if not raw or len(raw)%FRAME_INDEX.size:raise ValueError('Missing or truncated frame index')
        self.entries=list(FRAME_INDEX.iter_unpack(raw));self.times=[e[0] for e in self.entries]
        size=(self.path/'thermal.jsonl.gz').stat().st_size;end=0;previous=-math.inf
        for elapsed,offset,length in self.entries:
            if not math.isfinite(elapsed) or elapsed<=previous or offset!=end or not 0<length<=8*1024*1024 or offset+length>size:
                raise ValueError('Invalid recording index: time, offset or length')
            previous=elapsed;end=offset+length
        if end!=size or self.manifest.get('frames_written')!=len(self.entries):
            raise ValueError('Recording count or file size does not match its index')
        self.optical=None
        if self.manifest.get('optical_video_recorded'):
            if self.manifest.get('optical_codec') not in SUPPORTED_CODECS:raise ValueError('Unsupported optical recording format')
            if self.manifest.get('optical_frames_written')!=len(self.entries):raise ValueError('Optical manifest count differs')
            if (self.manifest.get('optical_width'),self.manifest.get('optical_height'))!=(1024,768):raise ValueError('Unsupported optical dimensions')
            self.optical=OpticalRecording(self.path,self.entries,self.manifest['optical_codec'])
        self.read(0)

    def index_at(self, elapsed):
        return max(0,min(len(self.entries)-1,bisect.bisect_right(self.times,elapsed)-1))

    def read(self,index):
        elapsed,offset,length=self.entries[index]
        with (self.path/'thermal.jsonl.gz').open('rb') as source:
            source.seek(offset);member=source.read(length)
        with gzip.GzipFile(fileobj=io.BytesIO(member)) as source:
            raw=source.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:raise ValueError('Decoded frame exceeds review limit')
        frames=json.loads(raw)
        if not isinstance(frames,list) or len(frames)!=1:raise ValueError('Expected one camera per indexed frame')
        frame=validate_frame(frames[0])
        if frame.get('valid',True) is not True:raise ValueError('Frame is explicitly marked invalid')
        if frame.get('elapsed_s')!=elapsed or frame.get('camera_id')!=self.manifest.get('camera_id'):
            raise ValueError('Frame time or camera identity differs from session')
        if frame.get('source')!=self.manifest.get('source') or frame.get('unit','C')!='C':
            raise ValueError('Frame source or unit differs from session')
        if frame['width']!=256 or frame['height']!=192:
            raise ValueError('Review currently supports 256 × 192 thermal frames')
        if 'workspace' in frame:
            settings=validate_settings(frame['workspace'])
            if settings['camera_id']!=frame['camera_id']:raise ValueError('Workspace camera identity mismatch')
            if measurement_values(frame,settings)!=frame.get('measurements'):
                raise ValueError('Recorded measurements differ from numerical pixels')
            frame['workspace']=settings
        return frame

    def histories(self, progress=lambda *_:None, cancelled=lambda:False, settings=None):
        if settings is not None:
            settings=validate_settings(settings)
            if settings['camera_id']!=self.manifest['camera_id']:raise ValueError('Analysis camera identity differs')
        series={};samples=0
        for index in range(len(self.entries)):
            if cancelled():return None
            frame=self.read(index)
            if settings is not None:frame=dict(frame,workspace=settings,measurements=measurement_values(frame,settings))
            definitions={v['id']:v for kind in ('points','areas') for v in frame.get('workspace',{}).get(kind,[])}
            for identifier,values in frame.get('measurements',{}).items():
                definition=definitions.get(identifier,{})
                geometry=json.dumps(geometry_for_history(definition,definitions),sort_keys=True)
                for statistic in ('value','min','mean','max'):
                    if statistic not in values:continue
                    value=values[statistic]
                    if not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Non-finite recorded measurement')
                    key=(identifier,statistic)
                    entry=series.setdefault(key,dict(name=definition.get('name',identifier),samples=[]))
                    entry['name']=definition.get('name',identifier)
                    entry['samples'].append((index,frame['elapsed_s'],value,geometry))
                    if definition.get('tracking'):
                        entry.setdefault('positions',{})[index]={k:values[k] for k in ('x','y','pixel_x','pixel_y','tracking')}
                    samples+=1
                    if samples>2_000_000:raise ValueError('History exceeds two million measurement samples')
            if index%100==0:progress(index+1,len(self.entries))
        progress(len(self.entries),len(self.entries))
        return series


def export_history(path,recording,series,analysis_fingerprint=None):
    # Exclusive creation protects an existing export even when used outside the UI.
    with Path(path).open('x',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream)
        writer.writerow(['camera_id','source','measurement_id','latest_name','statistic','frame_index','elapsed_s','temperature_c','geometry','measurement_basis','recording_sha256','tracking','x','y','pixel_x','pixel_y'])
        def safe(value):
            value=str(value)
            return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
        for (identifier,statistic),entry in series.items():
            for index,elapsed,value,geometry in entry['samples']:
                writer.writerow([safe(recording.manifest['camera_id']),safe(recording.manifest['source']),
                                 safe(identifier),safe(entry['name']),statistic,index,elapsed,value,geometry,
                                 'offline_fixed_geometry_all_frames' if analysis_fingerprint else 'original_recorded',analysis_fingerprint or '']+
                                [entry.get('positions',{}).get(index,{}).get(k,'') for k in ('tracking','x','y','pixel_x','pixel_y')])
