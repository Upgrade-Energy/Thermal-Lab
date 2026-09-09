"""Shared Windows update client. Release installers only; never execute repository source.

Vendored identically in Power Lab and Thermal Lab. No application data is uploaded.
"""
from __future__ import annotations
import atexit
import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
ALLOWED_REPOS = {'PowerLab': 'Upgrade-Energy/Power-Lab', 'ThermalLab': 'Upgrade-Energy/Thermal-Lab'}
UI_FONT = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
MAX_INSTALLER = 1024 * 1024 * 1024


class UpdateError(ValueError):
    pass


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:[.-]?(dev|alpha|beta|rc)(\d+)(?:\.(\d+))?)?', value, re.I)
    if not match:
        raise UpdateError('Unsupported release version')
    major, minor, patch, stage, number, extra = match.groups()
    return (int(major), int(minor), int(patch), {'dev': 0, 'alpha': 1, 'beta': 2, 'rc': 3, None: 4}[stage.lower() if stage else None], int(number or 0), int(extra or 0))


def config():
    metadata = ROOT / 'release.json'
    if metadata.exists():
        value = json.loads(metadata.read_text(encoding='utf-8'))
    else:
        # Preserve the existing pip-installed Thermal Lab entry points.
        from thermal_lab import __version__
        value = dict(app_id='ThermalLab', name='Thermal Lab', repository=ALLOWED_REPOS['ThermalLab'], version=__version__.replace('.dev','-dev'), asset_prefix='Thermal-Lab-Setup-')
    if ALLOWED_REPOS.get(value['app_id']) != value['repository']:
        raise UpdateError('Unknown application update repository')
    version_key(value['version'])
    return value


def data_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'UpgradeEnergy'


def _winapi():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    k.CreateMutexW.restype = ctypes.c_void_p
    k.OpenMutexW.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_wchar_p]
    k.OpenMutexW.restype = ctypes.c_void_p
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k.ReleaseMutex.argtypes = [ctypes.c_void_p]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    return k


_leases = []


def hold_app_lease(app_id):
    """Every app/service/worker holds a marker. Installer owns the startup gate."""
    if os.name != 'nt':
        return
    k = _winapi()
    gate = k.CreateMutexW(None, False, 'Local\\UpgradeEnergy.' + app_id + '.InstallGate')
    if not gate:
        raise UpdateError('Cannot verify installation lock')
    try:
        result = k.WaitForSingleObject(gate, 0)
        if result not in (0, 0x80):
            raise UpdateError('An installation is in progress. Open the app after it finishes.')
        try:
            marker = k.CreateMutexW(None, False, 'Local\\UpgradeEnergy.' + app_id + '.Running')
            if not marker:
                raise UpdateError('Cannot register the running application')
            _leases.append(marker)
            atexit.register(k.CloseHandle, marker)
        finally:
            k.ReleaseMutex(gate)
    finally:
        k.CloseHandle(gate)


def app_running(app_id):
    if os.name != 'nt':
        return False
    k = _winapi()
    handle = k.OpenMutexW(0x100000, False, 'Local\\UpgradeEnergy.' + app_id + '.Running')
    if handle:
        k.CloseHandle(handle)
        return True
    if ctypes.get_last_error() != 2:
        raise UpdateError('Cannot verify that the application is closed')
    return False


