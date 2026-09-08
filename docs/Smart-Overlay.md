# Smart overlay and measured camera calibration — DEV12

Open **Smart / calibrate…** in the Optical alignment controls. This experimental
window analyzes small regions independently so nearby and distant surfaces can
receive different optical corrections. It displays each result with the exact
thermal/optical pair used to estimate it. It never applies an older warp to a newer
frame. The main measurement workspace and original recordings are unchanged.

**Analyze one pair** freezes one result. **Start continuous** processes fresh pairs
in the background; **Stop** leaves a frozen preview. Supported regions blend
optical detail over thermal. Unsupported regions remain thermal-only, with amber
hatching when Show uncertainty is enabled. The percentage is supported image area,
not a confidence or accuracy percentage. Preview updates may be slower than capture.
Thermal data stays 256×192 and original optical storage stays 1024×768 YUYV.

Without measured calibration, the window explicitly says **UNCALIBRATED TRIAL**
and uses the main window's manual alignment as a starting point. It may reject
every region. Neither this mode nor the calibrated mode guarantees an all-scene
match. Temperature appearance often differs too much from visible texture.

## Calibrate the physical camera

A rigid, flat checkerboard must be visible in both thermal and optical images.
Use **8 × 6 squares**, giving **7 × 5 inner corners**, with accurately measured
square spacing. The [25 mm geometry template](calibration-target.svg) can help lay
out a target. Print at 100% and measure it; it is not a thermally visible target
by itself. A printed paper pattern or screen alone may show no thermal contrast.
The material/pattern must supply clear thermal as well as visible square edges.

1. Enable **Calibration mode** and enter the measured square spacing in mm.
2. Hold the entire pattern still in both cameras and click **Detect frozen pattern**.
3. Inspect the numbered corners: 1 and 35 must mark the same physical corners in
   both views. Use **Reverse optical order** if their sequences run opposite ways.
4. Click **Add verified pair**. Move the target across the view and change its
   distance and tilt. Capture 12–40 varied poses, including tilt in both directions.
5. Click **Solve & save calibration**. Repeated poses, poor coverage, insufficient
   tilt, inconsistent pairing or excessive validation error prevent saving.
6. Disable Calibration mode. Enter a representative **Reference depth** in metres,
   then try continuous analysis. This is an entered starting depth, not a measurement
   from the camera. Other depths can be matched locally within the search range.

Corner captures autosave beside the workspace in `stereo-calibration/<camera-hash>.draft.json`.
Reopening resumes them. Undo last pair corrects a mistake; New session starts new
captures. A solved calibration is stored separately as `<camera-hash>.json` and
remains available until another solution passes. A different camera identity or
sensor resolution cannot load it. Recalibrate if the sensor arrangement changes.
No calibration images or user camera views are uploaded.

## What is implemented, and what remains unqualified

Calibration solves each lens's intrinsics/distortion and the sensors' relative
rotation/translation. Every fourth pose is withheld from fitting. Validation
estimates its pose using thermal corners, then checks predicted optical corners.
Limits are 1.2 thermal pixels fit RMS and 2 pixels maximum held-out RMS. These
checks measure consistency, not certified metrology. See the
[OpenCV calibration documentation](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html).

Projection begins at the entered reference depth on the original thermal grid.
The matcher searches local translations up to 12 thermal pixels around that
projection. It checks contrast, correlation, alternate peaks, two-direction texture,
gradient agreement, and a reverse match. This follows the principle of checking
[forward/backward agreement](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html),
with a separate conservative patch matcher for thermal/visible images. Either
contrast polarity is allowed. Distinct 16-pixel regions are not smoothed together
across depth boundaries. Missing detail and occlusions are not filled with guesses.

This is a bounded local registration prototype, not dense metric depth estimation,
a trained cross-modal vision model, or guaranteed alignment of every image pixel.
Regions can still be falsely accepted or rejected. Regions outside usable coverage
or beyond the search range stay uncertain. The preview does not add or alter
measurement points, record its transient warp, change exports, or change Power
Lab's existing camera contract. Promoting it into measurement/export workflows
requires measured real-camera alignment validation and per-frame warp provenance.

## Verification on 2026-09-07

- 85 automated tests passed, including opposing shifts on synthetic near/far
  regions, inverted contrast, occlusion/unrelated/flat/one-edge rejection, source
  data immutability, cancellation, session persistence and late-result suppression.
- Synthetic 16-pose camera calibration recovered known geometry; incorrect corner
  ordering and duplicate poses were rejected. The synthetic pattern detector and
  fallback detector passed. These synthetic results do not calibrate the actual camera.
- Six frames across both existing TC001 Max recordings were processed and local
  rendered images inspected. All regions were rejected with the uncalibrated
  baseline. No positive real-scene registration accuracy claim is made.
- Windows native continuous preview advanced from analyzed frame 197 to 1061
  while main capture advanced to 1076 (43.2 seconds). Matching reported roughly
  0.01–0.02 seconds per pair in this scene; supported area remained 0%. Numerical
  256×192 and optical 1024×768 live capture continued. No throughput qualification
  of recording while this window runs was performed.
- Live calibration mode displayed both raw images, correctly rejected the scene
  without a checkerboard, and disabled Add/Solve. Camera calibration remains
  blocked on a suitable physical target and varied paired captures. This is the
  next required step before assessing useful real-camera automatic alignment.
