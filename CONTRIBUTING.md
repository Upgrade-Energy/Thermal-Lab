# Contributing and reporting bugs

Search [existing issues](https://github.com/Upgrade-Energy/Thermal-Lab/issues)
then use the bug report or feature request form. Include version, Windows build,
exact camera model, TopView version, USB ports/hubs/controllers, reproducible steps,
expected and actual behavior, and a minimal sanitized log or screenshot.

Do not attach GitHub tokens, vendor DLLs, private recordings, customer data or
full user-profile folders. The app's Report a bug command only opens the form;
you review and submit it yourself. No automatic crash upload is enabled.

For code changes, open a focused pull request and run
`python -m unittest discover -s tests -v` after installing `.[desktop]`.
Preserve numerical thermal data and original recordings. Camera ABI, USB-driver,
temperature-conversion and calibration changes need explicit hardware evidence;
a passing simulator or hosted runner is insufficient. Document tested models,
versions and remaining limitations. Contributions are under the repository MIT
license; retain third-party notices and do not contribute proprietary vendor binaries.
