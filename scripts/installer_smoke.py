"""Verify the complete staged package before atomically activating its shortcuts."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--activate',type=Path);args=parser.parse_args()
    config=json.loads((ROOT/'release.json').read_text())
    for line in (ROOT/'SHA256SUMS.txt').read_text().splitlines():
        expected,name=line.split('  ',1);path=ROOT/name
        if not path.is_relative_to(ROOT) or '..' in Path(name).parts:raise ValueError('Invalid package manifest')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Package checksum failed: '+name)
    import lab_update
    assert lab_update.config()['app_id']==config['app_id']
    runtime=ROOT/'runtime'
    for prefix,variable in [('tcl','TCL_LIBRARY'),('tk','TK_LIBRARY')]:
        choices=sorted((runtime/'tcl').glob(prefix+'[0-9]*'))
        if choices:os.environ[variable]=str(choices[-1])
    import tkinter as tk
    window=tk.Tk();window.withdraw();window.update();window.destroy()
    modules=['powerlab.server','powerlab.lab_engine'] if config['app_id']=='PowerLab' else ['numpy','PIL.Image','lz4.frame','cv2','imageio_ffmpeg','thermal_lab.desktop','thermal_lab.review','thermal_lab.integration','thermal_lab.service_manager']
    for module in modules:importlib.import_module(module)
    if config['app_id']=='ThermalLab':
        import imageio_ffmpeg,subprocess
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-version'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if args.activate:
        # Also recognize older releases that predate the shared installer marker.
        import socket, subprocess
        if config['app_id']=='PowerLab':
            probe=socket.socket()
            try:probe.bind(('127.0.0.1',48763))
            except OSError:raise ValueError('Close the existing Power Lab application before installing.')
            finally:probe.close()
        else:
            command = "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match '(thermal_lab\\.(desktop|review|integration|service_manager)|run_thermal_lab\\.py)' }) { exit 3 }"
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:raise ValueError('Close existing Thermal Lab camera, review and service processes before installing.')
        installed=args.activate.resolve()
        if ROOT.parent!=installed/'versions':raise ValueError('Unexpected installation destination')
        temporary=installed/'current.tmp';temporary.write_text(ROOT.name+'\n',encoding='ascii')
        os.replace(temporary,installed/'current.txt')
    print('PASS: package integrity, runtime, desktop modules and activation',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FAILED:',str(exc),file=sys.stderr);sys.exit(1)
