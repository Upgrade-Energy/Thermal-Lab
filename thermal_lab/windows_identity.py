"""Match native camera handles to Windows PnP physical device objects.

Only query handles created during native camera open, in its isolated worker.
An ambiguous or unavailable identity is an error, never an index fallback.
"""
import ctypes as c
from ctypes import wintypes as w


class Entry(c.Structure):
    _fields_ = [('handle', w.HANDLE), ('count', c.c_size_t), ('pointers', c.c_size_t),
                ('access', w.ULONG), ('type', w.ULONG), ('attributes', w.ULONG),
                ('reserved', w.ULONG)]


class UnicodeString(c.Structure):
    _fields_ = [('length', w.USHORT), ('maximum', w.USHORT), ('buffer', c.c_void_p)]


def handles():
    nt = c.WinDLL('ntdll')
    nt.NtQueryInformationProcess.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)]
    size = 65536
    while size <= 16 * 1024 * 1024:
        data = c.create_string_buffer(size)
        needed = w.ULONG()
        result = nt.NtQueryInformationProcess(w.HANDLE(-1), 51, data, size, c.byref(needed))
        if result == 0:
            count = c.c_size_t.from_buffer(data).value
            offset = 2 * c.sizeof(c.c_size_t)
            if offset + count * c.sizeof(Entry) > size:
                raise OSError('Invalid Windows handle inventory')
            return {Entry.from_buffer(data, offset + i*c.sizeof(Entry)).handle for i in range(count)}
        if result & 0xffffffff != 0xc0000004:
            raise OSError(f'Windows handle inventory failed: {result & 0xffffffff:#x}')
        size = max(size * 2, needed.value)
    raise OSError('Windows handle inventory exceeds limit')


def opened_camera_id(before, devices):
    nt = c.WinDLL('ntdll')
    nt.NtQueryObject.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)]
    matches = set()
    names = {d['pdo_name'].casefold(): d['instance_id'] for d in devices if d.get('pdo_name')}
    for handle in handles() - before:
        data = c.create_string_buffer(8192)
        needed = w.ULONG()
        if nt.NtQueryObject(handle, 1, data, len(data), c.byref(needed)) != 0:
            continue
        string = UnicodeString.from_buffer(data)
        if string.length and string.buffer:
            name = c.wstring_at(string.buffer, string.length // 2).casefold()
            if name in names:
                matches.add(names[name])
    if len(matches) != 1:
        raise OSError('Cannot uniquely verify the native camera identity')
    return matches.pop()
