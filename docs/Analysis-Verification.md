# DEV6 playback analysis verification — 7 September 2026

The offline player now supports independent analysis points and rectangular
regions, placement and movement on the saved thermal grid, renaming/removal,
current-frame values, full-recording histories and CSV export. Original recorded
measurements remain selectable. Edits apply fixed geometry to every frame.

Analysis autosaves outside the archive, under `~/Thermal-Lab-Analysis`. Named
copies use exclusive creation and cannot be saved within the source recording.
SHA-256 binding covers the manifest, thermal index and full numerical archive;
analysis for a different recording is rejected. Invalid layouts cannot replace
the last valid autosave. CSV labels offline analysis separately from original
recorded measurements and includes the recording fingerprint.

## Windows and real-recording checks

Used the existing two-camera hardware recording
`runtime/selected-workers-135427/camera0`, containing 499 frames from the
TC001 Max ending `YFDVS000000000001`. No new camera acquisition or power
instrument commands were needed for this offline feature.

Inspected the native interface while adding a point over a warm feature
(23.850 °C), drawing a region (21.66 / 22.61 / 24.85 °C), moving the point
to a cooler location (21.975 °C), and renaming it to “Surface probe.” Values
and full histories updated after the edits. Switching back to Recorded restored
the original “Camera 0 probe” at 22.100 °C and its original geometry.

An independent calculation checked all 1,996 analysis scalar samples: one point
plus region minimum, mean and maximum for every frame. Exported CSV contained
1,996 rows with the offline-analysis basis and fingerprint. Autosave and named
copy reloads preserved the exact definitions. All seven source archive files
retained identical SHA-256 hashes before and after analysis.

See [machine-readable results](camera-evidence/analysis-dev6-verification.json).
Local verification outputs are `runtime/analysis-dev6-history.csv` and
`runtime/analysis-dev6-copy.json`.

## Automated validation

44 tests pass. New coverage checks spatially varying numerical grids, moved
point histories, region statistics, original-history preservation, source file
immutability, reload/copy/export provenance, wrong-recording rejection, invalid
layout preservation, all four display rotations and region movement at sensor
boundaries. Existing optical recording and playback tests also pass.

The DEV6 wheel builds successfully. Native review error logs were empty.
The UI review found and corrected unreadable radio-button hover styling and
clarified analysis versus original-measurement labels.

## Limits

Analysis applies a fixed geometry across the entire recording; it does not track
moving objects or support time-varying analysis keyframes. Rectangle resizing,
polygons, lines and multiple analysis layers are not implemented. Save a named
copy before creating an alternative layout. Optical alignment follows the
original recorded frame. Temperatures remain apparent Celsius values; physical
exposure synchronization and absolute temperature calibration are unqualified.
