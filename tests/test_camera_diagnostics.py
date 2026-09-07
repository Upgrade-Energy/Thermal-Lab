import unittest
from unittest.mock import patch

from thermal_lab.camera_diagnostics import classify, diagnose


class CameraDiagnosticsTests(unittest.TestCase):
    def test_parent_ok_does_not_hide_missing_interface_driver(self):
        self.assertEqual(classify([{'problem_code': 0}, {'problem_code': 28}], []),
                         'WINDOWS_DEVICE_ERROR')

    def test_detection_is_not_access(self):
        self.assertEqual(classify([], []), 'DEVICE_NOT_PRESENT')
        self.assertEqual(classify([{'problem_code': 0}], []), 'WINUSB_INTERFACE_NOT_PRESENT')
        self.assertEqual(classify([{'problem_code': 0}], [{'opened': False}]), 'WINUSB_OPEN_FAILED')

    @patch('thermal_lab.camera_diagnostics.sys.platform', 'win32')
    @patch('thermal_lab.camera_diagnostics.winusb_interfaces', return_value=[{'opened': True}])
    @patch('thermal_lab.camera_diagnostics.pnp_devices', return_value=[{'problem_code': 0}])
    def test_usb_success_never_claims_capture(self, *_):
        report = diagnose()
        self.assertEqual(report['status'], 'USB_ACCESS_VERIFIED')
        for field in ('capture_verified', 'temperatures_verified', 'recording_verified'):
            self.assertIs(report[field], False)

    @patch('thermal_lab.camera_diagnostics.sys.platform', 'win32')
    @patch('thermal_lab.camera_diagnostics.winusb_interfaces', return_value=[])
    @patch('thermal_lab.camera_diagnostics.pnp_devices', side_effect=OSError('probe failed'))
    def test_probe_error_is_not_reported_as_absent(self, *_):
        report = diagnose()
        self.assertEqual(report['status'], 'DIAGNOSTIC_FAILED')
        self.assertIn('probe failed', report['errors'][0])
