# DEV5 continuous optical recording — 7 September 2026

Runs locally on Windows 11 (build 26200), with the installed hash-locked TopView
DLL and two TC001 Max devices. No Windows SDK or Power Lab process is required.
No power instruments were commanded.

## Implemented

The desktop records lossless 1024×768 YUYV optical planes alongside every
accepted 256×192 numerical thermal grid. A separate bounded writer queue keeps
storage out of the camera read loop. The optical index stores host arrival time,
native-buffer arrival sequence, byte offset, length and SHA-256; the thermal
frame carries the matching optical digest. Finalization requires equal counts
and successful writers. Queue, disk and camera faults leave a failed session.

Review supports Thermal, Optical and Blend, using the saved per-frame alignment
and measurement geometry. Seek/step/play uses the thermal host-arrival timeline.
Optical checksums and pair identity are checked when reading an optical frame;
the verification script checks every pair. Legacy thermal-only archives continue
to work. Original optical pixels are not resampled in storage.

## Failure found and corrected

An initial zlib level-1 implementation could not sustain concurrent optical
capture: its 16-frame queues filled after 45 and 58 thermal frames. Both sessions
reported FAILED. Increasing the queue would only delay the same failure, so the
shipped format uses direct lossless storage (`raw-yuyv422-v1`). This needs about
2.4 GB/minute per camera at 25 fps, plus numerical data; the desktop shows that
estimate before recording. The failed experimental format was not released.

## Two-camera hardware result

Production acquisition workers selected and verified each physical camera.
Both started without a read retry and exited normally. One device remained on
the hub and the other on a separate USB controller path.

| Camera instance suffix | Frames / optical pairs | Duration | Effective rate |
| --- | ---: | ---: | ---: |
| YFDVS000000000001 | 499 | 19.953 s | 24.959 fps |
| 6&2A549464&0&2 | 499 | 19.953 s | 24.959 fps |

Both manifests are COMPLETE. All 998 optical hashes, pair identities and
49,053,696 numerical temperature values were checked. Every optical frame had a
distinct hash. First and last numerical grids and optical planes exactly matched
the retained native buffers. Each optical data file is 784,859,136 bytes.

Machine-readable evidence:
[hub camera](camera-evidence/optical-dev5-camera0-verification.json),
[direct camera](camera-evidence/optical-dev5-camera1-verification.json).
Local archives: `runtime/selected-workers-135427/camera0` and `camera1`.
Captured midpoint images were inspected: the hub view showed the desk/keyboard
and people farther away; the direct camera showed ceiling lights and monitors.

## Review checks and limits

The updated desktop also connected, started and stopped an optical-enabled
session through its visible controls. It finalized 606 pairs; all 29,786,112
numerical values and 606 optical hashes passed independent verification, with
exact first/last raw-buffer matches. The optical checkbox stayed disabled during
recording and re-enabled after completion. The camera continued live preview.
Evidence: [desktop session](camera-evidence/20260907-135729-3f4eaf-verification.json).
The DEV5 wheel built successfully. Desktop and review error logs were empty.

The native review window was inspected in thermal, optical and blended modes.
Optical Play/Pause advanced through later frames with changing imagery, point
values and history cursor; switching modes preserved the selected frame and
measurement geometry. The review reads files without acquiring a camera.

40 automated tests pass, including optical lossless seek, mismatched pairing,
corrupt data/index, background disk failure, acquisition error propagation,
manifest consistency, legacy archive compatibility and existing thermal tests.

This is app-native continuous video, not MP4 export. Playback may skip display
frames to follow elapsed time; stepping accesses every stored frame. Same-buffer
pairing is verified, but physical thermal/optical exposure synchronization and
absolute temperature accuracy remain unqualified. Long-duration recording,
physical unplug/recovery and slow/full real-disk trials are still pending.
