# Power Lab local integration v1

Thermal Lab remains independently runnable. Its optional local service owns
camera discovery, native workers, measurement layouts and lossless recordings.
Power Lab coordinates the service through HTTP on **127.0.0.1 only**. No Power
Lab modules or instrument drivers are imported by Thermal Lab.

This increment is a programmatic API and CLI integration. Power Lab's Studio
controller can use real cameras alongside **simulated electrical runs**. New
camera-selection UI, embedded optical video and linked-archive scrubbing in the
Studio browser are not implemented. Use Thermal Lab's recording review for full
optical/thermal playback. Physical power output remains blocked by Studio.

## Launch

From the Thermal Lab repository, after installing `.[desktop]`:

```powershell
python -m thermal_lab.integration --topview-directory 'C:\path\to\TopView'
```

The default connection file is `%USERPROFILE%\.thermal-lab\integration.json`;
it contains an ephemeral port and bearer token. Keep this credential local; do
not include it in archives or source control. `--connection-file` and
`--recordings` select other locations. An OS-held file lock prevents duplicate
services on one connection file, releases on process death, and allows the next
service to replace the stale descriptor. Clients must reload the descriptor
after a service restart. A reconnect starts a new session; no run is resumed.

Camera windows and the service use the same per-device ownership guard. Release
cameras from TopView or Thermal Lab's live windows before using the service.
Both tested TC001 Max cameras still need separate USB controller paths; disk
compression does not reduce USB bandwidth.

## HTTP contract

All requests require `Authorization: Bearer <token>`. Browser `Origin` headers
are rejected; this endpoint is for the local Power Lab controller, not direct
web-page fetches. POST requests must be JSON objects of at most 64 KiB. Errors
return JSON `error` with HTTP 400/403/404/503. Requests have no arbitrary output
path or native command fields. The service creates archive paths itself.

| Endpoint | Purpose |
|---|---|
| GET `/v1/cameras` | Healthy/unhealthy Windows PnP identities and connection guidance |
| POST `/v1/connect` | Claim selected cameras with a client-generated 32-hex `session_id` and `cameras` list |
| POST `/v1/heartbeat` | Renew the session lease and return current state; supply `session_id` |
| GET `/v1/state` | Read freshness, named measurements, active run and last ten run summaries; does not renew lease |
| POST `/v1/runs/start` | Start lossless recording; supply `session_id`, 32-hex `run_id`, and same-host `run_origin_monotonic` |
| POST `/v1/runs/stop` | Finalize a run; supply `session_id` and `run_id` |
| POST `/v1/disconnect` | Release cameras after finalization; supply `session_id` |
| POST `/v1/shutdown` | Stop an idle service after cameras have been disconnected |

Each selected camera is `{camera_id, settings}`. `camera_id` is the Windows PnP
identity returned by discovery, never a persistent integer index. `settings`
uses Thermal Lab's workspace schema: named/identified points and rectangles in
normalized thermal coordinates, plus optional optical alignment. The service
validates identity and settings before acquisition. Settings are fixed for a
connected integration session. One to three selections are accepted; only two
physical cameras have been qualified.

Start is idempotent for the same session, run ID and origin. Its state progresses
STARTING → RECORDING only after every camera acknowledges recording and delivers
a preview from that run. Stop progresses STOPPING → COMPLETE only after every
worker confirms finalization. FAILED/INCOMPLETE/unfinished manifests must never
be treated as COMPLETE. Poll until completion; an HTTP acknowledgement alone
does not mean recording was finalized.

## Timing, quality and failures

Readings include physical camera identity, `source`, `unit: C`, arrival sequence,
`host_monotonic`, age, freshness, run ID, named numerical measurements and layout.
Measurements become empty when stale or disconnected. Power Lab additionally
ages its cached response so a lost service cannot leave a valid-looking reading.
The interface currently samples preview measurements at up to 10 Hz; the camera
archive independently retains **every accepted frame at approximately 25 fps**,
the full 256×192 temperature grid, and lossless 1024×768 optical pixels.

Camera manifests contain the Power Lab run ID, camera and run monotonic origins,
and the explicit arrival-time basis. Every recorded thermal frame also contains
`run_id` and `run_elapsed_s`. This supports a shared host timeline; it does not
claim simultaneous physical exposures, cross-host synchronization or calibrated
absolute temperature accuracy.

