import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from thermal_lab.tc001_max import TC001Max
from thermal_lab.desktop import Desktop
from thermal_lab.workspace import validate_settings, save_settings
from thermal_lab.device_hints import DeviceHints,ordered_indexes


class MultipleCameraTests(unittest.TestCase):
    def test_verified_hint_prevents_opening_other_camera_first(self):
        self.assertEqual(ordered_indexes(2,'b',{'0':'a'}),[1,0])
        self.assertEqual(ordered_indexes(2,'B',{'0':'a','1':'b'}),[1,0])
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',{'LOCALAPPDATA':folder}):
            devices=[dict(instance_id='a',pdo_name='pdo1'),dict(instance_id='b',pdo_name='pdo2')]
            hints=DeviceHints(devices);hints.observe(0,'a');hints.observe(1,'b')
            self.assertEqual(DeviceHints(devices).hints,{'0':'a','1':'b'})
            devices[0]['pdo_name']='new-pdo'
            self.assertEqual(DeviceHints(devices).hints,{})

    def test_startup_retries_are_bounded_and_stop_after_first_good_frame(self):
        camera=TC001Max('.',camera_id='fixture')
        with patch.object(camera,'_read',side_effect=[OSError('startup'),('frame','raw'),OSError('disconnect')]), \
             patch.object(camera,'close') as close, patch.object(camera,'__enter__') as enter, \
             patch('thermal_lab.tc001_max.time.sleep'):
            self.assertEqual(camera.read(),('frame','raw'))
            self.assertEqual(camera.startup_retries,1)
            with self.assertRaisesRegex(OSError,'disconnect'):camera.read()
            self.assertEqual(close.call_count,1)
            self.assertEqual(enter.call_count,1)
        camera=TC001Max('.')
        with patch.object(camera,'_read',side_effect=OSError('bad')), \
             patch.object(camera,'close'), patch.object(camera,'__enter__'), \
             patch('thermal_lab.tc001_max.time.sleep'):
            with self.assertRaises(OSError):camera.read()
            self.assertEqual(camera.startup_retries,2)

    def test_layouts_stay_with_physical_identity_after_selection_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop=object.__new__(Desktop)
            desktop.args=SimpleNamespace(workspace=Path(folder)/'layout.json')
            desktop.name=Mock();desktop.sync_alignment=Mock();desktop.refresh_rows=Mock()
            desktop.settings=validate_settings(dict(camera_id='camera-A',points=[dict(id='a',name='Probe A',x=.2,y=.3)]))
            desktop.prepare_camera_layout('camera-A')
            first_path=desktop.workspace_path
            save_settings(first_path,desktop.settings)
            desktop.prepare_camera_layout('camera-B')
            self.assertEqual(desktop.settings['points'],[])
            self.assertNotEqual(desktop.workspace_path,first_path)
            desktop.prepare_camera_layout('CAMERA-a')
            self.assertEqual(desktop.workspace_path,first_path)
            self.assertEqual(desktop.settings['points'][0]['name'],'Probe A')
