# Third-party components

The MIT license covers Upgrade Energy's Thermal Lab code and documentation.
Dependencies retain their own licenses; it does not relicense TOPDON software,
Windows drivers, Python, Tcl/Tk, NumPy, Pillow, OpenCV, LZ4 or FFmpeg.

The Windows installer retains dependency license files in its runtime tree and
records pinned wheel filenames and SHA-256 values in `DEPENDENCIES.json`.
See `scripts/windows-wheels.json` and `scripts/build_installer.py` for exact inputs.
FFmpeg distributed with imageio-ffmpeg has its own license/build conditions;
consult the bundled package notices before redistributing a modified binary.

TOPDON TopView and its proprietary camera DLLs/drivers are separate prerequisites.
No redistribution permission for those vendor libraries is asserted. They are
not included in this repository or installer. Install a compatible TopView copy
from TOPDON. TOPDON and TC001 Max are their owners' trademarks. This independent
project is not an official TOPDON product or endorsement.
