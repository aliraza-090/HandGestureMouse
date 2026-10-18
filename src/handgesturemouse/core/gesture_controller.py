"""Gesture recognition controller (pure logic, no dependencies on GUI).

This module turns MediaPipe landmarks into high-level ``MouseCommand``
objects using a temporal state machine:

- ``move``          index finger extended and stable      -> cursor movement
- ``left_click``    thumb+index pinch held briefly        -> left click
- ``right_click``   thumb+middle pinch (index open)       -> right click
- ``scroll``        index+middle "V" raised               -> vertical scrolling
- ``drag``          thumb+index pinch held > hold time    -> drag-and-drop

The classifier is deliberately conservative: gestures that are too similar to
the neutral pose produce no command.  Debouncing (edge-triggering),
cooldowns and hysteresis prevent repeated or unintended mouse actions.
"""

import time
from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional, Tuple

from .geometry import (
    PINKY_PIP,
    PINKY_TIP,
    RING_PIP,
    RING_TIP,
    INDEX_PIP,
    MIDDLE_PIP,
    MIDDLE_TIP,
    INDEX_TIP,
    thumb_extended,
    finger_extended,
    pinch_index,
    pinch_middle,
    hand_center,
)

# Gesture modes -------------------------------------------------------------

MODE_NONE = "none"
MODE_MOVE = "move"
MODE_SCROLL = "scroll"
MODE_LEFT_PINCH = "left_pinch"  # potential click or drag
MODE_DRAG = "drag"
MODE_RIGHT_PINCH = "right_pinch"

# Commands ------------------------------------------------------------------


@dataclass
class MouseCommand:
    """A single frame-level mouse action request.

    Coordinates are normalized (0..1) camera coordinates, except ``x``/``y``
    for ``move`` and ``drag_move`` which the pipeline maps to screen pixels.
    """

    kind: str  # move|left_click|right_click|scroll|drag_start|drag_move|drag_end|none
    x: Optional[float] = None
    y: Optional[float] = None
    click_x: Optional[float] = None
    click_y: Optional[float] = None
    steps: float = 0.0
    label: str = ""


@dataclass
class HandReport:
    """Finger pose snapshot used for the GUI status."""

    gesture: str = "none"
    fingers: Tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)  # thumb..pinky
    pinch_index: float = 1.0
    pinch_middle: float = 1.0
    hand_present: bool = False


