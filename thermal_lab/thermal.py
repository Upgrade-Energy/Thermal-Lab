"""Radiometric frames, named measurement points/areas and bounded asynchronous recording.

Camera frames carry explicit hardware/import/simulation provenance.
This module has no dependency on Power Lab or instrument control.
"""
import gzip
import copy
import json
import math
import queue
import struct
import threading
from collections import deque
from .validation import ValidationError, finite
from .validation import integer
from .regions import polygon_pixels, vertices

WIDTH,HEIGHT=32,24
FRAME_INDEX=struct.Struct('<dQI') # elapsed seconds, compressed byte offset, member length

def validate_frame(frame):
    w=integer(frame.get('width'),'Frame width',1,1024);h=integer(frame.get('height'),'Frame height',1,1024)
    if len(frame.get('temperatures',[]))!=w*h:raise ValidationError('Radiometric frame size mismatch')
    values=[finite(v,'Pixel temperature',-100,1000) for v in frame['temperatures']]
    return dict(frame,width=w,height=h,temperatures=values)

def measurements(frame,camera):
    w,h=frame['width'],frame['height'];values=frame['temperatures'];out={}
    def xy(x,y):return min(w-1,int(x*w)),min(h-1,int(y*h))
    for p in camera['points']:
        if p.get('tracking'):continue
        x,y=xy(p['x'],p['y']);out[p['name']]=dict(value=values[y*w+x],kind='point')
    for p in camera['areas']:
        if p.get('shape')=='polygon':
            block=[values[i] for i in polygon_pixels(tuple(vertices(p)),w,h)]
            if not block:raise ValidationError('Polygon contains no thermal pixel centers')
        else:
            x,y=xy(p['x'],p['y']);x2,y2=xy(p['x2'],p['y2'])
            block=[values[v*w+u] for v in range(y,y2+1) for u in range(x,x2+1)]
        out[p['name']]=dict(min=min(block),mean=sum(block)/len(block),max=max(block),kind='area')
    if any(p.get('tracking') for p in camera['points']):
        from .tracking import tracked_values
        out.update(tracked_values(frame,camera['points'],camera['areas']))
    return out

def simulation_frame(camera,index,elapsed,temperature):
    vals=[]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            inside=5<x<27 and 3<y<21
            heat=math.exp(-((x-18-index*2)**2+(y-11)**2)/28)
            vals.append(round((temperature if inside else 22)+heat*(4+index)+.1*math.sin(elapsed+x/4),2))
    f=dict(camera_id=camera['id'],width=WIDTH,height=HEIGHT,temperatures=vals,elapsed_s=elapsed,source='SIMULATION',timestamp_basis='simulated_host_monotonic',valid=True)
    f['measurements']=measurements(f,camera)
    return f

class Recorder:
    """One recorder thread, bounded queue. Disk/queue failures become visible faults."""
    def __init__(self,cameras,pre_s,compression_level=9,measurement_csv=False):
        self.compression_level=integer(compression_level,'Compression level',0,9)
        self.cameras=cameras;self.buffer=deque(maxlen=max(1,math.ceil(pre_s*2)+1))
        self.frames=[];self.file=None;self.worker=None;self.error=None;self.count=0
        self.q=queue.Queue(maxsize=120);self.closed=False;self.lock=threading.Lock()
        self.write_measurement_csv=measurement_csv;self.measurement_csv=None
    def preview(self,elapsed,temp):
        frames=[simulation_frame(c,i,elapsed,temp) for i,c in enumerate(self.cameras)]
        return self.ingest(frames)
    def ingest(self,frames):
        """Record supplied numerical frames; never substitute simulated pixels.

        elapsed_s describes the caller's explicitly declared recording timeline.
        Hardware adapters must preserve capture/arrival timestamp provenance.
        Copy before queueing so acquisition buffer reuse cannot corrupt records.
        """
        if self.closed:raise RuntimeError('Thermal recorder is closed')
        if self.error:raise OSError(self.error)
        # validate_frame already copies every temperature value. Deep-copy only
        # metadata to avoid a second full-resolution pixel copy on the hot path.
        frames=[validate_frame(dict(copy.deepcopy({k:v for k,v in f.items() if k!='temperatures'}),
                                    temperatures=f.get('temperatures',[]))) for f in frames]
        for frame in frames:
            frame['elapsed_s']=finite(frame.get('elapsed_s'),'Thermal elapsed time',-1e12,1e12)
            if not frame.get('camera_id') or not frame.get('source'):
                raise ValidationError('Thermal camera identity and source are required')
        self.frames=frames
        if self.worker:
            self._enqueue(frames)
        else:self.buffer.append(frames)
        return frames
    def start(self,path):
        if self.closed or self.worker:raise RuntimeError('Thermal recorder cannot be restarted')
        self.file=open(path,'wb')
        try:
            self.index_file=open(path.with_name('thermal.idx'),'wb')
            if self.write_measurement_csv:
                from .measurement_csv import MeasurementCSV
                self.measurement_csv=MeasurementCSV(path.parent)
        except Exception:
            self.file.close()
            if hasattr(self,'index_file'):self.index_file.close()
            raise
        self.worker=threading.Thread(target=self._write,name='Thermal recorder',daemon=True);self.worker.start()
        for frames in self.buffer:self._enqueue(frames)
        self.buffer.clear()
    def _enqueue(self,frames):
        if self.error:raise OSError(self.error)
        try:self.q.put_nowait(frames)
        except queue.Full:
            self.error='Thermal recorder queue full; frames were not silently dropped'
            raise OSError(self.error) from None
    def _write(self):
        try:
            while True:
                frames=self.q.get()
                if frames is None:break
                # Concatenated gzip members remain readable as a normal gzip stream,
                # while an index allows constant-memory random access for playback.
                member=gzip.compress((json.dumps(frames,allow_nan=False,separators=(',',':'))+'\n').encode(),compresslevel=self.compression_level,mtime=0)
                offset=self.file.tell();self.file.write(member);self.file.flush()
                if frames:
                    self.index_file.write(FRAME_INDEX.pack(frames[0]['elapsed_s'],offset,len(member)));self.index_file.flush()
                if self.measurement_csv:
                    for index,frame in enumerate(frames,self.count):self.measurement_csv.write(frame,index)
                self.count+=len(frames)
        except Exception as exc:self.error='Thermal recording failed: '+str(exc)
        finally:
            for stream in (self.file,self.index_file,self.measurement_csv):
                if stream is not None:
                    try:stream.close()
                    except Exception as exc:self.error='Thermal file finalization failed: '+str(exc)
    def close(self):
        if self.closed:return
        self.closed=True
        if self.worker:
            try:self.q.put(None,timeout=1)
            except queue.Full:self.error='Thermal finalization queue timeout'
            self.worker.join(timeout=3)
            if self.worker.is_alive():self.error='Thermal recorder did not finalize within deadline'
