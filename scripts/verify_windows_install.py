"""Windows CI qualification: install, open app/updater, block busy upgrades, preserve data."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lab_update import app_running


def wait_for(function,seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if function():return
        time.sleep(.2)
    raise AssertionError('Timed out waiting for Windows application')


def close_windows(pid):
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(handle,param):
        owner=wintypes.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid:user.PostMessageW(handle,0x10,0,0)
        return True
    user.EnumWindows(visit,0)


def main():
    assert os.name=='nt'
    settings=json.loads((ROOT/'release.json').read_text());app=settings['app_id']
    installer=next((ROOT/'dist').glob(settings['asset_prefix']+'*.exe'))
    installed=Path(os.environ['LOCALAPPDATA'])/'Programs/UpgradeEnergy'/app
    data=Path(os.environ['LOCALAPPDATA'])/'UpgradeEnergy'/app;data.mkdir(parents=True,exist_ok=True)
    sentinel=data/'installer-ci-preserve.txt';sentinel.write_text('User settings and recordings must survive.')
    thermal_saved=Path.home()/'.thermal-lab/installer-ci-preserve.txt';thermal_saved.parent.mkdir(exist_ok=True);thermal_saved.write_text('Original camera layout marker')
    result=subprocess.run([str(installer),'/S'],timeout=240);assert result.returncode==0,result.returncode
    pointer=(installed/'current.txt').read_text().strip();version=installed/'versions'/pointer
    runtime=version/'runtime/pythonw.exe';launcher=version/'launch_installed.py'
    assert (installed/'Launch.vbs').is_file()
    assert (Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Upgrade Energy'/f"{settings['name']}.lnk").exists()
    evidence=ROOT/'windows-evidence';evidence.mkdir(exist_ok=True)
    child=subprocess.Popen([str(runtime),str(launcher),'app'])
    # Exercise current-user Windows credential encryption without real credentials.
    subprocess.run([str(version/'runtime/python.exe'),'-c',
        "from lab_update import _protect; value=b'ci-synthetic-read-access'; encrypted=_protect(value); assert encrypted != value; assert _protect(encrypted, True) == value"],cwd=version,check=True,timeout=30)
    updater=None
    try:
        wait_for(lambda:app_running(app));assert child.poll() is None
        time.sleep(3)
        if app=='PowerLab':
            url=(data/'launch-url.txt').read_text().strip()
            with urllib.request.urlopen(url,timeout=5) as response:
                html=response.read().decode();assert 'Check for updates' in html
        from PIL import ImageGrab
        ImageGrab.grab().save(evidence/'application-desktop.png')
        result=subprocess.run([str(installer),'/S'],timeout=60)
        assert result.returncode==3,('Running app must block installation',result.returncode)
        assert (installed/'current.txt').read_text().strip()==pointer
        assert child.poll() is None
        if app=='PowerLab':
            import re
            token=re.search(r'name="powerlab-token" content="([^"]+)"',html).group(1)
            request=urllib.request.Request(url+'/api/action',data=b'{"action":"shutdown"}',headers={'Origin':url,'X-PowerLab-Token':token,'Content-Type':'application/json'})
            urllib.request.urlopen(request,timeout=10).close()
        else:close_windows(child.pid)
        child.wait(timeout=25);wait_for(lambda:not app_running(app))
        updater=subprocess.Popen([str(runtime),str(launcher),'updates'])
        time.sleep(4);assert updater.poll() is None
        ImageGrab.grab().save(evidence/'check-for-updates.png')
        # The separate updater remains open while the installer replaces the selected version.
        result=subprocess.run([str(installer),'/S'],timeout=240);assert result.returncode==0,result.returncode
        assert updater.poll() is None
        assert (installed/'current.txt').read_text().strip()!=pointer, 'Reinstall must use a fresh directory'
        assert version.is_dir(), 'Previous runtime must remain available to the updater'
        assert sentinel.read_text()=='User settings and recordings must survive.'
        assert thermal_saved.read_text()=='Original camera layout marker'
        close_windows(updater.pid);updater.wait(timeout=15)
        result=subprocess.run([str(installed/'Uninstall.exe'),'/S'],timeout=60);assert result.returncode==0
        wait_for(lambda:not (installed/'current.txt').exists())
        assert sentinel.read_text()=='User settings and recordings must survive.'
        assert thermal_saved.read_text()=='Original camera layout marker'
        (evidence/'verification.json').write_text(json.dumps(dict(app=app,version=settings['version'],install=True,app_launch=True,busy_install_blocked=True,update_dialog=True,credential_encryption=True,reinstall=True,settings_preserved=True,uninstall_preserves_data=True,hardware_tested=False),indent=2))
        print('PASS: Windows install, app and updater launch, busy-install lock, reinstall and data preservation')
    finally:
        for process in [child,updater]:
            if process and process.poll() is None:process.terminate();process.wait(timeout=10)


if __name__=='__main__':main()
