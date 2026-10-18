"""Windows auto-start management via the per-user ``Run`` registry key.

Writes ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` so the app
starts when the user signs in.  This is intentionally best-effort: registry
access may be restricted by policy, so every entry point reports success or
failure instead of raising, and the rest of the application keeps working.

The registry module is injectable so unit tests can supply a fake ``winreg``.
"""

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger("handgesturemouse.autostart")

try:  # pragma: no cover - Windows only
    import winreg as _winreg
except Exception:  # pragma: no cover - non-Windows
    _winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "HandGestureMouse"


class AutostartError(Exception):
    """Raised only for programmer errors; runtime failures return False."""


def _project_root() -> str:
    # <project>/src/handgesturemouse/utils/autostart.py -> <project>
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )


def _find_pythonw() -> str:
    candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return candidate if os.path.isfile(candidate) else sys.executable


class AutostartManager:
    """Enable / disable auto-start and query its current state."""

    def __init__(
        self,
        app_name: str = VALUE_NAME,
        command: Optional[str] = None,
        winreg_module: Optional[object] = None,
    ) -> None:
        self.app_name = app_name
        self._command = command
        self._winreg = _winreg if winreg_module is None else winreg_module

    # -- capability --------------------------------------------------------

    def is_supported(self) -> bool:
        """True when a usable registry module is available (Windows)."""
        return self._winreg is not None

    # -- command -----------------------------------------------------------

    def build_command(self) -> str:
        """Return the command line stored in the Run key."""
        if self._command:
            return self._command
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        main_py = os.path.join(_project_root(), "main.py")
        return f'"{_find_pythonw()}" "{main_py}"'

    # -- registry ----------------------------------------------------------

    def is_enabled(self) -> bool:
        if self._winreg is None:
            return False
        wr = self._winreg
        try:
            key = wr.OpenKey(wr.HKEY_CURRENT_USER, RUN_KEY, 0, wr.KEY_READ)
        except FileNotFoundError:
            return False
        except OSError:
            return False
        try:
            value, _ = wr.QueryValueEx(key, self.app_name)
            return bool(value)
        except FileNotFoundError:
            return False
        except OSError:
            return False
        finally:
            try:
                wr.CloseKey(key)
            except Exception:
                pass

    def enable(self) -> bool:
        if self._winreg is None:
            return False
        wr = self._winreg
        try:
            key = wr.CreateKey(wr.HKEY_CURRENT_USER, RUN_KEY)
        except OSError as exc:
            logger.warning("could not open Run key for auto-start: %s", exc)
            return False
        try:
            wr.SetValueEx(key, self.app_name, 0, wr.REG_SZ, self.build_command())
            logger.info("auto-start enabled")
            return True
        except OSError as exc:
            logger.warning("could not write auto-start value: %s", exc)
            return False
        finally:
            try:
                wr.CloseKey(key)
            except Exception:
                pass

    def disable(self) -> bool:
        if self._winreg is None:
            return False
        wr = self._winreg
        try:
            key = wr.OpenKey(wr.HKEY_CURRENT_USER, RUN_KEY, 0, wr.KEY_SET_VALUE)
        except FileNotFoundError:
            return True
        except OSError as exc:
            logger.warning("could not open Run key to disable auto-start: %s", exc)
            return False
        try:
            try:
                wr.DeleteValue(key, self.app_name)
            except FileNotFoundError:
                pass
            logger.info("auto-start disabled")
            return True
        except OSError as exc:
            logger.warning("could not delete auto-start value: %s", exc)
            return False
        finally:
            try:
                wr.CloseKey(key)
            except Exception:
                pass

    def set_enabled(self, enabled: bool) -> bool:
        return self.enable() if enabled else self.disable()
