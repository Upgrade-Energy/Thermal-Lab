"""Topology-scoped selection hints, never evidence of the opened identity.

Call under the Windows discovery mutex. Native identity must still be verified
before streaming. Prefer unknown indexes over opening another known camera.
"""
import json
import os
from pathlib import Path


def topology(devices):
    return sorted((d['instance_id'].casefold(), (d.get('pdo_name') or '').casefold()) for d in devices)


def ordered_indexes(count, camera_id, hints):
    def priority(index):
        identity=hints.get(str(index))
        return 0 if identity and identity.casefold()==camera_id.casefold() else 1 if identity is None else 2
    return sorted(range(count), key=priority)


class DeviceHints:
    def __init__(self, devices):
        self.path=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Thermal-Lab'/'device-index-hints.json'
        self.topology=topology(devices)
        self.hints={}
        try:
            if self.path.stat().st_size>65536:return
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if value.get('topology')!=[list(v) for v in self.topology]:return
            valid={v[0] for v in self.topology}
            self.hints={str(i):identity for i in range(len(devices))
                        if isinstance(identity:=value.get('hints',{}).get(str(i)),str) and identity.casefold() in valid}
        except (OSError,ValueError,AttributeError,TypeError):pass

    def observe(self,index,identity):
        self.hints={key:value for key,value in self.hints.items() if value.casefold()!=identity.casefold()}
        self.hints[str(index)]=identity
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(topology=self.topology,hints=self.hints)),encoding='utf-8')
        temp.replace(self.path)
