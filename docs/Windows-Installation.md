# Thermal Lab: installation and updates

Run `Thermal-Lab-Setup-0.1.0-dev15.exe` on Windows 10/11 x64. No separate Python installation is needed. The installer works for the current Windows user and creates Desktop and Start menu shortcuts. Choose Finish, then open Thermal Lab.

Thermal Lab also has Start menu shortcuts for **Power Lab service** and **Review recordings**. Install TOPDON TopView and its drivers separately; our installer does not redistribute proprietary camera DLLs. In Thermal Lab, select its TopView folder. To let Power Lab use the cameras, disconnect them from Thermal Lab live inspection, open **Power Lab service**, and choose **Start service**. Power Lab's Thermal Lab link uses this local service for selected-camera measurements and grouped recording start/stop. Closing the service window leaves it running; use **Stop service** after disconnecting Power Lab's camera group to stop it.

## Check for updates

1. Select **Check for updates** in the app or Start menu.
2. For these private repositories, select **Connect GitHub** once. Create a fine-grained GitHub token for Upgrade-Energy, selecting Power-Lab and Thermal-Lab, with **Contents: Read-only**. Your organization may require token approval. Paste it only into the local update dialog. A GitHub CLI login is also detected. No GitHub token is bundled in either installer.
3. Leave **Include development releases** selected while using DEV builds. Uncheck it for stable releases only.
4. Review the version and notes, then choose **Download update**. The app can continue operating while downloading.
5. Stop tests/recordings, close every window of the app being updated and its background service, then choose **Install update** in the separate update window. Open the app again from its shortcut after setup finishes. Updating never resumes a test or turns output on.

Each app checks only its own repository. Downloads and release checks use outbound HTTPS. Application control services stay on loopback; no firewall port or public website is required. Offline operation remains available. Update checks send no recordings, camera information or measurements.

## Data and recovery

Program versions are staged in `%LOCALAPPDATA%\Programs\UpgradeEnergy\ThermalLab\versions`. The installer validates runtime imports and its complete file manifest before atomically switching `current.txt`. Previous version folders are retained. An interrupted download does not replace the installed app. A failed stage does not change the selected version. If a newly installed version has a later behavioral regression, close the app/service and use a previously saved installer; this does not reverse data-schema changes.

Power Lab data remains in `%LOCALAPPDATA%\UpgradeEnergy\PowerLab`. Thermal Lab camera workspaces remain under `%USERPROFILE%\.thermal-lab`; recordings stay in `%USERPROFILE%\Thermal-Lab-Recordings` or your chosen recording folder. Existing folders are retained, including uninstall. Saved GitHub access is shared by both updaters and encrypted using Windows DPAPI; **Forget saved access** removes that saved credential for both tools.

For old portable builds, finish work and close them before running setup. Use the new shortcut afterwards. Keep your existing portable folder until the new installation has been checked. No setup requires the PC to be reachable from the internet.

## Publishing subsequent updates

Increment `release.json` and the app version, update `docs/Installer-Release-Notes.md`, and commit the fixes. The Windows installers workflow builds pinned Python/Tcl/Tk and wheel inputs, runs regression tests, then installs and opens the package on a Windows runner. It verifies blocked installation while the app is open, an independent update window, reinstall and data preservation. Only passing builds are published to GitHub Releases. Existing version assets are never replaced. The updater ignores source-only commits and releases with missing installer assets or GitHub SHA256 digests.

Includes Thermal Lab DEV14 camera, recording, review and alignment functionality. TOPDON TopView must already be installed; choose its folder. Native camera hardware was not requalified by installer tests.
