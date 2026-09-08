"""State guards without acquiring a camera or driving a desktop window."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from thermal_lab.alignment_tool import AlignmentTool,selected_region


class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value


class AlignmentToolTests(unittest.TestCase):
    def test_selected_measurement_rectangle_is_used_as_target(self):
        d=SimpleNamespace(selected='target',settings=dict(areas=[dict(id='target',x=.2,y=.3,x2=.6,y2=.8)]))
        self.assertEqual(selected_region(d),[.2,.3,.6,.8])
        d.selected='missing';self.assertIsNone(selected_region(d))
        d.selected='target';d.settings['areas'][0]['x2']=.21
        self.assertIsNone(selected_region(d))

    def test_optical_guidance_requires_explicit_thermal_target(self):
        t=self.tool();t.frame={};t.target_selected=False;t.guide=Value(True);t.point=Mock();t.start=None
        t.press(None,True)
        t.point.assert_not_called();self.assertIsNone(t.start)
        self.assertIn('LEFT',t.message.get())

    def test_zoomed_display_click_maps_to_original_sensor_coordinates(self):
        t=self.tool();t.bounds=[(10,20,400,300)]*2;t.view_regions=[[.2,.3,.6,.8]]*2
        self.assertEqual(t.point(SimpleNamespace(x=210,y=170)),(.4,.55))

    def test_new_points_disable_apply_until_fit_review(self):
        t=self.tool();t.frame={};t.target_selected=True;t.start=None;t.point_pairs=[[],[]]
        t.guide=Value(False);t.zoom_target=Value(False);t.buttons=Mock();t.draw=Mock()
        t.start_points();self.assertFalse(t.verified);self.assertTrue(t.point_mode);self.assertTrue(t.zoom_target.get())
        t.apply();t.desktop.changed.assert_not_called()
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
