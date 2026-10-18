"""Hand geometry helpers.

All functions operate on normalized (0..1) landmark coordinates and are pure
math, so they are fully unit-testable without MediaPipe or a camera.
"""

import math
from typing import Iterable, Sequence, Tuple

# MediaPipe hand landmark indices
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

Point = Sequence[float]


def dist2(a: Point, b: Point) -> float:
    """Squared Euclidean distance between two 2D points."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def dist(a: Point, b: Point) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def hand_scale(landmarks: Sequence[Point]) -> float:
    """Reference length used to normalise distances.

    Uses the wrist-to-middle-MCP distance and falls back to the palm size
    (index-MCP to pinky-MCP) when those landmarks are degenerate.
    """
    s0 = dist(landmarks[WRIST], landmarks[MIDDLE_MCP])
    if s0 > 1e-6:
        return s0
    return max(dist(landmarks[INDEX_MCP], landmarks[PINKY_MCP]), 1e-6)


def finger_extended(landmarks: Sequence[Point], tip: int, pip: int, gain: float = 1.0) -> bool:
    """Orientation-independent extension test.

    A finger is considered extended when its tip is farther from the wrist
    than its PIP joint is, scaled by ``gain``.
    """
    wrist = landmarks[WRIST]
    return dist(wrist, landmarks[tip]) > gain * dist(wrist, landmarks[pip])


def thumb_extended(landmarks: Sequence[Point], gain: float = 1.0) -> bool:
    """Thumb extension using the lateral distance from the index MCP."""
    ref = landmarks[INDEX_MCP]
    return dist(landmarks[THUMB_TIP], ref) > gain * dist(landmarks[THUMB_IP], ref)


def pinch_ratio(landmarks: Sequence[Point], tip_a: int = THUMB_TIP, tip_b: int = INDEX_TIP) -> float:
    """Distance between two fingertips normalised by hand scale.

    A value well below the pinch threshold indicates the fingertips touch.
    """
    return dist(landmarks[tip_a], landmarks[tip_b]) / hand_scale(landmarks)


def pinch_index(landmarks: Sequence[Point]) -> float:
    return pinch_ratio(landmarks, THUMB_TIP, INDEX_TIP)


def pinch_middle(landmarks: Sequence[Point]) -> float:
    return pinch_ratio(landmarks, THUMB_TIP, MIDDLE_TIP)


def hand_center(landmarks: Sequence[Point]) -> Point:
    """Approximate hand centroid (average of all 21 landmarks)."""
    n = len(landmarks)
    if n == 0:
        return (0.0, 0.0)
    x = sum(p[0] for p in landmarks) / n
    y = sum(p[1] for p in landmarks) / n
    return (x, y)


def largest_hand(hands: Iterable[Sequence[Point]]) -> Tuple[Sequence[Point], float]:
    """Return the hand with the largest palm span and its score."""
    best = None
    best_score = -1.0
    for landmarks in hands:
        score = _hand_score(landmarks)
        if score > best_score:
            best, best_score = landmarks, score
    return best, best_score


def _hand_score(landmarks: Sequence[Point]) -> float:
    wrist = landmarks[WRIST]
    return dist(wrist, landmarks[MIDDLE_MCP]) + dist(wrist, landmarks[INDEX_MCP])