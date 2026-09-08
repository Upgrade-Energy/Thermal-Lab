# Shared-hub retest — 7 September 2026

**Blocked:** two simultaneous full TC001 Max streams failed on the current hub.
Each camera works alone while both remain plugged into the hub. This supersedes
no successful separate-controller result; it tests the user's new shared-hub
connection explicitly. No power instruments were commanded.

Windows reports both cameras under
`USB\VID_05E3&PID_0610\6&32455ec1&0&2`, ports 2 and 4, on XHC0.
Both report WinUSB speed code 3, USB device descriptor version 0200 and
512-byte bulk endpoints. Speed code 3 alone means high-speed or higher;
the descriptor and endpoint information identify these as USB 2.0 devices.
Both have Windows status OK, problem code 0, and accessible USB interfaces.

## Tests

| Test | Result |
| --- | --- |
| Production simultaneous 60-second recording attempt | Failed early: camera 0 produced ten unusable alignment buffers; camera 1 finalized only 21 frames before the harness stopped it |
| Camera 0 alone, requested 25 fps | 195 valid frames over 7.766 s, 24.981 fps |
| Camera 1 alone, requested 25 fps | 195 valid frames over 7.766 s, 24.981 fps |
| Camera 0 alone, requested 10 fps | 194 valid frames over 7.719 s, **25.003 fps**; request did not reduce actual rate |
| Both, requested 10 fps | Camera 0 failed after 22 frames; camera 1 captured 348 frames at 25.009 fps |
| Both, requested 25 fps, repeat | Camera 0 failed after 20 frames; camera 1 retried startup once and captured 175 frames at 25.025 fps |

The rate experiments changed only the FPS field of the same native StreamInfo
structure, in isolated diagnostic processes. Production camera settings and
validation were preserved. A first probe-script attempt incorrectly replaced a
ctypes structure with a function and failed before streaming; it was corrected
and is excluded from the hardware results above. The successful second probe
used an ABI-compatible ctypes subclass. Diagnostic result status, not just
process exit code, indicates whether capture passed.

Decoded and visually inspected both independent captures: one sees the nearby
computer/hub and mat; the other sees the chair and room. Thermal and optical
images are intact. No malformed frames were accepted as valid measurements.
Both cameras were stopped after testing and their USB interfaces remained
accessible. The 48 automated tests passed after adding diagnostic metadata.

## Bandwidth and remaining options

The native output is 1,770,496 bytes per frame. Earlier direct USB tracing of
this same DLL observed 1,770,508-byte stream reads on endpoint 0x81, including
the transport wrapper. At 25 fps each, two streams require approximately
88.525 MB/s or 708.2 Mb/s before USB protocol overhead. That exceeds a shared
USB 2.0 high-speed link's 480 Mb/s signaling limit. This is a concrete capacity
constraint, although it does not prove the sole internal cause of every native
malformed-buffer error.

Lowering GUI refresh, dropping host frames or disabling optical *recording*
does not lower camera-to-PC traffic. The tested native FPS field did not reduce
traffic either. A true lower-bandwidth camera mode (lower sensor output rate,
thermal-only transport, smaller optical stream or compression before USB)
would require a supported camera/SDK control that has not been established.
Do not expose the ineffective FPS field as a working setting.

Both can remain connected to this hub for **one-camera-at-a-time** use. Reliable
simultaneous full-stream capture has only been verified on separate controller
paths. An ordinary USB 3 hub still routes these USB 2 devices through its USB 2
portion. A single-cable solution would need hardware providing independent
USB controller paths and compatibility with this PC; no specific dock has been
qualified or recommended for purchase.

## Evidence

[Machine-readable results](camera-evidence/shared-hub-20260907.json) include
the topology/descriptor diagnostic, failed production capture and corrected
single/concurrent rate experiments. Raw frames and logs remain local under
`runtime/shared-hub-rate-probes-v2` and
`recordings/shared-hub-20260907-test1`. The experimental probe script is retained
locally as `runtime/probe_shared_hub_rates.py`.

Diagnostics now save parent hub, location paths, raw WinUSB speed code and USB
device descriptor so future connection changes can be assessed directly.

References: [Microsoft USB FAQ](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-faq--introductory-level),
[WinUsb_QueryDeviceInformation](https://learn.microsoft.com/en-us/windows/win32/api/winusb/nf-winusb-winusb_querydeviceinformation).

## Replacement hub retest, 18:46 PDT

The replacement layout introduces upstream hub `VID_2109&PID_2822` at
`USBROOT(0)#USB(2)` on XHC0. The serial-based camera connects to its port 1.
The other camera connects through downstream hub `VID_05E3&PID_0610` on its
port 4, then port 1. Windows explicitly reports the downstream hub's parent
as the VIA hub. These can be internal hub layers; enumeration alone does not
identify how many physical enclosures the user has. Both cameras still report
USB descriptor 0200 and share the upstream USB 2 connection.

The production 60-second recording attempt failed early with native
`frame_get -625`. Both workers needed one startup retry; one camera saved only
15 paired frames before normal safety shutdown of the pair. Each camera then
passed an individual capture on the unchanged layout: 194 frames / 7.718 seconds
and 196 frames / 7.797 seconds, both about 25 fps. A second concurrent test again
failed: the downstream camera returned `-625` after 20 frames, while the other
captured 337 frames over 13.438 seconds, rejecting eight unusable buffers.

Inspected both production preview images: ceiling light and nearby computer/mat
are visible in their corresponding optical and thermal views. The short saved
archive passed all 737,280 temperature-value checks, 15 optical hashes/pairs,
75 history values, PNG exports, 16-frame MP4 decoding and unchanged-source
hashes. Its duration is only 0.563 seconds; this is **not** a successful sustained
or simultaneous two-camera test. Both workers were stopped after testing.

[Replacement-hub evidence](camera-evidence/new-hub-20260907.json) records the
new topology, both failed concurrent attempts, individual controls and short
archive verification. Local artifacts are in `recordings/new-hub-20260907-test1`,
`runtime/new-hub-rate-probes` and `runtime/new-hub-short-recording-verification`.
No production behavior was changed for this retest.
