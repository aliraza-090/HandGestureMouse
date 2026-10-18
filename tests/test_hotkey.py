"""Emergency hotkey parsing tests (no global listener is started)."""

from handgesturemouse.app import Application


def test_plain_modifiers_are_bracketed():
    assert Application._to_pynput_hotkey("ctrl+alt+e") == "<ctrl>+<alt>+e"
    assert Application._to_pynput_hotkey("ctrl+shift+q") == "<ctrl>+<shift>+q"


def test_already_bracketed_is_preserved():
    assert Application._to_pynput_hotkey("<ctrl>+<alt>+e") == "<ctrl>+<alt>+e"


def test_whitespace_and_case_are_normalised():
    assert Application._to_pynput_hotkey("  CTRL + Alt + E ") == "<ctrl>+<alt>+e"


def test_aliases_map_to_pynput_modifiers():
    assert Application._to_pynput_hotkey("win+space") == "<cmd>+space"
    assert Application._to_pynput_hotkey("control+alt+x") == "<ctrl>+<alt>+x"


def test_hide_instead_of_quit_only_when_tray_active_and_configured():
    # Both must be true to hide; otherwise the app quits.
    assert Application._hide_instead_of_quit(True, True) is True
    assert Application._hide_instead_of_quit(True, False) is False
    assert Application._hide_instead_of_quit(False, True) is False
    assert Application._hide_instead_of_quit(False, False) is False