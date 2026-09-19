# Thermal Lab desktop — DEV17

For named moving hottest/coldest measurements, see [Tracking guide](Tracking-Guide.md). DEV17 records their temperatures and pixel positions with Record / Stop and replays them in review.

Launch `thermal-lab` after `python -m pip install ".[desktop]"`, or run
`python scripts/run_thermal_lab.py` from the repository. Requires Windows x64
Python 3.12+ with Tcl/Tk, NumPy, Pillow, the tested TopView installation and its
camera driver. The native acquisition ABI remains experimental and hash-locked.

In the **Camera** tab, select the TOPDON runtime folder if it was not supplied
at launch. Close TopView, choose a camera from the
list, and click **Connect camera**. Refresh rescans connected devices while
disconnected. Native acquisition runs in a separate process. Disconnect releases
the camera. Closing the window requests shutdown and finalizes any numerical
recording; an unresponsive worker is terminated after a bounded wait and its
unfinished recording must be treated as incomplete.

## Find your controls

The desktop uses the manufacturing app's dark navy and blue visual family,
with rounded actions, consistent line icons and grouped controls:

- **Above the image:** view, palette, rotation, Fit and the measurement/movement tools.
- **Measure:** automatic hot/cold readings, named points and regions, and layout actions.
- **Alignment:** selected-subject alignment, optical sliders, lock/reset and experimental tools.
- **Camera:** friendly name, device identity, capture options, USB guidance, color range and runtime folder.
- **Header:** Connect/Disconnect, Record/Stop, Recordings and the Workspace menu.

Scroll within the inspector to reach its lower controls on shorter displays.
The divider beside the image adjusts the inspector width. **Workspace** also
provides recording review, another camera window, saved layouts and Close window.

## Name a camera

Select the camera, open **Camera**, enter a useful name such as **Pack front**,
and click **Save camera name**. The selector and window title use the new name.
Names are local to this Windows user and persist in
`~/.thermal-lab/camera-names.json`. They are associated with the Windows device
identity, so two cameras keep separate names and layouts. The full identity is
still visible in the Camera tab; the selector's final number only distinguishes
entries in the current list.

New recorded frames retain the name in their workspace metadata. Recording review
shows the name saved in the first frame, with the hardware identity available in
the Export tab. Renaming does not rewrite older recordings. A location-based
Windows identity can change after moving USB ports; name that new identity if needed.
Other windows read updated names when you open their camera list, use Refresh or
reconnect. Camera selection still uses the hardware identity, even when two
friendly names are identical.

## Two cameras

In **Camera** or **Workspace**, click **Open another camera window** to open an independent workspace with the
other detected camera selected. Connect it there. Each window has independent
view controls, alignment, points/regions and Record/Stop controls. A camera
already owned by another window cannot be acquired a second time. Closing either
window finalizes its recording and leaves the other running.

Use separate USB controller paths for two TC001 Max units. Our shared-hub tests
failed; moving one camera to another controller enabled concurrent recordings.
The title shows the saved camera name, or its Windows instance suffix when unnamed.
Location-based IDs may change when ports change, in which case a fresh layout
is used. Device indexes are never saved as camera identities. Physical exposure
synchronization is not provided by concurrent capture.

## Live views and alignment

Choose Thermal, Optical, Blend or Side by side. Optical is mapped into the
thermal sensor's coverage for overlay comparison. The rotation dropdown turns
both displayed layers together; it never rotates stored temperature arrays.
Use the mouse wheel to zoom, Pan to drag the view, and Fit to reset the viewport.

In **Alignment**, Thermal opacity controls the blend. **Align optical** lets you drag the optical
layer while thermal pixels and measurements stay fixed. Drag the X/Y, scale and
rotation sliders to adjust the overlay by eye; the adjacent number fields remain
available for fine adjustments. X/Y offsets are in native thermal pixels, before
display rotation; scale and angle adjust only the optical layer. Numeric edits
apply with Enter or when leaving the field and keep the sliders synchronized. Lock
alignment prevents changes; Reset restores the default optical transform.
This initial transform is not a factory registration calibration. Adjust it
for the target plane and distance; objects at different depths may not align.

### Auto alignment and working distance

For the experimental continuous regional preview and measured stereo calibration,
use **Alignment → Experimental overlay / calibration…** and follow the [Smart overlay guide](Smart-Overlay.md).

