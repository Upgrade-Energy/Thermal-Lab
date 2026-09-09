# Thermal-Lab 0.1.0-dev15: installer verification

Implemented a native NSIS Windows x64 Setup EXE, per-user shortcuts and uninstall entry, an isolated pinned Python 3.14.7 + Tcl/Tk 9 runtime, and Check for updates. Thermal Lab also bundles pinned NumPy, Pillow, OpenCV, LZ4 and FFmpeg wheels and provides a visible integration-service manager.

## Verified in this workspace

- Regression tests, release version selection and channel filtering, same-repository installer selection, draft/incomplete asset rejection, size/SHA256 checks, interrupted/corrupted download cleanup and authentication stripping on GitHub asset redirects.
- Power Lab update-launch endpoint enforces local session token and Origin and does not call stop/output controls.
- Thermal Lab service manager uses the existing local bearer-token protocol and cannot stop an owned camera session.
- Real browser check: Power Lab update entry and legacy entry render; no page errors or horizontal overflow at 1440 and 900 pixels.
- Native Tk update dialogs: available-release, no-release, offline/access-failure states; Thermal Lab service launcher. These are Linux-rendered windows with fixtures, not Windows or live GitHub release evidence.
- NSIS compilation and complete staged package checksums, required runtime modules/files and dependency hashes.

## Not yet verified

Windows execution of the Setup EXE, bundled application and updater; Windows DPAPI storage and named-mutex behavior; real GitHub asset download and installation. A prepared Windows workflow covers initial install, application launch, blocking install while active, independent updater launch, reinstall, shortcuts and user-data preservation.

GitHub source publication was rejected by automatic approval review because it requires explicit upload authorization. No remote source, branch, workflow or release was created in this turn. Accordingly the release workflow has not run and there is no new hosted release yet. Do not describe this local package as Windows-qualified or live-update-qualified.

The source changes and workflow are ready locally for publication after that authorization. Physical camera and electrical bench verification remain separate from installer qualification. No camera capture, output enable, driver installation or physical power test occurred here.
