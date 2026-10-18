"""Mouse safety tests: click-once semantics, button release, fail-safe."""

import queue
import threading
from types import SimpleNamespace

import pytest

from handgesturemouse.config.settings_manager import SettingsManager
from handgesturemouse.core.cursor_smoothing import CursorSmoother
from handgesturemouse.core.gesture_controller import GestureController, MouseCommand
from handgesturemouse.core.mouse_controller import MouseController
from handgesturemouse.core.pipeline import PipelineWorker


# -- MouseController ---------------------------------------------------------


def test_move_and_click_record_calls(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.move_to(10, 20)
    mouse.left_click(30, 40)
    mouse.right_click(50, 60)
    mouse.scroll(3)
    assert ("moveTo", 10, 20) in fake_pyautogui.calls
    assert ("click", 30, 40, "left") in fake_pyautogui.calls
    assert ("click", 50, 60, "right") in fake_pyautogui.calls
    assert any(call[0] == "scroll" for call in fake_pyautogui.calls)


def test_drag_tracks_and_releases_buttons(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.start_drag()
    assert "left" in mouse.held_buttons
    assert ("mouseDown", "left") in fake_pyautogui.calls
    mouse.start_drag()  # idempotent, must not press twice
    assert sum(1 for c in fake_pyautogui.calls if c == ("mouseDown", "left")) == 1
    mouse.drag_move(100, 100)
    mouse.end_drag()
    assert mouse.held_buttons == set()
    assert ("mouseUp", "left") in fake_pyautogui.calls


def test_end_drag_without_start_is_noop(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.end_drag()
    assert not any(call[0] == "mouseUp" for call in fake_pyautogui.calls)


def test_release_all_releases_every_button(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.start_drag("left")
    mouse.start_drag("right")
    mouse.release_all()
    assert mouse.held_buttons == set()
    assert ("mouseUp", "left") in fake_pyautogui.calls
    assert ("mouseUp", "right") in fake_pyautogui.calls


def test_fail_safe_invokes_callback_and_releases(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    events = []
    mouse.set_fail_safe_callback(events.append)
    mouse.start_drag()
    fake_pyautogui.raise_fail_safe = True
    mouse.move_to(5, 5)
    assert events, "fail-safe callback must fire"
    assert mouse.held_buttons == set()


def test_fail_safe_during_click_and_scroll(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    events = []
    mouse.set_fail_safe_callback(events.append)
    fake_pyautogui.raise_fail_safe = True
    mouse.left_click(1, 1)
    mouse.scroll(5)
    assert len(events) >= 1


# -- Pipeline integration ----------------------------------------------------


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
    def __init__(self):
        self._open = False

    def set_config(self, **kwargs):
        pass

    def open(self):
        self._open = True

    def close(self):
        self._open = False

    def is_open(self):
        return self._open

    def detect(self, frame):
        return SimpleNamespace(landmarks=None, error="", num_hands=0, handedness="", score=0.0)

    def annotate(self, frame, landmarks):
        return frame


def _make_worker(fake_pyautogui, settings_override=None):
    settings = SettingsManager()
    if settings_override:
        settings.update(settings_override)
    mouse = MouseController(pyautogui=fake_pyautogui)
    events = queue.Queue(maxsize=32)
    worker = PipelineWorker(
        camera=FakeCamera(),
        tracker=FakeTracker(),
        mouse=mouse,
        gesture=GestureController(settings.as_dict()),
        settings_provider=settings,
        event_queue=events,
        stop_event=threading.Event(),
    )
    return worker, mouse, events


def test_execute_move_and_click(fake_pyautogui):
    worker, _, _ = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="move", x=0.5, y=0.5))
    worker._execute(MouseCommand(kind="left_click", click_x=0.5, click_y=0.5))
    worker._execute(MouseCommand(kind="right_click"))
    worker._execute(MouseCommand(kind="scroll", steps=2))
    kinds = [c[0] for c in fake_pyautogui.calls]
    assert "moveTo" in kinds
    assert "click" in kinds
    assert "scroll" in kinds


def test_execute_drag_start_and_end(fake_pyautogui):
    worker, mouse, _ = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="drag_start"))
    assert "left" in mouse.held_buttons
    worker._execute(MouseCommand(kind="drag_move", x=0.6, y=0.6))
    worker._execute(MouseCommand(kind="drag_end"))
    assert mouse.held_buttons == set()


def test_disabled_gesture_is_not_executed(fake_pyautogui):
    worker, mouse, _ = _make_worker(fake_pyautogui, {"use_gesture_drag": False})
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="drag_start"))
    assert mouse.held_buttons == set()


