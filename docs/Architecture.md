# Application boundary

Thermal Lab is independently runnable and owns device discovery, camera
acquisition, numerical conversion, measurement definitions, thermal recordings
and its own desktop interface. Its package must not import `powerlab`.

Power Lab owns electrical recipes, instruments and protection. Future
integration is optional: pass a shared run ID and record/stop requests, exchange
selected temperature measurements with timestamp and freshness metadata, and
link resulting archives. A missing camera must be explicitly handled by the
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

Archive compatibility is preserved during extraction. No live IPC interface is
implemented yet. Historical Power Lab camera copies are migration references;
this repository is the source of truth for subsequent camera development.
