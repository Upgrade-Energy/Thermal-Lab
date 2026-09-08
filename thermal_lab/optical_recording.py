"""Lossless indexed optical frames, paired with thermal frames by host arrival.

This is an app-native video archive, not an MP4 or exposure-sync guarantee.
"""
import hashlib
from pathlib import Path
import queue
import struct
import threading
import zlib

OPTICAL_OFFSET=197632
OPTICAL_BYTES=1024*768*2
OPTICAL_INDEX=struct.Struct('<dQQI32s')
RAW_CODEC='raw-yuyv422-v1'
ZLIB_CODEC='zlib-yuyv422-v1'
CODEC='lz4-yuyv422-v1'
SUPPORTED_CODECS=(RAW_CODEC,ZLIB_CODEC,CODEC)


class OpticalRecorder:
    def __init__(self,path,codec=CODEC):
        if codec not in SUPPORTED_CODECS:raise ValueError('Unsupported optical recording format')
        self.codec=codec
        if codec==CODEC:
            import lz4.block
            self.compress=lambda plane:lz4.block.compress(plane,store_size=False)
        elif codec==ZLIB_CODEC:self.compress=lambda plane:zlib.compress(plane,1)
        else:self.compress=lambda plane:plane
        self.path=Path(path);self.count=0;self.error=None;self.closed=False
        self.q=queue.Queue(16)
        self.data=(self.path/'optical.bin').open('xb')
        try:self.index=(self.path/'optical.idx').open('xb')
        except Exception:self.data.close();raise
        self.thread=threading.Thread(target=self._write,daemon=True,name='Optical recording');self.thread.start()

    def ingest(self,raw,elapsed,sequence):
        if self.closed:raise RuntimeError('Optical recorder is closed')
        if self.error:raise OSError(self.error)
        plane=raw[OPTICAL_OFFSET:]
        if len(plane)!=OPTICAL_BYTES:raise ValueError('Optical frame size mismatch')
        digest=hashlib.sha256(plane).digest()
        try:self.q.put_nowait((plane,elapsed,sequence,digest))
        except queue.Full:
            self.error='Optical recording queue full; session is incomplete'
            raise OSError(self.error) from None
        return digest.hex()

    def _write(self):
        try:
            while True:
                sample=self.q.get()
                if sample is None:break
                plane,elapsed,sequence,digest=sample
                payload=self.compress(plane)
                offset=self.data.tell()
                self.data.write(payload);self.data.flush()
                self.index.write(OPTICAL_INDEX.pack(elapsed,sequence,offset,len(payload),digest));self.index.flush()
                self.count+=1
        except Exception as exc:self.error='Optical recording failed: '+str(exc)
        finally:
            try:self.data.close();self.index.close()
            except Exception as exc:self.error='Optical finalization failed: '+str(exc)

    def close(self):
        if self.closed:return
        self.closed=True
        try:self.q.put(None,timeout=1)
        except queue.Full:self.error='Optical finalization queue timeout'
        self.thread.join(timeout=3)
        if self.thread.is_alive():self.error='Optical writer did not finalize within deadline'


class OpticalRecording:
    def __init__(self,path,thermal_entries,codec=CODEC):
        if codec not in SUPPORTED_CODECS:raise ValueError('Unsupported optical recording format')
        self.codec=codec
        self.path=Path(path);index_path=self.path/'optical.idx'
        if index_path.stat().st_size!=len(thermal_entries)*OPTICAL_INDEX.size:raise ValueError('Optical and thermal frame counts differ')
        raw=index_path.read_bytes()
        self.entries=list(OPTICAL_INDEX.iter_unpack(raw));size=(self.path/'optical.bin').stat().st_size
        end=0;previous=-1
        for optical,thermal in zip(self.entries,thermal_entries):
            elapsed,sequence,offset,length,_=optical
            valid_length=length==OPTICAL_BYTES if codec==RAW_CODEC else 0<length<=OPTICAL_BYTES+65536
            if elapsed!=thermal[0] or sequence<=previous or offset!=end or not valid_length or offset+length>size:
                raise ValueError('Invalid optical pairing/index')
            end=offset+length;previous=sequence
        if end!=size:raise ValueError('Optical file size differs from index')

    def read(self,index,frame):
        elapsed,sequence,offset,length,digest=self.entries[index]
        if elapsed!=frame['elapsed_s'] or sequence!=frame['arrival_sequence'] or digest.hex()!=frame.get('optical_sha256'):
            raise ValueError('Optical frame does not match thermal frame')
        with (self.path/'optical.bin').open('rb') as source:source.seek(offset);plane=source.read(length)
        if self.codec==CODEC:
            import lz4.block
            try:plane=lz4.block.decompress(plane,uncompressed_size=OPTICAL_BYTES)
            except lz4.block.LZ4BlockError as exc:raise ValueError('Optical frame is corrupt') from exc
        elif self.codec==ZLIB_CODEC:
            try:
                decoder=zlib.decompressobj()
                plane=decoder.decompress(plane,OPTICAL_BYTES+1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Optical frame is corrupt')
            except zlib.error as exc:raise ValueError('Optical frame is corrupt') from exc
        if len(plane)!=OPTICAL_BYTES or hashlib.sha256(plane).digest()!=digest:
            raise ValueError('Optical frame is corrupt')
        return plane
