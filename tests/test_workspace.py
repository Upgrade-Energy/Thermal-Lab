import tempfile
import unittest
from pathlib import Path
from thermal_lab.workspace import validate_settings,save_settings,read_settings,measurement_values


class WorkspaceTests(unittest.TestCase):
    def test_duplicate_names_use_stable_ids_and_preserve_geometry(self):
        value=validate_settings(dict(points=[dict(id='a',name='Cell',x=0,y=0),dict(id='b',name='Cell',x=.9,y=.9)]))
        frame=dict(width=2,height=2,temperatures=[20,21,22,23])
        self.assertEqual(measurement_values(frame,value)['a']['value'],20)
        self.assertEqual(measurement_values(frame,value)['b']['value'],23)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'layout.json';save_settings(path,value);self.assertEqual(read_settings(path),value)

    def test_invalid_geometry_rejected_before_display_or_recording(self):
        for item in [dict(id='a',name='bad',x=-.1,y=0),dict(id='a',name='',x=0,y=0),dict(id='a',name='bad',x=1,y=0)]:
            with self.assertRaises(ValueError):validate_settings(dict(points=[item]))
        with self.assertRaises(ValueError):validate_settings(dict(areas=[dict(id='a',name='bad',x=.8,y=.2,x2=.1,y2=.5)]))
        item=dict(id='a',name='same',x=0,y=0)
        with self.assertRaises(ValueError):validate_settings(dict(points=[item,item]))
