# DEV4 playback verification — 7 September 2026

Implemented a standalone offline review window and a launch button in the live
desktop. The player reads indexed numerical thermal recordings without opening
a camera or altering an archive. Optical-video capture/playback remains pending.

## Implemented behavior

- Thermal image playback with play/pause, frame stepping, frame slider,
  host-time graph seeking, 0.25×–4× speed, palette and view rotation.
- Recorded point/region geometry, per-frame names and values, pixel inspection.
- Background history scan with numerical measurement recomputation.
- Point and region min/mean/max plots; missing/moved measurements create gaps.
- Full recorded history CSV export with camera/source, stable measurement IDs,
  latest names, frame indexes, elapsed times, scalar values and geometry.
- COMPLETE-manifest, index, offset, size, timestamp, identity and frame validation;
  corrupt/incomplete inputs produce visible errors. No recovery data is presented
  as a complete recording. Export refuses to overwrite an existing file.

## Real recording checks

| Recording | Frames checked | History series | Exact CSV rows |
| --- | ---: | ---: | ---: |
| 20260907-133454-6b6c4f | 1,211 | 1 point | 1,211 |
| 20260907-133339-c9c4e1 | 2,771 | 1 point + region min/mean/max | 11,084 |

Both recordings were captured from actual TC001 Max cameras during DEV3 testing.
The reader recomputed every saved measurement, recovered first/last pixel arrays
exactly from their native buffers, and sought to first/middle/last timestamps.
Every exported value, identity, statistic, index, time and geometry matched its
checked history sample. SHA-256 hashes of every source-session file were unchanged
after playback reads and export.

[Machine-readable results](camera-evidence/playback-dev4-verification.json)
contain source hashes and per-session checks. Local exported CSVs are under
ignored `runtime/*-review-history.csv`.

Native UI inspection exercised real-file playback, moving plot cursor, graph
seeking to frame 602, advancing to frame 603, and CSV export through the Windows
save dialog. The UI-created 1,211-row `runtime/review-ui-export.csv` was identical
byte-for-byte to the independently checked export. A low-contrast hovered button
was found and its style corrected. UI logs remained free of exceptions.
The final build also displayed the second recording's point and rectangle, and
switching the history selector to Region 1 mean produced its complete mean trace.

The automated suite contains 33 passing tests. New coverage includes exact seek
boundaries, missing/moved measurement histories, cancellation, CSV precision and
formula-like text escaping, overwrite rejection, incomplete/corrupt indexes,
wrong camera identity, and numerical measurement disagreement. Synthetic fixtures
are explicitly SIMULATION and are not counted as hardware evidence.

## Limits

Only single-camera 256×192 COMPLETE archives are supported by this initial player.
The index limit is one million frames; history limit is two million scalar
samples. History scanning can take time on long sessions but runs separately from
UI callbacks. Playback rendering follows host time and may skip display frames;
frame stepping and CSV export retain individual saved samples.

There is no continuous optical-video playback, graph/image export, new offline
measurement drawing, session comparison or exposure synchronization in DEV4.
Temperature values remain apparent readings with unqualified absolute accuracy.
