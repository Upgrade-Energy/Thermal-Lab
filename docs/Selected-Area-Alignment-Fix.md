# Selected-area alignment fix — DEV13

## Problem and change

The previous tool did not import the main workspace's selected measurement
rectangle. Its brightness-information matcher also often found implausible
geometry or rejected real targets: thermal hotspots and visible printed labels
do not describe the same image structure.

DEV13 imports the selected rectangle, or requires an explicit thermal target box.
It searches for the target's outline using polarity-independent edge orientation,
thermal silhouette extraction where available, and a denser offset/scale search.
Rotation stays close to the current sensor setting. Texture matching is a
fallback; when both methods return candidates, conflicting geometry is rejected.

**Align selected area → Preview auto-alignment → Apply to live** is separate
from the experimental regional/calibration tool. No checkerboard is required.
Matching changes the optical display transform only, not numerical thermal
pixels, measurement coordinates, capture resolution or archival recording data.

An uncertain match leaves live alignment unchanged and opens raw optical target
guidance. Box the same object on the right to estimate scale and offset visually;
the automatic matcher can then refine locally. An uncertain refinement retains
the paired-box estimate for visual review. A box estimate is not a calibrated
measurement of alignment accuracy or distance.

## Verification on Windows, September 7, 2026

- 88 automated tests passed. Added coverage for outline recovery despite unrelated
  internal heating/printed labels, importing measurement rectangles, small-region
  handling, and requiring a thermal selection before optical guidance. Existing
  tests cover unrelated-image rejection, cancellation, guided search bounds,
  camera/lock/stale-alignment guards and measurement preservation.
- Six original recorded hardware pairs were processed and their before/after
  crops inspected. A heated enclosure and a near bottle each produced an accepted
  improved fit. Four other frames were marked ambiguous, including one visibly
  wrong bottle scale. This is **not** a six-out-of-six automatic success claim.
  Input numerical arrays and optical image bytes were unchanged in all six cases.
- Native DEV13 reconnected to the TC001 Max and displayed 256×192 thermal and
  1024×768 optical frames at approximately 25 fps.
- On fresh live frozen frame 342, drawing a bottle target and clicking Preview
  automatically recovered dx −17.75, dy −13.0, scale 1.188, rotation 0°. The cap
  and sides visibly improved; Apply updated the live sliders and saved workspace.
- A second test created a measurement rectangle in the main view and reopened
  the tool. The same rectangle appeared as its target without redrawing. On
  frozen frame 1548, Preview returned dx −20.25, dy −10.0, scale 1.274, angle 0.2°.
  This preview was also visually inspected and applied. Differences between fits
  are evidence that these are estimates, not a metrology calibration.
- The active recording was finalized before restarting the old app. Its manifest
  reported COMPLETE with 12,309 frames. Camera images and recordings remain local
  and are excluded from this repository.

## Limits

Select one stationary object with a visible thermal boundary and a little
background. A small patch of uniform temperature, several depths in one box,
reflections, occlusion, moving targets or repeated outlines may be ambiguous.
The confidence checks are heuristics, not an accuracy percentage. Inspect the
selected object's boundary before applying. Other depths can remain misaligned.
The tool fits a similarity transform; it does not infer a depth map or certify
pixel-accurate thermal/optical registration. Thermal absolute accuracy and sensor
exposure synchronization remain unqualified.

Local diagnostic artifacts for this verification are under
`runtime/edge-check/selected-fix-results.json` and
`runtime/edge-check/selected-fix-montage.png`; they are intentionally not shipped.
