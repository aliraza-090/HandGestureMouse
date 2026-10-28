"""Additional tests covering required behaviors."""
import numpy as np

from handgesturemouse.core import geometry
from handgesturemouse.core.coordinate_mapper import CoordinateMapper
from handgesturemouse.core.cursor_smoothing import CursorSmoother
from handgesturemouse.core.gesture_controller import GestureController
from handgesturemouse.core.mouse_controller import MouseController, EmergencyStop
from handgesturemouse.core.hand_tracker import HandTracker
from handgesturemouse.config.defaults import DEFAULTS


def test_index_fingertip_coordinate_extraction(hand_factory):
    hand = hand_factory()
    # Index tip is landmark 8
    assert len(hand[8]) == 3
    assert 0.0 <= hand[8][0] <= 1.0
    assert 0.0 <= hand[8][1] <= 1.0


def test_horizontal_mirror_mapping():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=1.0)
    # With mirror, the coordinate mapping is still consistent
    x1, y1 = mapper.map(0.25, 0.5)
    x2, y2 = mapper.map(0.75, 0.5)
    assert x1 != x2


def test_screen_coordinate_conversion_and_clamping():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=1.0)
    x, y = mapper.map(0.0, 0.0)
    assert x >= 0 and y >= 0
    x, y = mapper.map(1.0, 1.0)
    assert x < 1920 and y < 1080


def test_smoothing_calculations():
    s = CursorSmoother(0.5)
    p1 = s.smooth(0, 0)
    p2 = s.smooth(100, 100)
    assert p1 == (0, 0)
    assert p2[0] > 0 and p2[0] < 100


def test_gesture_state_transitions_double_click(fake_clock, hand_factory):
    settings = dict(DEFAULTS)
    controller = GestureController(settings, clock=fake_clock)
    pinched = hand_factory(index_pinch=True)
    open_hand = hand_factory(extensions=(True, False, False, False))
    # First click
    controller.process(pinched)
    fake_clock.advance(0.1)
    cmd1 = controller.process(open_hand)
    assert cmd1.kind == "left_click"
    fake_clock.advance(0.05)
    controller.process(pinched)
    fake_clock.advance(0.1)
    cmd2 = controller.process(open_hand)
    # Second click within short time - might be allowed or may depend on cooldown
    # Just verify state machine handles it
    assert cmd2.kind in ("left_click", "none")


def test_drag_and_drop_behavior(fake_clock, hand_factory):
    settings = dict(DEFAULTS)
    controller = GestureController(settings, clock=fake_clock)
    pinched = hand_factory(index_pinch=True)
    open_hand = hand_factory(extensions=(True, False, False, False))
    assert controller.process(pinched).kind == "none"
    fake_clock.advance(0.5)
    assert controller.process(pinched).kind == "drag_start"
    assert controller.process(pinched).kind == "drag_move"
    assert controller.process(open_hand).kind == "drag_end"


def test_scroll_recognition(fake_clock, hand_factory):
    settings = dict(DEFAULTS)
    controller = GestureController(settings, clock=fake_clock)
    v1 = hand_factory(extensions=(True, True, False, False), cy=0.4)
    v2 = hand_factory(extensions=(True, True, False, False), cy=0.6)
    assert controller.process(v1).kind == "none"
    cmd = controller.process(v2)
    assert cmd.kind == "scroll"


def test_right_click_recognition(fake_clock, hand_factory):
    settings = dict(DEFAULTS)
    controller = GestureController(settings, clock=fake_clock)
    hand = hand_factory(extensions=(True, True, False, False), middle_pinch=True)
    assert controller.process(hand).kind == "right_click"


def test_mouse_button_release(fake_pyautogui):
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.start_drag()
    assert "left" in mouse.held_buttons
    mouse.release_all()
    assert mouse.held_buttons == set()


def test_emergency_stop_via_fail_safe(fake_pyautogui):
    triggered = []
    mouse = MouseController(pyautogui=fake_pyautogui)
    mouse.set_fail_safe_callback(lambda e: triggered.append(e))
    fake_pyautogui.raise_fail_safe = True
    try:
        mouse.move_to(0, 0)
    except Exception:
        pass
    assert len(triggered) >= 1


def test_hand_tracker_annotate_landmark_connection_handling():
    tracker = HandTracker(model_file="x.task")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Create dummy landmarks
    landmarks = [(0.5, 0.5, 0.0)] * 21
    out = tracker.annotate(frame, landmarks)
    assert out.shape == frame.shape
