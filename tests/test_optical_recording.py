import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from thermal_lab.optical_recording import OpticalRecorder,OpticalRecording,OPTICAL_BYTES,OPTICAL_OFFSET


class OpticalTests(unittest.TestCase):
    def fixture(self,path):
        plane=bytes(range(256))*(OPTICAL_BYTES//256)
        recorder=OpticalRecorder(path);frames=[]
        for i in range(3):
            data=plane if i!=1 else plane[::-1]
            digest=recorder.ingest(bytes(OPTICAL_OFFSET)+data,i*.04,100+i)
            frames.append(dict(elapsed_s=i*.04,arrival_sequence=100+i,optical_sha256=digest))
        recorder.close();self.assertIsNone(recorder.error);self.assertEqual(recorder.count,3)
        return frames,plane,[(i*.04,0,0) for i in range(3)]

    def test_lossless_random_seek_and_pair_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);frames,plane,entries=self.fixture(path);recording=OpticalRecording(path,entries)
            for i in (2,0,1):self.assertEqual(recording.read(i,frames[i]),plane[::-1] if i==1 else plane)
            for key,value in [('elapsed_s',999),('arrival_sequence',999),('optical_sha256','0'*64)]:
                with self.assertRaisesRegex(ValueError,'match'):recording.read(0,dict(frames[0],**{key:value}))

    def test_corrupt_data_and_count_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);frames,plane,entries=self.fixture(path)
            raw=bytearray((path/'optical.bin').read_bytes());raw[20]^=127;(path/'optical.bin').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'corrupt'):OpticalRecording(path,entries).read(0,frames[0])
            (path/'optical.idx').write_bytes((path/'optical.idx').read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'counts'):OpticalRecording(path,entries)

    def test_wrong_index_pairing_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);frames,plane,entries=self.fixture(path)
            entries[1]=(.041,0,0)
            with self.assertRaisesRegex(ValueError,'pairing'):OpticalRecording(path,entries)

    def test_background_disk_fault_is_reported_on_close(self):
        with tempfile.TemporaryDirectory() as temp:
            recorder=OpticalRecorder(temp)
            with patch.object(recorder.data,'write',side_effect=OSError('disk full')):
                recorder.ingest(bytes(OPTICAL_OFFSET+OPTICAL_BYTES),0.,1)
                recorder.close()
            self.assertIn('disk full',recorder.error)
            self.assertEqual(recorder.count,0)
            self.assertFalse(recorder.thread.is_alive())
