# DEV7 PNG and MP4 export — 7 September 2026

Recording review exports its current frame to PNG and the full recording to
H.264 MP4. Exports use the selected thermal/optical/blended view, palette,
rotation, original recorded or offline analysis measurements, and optional
temperature labels. Export settings are copied before background work starts.
The source numerical and optical archives remain read-only.

PNG contains rendered RGB pixels and embedded JSON provenance. MP4 is a lossy
25 fps presentation video with an adjacent JSON provenance file, including each
output frame's source index and elapsed time. Sampling holds the most recent
host-arrival frame, and includes the final source frame. It does not claim
device exposure synchronization. Normal and rotated exports use 1024×768 and
768×1024 dimensions respectively; thermal resolution remains 256×192.

## Real recording verification

Source: `runtime/selected-workers-135427/camera0`, 499 TC001 Max hardware frames.
Exported a blended video with the saved “Surface probe” and rectangular region
analysis, plus labeled blend and unlabeled optical PNGs. Full MP4 decoding
returned 500 frames at 1024×768 and 25 fps, lasting exactly 20.0 seconds. The source
mapping starts at frame 0 and ends at frame 498. The final MP4 is 4,736,620 bytes.

All seven source files retained identical SHA-256 hashes. Inspected the PNG and
decoded MP4 midpoint directly, including temperature labels and region geometry.
The first pass exposed a missing font glyph in the range header; the final pass
uses the system Segoe UI font on Windows, with portable fallbacks and a plain
“to” separator. The corrected PNG and decoded video labels were inspected again.

Evidence: [machine-readable export result](camera-evidence/media-dev7-verification.json).
Local outputs: `runtime/media-dev7-final/analysis-blend.png`, `optical.png`,
`analysis-blend.mp4`, its JSON sidecar, and decoded frames 1, 250 and 500.

The native **Save PNG** flow was exercised on the original Recorded view. Its
snapshot showed “Camera 0 probe” at 22.100 °C and the correct source frame/time.
The native **Export MP4** flow also completed, with progress and completion shown
in the window. Its Recorded/Thermal video decoded to 500 frames at 25 fps and
20.0 seconds; the sidecar correctly identifies original recorded measurements.
Desktop export error logs were empty.

## Failure handling and tests

48 automated tests pass. New checks cover exact PNG rendered-pixel round trips,
rotated dimensions, embedded measurement provenance, full MP4 decode and frame
mapping, missing optical data, encoder launch failure, cancellation, and a
destination file created while export is running. Existing data is preserved
and failed/cancelled exports leave no completed media or sidecar.

Files are rendered to private temporary files in the destination directory and
published without overwriting existing names. MP4 cancellation kills the encoder
if a pipe write blocks. A 45-second stalled-encoder watchdog bounds encoder hangs.
Closing review requests cancellation and waits for cleanup. The DEV7 wheel builds.

MP4 requires `imageio-ffmpeg` (included in the desktop extra); the tested wheel
provides FFmpeg 7.1 on this Windows PC. Implementation references:
[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg/blob/main/README.md) and
[FFmpeg formats](https://ffmpeg.org/ffmpeg-formats.html).

## Remaining limits

Export covers the whole recording at 1×; clip ranges, speed changes, audio,
combined two-camera videos and PDF reports are not implemented. The limit is
250,000 output frames. Large numbers of overlapping labels can obscure imagery;
disable labels for a clean export. PNG/MP4 are presentation files, not substitutes
for the numerical archive. No camera acquisition or power instrument commands
were needed for these offline export checks.
