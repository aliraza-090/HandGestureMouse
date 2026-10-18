"""Main application window: navigation, header and view switching."""

from typing import Dict, Optional

import customtkinter as ctk

from ..utils.paths import native_icon_path
from . import theme
from .camera_view import CameraView
from .dashboard import DashboardView
from .instructions_view import InstructionsView
from .settings_view import SettingsView

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("tracking", "Live Tracking"),
    ("settings", "Settings"),
    ("instructions", "Instructions"),
]

VIEWS = {
    "dashboard": DashboardView,
    "tracking": CameraView,
    "settings": SettingsView,
    "instructions": InstructionsView,
}


class _Chip(ctk.CTkFrame):
    def __init__(self, master, title: str) -> None:
        super().__init__(master, fg_color=theme.SURFACE_2, corner_radius=theme.RADIUS_SM)
        self.dot = ctk.CTkFrame(self, width=10, height=10, fg_color=theme.TEXT_FAINT, corner_radius=10)
        self.dot.pack(side="left", padx=(8, 6), pady=8)
        ctk.CTkLabel(self, text=title, font=theme.FONT_SMALL, text_color=theme.TEXT_DIM).pack(side="left", pady=8)
        self.value = ctk.CTkLabel(self, text="off", font=theme.FONT_SMALL, text_color=theme.TEXT)
        self.value.pack(side="left", padx=(4, 10), pady=8)

    def set(self, ok: bool, label: str, color: Optional[str] = None) -> None:
        self.dot.configure(fg_color=color or (theme.SUCCESS if ok else theme.DANGER))
        self.value.configure(text=label, text_color=color or theme.TEXT)


class MainWindow(ctk.CTk):
    def __init__(self, controller) -> None:
        super().__init__()
        self._controller = controller
        self._current = "dashboard"
        self._state = "stopped"

        self.title("HandGestureMouse - Hand Gesture Mouse Control")
        self.geometry("1040x700")
        self.minsize(900, 620)
        icon = native_icon_path()
        if icon:
            try:
                self.iconbitmap(icon)
            except Exception:
                pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_header()
        self._content = ctk.CTkFrame(self, fg_color=theme.BG)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)
        self._header.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._views: Dict[str, ctk.CTkFrame] = {}
        self.navigate("dashboard")

    # -- layout ----------------------------------------------------------------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=215, corner_radius=0, fg_color=theme.SURFACE)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 0))
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(sidebar, text="HandGestureMouse", font=theme.FONT_HEADING, text_color=theme.TEXT).grid(
            row=0, column=0, sticky="w", padx=18, pady=(22, 26)
        )

        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        for i, (key, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                font=theme.FONT_BODY,
                anchor="w",
                height=42,
                fg_color="transparent",
                hover_color=theme.SURFACE_2,
                text_color=theme.TEXT_DIM,
                corner_radius=theme.RADIUS_SM,
                command=lambda k=key: self.navigate(k),
            )
            btn.grid(row=i + 1, column=0, sticky="ew", padx=10, pady=3)
            self.nav_buttons[key] = btn

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=10, column=0, sticky="sw", padx=18, pady=16)
        ctk.CTkLabel(
            footer, text="v1.0.0 - offline", font=theme.FONT_SMALL, text_color=theme.TEXT_FAINT
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Developed by Ali Raza Chakrani",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_FAINT,
        ).pack(anchor="w")
        self._sidebar = sidebar

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0)
        header.grid_columnconfigure(3, weight=1)

        self.camera_chip = _Chip(header, "Camera")
        self.camera_chip.grid(row=0, column=0, padx=(16, 6), pady=10)
        self.hand_chip = _Chip(header, "Hand")
        self.hand_chip.grid(row=0, column=1, padx=6, pady=10)
        self.state_chip = _Chip(header, "Mouse")
        self.state_chip.grid(row=0, column=2, padx=6, pady=10)

        self.live_state = ctk.CTkLabel(
            header,
            text="State: Stopped",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_DIM,
        )
        self.live_state.grid(row=0, column=3, sticky="w", padx=16)

        self.emergency_btn = ctk.CTkButton(
            header,
            text="STOP",  # always visible emergency stop
            font=theme.FONT_SUBHEADING,
            fg_color=theme.DANGER,
            hover_color=theme.DANGER_HOVER,
            width=110,
            height=36,
            command=self._controller.emergency_stop,
        )
        self.emergency_btn.grid(row=0, column=4, padx=(16, 16), pady=8)
        self._header = header

    # -- view management --------------------------------------------------------

    def navigate(self, name: str) -> None:
        if name not in VIEWS:
            return
        self._current = name
        for key, btn in self.nav_buttons.items():
            btn.configure(fg_color=theme.ACCENT if key == name else "transparent", text_color=theme.TEXT if key == name else theme.TEXT_DIM)
        if name not in self._views:
            self._views[name] = VIEWS[name](self._content, self._controller)
            self._views[name].grid(row=0, column=0, sticky="nsew")
        self._views[name].tkraise()

    # -- updates -----------------------------------------------------------------

    def update_status(self, payload: Dict[str, object]) -> None:
        camera_ok = bool(payload.get("camera_open", False))
        hand_ok = bool(payload.get("hand", False))
        self.camera_chip.set(camera_ok, "On" if camera_ok else "Off")
        self.hand_chip.set(hand_ok, "Detected" if hand_ok else "None")
        for view in self._views.values():
            if hasattr(view, "update_status"):
                view.update_status(payload)

    def show_frame(self, jpeg: bytes) -> None:
        view = self._views.get("tracking")
        # Skip decoding / rendering entirely while minimised or hidden to the
        # tray: tracking keeps running but we do not waste CPU on a hidden feed.
        if self.state() != "normal":
            return
        if view is not None and self._current == "tracking":
            view.show_frame(jpeg)

    def set_state(self, state: str) -> None:
        self._state = state
        label = {"running": "Running - virtual mouse active", "paused": "Paused", "stopped": "Stopped"}.get(state, "Stopped")
        color = theme.status_color(state)
        self.live_state.configure(text=f"State: {label}", text_color=color)
        self.state_chip.set(state == "running", "Active" if state == "running" else (state.capitalize() if state in {"paused", "stopped"} else "Stopped"), color)
        for view in self._views.values():
            if hasattr(view, "set_state"):
                view.set_state(state)
        self.emergency_btn.configure(state="normal")

    def push_error(self, message: str) -> None:
        self.live_state.configure(text=f"Error: {message}", text_color=theme.DANGER)

    def push_info(self, message: str) -> None:
        self.live_state.configure(text=message, text_color=theme.WARN)

    def flash_feedback(self, action: str) -> None:
        view = self._views.get("tracking")
        if view is not None and hasattr(view, "flash_feedback"):
            view.flash_feedback(action)

    def update_camera_state(self, payload: Dict[str, object]) -> None:
        view = self._views.get("tracking")
        if view is not None and hasattr(view, "update_camera_state"):
            view.update_camera_state(payload)

    def reload_settings(self) -> None:
        view = self._views.get("settings")
        if view is not None and hasattr(view, "reload"):
            view.reload()

    def _on_unmap(self, event) -> None:
        # Only react to the window itself being minimised (not child widgets).
        if event.widget is not self:
            return
        try:
            if self.state() == "iconic":
                self._controller.on_minimize()
        except Exception:
            pass

    def _on_close(self) -> None:
        # Decide between hiding to tray and a full shutdown.
        self._controller.request_close()