import json
import tempfile
import unittest
from pathlib import Path

from thermal_lab.validation import ValidationError
from thermal_lab.thermal import measurements
from thermal_lab.topview_import import parse_topview_csv, read_topview_csv


SAMPLE = b'"File","capture.png","Unit(?)"\r\n"Area Name","Max.","Mean","Min."\r\n"P1","24.5","24.5","24.5"\r\n\r\n,"0","1",\r\n"0","20","24.5",\r\n"1","22","30",\r\n'


class TopViewImportTests(unittest.TestCase):
    def parse(self, data=SAMPLE, unit='C'):
        return parse_topview_csv(data, unit=unit, camera_id='test-camera')

    def test_real_units_and_pixel_measurements(self):
        frame = self.parse()
        self.assertEqual((frame['width'], frame['height']), (2, 2))
        self.assertEqual(frame['source'], 'HARDWARE_FILE_IMPORT')
        self.assertIsNone(frame['capture_timestamp'])
        camera = dict(points=[dict(name='P1', x=.5, y=0)],
                      areas=[dict(name='all', x=0, y=0, x2=1, y2=1)])
        values = measurements(frame, camera)
        self.assertEqual(values['P1']['value'], frame['vendor_measurements']['P1']['mean'])
        self.assertEqual(values['all']['mean'], 24.125)

    def test_units_are_explicit_and_converted(self):
        with self.assertRaises(ValidationError):
            self.parse(unit=None)
        self.assertAlmostEqual(self.parse(unit='F')['temperatures'][0], -6.6666666667)
        with self.assertRaises(ValidationError):
            self.parse(SAMPLE.replace(b'Unit(?)', 'Unit(Â°F)'.encode()))

    def test_corrupt_exports_rejected(self):
        for data in [b'plain,image', SAMPLE[:-10],
                     SAMPLE.replace(b'"1","22"', b'"2","22"'),
                     SAMPLE.replace(b'"20"', b'"nan"'),
                     SAMPLE.replace(b'"20"', b'"inf"'),
                     SAMPLE.replace(b'"20","24.5"', b'"20"')]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.parse(data)

    def test_file_and_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.csv'
            path.write_bytes(SAMPLE)
            frame = read_topview_csv(path, unit='C', camera_id='camera')
            self.assertEqual(json.loads(json.dumps(frame)), frame)
