"""Default settings and validation rules.

Every setting is defined with a validator and a human readable range, so the
SettingsManager can sanitise saved values that may come from an older version
or from a hand-edited JSON file.
"""

from typing import Callable, Dict, Tuple

_SENSITIVITY = (0.1, 5.0)
_SMOOTHING = (0.0, 1.0)
_THRESHOLD = (0.1, 1.0)
_COOLDOWN = (0.0, 5.0)
_SCROLL = (5.0, 100.0)
_CAMERA = (0, 10)
_HOTKEY_SAFE = (0.0, 0.5)
_ECO_IDLE = (5, 600)
_ECO_FPS = (1, 30)

DISPLAY_CHOICES = ("primary", "secondary", "span")

DEFAULTS: Dict[str, object] = {
    "camera_index": 0,
    "screen_width": 0,  # 0 => auto-detect current monitor resolution
    "screen_height": 0,  # 0 => auto-detect current monitor resolution
    "cursor_sensitivity": 1.0,
    "cursor_smoothing": 0.55,
    "mouse_smoothing_deade_zone": 0.02,
    "pinch_threshold": 0.30,
    "pinch_hold_threshold": 0.36,
    "click_hold_time": 0.35,  # seconds; longer contacts become a drag
    "gesture_cooldown": 0.35,  # seconds between discrete gestures
    "scroll_sensitivity": 30.0,
    "scroll_yield": 0.002,  # dead-band below which scroll deltas are ignored
    "num_hands": 1,
    "detection_confidence": 0.5,
    "max_fps": 30,
    "mirror_input": True,
    "use_gesture_move": True,
    "use_gesture_left_click": True,
    "use_gesture_right_click": True,
    "use_gesture_scroll": True,
    "use_gesture_drag": True,
    "emergency_hotkey": "ctrl+alt+e",
    "auto_open_camera": True,
    "enable_tray": True,  # show a Windows system tray icon
    "minimize_to_tray": True,  # minimizing the window hides it to the tray
    "close_to_tray": True,  # closing the window hides to tray instead of exiting
    "enable_audio_feedback": True,  # subtle sound cues for gestures
    "auto_start_windows": False,  # launch on Windows sign-in (HKCU Run key)
    "start_control_on_launch": True,  # begin controlling the mouse as soon as the app opens
    "show_tray_notifications": True,  # toast when the window is hidden to the tray
    "eco_mode": True,  # throttle tracking when no hand is present
    "eco_idle_seconds": 45,  # idle time before the eco throttle engages
    "eco_fps": 5,  # tracking rate while idle in eco mode
    "target_display": "primary",  # primary | secondary | span
}

_RULES: Dict[str, Callable[[object], Tuple[bool, object, str]]] = {}


def _range_rule(lo: float, hi: float):
    def rule(value: object) -> Tuple[bool, object, str]:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return False, float(lo), f"expected a number between {lo} and {hi}"
        num = min(max(num, lo), hi)
        return True, num, ""
    return rule


def _int_rule(lo: int, hi: int):
    def rule(value: object) -> Tuple[bool, object, str]:
        try:
            num = int(float(value))
        except (TypeError, ValueError):
            return False, 0, f"expected an integer between {lo} and {hi}"
        num = min(max(num, lo), hi)
        return True, num, ""
    return rule


def _bool_rule(value: object) -> Tuple[bool, object, str]:
    if isinstance(value, bool):
        return True, value, ""
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "on"}:
        return True, True, ""
    if isinstance(value, str) and value.strip().lower() in {"false", "0", "no", "off"}:
        return True, False, ""
    if value in (0, 1):
        return True, bool(value), ""
    return False, False, "expected a boolean"


def _hotkey_text(value: object) -> Tuple[bool, object, str]:
    if not isinstance(value, str) or not value.strip():
        return False, "ctrl+alt+e", "expected a non-empty hotkey string"
    return True, value.strip().lower(), ""


def _choice_rule(*allowed: str):
    allowed_lower = tuple(a.lower() for a in allowed)

    def rule(value: object) -> Tuple[bool, object, str]:
        if not isinstance(value, str) or value.strip().lower() not in allowed_lower:
            return False, allowed[0], f"expected one of: {', '.join(allowed)}"
        return True, value.strip().lower(), ""

    return rule


_RULES = {
    "camera_index": _int_rule(*_CAMERA),
    "screen_width": _int_rule(0, 32768),
    "screen_height": _int_rule(0, 32768),
    "cursor_sensitivity": _range_rule(*_SENSITIVITY),
    "cursor_smoothing": _range_rule(*_SMOOTHING),
    "mouse_smoothing_deade_zone": _range_rule(*_HOTKEY_SAFE),
    "pinch_threshold": _range_rule(*_THRESHOLD),
    "pinch_hold_threshold": _range_rule(*_THRESHOLD),
    "click_hold_time": _range_rule(*_COOLDOWN),
    "gesture_cooldown": _range_rule(*_COOLDOWN),
    "scroll_sensitivity": _range_rule(*_SCROLL),
    "scroll_yield": _range_rule(*_HOTKEY_SAFE),
    "num_hands": _int_rule(1, 2),
    "detection_confidence": _range_rule(0.2, 1.0),
    "max_fps": _int_rule(1, 120),
    "mirror_input": _bool_rule,
    "use_gesture_move": _bool_rule,
    "use_gesture_left_click": _bool_rule,
    "use_gesture_right_click": _bool_rule,
    "use_gesture_scroll": _bool_rule,
    "use_gesture_drag": _bool_rule,
    "emergency_hotkey": _hotkey_text,
    "auto_open_camera": _bool_rule,
    "enable_tray": _bool_rule,
    "minimize_to_tray": _bool_rule,
    "close_to_tray": _bool_rule,
    "enable_audio_feedback": _bool_rule,
    "auto_start_windows": _bool_rule,
    "start_control_on_launch": _bool_rule,
    "show_tray_notifications": _bool_rule,
    "eco_mode": _bool_rule,
    "eco_idle_seconds": _int_rule(*_ECO_IDLE),
    "eco_fps": _int_rule(*_ECO_FPS),
    "target_display": _choice_rule(*DISPLAY_CHOICES),
}


def validate(key: str, value: object) -> Tuple[bool, object, str]:
    """Validate ``value`` for ``key``.

    Returns a ``(ok, normalized, message)`` tuple.  When ``ok`` is True the
    normalized value is safe to store; otherwise the message explains why.
    """
    if key not in DEFAULTS:
        return False, value, f"unknown setting: {key}"
    rule = _RULES.get(key)
    if rule is None:
        return True, value, ""
    return rule(value)


def coerce_all(values: Dict[str, object]) -> Dict[str, object]:
    """Coerce every known key in ``values`` through its validator."""
    result: Dict[str, object] = {}
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        ok, normalized, _ = validate(key, value)
        result[key] = normalized if ok else DEFAULTS[key]
    return result