class GestureController:
    """Converts a hand landmark frame into a single mouse command."""

    def __init__(
        self,
        settings: Optional[Mapping[str, object]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings: Mapping[str, object] = settings if settings is not None else {}
        self._clock = clock

        self._mode = MODE_NONE
        self._pinch_started: float = 0.0
        self._pinch_pos: Tuple[float, float] = (0.0, 0.0)
        self._last_discrete: float = -1e9
        self._last_scroll_center: Optional[Tuple[float, float]] = None
        self._scroll_accumulator: float = 0.0
        self._last_scroll_y: Optional[float] = None
        self._last_x: Optional[float] = None
        self._last_y: Optional[float] = None

    # -- settings -----------------------------------------------------------

    def refresh(self, settings: Mapping[str, object]) -> None:
        self._settings = dict(settings)

    def _f(self, key: str) -> float:
        return float(self._settings.get(key, 0.0))

    def _b(self, key: str) -> bool:
        return bool(self._settings.get(key, True))

    # -- pinch state --------------------------------------------------------

    def _pinch_closed(self, ratio: float) -> bool:
        return ratio < self._f("pinch_threshold")

    def _pinch_open(self, ratio: float) -> bool:
        return ratio > self._f("pinch_hold_threshold")

    # -- public API ---------------------------------------------------------

    def process(self, landmarks: Optional[List[Tuple[float, float, float]]]) -> "MouseCommand":
        """Advance the state machine by one frame and return the command."""
        report = self.classify_pose(landmarks)
        if landmarks is None:
            command = self._on_hand_lost()
            return command
        return self._transition(report, landmarks)

    def classify_pose(self, landmarks: Optional[List[Tuple[float, float, float]]]) -> HandReport:
        """Static per-frame pose classification (testable without state)."""
        if not landmarks or len(landmarks) < 21:
            return HandReport(hand_present=False)
        fingers = (
            thumb_extended(landmarks),
            finger_extended(landmarks, INDEX_TIP, INDEX_PIP),
            finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP),
            finger_extended(landmarks, RING_TIP, RING_PIP),
            finger_extended(landmarks, PINKY_TIP, PINKY_PIP),
        )
        gesture = self._pose_name(landmarks, fingers)
        return HandReport(
            gesture=gesture,
            fingers=fingers,
            pinch_index=pinch_index(landmarks),
            pinch_middle=pinch_middle(landmarks),
            hand_present=True,
        )

    def _pose_name(self, landmarks, fingers) -> str:
        thumb, index, middle, ring, pinky = fingers
        pi = pinch_index(landmarks)
        pm = pinch_middle(landmarks)
        if self._pinch_closed(pi):
            return "pinch"
        if self._pinch_closed(pm):
            return "right-pinch"
        if index and middle and not ring and not pinky:
            return "scroll"
        if index and not middle and not ring and not pinky:
            return "move"
        return "open"

    def _transition(self, report: HandReport, landmarks) -> MouseCommand:
        now = self._clock()
        pi = report.pinch_index
        pm = report.pinch_middle
        index = report.fingers[1]
        middle = report.fingers[2]
        ring = report.fingers[3]
        pinky = report.fingers[4]
        index_pos = (landmarks[INDEX_TIP][0], landmarks[INDEX_TIP][1])

        if not self._is_scroll_pose(index, middle, ring, pinky):
            # leaving the scroll pose resets the scroll baseline
            self._last_scroll_y = None
            self._scroll_accumulator = 0.0

        self._last_x, self._last_y = index_pos

        mode = self._mode

        # --- left pinch entry ----------------------------------------------
        if mode in (MODE_NONE, MODE_MOVE, MODE_SCROLL):
            if self._pinch_closed(pi):
                self._mode = MODE_LEFT_PINCH
                self._pinch_started = now
                self._pinch_pos = index_pos
                return self._freeze_command("pinch")
            if self._pinch_closed(pm) and not self._pinch_closed(pi) and index and self._b(
                "use_gesture_right_click"
            ):
                self._mode = MODE_RIGHT_PINCH
                return self._right_click(now)
            if self._is_scroll_pose(index, middle, ring, pinky):
                return self._scroll_command(landmarks)
            if index and self._b("use_gesture_move"):
                if not ring and not pinky and not middle:
                    return MouseCommand(kind="move", x=index_pos[0], y=index_pos[1], label="move")
            return self._freeze_command("none")

        # --- active left pinch ----------------------------------------------
        if mode == MODE_LEFT_PINCH:
            if self._pinch_open(pi):
                self._mode = MODE_NONE
                held = now - self._pinch_started
                if held < self._f("click_hold_time") and self._b("use_gesture_left_click"):
                    return self._left_click(now, self._pinch_pos)
                return self._freeze_command("click released")
            if now - self._pinch_started >= self._f("click_hold_time") and self._b("use_gesture_drag"):
                self._mode = MODE_DRAG
                return MouseCommand(kind="drag_start", x=index_pos[0], y=index_pos[1], label="drag")
            return self._freeze_command("pinch")

        # --- active drag ------------------------------------------------------
        if mode == MODE_DRAG:
            if self._pinch_open(pi):
                self._mode = MODE_NONE
                self._note_discrete(now)
                return MouseCommand(kind="drag_end", label="drag end")
            return MouseCommand(kind="drag_move", x=index_pos[0], y=index_pos[1], label="drag")

        # --- active right pinch -------------------------------------------------
        if mode == MODE_RIGHT_PINCH:
            if self._pinch_open(pm):
                self._mode = MODE_NONE
            return self._freeze_command("right-pinch")

        return self._freeze_command("none")

    # -- helpers ---------------------------------------------------------------

    def _is_scroll_pose(self, index: bool, middle: bool, ring: bool, pinky: bool) -> bool:
        return index and middle and not ring and not pinky and self._b("use_gesture_scroll")

    def _freeze_command(self, label: str) -> MouseCommand:
        return MouseCommand(kind="none", label=label)

    def _left_click(self, now: float, pos: Tuple[float, float]) -> MouseCommand:
        if now - self._last_discrete < self._f("gesture_cooldown"):
            return self._freeze_command("left click (cooldown)")
        self._note_discrete(now)
        return MouseCommand(
            kind="left_click",
            click_x=pos[0],
            click_y=pos[1],
            label="left click",
        )

    def _right_click(self, now: float) -> MouseCommand:
        if now - self._last_discrete < self._f("gesture_cooldown"):
            return self._freeze_command("right-pinch (cooldown)")
        self._note_discrete(now)
        return MouseCommand(kind="right_click", label="right click")

    def _scroll_command(self, landmarks) -> MouseCommand:
        center = hand_center(landmarks)
        center_y = center[1]
        if self._last_scroll_y is None:
            self._last_scroll_y = center_y
            return MouseCommand(kind="none", label="scroll (idle)")
        delta = self._last_scroll_y - center_y  # up = positive
        self._last_scroll_y = center_y
        nominal = delta * self._f("scroll_sensitivity") * 10.0
        yield_band = self._f("scroll_yield")
        if abs(delta) < yield_band:
            nominal = 0.0
        self._scroll_accumulator += nominal
        steps = int(self._scroll_accumulator)
        steps = max(-30, min(30, steps))
        if steps != 0:
            self._scroll_accumulator -= steps
        if steps == 0:
            return MouseCommand(kind="none", label="scroll")
        return MouseCommand(
            kind="scroll",
            steps=float(steps),
            label="scroll up" if steps > 0 else "scroll down",
        )

    def _note_discrete(self, now: float) -> None:
        self._last_discrete = now

    def _on_hand_lost(self) -> MouseCommand:
        """Release drag state when the hand disappears mid-gesture."""
        self._last_scroll_y = None
        self._scroll_accumulator = 0.0
        self._last_scroll_center = None
        if self._mode == MODE_DRAG:
            self._mode = MODE_NONE
            return MouseCommand(kind="drag_end", label="drag (hand lost)")
        self._mode = MODE_NONE
        return MouseCommand(kind="none", label="no hand")

    def reset(self) -> None:
        """Clear all temporal state (used when control stops)."""
        self._mode = MODE_NONE
        self._pinch_started = 0.0
        self._pinch_pos = (0.0, 0.0)
        self._last_scroll_y = None
        self._scroll_accumulator = 0.0
        self._last_scroll_center = None

    @property
    def mode(self) -> str:
        return self._mode