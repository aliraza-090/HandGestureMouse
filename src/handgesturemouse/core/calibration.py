"""Gesture calibration: tune the pinch thresholds to a specific hand/camera.

The session is metric-based (it consumes already-computed pinch ratios and hand
scale) so it has no MediaPipe dependency and is fully unit-testable.  The
pipeline computes the metrics from live landmarks and feeds them in.

Workflow:
    1. ``open``   - the user holds the hand open; we record the hand scale and
       bounding box to understand the working distance / hand size.
    2. ``pinch``  - the user makes a natural pinch; we record pinch ratios and
       derive thresholds that sit comfortably between "closed" and "open".
"""

import statistics
from dataclasses import dataclass, field
from typing import List, Optional

STEP_OPEN = "open"
STEP_PINCH = "pinch"
STEP_DONE = "done"

# Safe bounds for the derived values (mirror config.defaults ranges).
_PINCH_MIN, _PINCH_MAX = 0.15, 0.60
_HOLD_MIN, _HOLD_MAX = 0.20, 0.70


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class CalibrationResult:
    pinch_threshold: float
    pinch_hold_threshold: float
    open_samples: int
    pinch_samples: int
    hand_scale: float = 0.0
    box_width: float = 0.0
    box_height: float = 0.0
    ok: bool = False
    message: str = ""

    def as_settings(self) -> dict:
        """The subset of settings to persist."""
        return {
            "pinch_threshold": round(self.pinch_threshold, 3),
            "pinch_hold_threshold": round(self.pinch_hold_threshold, 3),
        }


@dataclass
class CalibrationSession:
    """Collects samples across the two calibration steps."""

    min_open: int = 5
    min_pinch: int = 8
    step: str = STEP_OPEN
    _scales: List[float] = field(default_factory=list)
    _box_w: List[float] = field(default_factory=list)
    _box_h: List[float] = field(default_factory=list)
    _pinches: List[float] = field(default_factory=list)

    # -- state -------------------------------------------------------------

    def reset(self) -> None:
        self.step = STEP_OPEN
        self._scales.clear()
        self._box_w.clear()
        self._box_h.clear()
        self._pinches.clear()

    @property
    def open_samples(self) -> int:
        return len(self._scales)

    @property
    def pinch_samples(self) -> int:
        return len(self._pinches)

    def can_advance(self) -> bool:
        if self.step == STEP_OPEN:
            return self.open_samples >= self.min_open
        if self.step == STEP_PINCH:
            return self.pinch_samples >= self.min_pinch
        return False

    def advance(self) -> str:
        """Move to the next step (only when enough samples were collected)."""
        if not self.can_advance():
            return self.step
        if self.step == STEP_OPEN:
            self.step = STEP_PINCH
        elif self.step == STEP_PINCH:
            self.step = STEP_DONE
        return self.step

    def add(self, sample: dict) -> bool:
        """Route a metric sample to the current step.

        ``sample`` has ``hand_scale``/``box_width``/``box_height`` for the open
        step and ``pinch_ratio`` for the pinch step.  Returns True when the
        sample was accepted.
        """
        if self.step == STEP_OPEN:
            if "hand_scale" not in sample:
                return False
            self.add_open(
                hand_scale=float(sample.get("hand_scale", 0.0)),
                box_width=float(sample.get("box_width", 0.0)),
                box_height=float(sample.get("box_height", 0.0)),
            )
            return True
        if self.step == STEP_PINCH:
            if "pinch_ratio" not in sample:
                return False
            self.add_pinch(float(sample["pinch_ratio"]))
            return True
        return False

    def add_open(self, hand_scale: float, box_width: float = 0.0, box_height: float = 0.0) -> None:
        if hand_scale <= 0:
            return
        self._scales.append(float(hand_scale))
        self._box_w.append(float(box_width))
        self._box_h.append(float(box_height))

    def add_pinch(self, pinch_ratio: float) -> None:
        if pinch_ratio <= 0:
            return
        self._pinches.append(float(pinch_ratio))

    # -- result ------------------------------------------------------------

    def result(self) -> CalibrationResult:
        ok = self.open_samples >= self.min_open and self.pinch_samples >= self.min_pinch
        if not ok:
            return CalibrationResult(
                pinch_threshold=0.30,
                pinch_hold_threshold=0.36,
                open_samples=self.open_samples,
                pinch_samples=self.pinch_samples,
                ok=False,
                message="Not enough samples. Hold your hand open, then pinch, and record each step.",
            )

        mean_pinch = statistics.fmean(self._pinches)
        spread = statistics.pstdev(self._pinches) if len(self._pinches) > 1 else 0.0
        # Threshold sits above the observed closed-hand ratio with a safety
        # margin, so ordinary pinches register but near-touches do not.
        margin = max(0.05, 0.8 * spread)
        pinch_threshold = _clamp(mean_pinch + margin, _PINCH_MIN, _PINCH_MAX)
        hold = _clamp(pinch_threshold + 0.08, pinch_threshold + 0.02, _HOLD_MAX)

        return CalibrationResult(
            pinch_threshold=pinch_threshold,
            pinch_hold_threshold=hold,
            open_samples=self.open_samples,
            pinch_samples=self.pinch_samples,
            hand_scale=statistics.fmean(self._scales),
            box_width=statistics.fmean(self._box_w),
            box_height=statistics.fmean(self._box_h),
            ok=True,
            message="Calibration complete.",
        )
