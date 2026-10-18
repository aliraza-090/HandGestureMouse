"""Eco / battery-saver throttling tests."""

import numpy as np

from handgesturemouse.core.eco import EcoThrottle, MotionDetector


def test_disabled_always_uses_active_rate(fake_clock):
    eco = EcoThrottle(enabled=False, idle_seconds=45, eco_fps=5, active_fps=30, clock=fake_clock)
    fake_clock.advance(1000)
    assert eco.interval(hand_present=False) == 1.0 / 30
    assert eco.active is False


def test_hand_present_uses_active_rate(fake_clock):
    eco = EcoThrottle(enabled=True, idle_seconds=45, eco_fps=5, active_fps=30, clock=fake_clock)
    assert eco.interval(hand_present=True) == 1.0 / 30
    assert eco.active is False


def test_idle_throttles_to_eco_rate(fake_clock):
    eco = EcoThrottle(enabled=True, idle_seconds=45, eco_fps=5, active_fps=30, clock=fake_clock)
    # First idle frame starts the idle clock but keeps full speed.
    assert eco.interval(hand_present=False) == 1.0 / 30
    fake_clock.advance(44)
    assert eco.interval(hand_present=False) == 1.0 / 30
    assert eco.active is False
    fake_clock.advance(2)  # now past 45s of no hand
    assert eco.interval(hand_present=False) == 1.0 / 5
    assert eco.active is True


def test_hand_reentry_restores_full_rate_immediately(fake_clock):
    eco = EcoThrottle(enabled=True, idle_seconds=45, eco_fps=5, active_fps=30, clock=fake_clock)
    eco.interval(hand_present=False)
    fake_clock.advance(60)
    assert eco.interval(hand_present=False) == 1.0 / 5
    assert eco.active is True
    # A hand in the very next frame must restore 30 FPS (< 50ms latency).
    assert eco.interval(hand_present=True) == 1.0 / 30
    assert eco.active is False


def test_configure_and_reset(fake_clock):
    eco = EcoThrottle(enabled=True, idle_seconds=45, eco_fps=5, active_fps=30, clock=fake_clock)
    eco.configure(enabled=False, idle_seconds=10, eco_fps=8, active_fps=60)
    assert eco.enabled is False
    assert eco.idle_seconds == 10
    assert eco.eco_fps == 8
    assert eco.active_fps == 60
    eco.configure(enabled=True)
    eco.interval(hand_present=False)
    fake_clock.advance(11)
    assert eco.interval(hand_present=False) == 1.0 / 8
    assert eco.active is True
    eco.reset()
    assert eco.active is False


def test_motion_detector_ignores_static_frame():
    detector = MotionDetector(threshold=2.0)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    assert detector.update(frame) is False
    assert detector.update(frame) is False


def test_motion_detector_flags_change():
    detector = MotionDetector(threshold=2.0)
    dark = np.zeros((240, 320, 3), dtype=np.uint8)
    bright = np.full((240, 320, 3), 255, dtype=np.uint8)
    detector.update(dark)
    assert detector.update(bright) is True
    detector.reset()
    # After reset the first frame only primes the baseline.
    assert detector.update(bright) is False
