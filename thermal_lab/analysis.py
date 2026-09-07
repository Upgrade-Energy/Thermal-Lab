"""Separate, recording-bound offline measurement layouts."""
import hashlib
import json
from pathlib import Path
from .workspace import validate_settings


class Analysis:
    def __init__(self,recording,directory=None):
        self.recording=recording
        digest=hashlib.sha256()
        for name in ('camera-session.json','thermal.idx','thermal.jsonl.gz'):
            digest.update(name.encode())
            with (recording.path/name).open('rb') as source:
                while chunk:=source.read(1024*1024):digest.update(chunk)
        self.fingerprint=digest.hexdigest()
        self.path=Path(directory or Path.home()/'Thermal-Lab-Analysis')/(self.fingerprint+'.json')
        self.settings=validate_settings(dict(camera_id=recording.manifest['camera_id']))
        if self.path.exists():self.settings=self.read(self.path)

    def outside_archive(self,path):
        path=Path(path).resolve()
        if path.is_relative_to(self.recording.path.resolve()):raise ValueError('Save analysis outside the source recording folder')
        return path

    def document(self,settings):
        settings=validate_settings(settings)
        if settings['camera_id']!=self.recording.manifest['camera_id']:raise ValueError('Analysis camera identity differs')
        return dict(schema='thermal-lab-analysis-v1',basis='offline_fixed_geometry_all_frames',
                    recording_sha256=self.fingerprint,settings=settings)

    def read(self,path):
        path=Path(path)
        if path.stat().st_size>1024*1024:raise ValueError('Analysis exceeds 1 MiB')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema')!='thermal-lab-analysis-v1' or data.get('basis')!='offline_fixed_geometry_all_frames' or data.get('recording_sha256')!=self.fingerprint:
            raise ValueError('Analysis belongs to another recording or has an unsupported format')
        return self.document(data['settings'])['settings']

    def update(self,settings):
        data=self.document(settings);path=self.outside_archive(self.path)
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path)
        self.settings=data['settings']

    def save_copy(self,path):
        path=self.outside_archive(path)
        with path.open('x',encoding='utf-8') as stream:json.dump(self.document(self.settings),stream,indent=2,allow_nan=False)