The session lease expires after eight seconds without heartbeat. Camera faults
or lease loss abort the recording group instead of silently dropping a camera.
Startup, stream silence and finalization are bounded. Worker processes also
watch their owning process: owner death exits the worker and releases USB
handles, leaving interrupted archives unfinished. Power Lab applies its camera
failure policy, stops simulated output before camera finalization, and writes
`thermal-lab-link.json` with archive locations and honest completion status.
Unknown final frame counts are null, rather than invented zero counts.

Power Lab stores actual camera source labels separately from the SIMULATION
electrical source. Its ZIP includes the link manifest and recorded camera
measurements in `run.json`; it does not copy multi-gigabyte camera archives.
Keep or move those archives separately. Current links contain local absolute
paths, so a moved archive may require reopening manually in Thermal Lab.

## Verified on Windows, 2026-09-07

Two real-camera integrated runs completed, followed by a deliberate service
crash and successful restart/reconnect without moving cables. The audited
30-second run `db8ebf099839427593675199ac3343b8` contained 248 simulated electrical
samples and 784 full optical/thermal pairs per camera at 24.993 / 25.006 fps.
All 496 Power Lab camera observations matched the archived frame's measurements,
arrival sequence and host timestamp. All 77,070,336 numerical temperatures were
validated, all 1,568 optical hashes passed, and first/last native buffers matched
exactly. All source archive hashes remained unchanged. Saved blended frames from
both cameras were visually inspected.

The crash run `244d6a4e95534d6a9f8bab3ac3dcf8c7` faulted the simulation and retained
both incomplete archive paths. Both orphan camera workers exited. The restart
run `99605a4afbca4a08ad05878645d41e96` recorded another 159 pairs per camera and
completed. No power instrument was commanded. Physical unplug tests, long-run
integration qualification, external pre-event buffers,
absolute temperature calibration and physical protection remain pending.

## Power Lab browser views

Authenticated `POST /v1/view` accepts `camera_id` and `mode` (Thermal, Optical or
Blend). Live requests require the owning `session_id` and a fresh camera sample.
Recorded requests instead require a 32-hex `run_id` and finite `elapsed_s` on
Power Lab's shared run clock. Archive lookup is confined to the service's
recording root and verifies camera/run identities and COMPLETE manifests. It
works after service restart without relying on in-memory run history.

The reply contains the complete numerical frame and a lossless 1024 × 768 PNG
display image. Optical conversion/alignment are display-only. Stored original
YUYV and temperatures remain unchanged. Seeking uses the camera's recorded time
offset and reports the actual frame time and difference from the requested time;
it does not claim simultaneous exposure. Early/late seeks clamp to the first/last
frame with the difference still visible.

Power Lab proxies these calls through its session-authenticated HTTP server.
Service credentials remain server-side, and browser origins remain rejected by
Thermal Lab. Rendering happens outside the acquisition lock; preview requests do
not renew camera ownership leases or change recording settings.

Thermal Lab: **64 tests passed**. Power Lab: **92 of 93 tests passed**, including
all four new integration tests. The legacy `test_browser_loss_stops` assertion
also failed in an untouched `git archive HEAD` baseline: output was OFF while
phase text still read 'No-load check running'. Instrument-controller code/tests
were not changed.

Machine-readable evidence: `docs/camera-evidence/powerlab-integration-dev9.json`.
Repeat the hardware run with Power Lab's `scripts/test_thermal_integration.py`,
then audit its exported ZIP with `scripts/verify_powerlab_integration.py` here.

## Browser qualification, DEV10

Power Lab browser selection, measurement settings, preparation, recording, live
blended previews, linked Thermal/Optical/Blend review, event seeking, play/pause
and numerical pixel inspection were tested with both real cameras. Service loss
cleared the browser frames; restarting the service restored archived review.
The complete run retained 1,125 / 1,127 paired frames at 24.85 / 24.89 fps.
All 110,690,304 temperatures, 2,252 optical hashes and 386 Power Lab observations
passed audit; native first/last buffers matched and source files were unchanged.
Evidence: "docs/camera-evidence/powerlab-browser-dev10.json". Screenshots and
full camera recordings remain local. Thermal Lab: 66 tests pass. Power Lab: 95
tests pass, plus the DOM/API camera-selection workflow. No power instruments
were commanded. Browser refresh rate is independent of native recording rate.
