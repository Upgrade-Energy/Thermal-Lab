# TopView feature review and Thermal Lab priorities

DEV6 adds editable playback points/regions, separate analysis layouts and
recalculated histories; see [analysis verification](Analysis-Verification.md).

DEV5 adds continuous lossless optical recording and optical/blended review.
See [optical recording verification](Optical-Recording-Verification.md).
Image/standard-video export remains pending.

DEV4 adds thermal recording playback, recorded measurement histories and CSV
export; see [playback verification](Playback-Verification.md). The historical
feature comparison below remains a record of the initial review.

Update: the first native live workspace is now implemented in DEV2. See the
[desktop guide](Desktop-Guide.md) and [verification results](Desktop-Verification.md).
The comparison below retains the pre-implementation baseline and proposed scope.

Reviewed 7 September 2026 against installed TopView 1.30.003 on Windows with
the connected TC001 Max. Thermal Lab baseline: initial standalone extraction,
commit `d56bf8a`. This is a feature review and proposed implementation scope,
not a claim that the missing features have been implemented.

## What was inspected

TopView live analysis, image-mode menu, fusion calibration, measurement toolbar,
palette menu, measurement-parameter settings, library, saved-image analysis,
3D heat map and report landing page. A new live point and rectangle were placed
successfully. P1 read about 28.4 °C; R1 showed approximately 31.8 maximum,
27.6 mean and 22.5 minimum, with hot/cold markers on the image. These are scene
observations, not accuracy references. No thermal correction values were changed.
No power-instrument commands were issued.

“Observed control” means the feature was visible, not that every behavior was
tested. Point placement, rectangle placement and the 3D heat map were exercised.
Earlier still/video/CSV qualification is documented separately.

## Feature comparison

| Feature | TopView observation | Thermal Lab today | Priority |
| --- | --- | --- | --- |
| Live image workspace | Live TC001 Max image, zoom controls, full-screen and collapsible side panes | CLI capture only; no live GUI | First |
| Thermal/optical modes | Menu: Dual-spectrum 1, Dual-spectrum 2, Thermal Imaging, Visible Light. Dual-spectrum 1 displayed thermal colors with visible scene outlines | Temperature plane decoded; optical image not decoded or displayed | First |
| Overlay alignment | Calibration opens a Fusion Distance slider; displayed value 0.23 m. Slider not changed | No registration or alignment controls | First |
| Arbitrary alignment | No X/Y translation, rotation, scale, opacity or landmark alignment controls found in the inspected menus | None | First; proposed extension |
| Temperature points | Click-to-place P1, live value on image and measurement table; selection control | Named point calculation exists in code; capture CLI fixes one center point | First |
| Rectangular regions | Drag-to-draw R1, min/mean/max table and hot/cold image markers | Rectangle statistics exist in code; CLI fixes a full-frame region | First |
| Other measurement shapes | Line, circle and polygon toolbar controls observed | No corresponding region masks or editor | Next |
| Cursor temperature | Temperature-tracking tool observed in toolbar | No interactive pixel inspector | First |
| Measurement editing | Selection and delete controls observed; free naming/persistence not established during this review | No GUI, saved measurement presets or editing history | First; explicitly design these |
| Palettes | White Hot, Rainbow, Jungle, Black Hot, Red Hot, Arctic, Golden Red, Iron Red, Shimmer, Medical | No application palette selector | First, with a small initial selection |
| Temperature color scale | Vertical scale, lock button, disabled min/max fields while automatic | No display scale controls | First |
| Temperature correction | Emissivity with custom entry/material presets, ambient temperature and distance | Apparent temperatures only; no host correction | Required qualification work |
| Camera controls | Shutter button and range selector; active range displayed -20 to 150 °C | Native startup uses tested defaults; no user shutter/range controls | Next, after protocol validation |
| Capture and recording | Still and video controls; previously tested exports | Full numerical recording, index, first/last raw buffers; no capture GUI or rendered-video export | First |
| Library and playback | Photo/video library and offline analysis; playback/seek/speed controls observed | Indexed archive and verification tools; no visual browser/player | First |
| Offline analysis | Measurement toolbar, rotate/flip-style controls, CSV, Export and VS controls | Numerical frames can be read programmatically; no interactive re-analysis | Next |
| 3D heat map | Successfully opened numerical surface with 3D/Top/Left/Right/Front views | None | Later |
| Reports | Report and Template tabs with New/Edit controls | None | Later |

