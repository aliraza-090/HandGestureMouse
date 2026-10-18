"""Local ``.env`` configuration for fully offline operation.

This module loads environment variables from a ``.env`` file if one is present.
It uses only the standard library (no ``python-dotenv`` dependency) and every
failure mode is non-fatal, so the application always starts and runs offline
even when the file is missing, unreadable, or malformed.

Values are read from the first existing candidate file:

1. an explicit path passed to :func:`load_env` / :func:`find_env_file`,
2. ``.env`` in the current working directory,
3. ``.env`` in the project root (source layout), and
4. ``.env`` next to the frozen executable / PyInstaller bundle.

Loaded values are copied into :data:`os.environ` without overwriting variables
that are already defined by the operating system, matching the usual
dotenv precedence.
"""

import os
import re
import sys
from typing import Dict, Optional

ENV_FILENAME = ".env"
ENV_EXAMPLE_FILENAME = ".env.example"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

# ``${VAR}`` (POSIX) and ``%VAR%`` (Windows) expansion.
_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}|%([^%]+)%")

#: Environment keys that map onto persisted application settings.
_SETTING_KEYS = {
    "EMERGENCY_HOTKEY": "emergency_hotkey",
}

_loaded: Dict[str, str] = {}


def project_root() -> str:
    """Best-effort project root for the source layout."""
    here = os.path.dirname(os.path.abspath(__file__))  # .../handgesturemouse/config
    package = os.path.dirname(here)  # .../handgesturemouse
    src = os.path.dirname(package)  # .../src
    return os.path.dirname(src)  # <project root>


def candidate_paths(env_path: Optional[str] = None) -> Dict[str, str]:
    """Return the ordered standard ``.env`` locations that are searched."""
    candidates: Dict[str, str] = {}
    if env_path:
        candidates["explicit"] = os.path.abspath(env_path)
    candidates["cwd"] = os.path.join(os.getcwd(), ENV_FILENAME)
    candidates["project"] = os.path.join(project_root(), ENV_FILENAME)
    candidates["exe"] = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), ENV_FILENAME)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates["bundle"] = os.path.join(meipass, ENV_FILENAME)
    return candidates


def find_env_file(env_path: Optional[str] = None) -> Optional[str]:
    """Return the ``.env`` path to use, or ``None`` when absent.

    When ``env_path`` is given only that exact file is considered; otherwise the
    standard candidate locations are searched in order.
    """
    if env_path:
        return env_path if os.path.isfile(env_path) else None
    for path in candidate_paths().values():
        try:
            if os.path.isfile(path):
                return path
        except OSError:  # pragma: no cover - defensive
            continue
    return None


def _expand(value: str, environ: Dict[str, str]) -> str:
    """Expand ``${VAR}`` and ``%VAR%`` references using ``environ``."""

    def replace(match: "re.Match[str]") -> str:
        name = match.group(1) or match.group(2)
        return environ.get(name, match.group(0))

    return _VAR_PATTERN.sub(replace, value)


def parse_env_text(text: str, environ: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Parse ``.env`` text into a dict (comments, quotes, expansion handled)."""
    env = os.environ if environ is None else environ
    scope: Dict[str, str] = dict(env)
    result: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.lstrip("\ufeff").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            hash_index = value.find(" #")
            if hash_index != -1:
                value = value[:hash_index].rstrip()
        parsed_value = _expand(value, scope)
        result[key] = parsed_value
        scope[key] = parsed_value
    return result


def load_env(
    env_path: Optional[str] = None,
    override: bool = False,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Load ``.env`` values and return them.

    Values are written into ``environ`` (defaults to :data:`os.environ`) only
    when the key is not already defined, unless ``override`` is True.  The file
    is never required: a missing or unreadable file yields an empty dict.
    """
    path = find_env_file(env_path)
    if path is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return {}

    target = os.environ if environ is None else environ
    values = parse_env_text(text, target)
    for key, value in values.items():
        if override or key not in target:
            target[key] = value
    _loaded.clear()
    _loaded.update(values)
    return dict(values)


def values() -> Dict[str, str]:
    """Return a copy of the values read by the most recent :func:`load_env`."""
    return dict(_loaded)


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    """Return an environment value (process env first, then last ``.env``)."""
    if key in os.environ:
        return os.environ[key]
    if key in _loaded:
        return _loaded[key]
    return default


def to_bool(value: object, default: bool = False) -> bool:
    """Coerce common ``.env`` boolean spellings to ``bool``."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def get_bool(key: str, default: bool = False) -> bool:
    """Return a boolean environment value (graceful default when absent)."""
    return to_bool(get(key), default)


def apply_to_settings(manager) -> Dict[str, object]:
    """Apply recognised ``.env`` values onto a ``SettingsManager``.

    Only values that are present and pass the settings validator are applied;
    any error is ignored so a bad ``.env`` can never stop the application.
    """
    applied: Dict[str, object] = {}
    for env_key, setting_key in _SETTING_KEYS.items():
        raw = get(env_key)
        if raw is None:
            continue
        try:
            manager.update({setting_key: raw})
            applied[setting_key] = manager.get(setting_key)
        except Exception:  # pragma: no cover - best-effort override
            continue
    return applied


__all__ = [
    "ENV_FILENAME",
    "ENV_EXAMPLE_FILENAME",
    "project_root",
    "candidate_paths",
    "find_env_file",
    "parse_env_text",
    "load_env",
    "values",
    "get",
    "get_bool",
    "to_bool",
    "apply_to_settings",
]
