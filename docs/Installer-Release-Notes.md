# Thermal Lab 0.1.0-dev17

Track the hottest point, coldest point, or both, even when their locations change. In **Measure → Track a moving extreme**, choose **Whole image** or **Selected region**, then add the desired trackers. Rename them like other points. **Record session / Stop recording** saves temperatures and original thermal pixel positions for every accepted frame.

Recording review replays each tracker at its recorded position and graphs its temperature. CSV includes temperature, tracking rule and moving coordinates. Older recordings can also be measured with new trackers using **Layout → Analysis**, without modifying their original files. PNG and MP4 measurement labels follow the tracked positions.

Also includes the existing local desktop improvements: softer styling and grouped tools, hot/cold overview markers, camera names, clear-all-points control, polygon regions, recording timer, and automatic per-frame measurement CSV.


- Standalone Windows 10/11 x64 installer with bundled Python, Tcl/Tk and required desktop dependencies.
- Desktop and Start menu shortcuts, plus Check for updates.
- Updates select only this application's published GitHub release installer; development releases are optional.
- Private GitHub access uses a read-only Contents token encrypted for the current Windows user, or existing GitHub CLI access.
- Downloads are size- and SHA256-verified. Installers refuse to replace a running app or service.
- New versions are staged and verified before switching shortcuts; settings and recordings remain in place.
- Thermal Lab additionally includes a visible Power Lab service launcher and recording-review shortcut.

Preserves full 256 × 192 numerical thermal frames and optional lossless 1024 × 768 optical recordings. The tracker follows the extreme pixel in its search area; it does not identify or follow one physical object. TOPDON TopView must already be installed; choose its folder. Enable development releases in **Workspace → Check for updates** to receive DEV17.

The installers are currently unsigned. Windows may display an unknown-publisher prompt.
