# Standalone extraction verification — 7 September 2026

The standalone `thermal_lab` package passed 17 camera unit tests on native
Windows Python 3.12. The package, scripts and tests have no `powerlab` imports.
Only numerical validation helpers were extracted from Power Lab's models;
instrument models, controllers, servers and recipes were not copied.

A new 10-second hardware run from this repository completed with 160 distinct
256×192 frames, 162 received buffers and two startup discards. Observed host
rate was 16.519 fps on this run. Earlier pre-extraction runs achieved about
25 fps; sustained performance under varying host load remains qualification
work. No assertion of device-level drop-free capture is made.

Independent indexed playback checked all 7,864,320 numerical values, increasing
arrival times, stored center measurements, and exact raw-to-recorded round trips
for the first and last frames. See [machine-readable result](camera-evidence/extraction-check-verification.json).
Raw data remain locally in ignored `recordings/extraction-check`.

To verify another direct capture from the repository root:

```powershell
python scripts/verify_recording.py recordings/session-01
```

The verification script writes its JSON report to `docs/camera-evidence` and
requires Python assertions enabled. It is an explicit developer check, not an
automatic repair or recovery tool.

The native DLL was loaded from the existing TopView installation in the original
workspace. This is a vendor-runtime dependency, not a Power Lab application
dependency; another installation with the tested DLL and dependencies can be
selected with `--topview-directory`.
