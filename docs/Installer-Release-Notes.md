# Thermal Lab 0.1.0-dev15

- Standalone Windows 10/11 x64 installer with bundled Python, Tcl/Tk and required desktop dependencies.
- Desktop and Start menu shortcuts, plus Check for updates.
- Updates select only this application's published GitHub release installer; development releases are optional.
- Private GitHub access uses a read-only Contents token encrypted for the current Windows user, or existing GitHub CLI access.
- Downloads are size- and SHA256-verified. Installers refuse to replace a running app or service.
- New versions are staged and verified before switching shortcuts; settings and recordings remain in place.
- Thermal Lab additionally includes a visible Power Lab service launcher and recording-review shortcut.

Includes Thermal Lab DEV14 camera, recording, review and alignment functionality. TOPDON TopView must already be installed; choose its folder. Native camera hardware was not requalified by installer tests.

The installers are currently unsigned. Windows may display an unknown-publisher prompt.
