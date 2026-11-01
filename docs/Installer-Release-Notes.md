# Thermal Lab 0.1.0-dev19

Open-source distribution of Thermal Lab under the MIT license. Includes the
license and third-party notices in the Windows installer, a public operating
guide reconciled from Confluence and DEV18 evidence, and Workspace → Report a bug.
The bug-report action opens a GitHub form; it does not upload data automatically.

Retains DEV18 automatic TopView discovery, stale-path recovery, recording,
polygons, hot/cold tracking and review/export. Tested hardware remains TOPDON
TC001 Max, TopView 1.30.003 and WinUSB on Windows x64. Unknown vendor libraries
are rejected. TopView/drivers must be installed separately; no proprietary DLLs
are redistributed. Two cameras need separate USB controller paths; shared hubs
failed qualification. See the README and User Guide for setup and limitations.

Windows 10/11 x64. Unsigned development prerelease. CI installation/shortcut and
regression checks do not establish a new physical-camera qualification. Settings
and recordings are retained. Close app windows and the service before upgrading.
