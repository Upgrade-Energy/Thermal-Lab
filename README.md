# Upgrade Energy Thermal Lab

Standalone thermal camera capture, numerical measurements and recording.
**Power Lab is not required.** This repository owns thermal-camera development;
Power Lab can integrate with it later through a separate, versioned interface.

Version 0.1.0 DEV6 adds editable playback points and regions with separate
autosaved analysis layouts, recalculated histories and labeled CSV export.
It includes continuous lossless optical recording and optical/blended
playback alongside numerical thermal frames, temperature-history plots and CSV
export. It also supports independent windows for multiple TOPDON TC001 Max
cameras, with verified Windows device selection and separate measurement layouts.
The native interface includes thermal/optical/blended/side-by-side views, optical alignment,
named temperature points and rectangles, palettes, and numerical recording.
USB diagnostics and TopView CSV import remain available as command-line tools.
Optical storage uses about 2.4 GB/minute per camera at 25 fps. It is an indexed
app-native archive; standard MP4 export remains pending.

See the [TopView feature comparison and proposed UI priorities](docs/TopView-Feature-Review.md)
for overlay alignment, precise measurement placement and recording/playback scope.

## Open the desktop app

Install Python 3.12+ x64 with Tcl/Tk support, then install the desktop dependencies:

```powershell
python -m pip install ".[desktop]"
python scripts/run_thermal_lab.py --topview-directory 'C:\path\to\TopView'
```

After installation, `thermal-lab` also launches the interface. Choose the
TopView installation with Browse if no path was provided, select a camera, then
Connect camera. **Open another camera window** selects the other connected
camera in an independent window; connect and record there separately. Each window
can close without stopping the other. For two Max cameras, use separate USB
controller paths; the tested shared hub could not sustain both streams.
TopView itself must be closed. See the [desktop guide](docs/Desktop-Guide.md).
See [DEV5 optical verification](docs/Optical-Recording-Verification.md) for the
two-camera recording checks and remaining limits.

## Review a recording

Choose **Review recordings** in the live app, or launch the review interface
without connecting any camera:

```powershell
python -m thermal_lab.review --session recordings/session-01
```

After installation, `thermal-lab-review` launches the same player. Open a
finalized session folder, play/pause, step frames, drag the timeline or click a
history plot to seek. Choose a point or region statistic from the history list.
**Export history** writes all recorded measurement histories to a new CSV file.
The source recording stays unchanged. See [playback verification](docs/Playback-Verification.md).

The desktop uses NumPy and Pillow; the original capture/import CLI remains
standard-library-only. No Power Lab application or Windows SDK is required.

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

Use new output paths each time. Capture supports 1–600 seconds per camera.
When multiple cameras are connected, pass `--camera-id` with the Windows instance
ID reported by the diagnostic command. Run separate processes for concurrent CLI
capture. It records full numerical frames in `thermal.jsonl.gz`, a seek index in
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

Next: standard video/image export,
longer capture and disconnect/recovery tests, and environmental correction.
A later Power Lab integration should exchange
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
