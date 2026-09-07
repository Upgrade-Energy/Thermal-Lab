import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from thermal_lab.analysis import Analysis
from thermal_lab.playback import Recording,export_history
from thermal_lab.thermal import FRAME_INDEX
from thermal_lab.workspace import validate_settings,measurement_values


class AnalysisTests(unittest.TestCase):
    def test_review_mapping_all_rotations_and_region_move(self):
        from types import SimpleNamespace
        from thermal_lab.review import Review
        from thermal_lab.imaging import sensor_to_view
        review=Review.__new__(Review)
        for rotation in (0,90,180,270):
            review.rotation=SimpleNamespace(get=lambda:rotation)
            w,h=(192,256) if rotation in (90,270) else (256,192)
            review.position=(10,20,2,w,h)
            vx,vy=sensor_to_view(64,48,rotation)
            self.assertEqual(review.sensor(SimpleNamespace(x=10+vx*2,y=20+vy*2)),(.25,.25))
            self.assertIsNone(review.sensor(SimpleNamespace(x=9,y=20)))
        review.rotation=SimpleNamespace(get=lambda:0);review.position=(0,0,1,256,192)
        settings=self.settings();region=settings['areas'][0]
        review.analysis=SimpleNamespace(settings=settings);review.drag=('move',(.25,.25),region.copy())
        review.canvas=SimpleNamespace(delete=lambda *_:None);result=[];review.edited=result.append
        review.release(SimpleNamespace(x=250,y=190))
        moved=result[0]['areas'][0]
        self.assertAlmostEqual(moved['x2']-moved['x'],.25)
        self.assertAlmostEqual(moved['y2']-moved['y'],.25)
        self.assertAlmostEqual(moved['x2'],.999999999)
        self.assertAlmostEqual(moved['y2'],.999999999)

    def fixture(self,path):
        path.mkdir();entries=[];offset=0
        with (path/'thermal.jsonl.gz').open('wb') as stream:
            for i in range(3):
                settings=validate_settings(dict(camera_id='fixture'))
                frame=dict(camera_id='fixture',source='SIMULATION',width=256,height=192,
                           temperatures=[20+i+x/256+y/192 for y in range(192) for x in range(256)],elapsed_s=i*.04,workspace=settings,measurements={})
                member=gzip.compress(json.dumps([frame]).encode());stream.write(member)
                entries.append((i*.04,offset,len(member)));offset+=len(member)
        (path/'thermal.idx').write_bytes(b''.join(FRAME_INDEX.pack(*e) for e in entries))
        (path/'camera-session.json').write_text(json.dumps(dict(camera_id='fixture',source='SIMULATION',status='COMPLETE',frames_written=3)))
        return Recording(path)

    def settings(self):
        return validate_settings(dict(camera_id='fixture',points=[dict(id='p',name='Probe',x=.5,y=.5)],areas=[dict(id='r',name='Region',x=.25,y=.25,x2=.5,y2=.5)]))

    def test_reanalysis_history_values_and_source_immutability(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.fixture(root/'source')
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in r.path.iterdir()}
            analysis=Analysis(r,root/'analyses');analysis.update(self.settings())
            history=r.histories(settings=analysis.settings)
            self.assertEqual([v[2] for v in history[('p','value')]['samples']],[21,22,23])
            self.assertEqual([v[2] for v in history[('r','min')]['samples']],[20.5,21.5,22.5])
            moved=self.settings();moved['points'][0]['x']=0
            analysis.update(moved)
            self.assertEqual([v[2] for v in r.histories(settings=moved)[('p','value')]['samples']],[20.5,21.5,22.5])
            self.assertEqual(r.histories(),{})
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in r.path.iterdir()})
            self.assertEqual(Analysis(r,root/'analyses').settings,moved)

    def test_binding_exports_and_archive_write_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.fixture(root/'source');analysis=Analysis(r,root/'analyses');analysis.update(self.settings())
            analysis.save_copy(root/'copy.json');self.assertEqual(analysis.read(root/'copy.json'),analysis.settings)
            with self.assertRaises(FileExistsError):analysis.save_copy(root/'copy.json')
            with self.assertRaisesRegex(ValueError,'outside'):analysis.save_copy(r.path/'analysis.json')
            other=json.loads((root/'copy.json').read_text());other['recording_sha256']='0'*64
            (root/'other.json').write_text(json.dumps(other))
            with self.assertRaisesRegex(ValueError,'another'):analysis.read(root/'other.json')
            export_history(root/'history.csv',r,r.histories(settings=analysis.settings),analysis.fingerprint)
            with (root/'history.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),12)
            self.assertTrue(all(v['measurement_basis']=='offline_fixed_geometry_all_frames' and v['recording_sha256']==analysis.fingerprint for v in rows))

    def test_invalid_camera_or_geometry_never_replaces_saved_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.fixture(root/'source');analysis=Analysis(r,root/'analyses');analysis.update(self.settings())
            original=analysis.path.read_bytes();bad=self.settings();bad['camera_id']='other'
            with self.assertRaises(ValueError):analysis.update(bad)
            bad=self.settings();bad['areas'][0]['x2']=0
            with self.assertRaises(ValueError):analysis.update(bad)
            self.assertEqual(analysis.path.read_bytes(),original)
            with self.assertRaises(ValueError):r.histories(settings=dict(camera_id='other'))
