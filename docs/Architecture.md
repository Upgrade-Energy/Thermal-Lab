# Application boundary

Thermal Lab is independently runnable and owns device discovery, camera
acquisition, numerical conversion, measurement definitions, thermal recordings
and eventually its own interface. Its package must not import `powerlab`.

Power Lab owns electrical recipes, instruments and protection. Future
integration is optional: pass a shared run ID and record/stop requests, exchange
selected temperature measurements with timestamp and freshness metadata, and
link resulting archives. A missing camera must be explicitly handled by the
consumer when temperatures participate in test protection.

The current native library has process-global state. Keep acquisition in a
dedicated process. Do not embed it into an electrical controller process. The
tested adapter accepts one camera and rejects concurrent capture workers.

Archive compatibility is preserved during extraction. No live IPC interface is
implemented yet. Historical Power Lab camera copies are migration references;
this repository is the source of truth for subsequent camera development.
