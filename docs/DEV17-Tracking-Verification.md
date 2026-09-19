# DEV17 tracking verification

Verified locally on Windows on 2026-09-19 with a connected TOPDON TC001 Max. No power instruments were commanded.

- 133 Python tests pass, including native Tk controls, moving extremes, rectangle/polygon search boundaries, deterministic ties, saved layouts, dependent region deletion, original recording compatibility, offline analysis, CSV and PNG exports, and readable coincident tracker labels.
- Live UI test added hottest and coldest whole-image trackers and used Record / Stop to create `20260919-154143-3984e8` (105.703 seconds, 2,643 accepted frames).
- `scripts/verify_recording.py` checked all **129,908,736 temperature values**, all **21,144 measurement CSV rows**, all **2,643 optical/thermal pairs**, and exact first/last raw-frame round trips. All passed; arrival times strictly increased and the session finalized COMPLETE.
- The hottest tracker visited **33 unique pixels**, with 2,643 samples spanning **37.6–40.5375 °C**. The coldest visited **55 unique pixels**, spanning **18.475–19.975 °C**. Every saved position and temperature matched the numerical frame.
- Thermal resolution remained 256 × 192; optical remained lossless 1024 × 768. Tracking does not change the original temperatures or alignment.
- Recording review opened the hardware archive, displayed named moving markers, and completed history validation. Full-frame overview labels are suppressed when equivalent named trackers are present to prevent duplicate labels.
- A second hardware recording, `20260919-155443-6a0f68`, captured full-image and polygon-limited hot/cold trackers together: **867 frames**, **42,614,784 temperature values**, **8,670 CSV rows**, and **867 optical pairs** all verified exactly. It finalized COMPLETE after 34 seconds.
- Selected the hottest tracker in the native review table and clicked its graph to seek from frame 1 to frame 2,245. The marker and coordinates moved to the corresponding recorded thermal pixel while its curve remained continuous. Exported a 26,430-row history CSV and inspected the labeled PNG; corrected an edge label overlapping the export header.

This is software consistency and actual camera capture verification, not a new absolute-temperature calibration or exposure synchronization qualification. A controlled moving synthetic target test also verifies location changes independently of the stationary hardware scene.

The release includes earlier local GUI, polygon, camera-name, timer and automatic-CSV improvements that had not been included in DEV16. Those original local files were preserved separately while this release was developed from the installer branch.
