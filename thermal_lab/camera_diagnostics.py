"""Read-only TC001 Max Windows diagnostics; never imports instrument controllers.

USB access is distinct from radiometric capture. No undocumented vendor commands
are sent and no image or temperature measurement is synthesized by this module.
"""
import ctypes
from ctypes import wintypes as wt
from datetime import datetime, timezone
import json
import platform
import subprocess
import sys
import uuid


# From TOPDON TopView 1.30.003's devicer/devicer04/TC001Max.inf.
INTERFACE_GUID = 'FE7A2189-E1FA-AE49-D5C9-603519B1CDBB'
DEVICE_ID = 'VID_3474&PID_4962'


def pnp_devices():
    script = r"""
$ErrorActionPreference = 'Stop'
$items = @(Get-PnpDevice -PresentOnly | Where-Object {
    $_.InstanceId -like 'USB\VID_3474&PID_4962*'
} | ForEach-Object {
    $device = $_
    $props = @{}
    Get-PnpDeviceProperty -InstanceId $device.InstanceId | ForEach-Object {
        $props[$_.KeyName] = $_.Data
    }
    [ordered]@{
        instance_id = $device.InstanceId
        pdo_name = $props['DEVPKEY_Device_PDOName']
        name = $device.FriendlyName
        status = $device.Status
        problem_code = $props['DEVPKEY_Device_ProblemCode']
        problem_status = $props['DEVPKEY_Device_ProblemStatus']
        service = $props['DEVPKEY_Device_Service']
        driver_inf = $props['DEVPKEY_Device_DriverInfPath']
        driver_version = $props['DEVPKEY_Device_DriverVersion']
        compatible_ids = $props['DEVPKEY_Device_CompatibleIds']
    }
})
ConvertTo-Json -InputObject $items -Depth 5 -Compress
"""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, text=True, timeout=30, check=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    return json.loads(result.stdout)


