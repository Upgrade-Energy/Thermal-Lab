# Thermal Lab user guide

This public guide incorporates the relevant operating instructions from the
internal Confluence “Thermal Lab — Windows Usage and Camera Alignment Guide
(DEV16)”, version 3 (9 September 2026), reconciled with DEV18 source and setup
verification on 1 November 2026. Confluence's DEV16 download/private-access
instructions and its statement that automatic TopView detection is only proposed
are superseded. This guide is usable without Confluence access.

## Setup and updates

Follow [Windows installation](Windows-Installation.md) and the [README](../README.md).
Tested camera: **TOPDON TC001 Max**, Windows x64, **TopView 1.30.003**, WinUSB.
TopView must be installed separately; its DLLs and drivers are not bundled.
Close TopView before connecting, including in other Windows sessions.
Use Find TopView or Browse in Camera settings if detection cannot find a compatible
installation. Unsupported library versions are rejected; do not disable validation.

## Align a subject

Keep the camera and target still. Select **Align selected area…**, draw a rectangle
on the left thermal image, choose **Preview auto-alignment**, inspect the candidate,
and choose **Apply to live**. Preview alone does not change live alignment.
No checkerboard or distance entry is required. This fits a frozen pair and does
not continuously track the subject. Refit after distance or mounting changes.
Other objects at different distances may remain offset.

If automatic alignment is ambiguous, use **Match shared points**: identify 3–8
corresponding features, spread across the target, on the thermal and raw optical
images. Preview the point fit and inspect before applying. Nearly collinear or
inconsistent points are rejected. RMS residual measures agreement at your clicks,
not independently verified accuracy across the subject. Paired target boxes are
an alternative rough guide. Unlock alignment before applying if necessary.

Save a named target profile after inspection. Profiles belong to a camera identity.
Distance prediction requires at least two known-distance profiles and only
interpolates within their range; it does not measure distance.

## Measurements and recording

Add and name points, rectangles or polygons. Hot/cold trackers follow the extreme
pixel in the chosen image/region, not a specific object. See [Tracking guide](Tracking-Guide.md).
Palette and optical opacity change display only. Alignment moves the optical
layer, not measurement coordinates or the numerical thermal grid.

Choose **Record session**, then **Stop recording** and wait for **COMPLETE**.
FAILED or unfinished RECORDING sessions are incomplete. Default recordings are
under `%USERPROFILE%\Thermal-Lab-Recordings`. Optional lossless optical archives
retain 1024×768 YUYV data; thermal frames retain 256×192 numerical values.
Plan for about 2.4 GB/minute/camera of uncompressed optical data at 25 fps plus
thermal data; compression savings vary with the scene.

**Review recordings** supports playback, frame stepping, temperature histories,
CSV export, PNG snapshots and MP4. Keep original archives: MP4 is a rendered,
lossy presentation export. Absolute temperature accuracy and environmental or
emissivity corrections are not qualified.

## Multiple cameras and optional integration

Use **Open another camera window** for the second camera; verify each camera's
identity, layout and recording state. Use separate USB controller paths. Shared
hub tests failed; a new hub alone does not establish adequate bandwidth.
Concurrent recording does not synchronize physical exposures. Changing USB ports
can change Windows location-based identity; verify the selected layout afterward.

Power Lab is optional. Save per-camera layouts, disconnect live inspection, close
TopView, start the Thermal Lab Power Lab service, then select cameras through the
client. Stop and finalize recordings before disconnecting. Closing the service
manager window does not stop the service; use **Stop service**. See the versioned
[local integration guide](Power-Lab-Integration.md). Historical simulated electrical
runs or proposed three-camera support are not physical qualification evidence.

## Troubleshooting and reports

| Problem | Check |
| --- | --- |
| Camera missing or cannot connect | Check WinUSB/TopView installation, compatible DLL, cable, camera owner and other signed-in sessions. Refresh while disconnected. |
| TopView path belongs to another account | DEV18+ searches registry and standard folders; use Find TopView/Browse for a valid accessible installation. |
| Unsupported camera library | Retain the tested TopView 1.30.003 installation; newer versions need qualification. |
| Second camera fails or stream stops | Use separate USB controller paths and review shared-hub evidence. Reconnect; interrupted archives remain incomplete. |
| Preview matches but live view does not | Apply to live, check alignment lock and refresh the pair. |
| One distance aligns but another does not | Refit the subject or inspect a profile for that distance. |

Report repeatable problems through Workspace → Report a bug or GitHub Issues.
Remove tokens, private recordings, personal paths and customer data from attachments.
