import csv
import gzip
import json
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from thermal_lab.acquisition import worker
from thermal_lab.measurement_csv import MeasurementCSV
from thermal_lab.workspace import validate_settings, measurement_values
from tests import test_acquisition


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


class MeasurementCSVTests(unittest.TestCase):
    def test_csv_preserves_names_duplicate_ids_geometry_and_numerical_precision(self):
        with tempfile.TemporaryDirectory() as temp:
            layout=validate_settings(dict(camera_id='fixture',camera_name='Front Ω',
                points=[dict(id='p',name='=Terminal, A',x=.5,y=.5)],
                areas=[dict(id='r',name='=Terminal, A',x=0,y=0,x2=.99,y2=.99)]))
            frame=dict(camera_id='fixture',source='SIMULATION',elapsed_s=.04,width=2,height=2,
                       temperatures=[-2.125,12.25,23.5,42.015625],workspace=layout,workspace_revision=2,
                       run_id='a'*32,run_elapsed_s=1.04)
            frame['measurements']=measurement_values(frame,layout)
            log=MeasurementCSV(temp);log.write(frame,0);log.close();log.publish()
            data=rows(log.path)
            self.assertEqual([r['measurement_id'] for r in data],['p','r'])
            self.assertTrue(all(r['measurement_name']=="'=Terminal, A" for r in data))
            self.assertEqual(data[0]['camera_name'],'Front Ω')
            self.assertEqual(float(data[0]['value_c']),42.015625)
            self.assertEqual([float(data[1][k]) for k in ('min_c','mean_c','max_c')],[-2.125,18.91015625,42.015625])
            self.assertEqual(data[1]['x2'],'0.99');self.assertEqual(data[0]['x2'],'')
            self.assertEqual(data[0]['run_elapsed_s'],'1.04');self.assertEqual(log.frames,1)
            self.assertFalse((Path(temp)/'measurements.partial.csv').exists())
            with self.assertRaises(FileExistsError):log.publish()

    def test_record_stop_boundaries_and_per_frame_renames_across_two_sessions(self):
        with tempfile.TemporaryDirectory() as temp:
            first=Path(temp)/'first';second=Path(temp)/'second'
            commands=queue.Queue();events=queue.Queue()
            initial=dict(points=[dict(id='p',name='Terminal',x=.5,y=.5)],
                         areas=[dict(id='r',name='Pack',x=.1,y=.1,x2=.3,y2=.3)])
            changed=dict(points=[dict(id='p',name='Terminal after move',x=.2,y=.5)],areas=[])
            commands.put(dict(action='settings',settings=initial))
            class Camera:
                camera_id='fixture'
                def __init__(self,*_):self.origin=time.monotonic();self.reads=0
                def __enter__(self):return self
                def __exit__(self,*_):pass
                def read(self):
                    self.reads+=1
                    if self.reads==1:commands.put(dict(action='record',path=str(first)))
                    elif self.reads==2:commands.put(dict(action='settings',settings=changed))
                    elif self.reads==3:commands.put(dict(action='finish'))
                    elif self.reads==4:commands.put(dict(action='record',path=str(second)))
                    elif self.reads==5:commands.put(dict(action='stop'))
                    return dict(camera_id=self.camera_id,source='SIMULATION',width=256,height=192,
                                temperatures=[20.+self.reads]*49152,elapsed_s=self.reads*.04,
                                arrival_sequence=self.reads),bytes(1770496)
            with patch('thermal_lab.acquisition.TC001Max',Camera):
                worker('unused',commands,test_acquisition.PreviewQueue(1),events)
            for path,sequences,expected_rows in [(first,[2,3],3),(second,[5],1)]:
                manifest=json.loads((path/'camera-session.json').read_text())
                self.assertEqual(manifest['status'],'COMPLETE')
                self.assertEqual(manifest['measurement_csv_status'],'COMPLETE')
                self.assertEqual(manifest['measurement_csv_frames'],len(sequences))
                self.assertEqual(manifest['measurement_csv_rows'],expected_rows)
                frames=[json.loads(line)[0] for line in gzip.decompress((path/'thermal.jsonl.gz').read_bytes()).splitlines()]
                self.assertEqual([f['arrival_sequence'] for f in frames],sequences)
                data=rows(path/'measurements.csv');self.assertEqual(len(data),expected_rows)
                for row in data:
                    frame=frames[int(row['frame_index'])]
                    self.assertEqual(float(row['elapsed_s']),frame['elapsed_s'])
                    self.assertEqual(float(row['value_c'] or row['mean_c']),frame['temperatures'][0])
                self.assertFalse((path/'measurements.partial.csv').exists())
            data=rows(first/'measurements.csv')
            self.assertEqual([r['measurement_name'] for r in data],['Terminal','Pack','Terminal after move'])
            self.assertEqual([r['x'] for r in data],['0.5','0.1','0.2'])
            finished=[]
            while not events.empty():
                event=events.get()
                if event['kind']=='recording_finished':finished.append(event)
            self.assertEqual([e['measurement_csv'] for e in finished],[str(p/'measurements.csv') for p in (first,second)])

    def test_no_measurements_still_counts_frames_without_inventing_values(self):
        with tempfile.TemporaryDirectory() as temp:
            log=MeasurementCSV(temp)
            log.write(dict(workspace=validate_settings({})),0)
            log.close();log.publish()
            self.assertEqual((log.frames,log.rows),(1,0));self.assertEqual(rows(log.path),[])

    def test_csv_disk_failure_and_camera_failure_do_not_publish_complete_csv(self):
        for failure in ('csv','camera'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'recording'
                with patch('thermal_lab.acquisition.traceback.print_exc'):
                    if failure=='csv':
                        with patch.object(MeasurementCSV,'write',side_effect=OSError('CSV disk failure')):
                            manifest=test_acquisition.AcquisitionTests().run_worker(path)
                        self.assertIn('CSV disk failure',manifest['error'])
                    else:manifest=test_acquisition.AcquisitionTests().run_worker(path,'after-frame')
                self.assertEqual(manifest['status'],'FAILED')
                self.assertEqual(manifest['measurement_csv_status'],'INCOMPLETE')
                self.assertFalse((path/'measurements.csv').exists())
                self.assertTrue((path/'measurements.partial.csv').exists())
