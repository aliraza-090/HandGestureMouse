"""Design tokens for the HandGestureMouse UI."""

import customtkinter as ctk

# Palette ---------------------------------------------------------------
BG = "#0f1115"
SURFACE = "#171b24"
SURFACE_2 = "#1e2431"
SURFACE_3 = "#262e3f"
BORDER = "#2c3547"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#3a74e0"
SUCCESS = "#2ec27e"
SUCCESS_HOVER = "#27a86d"
DANGER = "#e5484d"
DANGER_HOVER = "#c23a3f"
WARN = "#f5a524"
TEXT = "#e8ecf4"
TEXT_DIM = "#97a1b3"
TEXT_FAINT = "#5f6b80"

# Fonts ------------------------------------------------------------------
# Tuples (family, size, style) are accepted by CustomTkinter widgets and do
# not require a Tk root to be defined (unlike ``ctk.CTkFont`` at import time).
FONT_TITLE = ("Segoe UI", 24, "bold")
FONT_HEADING = ("Segoe UI", 17, "bold")
FONT_SUBHEADING = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 12)
FONT_MONO = ("Consolas", 12)

RADIUS = 12
RADIUS_SM = 8


def apply_theme() -> None:
    """Configure CustomTkinter theme once."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def status_color(state: str) -> str:
    """Map service state to a badge color."""
    if state == "running":
        return SUCCESS
    if state == "paused":
        return WARN
    return DANGER if state == "emergency" else TEXT_FAINT