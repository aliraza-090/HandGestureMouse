"""Persistent, validated application settings.

Settings are stored as JSON in the user-writable ``%APPDATA%`` directory so
the application works offline and does not require write access to its own
install folder.
"""

import json
import os
from threading import Lock
from typing import Dict, Optional

from ..utils import paths
from .defaults import DEFAULTS, coerce_all, validate


class SettingsError(Exception):
    """Raised when settings cannot be loaded or saved."""


class SettingsManager:
    """Load / save / validate application settings."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or paths.settings_file()
        self._lock = Lock()
        self._data: Dict[str, object] = dict(DEFAULTS)
        self.load()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> Dict[str, object]:
        """Load settings from disk, falling back to defaults on any error."""
        with self._lock:
            data: Dict[str, object] = dict(DEFAULTS)
            if os.path.isfile(self._path):
                try:
                    with open(self._path, "r", encoding="utf-8") as fh:
                        stored = json.load(fh)
                    if isinstance(stored, dict):
                        data.update(coerce_all(stored))
                    else:
                        raise SettingsError("settings file is not a JSON object")
                except (OSError, ValueError, SettingsError):
                    # Corrupt settings must never prevent the app from starting.
                    data = dict(DEFAULTS)
            self._data = data
            return dict(self._data)

    def save(self) -> None:
        """Persist the current settings to disk (atomic write)."""
        with self._lock:
            tmp_path = self._path + ".tmp"
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2, sort_keys=True)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, self._path)
            except OSError as exc:
                raise SettingsError(f"could not save settings: {exc}") from exc

    def get(self, key: str) -> object:
        with self._lock:
            if key not in self._data:
                raise KeyError(f"unknown setting: {key}")
            return self._data[key]

    def set(self, key: str, value: object) -> None:
        """Validate and store a single setting (``validate`` errors raise)."""
        ok, normalized, message = validate(key, value)
        if not ok:
            raise ValueError(f"invalid setting {key!r}: {message}")
        with self._lock:
            self._data[key] = normalized

    def update(self, values: Dict[str, object]) -> None:
        """Validate and store several settings at once."""
        errors = []
        normalized: Dict[str, object] = {}
        for key, value in values.items():
            ok, clean, message = validate(key, value)
            if not ok:
                errors.append((key, message))
            else:
                normalized[key] = clean
        if errors:
            details = "; ".join(f"{k}: {m}" for k, m in errors)
            raise ValueError(f"invalid settings: {details}")
        with self._lock:
            self._data.update(normalized)

    def as_dict(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._data)

    def reset(self) -> None:
        """Restore all defaults and persist them."""
        with self._lock:
            self._data = dict(DEFAULTS)
        self.save()

    def validate_value(self, key: str, value: object):
        """Return ``(ok, normalized, message)`` without storing anything."""
        return validate(key, value)