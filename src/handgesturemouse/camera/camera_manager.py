"""Webcam capture management.

Owns a single OpenCV ``VideoCapture``.  Only one controller thread may open
the camera at a time; the GUI never reads frames directly.
"""

import logging
import threading
from typing import List, Optional, Tuple

logger = logging.getLogger("handgesturemouse.camera")

MAX_CAMERAS_SCAN = 8

# Keep the driver's internal queue tiny so ``read()`` always returns the newest
# frame instead of a stale one, and give slow USB cameras room to respond
# before OpenCV reports a failure (reduces spurious "device removed").
BUFFER_SIZE = 1
OPEN_TIMEOUT_MS = 5000
READ_TIMEOUT_MS = 5000


class CameraError(Exception):
    """Raised when the camera cannot be opened or captured."""


class CameraManager:
    """Open / read / release a webcam and detect disconnection."""

    def __init__(self, backend: Optional[object] = None, scan_limit: int = MAX_CAMERAS_SCAN) -> None:
        """``backend`` is injectable for tests (defaults to cv2.VideoCapture)."""
        self._backend = backend
        self._scan_limit = int(scan_limit)
        self._cap = None
        self._index = None
        self._lock = threading.Lock()
        self._read_count = 0
        self._last_read_ok = False

    def _build_capture(self, index: int):
        if self._backend is not None:
            return self._backend(index)
        import cv2

        cap = cv2.VideoCapture(index)
        self._apply_capture_options(cap, cv2)
        return cap

    @staticmethod
    def _apply_capture_options(cap, cv2_module) -> None:
        """Best-effort tuning: single-frame buffer + generous timeouts."""
        options = (
            ("CAP_PROP_BUFFERSIZE", BUFFER_SIZE),
            ("CAP_PROP_OPEN_TIMEOUT_MSEC", OPEN_TIMEOUT_MS),
            ("CAP_PROP_READ_TIMEOUT_MSEC", READ_TIMEOUT_MS),
        )
        for name, value in options:
            prop = getattr(cv2_module, name, None)
            if prop is None:
                continue
            try:
                cap.set(prop, value)
            except Exception:
                logger.debug("could not set %s", name, exc_info=True)

    def list_cameras(self) -> List[int]:
        """Probe camera indices and return the ones that open."""
        found: List[int] = []
        for index in range(self._scan_limit):
            cap = None
            try:
                cap = self._build_capture(index)
                if cap is not None and cap.isOpened():
                    found.append(index)
            except Exception:
                logger.debug("camera %d probe failed", index, exc_info=True)
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
        return found

    def open(self, index: int) -> None:
        index = int(index)
        with self._lock:
            # Already streaming the requested camera: do not reopen it (avoids
            # needless device resets and the flicker/stutter they cause).
            if self._cap is not None and self._cap.isOpened() and self._index == index:
                return
            self._release_locked()
            try:
                cap = self._build_capture(index)
            except Exception as exc:
                raise CameraError(f"could not open camera {index}: {exc}") from exc
            if cap is None or not cap.isOpened():
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
                raise CameraError(f"camera {index} could not be opened (in use or absent)")
            self._cap = cap
            self._index = index
            logger.info("camera %d opened", index)

    def read(self) -> Optional[object]:
        """Return a BGR frame or None when the camera is unavailable."""
        with self._lock:
            if self._cap is None:
                return None
            try:
                frame = None
                ok = False
                # Try to read once (compatible with test fakes)
                try:
                    ok, frame = self._cap.read()
                except Exception as exc:
                    logger.warning("camera read failed: %s", exc)
                    return None
                if ok and frame is not None:
                    self._read_count += 1
                    self._last_read_ok = True
                    return frame
                # If failed, try again once
                try:
                    ok, frame = self._cap.read()
                except Exception as exc:
                    logger.warning("camera read failed: %s", exc)
                    return None
                if not ok or frame is None:
                    return None
                self._read_count += 1
                self._last_read_ok = True
                return frame
            except Exception as exc:
                logger.warning("camera read failed: %s", exc)
                return None

    def set_open_dimensions(self, width: int, height: int) -> None:
        with self._lock:
            if self._cap is None:
                return
            try:
                self._cap.set(3, width)
                self._cap.set(4, height)
            except Exception:
                logger.debug("could not set camera resolution", exc_info=True)

    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    def _release_locked(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                logger.debug("camera release failed", exc_info=True)
        self._cap = None
        self._index = None

    def release(self) -> None:
        with self._lock:
            self._release_locked()
        logger.info("camera released")