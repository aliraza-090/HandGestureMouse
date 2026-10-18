# PyInstaller spec for HandGestureMouse.
#
# Build a folder-based (one-dir) distribution first - it is easier to debug:
#     pyinstaller packaging/HandGestureMouse.spec --noconfirm
#
# A single-file build is also supported (set ONE_FILE = True below); note that
# MediaPipe ships sizeable native libraries, so the single-file executable is
# large and slower to start because it unpacks on every launch.

import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ONE_FILE = False

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
RESOURCES = os.path.join(SRC, "handgesturemouse", "resources")
ICON = os.path.join(RESOURCES, "icons", "app.ico")

datas = [
    (os.path.join(RESOURCES, "models"), "resources/models"),
    (os.path.join(RESOURCES, "icons"), "resources/icons"),
]

# CustomTkinter ships JSON themes / assets that must be collected.
datas += collect_data_files("customtkinter")

# MediaPipe pulls in native libs + data files; collect everything it needs.
mp_datas, mp_binaries, mp_hidden = collect_all("mediapipe")

hiddenimports = list(mp_hidden) + collect_submodules("pystray") + [
    "mediapipe",
    "mediapipe.tasks",
    "mediapipe.tasks.python",
    "mediapipe.tasks.python.vision",
    "pynput",
    "pynput.keyboard",
    "pyautogui",
    "pystray",
    "pystray._win32",
    "PIL",
    "PIL.Image",
    "cv2",
    "numpy",
    "winsound",
    "winreg",
    # Feature-expansion modules (some are imported lazily at runtime).
    "handgesturemouse.core.eco",
    "handgesturemouse.core.calibration",
    "handgesturemouse.core.reconnect",
    "handgesturemouse.core.screens",
    "handgesturemouse.utils.feedback",
    "handgesturemouse.utils.autostart",
    "handgesturemouse.gui.calibration_dialog",
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[SRC],
    binaries=mp_binaries,
    datas=datas + mp_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "test", "pytest", "_pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

_icon = ICON if os.path.isfile(ICON) else None

if ONE_FILE:
    # Single-file build: everything is unpacked to a temp dir on launch.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="HandGestureMouse",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=_icon,
    )
else:
    # Folder build (recommended): dist/HandGestureMouse/HandGestureMouse.exe
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="HandGestureMouse",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=_icon,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="HandGestureMouse",
    )