Open **Align selected area…** in the Alignment tab. The tool freezes a fresh
thermal/optical pair while live acquisition continues. Keep the target stationary
and draw a rectangle around one object on the left thermal image, including its
outline and a little background. A selected measurement rectangle in the main
window is imported automatically. Click **Preview auto-alignment**, inspect the
blended outline, then **Apply to live**. This tool does not require a checkerboard.
Nothing changes in the live workspace until Apply. Cancel search
stops the background matcher. Refresh pair takes another image pair.

DEV14 searches scale and rotation around the selected subject and uses measured
edges rather than artificial edges from the selection rectangle. A new subject
is fitted independently; entering its distance is not required. Tight selections
with weak or incompatible features can still be ambiguous.

For a face or other target that remains misaligned, use **Match shared points**.
The tool zooms into the target. Click a recognizable feature on the LEFT, then
the same feature on the raw optical image on the RIGHT. Repeat for at least three
points spread across the selected subject, such as both eyes and the nose if
visible in both sensors. Click **Preview point fit**, inspect, then **Apply to live**.
Use **Undo point** to correct a click; turn off **Zoom selected target** if the
optical subject is outside the enlarged view. No distance or numerical offset is
needed. The fit solves offset, uniform scale and rotation from the shared points.
It rejects nearly collinear or inconsistent pairs. Its displayed residual measures
agreement at your clicks, not independently measured registration accuracy.
Preview auto-alignment preserves an existing three-point fit instead of drifting
away from those constraints. Refreshing or selecting a new thermal area clears them.

This changes overlay registration, not optical focus. A three-dimensional face
can retain local differences between the two viewpoints; no similarity transform
can guarantee every pixel corresponds perfectly. See [DEV14 verification](Subject-Alignment-DEV14.md).

If matching is uncertain, the tool enables **Guide with optical target box**. Draw a box
around the same object's outline on the raw optical image at right. The tool
estimates offset and scale from the paired boxes, retaining the current rotation.
Preview auto-alignment can then refine locally. An uncertain refinement retains the box-based
estimate; inspect it before applying. Manual sliders remain useful for fine tuning
and initial rotation. The frozen preview uses a fixed 180° display orientation.

Save a reviewed result with a target name such as Near bench or Far wall. Optionally
enter its measured working distance in metres. Profiles are specific to the camera
identity and stored in `alignment-profiles/` beside the workspace file. Preview
profile recalls one. To estimate another working distance, save at least two
profiles at different known distances, enter a distance between them and click
**Predict at distance**. Check the preview and Apply. Prediction interpolates in
inverse distance and refuses extrapolation. Update profiles after changing the
camera mounting or optical geometry.

This is target-plane alignment, not automatic depth measurement or a factory
calibration. The camera does not supply target distance. One global overlay cannot
simultaneously remove parallax for objects at different depths. Profile prediction
is an estimate requiring visual review; perspective and occlusion remain possible.
Automatic matching is experimental and may require paired-box guidance when hot
features do not correspond to visible outlines. Match scores are not accuracy
percentages. Alignment never resamples the recorded temperature grid, changes
measurement coordinates, or reduces raw optical recording quality.

Choose Iron, Rainbow, White hot or Black hot above the image. In the Camera tab,
Automatic range follows the
current thermal minimum/maximum; disable it and enter low/high Celsius values
for a fixed color scale. These display choices do not change measured values.

## Measurements

### Automatic hottest and coldest markers

The live image automatically tracks the hottest and coldest **measured pixels in
the full thermal frame**, with orange **Hot** and blue **Cold** temperature labels.
The Measure tab also shows both numbers. Turn off **Show hot / cold markers** to
hide the image labels. Markers follow the numerical grid, independently of the
palette or optical alignment, and remain correctly positioned when rotating or
zooming. Off-screen points are not drawn; the numerical sidebar still reports
the full-frame extremes. Live readings disappear when the frame becomes stale.

Markers appear in Thermal and Blend, and on the thermal half of Side by side.
Pure Optical has no automatic thermal markers. Recording review offers the same
toggle under Measurements, calculated from each saved frame. A uniform grid has
one combined Hot / Cold marker. Ties use the first matching sensor pixel.

These are pixel extrema, not region averages or tracked objects. They do not add
points to a layout or extra history series. The original grids already preserve
every temperature. Automatic hot/cold markers are display-only and are not burned
into PNG or MP4 exports; use a named point or region for exported measurement labels.

