"""Exercise native widgets and numerical overlays without claiming a USB camera."""
import tempfile
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from thermal_lab.desktop import Desktop
from thermal_lab.review import Review
from thermal_lab.workspace import validate_settings, read_settings
from thermal_lab.camera_names import save_name
from thermal_lab.imaging import sensor_to_view


@unittest.skipUnless(sys.platform=='win32','Native Windows widget checks require a Windows desktop')
class NativeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=tk.Tk();self.root.withdraw()
        self.args=SimpleNamespace(workspace=Path(self.folder.name)/'layout.json',camera_id='',topview_directory=None,
                                  recordings=Path(self.folder.name),session=None)
    def tearDown(self):
        for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
        self.root.destroy();self.folder.cleanup()
    def desktop(self):
        with patch('thermal_lab.desktop.pnp_devices',return_value=[]):app=Desktop(self.root,self.args)
        self.root.deiconify();self.root.geometry('1180x850');self.root.update()
        values=[22.0]*49152;values[0]=10;values[-1]=40
        app.frame=dict(width=256,height=192,temperatures=values);app.optical=Image.new('RGB',(1024,768))
        app.received_at=time.monotonic();return app
    def test_extrema_obey_view_toggle_rotation_and_freshness(self):
        app=self.desktop()
        for rotation in ('0','90','180','270'):
            app.rotation.set(rotation);app.render()
            self.assertTrue(app.canvas.find_withtag('extrema'))
            self.assertEqual(app.hot_value.get(),'40.0 °C');self.assertEqual(app.cold_value.get(),'10.0 °C')
        app.show_extrema.set(False);app.render();self.assertFalse(app.canvas.find_withtag('extrema'))
        app.show_extrema.set(True);app.mode.set('Optical');app.render();self.assertFalse(app.canvas.find_withtag('extrema'))
        app.mode.set('Side by side');app.render()
        texts=[app.canvas.itemcget(i,'text') for i in app.canvas.find_withtag('extrema') if app.canvas.type(i)=='text']
        self.assertEqual(len(texts),2)
        app.received_at=time.monotonic()-5;app.render()
        self.assertFalse(app.canvas.find_withtag('extrema'));self.assertEqual(app.hot_value.get(),'—')
    def test_clear_points_preserves_regions_and_saved_alignment(self):
        app=self.desktop()
        app.settings=validate_settings(dict(alignment=dict(dx=8,scale=1.3),points=[dict(id=str(i),name=f'P{i}',x=.5,y=.5) for i in range(31)],areas=[dict(id='r',name='Region',x=.1,y=.1,x2=.8,y2=.8)]))
        alignment=app.settings['alignment'].copy();app.tool.set('Point');app.clear_points()
        saved=read_settings(app.workspace_path)
        self.assertFalse(saved['points']);self.assertEqual(len(saved['areas']),1)
        self.assertEqual(saved['alignment'],alignment);self.assertEqual(app.tool.get(),'Select')

    def test_tracking_controls_persist_follow_pixels_and_cannot_be_dragged(self):
        app=self.desktop();app.rotation.set('0');app.show_extrema.set(False)
        app.track_buttons['hottest'].invoke();app.track_buttons['coldest'].invoke()
        self.assertEqual(len(read_settings(app.workspace_path)['points']),2)
        self.assertTrue(app.canvas.find_withtag('trackers'))
        hot=app.settings['points'][0]
        app.frame['temperatures']=[22.]*49152;app.frame['temperatures'][90*256+100]=55.125
        app.render();app.refresh_values()
        self.assertIn('55.12',app.table.item(hot['id'],'values')[1])
        x,y,scale,*_=app.viewports[0]
        event=SimpleNamespace(x=x+100.5*scale,y=y+90.5*scale)
        app.press(event);self.assertEqual(app.selected,hot['id'])
        original=app.settings.copy()
        end=SimpleNamespace(x=event.x+20,y=event.y+20)
        app.motion(end);app.release(end);self.assertEqual(app.settings,original)
        app.received_at=time.monotonic()-3;app.render();app.refresh_values()
        self.assertFalse(app.canvas.find_withtag('trackers'))
        self.assertEqual(app.table.item(hot['id'],'values')[1],'—')

    def test_tracking_selected_polygon_and_removal(self):
        app=self.desktop()
        app.add_polygon(dict(shape='polygon',vertices=[dict(x=x,y=y) for x,y in ((.1,.1),(.8,.1),(.1,.8))]))
        region=app.selected;app.tracking_scope.set('Selected region')
        app.track_buttons['hottest'].invoke();app.track_buttons['coldest'].invoke()
        self.assertEqual([p['region_id'] for p in app.settings['points']],[region,region])
        app.selected=region;app.remove()
        self.assertFalse(app.settings['areas']);self.assertFalse(app.settings['points'])

    def test_review_tracking_replays_and_analysis_can_add_to_old_frames(self):
        from test_tracking import fixture
        from thermal_lab.analysis import Analysis
        folder=Path(self.folder.name)/'archive';fixture(folder)
        app=Review(self.root,self.args);self.root.deiconify();self.root.update();app.open(folder)
        app.show_extrema.set(False);app.show(0)
        before=[app.canvas.coords(i) for i in app.canvas.find_withtag('trackers') if app.canvas.type(i)=='oval']
        app.show(7)
        after=[app.canvas.coords(i) for i in app.canvas.find_withtag('trackers') if app.canvas.type(i)=='oval']
        self.assertTrue(before);self.assertNotEqual(before,after)
        app.analysis=Analysis(app.recording,Path(self.folder.name)/'analysis')
        app.basis.set('Analysis');app.change_basis();app.track_buttons['coldest'].invoke()
        self.assertEqual(app.analysis.settings['points'][0]['tracking'],'coldest')
        self.assertTrue(app.canvas.find_withtag('trackers'))
        for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
        app.close()
        # close destroys the root; tearDown still has a live independent root.
        self.root=tk.Tk();self.root.withdraw()

    def test_other_window_rename_refreshes_selector_and_reconnected_layout(self):
        app=self.desktop();app.names_path=Path(self.folder.name)/'names.json'
        app.camera_ids=['USB-A','USB-B'];app.camera_choice.set('USB-A')
        save_name(app.names_path,'USB-A','Desk camera');app.update_camera_choices()
        # Another app process writes the registry after this selector was built.
        save_name(app.names_path,'USB-B','Room camera')
        self.root.tk.call(app.camera_box.cget('postcommand'))
        self.assertIn('Room camera',app.camera_box['values'][1])
        self.assertEqual(app.camera_choice.get(),'USB-A')
        app.prepare_camera_layout('USB-B')
        self.assertEqual(app.settings['camera_id'],'USB-B')
        self.assertEqual(app.settings['camera_name'],'Room camera')
    def test_playback_reserves_visible_graph_and_image(self):
        app=Review(self.root,self.args);self.root.deiconify();self.root.geometry('1180x850');self.root.update()
        self.assertGreaterEqual(app.graph.winfo_height(),100)
        self.assertLessEqual(app.graph.winfo_rooty()+app.graph.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height())
        self.assertGreaterEqual(app.canvas.winfo_height(),200)

    def test_polygon_corner_controls_and_editing_use_sensor_coordinates(self):
        app=self.desktop();app.tool.set('Polygon');self.root.update()
        def event(x,y):
            vx,vy=sensor_to_view(x*256,y*192,int(app.rotation.get()))
            px,py,scale,*_=app.viewports[0]
            app.received_at=time.monotonic()
            return SimpleNamespace(x=px+vx*scale,y=py+vy*scale)
        app.press(event(.2,.2));app.press(event(.8,.2))
        self.assertIn('disabled',app.polygon.finish_button.state())
        app.press(event(.8,.8));app.press(event(.2,.8));app.polygon.undo()
        self.assertEqual(len(app.polygon.points),3)
        app.polygon.finish();self.root.update()
        self.assertEqual(app.tool.get(),'Select');self.assertEqual(len(app.settings['areas']),1)
        item=app.settings['areas'][0];self.assertEqual(item['shape'],'polygon')
        self.assertTrue(app.canvas.find_withtag('polygon'))
        app.press(event(.8,.2));app.motion(event(.7,.25));app.release(event(.7,.25))
        self.assertAlmostEqual(app.settings['areas'][0]['vertices'][1]['x'],.7)
        self.assertAlmostEqual(read_settings(app.workspace_path)['areas'][0]['vertices'][1]['y'],.25)
        app.tool.set('Polygon');self.root.update();app.press(event(.3,.3));app.polygon.key(app.polygon.cancel)
        self.assertEqual(len(app.settings['areas']),1);self.assertFalse(app.polygon.points)
