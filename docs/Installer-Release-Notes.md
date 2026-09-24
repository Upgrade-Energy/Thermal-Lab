# Thermal Lab DEV18

Automatically detects a compatible TopView installation using Windows installation records and standard per-user and machine-wide locations. A stale saved path, including a path into another user's development folder, is replaced when a compatible installation is found. Camera settings now include Find TopView and validated Browse controls. Detection runs at startup and again before connecting; the Power Lab camera service uses the same detection.

TopView must still be installed separately. The tested camera library is TopView 1.30.003; unknown library versions are rejected rather than loaded with an unverified interface. No vendor libraries or camera drivers are redistributed. Close TopView and disconnect cameras in other Windows sessions before connecting.

Includes DEV17 recording, named measurements, polygons, and moving hottest/coldest trackers. Existing recordings and layouts are retained.
