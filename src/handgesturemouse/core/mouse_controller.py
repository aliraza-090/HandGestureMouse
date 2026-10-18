"""Safe wrapper around PyAutoGUI mouse actions.

PyAutoGUI's fail-safe is kept enabled by default: moving the physical mouse
to any corner of the screen raises ``FailSafeException`` and the controller
releases all buttons and reports the emergency stop.
"""

import logging
import threading
from typing import Callable, Optional, Set, Tuple

try:  # pragma: no cover - import side effects
    import pyautogui as _pg

    _pg.FAILSAFE = True  # keep the built-in corner fail-safe active
except Exception:  # pragma: no cover - allows unit tests without pyautogui
    _pg = None

logger = logging.getLogger("handgesturemouse.mouse")

_EMERGENCY_CALLBACK: Set[Callable[[], None]] = set()


class MouseControllerError(Exception):
    """Base mouse controller error."""


class EmergencyStop(MouseControllerError):
    """Raised internally when the PyAutoGUI fail-safe engages."""


class MouseController:
    """Executes mouse actions with safety guarantees.

    ``pyautogui`` is injected so tests can supply a fake.  A fail-safe
    callback receives ``EmergencyStop`` and should switch the app into a safe
    (stopped) state.
    """

    def __init__(self, pyautogui=None) -> None:
        self._pg = pyautogui if pyautogui is not None else _pg
        self._lock = threading.Lock()
        self._held: Set[str] = set()
        self._fail_safe_callback: Optional[Callable[[EmergencyStop], None]] = None

    @property
    def pyautogui(self):
        return self._pg

    def set_fail_safe_callback(self, callback: Optional[Callable[[EmergencyStop], None]]) -> None:
        self._fail_safe_callback = callback

    def screen_size(self) -> Tuple[int, int]:
        if self._pg is None:
            raise MouseControllerError("PyAutoGUI is not available")
        return self._pg.size()

    def _handle_fail_safe(self, exc: BaseException) -> None:
        self.release_all()
        if self._fail_safe_callback is not None:
            try:
                self._fail_safe_callback(EmergencyStop(str(exc)))
            except Exception:  # pragma: no cover - defensive
                logger.exception("fail-safe callback raised")

    def move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        if self._pg is None:
            return
        try:
            self._pg.moveTo(int(x), int(y), duration=duration)
        except (self._pg.FailSafeException, Exception) as exc:
            if isinstance(exc, self._pg.FailSafeException):
                self._handle_fail_safe(exc)
            else:
                raise

    def left_click(self, x: int, y: int) -> None:
        self._click_at(x, y, "left")

    def right_click(self, x: int, y: int) -> None:
        self._click_at(x, y, "right")

    def _click_at(self, x: int, y: int, button: str) -> None:
        if self._pg is None:
            return
        try:
            self._pg.click(int(x), int(y), button=button)
        except (self._pg.FailSafeException, Exception) as exc:
            if isinstance(exc, self._pg.FailSafeException):
                self._handle_fail_safe(exc)
            else:
                raise

    def scroll(self, clicks: float) -> None:
        if self._pg is None:
            return
        current = self._pg.position()
        try:
            self._pg.scroll(int(clicks), x=current.x, y=current.y)
        except (self._pg.FailSafeException, Exception) as exc:
            if isinstance(exc, self._pg.FailSafeException):
                self._handle_fail_safe(exc)
            else:
                raise

    def start_drag(self, button: str = "left") -> None:
        if self._pg is None:
            return
        with self._lock:
            if button in self._held:
                return
            try:
                self._pg.mouseDown(button=button)
            except (self._pg.FailSafeException, Exception) as exc:
                if isinstance(exc, self._pg.FailSafeException):
                    self._handle_fail_safe(exc)
                    return
                raise
            self._held.add(button)

    def drag_move(self, x: int, y: int) -> None:
        self.move_to(x, y)

    def end_drag(self, button: str = "left") -> None:
        if self._pg is None:
            return
        with self._lock:
            if button not in self._held:
                return
            try:
                self._pg.mouseUp(button=button)
            except (self._pg.FailSafeException, Exception) as exc:
                if isinstance(exc, self._pg.FailSafeException):
                    self._handle_fail_safe(exc)
                    return
                raise
            self._held.discard(button)

    def release_all(self) -> None:
        """Release every held mouse button (call on stop, error, close)."""
        if self._pg is None:
            self._held.clear()
            return
        with self._lock:
            buttons = list(self._held)
        for button in buttons:
            try:
                self._pg.mouseUp(button=button)
            except Exception:
                logger.debug("could not release %s", button)
        with self._lock:
            self._held.clear()

    @property
    def held_buttons(self) -> Set[str]:
        with self._lock:
            return set(self._held)