# Two-camera 30-minute verification — 7 September 2026

Tested DEV7 production acquisition workers on this Windows 11 PC with two
TC001 Max cameras, one direct and one through the previously verified hub on
a separate USB controller. Both connected without startup retries. This test
exercised worker capture and recording, not a sustained desktop-window test.
No Power Lab application, Windows SDK or power instrument commands were used.

## Capture and numerical results

| Check | Camera 0, direct | Camera 1, hub |
| --- | ---: | ---: |
| Finalized thermal/optical frame pairs | 45,008 | 45,010 |
| First-to-last duration | 1,801.875 s | 1,801.875 s |
| Average accepted-frame rate | 24.9779 fps | 24.9790 fps |
| Largest host-arrival gap | 93 ms | 94 ms |
| 99th-percentile host-arrival gap | 47 ms | 47 ms |
| Accepted sequence gaps | 0 | 0 |
| Numerical temperature values checked | 2,212,233,216 | 2,212,331,520 |
| Exported history values checked | 225,040 | 225,050 |
| Apparent temperature range across all pixels | 20.0375–25.725 °C | 20.35–35.2875 °C |

Camera 0 Windows instance: `USB\VID_3474&PID_4962\6&2A549464&0&2`.
Camera 1 Windows instance: `USB\VID_3474&PID_4962\YFDVS000000000001`.
The tested native DLL SHA-256 is
`f7a745d1e056e1dcda6de43ee30483fa5490eeb535bc18bbbd7ff031fcf6d3e6`.
Recording began at 00:04:36 UTC on 8 September (17:04:36 PDT on 7 September).

Both sessions finalized as `COMPLETE`, with null errors and worker exit code 0.
The source archives occupy 73,232,868,963 and 73,078,135,436 bytes
(146.31 GB combined, primarily lossless optical data).
Every indexed optical plane passed its SHA-256 and thermal-pairing checks.
Every thermal grid passed the production playback reader, with independent
point and rectangular-region calculations. CSV values, elapsed times, camera
identity, geometry and original-recorded provenance matched the histories.
First and last raw buffers reproduced the saved temperatures and optical bytes
exactly. Two points and one rectangular region provided five histories per
camera: two point values and region minimum, mean and maximum.

Inspected optical/thermal preview pairs at startup and each five-minute
checkpoint through minute 25. Both views remained intact. Camera-worker
working sets were approximately 59–65 MB at minute 9, 66 MB at minute 15 and
63–66 MB at minute 20. The post-run Windows USB diagnostic reopened both
camera interfaces successfully, with status OK and device problem code 0.

## Source optical repetition

Camera 0 contained 460 repeated optical planes in 33 adjacent-repeat runs;
camera 1 contained 461 in 30 runs. The longest run was 18 identical optical
planes spanning 0.687 seconds in either camera. Including the interval until
the next changed optical plane, the longest holds were 0.719 and 0.734 seconds.
The larger bursts occurred
approximately once per minute. Native full-buffer hashes changed across every
repeat run's endpoints, and temperatures generally changed too (identical
temperature grids at the endpoints of 2 and 4 runs respectively).

This is observed source-buffer behavior, not evidence of corrupted recording
or an exposure-synchronization guarantee. Its underlying device/SDK cause was
not established. The archive preserves every accepted buffer and does not
silently remove repeated optical planes or invent new optical exposures.

## Media verification

Both end-to-end verifiers completed with `PASS` and process exit code 0.
Each full-length thermal MP4 decoded to 45,048 frames at 1024×768 and 25 fps,
lasting 1,801.92 seconds. Source mappings include the first and last recorded
frames. Camera 0's MP4 is 880,670,222 bytes; camera 1's is 700,851,262 bytes.
All seven files in each source archive retained identical SHA-256 hashes after
history export, PNG export, full video rendering and full video decoding.

Inspected first, midpoint and last blended PNGs and decoded thermal video
samples from both cameras directly. Images, temperature labels and region
geometry were intact and readable. These are presentation exports at a fixed
25 fps; their mapping may hold or skip source frames to represent host-arrival
time. The original numerical and lossless optical archives remain authoritative.

## Evidence and reproduction

Local source archives: `recordings/soak-20260907-30min/camera0` and `camera1`.
Capture events, progress, USB diagnostics and repeat audits are in their parent
directory. Verification outputs are in
`runtime/soak-20260907-30min-verify-camera0` and `camera1`, including CSV,
blended PNG snapshots and full-length thermal MP4 presentation exports.
Raw recordings and media remain local and are excluded from Git.

Committed [machine-readable evidence](camera-evidence/sustained-20260907-verification.json)
includes both complete verifier results, source hashes, output artifact hashes,
capture events, USB state and the optical repetition findings.

See [the repeatable test procedure](Sustained-Camera-Test.md). The 48 automated
tests passed during this run. No production capture changes were required to
complete the sustained capture or numerical audit.

The run did not test disconnect/reconnect, hub interruption, forced low disk,
sleep/resume, absolute temperature calibration or environmental correction.
Host-arrival sequence continuity does not establish the camera's internal
exposure/drop count. Temperatures remain apparent readings; zero-offset
overlay alignment in these test layouts is not geometric calibration.
