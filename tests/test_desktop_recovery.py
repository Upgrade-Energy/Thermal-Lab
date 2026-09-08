import queue
import time
import unittest
from unittest.mock import Mock,patch
from thermal_lab.desktop import Desktop


class RecoveryTests(unittest.TestCase):
    def desktop(self):
        app=object.__new__(Desktop)
        for name in ('root','record_button','connect_button','optical_check','camera_box','refresh_button','status','cursor','info','render','refresh_values'):
            setattr(app,name,Mock())
        app.status.get.return_value='LIVE'
        app.process=Mock();app.process.is_alive.return_value=True
        app.events=queue.Queue();app.previews=queue.Queue()
        app.stream_active=True;app.frame={'old':'frame'};app.optical=object();app.received_at=time.monotonic()
        app.recording=True;app.record_pending=False;app.closing=False;app.stop_deadline=None;app.start_deadline=None
        return app

    def test_error_discards_pending_preview_and_measurements_immediately(self):
        app=self.desktop()
        app.events.put(dict(kind='error',message='Injected disconnect'))
        app.events.put(dict(kind='stopped'))
        app.previews.put(dict(frame={'old':'queued frame'},received_at=time.monotonic()))
        app.poll()
        self.assertIsNone(app.frame);self.assertIsNone(app.optical)
        self.assertFalse(app.stream_active)
        app.record_button.configure.assert_any_call(text='Record session',state='disabled')
        app.record_button.configure.assert_called_with(state='disabled')
        app.refresh_values.assert_called()

    def test_native_stream_hang_is_bounded(self):
        app=self.desktop();app.received_at=time.monotonic()-9
        app.poll()
        app.process.terminate.assert_called_once()
        self.assertFalse(app.stream_active);self.assertIsNone(app.frame)
        self.assertIn('incomplete',app.status.set.call_args.args[0])

    def test_stale_frame_cannot_start_recording(self):
        app=self.desktop();app.recording=False;app.received_at=time.monotonic()-2;app.send=Mock()
        app.toggle_record();app.send.assert_not_called()

    def test_new_frame_clears_disconnected_cursor_message(self):
        app=self.desktop();app.frame=None;app.recording=False
        app.previews.put(dict(frame=dict(arrival_sequence=1,elapsed_s=0.),raw=b'fixture',received_at=time.monotonic()))
        with patch('thermal_lab.desktop.optical_image',return_value=object()):app.poll()
        app.cursor.set.assert_called_with('Choose Point or Rectangle, then mark the image')
