"""Settings screen: sliders, toggles and camera selection with validation."""

from typing import Dict, List

import customtkinter as ctk

from . import theme

SLIDERS: List[tuple] = [
    ("cursor_sensitivity", "Cursor sensitivity", 0.1, 5.0, 98, 2),
    ("cursor_smoothing", "Cursor smoothing", 0.0, 1.0, 100, 2),
    ("mouse_smoothing_deade_zone", "Center dead zone", 0.0, 0.25, 100, 3),
    ("pinch_threshold", "Pinch threshold", 0.15, 0.6, 90, 2),
    ("pinch_hold_threshold", "Pinch release threshold", 0.2, 0.7, 100, 2),
    ("click_hold_time", "Click hold time (s)", 0.15, 1.0, 170, 2),
    ("gesture_cooldown", "Gesture cooldown (s)", 0.0, 2.0, 100, 2),
    ("scroll_sensitivity", "Scroll sensitivity", 5.0, 100.0, 190, 0),
    ("scroll_yield", "Scroll dead band", 0.0, 0.01, 100, 4),
    ("eco_idle_seconds", "Eco idle before throttle (s)", 5, 600, 119, 0),
    ("eco_fps", "Eco tracking rate (FPS)", 1, 30, 29, 0),
]

TOGGLES: List[tuple] = [
    ("use_gesture_move", "Move cursor with index finger"),
    ("use_gesture_left_click", "Left click with index pinch"),
    ("use_gesture_right_click", "Right click with middle pinch"),
    ("use_gesture_scroll", "Scroll with two-finger gesture"),
    ("use_gesture_drag", "Drag with held pinch"),
    ("mirror_input", "Mirror camera feed"),
]

TRAY_TOGGLES: List[tuple] = [
    ("enable_tray", "Show a system tray icon"),
    ("minimize_to_tray", "Minimise to tray instead of the taskbar"),
    ("close_to_tray", "Closing the window hides to tray (use Exit to quit)"),
]

SYSTEM_TOGGLES: List[tuple] = [
    ("start_control_on_launch", "Control the mouse as soon as the app opens"),
    ("enable_audio_feedback", "Play a subtle sound when a gesture fires"),
    ("show_tray_notifications", "Show a notification when hiding to the tray"),
    ("eco_mode", "Eco / battery saver (reduce CPU when no hand is present)"),
    ("auto_start_windows", "Start automatically when I sign in to Windows"),
]

DISPLAY_CHOICES = ["primary", "secondary", "span"]

SLIDER_FORMATS = {}


