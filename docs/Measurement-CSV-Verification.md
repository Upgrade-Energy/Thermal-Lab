# Automatic measurement CSV — 8 September 2026

Recording now writes an Excel-compatible `measurements.csv` alongside the thermal
and optical archive. It uses the same accepted frames and Record/Stop boundaries.
The thermal writer thread writes the CSV, so preview refresh and spreadsheet
generation never require another capture stream or rereading the full archive.
Native thermal resolution, temperature precision and optical recording are unchanged.

Every point or region in the recorded workspace gets one row per frame. Names,
stable IDs, geometry, camera identity and recording elapsed time are preserved.
Points have a value; regions have minimum, mean and maximum. The file includes
UTF-8 BOM and escapes formula-like names for spreadsheet use. Layout changes
apply to subsequent rows without relabeling previously recorded data.

During capture, the file is `measurements.partial.csv`. Only successful
finalization publishes `measurements.csv`; failures stay visibly incomplete in
both the filename and session manifest. The live **Show CSV** button becomes
available after a completed recording and reveals the file in File Explorer.
The existing review export is now labeled **Export history CSV**.

## Verification

The complete suite passed **104 tests**, including new coverage for point/region
statistics and precision, duplicate names with distinct IDs, Unicode and CSV
escaping, renaming/moving/removing a measurement, record boundaries across two
sessions, empty layouts and disk/camera failure finalization.

Native Windows testing with Desk camera added and renamed one temporary region
using the real Measure controls. A recording with the user's three existing
points plus that region produced:

| Check | Result |
| --- | --- |
| Session | `20260908-202917-760026` |
| Recorded frames | 600 |
| Measurement CSV rows | 2,400 |
| Recorded arrival rate | 25.0063 fps |
| CSV elapsed time | 0.031 to 23.985 seconds from recording start |
| Every CSV value, name, ID, geometry and frame time | Exact match to recorded frame |
| Numerical temperatures checked | 29,491,200 |
| Lossless optical pairs checked | 600 |
| First/last native thermal and optical comparisons | Exact |
| Completion | COMPLETE, CSV finalized, preview remained live |

The production verifier now checks optional automatic CSVs against every archived
frame in addition to its existing numerical and optical integrity checks. The
result is saved under `camera-evidence/20260908-202917-760026-verification.json`.
The temporary region was removed afterward; the user's three original points
and alignment were checked against a pre-test backup and preserved exactly.
Local test output and screenshots are under `runtime/dev15-csv/`.

A second live recording, `20260908-203307-0e0c9b`, passed the same numerical,
optical and CSV checks for **1,072 frames and 3,216 rows** with the original three
points. The final **Show CSV** control selected `measurements.csv` in File
Explorer. The native widget checks passed again after this final control change;
updated app error logs were empty. Across both recordings, **1,672 frames and
5,616 measurement rows** passed verification.

This was a real camera export check, not a new calibration or dual-camera
bandwidth qualification. The older Room window was already disconnected with a
native buffer error when inspected; its interface was refreshed and left idle.
No power instrument commands were sent.
