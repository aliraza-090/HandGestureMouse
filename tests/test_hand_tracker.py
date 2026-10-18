"""Hand-tracker error handling: missing model, detect-before-open, annotate."""

import numpy as np
import pytest

from handgesturemouse.core.hand_tracker import HandTracker, HandTrackerUnavailable


def test_missing_model_raises_helpful_error(tmp_path, monkeypatch):
    tracker = HandTracker(model_file=str(tmp_path / "missing.task"))
    # Avoid importing MediaPipe: only the model-file check is under test.
    monkeypatch.setattr(tracker, "_import", lambda: object())
    with pytest.raises(HandTrackerUnavailable) as excinfo:
        tracker.ensure_available()
    message = str(excinfo.value)
    assert "not found" in message
    assert "download_model" in message


def test_detect_without_open_returns_error_not_crash():
    tracker = HandTracker(model_file="does-not-matter.task")
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    result = tracker.detect(frame)
    assert result.error
    assert result.landmarks is None


def test_annotate_without_landmarks_is_identity():
    tracker = HandTracker(model_file="x.task")
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    assert tracker.annotate(frame, []) is frame
    assert tracker.annotate(frame, None) is frame


class _FakeLandmark:
    """Mimics mediapipe NormalizedLandmark: attributes only, NOT iterable."""

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __iter__(self):  # explicitly non-iterable, like the real object
        raise TypeError("'NormalizedLandmark' object is not iterable")


class _FakeCategory:
    def __init__(self, name, score):
        self.category_name = name
        self.score = score


class _FakeResult:
    def __init__(self, hand_landmarks, handedness):
        self.hand_landmarks = hand_landmarks
        self.handedness = handedness


class _FakeLandmarker:
    def __init__(self, result):
        self._result = result

    def detect_for_video(self, image, timestamp_ms):
        return self._result


class _FakeMP:
    class ImageFormat:
        SRGB = "SRGB"

    class Image:
        def __init__(self, image_format=None, data=None):
            self.image_format = image_format
            self.data = data


def test_detect_reads_normalized_landmark_attributes():
    # Reproduces the live crash: NormalizedLandmark is not iterable.
    raw = [_FakeLandmark(0.1 * i, 0.2 * i, 0.3 * i) for i in range(21)]

    tracker = HandTracker(model_file="does-not-matter.task")
    tracker._mp = _FakeMP
    tracker._landmarker = _FakeLandmarker(
        _FakeResult(
            hand_landmarks=[raw],
            handedness=[[_FakeCategory("Right", 0.97)]],
        )
    )

    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    result = tracker.detect(frame)

    assert result.error == ""
    assert result.num_hands == 1
    assert result.handedness == "Right"
    assert abs(result.score - 0.97) < 1e-9
    assert result.landmarks[0] == (0.0, 0.0, 0.0)
    assert result.landmarks[1] == (0.1, 0.2, 0.3)
    assert all(isinstance(v, float) for v in result.landmarks[0])


def test_detect_no_hands_returns_empty_result():
    tracker = HandTracker(model_file="does-not-matter.task")
    tracker._mp = _FakeMP
    tracker._landmarker = _FakeLandmarker(_FakeResult(hand_landmarks=[], handedness=[]))
    result = tracker.detect(np.zeros((16, 16, 3), dtype=np.uint8))
    assert result.num_hands == 0
    assert result.landmarks is None