def _protect(data, decrypt=False):
    if os.name != 'nt':
        raise UpdateError('Saved GitHub access is available in the Windows installer. Use GH_TOKEN for development.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    method = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise UpdateError('Windows could not unlock GitHub access. Connect again on this Windows account.')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel = ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(output.data)


def credential_path():
    return data_root() / 'GitHub' / 'read-access.dpapi'


def save_token(value):
    value = value.strip()
    if not re.fullmatch(r'[A-Za-z0-9_]{20,255}', value):
        raise UpdateError('Enter a GitHub read-only access token.')
    encrypted = _protect(value.encode())
    path = credential_path();path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp');temp.write_bytes(encrypted);temp.replace(path)


def get_token():
    for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if os.environ.get(key):
            return os.environ[key]
    path = credential_path()
    if path.exists():
        return _protect(path.read_bytes(), decrypt=True).decode()
    cli = shutil.which('gh')
    if cli:
        try:
            result = subprocess.run([cli, 'auth', 'token', '--hostname', 'github.com'], capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0:
                return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ''


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in {'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'} or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise UpdateError('Release download redirected outside GitHub')
        result = super().redirect_request(request, fp, code, msg, headers, newurl)
        if result and parsed.hostname != 'api.github.com':
            result.remove_header('Authorization')
        return result


def request(path, token, binary=False):
    if not path.startswith('/repos/') or '..' in path:
        raise UpdateError('Invalid GitHub request')
    headers = {'User-Agent': 'UpgradeEnergy-Lab-Updater/1', 'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        return urllib.request.build_opener(ReleaseRedirect()).open(urllib.request.Request('https://api.github.com' + path, headers=headers), timeout=20)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 404):
            raise UpdateError('GitHub access is needed. Connect a read-only token with Contents access to this repository.') from None
        if exc.code in (403, 429):
            raise UpdateError('GitHub refused the request or its rate limit was reached. Check repository access and try again later.') from None
        raise UpdateError('GitHub could not provide this update (HTTP %d).' % exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise UpdateError('Could not reach GitHub. Check internet access and try again. The installed app is unchanged.') from None


def select_release(releases, settings, preview):
    current = version_key(settings['version']);candidates = []
    for release in releases:
        if release.get('draft'):
            continue
        tag = release.get('tag_name', '')
        try:
            version = version_key(tag)
        except (UpdateError, TypeError):
            continue
        if version <= current or (not preview and (release.get('prerelease') or version[3] != 4)):
            continue
        name = settings['asset_prefix'] + tag.removeprefix('v') + '.exe'
        for asset in release.get('assets', []):
            if asset.get('name') != name or asset.get('state') != 'uploaded':
                continue
            digest = asset.get('digest', '')
            if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                continue
            if type(asset.get('id')) is not int or asset['id'] <= 0 or type(asset.get('size')) is not int or not 0 < asset['size'] <= MAX_INSTALLER:
                continue
            candidates.append((version, dict(version=tag.removeprefix('v'), name=name, asset_id=asset['id'], size=asset['size'], sha256=digest[7:], notes=str(release.get('body') or '')[:16000])))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def check(settings, preview, token=None):
    token = get_token() if token is None else token
    releases = []
    for page in range(1, 6):
        with request('/repos/' + settings['repository'] + '/releases?per_page=100&page=' + str(page), token) as response:
            raw = response.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise UpdateError('GitHub release response is too large')
        items = json.loads(raw)
        if not isinstance(items, list):
            raise UpdateError('GitHub returned an invalid release list')
        releases.extend(items)
        if len(items) < 100:
            return select_release(releases, settings, preview)
    raise UpdateError('Too many release pages to verify. Open GitHub releases to review the available builds.')


def verify_installer(path, release):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise UpdateError('The download is not a Windows installer')
        stream.seek(0)
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if Path(path).stat().st_size != release['size'] or digest.hexdigest() != release['sha256']:
        raise UpdateError('Installer checksum did not match GitHub. The update was not installed.')


def download(settings, release, token=None):
    token = get_token() if token is None else token
    folder = data_root() / settings['app_id'] / 'updates';folder.mkdir(parents=True, exist_ok=True)
    # Name comes from validated app metadata and a parsed version, never from a URL.
    if not re.fullmatch(re.escape(settings['asset_prefix']) + r'[0-9A-Za-z.\-]+\.exe', release['name']):
        raise UpdateError('Invalid installer name')
    destination = folder / release['name']
    temporary = destination.with_suffix('.part')
    started = time.monotonic()
    try:
        with request('/repos/' + settings['repository'] + '/releases/assets/' + str(release['asset_id']), token, binary=True) as response, temporary.open('wb') as output:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > release['size'] or total > MAX_INSTALLER or time.monotonic() - started > 600:
                    raise UpdateError('Installer download exceeded its expected size or time limit')
                output.write(block)
        verify_installer(temporary, release)
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def launch_installer(path, release, settings):
    if os.name != 'nt':
        raise UpdateError('Run this installer on Windows 10 or 11 x64.')
    if app_running(settings['app_id']):
        raise UpdateError('Close all ' + settings['name'] + ' windows and its background service, then click Install update again. The download is ready.')
    verify_installer(path, release)
    subprocess.Popen([str(path)], close_fds=True)


def open_updates():
    subprocess.Popen([sys.executable, str(ROOT / 'lab_update.py')], cwd=str(ROOT), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def main():
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser
    settings = config();root = tk.Tk();root.title(settings['name'] + ' · Updates');root.geometry('700x610');root.minsize(700,610)
    style = ttk.Style();style.theme_use('clam')
    style.configure('.', font=(UI_FONT, 11), background='#f3f6f9', foreground='#172b40')
    style.configure('TButton', padding=(12,8));root.configure(bg='#f3f6f9')
    frame = ttk.Frame(root, padding=24);frame.pack(fill='both', expand=True)
    ttk.Label(frame, text=settings['name'] + ' updates', font=(UI_FONT, 23, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Installed: ' + settings['version'] + '   ·   Windows x64').pack(anchor='w', pady=(6,15))
    preview = tk.BooleanVar(value=version_key(settings['version'])[3] != 4)
    ttk.Checkbutton(frame, text='Include development releases', variable=preview).pack(anchor='w')
    status = tk.StringVar(value='Ready to check GitHub for a packaged update.')
    ttk.Label(frame, textvariable=status, wraplength=600).pack(fill='x', pady=15)
    notes = tk.Text(frame, height=9, wrap='word', font=(UI_FONT,11), bg='white', fg='#24374a', relief='flat', padx=12, pady=12, state='disabled')
    notes.pack(fill='both', expand=True)
    actions = ttk.Frame(frame);actions.pack(fill='x', pady=15)
    result = {};events = queue.Queue();working = False

    def set_notes(value):
        notes.configure(state='normal');notes.delete('1.0','end');notes.insert('1.0',value);notes.configure(state='disabled')

    def task(kind, function):
        nonlocal working
        if working:return
        working = True;check_button.configure(state='disabled');download_button.configure(state='disabled');install_button.configure(state='disabled')
        status.set('Checking GitHub...' if kind == 'check' else 'Downloading and verifying the installer...')
        def run():
            try:events.put((kind, function(), None))
            except Exception as exc:events.put((kind, None, str(exc) if isinstance(exc, UpdateError) else 'The update could not be completed. Check internet access and available disk space, then try again.'))
        threading.Thread(target=run, daemon=True).start()

    def do_check():
        if working:return
        include_preview = preview.get();result.clear();set_notes('');task('check', lambda: check(settings, include_preview))

    def do_install():
        try:launch_installer(result['path'], result['release'], settings);status.set('Installer opened. Follow its steps, then reopen ' + settings['name'] + '.')
        except (UpdateError, OSError) as exc:status.set(str(exc))

    check_button = ttk.Button(actions, text='Check for updates', command=do_check);check_button.pack(side='left')
    download_button = ttk.Button(actions, text='Download update', state='disabled', command=lambda: task('download', lambda: download(settings, result['release'])));download_button.pack(side='left', padx=8)
    install_button = ttk.Button(actions, text='Install update', state='disabled', command=do_install);install_button.pack(side='left')

    def access():
        dialog = tk.Toplevel(root);dialog.title('Connect GitHub');dialog.geometry('600x310');dialog.transient(root)
        pane = ttk.Frame(dialog,padding=22);pane.pack(fill='both',expand=True)
        ttk.Label(pane, text='Private repository access', font=(UI_FONT,17,'bold')).pack(anchor='w')
        ttk.Label(pane, text='Use a fine-grained GitHub token with Contents: Read-only for Power-Lab and Thermal-Lab. Saved access is encrypted for your Windows account and shared by these two updaters.',wraplength=540).pack(anchor='w',pady=12)
        token = ttk.Entry(pane,show='•');token.pack(fill='x');token.focus_set()
        def save():
            try:save_token(token.get());token.delete(0,'end');dialog.destroy();do_check()
            except UpdateError as exc:messagebox.showerror('GitHub access',str(exc),parent=dialog)
        ttk.Button(pane,text='Save access and check',command=save).pack(anchor='w',pady=10)
        ttk.Button(pane,text='Open GitHub token settings',command=lambda:webbrowser.open('https://github.com/settings/personal-access-tokens')).pack(anchor='w')

    links = ttk.Frame(frame);links.pack(fill='x')
    ttk.Button(links,text='Connect GitHub',command=access).pack(side='left')
    ttk.Button(links,text='Forget saved access',command=lambda:(credential_path().unlink(missing_ok=True),status.set('Saved GitHub access removed.'))).pack(side='left',padx=8)
    ttk.Button(links,text='Release history',command=lambda:webbrowser.open('https://github.com/'+settings['repository']+'/releases')).pack(side='left')
    ttk.Label(frame, text='Settings and recordings stay in place. Close the app and its service before installing.',wraplength=600,foreground='#526679').pack(anchor='w',pady=(16,0))

    def poll():
        nonlocal working
        try:
            kind, value, error = events.get_nowait();working = False;check_button.configure(state='normal')
            if error:status.set(error)
            elif kind == 'check':
                result['release'] = value
                if value:
                    status.set('Available: ' + value['version'] + '  ·  %.1f MB' % (value['size']/1024/1024));set_notes(value['notes'] or 'No release notes provided.');download_button.configure(state='normal')
                else:status.set('No newer packaged release is available for this update channel.');set_notes('You can keep using the installed version. New fixes appear here after a Windows release is published.')
            else:
                result['path'] = value;status.set('Download verified. Close '+settings['name']+' and its service, then choose Install update.');install_button.configure(state='normal')
            if error and result.get('release'):download_button.configure(state='normal')
        except queue.Empty:pass
        root.after(100,poll)
    root.after(100,poll);root.after(250,do_check);root.mainloop()


if __name__ == '__main__':
    main()
