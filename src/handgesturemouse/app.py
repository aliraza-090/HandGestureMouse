"""Application coordinator: wires GUI, pipeline and global hotkeys together.

GUI runs on the Tkinter main thread.  All camera / inference / mouse work
happens on the pipeline thread, which posts :class:`PipelineEvent` objects to
a queue drained by the GUI on its own ``after()`` tick.
"""

import logging
import queue
import threading
from typing import List, Optional

from .camera.camera_manager import CameraManager
from .config.settings_manager import SettingsManager
from .core.gesture_controller import GestureController
from .core.hand_tracker import HandTracker
from .core.mouse_controller import MouseController
from .core.pipeline import MAX_QUEUE, PipelineWorker
from .gui import theme
from .gui.main_window import MainWindow
from .utils import paths
from .utils.autostart import AutostartManager
from .utils.feedback import AudioFeedback
from .utils.logger import configure_logging, get_logger

logger = get_logger("app")


class Application:
    """Owns all components and the application lifecycle."""

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.mouse = MouseController()
        self.gesture = GestureController(self.settings.as_dict())
        self.camera = CameraManager()
        self.audio = AudioFeedback(enabled=bool(self.settings.get("enable_audio_feedback")))
        self.autostart = AutostartManager()
        self.tracker = HandTracker(
            model_file=paths.model_path(),
            num_hands=int(self.settings.get("num_hands")),
            min_detection_confidence=float(self.settings.get("detection_confidence")),
        )
        self.events = queue.Queue(maxsize=MAX_QUEUE)
        self.stop_event = threading.Event()
        self.pipeline = PipelineWorker(
            camera=self.camera,
            tracker=self.tracker,
            mouse=self.mouse,
            gesture=self.gesture,
            settings_provider=self.settings,
            event_queue=self.events,
            stop_event=self.stop_event,
            audio=self.audio,
        )
        self.window: Optional[MainWindow] = None
        self._hotkey = None
        self._ui_state = "stopped"
        self._tray = None
        self._quitting = False
        self._calibration_dialog = None

    # -- lifecycle ----------------------------------------------------------------

    def run(self) -> None:
        configure_logging()
        theme.apply_theme()
        self.window = MainWindow(self)
        self._start_tray()
        self._apply_autostart()
        self.pipeline.start()
        self._install_hotkeys()
        # Control the mouse as soon as the app opens (unless the user opted out)
        # so the app never sits in a passive state the user has to toggle.
        if bool(self.settings.get("start_control_on_launch")):
            self.start_control()
        self.window.after(30, self._poll_events)
        try:
            self.window.mainloop()
        finally:
            self._shutdown()
        self.window = None

    def _shutdown(self) -> None:
        self._stop_tray()
        self.pipeline.stop_service()
        self.pipeline.request_stop()
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:  # pragma: no cover - already destroyed
                logger.debug("window already destroyed", exc_info=True)
            self.window = None
        self._stop_hotkeys()
        self.mouse.release_all()
        if self.pipeline.ident is not None:
            self.pipeline.join(timeout=3.0)
            if self.pipeline.is_alive():
                logger.warning("pipeline thread still alive after shutdown waited 3s")
            else:
                logger.info("pipeline thread joined")
        # Guarantee the camera device is released even if the pipeline thread
        # could not finish in time.
        try:
            self.camera.release()
        except Exception:
            logger.debug("camera release during shutdown failed", exc_info=True)

    # -- window / tray lifecycle -----------------------------------------------

    @staticmethod
    def _hide_instead_of_quit(tray_active: bool, configured: bool) -> bool:
        """Return True when the window should hide to the tray rather than quit."""
        return bool(tray_active and configured)

    def request_close(self) -> None:
        """Handle the window close button.

        When the tray is active and ``close_to_tray`` is enabled the window is
        hidden and tracking continues in the background; otherwise the whole
        application shuts down.
        """
        if self._hide_instead_of_quit(
            self._tray is not None and self._tray.is_running,
            bool(self.settings.get("close_to_tray")),
        ):
            logger.info("close requested: hiding window to tray")
            self.hide_window()
        else:
            logger.info("close requested: quitting application")
            self.quit_application()

    def on_minimize(self) -> None:
        """Handle the window being minimised; hide to tray when configured."""
        if self._hide_instead_of_quit(
            self._tray is not None and self._tray.is_running,
            bool(self.settings.get("minimize_to_tray")),
        ):
            self.hide_window()

    def show_window(self) -> None:
        if self.window is None:
            return
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
        except Exception:  # pragma: no cover - window may be closing
            logger.debug("could not show window", exc_info=True)

    def hide_window(self) -> None:
        if self.window is None:
            return
        try:
            self.window.withdraw()
            logger.info("window hidden to tray; tracking continues")
        except Exception:  # pragma: no cover - window may be closing
            logger.debug("could not hide window", exc_info=True)
        self._notify_tray_active()

    def _notify_tray_active(self) -> None:
        """Tell the user the app keeps working from the tray and how to stop it."""
        if self._tray is None or not bool(self.settings.get("show_tray_notifications")):
            return
        hotkey = str(self.settings.get("emergency_hotkey") or "ctrl+alt+e").upper()
        try:
            self._tray.notify(
                "HandGestureMouse is active in the system tray. "
                f"Use the global hotkey ({hotkey}) to pause/stop."
            )
        except Exception:  # pragma: no cover - best-effort notification
            logger.debug("tray notification failed", exc_info=True)

    def quit_application(self) -> None:
        """Fully stop tracking and close the application (works from the tray)."""
        if self._quitting:
            return
        self._quitting = True
        logger.info("quitting application")
        if self.window is not None:
            window = self.window
            self.window = None
            try:
                window.destroy()
            except Exception:  # pragma: no cover - defensive
                logger.debug("error destroying window", exc_info=True)

    def toggle_pause(self) -> None:
        """Pause the virtual mouse when running, otherwise start/resume it."""
        if self._ui_state == "running":
            self.pause_control()
        else:
            self.start_control()

    # -- system tray ----------------------------------------------------------

    def _start_tray(self) -> None:
        if not bool(self.settings.get("enable_tray")):
            logger.info("system tray disabled by settings")
            return
        from .gui.tray import TrayIcon, tray_available

        if not tray_available():
            logger.warning("pystray not available; continuing without a tray icon")
            if self.window is not None:
                self.window.push_info(
                    "System tray is unavailable (pystray not installed). "
                    "Use the window controls to minimise or quit."
                )
            return

        self._tray = TrayIcon(
            title="HandGestureMouse",
            image_path=paths.icon_path(),
            on_action=self._on_tray_action,
            state_provider=lambda: self._ui_state,
        )
        if not self._tray.start():
            self._tray = None
            if self.window is not None:
                self.window.push_info(
                    "System tray could not be started. The application still works; "
                    "closing the window will quit it."
                )

    def _stop_tray(self) -> None:
        if self._tray is not None:
            self._tray.stop()
            self._tray = None

    def _on_tray_action(self, action: str) -> None:
        """Called from the pystray thread; marshal onto the Tk main thread."""
        if self.window is None:
            return
        try:
            self.window.after(0, self._handle_tray_action, action)
        except Exception:  # pragma: no cover - window may be gone
            logger.debug("could not dispatch tray action %r", action, exc_info=True)

    def _handle_tray_action(self, action: str) -> None:
        logger.info("tray action: %s", action)
        if action == "show":
            self.show_window()
        elif action == "hide":
            self.hide_window()
        elif action == "toggle":
            self.toggle_pause()
        elif action == "exit":
            self.quit_application()

    def on_close(self) -> None:
        """Called by the window close handler; delegates to request_close()."""
        self.request_close()

    # -- GUI polling ---------------------------------------------------------------

    def _poll_events(self) -> None:
        if self.window is None:
            return
        try:
            while True:
                event = self.events.get_nowait()
                self._dispatch_event(event)
                self.events.task_done()
        except queue.Empty:
            pass
        finally:
            if self.window is not None:
                self.window.after(30, self._poll_events)

    def _dispatch_event(self, event) -> None:
        kind = event.kind
        payload = event.payload
        if kind == "status":
            self.window.update_status(payload)
        elif kind == "frame":
            self.window.show_frame(payload.get("jpeg"))
        elif kind == "state":
            self._ui_state = payload.get("state", "stopped")
            self.window.set_state(self._ui_state)
            if self._tray is not None:
                self._tray.update()
        elif kind == "emergency":
            self._ui_state = "stopped"
            self.window.set_state("stopped")
            self.window.push_error("Emergency stop triggered (fail-safe corner reached or hotkey).")
            logger.warning("emergency stop: %s", payload.get("message"))
        elif kind == "feedback":
            self.window.flash_feedback(str(payload.get("action") or ""))
        elif kind == "camera_state":
            self.window.update_camera_state(payload)
        elif kind == "calibration":
            if self._calibration_dialog is not None:
                self._calibration_dialog.update_progress(payload)
        elif kind == "calibration_result":
            self._on_calibration_result(payload)
        elif kind == "error":
            self.window.push_error(payload.get("message", "unknown error"))
            logger.error("pipeline error: %s", payload.get("message"))

    # -- control actions (used by views) -------------------------------------------

    def start_control(self) -> None:
        if not self.pipeline.is_alive():
            # The worker thread died (e.g. model/tracker initialisation failed);
            # do not pretend to run and leave the UI in a misleading state.
            logger.warning("start control ignored: pipeline thread is not running")
            if self.window is not None:
                self.window.push_error(
                    "Hand tracking is not running. Restart the application."
                )
            return
        logger.info("start control requested")
        self.pipeline.start_service()
        self._ui_state = "running"
        if self._tray is not None:
            self._tray.update()

    def pause_control(self) -> None:
        logger.info("pause control requested")
        self.pipeline.pause_service()
        self._ui_state = "paused"
        if self._tray is not None:
            self._tray.update()

    def stop_control(self) -> None:
        logger.info("stop control requested")
        self.pipeline.stop_service()
        self._ui_state = "stopped"
        if self._tray is not None:
            self._tray.update()

    def emergency_stop(self) -> None:
        logger.info("emergency stop requested")
        self.audio.emergency()
        self.pipeline.emergency_stop()
        self._ui_state = "stopped"
        if self.window is not None:
            self.window.set_state("stopped")
        if self._tray is not None:
            self._tray.update()

    def navigate(self, name: str) -> None:
        if self.window is not None:
            self.window.navigate(name)

    def apply_settings(self) -> None:
        self.pipeline.apply_settings()
        self._install_hotkeys()
        self._reconcile_tray()
        self._apply_autostart()
        try:
            self.audio.set_enabled(bool(self.settings.get("enable_audio_feedback")))
        except Exception:
            logger.debug("could not update audio feedback setting", exc_info=True)
        logger.info("settings applied")

    # -- auto-start ---------------------------------------------------------

    def _apply_autostart(self) -> None:
        """Sync the Windows Run-registry entry with the auto-start setting."""
        want = bool(self.settings.get("auto_start_windows"))
        if not self.autostart.is_supported():
            if want and self.window is not None:
                self.window.push_info("Auto-start is only available on Windows.")
            return
        if self.autostart.is_enabled() == want:
            return
        ok = self.autostart.set_enabled(want)
        if not ok:
            logger.warning("could not update auto-start registry entry (want=%s)", want)
            if self.window is not None:
                self.window.push_error(
                    "Could not update auto-start (registry access may be restricted)."
                )

    # -- calibration --------------------------------------------------------

    def open_calibration(self) -> None:
        if self.window is None:
            return
        if self._calibration_dialog is not None:
            try:
                self._calibration_dialog.focus()
            except Exception:
                pass
            return
        from .gui.calibration_dialog import CalibrationDialog

        self.pause_control()
        self._calibration_dialog = CalibrationDialog(self.window, self)
        self.pipeline.start_calibration()

    def calibration_advance(self) -> None:
        self.pipeline.advance_calibration()

    def calibration_cancel(self) -> None:
        self.pipeline.cancel_calibration()
        self._calibration_dialog = None

    def _on_calibration_result(self, payload) -> None:
        if bool(payload.get("ok")):
            try:
                self.settings.update(
                    {
                        "pinch_threshold": float(payload["pinch_threshold"]),
                        "pinch_hold_threshold": float(payload["pinch_hold_threshold"]),
                    }
                )
                self.settings.save()
                self.pipeline.apply_settings()
                if self.window is not None:
                    self.window.push_info("Calibration saved. Pinch thresholds updated.")
            except Exception as exc:
                logger.exception("could not save calibration")
                if self.window is not None:
                    self.window.push_error(f"Could not save calibration: {exc}")
        else:
            if self.window is not None:
                self.window.push_error(str(payload.get("message") or "Calibration failed."))
        if self._calibration_dialog is not None:
            self._calibration_dialog.show_result(payload)

    def calibration_closed(self) -> None:
        """Called by the dialog when it is dismissed."""
        self.pipeline.cancel_calibration()
        self._calibration_dialog = None
        if self.window is not None:
            self.window.reload_settings()

    def list_monitors(self) -> List[str]:
        from .core.screens import list_monitors

        return [m.label for m in list_monitors()]

    def _reconcile_tray(self) -> None:
        """Start/stop the tray so it matches the ``enable_tray`` setting."""
        want = bool(self.settings.get("enable_tray"))
        if want and (self._tray is None or not self._tray.is_running):
            self._start_tray()
        elif not want and self._tray is not None:
            self._stop_tray()
        elif self._tray is not None:
            self._tray.update()

    def get_cameras(self) -> List[int]:
        return self.camera.list_cameras()

    # -- global emergency hotkey -----------------------------------------------------

    @staticmethod
    def _to_pynput_hotkey(hotkey: str) -> str:
        """Convert ``ctrl+alt+e`` style into pynput's ``<ctrl>+<alt>+e`` form."""
        modifiers = {
            "ctrl": "<ctrl>",
            "control": "<ctrl>",
            "alt": "<alt>",
            "option": "<alt>",
            "shift": "<shift>",
            "cmd": "<cmd>",
            "win": "<cmd>",
            "super": "<cmd>",
            "meta": "<cmd>",
        }
        tokens = []
        for raw in hotkey.replace(" ", "").split("+"):
            if not raw:
                continue
            token = raw.lower()
            if token.startswith("<") and token.endswith(">"):
                tokens.append(token)
            elif token in modifiers:
                tokens.append(modifiers[token])
            else:
                tokens.append(token)
        return "+".join(tokens)

    def _install_hotkeys(self) -> None:
        self._stop_hotkeys()
        hotkey = str(self.settings.get("emergency_hotkey")).lower().strip()
        pynput_hotkey = self._to_pynput_hotkey(hotkey)
        try:
            from pynput import keyboard

            self._hotkey = keyboard.GlobalHotKeys({pynput_hotkey: self._on_hotkey})
            self._hotkey.start()
            logger.info("global emergency hotkey registered: %s (%s)", hotkey, pynput_hotkey)
        except Exception as exc:
            logger.warning("could not register global hotkey %r: %s", hotkey, exc)
            self._hotkey = None

    def _stop_hotkeys(self) -> None:
        if self._hotkey is not None:
            try:
                self._hotkey.stop()
            except Exception:
                pass
            self._hotkey = None

    def _on_hotkey(self) -> None:
        logger.info("global emergency hotkey pressed")
        try:
            self.audio.emergency()
        except Exception:
            pass
        try:
            self.pipeline.emergency_stop()
        except Exception:
            logger.exception("hotkey handler failed")
        if self.window is not None:
            self.window.after(0, self.window.set_state, "stopped")


def main() -> None:
    """Entry point: run the application GUI."""
    application = Application()
    try:
        application.run()
    except Exception:
        logging.getLogger("handgesturemouse").exception("application terminated with an unhandled error")
        raise


if __name__ == "__main__":
    main()