### Named points and regions

Choose **Point** and click a pixel, **Rectangle** and drag a region, or **Polygon**
for an irregular outline. Points
display a temperature; regions report minimum, mean and maximum. Select a row,
edit its name and click Rename. Select mode allows dragging a point or region;
draw a replacement rectangle to change its size. **Remove selected** deletes the selected
measurement. The mouse readout identifies the native thermal pixel and apparent
temperature. Zoom in for precise placement.

### Polygon areas

1. Choose **Polygon** above the live image. Click corners around the subject in
   order. A numbered dashed outline previews the shape; at least three corners
   are required, with a maximum of 64.
2. Correct a corner with **Undo corner**, **Backspace**, or a right-click on the
   image. **Cancel** or **Escape** discards the unfinished shape.
3. Click the first corner again, press **Enter** while the image has focus, or
   click **Finish polygon**. The tool returns to Select and the new polygon
   appears in the measurement table. Rename it like any other area.
4. In **Select**, drag inside the polygon to move it. Select it to reveal corner
   handles, then drag a handle to reshape it. Crossing edges, duplicate corners,
   and shapes containing no thermal pixel centers are rejected.

Concave outlines are supported. Minimum, mean and maximum use only thermal
pixels whose centers lie inside or on the polygon edge, never the whole bounding
rectangle. Polygons move with the display when zooming or rotating, while their
stored coordinates remain on the thermal sensor. Unfinished outlines do not add
measurements to a recording. Changing tools or cameras cancels an unfinished shape.

Polygon geometry and measurements are retained in layouts, recordings, playback,
CSV and labeled PNG/MP4 exports. Automatic CSV adds `shape` and `vertices` columns;
`x/y/x2/y2` give its bounding box. In recording review, choose **Analysis → Polygon**
to measure an irregular area across an existing recording, using the same corner
controls. Analysis changes remain separate from the source archive. The alignment
tool still uses a rectangular target crop, enclosing a selected polygon.

### Automatic measurement CSV with Record / Stop

1. Add the points and rectangles you want to measure. Select each in the
   **Measure** table, enter a meaningful **Selected measurement name** (for
   example **Positive terminal** or **Pack casing**), and click **Rename** or
   press Enter.
2. Click **Record session**. Every named point and region in that camera's layout
   is recorded automatically; highlighting a table row does not restrict logging.
3. Click **Stop recording**. After the session completes, click **Show CSV** beside
   **Recordings** to reveal `measurements.csv` in File Explorer. Open that file in
   Excel or import it into your spreadsheet program.
   The file is also in that session's folder under `~/Thermal-Lab-Recordings/`.

The CSV starts and stops with the recording. It has one row per measurement per
recorded frame, with elapsed seconds from recording start, camera and measurement
names, a stable measurement ID, and temperatures in Celsius. Point rows have
`value_c`; region rows have `min_c`, `mean_c` and `max_c`. Filter by
`measurement_name` in Excel to see a particular target. Coordinates are normalized
thermal sensor coordinates; frame indexes start at zero. Numeric precision is
preserved independently of the displayed rounding.

Names and geometry reflect each recorded frame: renaming or moving a measurement
during recording applies from that change onward. New measurements begin when
added, removed measurements stop, and duplicate names remain distinguishable by
ID. Naming before recording gives the clearest spreadsheet. With no named points
or regions, the CSV contains headers only; full temperature grids are still saved.
Each camera gets its own CSV, including when recording through the Power Lab
camera integration. Host arrival times do not establish synchronized exposures.

During recording the file is called `measurements.partial.csv`. A successful Stop,
Disconnect or app close finalizes it as `measurements.csv`. Failed sessions retain
the partial file and an incomplete status. Preview frames before Start or after
Stop are excluded. The CSV opens in Excel; use Excel's Save As for an `.xlsx` copy.

For older recordings, or measurements added afterward, use **Recordings → Export
→ Export history CSV**. That existing history export uses a separate row for each
region statistic and can export either Recorded or Analysis measurements.

**Measure → Clear all points** removes every manually placed point in one click
and saves the cleared layout. It preserves rectangles and optical alignment and
returns to Select mode, so the next image click will not add another point.
Saved recordings remain unchanged. Save a named layout first if you want to
reuse those points later.

