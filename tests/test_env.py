"""Tests for the local ``.env`` configuration loader (stdlib-only)."""

import os

from handgesturemouse.config import env
from handgesturemouse.config.settings_manager import SettingsManager

SAMPLE = """
# comment line
APP_ENV=production
export OFFLINE_MODE=True
TELEMETRY_ENABLED=False
QUOTED="hello world"
SPACED = value with spaces
INLINE=abc # trailing comment
HASH_IN_VALUE=pass#word
EXPANDED=${APP_ENV}-suffix
WINPATH=%APPDATA%/HandGestureMouse
NOEQUALS
"""


def test_parse_handles_comments_quotes_and_export():
    parsed = env.parse_env_text(SAMPLE, environ={"APPDATA": "C:/Users/x/AppData/Roaming"})
    assert parsed["APP_ENV"] == "production"
    assert parsed["OFFLINE_MODE"] == "True"
    assert parsed["QUOTED"] == "hello world"
    assert parsed["SPACED"] == "value with spaces"
    assert parsed["INLINE"] == "abc"
    assert parsed["HASH_IN_VALUE"] == "pass#word"
    assert parsed["EXPANDED"] == "production-suffix"
    assert parsed["WINPATH"] == "C:/Users/x/AppData/Roaming/HandGestureMouse"
    assert "NOEQUALS" not in parsed


def test_expansion_leaves_unknown_vars_untouched():
    parsed = env.parse_env_text("MODEL=%NOT_SET%/model.task", environ={})
    assert parsed["MODEL"] == "%NOT_SET%/model.task"


def test_load_env_populates_without_overriding(tmp_path):
    path = tmp_path / ".env"
    path.write_text("HGM_FLAG=fromfile\n", encoding="utf-8")
    target = {"HGM_FLAG": "fromenv"}
    env.load_env(env_path=str(path), environ=target)
    assert target["HGM_FLAG"] == "fromenv"  # existing value wins
    env.load_env(env_path=str(path), override=True, environ=target)
    assert target["HGM_FLAG"] == "fromfile"


def test_load_env_missing_file_is_graceful(tmp_path):
    missing = str(tmp_path / "does-not-exist.env")
    assert env.find_env_file(missing) is None
    assert env.load_env(env_path=missing, environ={}) == {}


def test_load_env_unreadable_directory_is_graceful(tmp_path):
    assert env.load_env(env_path=str(tmp_path), environ={}) == {}


def test_get_bool_parses_common_spellings(tmp_path):
    path = tmp_path / ".env"
    path.write_text("HGM_ON=yes\nHGM_OFF=off\nHGM_JUNK=maybe\n", encoding="utf-8")
    env.load_env(env_path=str(path), environ={})
    assert env.get_bool("HGM_ON") is True
    assert env.get_bool("HGM_OFF") is False
    assert env.get_bool("HGM_JUNK", default=True) is True
    assert env.get_bool("HGM_MISSING", default=True) is True
    assert env.to_bool(1) is True
    assert env.to_bool("0") is False


def test_apply_to_settings_maps_emergency_hotkey(tmp_path):
    path = tmp_path / ".env"
    path.write_text("EMERGENCY_HOTKEY=Ctrl+Shift+Q\n", encoding="utf-8")
    env.load_env(env_path=str(path), environ={})
    manager = SettingsManager(path=str(tmp_path / "settings.json"))
    applied = env.apply_to_settings(manager)
    assert applied["emergency_hotkey"] == "ctrl+shift+q"
    assert manager.get("emergency_hotkey") == "ctrl+shift+q"


def test_apply_to_settings_ignores_invalid_values(tmp_path):
    path = tmp_path / ".env"
    path.write_text("EMERGENCY_HOTKEY=\n", encoding="utf-8")
    env.load_env(env_path=str(path), environ={})
    manager = SettingsManager(path=str(tmp_path / "settings.json"))
    env.apply_to_settings(manager)
    assert manager.get("emergency_hotkey") == "ctrl+alt+e"


def test_project_root_contains_pyproject():
    root = env.project_root()
    assert os.path.isfile(os.path.join(root, "pyproject.toml"))
    assert "project" in env.candidate_paths()
