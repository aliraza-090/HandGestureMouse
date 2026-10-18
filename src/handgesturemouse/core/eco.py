"""Eco / battery-saver throttling.

Two cooperating pieces:

* :class:`EcoThrottle` decides the loop interval.  While a hand is visible (or
  the idle timeout has not elapsed) it returns the active-rate interval; after
  ``idle_seconds`` without a hand it drops to the slow ``eco_fps`` rate.  As
  soon as a hand is seen again the very next call restores the active rate.
* :class:`MotionDetector` provides a cheap, MediaPipe-free wake signal: while
  throttled, a significant frame-to-frame difference forces an immediate full
  processing pass so re-entry is detected with sub-frame latency.

Both classes are pure logic and deterministic so they can be unit tested
without a camera.
"""

import time
from typing import Callable, Optional

try:  # numpy is a hard dependency, but keep a safe fallback for importability
    import numpy as _np
except Exception:  # pragma: no cover - numpy is always installed in practice
    _np = None


class EcoThrottle:
    """Compute the pipeline loop interval for the eco/battery-saver policy."""

    def __init__(
        self,
        enabled: bool = True,
        idle_seconds: float = 45.0,
        eco_fps: float = 5.0,
        active_fps: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.enabled = bool(enabled)
        self.idle_seconds = max(0.0, float(idle_seconds))
        self.eco_fps = max(1.0, float(eco_fps))
        self.active_fps = max(1.0, float(active_fps))
        self._clock = clock
        self._last_hand: Optional[float] = None
        self._active = False

    @property
    def active(self) -> bool:
        """True while tracking is throttled due to inactivity."""
        return self._active

    def configure(
        self,
        enabled: Optional[bool] = None,
        idle_seconds: Optional[float] = None,
        eco_fps: Optional[float] = None,
        active_fps: Optional[float] = None,
    ) -> None:
        if enabled is not None:
            self.enabled = bool(enabled)
        if idle_seconds is not None:
            self.idle_seconds = max(0.0, float(idle_seconds))
        if eco_fps is not None:
            self.eco_fps = max(1.0, float(eco_fps))
        if active_fps is not None:
            self.active_fps = max(1.0, float(active_fps))

    def interval(self, hand_present: bool, now: Optional[float] = None) -> float:
        """Return the seconds to sleep before the next loop iteration."""
        now = self._clock() if now is None else now
        if not self.enabled:
            self._active = False
            return 1.0 / self.active_fps
        if hand_present:
            self._last_hand = now
            self._active = False
            return 1.0 / self.active_fps
        if self._last_hand is None:
            # First idle frame: start the idle clock, stay at full rate.
            self._last_hand = now
            self._active = False
            return 1.0 / self.active_fps
        if now - self._last_hand >= self.idle_seconds:
            self._active = True
            return 1.0 / self.eco_fps
        self._active = False
        return 1.0 / self.active_fps

    def reset(self) -> None:
        self._last_hand = None
        self._active = False


class MotionDetector:
    """Cheap frame-difference motion test used to wake the eco throttle early."""

    def __init__(self, threshold: float = 2.0, sample: int = 64) -> None:
        self.threshold = float(threshold)
        self.sample = max(4, int(sample))
        self._prev = None

    def reset(self) -> None:
        self._prev = None

    def _thumbnail(self, frame):
        if _np is None or frame is None:
            return None
        arr = _np.asarray(frame)
        if arr.ndim == 3:
            arr = arr[..., :3].mean(axis=2)
        if arr.ndim != 2 or arr.size == 0:
            return None
        step_y = max(1, arr.shape[0] // self.sample)
        step_x = max(1, arr.shape[1] // self.sample)
        return arr[::step_y, ::step_x].astype("float32")

    def update(self, frame) -> bool:
        """Feed a frame; return True when meaningful motion is detected."""
        thumb = self._thumbnail(frame)
        if thumb is None:
            return False
        if self._prev is None or self._prev.shape != thumb.shape:
            self._prev = thumb
            return False
        diff = float(_np.mean(_np.abs(thumb - self._prev))) if _np is not None else 0.0
        self._prev = thumb
        return diff >= self.threshold
