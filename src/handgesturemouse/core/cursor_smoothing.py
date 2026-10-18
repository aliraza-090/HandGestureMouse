"""Exponential moving average cursor smoothing.

A smoothing value of 0.0 disables smoothing (instant response), 1.0 applies
very heavy smoothing.  The alpha factor is derived linearly between the two.
"""

from typing import Optional, Tuple


class CursorSmoother:
    def __init__(self, smoothing: float = 0.5) -> None:
        self.smoothing = float(smoothing)
        self._x: Optional[float] = None
        self._y: Optional[float] = None

    @property
    def alpha(self) -> float:
        """Weight given to the newest sample (1.0 = no smoothing)."""
        return 1.0 - 0.95 * min(max(self.smoothing, 0.0), 1.0)

    def reset(self) -> None:
        self._x = None
        self._y = None

    def smooth(self, x: float, y: float) -> Tuple[float, float]:
        if self._x is None or self._y is None:
            self._x, self._y = x, y
            return x, y
        a = self.alpha
        self._x = a * x + (1.0 - a) * self._x
        self._y = a * y + (1.0 - a) * self._y
        return self._x, self._y

    def smooth_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        return self.smooth(point[0], point[1])