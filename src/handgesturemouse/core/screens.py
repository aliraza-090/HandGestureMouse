"""Multi-monitor discovery and display-region resolution.

Uses the Win32 ``EnumDisplayMonitors`` / ``GetMonitorInfoW`` API via ``ctypes``
so there is no extra dependency and everything stays offline.  When the API is
unavailable (non-Windows, or a stripped environment) the module degrades to a
single synthetic primary monitor.

The resolution helpers are pure functions over a list of :class:`Monitor`
objects, so they are fully unit-testable without any display hardware.
"""

import ctypes
import logging
from dataclasses import dataclass, replace
from typing import List, Optional

logger = logging.getLogger("handgesturemouse.screens")

MONITORINFOF_PRIMARY = 0x1
DISPLAY_CHOICES = ("primary", "secondary", "span")


@dataclass(frozen=True)
class Monitor:
    index: int
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    @property
    def label(self) -> str:
        kind = "Primary" if self.primary else f"Display {self.index + 1}"
        return f"{kind} ({self.width}x{self.height})"


@dataclass(frozen=True)
class DisplayRegion:
    """A physical screen rectangle the cursor is mapped into."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


def monitors_from_system() -> List[Monitor]:
    """Enumerate connected monitors. Returns [] when enumeration fails."""
    try:
        user32 = ctypes.windll.user32
    except Exception:  # pragma: no cover - non-Windows
        return []

    found: List[Monitor] = []

    def _callback(hmonitor, hdc, lprect, lparam):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        try:
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                r = info.rcMonitor
                found.append(
                    Monitor(
                        index=len(found),
                        x=int(r.left),
                        y=int(r.top),
                        width=int(r.right - r.left),
                        height=int(r.bottom - r.top),
                        primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                    )
                )
        except Exception:  # pragma: no cover - defensive
            logger.debug("GetMonitorInfoW failed", exc_info=True)
        return 1

    try:
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(_RECT),
            ctypes.c_void_p,
        )
        user32.EnumDisplayMonitors(0, 0, callback_type(_callback), 0)
    except Exception:  # pragma: no cover - defensive
        logger.debug("EnumDisplayMonitors failed", exc_info=True)
        return []

    if not found:
        return []
    # Primaries first, then left-to-right / top-to-bottom.
    found.sort(key=lambda m: (not m.primary, m.y, m.x))
    return [replace(m, index=i) for i, m in enumerate(found)]


def list_monitors() -> List[Monitor]:
    """Public enumeration helper with a single-monitor fallback."""
    monitors = monitors_from_system()
    if monitors:
        return monitors
    return [Monitor(index=0, x=0, y=0, width=1920, height=1080, primary=True)]


def virtual_span(monitors: List[Monitor]) -> DisplayRegion:
    """Bounding box covering every monitor (the 'span' option)."""
    x = min(m.x for m in monitors)
    y = min(m.y for m in monitors)
    right = max(m.x + m.width for m in monitors)
    bottom = max(m.y + m.height for m in monitors)
    return DisplayRegion(x, y, right - x, bottom - y)


def resolve_region(
    selection: str = "primary",
    monitors: Optional[List[Monitor]] = None,
) -> DisplayRegion:
    """Resolve a display selection (``primary``/``secondary``/``span``/index)."""
    monitors = list(monitors) if monitors is not None else monitors_from_system()
    if not monitors:
        return DisplayRegion(0, 0, 0, 0)

    sel = (selection or "primary").strip().lower()
    primary = next((m for m in monitors if m.primary), monitors[0])

    if sel == "span":
        return virtual_span(monitors)
    if sel in ("primary", "default"):
        return DisplayRegion(primary.x, primary.y, primary.width, primary.height)
    if sel == "secondary":
        others = [m for m in monitors if not m.primary]
        target = others[0] if others else primary
        return DisplayRegion(target.x, target.y, target.width, target.height)
    try:
        idx = int(sel)
    except ValueError:
        idx = -1
    if 0 <= idx < len(monitors):
        m = monitors[idx]
        return DisplayRegion(m.x, m.y, m.width, m.height)
    return DisplayRegion(primary.x, primary.y, primary.width, primary.height)
