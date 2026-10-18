"""Optional Windows system-tray integration backed by ``pystray``.

The tray is a convenience layer only: if ``pystray`` is missing or the tray
cannot be created, the application must keep working exactly as before.  All
menu actions are forwarded to a single ``on_action`` callback which the
:class:`~handgesturemouse.app.Application` marshals onto the Tk main thread.
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger("handgesturemouse.tray")


def tray_available() -> bool:
    """Return True when ``pystray`` can be imported."""
    try:
        import pystray  # noqa: F401
    except Exception:  # pragma: no cover - depends on environment
        return False
    try:
        import PIL.Image  # noqa: F401
    except Exception:  # pragma: no cover - Pillow is a hard dependency
        return False
    return True


def _fallback_image():
    """Build a small icon when the bundled PNG cannot be loaded."""
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=14, fill=(79, 140, 255, 255))
    draw.ellipse([20, 18, 44, 42], fill=(232, 236, 244, 255))
    return image


class TrayIcon:
    """Thin wrapper around a ``pystray.Icon`` with graceful degradation."""

    def __init__(
        self,
        title: str,
        image_path: Optional[str],
        on_action: Callable[[str], None],
        state_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        self._title = title
        self._image_path = image_path
        self._on_action = on_action
        self._state_provider = state_provider or (lambda: "stopped")
        self._icon = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        """Create and show the tray icon. Returns False on any failure."""
        if self._icon is not None:
            return True
        try:
            from pystray import Icon, Menu, MenuItem
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("system tray unavailable: %s", exc)
            return False

        try:
            image = self._load_image()
            menu = Menu(
                MenuItem("Show window", self._make_callback("show"), default=True),
                MenuItem("Hide window", self._make_callback("hide")),
                Menu.SEPARATOR,
                MenuItem(self._pause_label, self._make_callback("toggle")),
                Menu.SEPARATOR,
                MenuItem("Exit HandGestureMouse", self._make_callback("exit")),
            )
            self._icon = Icon(self._title, image, self._title, menu)
            self._icon.run_detached()
            logger.info("system tray icon started")
            return True
        except Exception as exc:
            logger.warning("system tray initialisation failed: %s", exc)
            self._icon = None
            return False

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:  # pragma: no cover - defensive
            logger.debug("error stopping tray icon", exc_info=True)
        finally:
            self._icon = None

    def update(self) -> None:
        """Refresh the tray menu (e.g. after a state change)."""
        if self._icon is None:
            return
        try:
            self._icon.update_menu()
        except Exception:  # pragma: no cover - defensive
            logger.debug("could not update tray menu", exc_info=True)

    def notify(self, message: str, title: Optional[str] = None) -> bool:
        """Show a balloon/toast notification; returns False when unavailable."""
        if self._icon is None:
            return False
        notify = getattr(self._icon, "notify", None)
        if notify is None:
            return False
        try:
            notify(message, title or self._title)
            return True
        except Exception:  # pragma: no cover - depends on platform/backend
            logger.debug("tray notification failed", exc_info=True)
            return False

    @property
    def is_running(self) -> bool:
        return self._icon is not None

    # -- internals ---------------------------------------------------------

    def _load_image(self):
        if self._image_path:
            try:
                from PIL import Image

                return Image.open(self._image_path)
            except Exception:
                logger.debug("could not load tray image %s", self._image_path, exc_info=True)
        return _fallback_image()

    def _make_callback(self, action: str):
        def _callback(icon, item):  # pystray passes (icon, item)
            try:
                self._on_action(action)
            except Exception:  # pragma: no cover - never break the tray thread
                logger.exception("tray action %r failed", action)

        return _callback

    def _pause_label(self, item) -> str:
        state = "stopped"
        try:
            state = self._state_provider()
        except Exception:  # pragma: no cover - defensive
            pass
        return "Resume tracking" if state == "paused" else "Pause tracking"
