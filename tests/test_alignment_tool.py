"""State guards without acquiring a camera or driving a desktop window."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from thermal_lab.alignment_tool import AlignmentTool


class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value


class AlignmentToolTests(unittest.TestCase):
    def tool(self):
        t=AlignmentTool.__new__(AlignmentTool)
        t.camera_id='camera-a';t.base=dict(dx=0,dy=0,scale=1,angle=0)
        t.candidate=dict(dx=12,dy=-5,scale=1.2,angle=2);t.verified=True;t.searching=False;t.message=Value('')
        t.desktop=SimpleNamespace(settings=dict(camera_id='camera-a',alignment=dict(t.base),points=[dict(x=10,y=20)],areas=[]),
            locked=Value(False),sync_alignment=Mock(),changed=Mock(),render=Mock())
        return t

    def test_apply_preserves_measurements_and_updates_display(self):
        t=self.tool();points=copy.deepcopy(t.desktop.settings['points']);t.apply()
        self.assertEqual(t.desktop.settings['alignment'],t.candidate)
        self.assertEqual(t.desktop.settings['points'],points)
        t.desktop.changed.assert_called_once();t.desktop.render.assert_called_once()

    def test_locked_stale_camera_changed_alignment_and_uncertain_guards(self):
        for mode in ('locked','camera','alignment','uncertain','searching'):
            t=self.tool()
            if mode=='locked':t.desktop.locked.set(True)
            if mode=='camera':t.desktop.settings['camera_id']='camera-b'
            if mode=='alignment':t.desktop.settings['alignment']['dx']=5
            if mode=='uncertain':t.verified=False
            if mode=='searching':t.searching=True
            before=copy.deepcopy(t.desktop.settings);t.apply()
            self.assertEqual(t.desktop.settings,before);t.desktop.changed.assert_not_called()

    def test_profile_preview_clears_previous_target_guidance(self):
        t=self.tool();t.frame={};t.guided_seed=dict(t.candidate);t.optical_region=[.1,.1,.5,.5];t.guide=Value(True)
        t.profile_choice=Value('Far');t.name=Value('');t.distance=Value('');t.buttons=Mock();t.draw=Mock()
        t.profiles=dict(profiles=[dict(name='Far',alignment=dict(t.base),region=[.2,.2,.8,.8],distance_m=3)])
        t.load_profile();self.assertIsNone(t.guided_seed);self.assertIsNone(t.optical_region);self.assertFalse(t.guide.get())
        self.assertEqual(t.distance.get(),'3');t.desktop.changed.assert_not_called()


if __name__=='__main__':unittest.main()
