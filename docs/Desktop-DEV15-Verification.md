# DEV15 desktop refresh and verification

The subsequent [two-camera GUI check](DEV15-Two-Camera-Verification.md) covers
concurrent desktop recording, names, independent layouts and reconnects.
The [measurement CSV check](Measurement-CSV-Verification.md) covers automatic
named point/region logging with recording start and stop.
The [timer and polygon check](Polygon-Timer-Verification.md) covers recording
duration, irregular measurement areas, editing, playback and exports.

Verified locally on Windows on 8 September 2026 (UTC), with the connected TC001 Max.
This update covers the standalone Thermal Lab native app. Power instruments were
not commanded and the Power Lab repository was not changed.

## Changes

The visual reference was the manufacturing app's existing station screenshot:
dark navy surfaces, layered slate panels, blue actions, rounded controls and clear
headings. A shared native theme now covers live capture, recording review,
selected-subject alignment and experimental overlay/calibration. Checkboxes,
sliders, menus, tool icons, focus outlines and disabled states use the same palette.

Live controls are grouped into Measure, Alignment and Camera inspectors. Recording
and connection controls stay in the header. Playback groups measurement editing
and exports into separate tabs, with a reserved timeline and history graph below.
Both inspectors scroll; measurement tables have their own scrollbars.

Automatic Hot and Cold markers identify exact numerical pixel extrema with Celsius
labels. They respect display rotation, zoom, view mode and live freshness. Camera
names persist by Windows identity and are retained in new frame workspace metadata;
review uses the first frame's saved name. Clear all points removes manual points
while preserving regions and alignment.

## Iteration and UI checks

Captured and inspected the baseline and multiple revisions of the running app.
Adjusted oversized controls, replaced the old checkbox glyphs and slider handles,
repaired text encoding, and corrected the playback layout that hid the history
graph beneath the window. Inspected the final PNG export as well as UI screenshots.

Exercised these flows through the native Windows interface:

- Connect the camera, inspect live Blend with moving hot/cold numerical labels.
- Save the name **Desk camera**, restart and verify the same camera/name/layout.
- Switch inspector tabs and open the Workspace menu.
- Open selected-subject alignment, draw a thermal target and preview matching.
  The selected low-contrast scene was ambiguous; guidance was offered and no
  uncertain transform was applied to the live workspace.
- Analyze a frame in experimental overlay. This uncalibrated scene returned 0%
  supported area and the expected uncertainty hatching. Inspect calibration mode
  with its fields and disabled Add/Solve actions. No calibration was saved.
- Record and stop a new session, open it from the live workspace, and inspect playback.
- Play an older archive, add a point in a new archive's separate Analysis layout,
  inspect its complete temperature history and export a labeled PNG. Reopen the
  player, restore that analysis, seek by clicking its graph and inspect Blend at
  the selected time with the saved camera name.

Screenshots, the PNG and audit JSON are local evidence under `runtime/dev15-ui/`.
Camera images are excluded from Git. Representative files are `live-final.jpg`,
`alignment-final.jpg`, `workspace-menu.jpg`, `experimental-overlay.jpg`,
`calibration-screen.jpg`, `review-final.jpg`, `review-history-export.jpg` and `export-check.png`.

## Numerical and recording evidence

Session: `20260908-031953-016313`, status **COMPLETE**.

| Check | Result |
| --- | --- |
| Accepted thermal/optical pairs | 1,368 |
| Rate from host arrival times | 25.0037 fps |
| Numerical values read and checked | 67,239,936 |
| Original optical hashes checked | 1,368 |
| Extrema compared with each grid's min/max | Exact |
| First/last retained native buffers compared | Exact thermal and optical data |
| Saved camera name in frame workspaces | Preserved |

Capture retained the native 256 × 192 thermal grid and lossless 1024 × 768 optical
plane. The UI changes do not reduce camera quality. The audit is stored in
`runtime/dev15-ui/recording-audit.json`.

The automated suite passes **99 tests**, including numerical extrema at image
edges and all four rotations, nonfinite/uniform grids, marker visibility and
staleness, camera-name persistence and validation, bulk point clearing with
region/alignment preservation, and a real Tk playback layout at 1180 × 850.
Existing capture, recording, analysis, alignment and export regression checks
also pass. Captured live/review stderr logs contained no errors.
The three native Tk window checks run on Windows; the numerical regression suite
also remains available to the headless Linux CI job.

## Boundaries

Hot/cold values are apparent pixel temperatures, not area averages or calibrated
absolute accuracy. Automatic extrema are display-only; exported PNG/MP4 labels
still use named measurements. Original numerical grids retain all temperatures.
This session validates the native GUI and one camera's recording path; it does
not requalify two-camera USB bandwidth, exposure synchronization, physical stereo
calibration, alignment accuracy on every target or Power Lab instrument control.
