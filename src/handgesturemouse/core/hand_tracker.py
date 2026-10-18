"""MediaPipe hand tracking wrapper.

Uses the MediaPipe Tasks ``HandLandmarker`` (VIDEO mode) which is the only
landmarking interface shipped with MediaPipe 1.x.  The writers of the model
file are published by Google and downloaded once by ``scripts/download_model.py``.

Landmarks are returned as plain ``(x, y, z)`` tuples of normalized
coordinates so the rest of the pipeline stays MediaPipe-free and testable.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..utils.paths import model_path
from .geometry import largest_hand

logger = logging.getLogger("handgesturemouse.tracker")

MODEL_FILE = "hand_landmarker.task"


class HandTrackerUnavailable(Exception):
    """Raised when MediaPipe or the model file is missing."""


@dataclass
class TrackedHand:
    """A single tracked hand."""

    handedness: str
    score: float
    landmarks: List[Tuple[float, float, float]] = field(default_factory=list)


@dataclass
class HandTrackerResult:
    """Output of one detection pass."""

    landmarks: Optional[List[Tuple[float, float, float]]] = None
    handedness: str = ""
    score: float = 0.0
    num_hands: int = 0
    error: str = ""


class HandTracker:
    """Thin wrapper around MediaPipe HandLandmarker (Tasks API)."""

    def __init__(
        self,
        model_file: Optional[str] = None,
        num_hands: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self.model_file = model_file or model_path()
        self.num_hands = max(1, min(2, int(num_hands)))
        self.min_detection_confidence = float(min_detection_confidence)
        self.min_tracking_confidence = float(min_tracking_confidence)
        self._landmarker = None
        self._mp = None
        self._vision = None
        self._video_mode = None
        self._frame_counter = 0

    # -- bindings ------------------------------------------------------------

    def _import(self):
        if self._mp is None:
            try:
                import mediapipe as mp

                from mediapipe.tasks.python import BaseOptions
                from mediapipe.tasks.python.vision import (
                    HandLandmarker,
                    HandLandmarkerOptions,
                    RunningMode,
                )

                self._mp = mp
                self._base_options = BaseOptions
                self._landmarker_cls = HandLandmarker
                self._options_cls = HandLandmarkerOptions
                self._video_mode = RunningMode.VIDEO
            except Exception as exc:
                raise HandTrackerUnavailable(
                    "MediaPipe Tasks is not installed or cannot be imported"
                ) from exc
        return self._mp

    def ensure_available(self) -> None:
        """Verify the model file exists and MediaPipe imports (idempotent)."""
        self._import()
        if not self.model_file or not os.path.isfile(self.model_file):
            raise HandTrackerUnavailable(
                f"hand landmarker model not found: {self.model_file or 'unset'}. "
                f"Run `python scripts/download_model.py` to fetch it."
            )

    def open(self) -> None:
        """Create the MediaPipe landmarker (idempotent)."""
        self.ensure_available()
        if self._landmarker is not None:
            return
        try:
            options = self._options_cls(
                base_options=self._base_options(model_asset_path=self.model_file),
                running_mode=self._video_mode,
                num_hands=self.num_hands,
                min_hand_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                min_hand_presence_confidence=self.min_detection_confidence,
            )
            self._landmarker = self._landmarker_cls.create_from_options(options)
        except Exception as exc:
            logger.exception("failed to create HandLandmarker")
            raise HandTrackerUnavailable(f"failed to initialise hand landmarker: {exc}") from exc

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                logger.debug("error closing landmarker", exc_info=True)
        self._landmarker = None

    def set_config(self, num_hands: int = 1, min_detection_confidence: float = 0.5) -> None:
        """Update configuration; reopens the landmarker when it changed."""
        new_num = max(1, min(2, int(num_hands)))
        new_conf = float(min_detection_confidence)
        if (
            new_num != self.num_hands
            or abs(new_conf - self.min_detection_confidence) > 1e-6
        ):
            self.num_hands = new_num
            self.min_detection_confidence = new_conf
            self.min_tracking_confidence = new_conf
            self.close()

    @property
    def is_open(self) -> bool:
        return self._landmarker is not None

    # -- inference -------------------------------------------------------------

    def detect(self, frame_bgr: np.ndarray) -> HandTrackerResult:
        """Run detection on a BGR OpenCV frame and mirror-track like selfie mode.

        The caller is responsible for handing the mirrored frame; we expect the
        frame exactly as it will be shown to the user.
        """
        max_ts = 1 << 30
        self._frame_counter += 1
        timestamp_ms = (self._frame_counter * 1000) % max_ts
        try:
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_bgr)
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as exc:
            logger.warning("detection failed: %s", exc)
            return HandTrackerResult(error=str(exc))

        num_hands = len(result.hand_landmarks)
        if num_hands == 0:
            return HandTrackerResult(num_hands=0)

        hands = []
        for i in range(num_hands):
            handedness = result.handedness[i][0].category_name if i < len(result.handedness) else ""
            score = result.handedness[i][0].score if i < len(result.handedness) else 0.0
            landmarks = [
                (float(lm.x), float(lm.y), float(lm.z))
                for lm in result.hand_landmarks[i]
            ]
            hands.append(TrackedHand(handedness=handedness, score=score, landmarks=landmarks))

        hand, _ = largest_hand([h.landmarks for h in hands])
        handedness = next((h.handedness for h in hands if _same(h.landmarks, hand)), "")
        score = next((h.score for h in hands if _same(h.landmarks, hand)), 0.0)
        return HandTrackerResult(
            landmarks=hand,
            handedness=handedness,
            score=score,
            num_hands=num_hands,
        )

    def annotate(self, frame_bgr: np.ndarray, landmarks) -> np.ndarray:
        """Draw landmarks / connections onto a BGR frame (in place)."""
        if not landmarks:
            return frame_bgr
        try:
            from mediapipe.tasks.python.vision import HandLandmarksConnections
            from mediapipe.tasks.python.vision.drawing_utils import draw_landmarks
            from mediapipe.tasks.python.vision.drawing_styles import (
                get_default_hand_connections_style,
                get_default_hand_landmarks_style,
            )

            from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark

            normalised = [NormalizedLandmark(x=lm[0], y=lm[1], z=lm[2]) for lm in landmarks]
            draw_landmarks(
                frame_bgr,
                normalised,
                HandLandmarksConnections.HAND_CONNECTIONS,
                get_default_hand_landmarks_style(),
                get_default_hand_connections_style(),
            )
        except Exception:
            logger.debug("landmark drawing failed", exc_info=True)
        return frame_bgr


def _same(a, b) -> bool:
    if len(a) != len(b):
        return False
    return all(x == y for x, y in zip(a, b))