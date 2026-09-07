import struct
import unittest
from thermal_lab.validation import ValidationError
from thermal_lab.tc001_max import decode_frame, FRAME_BYTES, PLANE_BYTES, TC001Max


class TC001MaxTests(unittest.TestCase):
    def frame(self):
        # Explicit synthetic byte fixture: it never claims hardware evidence.
        raw = bytearray(FRAME_BYTES)
        raw[:PLANE_BYTES] = b'\x40\x80' * (PLANE_BYTES // 2)
        raw[PLANE_BYTES:2 * PLANE_BYTES] = struct.pack('<H', 19072) * 49152
        return raw

    def decode(self, data):
        return decode_frame(data, camera_id='fixture', elapsed_s=.2, sequence=3)

    def test_layout_units_orientation_and_provenance(self):
        data = self.frame()
        struct.pack_into('<H', data, PLANE_BYTES + 2, 19136)
        f = self.decode(data)
        self.assertEqual((f['width'], f['height']), (256, 192))
        self.assertEqual(f['temperatures'][:2], [24.85, 25.85])
        self.assertIsNone(f['capture_timestamp'])
        self.assertIsNone(f['device_frame_counter'])
        self.assertFalse(f['host_environment_correction_applied'])
        self.assertEqual(f['timestamp_basis'], 'host_monotonic_arrival')

    def test_corrupt_startup_and_truncated_frame_rejected(self):
        data = self.frame()
        with self.assertRaises(ValidationError): self.decode(data[:-1])
        data[199] = 127
        with self.assertRaisesRegex(ValidationError, 'misaligned'): self.decode(data)
        data[199] = 128
        struct.pack_into('<H', data, PLANE_BYTES, 65535)
        with self.assertRaisesRegex(ValidationError, 'codes'): self.decode(data)

    def test_celsius_values_preserve_original_codes(self):
        data = self.frame()
        for i, code in enumerate(range(18000, 19000)):
            struct.pack_into('<H', data, PLANE_BYTES + 2*i, code)
        values = self.decode(data)['temperatures'][:1000]
        self.assertEqual([round((v+273.15)*64) for v in values], list(range(18000,19000)))

    def test_closed_camera_does_not_call_native_code(self):
        camera = TC001Max('.')
        camera.close()
        with self.assertRaises(RuntimeError): camera.read()


if __name__ == '__main__': unittest.main()
