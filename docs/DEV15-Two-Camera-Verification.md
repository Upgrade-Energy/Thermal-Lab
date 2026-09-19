# DEV15 two-camera desktop verification — 8 September 2026

Tested the actual native Windows app with two TOPDON TC001 Max cameras. Both
devices reported Windows status OK and problem code 0. Their location paths
resolved to separate USB controllers, XHC1 and XHC0. This result applies to this
connection arrangement; it does not qualify putting both cameras on one hub.

## Native GUI flows

- Opened the second window through Workspace → Open another camera window while
  the first camera streamed. The two windows displayed distinct desk and room views.
- Saved **Room camera** for the second camera; **Desk camera** retained its name.
  Both names and device selections survived app restarts.
- Added one test point to Desk camera and one test rectangle to Room camera.
  The table, image geometry and saved layouts remained independent. Selecting
  each friendly name restored the correct layout, without mixing device IDs.
- Recorded both cameras concurrently with full thermal grids and lossless optical
  planes. Disconnecting Room camera finalized its session while Desk camera kept
  recording. Room camera reconnected with its region and name intact.
- Disconnected and restarted Desk camera while Room camera continued recording.
  Desk camera recovered with its original point and alignment. Closing the Room
  window then finalized its second recording without stopping Desk camera.
- Reopened Room camera with the updated code, recorded both again, and used the
  independent Stop recording buttons. Both previews remained live afterward.
- Removed the temporary measurements. Desk camera's original saved layout was
  restored exactly; Room camera retained its new name and original alignment.

## Issues found and fixed

Starting a recording could leave the preceding session's COMPLETE status visible,
and the first counter could display `None`. Recording-start events now show the
new session path and the initial frame count displays zero until counts arrive.

Camera names were cached independently in each process. Renaming Room camera did
not update the Desk window's camera list even after Refresh. Opening the selector,
refreshing devices and reconnecting now reload the shared name registry. The
correct hardware identity remains the selection key. Added a regression check
for another window's rename and the resulting reconnected layout metadata.

The complete automated suite passes **100 tests**. Capture and recording workers
were not altered. The restarted live app error logs were empty.

## Recording evidence

The production verifier reads every numerical grid, checks stored measurements
against it, verifies every lossless optical SHA-256 and pairing, checks strictly
increasing arrival times, and compares the retained first/last native buffers
with their recorded thermal and optical values.

The following sessions finalized COMPLETE and passed those checks:

| Session | Camera | Paired frames | Average fps |
| --- | --- | ---: | ---: |
| 20260908-122327-0667e2 | Desk | 4,005 | 24.9519 |
| 20260908-122354-d4bfec | Room | 1,049 | 25.0179 |
| 20260908-122548-f56191 | Room | 7,510 | 24.9365 |
| 20260908-123002-9f1e3c | Desk | 7,277 | 23.7887 |
| 20260908-123313-c68499 | Room | 1,721 | 24.3485 |
| 20260908-123810-fe46b1 | Room | 2,945 | 24.2772 |
| 20260908-123826-da0a91 | Desk | 1,989 | 24.9279 |

All **seven sessions passed**, totaling **26,496 paired frames**,
**1,302,331,392 numerical temperature values**, and **26,496 optical hash checks**.
Each retained the native **256 × 192 thermal grid** and lossless **1024 × 768
optical plane**. First, middle and last samples retained the expected camera name,
independent measurement layout and alignment; calculated extrema matched the
temperature grid exactly.

The 12:30 Desk and 12:33 Room runs overlapped heavy background archive
verification. Arrival rates were lower during that workload, with maximum gaps
of 110 ms and 172 ms. The final two runs repeated the test after those audits
finished: **24.93 fps Desk** and **24.28 fps Room**, including **79.81 seconds**
of concurrent recording. Both had maximum host-arrival gaps of 79 ms. Full
resolution, numerical precision and lossless optical content were preserved;
these rates do not prove a unique physical exposure in every nominal 40 ms slot.

Inspected first/middle/last thermal, optical and blended frame sheets from both
cameras. They showed the correct distinct scenes and measurement overlays,
without swapped camera content or corrupt images. These sheets are preview
renders; the original archives retain native resolution. Both updated app
windows were left connected and live, with recording stopped and no temporary
test measurements.

Per-session verifier JSON is under `docs/camera-evidence/`. Local screenshots,
frame samples, original-layout backups and the combined audit are under
`runtime/dev15-dual/`. Original recordings remain under `~/Thermal-Lab-Recordings`.

## Scope

Reconnect testing used the app's Disconnect/Connect and close/reopen controls.
No physical unplug test, USB power interruption, new camera calibration or power
instrument command was performed. The two recordings use host arrival times;
concurrent capture does not establish physical exposure synchronization.
