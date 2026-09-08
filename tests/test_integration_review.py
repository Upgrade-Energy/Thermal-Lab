import base64
import gzip
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from PIL import Image
from thermal_lab.integration_review import camera_view
from thermal_lab.thermal import FRAME_INDEX
from thermal_lab.workspace import validate_settings, measurement_values


class IntegrationReviewTests(unittest.TestCase):
    def test_persisted_run_seek_uses_common_time_and_retains_numbers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve(); uid='a'*32; folder=root/uid/'camera0';folder.mkdir(parents=True)
            settings=validate_settings(dict(camera_id='camera',points=[dict(id='p',name='Probe',x=.5,y=.5)]))
            index=[]; offset=0
            with (folder/'thermal.jsonl.gz').open('wb') as stream:
                for i in range(3):
                    f=dict(camera_id='camera',source='SIMULATION',width=256,height=192,unit='C',
                        temperatures=[20.+i]*49152,workspace=settings,elapsed_s=i*.04,run_elapsed_s=2+i*.04,run_id=uid)
                    f['measurements']=measurement_values(f,settings)
                    raw=gzip.compress(json.dumps([f]).encode());stream.write(raw)
                    index.append(FRAME_INDEX.pack(f['elapsed_s'],offset,len(raw)));offset+=len(raw)
            (folder/'thermal.idx').write_bytes(b''.join(index))
            manifest=dict(status='COMPLETE',frames_written=3,camera_id='camera',source='SIMULATION',run_id=uid)
            (folder/'camera-session.json').write_text(json.dumps(manifest))
            service=SimpleNamespace(recordings=root)
            request=dict(run_id=uid,camera_id='camera',elapsed_s=2.05)
            result=camera_view(service,request)
            self.assertEqual(result['frame_index'],1)
            self.assertEqual(result['frame']['elapsed_s'],2.04)
            self.assertEqual(result['frame']['temperatures'],[21.]*49152)
            self.assertAlmostEqual(result['time_difference_s'],-.01)
            image=Image.open(io.BytesIO(base64.b64decode(result['image'].split(',')[1])))
            self.assertEqual(image.size,(1024,768))
            self.assertEqual(camera_view(service,dict(request,elapsed_s=-10))['frame_index'],0)
            self.assertEqual(camera_view(service,dict(request,elapsed_s=100))['frame_index'],2)
            for bad in [dict(run_id='../bad'),dict(elapsed_s=float('nan')),dict(camera_id='other'),dict(mode='bogus')]:
                with self.assertRaises(ValueError):camera_view(service,dict(request,**bad))
            manifest['status']='RECORDING';(folder/'camera-session.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'COMPLETE'):camera_view(service,request)
