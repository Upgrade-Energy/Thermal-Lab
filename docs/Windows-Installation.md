# Windows installation and updates

Download `Thermal-Lab-Setup-0.1.0-dev19.exe` from the
[GitHub releases page](https://github.com/Upgrade-Energy/Thermal-Lab/releases).
Windows 10/11 x64; per-user installation; Python, Tcl/Tk and desktop dependencies
included. The unsigned installer creates Desktop and Start menu shortcuts.
Close the app and its background service before installation.

Install compatible TOPDON TopView and its camera driver separately. Tested:
TC001 Max with TopView 1.30.003 and WinUSB. Vendor DLLs/drivers are not bundled.
DEV18+ discovers compatible TopView installations and recovers stale paths;
Camera settings offers Find TopView and Browse. Close TopView and camera owners
in other signed-in sessions. See [user guide](User-Guide.md) for USB limitations.

## Updates

Choose **Workspace → Check for updates** or the Start menu shortcut. Public
releases require no GitHub token. Leave **Include development releases** selected
for DEV builds, review the notes and download. Downloads are checked against
GitHub's size and SHA-256 digest. Finish recordings, close app windows and the
service, then choose Install update. Reopen from the shortcut after setup.

The updater checks only this repository, over outbound HTTPS. It sends no
recordings or measurements. Offline operation remains available. Source-only
commits are not updates. If an older installation has invalid saved GitHub access,
use Forget saved access or download the public installer manually. Forgetting
shared saved access also affects the Power Lab updater.

## Retained data

Program versions are staged under `%LOCALAPPDATA%\Programs\UpgradeEnergy\ThermalLab\versions`.
Setup verifies the staged runtime and manifest before changing `current.txt`.
Previous program versions are retained. Settings remain in `%USERPROFILE%\.thermal-lab`;
recordings remain in `%USERPROFILE%\Thermal-Lab-Recordings` or the chosen folder.
Reinstall/uninstall preserves these folders. Preserve original archives and backups.
A previous installer can restore an older program, but cannot reverse data-schema changes.

## Release process

Increment release.json, pyproject.toml and thermal_lab/__init__.py; update release
notes. The Windows installers workflow tests, builds pinned dependencies, verifies
installation/shortcuts/busy-update/reinstall/data preservation on Windows, then
publishes a new EXE and checksum. Existing assets are not overwritten. Hosted
Windows checks are not a new physical-camera test.
