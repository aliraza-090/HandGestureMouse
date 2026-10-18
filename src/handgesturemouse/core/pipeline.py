"""Background pipeline tying camera -> tracking -> gesture -> mouse together.

Runs in a dedicated thread so the GUI never blocks on camera reads or
MediaPipe inference.  The GUI polls :class:`PipelineEvent` objects off a
thread-safe queue and applies them on the Tkinter thread.
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..utils.logger import get_logger
from .calibration import STEP_DONE, STEP_OPEN, STEP_PINCH, CalibrationSession
from .coordinate_mapper import CoordinateMapper
from .cursor_smoothing import CursorSmoother
from .eco import EcoThrottle, MotionDetector
from .geometry import hand_scale, pinch_index
from .gesture_controller import GestureController, MouseCommand
from .hand_tracker import HandTracker
from .mouse_controller import MouseController
from .reconnect import ReconnectBackoff
from .screens import DisplayRegion, resolve_region

logger = get_logger("pipeline")

MAX_QUEUE = 8
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
JPEG_QUALITY = 72

# Crash-recovery policy: retry every 2s, up to 5 times.
RECONNECT_INTERVAL = 2.0
RECONNECT_MAX_ATTEMPTS = 5
# Tolerate a few consecutive missed frames before declaring the camera lost:
# single delayed frames (OS scheduling, brief USB hiccups) must not trigger a
# reconnect storm.
CAMERA_LOSS_THRESHOLD = 3
# While throttled in eco mode we still poll cheaply for motion so a hand
# re-entering the frame restores full-rate tracking within ~40ms.
ECO_WAKE_POLL = 0.04

# High-contrast HUD colours (BGR) per detected pose.
HUD_COLORS = {
    "move": (0, 200, 0),
    "scroll": (255, 180, 0),
    "pinch": (0, 215, 215),
    "right-pinch": (0, 140, 255),
    "open": (200, 200, 200),
}
HUD_NO_HAND = (120, 120, 120)


@dataclass
class PipelineEvent:
    """Message emitted from the pipeline thread to the GUI thread."""

    kind: str  # status|frame|error|emergency|state
    payload: Dict[str, Any] = field(default_factory=dict)


class PipelineWorker(threading.Thread):
    """Owns the capture / inference / action loop."""

    def __init__(
        self,
        camera,
        tracker: HandTracker,
        mouse: MouseController,
        gesture: GestureController,
        settings_provider,
        event_queue: queue.Queue,
        stop_event: threading.Event,
        audio=None,
    ) -> None:
        super().__init__(name="handgesturemouse-pipeline", daemon=True)
        self.camera = camera
        self.tracker = tracker
        self.mouse = mouse
        self.gesture = gesture
        self.settings_provider = settings_provider
        self.events = event_queue
        self._stop = stop_event
        self._audio = audio

        self._mouse_enabled = False
        self._state = "stopped"  # stopped | running | paused

        self._settings: Dict[str, object] = {}
        self._mapper = CoordinateMapper(1920, 1080)
        self._smoother = CursorSmoother(0.5)
        self._region = DisplayRegion(0, 0, 1920, 1080)
        self._fps = 0.0
        self._camera_failures = 0
        self._camera_note = ""

        # Eco / battery saver and crash-recovery helpers.
        self._eco = EcoThrottle(enabled=True, idle_seconds=45, eco_fps=5, active_fps=30)
        self._motion = MotionDetector()
        self._backoff = ReconnectBackoff(
            max_attempts=RECONNECT_MAX_ATTEMPTS, interval=RECONNECT_INTERVAL
        )
        self._reconnecting = False

        # Gesture calibration session (driven by the settings wizard).
        self._calib: Optional[CalibrationSession] = None
        self._calib_active = False

        # fail-safe: any PyAutoGUI corner fail-safe stops the virtual mouse
        self.mouse.set_fail_safe_callback(self._on_fail_safe)

        self._try_configure()

    # -- public control interface ---------------------------------------------

    def start_service(self) -> None:
        """Begin or resume mouse control (camera continues either way)."""
        self._mouse_enabled = True
        self._post_state("running")

    def pause_service(self) -> None:
        """Pause mouse control but keep tracking the hand."""
        self._mouse_enabled = False
        self._release_all()
        self.gesture.reset()
        self._post_state("paused")

    def stop_service(self) -> None:
        """Fully stop mouse control and release buttons."""
        self._mouse_enabled = False
        self.gesture.reset()
        self._release_all()
        self._smoother.reset()
        self._post_state("stopped")

    def emergency_stop(self) -> None:
        self.stop_service()
        self._post_state("stopped")

    @property
    def mouse_enabled(self) -> bool:
        return self._mouse_enabled

    def request_stop(self) -> None:
        self._stop.set()

    # -- configuration ---------------------------------------------------------

    def _try_configure(self) -> None:
        prev = self._settings
        cfg = self.settings_provider.as_dict()
        self._settings.update(cfg)
        self.gesture.refresh(cfg)

        self.tracker.set_config(
            num_hands=int(cfg.get("num_hands", 1)),
            min_detection_confidence=float(cfg.get("detection_confidence", 0.5)),
        )

        camera_index = int(cfg.get("camera_index", 0))
        if self.camera.is_open() and "camera_index" in cfg and int(prev.get("camera_index", -1)) != camera_index:
            try:
                self.open_camera()
            except Exception as exc:
                self._post_error(str(exc))

        width = int(cfg.get("screen_width") or 0)
        height = int(cfg.get("screen_height") or 0)
        if width > 0 and height > 0:
            # Explicit override: treat the whole screen as a single region.
            self._region = DisplayRegion(0, 0, width, height)
        else:
            region = resolve_region(str(cfg.get("target_display", "primary")))
            if region.width <= 0 or region.height <= 0:
                try:
                    screen_w, screen_h = self.mouse.screen_size()
                except Exception:
                    screen_w, screen_h = 1920, 1080
                region = DisplayRegion(0, 0, screen_w, screen_h)
            self._region = region

        self._mapper.update(
            self._region.width,
            self._region.height,
            dead_zone=float(cfg.get("mouse_smoothing_deade_zone", 0.0)),
            sensitivity=float(cfg.get("cursor_sensitivity", 1.0)),
        )
        self._smoother.smoothing = float(cfg.get("cursor_smoothing", 0.5))

        # Eco / battery saver.
        self._eco.configure(
            enabled=bool(cfg.get("eco_mode", True)),
            idle_seconds=float(cfg.get("eco_idle_seconds", 45)),
            eco_fps=float(cfg.get("eco_fps", 5)),
            active_fps=float(cfg.get("max_fps", 30)),
        )

        # Audio feedback.
        if self._audio is not None:
            try:
                self._audio.set_enabled(bool(cfg.get("enable_audio_feedback", True)))
            except Exception:
                pass

        # Keep the camera in the desired state when the setting is toggled.
        if bool(cfg.get("auto_open_camera", True)) and not self.camera.is_open():
            self.open_camera()

    def apply_settings(self) -> None:
        self._try_configure()

    def open_camera(self) -> None:
        if self.camera.is_open():
            return
        index = int(self._settings.get("camera_index", 0))
        try:
            self.camera.open(index)
            self.camera.set_open_dimensions(FRAME_WIDTH * 2, FRAME_HEIGHT * 2)
            self._camera_note = "Camera connected"
            self._post_status(hand=False)
        except Exception as exc:
            self._post_error(str(exc))

    # -- calibration (gesture wizard) -----------------------------------------

    def start_calibration(self) -> None:
        """Begin a fresh calibration session (collection happens in the loop)."""
        self._calib = CalibrationSession()
        self._calib_active = True
        self._publish_calibration()

    def cancel_calibration(self) -> None:
        self._calib = None
        self._calib_active = False

    @property
    def calibrating(self) -> bool:
        return self._calib_active

    def advance_calibration(self) -> None:
        """Move the session to the next step once enough samples exist."""
        session = self._calib
        if session is None:
            return
        step = session.advance()
        if step == STEP_DONE:
            result = session.result()
            self._calib = None
            self._calib_active = False
            self._publish(
                "calibration_result",
                pinch_threshold=result.pinch_threshold,
                pinch_hold_threshold=result.pinch_hold_threshold,
                ok=result.ok,
                message=result.message,
                open_samples=result.open_samples,
                pinch_samples=result.pinch_samples,
            )
        else:
            self._publish_calibration()

    def _publish_calibration(self) -> None:
        session = self._calib
        if session is None:
            return
        self._publish(
            "calibration",
            step=session.step,
            open_samples=session.open_samples,
            pinch_samples=session.pinch_samples,
            ready=session.can_advance(),
        )

    def _feed_calibration(self, landmarks) -> None:
        session = self._calib
        if not self._calib_active or session is None or not landmarks:
            return
        if session.step == STEP_OPEN:
            xs = [p[0] for p in landmarks]
            ys = [p[1] for p in landmarks]
            session.add_open(
                hand_scale(landmarks),
                max(xs) - min(xs),
                max(ys) - min(ys),
            )
        elif session.step == STEP_PINCH:
            session.add_pinch(pinch_index(landmarks))
        self._publish_calibration()

    # -- feedback -------------------------------------------------------------

    def _feedback(self, event: str) -> None:
        """Play an audio cue and post a HUD flash for a gesture (never raises)."""
        if self._audio is not None:
            try:
                self._audio.play(event)
            except Exception:
                logger.debug("audio feedback failed", exc_info=True)
        self._publish("feedback", action=event)



    def _publish(self, kind: str, **payload) -> None:
        try:
            self.events.put_nowait(PipelineEvent(kind=kind, payload=payload))
        except queue.Full:
            pass  # the GUI drains the queue promptly; old frames may drop

    def _post_status(self, hand: bool = False, gesture: str = "", command: str = "", **extra) -> None:
        self._publish(
            "status",
            camera_open=self.camera.is_open(),
            hand=hand,
            gesture=gesture,
            command=command,
            fps=round(self._fps, 1),
            mouse_enabled=self._mouse_enabled,
            camera_note=self._camera_note,
            **extra,
        )

    def _post_state(self, state: str) -> None:
        self._state = state
        self._publish("state", state=state)

    def _post_error(self, message: str) -> None:
        self._publish("error", message=message)

    # -- fail-safe ----------------------------------------------------

    def _on_fail_safe(self, exc) -> None:
        logger.warning("fail-safe triggered: %s", exc)
        self._mouse_enabled = False
        self._release_all()
        self._feedback("emergency")
        self._publish("emergency", message=str(exc))
        self._post_state("stopped")

    def _release_all(self) -> None:
        try:
            self.mouse.release_all()
        except Exception:
            logger.exception("error releasing mouse buttons")

    # -- helpers --------------------------------------------------------------

    def _grab_frame(self):
        frame = self.camera.read()
        if frame is None:
            self._camera_failures += 1
            if self._camera_failures == 1:
                # Zero stuck input: release the moment frames stop arriving,
                # even before we are sure the device is really gone.
                logger.debug("camera frame missed; releasing held input")
                self._release_all()
            if self._camera_failures >= CAMERA_LOSS_THRESHOLD:
                self._handle_camera_loss()
            return None
        if self._reconnecting:
            self._on_camera_recovered()
        self._camera_failures = 0
        if self._settings.get("mirror_input", True):
            try:
                import cv2

                frame = cv2.flip(frame, 1)
            except Exception:
                pass
        return frame

    def _handle_camera_loss(self) -> None:
        """React to a dropped frame: release input, then retry with backoff."""
        if not self._backoff.active:
            logger.warning("camera connection lost; starting reconnect backoff")
            self._backoff.start()
            self._reconnecting = True
            self._camera_note = "Camera disconnected - reconnecting..."
            # Zero stuck input: never leave a button held while disconnected.
            self._release_all()
            self._eco.reset()
            self._motion.reset()
            self._post_status(hand=False)
            self._publish("camera_state", state="disconnected")

        if self._backoff.exhausted:
            return

        now = time.monotonic()
        if not self._backoff.due(now):
            return

        self._backoff.record_attempt(now)
        attempt = self._backoff.attempts
        logger.info("camera reconnect attempt %d/%d", attempt, self._backoff.max_attempts)
        self._camera_note = (
            f"Camera disconnected - reconnecting ({attempt}/{self._backoff.max_attempts})..."
        )
        self._post_status(hand=False)
        self._publish(
            "camera_state",
            state="reconnecting",
            attempt=attempt,
            max_attempts=self._backoff.max_attempts,
        )
        try:
            self.camera.release()
        except Exception:
            pass
        self.open_camera()
        if self._backoff.exhausted and not self.camera.is_open():
            self._camera_note = "Camera disconnected - retries exhausted."
            self._post_status(hand=False)
            self._publish("camera_state", state="failed")

    def _on_camera_recovered(self) -> None:
        logger.info("camera reconnected")
        self._backoff.reset()
        self._reconnecting = False
        self._camera_failures = 0
        self._camera_note = "Camera reconnected"
        self._publish("camera_state", state="connected")
        self._post_status(hand=False)

    def _draw_hud(self, frame, gesture_label: str, command_label: str, hand: bool):
        """Draw a high-contrast gesture/action badge onto a BGR frame in place."""
        try:
            import cv2
        except Exception:
            return frame
        if not hand:
            text = "NO HAND"
            color = HUD_NO_HAND
        else:
            text = (gesture_label or "hand").replace("-", " ").upper()
            if command_label and command_label not in {"none", "move"}:
                text = f"{text}  |  {command_label.upper()}"
            color = HUD_COLORS.get(gesture_label, (0, 200, 0))
        try:
            height, width = frame.shape[:2]
            scale = max(0.5, min(1.0, width / 640.0))
            thickness = max(1, int(round(2 * scale)))
            (tw, th), baseline = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
            )
            x, y = 10, 10
            cv2.rectangle(
                frame,
                (x - 5, y - 5),
                (x + tw + 9, y + th + baseline + 5),
                (0, 0, 0),
                -1,
            )
            cv2.putText(
                frame,
                text,
                (x + 2, y + th + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                scale,
                color,
                thickness,
                cv2.LINE_AA,
            )
        except Exception:
            logger.debug("could not draw HUD badge", exc_info=True)
        return frame

    def _downscale(self, frame):
        try:
            import cv2

            h, w = frame.shape[:2]
            scale = min(1.0, FRAME_WIDTH / w, FRAME_HEIGHT / h)
            if scale < 1.0:
                frame = cv2.resize(
                    frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
                )
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if ok:
                return buf.tobytes()
        except Exception:
            logger.debug("frame encoding failed", exc_info=True)
        return None

    # -- main loop -------------------------------------------------------------

    def run(self) -> None:
        logger.info("pipeline worker started")
        try:
            if self._settings.get("auto_open_camera", True):
                self.open_camera()
            self.tracker.open()
        except Exception as exc:
            self._post_error(str(exc))
            logger.exception("pipeline startup failed")
            # Release anything already acquired so the webcam is not left
            # locked and the UI does not show a dead "running" pipeline.
            self._teardown()
            logger.info("pipeline worker stopped after startup failure")
            return

        frame_count = 0
        last = time.perf_counter()

        while not self._stop.is_set():
            loop_start = time.perf_counter()
            frame = self._grab_frame()

            if frame is not None and not self.tracker.is_open:
                try:
                    self.tracker.open()
                except Exception as exc:
                    self._post_error(str(exc))
                    frame = None

            # Eco / battery saver: while throttled, poll cheaply for motion and
            # skip the expensive inference pass unless something moved.  The
            # light motion check keeps re-entry latency under ~40ms.
            throttled = self._eco.active
            motion = self._motion.update(frame) if frame is not None else False
            skip_inference = self._eco.enabled and throttled and not motion

            if skip_inference:
                self._post_status(hand=False, gesture="", command="", eco=True)
                if frame is not None:
                    jpeg = self._downscale(frame)
                    if jpeg:
                        self._publish("frame", jpeg=jpeg)
                self._sleep_remaining(ECO_WAKE_POLL, loop_start)
                frame_count += 1
                continue

            result = self.tracker.detect(frame) if frame is not None else None

            command: MouseCommand = None
            gesture_label = ""
            hand = False
            if result is not None and not result.error and result.landmarks is not None:
                frame = self.tracker.annotate(frame, result.landmarks)
                hand = True
                self._feed_calibration(result.landmarks)
                command = self.gesture.process(result.landmarks)
                gesture_label = self.gesture.classify_pose(result.landmarks).gesture
            else:
                command = self.gesture.process(None)

            if self._mouse_enabled:
                self._execute(command)

            if frame is not None:
                # Render gesture/action text onto the frame so the user always
                # sees the system responding, regardless of the side panel.
                frame = self._draw_hud(
                    frame, gesture_label, command.label if command else "", hand
                )

            self._post_status(
                hand=hand,
                gesture=gesture_label,
                command=command.label if command else "",
                eco=self._eco.active,
            )

            if frame is not None:
                jpeg = self._downscale(frame)
                if jpeg:
                    self._publish("frame", jpeg=jpeg)

            # FPS accounting + pacing
            now = time.perf_counter()
            elapsed = now - last
            if elapsed > 0:
                inst_fps = 1.0 / elapsed
                self._fps = self._fps * 0.9 + inst_fps * 0.1 if self._fps else inst_fps
            last = now

            # Throttle to the eco rate after inactivity, otherwise full speed.
            self._sleep_remaining(self._eco.interval(hand, now=now), loop_start)
            frame_count += 1

        self._teardown()
        logger.info("pipeline worker stopped after %d frames", frame_count)

    @staticmethod
    def _sleep_remaining(interval: float, loop_start: float) -> None:
        remaining = interval - (time.perf_counter() - loop_start)
        if remaining > 0:
            time.sleep(remaining)

    def _teardown(self) -> None:
        """Release tracker, camera and mouse buttons and report the stopped state.

        Safe to call multiple times and from both the normal stop path and the
        startup-failure path.
        """
        try:
            self.tracker.close()
        except Exception:
            logger.debug("error closing tracker", exc_info=True)
        try:
            self.camera.release()
        except Exception:
            pass
        self._release_all()
        self._mouse_enabled = False
        self._publish("state", state="stopped")
        self._publish("status", camera_open=False, hand=False, fps=0.0, mouse_enabled=False, command="")

    # -- command dispatch -----------------------------------------------------

    def _execute(self, cmd: MouseCommand) -> None:
        kind = cmd.kind
        cfg = self._settings
        try:
            if kind == "move":
                if cfg.get("use_gesture_move", True):
                    x, y = self._map_and_smooth(cmd.x, cmd.y)
                    self.mouse.move_to(x, y)
            elif kind == "left_click":
                if cfg.get("use_gesture_left_click", True):
                    x, y = self._map_screen(cmd.click_x, cmd.click_y)
                    self.mouse.left_click(x, y)
                    self._feedback("left_click")
            elif kind == "right_click":
                if cfg.get("use_gesture_right_click", True):
                    pos = self.mouse.pyautogui.position() if self.mouse.pyautogui else None
                    if pos is not None:
                        self.mouse.right_click(pos.x, pos.y)
                    else:
                        self.mouse.right_click(*self._current_screen_pos())
                    self._feedback("right_click")
            elif kind == "scroll":
                if cfg.get("use_gesture_scroll", True):
                    self.mouse.scroll(cmd.steps)
            elif kind == "drag_start":
                if cfg.get("use_gesture_drag", True):
                    self.mouse.start_drag()
                    self._feedback("drag")
            elif kind == "drag_move":
                if cfg.get("use_gesture_drag", True):
                    x, y = self._map_and_smooth(cmd.x, cmd.y)
                    self.mouse.drag_move(x, y)
            elif kind == "drag_end":
                self.mouse.end_drag()
        except Exception as exc:
            logger.exception("error executing command %s", kind)
            self._post_error(f"mouse action failed: {exc}")

    def _map_screen(self, x: float, y: float):
        """Map normalized coords into the selected display region."""
        mx, my = self._mapper.map(x, y)
        return self._region.x + mx, self._region.y + my

    def _map_and_smooth(self, x: float, y: float):
        sx, sy = self._map_screen(x, y)
        return self._smoother.smooth(sx, sy)

    def _current_screen_pos(self):
        return (
            int(self._region.x + self._region.width / 2),
            int(self._region.y + self._region.height / 2),
        )