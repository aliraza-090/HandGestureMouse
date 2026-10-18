"""Auto-start registry helper tests using a fake ``winreg`` module."""

import sys

from handgesturemouse.utils.autostart import RUN_KEY, AutostartManager


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.store = {}
        self.fail_create = False

    def OpenKey(self, root, sub, reserved, access):
        key = (root, sub)
        if key not in self.store:
            raise FileNotFoundError(sub)
        return key

    def CreateKey(self, root, sub):
        if self.fail_create:
            raise OSError("access denied")
        self.store.setdefault((root, sub), {})
        return (root, sub)

    def SetValueEx(self, key, name, reserved, kind, value):
        self.store[key][name] = (value, kind)

    def QueryValueEx(self, key, name):
        data = self.store[key]
        if name not in data:
            raise FileNotFoundError(name)
        return data[name]

    def DeleteValue(self, key, name):
        data = self.store.get(key)
        if data is None or name not in data:
            raise FileNotFoundError(name)
        del data[name]

    def CloseKey(self, key):
        pass


def test_enable_disable_and_query():
    fake = FakeWinreg()
    manager = AutostartManager(app_name="Hgm", winreg_module=fake)
    assert manager.is_supported() is True
    assert manager.is_enabled() is False

    assert manager.enable() is True
    assert manager.is_enabled() is True
    value, kind = fake.store[("HKCU", RUN_KEY)]["Hgm"]
    assert kind == FakeWinreg.REG_SZ
    assert "main.py" in value

    assert manager.disable() is True
    assert manager.is_enabled() is False
    assert "Hgm" not in fake.store[("HKCU", RUN_KEY)]


def test_disable_when_absent_is_success():
    fake = FakeWinreg()
    manager = AutostartManager(app_name="Hgm", winreg_module=fake)
    assert manager.disable() is True


def test_set_enabled_round_trip():
    fake = FakeWinreg()
    manager = AutostartManager(app_name="Hgm", winreg_module=fake)
    assert manager.set_enabled(True) is True
    assert manager.is_enabled() is True
    assert manager.set_enabled(False) is True
    assert manager.is_enabled() is False


def test_restricted_registry_returns_false():
    fake = FakeWinreg()
    fake.fail_create = True
    manager = AutostartManager(app_name="Hgm", winreg_module=fake)
    assert manager.enable() is False  # must not raise


def test_build_command_frozen_uses_executable(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    manager = AutostartManager(app_name="Hgm", winreg_module=FakeWinreg())
    assert manager.build_command() == f'"{sys.executable}"'


def test_build_command_source_runs_main(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    manager = AutostartManager(app_name="Hgm", winreg_module=FakeWinreg())
    command = manager.build_command()
    assert command.endswith('"') and "main.py" in command


def test_unsupported_without_registry_module():
    manager = AutostartManager(app_name="Hgm", winreg_module=None)
    # Force the "no registry" branch regardless of host platform.
    manager._winreg = None
    assert manager.is_supported() is False
    assert manager.enable() is False
    assert manager.disable() is False
