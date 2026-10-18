"""Settings validation and persistence tests."""

import json

import pytest

from handgesturemouse.config.defaults import DEFAULTS, validate
from handgesturemouse.config.settings_manager import SettingsManager, SettingsError


def test_defaults_are_loaded(tmp_path):
    manager = SettingsManager(path=str(tmp_path / "settings.json"))
    assert manager.get("cursor_smoothing") == DEFAULTS["cursor_smoothing"]
    assert manager.get("camera_index") == 0


def test_set_and_persist_round_trip(tmp_path):
    path = str(tmp_path / "settings.json")
    manager = SettingsManager(path=path)
    manager.set("cursor_sensitivity", 2.5)
    manager.set("emergency_hotkey", "Ctrl+Alt+Q")
    manager.save()

    reloaded = SettingsManager(path=path)
    assert reloaded.get("cursor_sensitivity") == pytest.approx(2.5)
    assert reloaded.get("emergency_hotkey") == "ctrl+alt+q"


def test_invalid_value_is_rejected():
    ok, _, message = validate("cursor_sensitivity", "not-a-number")
    assert not ok
    assert message


def test_out_of_range_is_clamped_not_rejected():
    ok, value, _ = validate("cursor_sensitivity", 999)
    assert ok
    assert value == 5.0


def test_boolean_strings_are_coerced():
    ok, value, _ = validate("mirror_input", "false")
    assert ok and value is False
    ok, value, _ = validate("mirror_input", "yes")
    assert ok and value is True


def test_unknown_key_rejected():
    ok, _, message = validate("nonexistent", 1)
    assert not ok
    assert "unknown" in message


def test_set_invalid_raises(tmp_path):
    manager = SettingsManager(path=str(tmp_path / "s.json"))
    with pytest.raises(ValueError):
        manager.set("cursor_smoothing", "abc")


def test_update_multiple_and_reject_atomically(tmp_path):
    manager = SettingsManager(path=str(tmp_path / "s.json"))
    with pytest.raises(ValueError):
        manager.update({"cursor_smoothing": 0.2, "camera_index": "bad"})
    # nothing should have been applied because one value was invalid
    assert manager.get("cursor_smoothing") == DEFAULTS["cursor_smoothing"]


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")
    manager = SettingsManager(path=str(path))
    assert manager.get("cursor_smoothing") == DEFAULTS["cursor_smoothing"]


def test_stored_values_are_sanitised_on_load(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"cursor_sensitivity": 100, "camera_index": -5, "junk": 1}), encoding="utf-8")
    manager = SettingsManager(path=str(path))
    assert manager.get("cursor_sensitivity") == 5.0
    assert manager.get("camera_index") == 0
    assert "junk" not in manager.as_dict()


def test_reset_restores_defaults(tmp_path):
    path = str(tmp_path / "s.json")
    manager = SettingsManager(path=path)
    manager.set("scroll_sensitivity", 50.0)
    manager.reset()
    assert manager.get("scroll_sensitivity") == DEFAULTS["scroll_sensitivity"]


def test_non_object_json_falls_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    manager = SettingsManager(path=str(path))
    assert manager.get("cursor_smoothing") == DEFAULTS["cursor_smoothing"]


def test_tray_settings_have_defaults_and_validate():
    assert DEFAULTS["enable_tray"] is True
    assert DEFAULTS["minimize_to_tray"] is True
    assert DEFAULTS["close_to_tray"] is True
    ok, value, _ = validate("close_to_tray", "off")
    assert ok and value is False
    ok, value, _ = validate("enable_tray", 1)
    assert ok and value is True


def test_auto_open_camera_default_and_validation():
    assert DEFAULTS["auto_open_camera"] is True
    ok, value, _ = validate("auto_open_camera", "no")
    assert ok and value is False


def test_new_tray_settings_persist(tmp_path):
    path = str(tmp_path / "s.json")
    manager = SettingsManager(path=path)
    manager.update({"enable_tray": False, "minimize_to_tray": False})
    manager.save()
    reloaded = SettingsManager(path=path)
    assert reloaded.get("enable_tray") is False
    assert reloaded.get("minimize_to_tray") is False
    assert reloaded.get("close_to_tray") is True


def test_feature_settings_defaults_and_validation():
    assert DEFAULTS["enable_audio_feedback"] is True
    assert DEFAULTS["auto_start_windows"] is False
    assert DEFAULTS["eco_mode"] is True
    assert DEFAULTS["eco_idle_seconds"] == 45
    assert DEFAULTS["eco_fps"] == 5
    assert DEFAULTS["target_display"] == "primary"

    ok, value, _ = validate("target_display", "SECONDARY")
    assert ok and value == "secondary"
    ok, _, _ = validate("target_display", "quad")
    assert not ok

    ok, value, _ = validate("eco_fps", 999)
    assert ok and value == 30
    assert validate("eco_idle_seconds", 1)[1] == 5
    assert validate("auto_start_windows", "yes")[1] is True


def test_feature_settings_persist(tmp_path):
    path = str(tmp_path / "s.json")
    manager = SettingsManager(path=path)
    manager.update(
        {
            "enable_audio_feedback": False,
            "auto_start_windows": True,
            "eco_mode": False,
            "eco_idle_seconds": 120,
            "eco_fps": 10,
            "target_display": "secondary",
        }
    )
    manager.save()
    reloaded = SettingsManager(path=path)
    assert reloaded.get("enable_audio_feedback") is False
    assert reloaded.get("auto_start_windows") is True
    assert reloaded.get("eco_mode") is False
    assert reloaded.get("eco_idle_seconds") == 120
    assert reloaded.get("eco_fps") == 10
    assert reloaded.get("target_display") == "secondary"


def test_ux_settings_defaults_and_validation():
    assert DEFAULTS["start_control_on_launch"] is True
    assert DEFAULTS["show_tray_notifications"] is True
    ok, value, _ = validate("start_control_on_launch", "no")
    assert ok and value is False
    ok, value, _ = validate("show_tray_notifications", 1)
    assert ok and value is True


def test_ux_settings_persist(tmp_path):
    path = str(tmp_path / "s.json")
    manager = SettingsManager(path=path)
    manager.update({"start_control_on_launch": False, "show_tray_notifications": False})
    manager.save()
    reloaded = SettingsManager(path=path)
    assert reloaded.get("start_control_on_launch") is False
    assert reloaded.get("show_tray_notifications") is False