The same sensor coordinates are used in every view. A point placed over a
visible-light object measures the corresponding thermal pixel under the current
registration, not an optical-image temperature. Alignment changes never move
measurement geometry. A stale/disconnected image is clearly labeled and its
live measurements become unavailable.

Layouts preserve named measurement IDs, geometry, camera identity and optical
alignment. They autosave to `~/.thermal-lab/workspace-<camera-hash>.json`; Save layout and
Load layout manage named JSON presets. `--workspace PATH` selects an alternate
autosave basename; a camera-specific suffix is added. Existing single-camera
layouts migrate only when their camera identity matches. Palettes, opacity and
view orientation currently reset on launch.

## Recordings

The timer in the header beside **Record session / Stop recording** displays
**hours:minutes:seconds** from the acquisition worker's recording start. It resets
for every new recording. After Stop it shows **Recorded** with the final recorded
frame's elapsed time; an interrupted capture is labeled **Interrupted**. Camera
uptime is separately labeled in the bottom status line. The timer follows host
time and does not claim hardware exposure synchronization.

**Record session** starts a uniquely named session under
`~/Thermal-Lab-Recordings`. Stop recording finalizes it. Override the destination
with `--recordings PATH`.

Each accepted numerical frame is recorded with the measurement layout,
alignment, revision, calculated values, source identity and host arrival time.
Display frames may be skipped when rendering falls behind; accepted recording
frames are queued separately and queue/storage failures are surfaced.

**Camera → Record lossless optical video** is enabled by default; turn it off before recording to retain
only numerical thermal frames. The option is fixed for the session. When enabled,
every accepted thermal frame has a lossless 1024×768 YUYV optical plane in
`optical.bin`, with timestamp, sequence, offset and SHA-256 in `optical.idx`.
DEV8 uses lossless LZ4 compression of the original YUYV bytes, with no resizing,
frame-rate reduction or pixel changes. Savings depend on the scene; budget at
least the uncompressed 2.4 GB/minute per camera at 25 fps, plus thermal data.
The reader verifies the original optical SHA-256 after bounded decompression.
Existing raw archives remain readable. Storage or queue failures fail the session.
The first/last full native buffers are also retained for independent comparison.
This is an app-native video archive; recording review can export a rendered MP4.
Use `python scripts/verify_recording.py SESSION_DIRECTORY` to check all numerical
frames and optical pair hashes. Only `COMPLETE` manifests represent finalized sessions;
`FAILED` and unfinished `RECORDING` sessions remain incomplete.

The Camera tab identifies cameras sharing a hub's upstream USB path,
including nested hubs. For two TC001 Max cameras at full quality, use separate
USB controllers. Different root ports on one controller remain unverified.
Click **Refresh** after moving cables; this is a topology check, not a bandwidth
reservation or proof that a camera will stream.

Camera errors immediately clear the image and temperature readings. A stream
that stops delivering previews for eight seconds is terminated so the UI remains
usable; any unfinished recording stays incomplete. Reconnect the selected camera
to recover, then start a new recording. Failed recordings are never silently
resumed or spliced into a new stream. If Windows assigns a new location-based
camera identity after moving ports, select it and verify its measurement layout.

## Review and temperature histories

**Recordings**, or **Workspace → Review recordings…**, opens an independent offline player. If the current window
has a stopped recording, it opens that session; otherwise choose **Open recording**
and select its folder. You can also run `thermal-lab-review` after installation,
or `python -m thermal_lab.review --session PATH` directly from the repository.
Review does not acquire a camera and can run alongside live windows.

Play/Pause uses the recorded host-arrival timeline, with 0.25× through 4× speeds.
Previous/Next steps one frame; the slider seeks by frame and clicking the history
graph seeks by elapsed time. Rendering can skip frames to keep up with playback
time; individual stepping still accesses every saved frame. The image uses the
recorded temperature grid and recorded point/region geometry. For optical-enabled
archives, choose Thermal, Optical or Blend at the right of the playback toolbar. Optical uses the
alignment saved at that frame; Blend uses 55% thermal opacity. Original optical
pixels stay unchanged in the archive. Older thermal-only archives remain playable.
Palettes and view
rotation change only rendering. Hover over a pixel to inspect its saved value.

Histories load in the background and validate recorded measurements against the
numerical grids. The history list provides point values and region minimum,
mean and maximum. A line breaks when a measurement is missing or its geometry
changes. The list uses its most recent recorded name; the image/table retain
the name recorded at the selected frame. No interpolation fills missing samples.

