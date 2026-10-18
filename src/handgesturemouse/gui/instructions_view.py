"""Instructions screen: how to use every gesture and recover control."""

import customtkinter as ctk

from . import theme

GESTURES = [
    ("Move cursor", "Extend only your index finger and point. The cursor follows your fingertip smoothly. Keep other fingers folded.",
     "Keep your hand relaxed in the centre of the frame for a steering dead-zone."),
    ("Left click", "Pinch your thumb and index fingertips together briefly, then release.", "A short contact clicks once. Release before about 0.35 s."),
    ("Right click", "Pinch your thumb and middle fingertips together while keeping the index finger straight.", "Makes a right-click each time you pinch."),
    ("Vertical scroll", "Show an index + middle finger \u201cV\u201d and move the hand up or down.", "Moving the hand up scrolls up; moving it down scrolls down."),
    ("Drag and drop", "Pinch thumb + index and hold the pinch longer than the hold time (~0.35 s), then move your hand.", "Release the pinch to drop."),
    ("Stop / pause", "Press Stop or Pause in the app, or the emergency hotkey (default ctrl+alt+e).", "The virtual mouse is released immediately."),
]

RECOVERY = [
    ("I can't regain normal mouse control",
     "Press the big red STOP button in the header, or press ctrl+alt+e. Both release every pressed mouse button and disable the virtual mouse instantly."),
    ("Start / Pause / Stop",
     "Start Control enables the virtual mouse. Pause keeps the live view but stops mouse actions. Stop turns everything off and releases buttons."),
    ("The camera feed is black",
     "Make sure no other application (Zoom, Teams, OBS) is using the webcam. Press Rescan cameras in Settings, pick another camera, then Save."),
    ("No hand is detected",
     "Move into good, even lighting. Keep the whole hand visible, palms facing the camera at moderate distance (about 30-80 cm). Check detection confidence in Settings."),
    ("The cursor jumps around",
     "Lower cursor sensitivity, raise cursor smoothing or increase the dead zone in Settings. Anchor your wrist and move your hand smoothly."),
    ("Clicking happens by accident",
     "Raise the pinch threshold and pinch release threshold, or increase gesture cooldown. Use the Gestures toggles in Settings to disable clicks."),
    ("The physical mouse fights the virtual one",
     "Keep the physical mouse still while the virtual mouse is active. Both mice share the OS cursor. Use the emergency hotkey when you need your hand back quickly."),
]

NOTES = [
    "The camera feed is mirrored so your right hand lines up with the cursor.",
    "All processing is local; frames never leave your computer.",
    "PyAutoGUI's corner fail-safe stays on - moving the physical mouse to any edge/top corner also stops the virtual mouse.",
]


class InstructionsView(ctk.CTkScrollableFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = controller
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Gesture Instructions", font=theme.FONT_HEADING, text_color=theme.TEXT).grid(
            row=0, column=0, sticky="w", padx=8, pady=(4, 2)
        )
        ctk.CTkLabel(
            self,
            text="Gesture list, safety information and troubleshooting.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_DIM,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 10))

        self._next_row = 2

        gestures_header = self._card("Supported gestures")
        for i, (name, how, tip) in enumerate(GESTURES):
            row = ctk.CTkFrame(gestures_header, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=4)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=name, font=theme.FONT_SUBHEADING, text_color=theme.ACCENT, width=180, anchor="w").grid(
                row=0, column=0, sticky="nw", padx=(4, 8)
            )
            ctk.CTkLabel(
                row, text=how, font=theme.FONT_BODY, text_color=theme.TEXT, justify="left", anchor="w", wraplength=560
            ).grid(row=0, column=1, sticky="ew")
            if tip:
                ctk.CTkLabel(
                    row,
                    text="Tip: " + tip,
                    font=theme.FONT_SMALL,
                    text_color=theme.TEXT_FAINT,
                    justify="left",
                    wraplength=560,
                ).grid(row=1, column=1, sticky="ew")

        recovery = self._card("Start, stop and recovery")
        for title, body in RECOVERY:
            sub = ctk.CTkFrame(recovery, fg_color="transparent")
            sub.pack(fill="x", anchor="w", pady=(6, 2))
            ctk.CTkLabel(sub, text="\u2022 " + title, font=theme.FONT_BODY, text_color=theme.TEXT, justify="left", wraplength=640, anchor="w").pack(anchor="w")
            ctk.CTkLabel(sub, text=body, font=theme.FONT_SMALL, text_color=theme.TEXT_DIM, justify="left", wraplength=620, anchor="w").pack(anchor="w", padx=16)

        notes = self._card("Good to know")
        for note in NOTES:
            ctk.CTkLabel(notes, text="\u2022 " + note, font=theme.FONT_BODY, text_color=theme.TEXT_DIM, justify="left", wraplength=640, anchor="w").pack(anchor="w", pady=3)

    def _card(self, title: str) -> "ctk.CTkFrame":
        frame = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        ctk.CTkLabel(frame, text=title, font=theme.FONT_SUBHEADING, text_color=theme.TEXT).pack(anchor="w", padx=14, pady=(12, 4))
        frame.grid(row=self._next_row, column=0, sticky="ew", pady=8)
        self._next_row += 1
        return frame