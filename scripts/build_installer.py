"""Cross-build a per-user Windows x64 installer with an isolated, pinned runtime.

Requires makensis and msiextract. GitHub builds on Ubuntu and verifies on Windows.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
PYTHON_URL='https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip'
PYTHON_HASH='d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15'
TK_URL='https://www.python.org/ftp/python/3.14.7/amd64/tcltk.msi'
TK_HASH='4ae542ab046b3a1b2f10e6c1ee91a215cb4d0638aae373d6e0687472eb7170bd'


def fetch(cache,name,url,digest):
    path=cache/name
    if not path.exists():
        with urllib.request.urlopen(url,timeout=30) as response:path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Dependency checksum mismatch: '+name)
    return path


def copy_source(target,thermal):
    names=['lab_update.py','release.json','launch_installed.py','README.md']
    if not thermal:names+=['run_app.py']
    for name in names:shutil.copy2(ROOT/name,target/name)
    for name in (['thermal_lab'] if thermal else ['powerlab']):
        shutil.copytree(ROOT/name,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'scripts').mkdir();shutil.copy2(ROOT/'scripts/installer_smoke.py',target/'scripts/installer_smoke.py')
    if (ROOT/'docs/Windows-Installation.md').exists():shutil.copy2(ROOT/'docs/Windows-Installation.md',target/'INSTALLATION.txt')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cache',type=Path,default=ROOT/'build/cache');parser.add_argument('--makensis',default='makensis');parser.add_argument('--msiextract',default='msiextract');args=parser.parse_args()
    settings=json.loads((ROOT/'release.json').read_text());thermal=settings['app_id']=='ThermalLab';version=settings['version']
    args.cache.mkdir(parents=True,exist_ok=True)
    runtime_archive=fetch(args.cache,'python-3.14.7-embed-amd64.zip',PYTHON_URL,PYTHON_HASH)
    tk_archive=fetch(args.cache,'tcltk-3.14.7.msi',TK_URL,TK_HASH)
    build=ROOT/'build';build.mkdir(exist_ok=True)
    stage=build/'payload'
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir();copy_source(stage,thermal)
    runtime=stage/'runtime';runtime.mkdir()
    with ZipFile(runtime_archive) as archive:archive.extractall(runtime)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([args.msiextract,'-C',tmp,str(tk_archive.resolve())],check=True,stdout=subprocess.DEVNULL)
        for folder in ('DLLs','tcl','Lib/tkinter'):
            shutil.copytree(Path(tmp)/folder,runtime/folder)
    (runtime/'python314._pth').write_text('python314.zip\n.\nDLLs\nLib\nLib/site-packages\n..\nimport site\n',encoding='ascii')
    if thermal:
        lock=json.loads((ROOT/'scripts/windows-wheels.json').read_text());wheel_dir=args.cache/'wheels';wheel_dir.mkdir(exist_ok=True)
        missing=[row['requirement'] for row in lock if not (wheel_dir/row['filename']).exists()]
        if missing:subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--no-deps','--platform','win_amd64','--python-version','3.14','--implementation','cp','--abi','cp314','--dest',str(wheel_dir),*missing],check=True)
        packages=runtime/'Lib/site-packages';packages.mkdir(parents=True,exist_ok=True)
        for item in lock:
            wheel=wheel_dir/item['filename']
            if hashlib.sha256(wheel.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Wheel checksum mismatch: '+wheel.name)
            with ZipFile(wheel) as archive:archive.extractall(packages)
        shutil.copy2(ROOT/'scripts/windows-wheels.json',stage/'DEPENDENCIES.json')
    (stage/'THIRD-PARTY-NOTICES.txt').write_text('Python 3.14.7: runtime/LICENSE.txt. Tcl/Tk: licenses retained under runtime/tcl.\nThermal Lab dependency licenses are retained in runtime/Lib/site-packages/*.dist-info.\nNo proprietary TopView DLLs or camera drivers are redistributed. Install TopView separately.\n',encoding='utf-8')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(stage).as_posix()+'\n' for p in sorted(stage.rglob('*')) if p.is_file())
    (stage/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8')
    build_id=version+'-'+hashlib.sha256(manifest.encode()).hexdigest()[:12]
    destination=ROOT/'dist';destination.mkdir(exist_ok=True)
    installer=destination/(settings['asset_prefix']+version+'.exe')
    script=(ROOT/'scripts/windows-installer.nsi').read_text()
    values={'APP_ID':settings['app_id'],'APP_NAME':settings['name'],'VERSION':version,'BUILD_ID':build_id,'PAYLOAD':str(stage.resolve()),'OUTFILE':str(installer.resolve()),'SHORT_NAME':settings['repository'].split('/')[1]}
    for key,value in values.items():script=script.replace('@'+key+'@',value)
    generated=build/'installer.nsi';generated.write_text(script,encoding='utf-8')
    subprocess.run([args.makensis,'-V2',str(generated)],check=True)
    digest=hashlib.sha256(installer.read_bytes()).hexdigest();installer.with_suffix('.exe.sha256').write_text(digest+'  '+installer.name+'\n')
    receipt=dict(app=settings['app_id'],version=version,build_id=build_id,installer=installer.name,sha256=digest,size=installer.stat().st_size,runtime_sha256=PYTHON_HASH,tcltk_sha256=TK_HASH,windows_execution='required by release workflow')
    (build/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
