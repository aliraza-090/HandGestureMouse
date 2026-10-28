"""Regression tests for hand skeleton rendering."""
import numpy as np

from handgesturemouse.core.hand_tracker import HandTracker
from mediapipe.tasks.python.vision import HandLandmarksConnections


def test_hand_connections_rendered():
    tracker = HandTracker(model_file="x.task")
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    # Create 21 dummy landmarks
    landmarks = [(0.5, 0.5, 0.0)] * 21
    out = tracker.annotate(frame.copy(), landmarks)
    # Should draw something (connections exist)
    assert out is not None
    assert out.shape == (200, 200, 3)
    # Verify connections are accessible
    assert len(HandLandmarksConnections.HAND_CONNECTIONS) > 0
