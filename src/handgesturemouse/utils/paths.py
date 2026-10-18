"""Filesystem paths: user data directory, resources, logs.

The application must work both as a source checkout and as a PyInstaller
bundle.  User configuration and logs always live under ``%APPDATA%`` so a
portable build remains write-safe and the app keeps working offline.
"""

import os
import sys
from typing import Optional

_APP_NAME = "HandGestureMouse"


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_base() -> str:
    """Directory that contains bundled resources at runtime."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    # source layout: <project>/src/handgesturemouse
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resources_dir() -> str:
    """Absolute path of the bundled ``resources`` directory."""
    return os.path.join(bundle_base(), "resources")


def model_path() -> Optional[str]:
    """Path of the MediaPipe hand landmarker model, or None when absent."""
    candidate = os.path.join(resources_dir(), "models", "hand_landmarker.task")
    return candidate if os.path.isfile(candidate) else None


def icon_path() -> Optional[str]:
    """Path of the application icon, or None when absent."""
    for name in ("app.ico", "app.png"):
        candidate = os.path.join(resources_dir(), "icons", name)
        if os.path.isfile(candidate):
            return candidate
    return None


def native_icon_path() -> Optional[str]:
    """Windows-native icon (``.ico``) or None."""
    candidate = os.path.join(resources_dir(), "icons", "app.ico")
    return candidate if os.path.isfile(candidate) else None


def user_data_dir() -> str:
    """User-writable directory for settings and logs (``%APPDATA%``)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, _APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def settings_file() -> str:
    """Path of the JSON settings file."""
    return os.path.join(user_data_dir(), "settings.json")


def log_dir() -> str:
    """User-writable directory for log files."""
    path = os.path.join(user_data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path