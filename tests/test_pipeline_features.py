"""Pipeline feature tests: audio feedback, calibration feed, reconnect."""

import queue
import threading
from types import SimpleNamespace

from handgesturemouse.config.settings_manager import SettingsManager
from handgesturemouse.core.gesture_controller import GestureController, MouseCommand
from handgesturemouse.core.mouse_controller import MouseController
from handgesturemouse.core.pipeline import PipelineWorker


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
    def __init__(self, result=None):
        self._open = False
        self.result = result or SimpleNamespace(landmarks=None, error="", num_hands=0, handedness="", score=0.0)

    def set_config(self, **kwargs):
        pass

    def open(self):
        self._open = True

    def close(self):
        self._open = False

    def is_open(self):
        return self._open

    def detect(self, frame):
        return self.result

    def annotate(self, frame, landmarks):
        return frame


class FakeAudio:
    def __init__(self):
        self.enabled = True
        self.calls = []

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def play(self, event):
        if self.enabled:
            self.calls.append(event)


def _make_worker(fake_pyautogui, settings_override=None, audio=None):
    settings = SettingsManager()
    if settings_override:
        settings.update(settings_override)
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
        audio=audio,
    )
    return worker, mouse, events


def _drain(events):
    out = []
    while not events.empty():
        out.append(events.get_nowait())
    return out


def test_left_click_plays_audio_and_posts_feedback(fake_pyautogui):
    audio = FakeAudio()
    worker, _, events = _make_worker(fake_pyautogui, audio=audio)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="left_click", click_x=0.5, click_y=0.5))
    assert "left_click" in audio.calls
    kinds = [e.kind for e in _drain(events)]
    assert "feedback" in kinds


def test_drag_start_plays_audio(fake_pyautogui):
    audio = FakeAudio()
    worker, mouse, _ = _make_worker(fake_pyautogui, audio=audio)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="drag_start"))
    assert "drag" in audio.calls
    worker._execute(MouseCommand(kind="drag_end"))


def test_audio_disabled_by_setting(fake_pyautogui):
    audio = FakeAudio()
    worker, _, _ = _make_worker(fake_pyautogui, {"enable_audio_feedback": False}, audio=audio)
    assert audio.enabled is False


def test_camera_loss_releases_buttons_and_reports(fake_pyautogui):
    worker, mouse, events = _make_worker(fake_pyautogui)
    worker._mouse_enabled = True
    worker._execute(MouseCommand(kind="drag_start"))
    assert "left" in mouse.held_buttons

    worker._handle_camera_loss()
    assert mouse.held_buttons == set()  # zero stuck input
    assert worker._reconnecting is True
    kinds = [e.kind for e in _drain(events)]
    assert "camera_state" in kinds


def test_camera_recovery_resets_backoff(fake_pyautogui):
    worker, _, events = _make_worker(fake_pyautogui)
    worker._handle_camera_loss()
    assert worker._backoff.active is True
    worker._on_camera_recovered()
    assert worker._backoff.active is False
    assert worker._reconnecting is False
    states = [e.payload.get("state") for e in _drain(events) if e.kind == "camera_state"]
    assert "connected" in states


def test_calibration_session_collects_and_produces_result(fake_pyautogui, hand_factory):
    worker, _, events = _make_worker(fake_pyautogui)
    worker.start_calibration()
    landmarks = hand_factory()  # open hand
    for _ in range(6):
        worker._feed_calibration(landmarks)
    worker.advance_calibration()  # -> pinch step

    # A positive pinch ratio sample (the session rejects non-positive values).
    pinch_landmarks = hand_factory(scale=0.22)
    for _ in range(10):
        worker._feed_calibration(pinch_landmarks)
    worker.advance_calibration()  # -> done

    results = [e for e in _drain(events) if e.kind == "calibration_result"]
    assert results
    payload = results[-1].payload
    assert payload["ok"] is True
    assert 0.15 <= payload["pinch_threshold"] <= 0.6


def test_calibration_progress_events(fake_pyautogui, hand_factory):
    worker, _, events = _make_worker(fake_pyautogui)
    worker.start_calibration()
    worker._feed_calibration(hand_factory())
    progress = [e for e in _drain(events) if e.kind == "calibration"]
    assert progress
    assert progress[-1].payload["step"] == "open"
    worker.cancel_calibration()
    assert worker.calibrating is False


def test_map_screen_applies_region_offset(fake_pyautogui):
    worker, _, _ = _make_worker(fake_pyautogui)
    from handgesturemouse.core.screens import DisplayRegion

    worker._region = DisplayRegion(1000, 500, 1920, 1080)
    worker._mapper.update(1920, 1080, 0.0, 1.0)
    x, y = worker._map_screen(0.5, 0.5)
    assert x == 1000 + 960
    assert y == 500 + 540
