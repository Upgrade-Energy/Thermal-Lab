# Thermal Lab — TOPDON TC001 Max thermal camera app

Open-source Windows desktop app for live thermal/optical viewing, numerical
measurements, alignment, recording, playback and CSV/PNG/MP4 export.
**Tested camera: TOPDON TC001 Max. Power Lab is optional and is not required.**

[Download Windows installer](https://github.com/Upgrade-Energy/Thermal-Lab/releases)
· [User guide](docs/User-Guide.md)
· [Report a bug](https://github.com/Upgrade-Energy/Thermal-Lab/issues/new?template=bug_report.yml)
· [MIT license](LICENSE)

## Install and connect

1. Download `Thermal-Lab-Setup-0.1.0-dev19.exe` from the DEV19 release assets.
   Development releases are marked **Pre-release**; use the releases page, not `/releases/latest`.
2. Run setup on Windows 10/11 x64. Python and desktop dependencies are included.
   The installer is unsigned; Windows may display an unknown-publisher prompt.
3. Separately install compatible [TOPDON TopView for Windows](https://www.topdon.com/pages/topdon-apps-thermal-imagers).
   **Tested version: 1.30.003. Newer vendor versions are not automatically compatible.**
4. Connect the TC001 Max, close TopView and other camera owners (including other
   signed-in Windows sessions), then open Thermal Lab and connect the camera.
   Camera settings includes **Find TopView** and validated **Browse** controls.

## USB driver and camera limitations

- Windows **WinUSB** and the installed TopView native libraries are required.
  The EXE does **not** install camera drivers or bundle proprietary TOPDON DLLs.
- The adapter accepts only the tested `libirdvs.dll` SHA-256 documented in
  [direct capture](docs/TC001-Max-Direct-Capture.md). Unknown libraries are rejected.
  Automatic discovery finds a compatible installation; it does not install TopView.
- Our direct raw-WinUSB prototype lost frame alignment on partial transfers.
  The working capture path therefore depends on the vendor library for framing.
  A generic USB driver alone is insufficient. Do not bypass the library hash check.
- **Two cameras need separate USB controller paths.** Shared-hub tests failed;
  replacing the hub did not solve the bandwidth constraint, and the tested native
  FPS request did not reduce USB traffic. See [USB evidence](docs/Shared-Hub-Verification.md).
- TC001, TC002 and other TOPDON cameras are **not qualified by the TC001 Max tests**.
  Physical capture is Windows-only; Linux/macOS live capture is not supported.
- Apparent temperatures are preserved numerically, but absolute accuracy and
  emissivity/environment corrections remain unqualified. Alignment is experimental
  and must be visually inspected. Host arrival times are not exposure synchronization.

## Features and evidence

Named points, rectangles, polygons and moving hot/cold pixel trackers; independent
camera windows; optical/thermal blend and selected-subject alignment; lossless
optical archives and numerical thermal frames; recording review and exports.
Trackers follow extrema, not a recognized physical object. MP4 is a lossy display
export: retain original archives for numerical analysis.

- [User guide](docs/User-Guide.md) — setup, alignment, recording and troubleshooting
- [Detailed desktop guide](docs/Desktop-Guide.md) and [tracking guide](docs/Tracking-Guide.md)
- [DEV18 physical setup verification](docs/DEV18-Setup-Verification.md)
- [DEV17 tracking verification](docs/DEV17-Tracking-Verification.md)
- [Two-camera sustained test](docs/Sustained-Camera-Verification.md)
- [Installation, updates and retained data](docs/Windows-Installation.md)
- [Optional local Power Lab interface](docs/Power-Lab-Integration.md)

DEV19 packages the public documentation, license and bug-report link on top of
DEV18. CI regression and Windows installer checks do not constitute a new
physical-camera qualification. Historical evidence is dated in each document.

## Bugs and contributions

Use **Workspace → Report a bug…** or [GitHub Issues](https://github.com/Upgrade-Energy/Thermal-Lab/issues/new/choose).
The form requests the app/Windows/TopView versions, camera model, USB topology,
reproduction steps, expected result and actual result. Reporting opens GitHub;
it does not upload recordings or submit a report automatically. A GitHub account
is needed to submit issues. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Develop from source

Python 3.12+ x64 with Tcl/Tk:

```powershell
python -m pip install ".[desktop]"
python scripts/run_thermal_lab.py
python -m unittest discover -s tests -v
```

The Windows workflow builds from pinned runtime/wheel inputs, runs regression
and Windows install/shortcut/reinstall/data-preservation checks, then publishes
a versioned EXE and SHA-256 checksum. Existing release assets are never replaced.
Source-only changes are not installed by the updater.

## License and origin

[MIT](LICENSE), copyright Upgrade Energy. Dependencies retain their own licenses:
[third-party notices](THIRD-PARTY-NOTICES.md). No TOPDON proprietary library or
driver is licensed or redistributed by this project. Independent project; not an
official TOPDON application.

Extracted from Upgrade Energy Power Lab in September 2026. The application name,
repository URL and legacy camera mutex are retained for existing updater and
camera-ownership compatibility. See [extraction history](docs/Extraction-Verification.md).
