# DEV2 desktop verification — 7 September 2026

Tested on the local Windows PC with its connected TC001 Max, using TopView's
tested native DLL with TopView closed. No power instruments were accessed.

## Implemented and inspected

- Native Tk desktop window; native acquisition isolated in a spawned process.
- 1024×768 optical image decoded from the full native frame; actual scene
  inspected alongside 256×192 thermal data, including a moving hand.
- Thermal, optical, blend and side-by-side modes; uniform optical scale,
  rotation and X/Y offsets; opacity, lock and reset; common view rotation,
  zoom/pan/fit; four palettes and automatic/manual temperature color limits.
- Point placement, naming, rectangular region drawing and live statistics.
  A point named “Ceiling light” and a surrounding region were exercised.
- Dragging optical alignment moved the optical image while thermal measurement
  geometry stayed fixed. Reset restored the optical transform. Side-by-side
  display showed the same measurement geometry on both aligned views.
- Autosaved point name/geometry and alignment loaded after restarting the app.
- Stopped acquisition showed a stale-image banner and unavailable measurements.
- Clipped controls and low-contrast dropdowns found during inspection were
  corrected. The final window displayed its save/load controls and temperature
  qualification footer together.

## Hardware recording checks

The first desktop-started recording stored **950 frames over 37.969 seconds**,
an observed **24.994 fps**, while alignment and view mode were changed. Independent
indexed playback verified every value in all **46,694,400 temperature values**,
the recorded point/region calculations, increasing arrival times, and exact
first/last raw-buffer round trips. Recording captured two optical-alignment
states across three workspace revisions while measurement geometry stayed in
one unchanged state.

After restarting the final desktop build, a second recording was terminated by
the **Disconnect** button while recording remained active. It finalized as
`COMPLETE` with **372 frames**, rather than leaving an unfinished archive.
Independent playback verified its **18,284,544 temperature values**, measurements
and first/last raw round trips. Desktop stderr logs were empty on these runs.

- [950-frame verification](camera-evidence/20260907-125117-d97685-verification.json)
- [Alignment/geometry consistency](camera-evidence/desktop-alignment-recording-check.json)
- [Disconnect finalization verification](camera-evidence/20260907-125459-216333-verification.json)
- [26 passing automated tests](camera-evidence/desktop-tests.txt)

Automated coverage includes optical YUYV layout, grayscale conversion,
alignment translation/inversion, pixel-coordinate round trips through all four
view rotations, clipping/hit-testing across zoomed side-by-side panels,
temperature independence from rendering, invalid layouts,
duplicate measurement names with distinct IDs, recording finalization and an
injected camera-disconnect error. The synthetic tests do not constitute
additional hardware evidence. A DEV2 wheel also built successfully.

Full recordings and raw frames remain local under ignored
`recordings/desktop-tests/`; local UI logs are under `runtime/`.

## Limits

These checks cover the first live workspace, not every possible UI interaction
or a long-duration soak. Explicit optical scale/angle controls are backed by
transform tests; arbitrary perspective registration, landmark fitting, region
resize handles, per-region corrections and all advanced shape tools remain
future work. Physical USB unplug recovery was not exercised in this increment.

Optical playback/video recording and graphical recording review are not yet
implemented. Numerical recording preserves full thermal grids, measurement
definitions and alignment changes, but only first/last full native buffers.
Apparent-temperature accuracy, environmental correction and physical
thermal/optical exposure synchronization remain unqualified. Camera-range and
shutter controls are unchanged from the existing adapter.
