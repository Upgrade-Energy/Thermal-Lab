import queue
import time
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from PIL import Image
from thermal_lab.smart_alignment_tool import SmartAlignmentTool
from thermal_lab.stereo_calibration import save_session,read_session
from test_stereo_calibration import observations
import tempfile
from pathlib import Path


class SmartToolTests(unittest.TestCase):
    def test_camera_identity_freshness_and_frame_copy(self):
        tool=SmartAlignmentTool.__new__(SmartAlignmentTool);tool.camera_id='a'
        d=SimpleNamespace(settings=dict(camera_id='a',alignment={}),frame=dict(temperatures=[25]),optical=Image.new('RGB',(1024,768)),received_at=time.monotonic());tool.desktop=d
        frame,optical,_=tool.fresh_pair();frame['temperatures'][0]=100;optical.putpixel((0,0),(255,0,0))
        self.assertEqual(d.frame['temperatures'],[25]);self.assertEqual(d.optical.getpixel((0,0)),(0,0,0))
        d.received_at-=2
        with self.assertRaisesRegex(ValueError,'STALE'):tool.fresh_pair()
        d.received_at=time.monotonic();d.settings['camera_id']='b'
        with self.assertRaises(ValueError):tool.fresh_pair()

    def test_cancelled_calibration_cannot_save_late_result(self):
        t=SmartAlignmentTool.__new__(SmartAlignmentTool);t.closed=False;t.busy=True;t.continuous=False;t.generation=2
        t.results=queue.Queue();t.results.put((1,'solve',True,{},None));t.window=Mock();t.update_buttons=Mock()
        with patch('thermal_lab.smart_alignment_tool.save_calibration') as save:t.poll();save.assert_not_called()
        self.assertFalse(t.busy)

    def test_capture_session_survives_restart_and_rejects_other_camera(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'camera.json';pairs=observations()[:2]
            save_session(path,'a',pairs,25);loaded,spacing=read_session(path,'a')
            self.assertEqual(loaded,pairs);self.assertEqual(spacing,25)
            with self.assertRaises(ValueError):read_session(path,'b')


if __name__=='__main__':unittest.main()
