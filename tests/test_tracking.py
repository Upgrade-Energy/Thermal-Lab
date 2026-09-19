import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from thermal_lab.workspace import validate_settings, measurement_values
from thermal_lab.tracking import add_tracker, remove_measurement, positioned
from thermal_lab.thermal import Recorder
from thermal_lab.playback import Recording, export_history
from thermal_lab.analysis import Analysis, recording_fingerprint
from thermal_lab.media_export import export_png


def fixture(directory, count=8, tracking=True):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    settings=validate_settings(dict(camera_id='tracking-fixture',camera_name='Moving test targets'))
    if tracking:
        for kind in ('hottest','coldest'):settings,_=add_tracker(settings,kind)
    writer=Recorder([],0,measurement_csv=True);writer.start(directory/'thermal.jsonl.gz')
    for i in range(count):
        values=[22.0]*49152
        values[(40+i)*256+30+i*5]=40+i*.25
        values[(130-i)*256+210-i*5]=10-i*.125
        frame=dict(width=256,height=192,temperatures=values,elapsed_s=i*.1,
                   camera_id='tracking-fixture',source='SIMULATION',workspace=settings)
        frame['measurements']=measurement_values(frame,settings);writer.ingest([frame])
    writer.close()
    if writer.error:raise RuntimeError(writer.error)
    writer.measurement_csv.publish()
    (directory/'camera-session.json').write_text(json.dumps(dict(camera_id='tracking-fixture',source='SIMULATION',
        status='COMPLETE',frames_written=count,optical_video_recorded=False)),encoding='utf-8')
    return settings


class TrackingTests(unittest.TestCase):
    def test_full_image_moves_and_keeps_precision(self):
        settings=validate_settings({})
        settings,hot=add_tracker(settings,'hottest');settings,cold=add_tracker(settings,'coldest')
        for index in (0,3,11):
            values=[20.0]*12;values[index]=31.234375;values[(index+1)%12]=9.109375
            frame=dict(width=4,height=3,temperatures=values)
            found=measurement_values(frame,settings)
            self.assertEqual(found[hot['id']]['value'],31.234375)
            self.assertEqual(found[hot['id']]['pixel_x'],index%4)
            self.assertEqual(found[hot['id']]['pixel_y'],index//4)
            self.assertEqual(found[hot['id']]['x'],(index%4+.5)/4)
            self.assertEqual(found[cold['id']]['value'],9.109375)
            self.assertEqual(positioned(hot,found)['x'],found[hot['id']]['x'])
        self.assertIsNone(positioned(hot,{}))

    def test_region_excludes_extremes_outside_and_follows_edits(self):
        rectangle=dict(id='r',name='Battery',x=.25,y=.25,x2=.5,y2=.5)
        polygon=dict(id='r',name='Battery',shape='polygon',vertices=[dict(x=x,y=y) for x,y in ((.25,.25),(.75,.25),(.25,.75))])
        for area in (rectangle,polygon):
            settings=validate_settings(dict(areas=[area]));settings,hot=add_tracker(settings,'hottest','r',True)
            settings,cold=add_tracker(settings,'coldest',hot['id'],True)
            data=[20.0]*64;data[0]=100;data[-1]=-50;data[3*8+3]=35;data[2*8+2]=12
            found=measurement_values(dict(width=8,height=8,temperatures=data),settings)
            self.assertEqual((found[hot['id']]['value'],found[cold['id']]['value']),(35,12))
            self.assertEqual(found[hot['id']]['region_id'],'r')
            self.assertEqual(found['r']['max'],found[hot['id']]['value'])
            self.assertFalse(remove_measurement(settings,'r')['points'])
        settings['areas']=[dict(rectangle,x=0,y=0,x2=.1,y2=.1)]
        self.assertEqual(measurement_values(dict(width=8,height=8,temperatures=data),settings)[hot['id']]['value'],100)

    def test_ties_keep_both_named_trackers_and_use_first_pixel(self):
        settings=validate_settings({})
        for kind in ('hottest','coldest'):settings,_=add_tracker(settings,kind)
        values=measurement_values(dict(width=4,height=3,temperatures=[20.]*12),settings)
        self.assertEqual(len(values),2)
        self.assertTrue(all(v['pixel_x']==v['pixel_y']==0 for v in values.values()))
        repeated,item=add_tracker(settings,'hottest');self.assertEqual(repeated,settings)
        self.assertEqual(len(repeated['points']),2)

    def test_invalid_definitions_rejected_and_fixed_points_unchanged(self):
        settings=validate_settings(dict(points=[dict(id='p',name='Fixed',x=.5,y=.5)]))
        self.assertEqual(measurement_values(dict(width=2,height=2,temperatures=[1,2,3,4]),settings),{'p':dict(value=4,kind='point')})
        for extra in (dict(tracking='warm'),dict(region_id='r'),dict(tracking='hottest',region_id='missing')):
            with self.assertRaises(ValueError):validate_settings(dict(points=[dict(settings['points'][0],**extra)]))
        with self.assertRaises(ValueError):add_tracker(settings,'hottest',selected_region=True)

    def test_recording_csv_history_and_media_keep_dynamic_positions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);settings=fixture(root/'recording');recording=Recording(root/'recording')
            hot,cold=settings['points'];history=recording.histories()
            samples=history[(hot['id'],'value')]['samples']
            self.assertEqual([s[2] for s in samples],[40+i*.25 for i in range(8)])
            self.assertEqual(len({s[3] for s in samples}),1,'Movement must not split history curves')
            positions=history[(hot['id'],'value')]['positions']
            self.assertEqual([p['pixel_x'] for p in positions.values()],[30+i*5 for i in range(8)])
            with (recording.path/'measurements.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),16)
            for row in rows:
                f=recording.read(int(row['frame_index']));value=f['measurements'][row['measurement_id']]
                for field in ('x','y','pixel_x','pixel_y'):self.assertEqual(float(row[field]),value[field])
                self.assertEqual(float(row['value_c']),value['value'])
            export_history(root/'history.csv',recording,history)
            with (root/'history.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual([int(r['pixel_x']) for r in rows[:8]],[30+i*5 for i in range(8)])
            meta=export_png(recording,7,root/'frame.png',dict(rotation=90))
            self.assertEqual(meta['measurements'][hot['id']]['pixel_x'],65)
            self.assertEqual(meta['measurements'][cold['id']]['pixel_y'],123)

    def test_offline_tracking_old_recording_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root/'recording',tracking=False);recording=Recording(root/'recording')
            fingerprint=recording_fingerprint(recording);analysis=Analysis(recording,root/'analysis')
            settings,hot=add_tracker(analysis.settings,'hottest');analysis.update(settings)
            self.assertEqual(analysis.read(analysis.path),settings)
            self.assertEqual(len(recording.histories(settings=settings)[(hot['id'],'value')]['samples']),8)
            self.assertEqual(recording_fingerprint(recording),fingerprint)
            self.assertFalse(recording.read(7)['measurements'])

    def test_region_geometry_change_splits_history_but_rename_does_not(self):
        from thermal_lab.tracking import geometry_for_history
        settings=validate_settings(dict(areas=[dict(id='r',name='Region',x=.1,y=.1,x2=.5,y2=.5)]))
        settings,hot=add_tracker(settings,'hottest','r',True)
        definitions={item['id']:item for group in ('points','areas') for item in settings[group]}
        original=geometry_for_history(hot,definitions)
        definitions['r']['name']='Renamed'
        self.assertEqual(geometry_for_history(hot,definitions),original)
        definitions['r']['x2']=.8
        self.assertNotEqual(geometry_for_history(hot,definitions),original)
