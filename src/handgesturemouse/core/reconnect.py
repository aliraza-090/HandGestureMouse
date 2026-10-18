"""Camera reconnect backoff state machine.

Kept free of camera / GUI dependencies so the retry policy can be tested with a
fake clock.  The pipeline drives it: on a failed read it calls ``start()``,
re-checks ``due()`` each loop and calls ``record_attempt()`` before every
re-open attempt.  A successful read calls ``reset()``.
"""

import time
from typing import Callable, Optional


class ReconnectBackoff:
    """Retry every ``interval`` seconds, up to ``max_attempts`` times."""

    def __init__(
        self,
        max_attempts: int = 5,
        interval: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.interval = max(0.0, float(interval))
        self._clock = clock
        self._active = False
        self._attempts = 0
        self._next_at = 0.0

    # -- state -------------------------------------------------------------

    @property
    def active(self) -> bool:
        """True while a disconnect is being handled."""
        return self._active

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def exhausted(self) -> bool:
        return self._attempts >= self.max_attempts

    # -- transitions -------------------------------------------------------

    def start(self, now: Optional[float] = None) -> None:
        """Begin handling a disconnect (idempotent while already active)."""
        if self._active:
            return
        now = self._clock() if now is None else now
        self._active = True
        self._attempts = 0
        self._next_at = now + self.interval

    def due(self, now: Optional[float] = None) -> bool:
        """True when a reconnect attempt should be made right now."""
        if not self._active or self.exhausted:
            return False
        now = self._clock() if now is None else now
        return now >= self._next_at

    def record_attempt(self, now: Optional[float] = None) -> None:
        """Register that an attempt is being made and schedule the next one."""
        now = self._clock() if now is None else now
        self._attempts += 1
        self._next_at = now + self.interval

    def reset(self) -> None:
        self._active = False
        self._attempts = 0
        self._next_at = 0.0
