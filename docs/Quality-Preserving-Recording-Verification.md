# DEV8 quality-preserving recording and recovery

Tested on the local Windows PC on 2026-09-07, using two real TC001 Max cameras
on separate AMD USB controller paths. No power instruments were commanded.

## Quality and storage

New optical archives use `lz4-yuyv422-v1`: independently compressed original
1024×768 YUYV422 planes. No scaling, quantization or frame-rate reduction is
introduced. All 256×192 numerical temperature values remain in every accepted
thermal frame. Index hashes cover the original, uncompressed optical bytes.

The first implementation using zlib level 1 could not keep up with two cameras:
both bounded optical queues filled after 55 recorded frames. Both sessions
reported FAILED. The final implementation uses LZ4 4.4.5, which compressed a
real sample in approximately 3.1 ms rather than zlib's 29.3 ms on this PC.
These are sample timings, not guaranteed throughput on other computers.

The subsequent simultaneous hardware test completed:

| Check | Camera 0 (serial identity) | Camera 1 (location identity) |
|---|---:|---:|
| Finalized thermal/optical pairs | 3,047 | 3,048 |
| Recorded span | 121.875 s | 121.922 s |
| Average arrival rate | 24.993 fps | 24.991 fps |
| Accepted sequence gaps | 0 | 0 |
| Maximum arrival gap | 47 ms | 47 ms |
| Numerical values checked | 149,766,144 | 149,815,296 |
| Point/region history values checked | 15,235 | 15,240 |
| Raw optical size for those frames | 4,792,516,608 B | 4,794,089,472 B |
| Compressed optical size | 3,215,685,139 B | 3,317,088,760 B |
| Optical storage reduction | 32.90% | 30.81% |

Every optical pair was decompressed and checked against the SHA-256 calculated
from the original capture. Every numerical grid was validated and every point
and region statistic independently recalculated. First and last native buffers
matched both numerical temperatures and decompressed optical bytes exactly.
Histories and their CSV values, times, geometry and camera identity matched.
Saved previews and blended snapshots were personally inspected: clear desk/PC
and room scenes, corresponding thermal content, and correctly placed annotations.

Older raw optical archives remain readable: the 45,008-frame legacy camera0
archive reopened and its first/last optical hashes passed. Synthetic tests also
cover legacy raw data, incompressible pixels, corruption, oversized decoded
frames, trailing compressed data and disk errors.

Capture: `recordings/lossless-20260907-lz4-dual/`.
Full audits and presentation exports: `runtime/dev8-verify-camera0/` and
`runtime/dev8-verify-camera1/`. Captured images stay local.
Both full audits finished PASS. The entire presentation MP4 exports decoded
successfully (3,048 / 3,050 frames, 1024×768 at 25 fps, with first/last source
mapping checked). All seven source files per camera were unchanged after review
and export. MP4 is a rendered presentation format; it does not replace the
lossless archive. Machine-readable results are in
`docs/camera-evidence/dev8-quality-verification.json`.

## Connection guidance and recovery

The desktop displays a topology assessment from Windows PnP location paths.
Nested hubs sharing one root-port link are recognized as a shared hub path.
Different root ports on the same controller are labeled unverified; missing
topology is unknown. The real separate-controller guidance was visually checked.
Refresh is required after moving cables. This guidance does not reserve bandwidth.

An intentional termination of this app's acquisition worker during a disposable
hardware recording immediately cleared the image and measurements. The desktop
reported an incomplete session, and review rejected its unfinished RECORDING
manifest. A misleading disabled 'Stop recording' label was found and corrected
to 'Record session'.
The stale disconnected cursor message was also corrected to clear when a fresh
frame arrives after reconnect.

The same physical camera subsequently reconnected without cable changes. A new
277-frame optical/numerical recording finalized COMPLETE and passed the full
recording verifier, including 13,615,104 numerical values and every optical hash.
The earlier incomplete archive was retained separately. The corrected desktop
also successfully disconnected and reconnected within the same window.

Automated fault tests cover read failure after a recorded frame, preservation
of the FAILED archive across recovery, disk failure, discarded queued previews
after camera loss, stale-frame recording prevention, and the eight-second
established-stream watchdog. A native hang leaves the archive explicitly
unfinished rather than inventing successful finalization.
All 59 automated tests passed on the local Windows Python 3.12 runtime.

## Limits

This is a two-minute qualification of the new compressor. The previous 30-minute
test used raw optical storage. Storage savings vary with scene and noise; keep
uncompressed-size headroom. The new format needs the desktop LZ4 dependency and
DEV8 or later to read it. USB traffic is unchanged, so compression does not fix
the shared USB 2 hub bandwidth limitation.

Physical unplug/replug was not performed in this turn; real process-failure
recovery and simulated camera read failures were tested. Device exposure timing,
absolute temperature accuracy and the previously observed brief source optical
holds remain unqualified. Accepted sequence continuity is not a device-level
dropped-exposure counter.
