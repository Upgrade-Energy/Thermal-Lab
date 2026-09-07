import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thermal_lab.camera_archive import archive_topview
from thermal_lab.validation import ValidationError
from thermal_lab.thermal import FRAME_INDEX, Recorder

CSV = b'File,test.png,Unit(?)\nArea Name,Max.,Mean,Min.\n\n,0,1,\n0,21.5,30.2,\n'


class CameraArchiveTests(unittest.TestCase):
    def test_preview_without_enabled_cameras(self):
        recorder = Recorder([], 0)
        self.assertEqual(recorder.preview(0, 22), [])
        recorder.close()

    def test_indexed_round_trip_and_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'frame.csv'
            source.write_bytes(CSV)
            target = root / 'recording'
            result = archive_topview([source], target, unit='C', camera_id='camera1')
            self.assertEqual((result['status'], result['frames_written']), ('COMPLETE', 1))
            elapsed, offset, size = FRAME_INDEX.unpack((target / 'thermal.idx').read_bytes())
            with (target / 'thermal.jsonl.gz').open('rb') as stream:
                stream.seek(offset)
                frame = json.loads(gzip.decompress(stream.read(size)))[0]
            self.assertEqual(frame['temperatures'], [21.5, 30.2])
            self.assertEqual(frame['elapsed_s'], elapsed)
            self.assertEqual(frame['source'], 'HARDWARE_FILE_IMPORT')
            self.assertIsNone(frame['capture_timestamp'])
            self.assertEqual(frame['recording_timestamp_basis'], 'host_import_monotonic')
            with self.assertRaises(FileExistsError):
                archive_topview([source], target, unit='C', camera_id='camera1')

    def test_bad_input_marks_failure(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'recording'
            with self.assertRaises(FileNotFoundError):
                archive_topview([Path(root) / 'missing.csv'], target, unit='C', camera_id='camera1')
            result = json.loads((target / 'camera-session.json').read_text())
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['frames_written'], 0)

    def test_writer_fault_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'frame.csv'
            source.write_bytes(CSV)
            with patch('thermal_lab.thermal.gzip.compress', side_effect=OSError('disk fixture failure')):
                with self.assertRaisesRegex(OSError, 'disk fixture failure'):
                    archive_topview([source], root / 'recording', unit='C', camera_id='camera1')
            result = json.loads((root / 'recording' / 'camera-session.json').read_text())
            self.assertEqual(result['status'], 'FAILED')

    def test_acquisition_buffer_reuse_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder([], 0)
            frame = dict(width=1, height=1, temperatures=[22.1], camera_id='real',
                         source='HARDWARE_FILE_IMPORT', elapsed_s=0)
            recorder.ingest([frame])
            frame['temperatures'][0] = 99
            path = Path(root) / 'thermal.jsonl.gz'
            recorder.start(path)
            with self.assertRaises(RuntimeError):
                recorder.start(path)
            recorder.close()
            self.assertIsNone(recorder.error)
            self.assertEqual(json.loads(gzip.decompress(path.read_bytes()))[0]['temperatures'], [22.1])
            with self.assertRaises(RuntimeError):
                recorder.ingest([frame])
            fresh = Recorder([], 0)
            frame['elapsed_s'] = float('nan')
            with self.assertRaises(ValidationError):
                fresh.ingest([frame])


if __name__ == '__main__':
    unittest.main()
