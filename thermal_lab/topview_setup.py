"""Discover an accessible, ABI-qualified TopView installation for this user."""
import hashlib
import os
from pathlib import Path

LIBRARY = Path('dll/dll_c001max/libirdvs.dll')
DLL_SHA256 = 'f7a745d1e056e1dcda6de43ee30483fa5490eeb535bc18bbbd7ff031fcf6d3e6'


class TopViewSetupError(OSError):
    pass


def registry_locations():
    if os.name != 'nt':
        return []
    import winreg
    found = []
    key_name = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                                name = str(winreg.QueryValueEx(entry, 'DisplayName')[0])
                                if 'topview' not in name.casefold():
                                    continue
                                for field in ('InstallLocation', 'DisplayIcon'):
                                    try:
                                        value = str(winreg.QueryValueEx(entry, field)[0]).strip()
                                        if field == 'DisplayIcon':
                                            value = value.split('",', 1)[0].strip('"') if value.startswith('"') else value.rsplit(',', 1)[0]
                                            value = str(Path(value).parent)
                                        if value:
                                            found.append(Path(os.path.expandvars(value.strip('"'))))
                                    except OSError:
                                        pass
                        except OSError:
                            continue
            except OSError:
                continue
    return found


def installation_locations():
    found = registry_locations()
    for variable in ('ProgramW6432', 'ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        value = os.environ.get(variable)
        if value:
            base = Path(value)
            for relative in ('TOPDON/TopView', 'TopView', 'Programs/TOPDON/TopView', 'Programs/TopView'):
                found.append(base / relative)
    return found


def qualified_root(directory):
    if not directory or not str(directory).strip():
        return None
    path = Path(os.path.expandvars(str(directory).strip().strip('"')))
    # Accept the install folder, its app subfolder, or an explicitly selected DLL/exe.
    if path.suffix.casefold() in ('.dll', '.exe'):
        path = path.parent
    candidates = [path, path / 'app']
    if path.name.casefold() == 'dll_c001max':
        candidates.append(path.parent.parent)
    for candidate in candidates:
        try:
            library = candidate / LIBRARY
            if library.stat().st_size > 64 * 1024 * 1024:
                continue
            if hashlib.sha256(library.read_bytes()).hexdigest() == DLL_SHA256:
                return candidate.resolve()
        except OSError:
            continue
    return None


def resolve_topview(preferred=None, *, locations=None):
    selected = qualified_root(preferred)
    if selected is not None:
        return selected
    seen = set()
    for candidate in installation_locations() if locations is None else locations:
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        selected = qualified_root(candidate)
        if selected is not None:
            return selected
    raise TopViewSetupError(
        'No compatible TopView camera library was found. In Camera, choose Find TopView '
        'or Browse to the TopView installation folder containing '
        'dll/dll_c001max/libirdvs.dll. TopView 1.30.003 is the tested version. '
        'A saved path from another Windows account may not be accessible. '
        'If your installed version differs, its camera library needs compatibility verification.'
    )
