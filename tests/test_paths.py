"""Resource path resolution in normal and frozen (PyInstaller) execution."""

import os
import sys

from handgesturemouse.utils import paths


def test_source_bundle_base_points_at_package():
    assert paths.is_frozen() is False
    base = paths.bundle_base()
    assert os.path.isdir(base)
    assert os.path.basename(base) == "handgesturemouse"
    assert os.path.basename(paths.resources_dir()) == "resources"


def test_resources_and_model_paths_are_consistent():
    res = paths.resources_dir()
    model = paths.model_path()
    if model is not None:
        assert os.path.isfile(model)
        assert os.path.dirname(os.path.dirname(model)) == res
    icon = paths.icon_path()
    if icon is not None:
        assert os.path.isfile(icon)


def test_frozen_bundle_uses_meipass(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", r"C:\frozen\app", raising=False)
    assert paths.is_frozen() is True
    assert paths.bundle_base() == r"C:\frozen\app"
    assert paths.resources_dir() == os.path.join(r"C:\frozen\app", "resources")
    assert paths.model_path() is None  # nothing there on this machine


def test_user_dirs_are_writable(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data_dir = paths.user_data_dir()
    assert os.path.isdir(data_dir)
    assert data_dir.startswith(str(tmp_path))
    # settings file path lives inside the user data directory
    assert os.path.dirname(paths.settings_file()) == data_dir
    assert os.path.isdir(paths.log_dir())
