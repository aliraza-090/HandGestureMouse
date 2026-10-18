"""Non-blocking audio feedback for gestures.

Uses the Windows-native ``winsound`` module when available and degrades to a
silent no-op everywhere else (or when the ``winsound`` backend is missing), so
importing this module never breaks the app on a non-Windows build.

Sounds are played asynchronously (``SND_ASYNC``) so the pipeline thread is
never blocked by audio playback.
"""

import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger("handgesturemouse.feedback")

try:  # pragma: no cover - platform specific import
    import winsound as _winsound
except Exception:  # pragma: no cover - non-Windows / stripped Python
    _winsound = None

# Friendly system sound aliases (see winsound docs).
DEFAULT_ALIASES: Dict[str, str] = {
    "left_click": "SystemAsterisk",
    "right_click": "SystemExclamation",
    "drag": "SystemDefault",
    "emergency": "SystemHand",
    "calibrate": "SystemQuestion",
}


class AudioFeedback:
    """Plays short system sounds for gestures when enabled.

    ``backend`` is injectable for tests; when it is ``None`` (e.g. off Windows)
    every call is a harmless no-op.
    """

    def __init__(
        self,
        enabled: bool = True,
        backend: Optional[object] = None,
        aliases: Optional[Dict[str, str]] = None,
    ) -> None:
        self._backend = _winsound if backend is None else backend
        self._aliases = dict(aliases or DEFAULT_ALIASES)
        self._lock = threading.Lock()
        self.enabled = bool(enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def play(self, event: str) -> None:
        """Play the sound registered for ``event`` (never raises)."""
        if not self.enabled or self._backend is None:
            return
        alias = self._aliases.get(event)
        if alias is None:
            return
        flags = getattr(self._backend, "SND_ASYNC", 1) | getattr(self._backend, "SND_ALIAS", 0x10000)
        try:
            with self._lock:
                self._backend.PlaySound(alias, flags)
        except Exception:  # pragma: no cover - audio must never crash tracking
            logger.debug("audio feedback failed for %s", event, exc_info=True)

    # Convenience wrappers -------------------------------------------------

    def left_click(self) -> None:
        self.play("left_click")

    def right_click(self) -> None:
        self.play("right_click")

    def drag(self) -> None:
        self.play("drag")

    def emergency(self) -> None:
        self.play("emergency")

    def calibrate(self) -> None:
        self.play("calibrate")
