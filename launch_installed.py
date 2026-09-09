"""Packaged entry points; errors remain visible even with pythonw."""
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    root=Path(__file__).resolve().parent
    runtime=root/'runtime'
    if (runtime/'tcl').exists():
        for prefix,variable in [('tcl','TCL_LIBRARY'),('tk','TK_LIBRARY')]:
            choices=sorted((runtime/'tcl').glob(prefix+'[0-9]*'))
            if choices:os.environ[variable]=str(choices[-1])
    config=json.loads((root/'release.json').read_text())
    mode=sys.argv[1] if len(sys.argv)>1 else 'app';sys.argv=[str(root/'launch_installed.py')]
    if mode=='updates':
        from lab_update import main as updates
        updates();return
    if config['app_id']=='PowerLab':
        from run_app import main as app
        app()
    else:
        module={'app':'thermal_lab.desktop','service':'thermal_lab.service_manager','review':'thermal_lab.review'}.get(mode)
        if module is None:raise ValueError('Unknown Thermal Lab entry point')
        runpy.run_module(module,run_name='__main__')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,str(exc),'Lab application could not start',0x10)
        else:raise
