# DEV3 multi-camera desktop verification — 7 September 2026

Two connected TC001 Max units were tested on this Windows PC, on different USB
controllers. No power instruments were accessed. This increment replaces the
single-camera guard with explicit device selection, concurrent independent
windows and camera-specific layouts/recordings.

## Identity and startup fixes

The native DLL's numeric device indexes changed after reconnecting. The adapter
now checks the actual newly opened Windows handle's physical device object name
against PnP identity **before initializing or streaming**. Missing/ambiguous
identity fails; PnP enumeration order is never used as proof of identity.

Concurrent selection initially raced. A named mutex now serializes only device
selection/start, leaving capture concurrent. A later desktop test exposed a hang
when selection probed the already-streaming camera first. Topology-scoped hints
now prefer a previously verified matching index, then unknown indexes. Every
open still verifies actual identity; hints are never accepted as identity proof.
Changing PnP device-object topology invalidates hints. Hints live under
`%LOCALAPPDATA%/Thermal-Lab/device-index-hints.json` and contain no frames.

A per-camera mutex rejects duplicate ownership before native open. A real CLI
duplicate-open attempt was rejected while the desktop recording continued.
Startup reads can reopen at most twice before any frame has been accepted.
Established-stream failures are surfaced without silently restarting a recording.
The desktop terminates a stuck startup after 30 seconds and a requested stop
after seven seconds. A timed-out native startup was exercised during development;
it left no falsely completed recording.

## Verified hardware results

An initial integrated-worker test recorded **498 frames on each camera** with
distinct verified identities and independent point definitions. Both archives
passed indexed numerical verification. The tests launched workers in reversed
PnP-list order to exercise selection.

Desktop operation was then exercised through the native Windows UI:

- Chose and connected a camera; placed a temperature point and saw its live value.
- Opened a separate camera window using the app button.
- Restored each camera's own layout after closing/reopening windows.
- Started separate numerical recordings while both streams were live.
- Closed the hub-camera window during recording; its archive finalized while
  the directly connected camera kept streaming and recording.
- Stopped the remaining recording normally, keeping its preview live.
- Reopened the other window and reconnected with its original camera layout.
- Inspected live views and decoded optical/thermal first/last capture artifacts.

| Desktop session | Frames | Recorded rate | Finalization |
| --- | ---: | ---: | --- |
| 20260907-133017-909c50 | 3,437 | Approximately 25 fps | Window close; other startup failure did not interrupt recording |
| 20260907-133339-c9c4e1 | 2,771 | 24.955 fps | Window close while the other recorded |
| 20260907-133454-6b6c4f | 1,211 | 24.981 fps | Stop recording; preview continued |

The final pair had about **35.72 seconds of overlapping host-arrival recording**.
Its **3,982 frames / 195,723,264 temperature values** passed finite-value,
measurement-recomputation, monotonic-arrival, index/count and exact first/last
raw-buffer round-trip checks. An additional full archive scan checked the actual
camera identity, native-handle identity basis and matching workspace identity on
every frame, with disjoint measurement IDs across the pair. Neither successful
final worker needed a startup retry. Both archives are `COMPLETE`.

Evidence:

- [Camera pair identity and overlap](camera-evidence/desktop-dev3-pair.json)
- [Hub-camera numerical verification](camera-evidence/20260907-133339-c9c4e1-verification.json)
- [Direct-camera numerical verification](camera-evidence/20260907-133454-6b6c4f-verification.json)
- [First desktop recording](camera-evidence/20260907-133017-909c50-verification.json)
- [Worker camera 0](camera-evidence/selected-workers-132749-camera0.json)
- [Worker camera 1](camera-evidence/selected-workers-132749-camera1.json)

Full recordings remain local in ignored `recordings/desktop-dev3/`; the inspected
image comparison is `runtime/desktop-dev3-recorded-pair.png`. Local diagnostic
scripts/logs remain under `runtime/`. The 29 automated tests pass, including
bounded startup retry, no retry after a good frame, camera-layout isolation,
case-insensitive identity, hint ordering and topology invalidation. DEV3 builds
as a standalone wheel; no proprietary DLLs or recordings are bundled.

## Limits

Multi-camera use currently means independent windows, not a combined multi-camera
canvas or synchronized record-all command. The tested configuration is two Max
cameras on separate controllers; shared-hub capture failed. Hotplug during live
capture, arbitrary hubs, other DLL versions and a long-duration soak remain
unqualified. Native crashes/timeouts remain possible and are isolated per worker.

Concurrent host arrivals do not establish synchronized exposures. Absolute
temperature accuracy, environmental corrections and continuous optical-video
recording remain outside this increment. Existing overlay and measurement
features continue to operate independently per camera.