The optical mode menu was inspected; the distinct rendering behavior of both
dual-spectrum variants was not individually qualified. Rotation/flip, comparison,
range switching, shutter operation and report generation were not exercised.
Do not infer their complete behavior from button labels alone.

## Overlay behavior we should implement

Provide thermal-only, optical-only, side-by-side and blended views. Add an
opacity slider, drag-to-align with numeric X/Y offsets, scale, rotation,
reset-to-default, lock alignment, and named alignment presets. Add an optional
edge-overlay view after basic optical decoding and blending work.

For repeatable bench setups, offer paired landmarks: select the same features
in the thermal and optical images, solve an alignment and display residual
error. Save the transform with camera identity, image dimensions, orientation,
working distance and recording metadata. A simple affine transform is a useful
starting model; perspective correction should be an explicit advanced mode.

Alignment should not promise a perfect match at every depth. The two camera
viewpoints produce depth-dependent mismatch; a preset should describe the
working plane/distance for which it was adjusted. TopView's fusion-distance
control and its separate measurement Distance setting must not be conflated.

Keep the thermal grid as the measurement reference. Optical layers and display
transforms must never change numerical temperatures. Map clicks back to thermal
sensor coordinates, reject clicks outside thermal coverage, and preserve the
same selected pixel through zoom, rotation, resizing and view-mode changes.
Display interpolation must not be presented as extra thermal resolution.

## Measurement behavior we should implement

Click to add a point; drag to move it; assign a name such as “Connector” or
“Cell 1”; choose color, label visibility and whether it is recorded. Support
pixel coordinates and a magnified thermal view for precise placement. Label
whether a point is a single pixel or an explicitly chosen averaging region.

Rectangles should support drag/resize and named min/mean/max readings, including
the coordinates of the hottest and coldest pixels. Add circles, polygons and
line profiles afterward. Store stable IDs, geometry and edits, not only labels.
Provide a measurement table and time-series plots with CSV export, saved layouts,
and a reference-point/region temperature difference calculation.

Permit measurements to be added or changed during playback because the original
numerical grids are retained. Preserve the original recorded measurements and
mark later analysis separately. Threshold alerts, per-region emissivity and
measurement uncertainty are later additions requiring their own validation.

## Recording changes required for overlay playback

The current recorder saves every temperature grid but only the first and last
full native buffers. Consequently it does **not** preserve a continuous optical
stream. We must validate optical decoding and retain optical frames with timing
and pairing metadata before promising blended playback or export.

Store immutable thermal data, a separately encoded optical stream, alignment
settings and measurement definitions. Render palettes, labels and overlays on
playback/export rather than making a flattened video the only retained result.
Expose incomplete pairs, camera loss, stale frames and storage failure. Host
arrival time remains the available timing basis until device timestamps are
understood; physical thermal/optical exposure synchronization is unqualified.

## Suggested implementation sequence and acceptance checks

1. **Standalone live workspace:** decode and inspect optical frames; thermal,
   optical, side-by-side and blend views; zoom/fit/rotation; palettes and fixed
   or automatic color range. Verify orientation, colors, frame pairing and
   capture responsiveness on the actual camera.
2. **Precise measurement and alignment:** point/rectangle placement, names and
   table; opacity and alignment transform/presets. Verify that the same thermal
   pixel and value remain selected through all view transformations; alignment
   changes must not alter raw temperatures.
3. **Complete recording and review:** retain both streams, measurement layouts
   and transforms; seekable playback, plots, CSV and image/video export. Check
   saved-frame equality, restart/reopen, incomplete sessions, disk failure,
   disconnects and sustained performance under host load.
4. **Advanced inspection:** circles/polygons/lines, comparison, validated
   environmental correction and camera range/shutter controls. Keep calibration
   status explicit until comparisons and physical-reference checks pass.
5. **Optional presentation features:** reports and 3D heat maps. Keep these
   secondary to accurate placement, alignment and reliable recording.

This scope belongs entirely in Thermal Lab. Power Lab integration remains an
optional consumer of recordings and selected fresh measurements.
