"""Live hand tracking view: webcam feed with landmarks and gesture status."""

import io
from typing import Dict, Optional

import customtkinter as ctk
from PIL import Image

from . import theme

VIEW_W = 640
VIEW_H = 360


class CameraView(ctk.CTkFrame):
    def __init__(self, master, controller) -> None:
        super().__init__(master, fg_color="transparent")
        self._controller = controller
        self._image_ref = None
        self._last = {"camera": False, "hand": False, "gesture": "", "fps": 0.0, "command": ""}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        ctk.CTkLabel(header, text="Live Hand Tracking", font=theme.FONT_HEADING, text_color=theme.TEXT).pack(side="left")
        self.fps_label = ctk.CTkLabel(
            header, text="0 FPS", font=theme.FONT_MONO, text_color=theme.TEXT_DIM
        )
        self.fps_label.pack(side="right")

        # video box --------------------------------------------------------
        video_box = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        video_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=6)

        self.video_label = ctk.CTkLabel(video_box, text="", fg_color=theme.SURFACE)
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Reconnect badge (crash recovery) + transient gesture feedback flash.
        self.reconnect_label = ctk.CTkLabel(
            video_box,
            text="",
            font=theme.FONT_SUBHEADING,
            text_color=theme.DANGER,
            fg_color=theme.SURFACE,
        )
        self.feedback_label = ctk.CTkLabel(
            video_box,
            text="",
            font=theme.FONT_SUBHEADING,
            text_color=theme.ACCENT,
            fg_color=theme.SURFACE,
        )
        self.reconnect_label.place(relx=0.5, rely=0.07, anchor="center")
        self.reconnect_label.place_forget()
        self.feedback_label.place(relx=0.5, rely=0.92, anchor="center")
        self.feedback_label.place_forget()
        self._feedback_job = None

        self.no_hand_label = ctk.CTkLabel(
            video_box,
            text="No hand detected.\nMove your hand into the camera frame.",
            font=theme.FONT_BODY,
            text_color=theme.TEXT,
            fg_color="transparent",
        )
        self.camera_off_label = ctk.CTkLabel(
            video_box,
            text="Camera is offline. Check the camera in Settings.",
            font=theme.FONT_BODY,
            text_color=theme.DANGER,
            fg_color="transparent",
        )
        self.no_hand_label.place(relx=0.5, rely=0.5, anchor="center")
        self.camera_off_label.place(relx=0.5, rely=0.5, anchor="center")
        self.no_hand_label.place_forget()
        self.camera_off_label.place_forget()

        # status bar ----------------------------------------------------------
        status = ctk.CTkFrame(self, fg_color="transparent")
        status.grid(row=2, column=0, sticky="ew", padx=20, pady=(6, 4))
        status.grid_columnconfigure((0, 1, 2), weight=1)

        self.camera_badge = self._badge(status, "CAMERA")
        self.camera_badge.grid(row=0, column=0, sticky="w")
        self.gesture_badge = self._badge(status, "GESTURE")
        self.gesture_badge.grid(row=0, column=1, sticky="w")
        self.command_badge = self._badge(status, "ACTION")
        self.command_badge.grid(row=0, column=2, sticky="w")

        footer = ctk.CTkLabel(
            self,
            text="Feed is mirrored. Use your right hand for easiest control. Emergency stop: ctrl+alt+e (configurable).",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_FAINT,
        )
        footer.grid(row=3, column=0, sticky="w", padx=20, pady=(4, 16))

    def _badge(self, parent, title: str) -> "ctk.CTkFrame":
        frame = ctk.CTkFrame(parent, fg_color=theme.SURFACE_2, corner_radius=theme.RADIUS_SM)
        ctk.CTkLabel(frame, text=title, font=theme.FONT_SMALL, text_color=theme.TEXT_FAINT).pack(side="left", padx=(10, 4), pady=6)
        value = ctk.CTkLabel(frame, text="Off", font=theme.FONT_SUBHEADING, text_color=theme.TEXT, width=150)
        value.pack(side="left", padx=(4, 10), pady=6)
        setattr(self, f"{title.lower()}_value", value)
        return frame

    # -- frame rendering --------------------------------------------------

    def show_frame(self, jpeg_bytes: bytes) -> None:
        try:
            image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        except Exception:
            return
        image = _cover(image, VIEW_W, VIEW_H)
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(VIEW_W, VIEW_H))
        self._image_ref = ctk_image
        self.video_label.configure(image=ctk_image, text="")

    # -- status updates -----------------------------------------------------

    def update_status(self, payload: Dict[str, object]) -> None:
        self._last = {
            "camera": bool(payload.get("camera_open")),
            "hand": bool(payload.get("hand")),
            "gesture": str(payload.get("gesture") or ""),
            "fps": float(payload.get("fps") or 0.0),
            "command": str(payload.get("command") or ""),
        }
        self.fps_label.configure(text=f"{self._last['fps']:.0f} FPS")

        camera_ok = self._last["camera"]
        hand_ok = self._last["hand"]
        gesture = self._last["gesture"].replace("-", " ").upper() or "NONE"
        command = self._last["command"] or "none"

        self._set_badge("camera", "ON" if camera_ok else "OFF", theme.SUCCESS if camera_ok else theme.DANGER)
        self._set_badge("gesture", gesture, theme.WARN if hand_ok else theme.TEXT_FAINT)
        self._set_badge("action", command.upper(), theme.ACCENT)

        if not camera_ok:
            self.camera_off_label.place(relx=0.5, rely=0.5, anchor="center")
            self.no_hand_label.place_forget()
        elif not hand_ok:
            self.camera_off_label.place_forget()
            self.no_hand_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.camera_off_label.place_forget()
            self.no_hand_label.place_forget()

    def _set_badge(self, name: str, text: str, color: str) -> None:
        label = getattr(self, f"{name}_value", None)
        if label is not None:
            label.configure(text=text, text_color=color)

    # -- crash recovery + feedback ------------------------------------------

    def update_camera_state(self, payload: Dict[str, object]) -> None:
        state = str(payload.get("state") or "")
        if state == "reconnecting":
            attempt = payload.get("attempt")
            total = payload.get("max_attempts")
            text = f"Camera Disconnected - Reconnecting ({attempt}/{total})..."
        elif state == "disconnected":
            text = "Camera Disconnected - Reconnecting..."
        elif state == "failed":
            text = "Camera Disconnected - retries exhausted. Check Settings."
        else:
            self.reconnect_label.place_forget()
            return
        self.reconnect_label.configure(text=text)
        self.reconnect_label.place(relx=0.5, rely=0.07, anchor="center")

    def flash_feedback(self, action: str) -> None:
        if not action:
            return
        labels = {
            "left_click": "LEFT CLICK",
            "right_click": "RIGHT CLICK",
            "drag": "DRAG ENGAGED",
            "emergency": "EMERGENCY STOP",
        }
        text = labels.get(action, action.replace("_", " ").upper())
        color = theme.DANGER if action == "emergency" else theme.ACCENT
        self.feedback_label.configure(text=text, text_color=color)
        self.feedback_label.place(relx=0.5, rely=0.92, anchor="center")
        if self._feedback_job is not None:
            try:
                self.after_cancel(self._feedback_job)
            except Exception:
                pass
        self._feedback_job = self.after(600, self._hide_feedback)

    def _hide_feedback(self) -> None:
        self._feedback_job = None
        try:
            self.feedback_label.place_forget()
        except Exception:
            pass


def _cover(image: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Resize to fit ``(box_w, box_h)`` preserving aspect ratio without cropping."""
    try:
        scale = min(box_w / image.width, box_h / image.height)
        if scale <= 0:
            scale = 1.0
        new_w, new_h = max(1, int(image.width * scale)), max(1, int(image.height * scale))
        image = image.resize((new_w, new_h), Image.LANCZOS)
        # Create canvas with background color to avoid stretching
        canvas = Image.new('RGB', (box_w, box_h), (23, 27, 36))  # theme.SURFACE_2 approx
        left = (box_w - new_w) // 2
        top = (box_h - new_h) // 2
        canvas.paste(image, (left, top))
        return canvas
    except Exception:
        scale = max(box_w / image.width, box_h / image.height)
        new_w, new_h = max(1, int(image.width * scale)), max(1, int(image.height * scale))
        image = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - box_w) // 2
        top = (new_h - box_h) // 2
        return image.crop((left, top, left + box_w, top + box_h))