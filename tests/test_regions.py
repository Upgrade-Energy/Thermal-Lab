import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from thermal_lab.regions import polygon_geometry,polygon_pixels,vertices,area_contains,moved,with_vertex
from thermal_lab.workspace import validate_settings,measurement_values,save_settings,read_settings
from thermal_lab.measurement_csv import MeasurementCSV


def polygon(points):
    return dict(id='poly',name='Pack outline',**polygon_geometry([dict(x=x,y=y) for x,y in points]))


class PolygonTests(unittest.TestCase):
    def test_concave_mask_excludes_bounding_box_background_and_is_winding_independent(self):
        p=polygon([(.01,.01),(.99,.01),(.99,.49),(.49,.49),(.49,.99),(.01,.99)])
        expected=tuple(list(range(8))+[8,9,12,13])
        self.assertEqual(polygon_pixels(tuple(vertices(p)),4,4),expected)
        self.assertEqual(polygon_pixels(tuple(reversed(vertices(p))),4,4),expected)
        frame=dict(width=4,height=4,temperatures=list(range(15))+[900])
        value=measurement_values(frame,dict(points=[],areas=[p]))['poly']
        self.assertEqual(value,dict(min=0,mean=70/12,max=13,kind='area'))
        self.assertFalse(area_contains(p,.75,.75));self.assertTrue(area_contains(p,.25,.75))

    def test_pixel_centers_on_polygon_boundary_are_included(self):
        p=polygon([(.125,.125),(.875,.125),(.125,.875)])
        self.assertEqual(polygon_pixels(tuple(vertices(p)),4,4),(0,1,2,3,4,5,6,8,9,12))

    def test_invalid_shapes_rejected_without_modifying_saved_geometry(self):
        for points in [[],[(.1,.1),(.9,.9)],[(.1,.1),(.9,.9),(.1,.9),(.9,.1)],
                       [(0,0),(.5,.5),(.8,.8)],[(.1,.1),(.8,.1),(.1,.1)],
                       [(.1,.1),(.8,.1),(1.2,.8)],[(0,0),(.00001,0),(0,.00001)]]:
            with self.subTest(points=points),self.assertRaises(ValueError):polygon(points)
        p=polygon([(.1,.1),(.9,.1),(.9,.9),(.1,.9)]);original=copy.deepcopy(p)
        with self.assertRaises(ValueError):with_vertex(p,1,.05,.5)
        self.assertEqual(p,original)

    def test_geometry_survives_layout_and_csv_and_move_clamps_all_vertices(self):
        p=polygon([(.1,.1),(.8,.1),(.5,.8)])
        shifted=moved(p,.4,-.8)
        self.assertAlmostEqual(shifted['x2'],.999999999);self.assertEqual(shifted['y'],0)
        self.assertAlmostEqual(shifted['vertices'][0]['x']-p['vertices'][0]['x'],.199999999)
        layout=validate_settings(dict(camera_id='fixture',areas=[p]))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'layout.json';save_settings(path,layout);self.assertEqual(read_settings(path),layout)
            frame=dict(camera_id='fixture',source='SIMULATION',width=256,height=192,
                       temperatures=[22.125]*49152,elapsed_s=1.25,workspace=layout)
            frame['measurements']=measurement_values(frame,layout)
            log=MeasurementCSV(temp);log.write(frame,0);log.close();log.publish()
            with log.path.open(encoding='utf-8-sig',newline='') as stream:row=next(csv.DictReader(stream))
            self.assertEqual(row['shape'],'polygon');self.assertEqual(json.loads(row['vertices']),p['vertices'])
            self.assertEqual(float(row['mean_c']),22.125)

    def test_legacy_rectangle_geometry_and_pixel_inclusion_unchanged(self):
        item=dict(id='box',name='Box',x=.1,y=.1,x2=.5,y2=.5)
        settings=validate_settings(dict(areas=[item]));self.assertEqual(settings['areas'],[item])
        values=measurement_values(dict(width=4,height=4,temperatures=list(range(16))),settings)['box']
        self.assertEqual(values,dict(min=0,mean=5.,max=10,kind='area'))

    def test_polygon_recording_playback_history_and_png_keep_the_actual_outline(self):
        from thermal_lab.thermal import Recorder
        from thermal_lab.playback import Recording,export_history
        from thermal_lab.media_export import export_png
        from PIL import Image
        p=polygon([(.001,.001),(.999,.001),(.999,.499999),(.499999,.499999),(.499999,.999),(.001,.999)])
        settings=validate_settings(dict(camera_id='fixture',areas=[p]))
        temperatures=[21. if x<128 or y<96 else 900. for y in range(192) for x in range(256)]
        temperatures[0]=35.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'session';archive.mkdir()
            recorder=Recorder([],0,compression_level=1,measurement_csv=True);recorder.start(archive/'thermal.jsonl.gz')
            for elapsed in (0.,.04):
                frame=dict(camera_id='fixture',source='SIMULATION',width=256,height=192,
                           temperatures=temperatures,elapsed_s=elapsed,workspace=settings)
                frame['measurements']=measurement_values(frame,settings);recorder.ingest([frame])
            recorder.close();self.assertIsNone(recorder.error);recorder.measurement_csv.publish()
            (archive/'camera-session.json').write_text(json.dumps(dict(camera_id='fixture',source='SIMULATION',status='COMPLETE',frames_written=2)))
            recording=Recording(archive);self.assertEqual(recording.read(0)['workspace'],settings)
            histories=recording.histories();self.assertEqual([s[2] for s in histories[('poly','max')]['samples']],[35.,35.])
            self.assertAlmostEqual(histories[('poly','mean')]['samples'][0][2],21.+14/36864)
            export_history(root/'history.csv',recording,histories)
            with (root/'history.csv').open(encoding='utf-8-sig',newline='') as stream:row=next(csv.DictReader(stream))
            self.assertEqual(json.loads(row['geometry'])['vertices'],p['vertices'])
            for rotation in (0,90,180,270):
                path=root/f'{rotation}.png';meta=export_png(recording,0,path,dict(rotation=rotation))
                self.assertEqual(meta['measurements']['poly']['max'],35.)
                with Image.open(path) as picture:self.assertEqual(picture.size,(768,1024) if rotation in (90,270) else (1024,768))
