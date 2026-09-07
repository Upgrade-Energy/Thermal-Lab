# Upgrade Energy Thermal Lab

Standalone thermal camera capture, numerical measurements and recording.
**Power Lab is not required.** This repository owns thermal-camera development;
Power Lab can integrate with it later through a separate, versioned interface.

Version 0.1.0 DEV1 provides command-line tools for one TOPDON TC001 Max on
Windows, full-resolution 256×192 temperature recording, point/area measurements,
USB diagnostics and TopView CSV import. A graphical live-view and playback
interface is planned; it is not included in this first extraction.

## Capture on Windows

Use Python 3.12+ x64 and the tested TopView 1.30.003 installation and camera
driver. There are no third-party Python runtime dependencies. TopView must be
closed during capture; its installed native DLLs are required, but a Windows
SDK and running TopView process are not. Proprietary binaries are not bundled.

From this repository:

```powershell
python scripts/check_tc001.py --output recordings/usb-check-01.json
python scripts/capture_tc001.py --topview-directory 'C:\path\to\TopView' --output recordings/session-01 --seconds 45
```

Use new output paths each time. Capture supports 1–600 seconds and one healthy
camera. It records full numerical frames in `thermal.jsonl.gz`, a seek index in
`thermal.idx`, first/last raw frames, and `camera-session.json`. A successful
session has status `COMPLETE`. `FAILED` or unfinished `RECORDING` sessions are
incomplete. Times are host arrivals, not physical exposure times.

The experimental adapter is locked to the tested camera DLL hash. Temperatures
are apparent readings; host emissivity/environment corrections and absolute
accuracy remain unqualified. See [hardware evidence and limits](docs/TC001-Max-Direct-Capture.md).

## Import existing numerical captures

```powershell
python scripts/import_topview_csv.py --help
python scripts/record_topview.py capture1.csv capture2.csv --unit C --camera-id camera1 --output recordings/import-01
```

Imported recordings preserve their source and use explicitly labeled import
arrival times. They do not invent exposure timestamps or derive temperatures
from colored images. The existing `powerlab-camera-import-v1` format identifier
is retained for file compatibility; it does not imply an application dependency.

## Development

```powershell
python -m unittest discover -s tests -v
```

The `thermal_lab` package is also installable with `python -m pip install .`.
CI tests parsers, numerical decoding and recording without opening hardware.
Hardware tests are run explicitly using the commands above.

Next: standalone live view, measurement editing and recording/playback UI;
longer capture and disconnect/recovery tests; environmental correction;
multi-camera identity and timing. A later Power Lab integration should exchange
run IDs, recording commands and selected measurements with freshness metadata.
No instrument-control code, web server, battery recipes or Power Lab package is
included here.

## Origin

Extracted from Upgrade-Energy/Power-Lab, branch `development/lab-studio-v0.2`,
base commit `d52d2418466b04d343776ffed695359a46e559e3`, including the local camera
development verified on 7 September 2026. Historical evidence is labeled as
pre-extraction. New changes to the camera adapter and tools belong here.
The legacy `Local\PowerLabTC001MaxCapture` mutex name is intentionally retained
to prevent old and new capture workers from opening the same camera together.
