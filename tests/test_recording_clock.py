import unittest
from unittest.mock import patch
from thermal_lab.recording_clock import RecordingClock,duration_text


class RecordingClockTests(unittest.TestCase):
    def test_acquisition_origin_stop_freeze_and_new_recording_reset(self):
        clock=RecordingClock();self.assertEqual(clock.text(),'Recording  00:00:00')
        clock.start(5000.)
        with patch('thermal_lab.recording_clock.time.monotonic',return_value=8661.9):
            self.assertEqual(clock.text(),'Recording  01:01:01')
            clock.finish(3660.5);self.assertEqual(clock.text(),'Recorded  01:01:00')
            clock.start(8661.9);self.assertEqual(clock.text(),'Recording  00:00:00')
        with patch('thermal_lab.recording_clock.time.monotonic',return_value=8665.5):clock.interrupt()
        self.assertEqual(clock.text(),'Interrupted  00:00:03')
        self.assertEqual(duration_text(360000),'100:00:00');self.assertEqual(duration_text(-1),'00:00:00')
