# Sustained two-camera recording test

These explicit hardware checks exercise the production camera workers,
recorders, playback reader, temperature histories and media exporters. They do
not connect to power instruments. Close other programs using the cameras before
starting. Use two TC001 Max cameras on the verified separate USB controller
paths; a hub on one path is supported by this test setup.

```powershell
python scripts/soak_cameras.py --seconds 1800 --topview-directory 'C:\path\to\TopView' --output recordings/soak-01
python scripts/verify_soak.py recordings/soak-01/camera0 --output runtime/soak-01-verify-camera0
python scripts/verify_soak.py recordings/soak-01/camera1 --output runtime/soak-01-verify-camera1
```

Use new output directories. Install the desktop dependencies first. The capture
requires exactly two detected cameras and checks disk capacity before opening
them. The default 30-minute run reserves an estimated 172 GB of free capacity;
actual use depends on thermal compression. Both optical planes and numerical
temperature frames are recorded. Each camera has two temperature points and
one rectangular region. Preview images are saved at startup and every five
minutes, with progress and final worker events saved alongside the recordings.

The capture stops both workers if either reports an error, previews become
stale, a worker exits unexpectedly, or free space falls below 10 GB. A normal
run adds two seconds to the requested duration to allow the finalized
first-to-last recording span to meet the requested minimum. The capture result
`CAPTURE_FINISHED` is not a verification pass: run the verifier afterward.

The verifier checks every indexed thermal frame and matching optical plane,
camera identity, accepted-frame sequence continuity, all point/region values,
and every exported history CSV value. First and last raw buffers must reproduce
the saved numerical temperatures and optical bytes exactly. It exports blended
PNG snapshots from the beginning, middle and end, then a full-length labeled
thermal MP4 and decodes every video frame. Source file hashes must remain
unchanged throughout. Inspect the snapshots and decoded video samples directly.

`verification.json` reaches `PASS` only after all checks complete. The
intermediate `RECORDING_AND_HISTORIES_PASS` status excludes media verification.
This is a fixed-layout test; it expects unchanged measurement geometry during
recording. For shorter trial recordings, set `--minimum-seconds` explicitly.

Times describe Windows host arrival, not device exposure synchronization.
Sequence continuity concerns frames accepted by the native adapter; it cannot
establish how many exposures the camera generated internally. Numerical checks
verify data integrity and calculations, not absolute temperature calibration.
PNG/MP4 are presentation exports; the source archive retains numerical data.

Disconnect/reconnect, hub interruption, forced low-disk conditions, and
environmental/emissivity calibration are separate tests.
