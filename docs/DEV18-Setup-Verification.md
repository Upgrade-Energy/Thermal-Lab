# DEV18 TopView discovery verification

Fixed failure to open the vendor library when a saved configuration points into a different Windows user's development folder. Windows uninstall registry entries (HKCU/HKLM, both registry views) and standard installation folders are searched. Valid custom paths remain supported. Libraries must match the existing ABI qualification digest; unknown versions are not loaded.

On 24 September 2026, an isolated Windows test profile was seeded with a nonexistent other-user TopView path. The updated desktop automatically selected C:/Program Files/TOPDON/TopView, persisted that correction and displayed real TC001 Max thermal and optical frames at original 256x192 and 1024x768 resolutions. No vendor DLLs were copied or bundled. No power instruments were accessed.

142 regression tests passed with the installed Python 3.14 Windows runtime, including new-user discovery, stale and inaccessible paths, unsupported library rejection, custom folders, saved correction, busy-camera protection and native desktop tests. This simulates a fresh/stale user configuration; it does not claim a login test under Trevor's actual account.
