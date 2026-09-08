# DEV11 alignment verification — 2026-09-07

The native tool estimates a similarity transform for a selected target plane.
It does not measure depth. Named camera-bound profiles optionally carry operator
distances, with inverse-distance interpolation between saved settings. Thermal
coordinates and original recording data remain unchanged.

## Checks

- 75 unit tests pass, including recovery of known offset, scale and rotation with
  inverted/nonlinear thermal brightness, no-detail/unrelated-detail rejection,
  cancellation, paired near/far target geometry, distance interpolation, camera
  identity validation, and locked/stale/uncertain Apply guards.
- Native Windows dialog exercised using a clearly labeled recorded-image fixture:
  target drawing, automatic search, paired optical target guidance, local refinement,
  profile save and explicit Apply. No USB access or live workspace mutation by the fixture.
- Two real TC001 Max recordings from integration run
  `1188a045356e49bc810a94150dc7c838` inspected at frames 562 and 563.
  Unconstrained candidates were visually wrong or ambiguous. In the final checks,
  both were rejected. Camera 0's misleading 19° candidate scored 0.246 but failed
  the geometry guard; camera 1's candidate failed geometry and ambiguity checks.
- Paired boxes on camera 0's enclosure produced a visibly closer target overlay.
  Final local refinement remained ambiguous, so the box estimate was retained.
  This is evidence for a usable guided workflow, not qualification of automatic
  alignment accuracy on arbitrary scenes or a physical near/far calibration.
- SHA-256 hashes of all 14 source archive files matched before/after validation.
  Captured images and test profiles remain local under ignored `runtime/`.
- DEV11 relaunched and reconnected the same Windows camera identity. Fresh live
  frames reported 256×192 numerical thermal and 1024×768 optical dimensions. The
  assistant opened on frozen live frame 119 with the existing alignment preserved;
  native dark-theme controls and images were visually inspected. No live alignment
  was applied during this check.

## Algorithm and limits

NumPy/Pillow implementation: downsampled grayscale optical samples, selected
numerical thermal region, normalized mutual information, deterministic search and
held-out samples. Mutual information allows differing brightness across modalities;
see the [ITK registration guide](https://itk.org/ITKSoftwareGuide/html/Book2/ITKSoftwareGuide-Book2ch3.html).
No ITK dependency is required.

Acceptance gates check information, ambiguity, overlap and plausible change from
the starting alignment (rotation at most 8°, scale ratio 0.65–1.5 and translation
at most 64 thermal pixels). Guided refinement is limited to ±8 pixels, ±12% scale
and ±3° around the box estimate. These are heuristics, not calibrated confidence
or a guarantee of correct matching. All candidates require human preview/Apply.
Search runs outside Tk with cancellation and a 25-second limit.

The tool supports one depth plane at a time, assumes a fixed camera arrangement,
and does not correct perspective, lens distortion, occlusion or moving-target
exposure differences. No simultaneous multi-depth warp, range sensor, or physical
distance calibration was added. Browser UI continues to use the resulting ordinary
workspace alignment through the existing integration; the assistant itself is native.
