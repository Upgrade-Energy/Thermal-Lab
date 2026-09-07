import gzip
import json
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from thermal_lab.acquisition import worker


class PreviewQueue(queue.Queue):
    def cancel_join_thread(self):pass


class AcquisitionTests(unittest.TestCase):
    def run_worker(self, path, fail=False):
        commands=queue.Queue();events=queue.Queue()
        commands.put(dict(action='settings',settings=dict(points=[dict(id='probe',name='Probe',x=.5,y=.5)])))
        commands.put(dict(action='record',path=str(path)))
        class Camera:
            camera_id='synthetic-test-fixture'
            def __init__(self,*_):self.origin=time.monotonic()
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self):
                if fail:raise OSError('Injected camera disconnect')
                commands.put(dict(action='stop'))
                return dict(width=256,height=192,temperatures=[24.5]*49152,
                            camera_id=self.camera_id,elapsed_s=time.monotonic()-self.origin,
                            source='SIMULATION',arrival_sequence=1),bytes(1770496)
        with patch('thermal_lab.acquisition.TC001Max',Camera):
            worker('unused',commands,PreviewQueue(1),events)
        return json.loads((path/'camera-session.json').read_text())

    def test_stop_finalizes_recording_and_preserves_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'recording';manifest=self.run_worker(path)
            self.assertEqual((manifest['status'],manifest['frames_written']),('COMPLETE',1))
            frame=json.loads(gzip.decompress((path/'thermal.jsonl.gz').read_bytes()))[0]
            self.assertEqual(frame['measurements']['probe']['value'],24.5)
            self.assertEqual(frame['workspace']['points'][0]['name'],'Probe')
            self.assertFalse(manifest['optical_video_recorded'])

    def test_camera_failure_cannot_complete_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('thermal_lab.acquisition.traceback.print_exc'):
                manifest=self.run_worker(Path(tmp)/'recording',True)
            self.assertEqual(manifest['status'],'FAILED')
            self.assertIn('disconnect',manifest['error'])
