# Thermal Lab desktop — DEV4

Launch `thermal-lab` after `python -m pip install ".[desktop]"`, or run
`python scripts/run_thermal_lab.py` from the repository. Requires Windows x64
Python 3.12+ with Tcl/Tk, NumPy, Pillow, the tested TopView installation and its
camera driver. The native acquisition ABI remains experimental and hash-locked.

Select the TopView installation folder, close TopView, choose a camera from the
list, and click **Connect camera**. Refresh rescans connected devices while
disconnected. Native acquisition runs in a separate process. Disconnect releases
the camera. Closing the window requests shutdown and finalizes any numerical
recording; an unresponsive worker is terminated after a bounded wait and its
unfinished recording must be treated as incomplete.

## Two cameras

Click **Open another camera window** to open an independent workspace with the
other detected camera selected. Connect it there. Each window has independent
view controls, alignment, points/regions and Record/Stop controls. A camera
already owned by another window cannot be acquired a second time. Closing either
window finalizes its recording and leaves the other running.

Use separate USB controller paths for two TC001 Max units. Our shared-hub tests
failed; moving one camera to another controller enabled concurrent recordings.
The Windows instance suffix in each title identifies that window's device.
Location-based IDs may change when ports change, in which case a fresh layout
is used. Device indexes are never saved as camera identities. Physical exposure
synchronization is not provided by concurrent capture.

## Live views and alignment

Choose Thermal, Optical, Blend or Side by side. Optical is mapped into the
thermal sensor's coverage for overlay comparison. The rotation dropdown turns
both displayed layers together; it never rotates stored temperature arrays.
Use the mouse wheel to zoom, Pan to drag the view, and Fit to reset the viewport.

Thermal opacity controls the blend. **Align optical** lets you drag the optical
layer while thermal pixels and measurements stay fixed. X/Y offsets are in
native thermal pixels, before display rotation; scale and angle adjust only the
optical layer. Numeric edits apply with Enter or when leaving the field. Lock
alignment prevents changes; Reset restores the default optical transform.
This initial transform is not a factory registration calibration. Adjust it
for the target plane and distance; objects at different depths may not align.

Choose Iron, Rainbow, White hot or Black hot. Automatic range follows the
current thermal minimum/maximum; disable it and enter low/high Celsius values
for a fixed color scale. These display choices do not change measured values.

## Measurements

Choose **Point** and click a pixel, or **Rectangle** and drag a region. Points
display a temperature; regions report minimum, mean and maximum. Select a row,
edit its name and click Rename. Select mode allows dragging a point or region;
draw a replacement rectangle to change its size. Remove deletes the selected
measurement. The mouse readout identifies the native thermal pixel and apparent
temperature. Zoom in for precise placement.

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

**Record temperatures** starts a uniquely named session under
`~/Thermal-Lab-Recordings`. Stop recording finalizes it. Override the destination
with `--recordings PATH`.

Each accepted numerical frame is recorded with the measurement layout,
alignment, revision, calculated values, source identity and host arrival time.
Display frames may be skipped when rendering falls behind; accepted recording
frames are queued separately and queue/storage failures are surfaced.

The recording is radiometric numerical data, **not continuous optical video**.
Only the first/last full native buffers are retained. Optical video,
synchronized video export and device exposure timestamps remain future
work. Use `python scripts/verify_recording.py SESSION_DIRECTORY` for independent
numerical verification. Only `COMPLETE` manifests represent finalized sessions;
`FAILED` and unfinished `RECORDING` sessions remain incomplete.

## Review and temperature histories

**Review recordings** opens an independent offline player. If the current window
has a stopped recording, it opens that session; otherwise choose **Open recording**
and select its folder. You can also run `thermal-lab-review` after installation,
or `python -m thermal_lab.review --session PATH` directly from the repository.
Review does not acquire a camera and can run alongside live windows.

Play/Pause uses the recorded host-arrival timeline, with 0.25× through 4× speeds.
Previous/Next steps one frame; the slider seeks by frame and clicking the history
graph seeks by elapsed time. Rendering can skip frames to keep up with playback
time; individual stepping still accesses every saved frame. The image uses the
recorded temperature grid and recorded point/region geometry. Palettes and view
rotation change only rendering. Hover over a pixel to inspect its saved value.

Histories load in the background and validate recorded measurements against the
numerical grids. The history list provides point values and region minimum,
mean and maximum. A line breaks when a measurement is missing or its geometry
changes. The list uses its most recent recorded name; the image/table retain
the name recorded at the selected frame. No interpolation fills missing samples.

**Export history** writes all histories into a new UTF-8 CSV, with camera/source,
stable measurement ID, most recent name, statistic, zero-based frame index,
elapsed seconds, Celsius value and geometry. Existing files are not overwritten.
The numerical values preserve stored precision, independent of display rounding.

This first player accepts COMPLETE single-camera 256×192 archives with consistent
indexes/counts and validated frame identities. Incomplete sessions and corrupt
indexes are rejected; later frame/history errors are surfaced. Indexes are limited
to one million entries and histories to two million scalar samples. This is
recorded thermal review, not optical video, re-analysis with newly drawn regions,
multi-session comparison, or physical-exposure synchronization.

Temperatures are apparent Celsius values without host emissivity/environment
correction. Absolute accuracy and physical thermal/optical exposure pairing
remain unqualified. This app does not control power instruments.
