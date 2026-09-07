> Historical hardware qualification performed before extraction from Power Lab.
> Runtime paths below refer to the original workspace. See README for standalone usage.

# TC001 Max direct Windows capture — 7 September 2026

Power Lab now captures and records the connected TC001 Max directly using the
locally installed TopView 1.30.003 camera library. TopView was closed during all
direct recordings. No Windows SDK was obtained or required. All hardware work
was limited to the camera; no power or DAQ instrument commands were issued.

## Hardware results

Windows 11 x64, native x64 Python, WinUSB, VID 3474 / PID 4962, serial
YFDVS000000000001. The driver remained healthy after the recordings.

| Check | Result |
| --- | --- |
| Initial 12-second recording | 223 distinct frames; approximately 19 fps before optimization |
| Optimized 45-second recording | 1,120 distinct frames; 25.006 fps; 1,122 received buffers, two startup discards |
| Fresh-worker reopen, 20 seconds | 494 distinct frames; 25.001 fps; 496 received buffers, two startup discards |
| Independent archive verification | All 1,614 frames / 79,331,328 finite temperature values checked; increasing arrival times; center-point calculations matched |
| Raw-to-recorded round trip | First and last frames of both optimized runs exactly matched decoded raw buffers and recovered original integer temperature codes |
| Concurrent capture worker | Rejected before opening USB; FAILED manifest with zero frames |
| Visual inspection | First/last thermal frames showed a coherent bench scene; no visible startup corruption in accepted frames |
| USB cleanup | Standard USB diagnostic passed after all workers exited; camera healthy, no errors |

These are observed host rates, not a claim of zero device drops. Each optimized
recording discarded its first two buffers and required no further alignment
rejections. Device exposure timestamps and counters have not been decoded.

## Run from the repository

Close TopView before capture. Use x64 Python on Windows and the tested TopView
installation, including its original dependencies and installed camera driver:

```powershell
python scripts/check_tc001.py --output runtime/camera-evidence/usb-new.json
python scripts/capture_tc001.py --topview-directory runtime/topdon/app --output runtime/camera-evidence/capture-new --seconds 45
```

Output paths must be new. Capture duration is bounded to 1–600 seconds. The CLI
is independent of the bench controller and accepts exactly one healthy Max.
It writes `camera-session.json`, indexed `thermal.jsonl.gz` / `thermal.idx`,
and first/last raw `.frame` buffers. Each numeric frame contains 49,152 Celsius
values, a center point, full-frame minimum/maximum/mean, source identity,
arrival time, and experimental calibration metadata. Native sensor orientation
is 256 columns by 192 rows; rotate clockwise only when matching TopView display.

The manifest must say `COMPLETE`; exceptions produce `FAILED`. Process crashes
can leave `RECORDING`, which must be treated as incomplete. Archive timestamps
are host monotonic arrivals, not physical exposure times. Separate captures have
separate origins. The library belongs in a dedicated acquisition process.

## How the direct path was established

Standard WinUSB enumeration initially inspected only interface 0. Expanded
diagnostics found interface 1, alternate setting 1, with stream IN endpoint 0x81
and OUT 0x04. Observing TopView's camera calls established initialization,
buffer size and native function structures. A raw WinUSB prototype received
data but lost frame alignment across partial transfers; it was not adopted.
The installed vendor library handles framing successfully.

`thermal_lab/tc001_max.py` locks the observed ABI to `dll/dll_c001max/libirdvs.dll`
SHA-256 `f7a745d1e056e1dcda6de43ee30483fa5490eeb535bc18bbbd7ff031fcf6d3e6`.
Unknown versions are rejected. No proprietary DLL is included in the repository.
This is an experimental adapter based on observed calls, not a documented SDK
contract. Keep the tested installation and its dependencies together.

The native buffer is 1,770,496 bytes. Its first 98,304 bytes contain a 256×192
neutral-chroma YUYV infrared plane; the next 98,304 bytes contain little-endian
16-bit temperature codes. Initial capture exposed an incorrectly aligned first
buffer with plausible false temperatures. The adapter now discards two startup
buffers and checks infrared chroma, size and supported temperature range on
every frame. Sustained invalid buffers and frozen thermal planes fail capture.

Numerical recording initially managed approximately 19 fps. A temperature
lookup table, avoiding a redundant deep copy of pixel values, and gzip level 1
raised measured recording throughput to approximately 25 fps. Other recorder
callers retain their original compression default.

## Temperature interpretation

The observed apparent-temperature conversion is `code / 64 - 273.15` Celsius.
For one actual TopView still with emissivity set to 1.00, all 49,152 decoded
pixels were compared with the corresponding vendor CSV after rotation. Maximum
absolute difference was 0.0625 °C; mean absolute difference was 0.0272 °C.
The CSV reports tenths of a degree. This comparison supports the conversion;
it does not establish absolute physical accuracy or a complete correction model.
TopView's original emissivity 0.98 configuration was restored after comparison.

Frames explicitly report `apparent_raw_kelvin_64`, no host environmental
correction, and unqualified absolute accuracy. Emissivity, reflected temperature,
distance and atmospheric correction must be implemented and validated before
claiming equivalence across TopView settings or calibrated object temperatures.

## Evidence and remaining camera work

- [45-second archive verification](camera-evidence/direct-recording-02-verification.json)
- [20-second archive verification](camera-evidence/direct-recording-03-verification.json)
- [TopView numerical comparison](camera-evidence/unity-emissivity-comparison.json)
- [Post-capture USB inspection](camera-evidence/windows-usb-after-direct-capture.json)
- [45 passing camera/Studio tests](camera-evidence/direct-capture-tests.txt)

Large raw files and recordings remain locally under
`runtime/camera-evidence/direct-recording-02` and `direct-recording-03`.
The inspected first/last montage is `direct-recording-02/inspection.png`.
Earlier vendor export/video evidence remains in the Power-Lab repository.

Remaining work: Studio live-view integration, independent disconnect/recovery
qualification, longer soak tests, multi-camera identity and synchronization,
exposure timing/drop detection, environmental correction and absolute accuracy.
The current Studio UI still uses simulated thermal frames. No power-instrument
integration is enabled by this camera increment.
