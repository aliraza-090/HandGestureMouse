"""Dashboard: application summary, status indicators and primary actions."""

from typing import Dict, Optional

import customtkinter as ctk

from ..utils.paths import icon_path
from . import theme


def _status_dot(parent, color: str = theme.TEXT_FAINT, size: int = 12) -> "ctk.CTkFrame":
    frame = ctk.CTkFrame(parent, width=size, height=size, fg_color=color, corner_radius=size)
    frame.pack_propagate(False)
    return frame


class _StatusCard(ctk.CTkFrame):
    def __init__(self, master, title: str, controller) -> None:
        super().__init__(master, fg_color=theme.SURFACE_2, corner_radius=theme.RADIUS)
        self._title = title
        self._controller = controller
        self.grid_columnconfigure(1, weight=1)

        self.dot = _status_dot(self)
        self.dot.pack(side="left", padx=(14, 10), pady=14)

        text_box = ctk.CTkFrame(self, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True, pady=14)
        ctk.CTkLabel(text_box, text=title, font=theme.FONT_SMALL, text_color=theme.TEXT_DIM).pack(anchor="w")
        self.value = ctk.CTkLabel(
            text_box, text="Unknown", font=theme.FONT_SUBHEADING, text_color=theme.TEXT
        )
        self.value.pack(anchor="w", pady=(2, 0))

    def set_status(self, ok: bool, label: str, color: Optional[str] = None) -> None:
        self.dot.configure(fg_color=color or (theme.SUCCESS if ok else theme.DANGER))
        self.value.configure(text=label)


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header -----------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        logo_path = icon_path()
        if logo_path:
            try:
                from PIL import Image

                logo = ctk.CTkImage(
                    light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(56, 56)
                )
                icon_label = ctk.CTkLabel(header, image=logo, text="")
                icon_label.pack(side="left", padx=(0, 16))
            except Exception:
                icon_label = None
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title_box, text="HandGestureMouse", font=theme.FONT_TITLE, text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="Control your mouse cursor with webcam hand gestures - fully offline.",
            font=theme.FONT_BODY,
            text_color=theme.TEXT_DIM,
        ).pack(anchor="w", pady=(2, 0))

        # Status cards -------------------------------------------------------
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        for col in range(3):
            cards.grid_columnconfigure(col, weight=1, uniform="cards")

        self.camera_card = _StatusCard(cards, "Camera", self._controller)
        self.hand_card = _StatusCard(cards, "Hand detection", self._controller)
        self.mouse_card = _StatusCard(cards, "Virtual mouse", self._controller)
        self.camera_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.hand_card.grid(row=0, column=1, sticky="ew", padx=4)
        self.mouse_card.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        # Main actions ----------------------------------------------------------
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=24, pady=12)
        actions.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(
            actions,
            text="Start Control",
            font=theme.FONT_BODY,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            width=170,
            height=42,
            command=controller.start_control,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 8), pady=6)

        self.pause_btn = ctk.CTkButton(
            actions,
            text="Pause Control",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_3,
            hover_color=theme.BORDER,
            width=170,
            height=42,
            state="disabled",
            command=controller.pause_control,
        )
        self.pause_btn.grid(row=0, column=1, padx=8, pady=6)

        self.stop_btn = ctk.CTkButton(
            actions,
            text="Stop Control",
            font=theme.FONT_BODY,
            fg_color=theme.DANGER,
            hover_color=theme.DANGER_HOVER,
            width=170,
            height=42,
            state="disabled",
            command=controller.stop_control,
        )
        self.stop_btn.grid(row=0, column=2, padx=(8, 0), pady=6)

        hint = ctk.CTkLabel(
            self,
            text="Tip: press the STOP button in the header (or the ctrl+alt+e hotkey) to instantly release the mouse.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_FAINT,
        )
        hint.grid(row=3, column=0, sticky="w", padx=24, pady=(0, 8))

        # Quick access -------------------------------------------------------------
        quick = ctk.CTkFrame(self, fg_color="transparent")
        quick.grid(row=4, column=0, sticky="ew", padx=24, pady=(8, 20))
        quick.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(
            quick,
            text="Settings",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            height=40,
            command=lambda: controller.navigate("settings"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            quick,
            text="Gesture Instructions",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            height=40,
            command=lambda: controller.navigate("instructions"),
        ).grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkButton(
            quick,
            text="Exit Application",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.DANGER_HOVER,
            text_color=theme.DANGER,
            height=40,
            command=controller.quit_application,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

    # -- updates ----------------------------------------------------------------

    def update_status(self, payload: Dict[str, object]) -> None:
        camera_ok = bool(payload.get("camera_open"))
        hand_ok = bool(payload.get("hand"))
        self.camera_card.set_status(
            camera_ok, "Connected" if camera_ok else "Disconnected"
        )
        self.hand_card.set_status(
            hand_ok, "Hand detected" if hand_ok else "No hand"
        )

    def set_state(self, state: str) -> None:
        running = state == "running"
        paused = state == "paused"
        self.start_btn.configure(
            state="normal" if not running else "disabled",
            text="Resume" if paused else "Start Control",
        )
        self.pause_btn.configure(state="normal" if running else "disabled")
        self.stop_btn.configure(state="normal" if running or paused else "disabled")
        self.mouse_card.set_status(
            running,
            "Active" if running else ("Paused" if paused else "Off"),
            theme.SUCCESS if running else (theme.WARN if paused else theme.TEXT_FAINT),
        )