def winusb_interfaces():
    """Open only the vendor's device interface and query standard USB metadata."""
    class Guid(ctypes.Structure):
        _fields_ = [('bytes', ctypes.c_ubyte * 16)]

    class InterfaceDescriptor(ctypes.Structure):
        _pack_ = 1
        _fields_ = [(name, ctypes.c_ubyte) for name in (
            'length', 'type', 'number', 'alternate', 'endpoint_count',
            'interface_class', 'subclass', 'protocol', 'string_index')]

    class Pipe(ctypes.Structure):
        _fields_ = [('type', ctypes.c_int), ('id', ctypes.c_ubyte),
                    ('max_packet_size', ctypes.c_ushort), ('interval', ctypes.c_ubyte)]

    guid = Guid.from_buffer_copy(uuid.UUID(INTERFACE_GUID).bytes_le)
    cm = ctypes.WinDLL('cfgmgr32', use_last_error=True)
    cm.CM_Get_Device_Interface_List_SizeW.argtypes = [ctypes.POINTER(wt.ULONG), ctypes.POINTER(Guid), wt.LPCWSTR, wt.ULONG]
    cm.CM_Get_Device_Interface_List_SizeW.restype = wt.ULONG
    cm.CM_Get_Device_Interface_ListW.argtypes = [ctypes.POINTER(Guid), wt.LPCWSTR, wt.LPWSTR, wt.ULONG, wt.ULONG]
    cm.CM_Get_Device_Interface_ListW.restype = wt.ULONG
    length = wt.ULONG()
    rc = cm.CM_Get_Device_Interface_List_SizeW(ctypes.byref(length), ctypes.byref(guid), None, 0)
    if rc:
        raise OSError(f'CM_Get_Device_Interface_List_SizeW: CONFIGRET {rc:#x}')
    buffer = ctypes.create_unicode_buffer(max(1, length.value))
    rc = cm.CM_Get_Device_Interface_ListW(ctypes.byref(guid), None, buffer, length, 0)
    if rc:
        raise OSError(f'CM_Get_Device_Interface_ListW: CONFIGRET {rc:#x}')
    paths = [p for p in buffer[:].split('\0') if DEVICE_ID.lower() in p.lower()]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    usb = ctypes.WinDLL('winusb', use_last_error=True)
    kernel.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE]
    kernel.CreateFileW.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.CloseHandle.restype = wt.BOOL
    usb.WinUsb_Initialize.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HANDLE)]
    usb.WinUsb_Initialize.restype = wt.BOOL
    usb.WinUsb_Free.argtypes = [wt.HANDLE]
    usb.WinUsb_Free.restype = wt.BOOL
    usb.WinUsb_QueryInterfaceSettings.argtypes = [wt.HANDLE, ctypes.c_ubyte, ctypes.POINTER(InterfaceDescriptor)]
    usb.WinUsb_QueryInterfaceSettings.restype = wt.BOOL
    usb.WinUsb_QueryPipe.argtypes = [wt.HANDLE, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.POINTER(Pipe)]
    usb.WinUsb_QueryPipe.restype = wt.BOOL
    usb.WinUsb_GetAssociatedInterface.argtypes = [wt.HANDLE, ctypes.c_ubyte, ctypes.POINTER(wt.HANDLE)]
    usb.WinUsb_GetAssociatedInterface.restype = wt.BOOL
    results = []
    for path in paths:
        item = dict(path=path, opened=False, endpoints=[])
        results.append(item)
        handle = kernel.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000, None)
        if handle == ctypes.c_void_p(-1).value:
            item['error_stage'] = 'CreateFileW'
            item['winerror'] = ctypes.get_last_error()
            item['error'] = str(ctypes.WinError(ctypes.get_last_error()))
            continue
        interface = wt.HANDLE()
        stage = 'WinUsb_Initialize'
        try:
            if not usb.WinUsb_Initialize(handle, ctypes.byref(interface)):
                raise ctypes.WinError(ctypes.get_last_error())
            descriptor = InterfaceDescriptor()
            stage = 'WinUsb_QueryInterfaceSettings'
            if not usb.WinUsb_QueryInterfaceSettings(interface, 0, ctypes.byref(descriptor)):
                raise ctypes.WinError(ctypes.get_last_error())
            item['interface'] = {name: getattr(descriptor, name) for name, _ in descriptor._fields_}
            for index in range(descriptor.endpoint_count):
                pipe = Pipe()
                stage = 'WinUsb_QueryPipe'
                if not usb.WinUsb_QueryPipe(interface, 0, index, ctypes.byref(pipe)):
                    raise ctypes.WinError(ctypes.get_last_error())
                item['endpoints'].append({name: getattr(pipe, name) for name, _ in pipe._fields_})
            item['opened'] = True
            # The Max's stream belongs to associated interface 1, alternate 1.
            # Query every available alternate without switching the device mode.
            item['associated_interfaces'] = []
            for associated_index in range(8):
                associated = wt.HANDLE()
                if not usb.WinUsb_GetAssociatedInterface(interface, associated_index, ctypes.byref(associated)):
                    if ctypes.get_last_error() == 259:  # ERROR_NO_MORE_ITEMS
                        break
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    for alternate in range(16):
                        desc = InterfaceDescriptor()
                        if not usb.WinUsb_QueryInterfaceSettings(associated, alternate, ctypes.byref(desc)):
                            if ctypes.get_last_error() == 259:
                                break
                            raise ctypes.WinError(ctypes.get_last_error())
                        detail = {name: getattr(desc, name) for name, _ in desc._fields_}
                        detail['endpoints'] = []
                        for index in range(desc.endpoint_count):
                            pipe = Pipe()
                            if not usb.WinUsb_QueryPipe(associated, alternate, index, ctypes.byref(pipe)):
                                raise ctypes.WinError(ctypes.get_last_error())
                            detail['endpoints'].append({name: getattr(pipe, name) for name, _ in pipe._fields_})
                        item['associated_interfaces'].append(detail)
                finally:
                    usb.WinUsb_Free(associated)
        except OSError as exc:
            item['error_stage'] = stage
            item['winerror'] = getattr(exc, 'winerror', None)
            item['error'] = str(exc)
        finally:
            if interface.value:
                usb.WinUsb_Free(interface)
            kernel.CloseHandle(handle)
    return results


def classify(devices, interfaces):
    if not devices:
        return 'DEVICE_NOT_PRESENT'
    if any(d.get('problem_code') not in (0, None) for d in devices):
        return 'WINDOWS_DEVICE_ERROR'
    if not interfaces:
        return 'WINUSB_INTERFACE_NOT_PRESENT'
    if not any(i.get('opened') for i in interfaces):
        return 'WINUSB_OPEN_FAILED'
    return 'USB_ACCESS_VERIFIED'


def diagnose():
    report = dict(schema_version=1, utc=datetime.now(timezone.utc).isoformat(),
                  platform=platform.platform(), python=sys.executable,
                  scope='TC001 Max only; standard USB metadata; no vendor commands',
                  devices=[], interfaces=[], errors=[],
                  capture_verified=False, temperatures_verified=False,
                  recording_verified=False)
    if sys.platform != 'win32':
        report['status'] = 'NOT_WINDOWS'
        return report
    for key, probe in [('devices', pnp_devices), ('interfaces', winusb_interfaces)]:
        try:
            report[key] = probe()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report['errors'].append(f'{key}: {exc}')
    report['status'] = 'DIAGNOSTIC_FAILED' if report['errors'] else classify(report['devices'], report['interfaces'])
    return report
