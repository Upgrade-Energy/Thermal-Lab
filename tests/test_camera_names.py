import tempfile
import unittest
from pathlib import Path
from thermal_lab.camera_names import read_names, save_name, display_name
from thermal_lab.workspace import validate_settings


class CameraNamesTests(unittest.TestCase):
    def test_names_follow_identity_and_preserve_other_cameras(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'names.json'
            save_name(path,'USB-A','Pack front');save_name(path,'USB-B','Pack rear')
            save_name(path,'usb-a','Cell side')
            names=read_names(path)
            self.assertEqual(display_name('USB-A',names),'Cell side')
            self.assertEqual(display_name('usb-b',names),'Pack rear')
            layout=validate_settings(dict(camera_id='USB-A',camera_name='Cell side'))
            self.assertEqual(layout['camera_id'],'USB-A')
            self.assertEqual(layout['camera_name'],'Cell side')
            for bad in ('','x'*61,'bad\nname'):
                with self.assertRaises(ValueError):save_name(path,'USB-A',bad)
            self.assertEqual(read_names(path),names)
