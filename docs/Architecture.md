# Application boundary

Thermal Lab is independently runnable and owns device discovery, camera
acquisition, numerical conversion, measurement definitions, thermal recordings
and its own desktop interface. Its package must not import `powerlab`.

Power Lab owns electrical recipes, instruments and protection. Optional
integration passes a shared run ID and record/stop requests, exchanges
selected temperature measurements with timestamp and freshness metadata, and
links resulting archives. A missing camera must be explicitly handled by the
consumer when temperatures participate in test protection.

The current native library has process-global state. Keep acquisition in a
dedicated process. Do not embed it into an electrical controller process. The
adapter uses one process per selected camera and rejects duplicate ownership of
that device. Windows physical device object names verify the opened native
handle before streaming. Index hints are scoped to the current PnP topology and
only influence selection order; they never replace identity verification. A
shared Windows mutex serializes selection, while capture remains concurrent.

Each camera window is an independent process with its own acquisition worker,
recording and identity-keyed layout. Closing one does not terminate another.
Startup read retries are limited to two and stop after the first accepted frame;
an established-stream failure is reported instead of splicing a restarted stream
into a recording. The desktop bounds native startup and shutdown hangs.
DEV8 also bounds established preview silence to eight seconds and immediately
invalidates displayed frames/measurements on an error or worker exit.

Optical recording compresses each original YUYV422 plane independently with
LZ4 blocks (no stored size header), indexed by its compressed length. The
manifest codec is `lz4-yuyv422-v1`; SHA-256 remains over uncompressed original
bytes. Reads bound decompression to 1,572,864 bytes and require the exact length
and hash. Legacy `raw-yuyv422-v1` and experimental `zlib-yuyv422-v1` remain
readable. A bounded writer queue fails explicitly rather than dropping frames.

DEV9 adds an optional authenticated loopback service and shared run IDs, arrival
timestamps, freshness-aware numerical measurements and archive links for Power
Lab's simulated Studio runs. See [the v1 contract](Power-Lab-Integration.md).
Archive compatibility is preserved. Historical Power Lab camera copies are migration references;
this repository is the source of truth for subsequent camera development.
