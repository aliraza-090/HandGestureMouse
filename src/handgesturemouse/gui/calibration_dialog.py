"""Modal gesture-calibration wizard.

Two steps (hold hand open, then pinch).  Live progress is delivered from the
pipeline via ``PipelineEvent`` objects dispatched on the Tk main thread, so all
widget updates here happen on the main thread.
"""

import customtkinter as ctk

from . import theme


class CalibrationDialog(ctk.CTkToplevel):
    def __init__(self, master, controller) -> None:
        super().__init__(master)
        self._controller = controller
        self._finished = False

        self.title("Gesture Calibration")
        self.geometry("460x320")
        self.resizable(False, False)
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Gesture Calibration", font=theme.FONT_HEADING, text_color=theme.TEXT
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4))

        self.step_label = ctk.CTkLabel(
            self,
            text="Step 1 of 2 - Hold your hand open in front of the camera.",
            font=theme.FONT_BODY,
            text_color=theme.TEXT,
            wraplength=400,
            justify="left",
        )
        self.step_label.grid(row=1, column=0, sticky="w", padx=20, pady=(2, 6))

        self.progress_label = ctk.CTkLabel(
            self,
            text="Open frames captured: 0",
            font=theme.FONT_MONO,
            text_color=theme.TEXT_DIM,
        )
        self.progress_label.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 6))

        self.hint_label = ctk.CTkLabel(
            self,
            text="Keep your hand comfortably inside the frame.",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_FAINT,
            wraplength=400,
            justify="left",
        )
        self.hint_label.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 10))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=20, pady=(6, 18))
        buttons.grid_columnconfigure((0, 1), weight=1)

        self.cancel_btn = ctk.CTkButton(
            buttons,
            text="Cancel",
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_2,
            hover_color=theme.SURFACE_3,
            command=self._close,
        )
        self.cancel_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.next_btn = ctk.CTkButton(
            buttons,
            text="Next: Pinch",
            font=theme.FONT_BODY,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            state="disabled",
            command=self._advance,
        )
        self.next_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.after(150, self._raise)

    # -- helpers -----------------------------------------------------------

    def _raise(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except Exception:
            return False

    def _advance(self) -> None:
        if self._finished:
            self._close()
            return
        self._controller.calibration_advance()

    def _close(self) -> None:
        self._controller.calibration_closed()
        try:
            self.destroy()
        except Exception:
            pass

    # -- pipeline-driven updates -------------------------------------------

    def update_progress(self, payload) -> None:
        if not self._alive() or self._finished:
            return
        step = str(payload.get("step") or "")
        ready = bool(payload.get("ready"))
        if step == "open":
            self.step_label.configure(
                text="Step 1 of 2 - Hold your hand open in front of the camera.",
                text_color=theme.TEXT,
            )
            self.progress_label.configure(
                text=f"Open frames captured: {int(payload.get('open_samples') or 0)}"
            )
            self.next_btn.configure(text="Next: Pinch", state="normal" if ready else "disabled")
        elif step == "pinch":
            self.step_label.configure(
                text="Step 2 of 2 - Now make a natural pinch (thumb + index finger).",
                text_color=theme.TEXT,
            )
            self.progress_label.configure(
                text=f"Pinch frames captured: {int(payload.get('pinch_samples') or 0)}"
            )
            self.next_btn.configure(text="Finish", state="normal" if ready else "disabled")

    def show_result(self, payload) -> None:
        if not self._alive():
            return
        self._finished = True
        if bool(payload.get("ok")):
            self.step_label.configure(text="Calibration complete.", text_color=theme.SUCCESS)
            self.progress_label.configure(
                text=(
                    f"pinch threshold: {float(payload.get('pinch_threshold', 0.0)):.2f}   "
                    f"release: {float(payload.get('pinch_hold_threshold', 0.0)):.2f}"
                )
            )
            self.hint_label.configure(text="Values saved to your settings.")
        else:
            self.step_label.configure(
                text=str(payload.get("message") or "Calibration failed."),
                text_color=theme.DANGER,
            )
            self.progress_label.configure(text="")
            self.hint_label.configure(text="You can close this and try again.")
        self.cancel_btn.configure(state="disabled")
        self.next_btn.configure(text="Close", state="normal", fg_color=theme.ACCENT)