In the **Export** tab, **Export history CSV** writes all histories into a new UTF-8 CSV, with camera/source,
stable measurement ID, most recent name, statistic, zero-based frame index,
elapsed seconds, Celsius value and geometry. Existing files are not overwritten.
The numerical values preserve stored precision, independent of display rounding.

This first player accepts COMPLETE single-camera 256×192 archives with consistent
indexes/counts and validated frame identities. Incomplete sessions and corrupt
indexes are rejected; later frame/history errors are surfaced. Indexes are limited
to one million entries and histories to two million scalar samples. This is
recorded-frame review; multi-session comparison and physical-exposure
synchronization remain future work.

## Add measurements during playback

In the review **Measurements** tab, choose **Analysis** from Layout. **Point** places a point on the saved
thermal grid; **Rectangle** draws a region. Use **Select** and drag to move either
measurement. Select a measurement or table row, edit its name, and click Rename;
Remove removes it from this analysis. Drawing another rectangle creates another
region. Placement works in rotated thermal, aligned optical and blended views.

Analysis geometry is fixed across the entire recording. Moving a point or region
recalculates its history across all frames; this does not track a moving object.
The current frame table updates immediately. Graphs recalculate in the background;
export becomes available when the current calculation finishes. Point histories
contain pixel values; region histories contain minimum, mean and maximum.

**Recorded** restores the original measurements and their per-frame geometry.
The original numerical grids, optical data and recorded measurement definitions
are never modified. Optical alignment still follows the recorded frame.

Edits autosave under `~/Thermal-Lab-Analysis/<recording-sha256>.json`. Reopen the
recording and choose Analysis to restore them. **Save analysis** creates a new
named copy; **Load analysis** replaces the current analysis with a saved layout
for this same recording. Binding uses SHA-256 of the manifest, numerical archive
and numerical index, so a different recording is rejected even from the same
camera. Save copies and analysis CSVs outside the source recording folder.

**Export history** exports the current Recorded or Analysis histories. CSV fields
`measurement_basis` and `recording_sha256` distinguish later fixed-geometry
analysis from original recorded measurements. Save a named copy to retain an
alternative layout before editing further. See [DEV6 verification](Analysis-Verification.md).

Temperatures are apparent Celsius values without host emissivity/environment
correction. Absolute accuracy and physical thermal/optical exposure pairing
remain unqualified. This app does not control power instruments.

## PNG snapshots and MP4 export

In the review **Export** tab, **Save PNG** exports the currently selected frame. **Export MP4** exports the full
recording at 1× speed, using Thermal, Optical or Blend, the current palette and
rotation, and the selected Recorded or Analysis measurements. Toggle **Export
temperature labels** to include or omit the header, geometry and numerical labels.
Settings are captured when export begins; further review edits do not change an
export already running. The playback speed selector does not affect export speed.

Files are 1024×768, or 768×1024 for 90°/270° rotation. Thermal display resolution
is upscaled from the original 256×192 grid; it adds no measurement resolution.
PNG stores rendered pixels losslessly. MP4 uses H.264/yuv420p at 25 fps and is a
lossy presentation file. Keep the source archive for numerical analysis.

MP4 follows host-arrival time by holding the latest source frame at each 40 ms
output step. It can repeat or skip source frames, and includes the final source
frame; output duration can extend by less than 80 ms beyond the source time span.
It provides no physical-exposure synchronization. Exports are limited to 250,000
output frames (about 2 h 46 min at 25 fps); clip-range export is not yet available.

PNG embeds a `ThermalLab` JSON metadata field with frame identity and measurements.
MP4 writes an adjacent `.mp4.json` file containing the source recording fingerprint,
frozen export settings, measurement basis, and frame-by-frame source-index/time
mapping. Keep that file with the video for traceability.

Choose a new filename outside the source recording folder. Existing files are
never overwritten. Exports run in the background; **Cancel export** stops MP4
generation and removes incomplete temporary outputs. Closing review waits for
export cleanup. Successful completion is shown separately from history progress.

MP4 uses the FFmpeg executable supplied by `imageio-ffmpeg` in the desktop
dependencies. Update an older installation with `python -m pip install ".[desktop]"`.
No Windows SDK is required. See [DEV7 verification](Media-Export-Verification.md).