def _fmt(key: str, value: float) -> str:
    steps = {k: s for k, _, _, _, s, _ in SLIDERS}
    decimals = {k: d for k, _, _, _, _, d in SLIDERS}
    n = decimals.get(key, 2)
    return f"{value:.{n}f}"


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = controller
        self._sliders: Dict[str, ctk.CTkSlider] = {}
        self._slider_values: Dict[str, ctk.CTkLabel] = {}
        self._toggles: Dict[str, ctk.CTkSwitch] = {}
        self._values: Dict[str, object] = {}

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Settings", font=theme.FONT_HEADING, text_color=theme.TEXT).grid(
            row=0, column=0, sticky="w", padx=8, pady=(4, 4)
        )
        ctk.CTkLabel(
            self,
            text="Changes are applied when you press Save. Invalid values are rejected.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_DIM,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 12))

        # Camera -------------------------------------------------------------
        self._next_row = 2
        camera_frame = self._section("Camera")
        self.camera_box = ctk.CTkOptionMenu(
            camera_frame,
            values=["0"],
            command=self._on_camera_pick,
            fg_color=theme.SURFACE_2,
            button_color=theme.SURFACE_3,
            button_hover_color=theme.BORDER,
        )
        self.camera_box.pack(side="left", padx=(6, 8), pady=8)
        ctk.CTkButton(
            camera_frame,
            text="Rescan cameras",
            font=theme.FONT_SMALL,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            width=130,
            command=self._rescan_cameras,
        ).pack(side="left", pady=8)
        self.camera_error = ctk.CTkLabel(
            camera_frame, text="", font=theme.FONT_SMALL, text_color=theme.DANGER
        )
        self.camera_error.pack(side="left", padx=12)
        auto_toggle = ctk.CTkSwitch(
            camera_frame,
            text="Open automatically at startup",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT,
            progress_color=theme.ACCENT,
        )
        auto_toggle.pack(side="left", padx=8)
        self._toggles["auto_open_camera"] = auto_toggle

        # Sliders -------------------------------------------------------------
        for key, label, lo, hi, steps, _ in SLIDERS:
            row_frame = ctk.CTkFrame(self, fg_color=theme.SURFACE_2, corner_radius=theme.RADIUS_SM)
            row_index = self._next_row
            self._next_row += 1
            row_frame.grid(row=row_index, column=0, sticky="ew", pady=3)
            row_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_frame, text=label, font=theme.FONT_BODY, text_color=theme.TEXT).grid(
                row=0, column=0, sticky="w", padx=(12, 8), pady=8
            )
            value_label = ctk.CTkLabel(
                row_frame,
                text="",
                font=theme.FONT_MONO,
                text_color=theme.ACCENT,
                width=70,
                anchor="e",
            )
            value_label.grid(row=0, column=2, padx=12, pady=8)
            slider = ctk.CTkSlider(
                row_frame,
                from_=lo,
                to=hi,
                number_of_steps=steps,
                command=lambda v, k=key: self._on_slider(k, v),
                progress_color=theme.ACCENT,
            )
            slider.grid(row=0, column=1, sticky="ew", padx=8, pady=12)
            self._sliders[key] = slider
            self._slider_values[key] = value_label

        # Toggles -------------------------------------------------------------
        toggle_frame = self._section("Gestures")
        for i, (key, label) in enumerate(TOGGLES):
            toggle = ctk.CTkSwitch(
                toggle_frame,
                text=label,
                font=theme.FONT_BODY,
                text_color=theme.TEXT,
                progress_color=theme.ACCENT,
            )
            toggle.pack(anchor="w", padx=8, pady=5)
            self._toggles[key] = toggle

        # Background / tray ----------------------------------------------------
        tray_frame = self._section("Background & system tray")
        ctk.CTkLabel(
            tray_frame,
            text="Tracking keeps running while the window is minimised or hidden to the tray.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_DIM,
        ).pack(anchor="w", padx=8, pady=(0, 4))
        for key, label in TRAY_TOGGLES:
            toggle = ctk.CTkSwitch(
                tray_frame,
                text=label,
                font=theme.FONT_BODY,
                text_color=theme.TEXT,
                progress_color=theme.ACCENT,
            )
            toggle.pack(anchor="w", padx=8, pady=5)
            self._toggles[key] = toggle

        # Feedback & power -----------------------------------------------------
        system_frame = self._section("Feedback & power")
        for key, label in SYSTEM_TOGGLES:
            toggle = ctk.CTkSwitch(
                system_frame,
                text=label,
                font=theme.FONT_BODY,
                text_color=theme.TEXT,
                progress_color=theme.ACCENT,
            )
            toggle.pack(anchor="w", padx=8, pady=5)
            self._toggles[key] = toggle

        # Display / multi-monitor ---------------------------------------------
        display_frame = self._section("Display")
        ctk.CTkLabel(
            display_frame,
            text="Monitor to control",
            font=theme.FONT_BODY,
            text_color=theme.TEXT,
        ).pack(side="left", padx=(8, 8), pady=10)
        self.display_box = ctk.CTkOptionMenu(
            display_frame,
            values=DISPLAY_CHOICES,
            fg_color=theme.SURFACE_2,
            button_color=theme.SURFACE_3,
            button_hover_color=theme.BORDER,
        )
        self.display_box.pack(side="left", padx=(0, 8), pady=8)
        self.display_hint = ctk.CTkLabel(
            display_frame, text="", font=theme.FONT_SMALL, text_color=theme.TEXT_DIM
        )
        self.display_hint.pack(side="left", padx=8)

        # Calibration ----------------------------------------------------------
        cal_frame = self._section("Gesture calibration")
        ctk.CTkLabel(
            cal_frame,
            text="Tune the pinch thresholds to your hand size and camera distance.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_DIM,
        ).pack(anchor="w", padx=8, pady=(0, 4))
        ctk.CTkButton(
            cal_frame,
            text="Start Calibration...",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            width=170,
            command=self._controller.open_calibration,
        ).pack(anchor="w", padx=8, pady=(0, 10))

        # Hotkey ---------------------------------------------------------------
        hot_frame = self._section("Emergency stop")
        ctk.CTkLabel(
            hot_frame,
            text="Global hotkey (e.g. ctrl+alt+e)",
            font=theme.FONT_BODY,
            text_color=theme.TEXT,
        ).pack(side="left", padx=(8, 8), pady=10)
        self.hotkey_entry = ctk.CTkEntry(
            hot_frame, width=180, fg_color=theme.SURFACE_2, border_color=theme.BORDER
        )
        self.hotkey_entry.pack(side="left", padx=(0, 8), pady=10)
        ctk.CTkLabel(
            hot_frame,
            text="Presses it to instantly release the mouse.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_DIM,
        ).pack(side="left")

        # Footer ---------------------------------------------------------------
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer_row = self._next_row
        self._next_row += 1
        footer.grid(row=footer_row, column=0, sticky="ew", pady=(14, 4))
        self.feedback = ctk.CTkLabel(footer, text="", font=theme.FONT_BODY, text_color=theme.SUCCESS)
        self.feedback.pack(side="left", padx=4)
        ctk.CTkButton(
            footer,
            text="Reset defaults",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            command=self._reset,
        ).pack(side="right", padx=6)
        ctk.CTkButton(
            footer,
            text="Save Settings",
            font=theme.FONT_BODY,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            command=self._save,
        ).pack(side="right", padx=6)

        self._load_values()

    # -- layout helpers ---------------------------------------------------------

    def _section(self, title: str) -> "ctk.CTkFrame":
        frame = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        ctk.CTkLabel(frame, text=title, font=theme.FONT_SUBHEADING, text_color=theme.TEXT).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        row_index = self._next_row
        self._next_row += 1
        frame.grid(row=row_index, column=0, sticky="ew", pady=8)
        return frame

    # -- value handling ---------------------------------------------------------

    def _load_values(self) -> None:
        settings = self._controller.settings
        cameras = self._controller.get_cameras() or ["0"]
        self.camera_box.configure(values=[str(c) for c in cameras])
        current = int(settings.get("camera_index"))
        self.camera_box.set(str(current) if str(current) in [str(c) for c in cameras] else str(cameras[0]))
        for key, slider in self._sliders.items():
            value = float(settings.get(key))
            slider.set(value)
            self._slider_values[key].configure(text=_fmt(key, value))
        for key, toggle in self._toggles.items():
            toggle.select() if bool(settings.get(key)) else toggle.deselect()
        self.hotkey_entry.delete(0, "end")
        self.hotkey_entry.insert(0, str(settings.get("emergency_hotkey")))
        self.display_box.set(str(settings.get("target_display") or "primary"))
        try:
            monitors = self._controller.list_monitors()
            self.display_hint.configure(text="Detected: " + "; ".join(monitors))
        except Exception:
            self.display_hint.configure(text="")
        self.feedback.configure(text="")

    def reload(self) -> None:
        """Re-read values from settings (used after calibration)."""
        self._load_values()

    def _on_slider(self, key: str, value: float) -> None:
        self._slider_values[key].configure(text=_fmt(key, value))

    def _on_camera_pick(self, value: str) -> None:
        self.camera_box.set(value)

    def _rescan_cameras(self) -> None:
        cameras = self._controller.get_cameras()
        self.camera_box.configure(values=[str(c) for c in cameras])
        if cameras:
            self.camera_box.set(str(cameras[0]))
            self.camera_error.configure(text="")
        else:
            self.camera_error.configure(text="No camera found")

    def _current_values(self) -> Dict[str, object]:
        values: Dict[str, object] = {}
        for key, slider in self._sliders.items():
            values[key] = float(slider.get())
        for key, toggle in self._toggles.items():
            values[key] = bool(toggle.get())
        try:
            values["camera_index"] = int(self.camera_box.get())
        except ValueError:
            values["camera_index"] = 0
        values["emergency_hotkey"] = self.hotkey_entry.get().strip()
        values["target_display"] = self.display_box.get()
        return values

    def _save(self) -> None:
        values = self._current_values()
        pinch = float(values.get("pinch_threshold", 0.3))
        hold = float(values.get("pinch_hold_threshold", 0.36))
        if hold <= pinch:
            self.feedback.configure(text="Pinch release threshold must be above pinch threshold.", text_color=theme.DANGER)
            return
        try:
            self._controller.settings.update(values)
            self._controller.settings.save()
            self._controller.apply_settings()
        except ValueError as exc:
            self.feedback.configure(text=str(exc), text_color=theme.DANGER)
            return
        self.feedback.configure(text="Settings saved and applied.", text_color=theme.SUCCESS)

    def _reset(self) -> None:
        self._controller.settings.reset()
        self._load_values()
        self._controller.apply_settings()
        self.feedback.configure(text="Defaults restored.", text_color=theme.SUCCESS)