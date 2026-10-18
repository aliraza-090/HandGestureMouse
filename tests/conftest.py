"""Shared pytest fixtures and a synthetic hand model.

Tests never open a camera or move the real mouse.  ``make_hand`` builds a
21-landmark list matching the MediaPipe hand topology so the gesture geometry
can be exercised deterministically.
"""

import os
import sys

import pytest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _finger_points(cx, off, cy, length, extended):
    """Return (mcp, pip, dip, tip) for one finger of the synthetic hand."""
    mcp = (cx + off, cy, 0.0)
    if extended:
        pip = (cx + off, cy - 0.45 * length, 0.0)
        dip = (cx + off, cy - 0.75 * length, 0.0)
        tip = (cx + off, cy - length, 0.0)
    else:
        pip = (cx + off, cy - 0.15 * length, 0.0)
        dip = (cx + off, cy + 0.05 * length, 0.0)
        tip = (cx + off, cy + 0.25 * length, 0.0)
    return mcp, pip, dip, tip


def make_hand(
    cx: float = 0.5,
    cy: float = 0.5,
    scale: float = 0.15,
    extensions=(True, True, True, True),  # index, middle, ring, pinky
    index_pinch: bool = False,
    middle_pinch: bool = False,
):
    """Build 21 normalized ``(x, y, z)`` landmarks.

    ``extensions`` controls finger extension; ``index_pinch`` places the thumb
    tip onto the index tip; ``middle_pinch`` onto the middle tip.
    """
    landmarks = [None] * 21
    wrist = (cx, cy + scale, 0.0)
    landmarks[0] = wrist  # wrist
    landmarks[1] = (cx - 0.03, cy + 0.10, 0.0)  # thumb CMC
    landmarks[2] = (cx - 0.05, cy + 0.06, 0.0)  # thumb MCP
    landmarks[3] = (cx - 0.07, cy + 0.03, 0.0)  # thumb IP

    offsets = {"index": -0.06, "middle": 0.0, "ring": 0.06, "pinky": 0.12}
    lengths = {"index": scale * 1.05, "middle": scale * 1.15, "ring": scale * 1.05, "pinky": scale * 0.9}
    mcp_index = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}
    order = ["index", "middle", "ring", "pinky"]
    for i, name in enumerate(order):
        base = mcp_index[name]
        pts = _finger_points(cx, offsets[name], cy, lengths[name], extensions[i])
        landmarks[base], landmarks[base + 1], landmarks[base + 2], landmarks[base + 3] = pts

    if index_pinch:
        landmarks[4] = landmarks[8]
    elif middle_pinch:
        landmarks[4] = landmarks[12]
    else:
        landmarks[4] = (cx - 0.11, cy + 0.04, 0.0)  # thumb tip well away
    return landmarks


@pytest.fixture
def hand_factory():
    return make_hand


class FakeClock:
    """Deterministic monotonic clock for the gesture state machine."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock():
    return FakeClock()


class FakePyAutoGUI:
    """Minimal PyAutoGUI replacement recording every call."""

    class FailSafeException(Exception):
        pass

    FAILSAFE = True

    def __init__(self) -> None:
        self.calls = []
        self._pos = type("P", (), {"x": 0, "y": 0})()
        self._screen = (1920, 1080)
        self.raise_fail_safe = False
        self.down = set()

    def _check(self):
        if self.raise_fail_safe:
            raise self.FailSafeException("corner")

    def size(self):
        return self._screen

    def moveTo(self, x, y, duration=0.0):
        self._check()
        self.calls.append(("moveTo", x, y))
        self._pos = type("P", (), {"x": x, "y": y})()

    def click(self, x, y, button="left"):
        self._check()
        self.calls.append(("click", x, y, button))

    def scroll(self, clicks, x=None, y=None):
        self._check()
        self.calls.append(("scroll", clicks, x, y))

    def position(self):
        return self._pos

    def mouseDown(self, button="left"):
        self._check()
        self.calls.append(("mouseDown", button))
        self.down.add(button)

    def mouseUp(self, button="left"):
        if self.raise_fail_safe:
            raise self.FailSafeException("corner")
        self.calls.append(("mouseUp", button))
        self.down.discard(button)


@pytest.fixture
def fake_pyautogui():
    return FakePyAutoGUI()