def test_stop_service_releases_held_buttons(fake_pyautogui):
    worker, mouse, _ = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="drag_start"))
    assert "left" in mouse.held_buttons
    worker.stop_service()
    assert mouse.held_buttons == set()
    assert worker.mouse_enabled is False


def test_pipeline_fail_safe_posts_emergency(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    mouse.start_drag()
    fake_pyautogui.raise_fail_safe = True
    worker._execute(MouseCommand(kind="move", x=0.5, y=0.5))

    kinds = []
    while not events.empty():
        kinds.append(events.get_nowait().kind)
    assert "emergency" in kinds
    assert worker.mouse_enabled is False
    assert mouse.held_buttons == set()


def test_pause_service_releases_held_buttons(fake_pyautogui):
    worker, mouse, _ = _make_worker(fake_pyautogui)
    worker.start_service()
    worker._execute(MouseCommand(kind="drag_start"))
    assert "left" in mouse.held_buttons
    worker.pause_service()
    assert mouse.held_buttons == set()
    assert worker.mouse_enabled is False


def test_emergency_stop_releases_and_reports_stopped(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    worker.start_service()
    worker._execute(MouseCommand(kind="drag_start"))
    worker.emergency_stop()
    assert mouse.held_buttons == set()
    assert worker.mouse_enabled is False
    states = []
    while not events.empty():
        event = events.get_nowait()
        if event.kind == "state":
            states.append(event.payload.get("state"))
    assert states[-1] == "stopped"


def test_pipeline_run_releases_camera_and_buttons_on_stop(fake_pyautogui):
    worker, mouse, _ = _make_worker(fake_pyautogui)
    released = {"camera": False}
    closed = {"tracker": False}

    def record_release():
        released["camera"] = True

    def record_close():
        closed["tracker"] = True

    worker.camera.release = record_release
    worker.tracker.close = record_close

    # Hold a button so we can prove it is released on shutdown.
    mouse.start_drag()
    assert "left" in mouse.held_buttons

    # Pre-set the stop flag: run() should skip the loop and run cleanup only.
    worker._stop.set()
    worker.run()

    assert released["camera"] is True
    assert closed["tracker"] is True
    assert mouse.held_buttons == set()


def test_pipeline_run_cleans_up_when_tracker_startup_fails(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    released = {"camera": False}
    closed = {"tracker": False}
    worker.camera.release = lambda: released.__setitem__("camera", True)
    worker.tracker.close = lambda: closed.__setitem__("tracker", True)

    def boom():
        raise RuntimeError("model missing")

    # Simulate a tracker that fails to initialise after the camera opened.
    worker.tracker.open = boom
    mouse.start_drag()
    assert "left" in mouse.held_buttons

    worker.run()  # must not raise; must clean up the opened camera

    assert released["camera"] is True
    assert closed["tracker"] is True
    assert mouse.held_buttons == set()
    assert worker.mouse_enabled is False

    states = []
    while not events.empty():
        event = events.get_nowait()
        if event.kind == "state":
            states.append(event.payload.get("state"))
    assert states and states[-1] == "stopped"


def test_repeated_stop_is_safe(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    worker.start_service()
    worker._execute(MouseCommand(kind="drag_start"))
    assert "left" in mouse.held_buttons
    worker.stop_service()
    worker.stop_service()  # must be idempotent, not raise
    assert mouse.held_buttons == set()
    assert worker.mouse_enabled is False
    states = []
    while not events.empty():
        event = events.get_nowait()
        if event.kind == "state":
            states.append(event.payload.get("state"))
    assert states and states[-1] == "stopped"


def test_execute_swallows_mouse_errors_and_reports(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True

    def boom(*args, **kwargs):
        raise RuntimeError("input blocked by OS")

    mouse.move_to = boom
    worker._execute(MouseCommand(kind="move", x=0.5, y=0.5))  # must not raise

    kinds = []
    while not events.empty():
        kinds.append(events.get_nowait().kind)
    assert "error" in kinds


def test_grab_frame_returns_none_when_camera_closed(fake_pyautogui):
    worker, _, _ = _make_worker(fake_pyautogui)
    # FakeCamera starts closed; read() returns None and must not raise.
    assert worker._grab_frame() is None
