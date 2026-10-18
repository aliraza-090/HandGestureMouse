"""Coordinate mapping, dead-zone and smoothing tests."""

import pytest

from handgesturemouse.core.coordinate_mapper import CoordinateMapper, clamp, remap_range
from handgesturemouse.core.cursor_smoothing import CursorSmoother


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10


def test_center_maps_to_screen_center():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=1.0)
    x, y = mapper.map(0.5, 0.5)
    assert x == pytest.approx(960)
    assert y == pytest.approx(540)


def test_edges_are_clamped():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=1.0)
    assert mapper.map(0.0, 0.0) == (0, 0)
    right, bottom = mapper.map(1.0, 1.0)
    assert right == 1919
    assert bottom == 1079


def test_sensitivity_moves_cursor_faster():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=2.0)
    slow = CoordinateMapper(1920, 1080, dead_zone=0.0, sensitivity=1.0)
    assert mapper.map(0.75, 0.5)[0] > slow.map(0.75, 0.5)[0]


def test_dead_zone_freezes_center():
    mapper = CoordinateMapper(1920, 1080, dead_zone=0.1, sensitivity=1.0)
    assert mapper.map(0.5, 0.5) == (960, 540)
    assert mapper.map(0.55, 0.45) == (960, 540)  # inside the dead zone
    assert mapper.map(0.9, 0.5)[0] > 960


def test_invalid_screen_size_raises():
    with pytest.raises(ValueError):
        CoordinateMapper(0, 0)


def test_remap_range():
    assert remap_range(0.5, 0, 1, 0, 10) == pytest.approx(5)
    assert remap_range(5, 0, 10, 0, 100) == pytest.approx(50)


def test_smoother_first_sample_is_exact():
    smoother = CursorSmoother(0.5)
    assert smoother.smooth(100, 200) == (100, 200)


def test_smoothing_converges_towards_target():
    smoother = CursorSmoother(0.8)
    smoother.smooth(0, 0)
    for _ in range(50):
        x, y = smoother.smooth(100, 100)
    assert x == pytest.approx(100, abs=1)
    assert y == pytest.approx(100, abs=1)


def test_zero_smoothing_is_instant():
    smoother = CursorSmoother(0.0)
    assert smoother.alpha == pytest.approx(1.0)
    smoother.smooth(0, 0)
    assert smoother.smooth(50, 50) == pytest.approx((50, 50))


def test_reset_clears_history():
    smoother = CursorSmoother(0.9)
    smoother.smooth(10, 10)
    smoother.reset()
    assert smoother.smooth(300, 300) == (300, 300)