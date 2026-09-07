import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from thermal_lab.playback import Recording,export_history
from thermal_lab.thermal import FRAME_INDEX
from thermal_lab.workspace import validate_settings,measurement_values


class PlaybackTests(unittest.TestCase):
    def test_optical_manifest_and_legacy_compatibility(self):
        from thermal_lab.optical_recording import OpticalRecorder,CODEC,OPTICAL_BYTES,OPTICAL_OFFSET
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);frames=self.fixture(root)
            self.assertIsNone(Recording(root).optical)
            optical=OpticalRecorder(root);entries=[];offset=0
            with (root/'thermal.jsonl.gz').open('wb') as stream:
                for i,frame in enumerate(frames):
                    frame['arrival_sequence']=i+1
                    frame['optical_sha256']=optical.ingest(bytes(OPTICAL_OFFSET+OPTICAL_BYTES),frame['elapsed_s'],i+1)
                    member=gzip.compress(json.dumps([frame]).encode());stream.write(member)
                    entries.append((frame['elapsed_s'],offset,len(member)));offset+=len(member)
            optical.close()
            (root/'thermal.idx').write_bytes(b''.join(FRAME_INDEX.pack(*e) for e in entries))
            manifest=json.loads((root/'camera-session.json').read_text())
            manifest.update(optical_video_recorded=True,optical_codec=CODEC,optical_frames_written=4,optical_width=1024,optical_height=768)
            (root/'camera-session.json').write_text(json.dumps(manifest))
            r=Recording(root);self.assertEqual(r.optical.read(2,r.read(2)),bytes(OPTICAL_BYTES))
            for key,value in [('optical_codec','unknown'),('optical_frames_written',3),('optical_width',256)]:
                (root/'camera-session.json').write_text(json.dumps(dict(manifest,**{key:value})))
                with self.assertRaises(ValueError):Recording(root)

    def fixture(self,root):
        offsets=[];frames=[];offset=0
        with (root/'thermal.jsonl.gz').open('wb') as file:
            for i in range(4):
                settings=validate_settings(dict(camera_id='fixture',points=[] if i==2 else [dict(id='p',name='=Probe' if i<3 else 'Renamed',x=.5 if i<3 else .2,y=.5)]))
                f=dict(camera_id='fixture',source='SIMULATION',unit='C',width=256,height=192,
                       temperatures=[20.+i]*49152,elapsed_s=2+i*.04,workspace=settings)
                f['measurements']=measurement_values(f,settings);frames.append(f)
                raw=gzip.compress(json.dumps([f]).encode());file.write(raw)
                offsets.append((f['elapsed_s'],offset,len(raw)));offset+=len(raw)
        (root/'thermal.idx').write_bytes(b''.join(FRAME_INDEX.pack(*e) for e in offsets))
        (root/'camera-session.json').write_text(json.dumps(dict(camera_id='fixture',source='SIMULATION',status='COMPLETE',frames_written=4)))
        return frames

    def test_seek_frame_values_and_history_geometry_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);frames=self.fixture(root);r=Recording(root)
            self.assertEqual([r.index_at(t) for t in [-1,2.,2.05,999]],[0,0,1,3])
            self.assertEqual(r.read(3),frames[3])
            history=r.histories();samples=history[('p','value')]['samples']
            self.assertEqual([s[0] for s in samples],[0,1,3])
            self.assertEqual([s[2] for s in samples],[20,21,23])
            self.assertNotEqual(samples[1][3],samples[2][3])
            self.assertEqual(history[('p','value')]['name'],'Renamed')
            self.assertIsNone(r.histories(cancelled=lambda:True))
            export_history(root/'history.csv',r,history)
            with (root/'history.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual([float(row['temperature_c']) for row in rows],[20,21,23])
            self.assertTrue(all(row['source']=='SIMULATION' for row in rows))
            with self.assertRaises(FileExistsError):export_history(root/'history.csv',r,history)

    def test_incomplete_truncated_and_wrong_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            m=json.loads((root/'camera-session.json').read_text());m['status']='RECORDING'
            (root/'camera-session.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'COMPLETE'):Recording(root)
            m['status']='COMPLETE';m['camera_id']='other';(root/'camera-session.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'identity'):Recording(root)
            m['camera_id']='fixture';(root/'camera-session.json').write_text(json.dumps(m))
            (root/'thermal.idx').write_bytes((root/'thermal.idx').read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'truncated'):Recording(root)

    def test_corrupt_index_and_measurements_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            index=bytearray((root/'thermal.idx').read_bytes());index[:FRAME_INDEX.size]=FRAME_INDEX.pack(2.,1,100)
            (root/'thermal.idx').write_bytes(index)
            with self.assertRaisesRegex(ValueError,'index'):Recording(root)
            self.fixture(root)
            first=Recording(root).read(0);first['measurements']['p']['value']=999
            member=gzip.compress(json.dumps([first]).encode())
            (root/'thermal.jsonl.gz').write_bytes(member)
            (root/'thermal.idx').write_bytes(FRAME_INDEX.pack(2.,0,len(member)))
            m=json.loads((root/'camera-session.json').read_text());m['frames_written']=1
            (root/'camera-session.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'measurements'):Recording(root)

    def test_csv_formula_names_are_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);r=Recording(root)
            history=r.histories();history[('p','value')]['name']='=1+1'
            export_history(root/'export.csv',r,history)
            with (root/'export.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(rows[0]['latest_name'],"'=1+1")
