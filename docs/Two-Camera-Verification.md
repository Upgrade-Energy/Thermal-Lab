# Two-camera test — 7 September 2026

Status: individual capture verified; simultaneous capture blocked on the tested
hub connection. Production adapter retains its single-camera guard.

Both TC001 Max devices enumerated healthy with WinUSB / oem95.inf. Standard USB
interface access succeeded for both. Windows reports both attached to the same
`VID_05E3&PID_0610` hub, on ports 2 and 1 respectively.

An isolated local experiment used one process per camera and the existing,
hash-qualified TopView DLL. The production adapter was not changed. Inspection
of the native open function confirmed that the third DeviceInfo field selects
the zero-based matching VID/PID device. Observed CreateFileA calls associated:

| Experimental index | Windows instance suffix | Inspected optical scene |
| --- | --- | --- |
| 0 | YFDVS000000000001 | Desk and keyboard |
| 1 | 7&25379B34&0&1 | Ceiling and light |

These are observed mappings for this connection, not stable index guarantees.
The second instance ID is location-based; moving ports may change it.

## Results

| Run | Camera 0 | Camera 1 |
| --- | --- | --- |
| Simultaneous, 13:10:58 | No frames; native frame_get -625 | No frames; native frame_get -625 |
| Sequential, 13:11:16 | 297 distinct frames / 12.000 s | 297 distinct frames / 12.016 s |
| Simultaneous, 13:11:59 | 286 distinct frames / 12.016 s | Native process access violation, exit 0xC0000005 |
| Simultaneous without tracing, 13:12:32 | Ten unusable startup/alignment buffers; failed | 249 distinct frames / 12.000 s, five rejected buffers |

The sequential run validated thermal-plane alignment and temperature code range
on every accepted frame, and saved first/last full native buffers. Both optical
images were decoded and visually inspected. First-frame apparent temperature
ranges were 21.2875–25.225 C and 23.1–27.725 C respectively. These are not
calibrated absolute-accuracy results or full numerical-recording qualification.

The observed native payload is 1,770,496 bytes per frame: two streams at the
requested 25 fps require 88,524,800 bytes/s before protocol overhead. Shared hub
bandwidth is a suspected constraint, not a proven sole cause of the native crash.
The untraced repeat confirms simultaneous failure is not limited to tracing.

## Next hardware check

Move one camera outside this hub onto another PC USB path, preferably a different
host controller, and repeat isolated concurrent capture. Do not enable production
multi-camera selection or claim simultaneous recording until both streams pass,
physical identity is verified, and independent numerical archives are validated.

Local raw buffers, native logs and open traces are under ignored
`runtime/two-camera-probe-{131058,131116,131159,131232}/`. The experiment script is
`runtime/probe_two_cameras.py`; it is a diagnostic guard override, not supported
application code. Initial USB evidence is `runtime/two-camera-ready-check-20260907.json`.
No power instruments were controlled.
