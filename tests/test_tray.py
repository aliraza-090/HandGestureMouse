"""System-tray wrapper tests using a fake ``pystray`` module.

No real tray icon is created: a lightweight fake is injected into
``sys.modules`` so the wrapper's menu wiring and fallback behaviour can be
exercised deterministically.
"""

import sys
import types

from handgesturemouse.gui.tray import TrayIcon, tray_available


class FakeIcon:
    def __init__(self, name, image, title, menu):
        self.name = name
        self.image = image
        self.title = title
        self.menu = menu
        self.visible = False
        self.stopped = False
        self.updated = 0
        self.notifications = []

    def run_detached(self):
        self.visible = True

    def stop(self):
        self.stopped = True
        self.visible = False

    def update_menu(self):
        self.updated += 1

    def notify(self, message, title=None):
        self.notifications.append((message, title))


class FakeMenu:
    SEPARATOR = "---"

    def __init__(self, *items):
        self.items = list(items)


class FakeMenuItem:
    def __init__(self, text, action, **kwargs):
        self.text = text
        self.action = action


def _install_fake_pystray(monkeypatch):
    module = types.ModuleType("pystray")
    module.Icon = FakeIcon
    module.Menu = FakeMenu
    module.MenuItem = FakeMenuItem
    monkeypatch.setitem(sys.modules, "pystray", module)
    return module


def test_start_stop_and_action_dispatch(monkeypatch):
    _install_fake_pystray(monkeypatch)
    actions = []
    tray = TrayIcon("HandGestureMouse", None, on_action=actions.append, state_provider=lambda: "stopped")

    assert tray.start() is True
    assert tray.is_running is True
    assert tray._icon.visible is True

    # Menu should contain Show / Hide / Pause / Exit actions.
    texts = [item.text for item in tray._icon.menu.items if isinstance(item, FakeMenuItem)]
    assert "Show window" in texts
    assert "Hide window" in texts
    assert "Exit HandGestureMouse" in texts

    # Simulate clicking each item.
    for item in tray._icon.menu.items:
        if isinstance(item, FakeMenuItem) and not callable(item.text):
            item.action(tray._icon, item)
    assert "show" in actions and "hide" in actions and "exit" in actions

    tray.update()
    assert tray._icon.updated == 1

    tray.stop()
    assert tray.is_running is False
    assert tray._icon is None


def test_pause_label_reflects_state(monkeypatch):
    _install_fake_pystray(monkeypatch)
    state = {"v": "stopped"}
    tray = TrayIcon("t", None, on_action=lambda a: None, state_provider=lambda: state["v"])
    assert tray._pause_label(None) == "Pause tracking"
    state["v"] = "paused"
    assert tray._pause_label(None) == "Resume tracking"


def test_start_failure_is_graceful(monkeypatch):
    # Make ``import pystray`` raise by poisoning sys.modules.
    monkeypatch.setitem(sys.modules, "pystray", None)
    tray = TrayIcon("t", None, on_action=lambda a: None)
    assert tray.start() is False
    assert tray.is_running is False


def test_tray_available_returns_bool():
    assert isinstance(tray_available(), bool)


def test_update_and_stop_without_start_are_safe():
    tray = TrayIcon("t", None, on_action=lambda a: None)
    tray.update()  # no icon yet -> no-op
    tray.stop()  # no icon -> no-op
    assert tray.is_running is False


def test_notify_forwards_to_icon(monkeypatch):
    _install_fake_pystray(monkeypatch)
    tray = TrayIcon("HandGestureMouse", None, on_action=lambda a: None)

    assert tray.notify("hello") is False  # no icon yet

    tray.start()
    assert tray.notify("hello") is True
    assert tray._icon.notifications[-1][0] == "hello"


def test_notify_without_backend_support_is_safe(monkeypatch):
    _install_fake_pystray(monkeypatch)
    tray = TrayIcon("t", None, on_action=lambda a: None)
    tray.start()
    tray._icon = object()  # backend without a notify() method
    assert tray.notify("x") is False
