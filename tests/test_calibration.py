"""Gesture calibration session tests (metric based, no camera needed)."""

from handgesturemouse.core.calibration import (
    STEP_DONE,
    STEP_OPEN,
    STEP_PINCH,
    CalibrationSession,
)


def _feed_open(session, n, scale=0.15):
    for _ in range(n):
        session.add_open(scale, box_width=0.4, box_height=0.5)


def _feed_pinch(session, n, ratio=0.18):
    for _ in range(n):
        session.add_pinch(ratio)


def test_starts_on_open_step():
    session = CalibrationSession()
    assert session.step == STEP_OPEN
    assert session.can_advance() is False


def test_advance_requires_minimum_samples():
    session = CalibrationSession(min_open=5, min_pinch=8)
    _feed_open(session, 4)
    assert session.advance() == STEP_OPEN  # not enough yet
    _feed_open(session, 1)
    assert session.advance() == STEP_PINCH


def test_full_flow_produces_bounded_thresholds():
    session = CalibrationSession(min_open=3, min_pinch=3)
    _feed_open(session, 3)
    session.advance()
    _feed_pinch(session, 5)
    assert session.advance() == STEP_DONE

    result = session.result()
    assert result.ok is True
    assert 0.15 <= result.pinch_threshold <= 0.60
    assert result.pinch_hold_threshold > result.pinch_threshold
    assert result.pinch_hold_threshold <= 0.70
    assert result.open_samples == 3
    assert result.pinch_samples == 5
    settings = result.as_settings()
    assert set(settings) == {"pinch_threshold", "pinch_hold_threshold"}


def test_result_incomplete_when_not_enough_samples():
    session = CalibrationSession(min_open=5, min_pinch=8)
    _feed_open(session, 1)
    result = session.result()
    assert result.ok is False
    assert result.message
    assert 0.15 <= result.pinch_threshold <= 0.6


def test_add_routes_by_step():
    session = CalibrationSession(min_open=2, min_pinch=2)
    assert session.add({"hand_scale": 0.2, "box_width": 0.3, "box_height": 0.4}) is True
    assert session.open_samples == 1
    assert session.add({"pinch_ratio": 0.2}) is False  # still on open step
    session.advance() if session.can_advance() else None
    session.add({"hand_scale": 0.2})
    session.advance()
    assert session.step == STEP_PINCH
    assert session.add({"pinch_ratio": 0.2}) is True
    assert session.pinch_samples == 1


def test_non_positive_samples_are_ignored():
    session = CalibrationSession()
    session.add_open(0.0, 0.0, 0.0)
    session.add_pinch(0.0)
    assert session.open_samples == 0
    assert session.pinch_samples == 0


def test_reset_clears_samples():
    session = CalibrationSession(min_open=1, min_pinch=1)
    _feed_open(session, 2)
    session.advance()
    _feed_pinch(session, 2)
    session.reset()
    assert session.step == STEP_OPEN
    assert session.open_samples == 0
    assert session.pinch_samples == 0


def test_tighter_pinch_produces_higher_threshold_than_loose():
    tight = CalibrationSession(min_open=2, min_pinch=4)
    _feed_open(tight, 2)
    tight.advance()
    _feed_pinch(tight, 4, ratio=0.10)
    tight.advance()

    loose = CalibrationSession(min_open=2, min_pinch=4)
    _feed_open(loose, 2)
    loose.advance()
    _feed_pinch(loose, 4, ratio=0.30)
    loose.advance()

    assert loose.result().pinch_threshold > tight.result().pinch_threshold
