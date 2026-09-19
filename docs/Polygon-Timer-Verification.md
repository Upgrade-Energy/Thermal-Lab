# Recording timer and polygon areas — 8 September 2026

Verified on native Windows with the connected Desk TC001 Max, using the standalone
Thermal Lab app. No power instruments were commanded.

## Behavior

The header timer sits beside Record/Stop and displays hours:minutes:seconds.
It starts from the acquisition worker's monotonic recording origin, resets for
each session, and retains the final recorded frame's duration after Stop.
Interrupted capture is labeled Interrupted. Camera uptime has its own explicit
label in the bottom status line. The completed manifest retains `duration_s`.

Polygon areas support 3–64 ordered corners, including concave outlines. Click
corners; finish by clicking the first corner, pressing Enter with image focus,
or using Finish polygon. Undo corner, Backspace and right-click remove the last
corner; Cancel or Escape discards a draft. In Select mode, drag the shape to move
it or drag its corner handles to reshape it. Invalid crossing or empty shapes
are rejected. Draft shapes do not enter recorded measurements.

Minimum, mean and maximum use only thermal pixels whose centers fall inside or
on the polygon edge. Saved layouts, recorded workspace geometry, automatic CSV,
playback, analysis history and labeled image/video exports preserve the polygon.
Automatic CSV appends `shape` and JSON `vertices`; its existing coordinate columns
give the bounding box. Older point/rectangle layouts and archives remain readable.
Selected-target alignment still uses a rectangular crop around a selected area.

## Automated and native UI checks

The full suite passed **112 tests**. New checks cover concave masks, boundaries,
invalid geometry, layout and CSV persistence, movement, recording/playback/history,
export outlines at all four rotations, clock reset/freeze/error behavior, and native
Tk polygon creation, corner editing and cancellation.

The real Windows interface was exercised and screenshots inspected:

- Created a concave six-corner polygon over the live thermal image.
- Checked disabled Finish below three corners, right-click undo, numbered preview
  corners, closing via the first corner, and dragging a selected corner.
- Recorded twice. The first timer advanced and stopped at **00:00:55**. The next
  session reset to zero and stopped at **00:01:10**.
- Opened the second recording and checked the recorded outline and numerical row.
- Switched playback to Analysis, drew a triangle and finished it with Enter;
  its min/mean/max appeared and its separate analysis history was generated.
- Inspected a full-resolution labeled Blend PNG containing the concave polygon.

The temporary live polygon was removed after testing. The user's three original
points, names and alignment matched the pre-test backup exactly. The updated Desk
window was left live and not recording. Its error log was empty.

## Real recording evidence

| Session | Frames | Duration | Host arrival rate | CSV rows | Audit |
| --- | ---: | ---: | ---: | ---: | --- |
| `20260908-210535-b930b9` | 1,379 | 55.157 s | 25.0045 fps | 5,516 | PASS |
| `20260908-210743-b0e1e1` | 1,764 | 70.546 s | 25.0018 fps | 7,056 | PASS |

Every CSV value, name, ID, geometry and timestamp matched its archived frame.
The production verifier checked all numerical temperatures and optical pairs,
plus exact first/last retained native buffers. Native **256 × 192 thermal** and
lossless **1024 × 768 optical** recording quality was preserved. Audit JSON files
are in `docs/camera-evidence/` under the session names above.

An independent OpenCV point-in-polygon check agreed exactly at all 49,152 thermal
pixel centers: the test polygon contained 7,894 pixels. Independently recomputed
minimum, mean and maximum matched the first, middle and last frames of both
recordings. Local screenshots, test output, exported images and the independent
check are under `runtime/dev15-polygon/`; camera images remain excluded from Git.

This verifies measurement geometry and recording integrity. Temperatures remain
apparent values and timestamps use host arrival. This is not a new calibration,
exposure-synchronization or two-camera USB qualification.
