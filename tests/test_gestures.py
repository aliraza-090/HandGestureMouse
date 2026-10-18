"""Gesture classification, debouncing and state machine tests."""

from handgesturemouse.config.defaults import DEFAULTS
from handgesturemouse.core import geometry
from handgesturemouse.core.gesture_controller import (
    MODE_DRAG,
    GestureController,
)


def _controller(fake_clock, **overrides):
    settings = dict(DEFAULTS)
    settings.update(overrides)
    return GestureController(settings, clock=fake_clock)


def test_geometry_finger_extension(hand_factory):
    extended = hand_factory(extensions=(True, True, True, True))
    folded = hand_factory(extensions=(False, False, False, False))
    assert geometry.finger_extended(extended, geometry.INDEX_TIP, geometry.INDEX_PIP)
    assert not geometry.finger_extended(folded, geometry.INDEX_TIP, geometry.INDEX_PIP)
    assert geometry.hand_scale(extended) > 0


def test_open_hand_extends_no_command(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    cmd = controller.process(hand_factory(extensions=(False, False, False, False)))
    assert cmd.kind == "none"


def test_index_finger_emits_move(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    hand = hand_factory(extensions=(True, False, False, False), cx=0.4, cy=0.4)
    cmd = controller.process(hand)
    assert cmd.kind == "move"
    assert cmd.x == hand[geometry.INDEX_TIP][0]
    assert cmd.y == hand[geometry.INDEX_TIP][1]


def test_no_hand_returns_none(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    assert controller.process(None).kind == "none"


def test_left_click_fires_once_on_release(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    pinched = hand_factory(index_pinch=True)

    assert controller.process(pinched).kind == "none"
    fake_clock.advance(0.1)
    assert controller.process(pinched).kind == "none"
    fake_clock.advance(0.1)
    released = controller.process(hand_factory(extensions=(True, False, False, False)))
    assert released.kind == "left_click"
    # subsequent open frames must not repeat the click
    assert controller.process(hand_factory(extensions=(True, False, False, False))).kind != "left_click"


def test_left_click_debounced_within_cooldown(hand_factory, fake_clock):
    controller = _controller(fake_clock, gesture_cooldown=0.5)
    pinched = hand_factory(index_pinch=True)
    open_hand = hand_factory(extensions=(True, False, False, False))

    assert controller.process(pinched).kind == "none"
    assert controller.process(open_hand).kind == "left_click"
    # A second pinch released inside the cooldown must not click again.
    fake_clock.advance(0.1)
    controller.process(pinched)
    fake_clock.advance(0.1)
    assert controller.process(open_hand).kind != "left_click"


def test_long_hold_becomes_drag(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    pinched = hand_factory(index_pinch=True)

    assert controller.process(pinched).kind == "none"
    fake_clock.advance(0.5)
    assert controller.process(pinched).kind == "drag_start"
    assert controller.mode == MODE_DRAG
    assert controller.process(pinched).kind == "drag_move"
    fake_clock.advance(0.1)
    assert controller.process(hand_factory(extensions=(True, False, False, False))).kind == "drag_end"
    assert controller.mode == "none"


def test_hand_lost_releases_drag(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    pinched = hand_factory(index_pinch=True)
    controller.process(pinched)
    fake_clock.advance(0.5)
    assert controller.process(pinched).kind == "drag_start"
    assert controller.process(None).kind == "drag_end"


def test_right_click_on_middle_pinch(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    hand = hand_factory(extensions=(True, True, False, False), middle_pinch=True)
    assert controller.process(hand).kind == "right_click"


def test_right_click_cooldown(hand_factory, fake_clock):
    controller = _controller(fake_clock, gesture_cooldown=0.5)
    hand = hand_factory(extensions=(True, True, False, False), middle_pinch=True)
    open_hand = hand_factory(extensions=(True, False, False, False))

    assert controller.process(hand).kind == "right_click"
    fake_clock.advance(0.1)
    controller.process(open_hand)
    fake_clock.advance(0.1)  # 0.2s since the first click: inside the cooldown
    assert controller.process(hand).kind == "none"
    fake_clock.advance(0.1)
    controller.process(open_hand)
    fake_clock.advance(0.4)  # reunite after the cooldown
    assert controller.process(hand).kind == "right_click"


def test_scroll_gesture_direction(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    v_pose_a = hand_factory(extensions=(True, True, False, False), cy=0.45)
    v_pose_b = hand_factory(extensions=(True, True, False, False), cy=0.55)  # hand moved down

    assert controller.process(v_pose_a).kind == "none"  # first frame establishes baseline
    cmd = controller.process(v_pose_b)
    assert cmd.kind == "scroll"
    assert cmd.steps < 0  # moving the hand down scrolls down


def test_disabled_gesture_produces_no_action(hand_factory, fake_clock):
    controller = _controller(fake_clock, use_gesture_move=False)
    cmd = controller.process(hand_factory(extensions=(True, False, False, False)))
    assert cmd.kind == "none"


def test_classify_pose_reports_fingers(hand_factory, fake_clock):
    controller = _controller(fake_clock)
    report = controller.classify_pose(hand_factory(extensions=(True, False, False, False)))
    assert report.hand_present is True
    assert report.fingers[1] is True
    assert report.gesture == "move"