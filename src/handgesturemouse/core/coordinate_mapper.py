"""Cursor coordinate mapping and dead-zone remapping."""

from typing import Tuple

import numpy as np


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class CoordinateMapper:
    """Map normalized camera coordinates to screen pixels.

    ``dead_zone`` implements the classic HandTracking "rescale to dead zone"
    band: while the hand stays near the center of the frame the cursor does
    not move, which keeps the cursor steady and reduces accidental drift.
    """

    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        dead_zone: float = 0.0,
        sensitivity: float = 1.0,
    ) -> None:
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("screen dimensions must be positive")
        self.screen_width = int(screen_width)
        self.screen_height = int(screen_height)
        self.dead_zone = clamp(float(dead_zone), 0.0, 0.5)
        self.sensitivity = max(0.0, float(sensitivity))

    def update(self, screen_width: int, screen_height: int, dead_zone: float, sensitivity: float) -> None:
        self.screen_width = int(screen_width)
        self.screen_height = int(screen_height)
        self.dead_zone = clamp(float(dead_zone), 0.0, 0.5)
        self.sensitivity = max(0.0, float(sensitivity))

    def map_horizontal(self, x: float) -> float:
        return _remap_horizontal(self.screen_width, x, self.dead_zone, self.sensitivity)

    def map_vertical(self, y: float) -> float:
        return _remap_vertical(self.screen_height, y, self.dead_zone, self.sensitivity)

    def map(self, x: float, y: float) -> Tuple[float, float]:
        """Map normalized ``(x, y)`` to ``(screen_x, screen_y)``."""
        return (
            _remap_horizontal(self.screen_width, x, self.dead_zone, self.sensitivity),
            _remap_vertical(self.screen_height, y, self.dead_zone, self.sensitivity),
        )


def _remap_horizontal(width: int, x: float, dead_zone: float, sensitivity: float) -> float:
    center = 0.5
    if abs(x - center) <= dead_zone:
        return center * width
    sign = 1.0 if x > center else -1.0
    magnitude = (abs(x - center) - dead_zone) / (0.5 - dead_zone)
    return clamp(center * width + sign * magnitude * sensitivity * width / 2.0, 0, width - 1)


def _remap_vertical(height: int, y: float, dead_zone: float, sensitivity: float) -> float:
    center = 0.5
    if abs(y - center) <= dead_zone:
        return center * height
    sign = 1.0 if y > center else -1.0
    magnitude = (abs(y - center) - dead_zone) / (0.5 - dead_zone)
    return clamp(center * height + sign * magnitude * sensitivity * height / 2.0, 0, height - 1)


def remap_range(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    """Linear interpolation of ``x`` from one range to another (unclamped)."""
    if in_max == in_min:
        return (out_min + out_max) / 2.0
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def cartesian_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Euclidean distance used for movement snap detection."""
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))