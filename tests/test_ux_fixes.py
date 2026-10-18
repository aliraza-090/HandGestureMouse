"""Regression tests for the UX fixes: always-on control, robust camera loop,
and on-frame gesture feedback.

These tests never touch a real camera or move the real mouse.
"""

import queue
import threading
from types import SimpleNamespace

import numpy as np

from handgesturemouse.app import Application
from handgesturemouse.camera.camera_manager import CameraManager
from handgesturemouse.config.settings_manager import SettingsManager
from handgesturemouse.core.gesture_controller import GestureController
from handgesturemouse.core.mouse_controller import MouseController
from handgesturemouse.core.pipeline import PipelineWorker


class FakeCap:
    def __init__(self, index=0, opened=True, frames=None):
        self.index = index
        self._opened = opened
        self._frames = list(frames or [])
        self._released = False

    def isOpened(self):
        return self._opened and not self._released

    def read(self):
        if self._frames:
            return True, self._frames.pop(0)
        return False, None

    def set(self, prop, value):
        pass

    def release(self):
        self._released = True


class FakeCamera:
    def __init__(self):
        self._open = False

    def open(self, index):
        self._open = True

    def is_open(self):
        return self._open

    def read(self):
        return None

    def set_open_dimensions(self, w, h):
        pass

    def release(self):
        self._open = False


class FakeTracker:
    def set_config(self, **kwargs):
        pass

    def open(self):
        pass

    def close(self):
        pass

    def is_open(self):
        return True

    def detect(self, frame):
        return SimpleNamespace(landmarks=None, error="", num_hands=0, handedness="", score=0.0)

    def annotate(self, frame, landmarks):
        return frame


def _make_worker(fake_pyautogui):
    settings = SettingsManager()
    mouse = MouseController(pyautogui=fake_pyautogui)
    events = queue.Queue(maxsize=64)
    worker = PipelineWorker(
        camera=FakeCamera(),
        tracker=FakeTracker(),
        mouse=mouse,
        gesture=GestureController(settings.as_dict()),
        settings_provider=settings,
        event_queue=events,
        stop_event=threading.Event(),
    )
    return worker


# -- Feature A: control is active without a manual toggle --------------------


class FakePipeline:
    def __init__(self, alive=True):
        self.alive = alive
        self.started = 0
        self.stopped = 0

    def is_alive(self):
        return self.alive

    def start_service(self):
        self.started += 1

    def stop_service(self):
        self.stopped += 1


def test_start_control_immediately_enters_active_state():
    app = Application.__new__(Application)
    app.pipeline = FakePipeline(alive=True)
    app.window = None
    app._tray = None
    app._ui_state = "stopped"

    app.start_control()

    assert app._ui_state == "running"
    assert app.pipeline.started == 1


class _FakeSettings:
    def __init__(self, **values):
        self._values = values

    def get(self, key):
        return self._values.get(key)


class _FakeTray:
    def __init__(self):
        self.messages = []

    def notify(self, message, title=None):
        self.messages.append((message, title))
        return True


def test_notify_tray_active_mentions_hotkey():
    tray = _FakeTray()
    app = SimpleNamespace(
        _tray=tray,
        settings=_FakeSettings(show_tray_notifications=True, emergency_hotkey="ctrl+alt+e"),
    )
    Application._notify_tray_active(app)

    assert tray.messages
    message = tray.messages[0][0]
    assert "system tray" in message
    assert "CTRL+ALT+E" in message


def test_notify_tray_active_respects_toggle_and_missing_tray():
    tray = _FakeTray()
    app = SimpleNamespace(
        _tray=tray,
        settings=_FakeSettings(show_tray_notifications=False, emergency_hotkey="ctrl+alt+e"),
    )
    Application._notify_tray_active(app)
    assert tray.messages == []

    # A missing tray must never raise.
    Application._notify_tray_active(
        SimpleNamespace(
            _tray=None,
            settings=_FakeSettings(show_tray_notifications=True, emergency_hotkey="ctrl+alt+e"),
        )
    )


# -- Feature B: robust camera loop -------------------------------------------


def test_open_same_index_does_not_reopen_capture():
    created = []

    def backend(index):
        cap = FakeCap(index=index, opened=True)
        created.append(cap)
        return cap

    manager = CameraManager(backend=backend)
    manager.open(0)
    manager.open(0)  # already streaming this camera -> must not reopen
    assert len(created) == 1

    manager.open(1)  # a different camera is a legitimate reopen
    assert len(created) == 2


def test_camera_loss_tolerates_a_few_delayed_frames(fake_pyautogui):
    worker = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True

    assert worker._grab_frame() is None  # miss 1
    assert worker._grab_frame() is None  # miss 2
    assert worker._backoff.active is False  # tolerated, no reconnect storm

    assert worker._grab_frame() is None  # miss 3 -> threshold reached
    assert worker._backoff.active is True


def test_first_missed_frame_releases_buttons(fake_pyautogui):
    worker = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    worker.mouse.start_drag()
    assert "left" in worker.mouse.held_buttons

    worker._grab_frame()

    assert worker.mouse.held_buttons == set()  # zero stuck input immediately


# -- Feature C: gesture badge drawn on the frame -----------------------------


def test_draw_hud_renders_badge_without_resizing(fake_pyautogui):
    worker = _make_worker(fake_pyautogui)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    out = worker._draw_hud(frame, "move", "move", hand=True)

    assert out.shape == (240, 320, 3)
    assert out.any()  # something was actually drawn


def test_draw_hud_handles_no_hand(fake_pyautogui):
    worker = _make_worker(fake_pyautogui)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    out = worker._draw_hud(frame, "", "", hand=False)

    assert out.any()
