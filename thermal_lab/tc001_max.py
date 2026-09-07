"""Experimental TC001 Max acquisition using the locally installed TopView DLL.

The ABI was observed in TopView 1.30.003 and checked against that exact binary.
No SDK or TopView process is required at capture time. Never distribute the DLL
with this module. Only one camera and one acquisition worker are qualified here.
The decoder returns apparent temperatures; host emissivity/distance corrections
are not applied. See docs/TC001-Max-Direct-Capture.md for evidence and limitations.
"""
import ctypes as c
import hashlib
import os
import struct
import sys
import time
from pathlib import Path

from .camera_diagnostics import pnp_devices
from .validation import ValidationError

FRAME_BYTES = 1770496
PLANE_BYTES = 98304
DLL_SHA256 = 'f7a745d1e056e1dcda6de43ee30483fa5490eeb535bc18bbbd7ff031fcf6d3e6'
TEMPERATURE_LUT = tuple(round(value / 64 - 273.15, 6) for value in range(65536))


def decode_frame(data, *, camera_id, elapsed_s, sequence):
    if len(data) != FRAME_BYTES:
        raise ValidationError('TC001 Max frame length mismatch')
    # The observed IR plane is neutral-chroma YUYV. Startup misalignment can
    # place visible-camera data here, including plausible but false temperatures.
    if data[1:PLANE_BYTES:2] != b'\x80' * (PLANE_BYTES // 2):
        raise ValidationError('TC001 Max IR plane is misaligned or unsupported')
    codes = struct.unpack('<49152H', data[PLANE_BYTES:2 * PLANE_BYTES])
    if not all(11081 <= value <= 52681 for value in codes):
        raise ValidationError('TC001 Max temperature codes outside supported range')
    # Native sensor orientation, 256 columns x 192 rows. Rotate only for display.
    values = [TEMPERATURE_LUT[value] for value in codes]
    return dict(width=256, height=192, temperatures=values, camera_id=camera_id,
                elapsed_s=elapsed_s, arrival_sequence=sequence, source='HARDWARE',
                valid=True, unit='C', timestamp_basis='host_monotonic_arrival',
                capture_timestamp=None, device_frame_counter=None,
                temperature_basis='apparent_raw_kelvin_64',
                host_environment_correction_applied=False,
                calibration_status='experimental; absolute accuracy unqualified',
                orientation='native_sensor', raw_sha256=hashlib.sha256(data).hexdigest())


class DeviceInfo(c.Structure):
    _fields_ = [('pid', c.c_uint32), ('vid', c.c_uint32), ('index', c.c_uint32)]


class StreamInfo(c.Structure):
    _fields_ = [('format', c.c_char_p), ('width', c.c_uint32), ('height', c.c_uint32),
                ('size', c.c_uint32), ('fps', c.c_uint32), ('timeout', c.c_uint32),
                ('mode', c.c_uint16)]


class TC001Max:
    """Use in a dedicated process: native calls have a 2-second frame timeout.

    The vendor library contains process-global streaming state. This adapter
    rejects multiple connected Max devices rather than assign unstable indexes.
    """
    def __init__(self, topview_directory):
        self.directory = Path(topview_directory).resolve()
        self.handle = None
        self.started = False
        self.opened = False
        self.dll_paths = []
        self.mutex = None
        self.received = 0
        self.rejected = 0

    def __enter__(self):
        if sys.platform != 'win32' or c.sizeof(c.c_void_p) != 8:
            raise OSError('TC001 Max adapter requires Windows x64 Python')
        library = self.directory / 'dll/dll_c001max/libirdvs.dll'
        if hashlib.sha256(library.read_bytes()).hexdigest() != DLL_SHA256:
            raise OSError('Unqualified libirdvs.dll version; refusing unknown native ABI')
        devices = pnp_devices()
        if len(devices) != 1 or devices[0].get('problem_code') != 0:
            raise OSError('Exactly one healthy TC001 Max must be connected')
        self.camera_id = devices[0]['instance_id']
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [c.c_void_p, c.c_int, c.c_wchar_p]
        self.kernel.CreateMutexW.restype = c.c_void_p
        self.kernel.CloseHandle.argtypes = [c.c_void_p]
        self.mutex = self.kernel.CreateMutexW(None, False, 'Local\\PowerLabTC001MaxCapture')
        if not self.mutex:
            raise c.WinError(c.get_last_error())
        if c.get_last_error() == 183:
            self.kernel.CloseHandle(self.mutex)
            self.mutex = None
            raise OSError('Another Power Lab camera worker is active')
        try:
            for directory in [self.directory, library.parent]:
                self.dll_paths.append(os.add_dll_directory(str(directory)))
            self.dll = c.CDLL(str(library))
            signatures = {
                'handle_create': ([c.c_void_p], c.c_void_p),
                'open': ([c.c_void_p, c.POINTER(DeviceInfo)], c.c_int),
                'init': ([c.c_void_p, c.c_void_p], c.c_int),
                'start_stream': ([c.c_void_p, c.POINTER(StreamInfo)], c.c_int),
                'frame_get': ([c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32], c.c_int),
                'stop_stream': ([c.c_void_p], c.c_int),
                'close': ([c.c_void_p], c.c_int),
                'handle_delete': ([c.c_void_p], c.c_int),
            }
            for name, (args, result) in signatures.items():
                function = getattr(self.dll, 'irdvs_camera_' + name)
                function.argtypes, function.restype = args, result
            self.table = (c.c_void_p * 8)()
            self.dll.irdvs_camera_handle_create(self.table)
            self.handle = self.table[0]
            if not self.handle:
                raise OSError('Camera handle allocation failed')
            self._check('open', self.dll.irdvs_camera_open(self.handle, c.byref(DeviceInfo(0x4962, 0x3474, 0))))
            self.opened = True
            self._check('init', self.dll.irdvs_camera_init(self.handle, None))
            self._check('start', self.dll.irdvs_camera_start_stream(
                self.handle, c.byref(StreamInfo(b'YUYV', 256, 3458, FRAME_BYTES, 25, 2000, 0))))
            self.started = True
            self.buffer = c.create_string_buffer(FRAME_BYTES)
            self.origin = time.monotonic()
            return self
        except Exception:
            self.close()
            raise

    @staticmethod
    def _check(operation, result):
        if result != 0:
            raise OSError(f'TC001 Max {operation} failed ({result}); close TopView if it owns the camera')

    def read(self):
        if not self.started:
            raise RuntimeError('Camera stream is closed')
        # Discard the first two buffers after every open, then validate alignment
        # on EVERY frame. A sustained malformed stream fails instead of hanging.
        for _ in range(10):
            self._check('frame_get', self.dll.irdvs_camera_frame_get(self.handle, 0, self.buffer, FRAME_BYTES))
            elapsed = time.monotonic() - self.origin
            self.received += 1
            data = self.buffer.raw
            if self.received <= 2:
                self.rejected += 1
                continue
            try:
                frame = decode_frame(data, camera_id=self.camera_id,
                                     elapsed_s=elapsed, sequence=self.received - 1)
            except ValidationError:
                self.rejected += 1
                continue
            return frame, data
        raise OSError('TC001 Max produced ten consecutive unusable startup/alignment buffers')

    def close(self):
        errors = []
        if self.handle:
            if self.started:
                result = self.dll.irdvs_camera_stop_stream(self.handle)
                if result: errors.append(f'stop: {result}')
                self.started = False
            if self.opened:
                result = self.dll.irdvs_camera_close(self.handle)
                if result: errors.append(f'close: {result}')
                self.opened = False
            self.dll.irdvs_camera_handle_delete(self.handle)
            self.handle = None
        for directory in self.dll_paths:
            directory.close()
        self.dll_paths.clear()
        if self.mutex:
            self.kernel.CloseHandle(self.mutex)
            self.mutex = None
        if errors:
            raise OSError('TC001 Max cleanup failed: ' + ', '.join(errors))

    def __exit__(self, *_):
        self.close()
