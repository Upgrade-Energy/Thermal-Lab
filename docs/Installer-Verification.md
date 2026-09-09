# Thermal-Lab 0.1.0-dev16: installer verification

Implemented a native NSIS Windows x64 Setup EXE, per-user shortcuts and uninstall entry, an isolated pinned Python 3.14.7 + Tcl/Tk 9 runtime, and Check for updates. Thermal Lab also bundles pinned NumPy, Pillow, OpenCV, LZ4 and FFmpeg wheels and provides a visible integration-service manager.

## Verified in this workspace

- Regression tests, release version selection and channel filtering, same-repository installer selection, draft/incomplete asset rejection, size/SHA256 checks, interrupted/corrupted download cleanup and authentication stripping on GitHub asset redirects.
- Power Lab update-launch endpoint enforces local session token and Origin and does not call stop/output controls.
- Thermal Lab service manager uses the existing local bearer-token protocol and cannot stop an owned camera session.
- Real browser check: Power Lab update entry and legacy entry render; no page errors or horizontal overflow at 1440 and 900 pixels.
- Native Tk update dialogs: available-release, no-release, offline/access-failure states; Thermal Lab service launcher. These are Linux-rendered windows with fixtures, not Windows or live GitHub release evidence.
- NSIS compilation and complete staged package checksums, required runtime modules/files and dependency hashes.

## Windows qualification

Initial Windows testing passed installation, direct application/updater launch, busy-install refusal, DPAPI credential encryption, reinstall while the updater was open, data preservation, and a real GitHub installer download. The subsequent test opening the actual Start menu shortcut exposed a launcher defect: VBScript Trim does not remove the newline from the version pointer. The initial DEV5/DEV15 installers have been withdrawn from the update feed.

The corrected DEV6/DEV16 launchers read the pointer with ReadLine. The release workflow now opens both the application and updater through their generated Windows shortcuts before publishing. See the workflow associated with the current release tag for final Windows and GitHub download evidence. Physical lab-computer, instrument and camera tests remain separate from installer qualification.

## Final result

[Release v0.1.0-dev16](https://github.com/Upgrade-Energy/Thermal-Lab/releases/tag/v0.1.0-dev16) passed the [complete Windows and GitHub verification workflow](https://github.com/Upgrade-Energy/Thermal-Lab/actions/runs/34342751756). Both actual Start menu shortcuts launched successfully. Tested release source: `840a553656fee42d371f6090f309080b03988b7b`. Published installer SHA256: `8669cf9f7521da95cbad2ad688c745faefe855ae882d737d7a8a08b73b482dd6`.
