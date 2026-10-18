"""Packaging / distribution consistency tests.

These verify that the shipped resources exist and that the PyInstaller spec and
Inno Setup script keep pointing at the real layout. They need no hardware.
"""

import os

from handgesturemouse.utils import paths

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel_path):
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
        return fh.read()


def test_resources_ship_model_and_icons():
    assert paths.model_path() is not None
    assert os.path.isfile(paths.model_path())
    assert paths.icon_path() is not None
    assert paths.native_icon_path() is not None


def test_pyinstaller_spec_bundles_resources_and_pystray_backend():
    spec = _read(os.path.join("packaging", "HandGestureMouse.spec"))
    assert "resources/models" in spec
    assert "resources/icons" in spec
    assert 'collect_submodules("pystray")' in spec
    assert '"pystray._win32"' in spec
    assert "mediapipe" in spec


def test_installer_targets_pyinstaller_output_and_startmenu():
    iss = _read(os.path.join("packaging", "installer.iss"))
    # Installs the whole folder build produced by the spec.
    assert r"..\dist\HandGestureMouse\*" in iss
    # Deterministic output path used by the release process.
    assert "OutputDir=Output" in iss
    assert "OutputBaseFilename=HandGestureMouse-Setup" in iss
    # Start Menu shortcut for the application.
    assert r"{group}\{#MyAppName}" in iss


def test_installer_keeps_user_data_on_uninstall():
    iss = _read(os.path.join("packaging", "installer.iss"))
    section = iss.split("[UninstallDelete]", 1)[1]
    active = [
        line.strip()
        for line in section.splitlines()
        if line.strip() and not line.strip().startswith(";") and line.strip().startswith("Type:")
    ]
    assert active == [], "uninstall should not delete user settings/logs"
