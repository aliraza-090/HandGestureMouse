# HandGestureMouse — Real-Time Hand Gesture Virtual Mouse

**Developed by Ali Raza Chakrani**

Control your Windows mouse cursor in real time using hand gestures captured from
an ordinary webcam. Everything runs **locally and offline** — no cloud services,
no accounts, no network access, and no data ever leaves your machine.

HandGestureMouse uses Google **MediaPipe Tasks** hand-landmark detection on top of
**OpenCV**, drives the real OS cursor through **PyAutoGUI**, and presents a modern
**CustomTkinter** desktop UI with a background **system-tray** mode.

> Platform: Windows 10/11 (x64) · Python 3.10+ · Fully offline

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Supported gestures](#supported-gestures)
- [Installation & setup](#installation--setup)
- [Build & packaging](#build--packaging)
- [Architecture](#architecture)
- [Settings reference](#settings-reference)
- [Testing](#testing)
- [Offline & privacy](#offline--privacy)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

---

## Features

- **Real-time 21-landmark hand tracking** using MediaPipe Tasks (Hand Landmarker),
  running continuously at up to 30 FPS.
- **OS-level, system-wide mouse control** — the gestures drive the *real* Windows
  cursor and buttons, so they work in any application, not just inside the app.
- **EMA jitter smoothing** with a configurable dead zone for a steady, natural
  cursor (exponential moving average + per-frame smoothing factor).
- **Fail-safe emergency controls**:
  - a global emergency hotkey (default `Ctrl+Alt+E`, configurable — set it to
    `ESC` if you prefer),
  - a PyAutoGUI **corner trip** (slam the pointer into the top-left corner),
  - an always-visible **STOP** button.
  Any of these instantly releases every held mouse button.
- **Background system-tray integration** — minimize or close the window to the
  tray and tracking keeps running; a notification confirms the app is still active
  and shows the emergency hotkey.
- **Active on launch** — mouse control starts automatically when the app opens,
  so it never sits in a passive state you have to toggle.
- **Live camera preview** with the 21-landmark skeleton overlay and a
  high-contrast on-frame gesture/action badge.
- **Gesture calibration wizard** to tune the pinch thresholds to your hand size
  and camera distance.
- **Multi-monitor support** — control the Primary display, a Secondary display,
  or the full Virtual Span.
- **Eco / battery saver** — throttles inference after inactivity and restores
  full-rate tracking within a frame when a hand returns.
- **Crash recovery / health monitor** — a single-frame camera buffer and
  delayed-frame tolerance avoid false disconnects; real disconnects release all
  buttons and auto-reconnect with backoff while the GUI stays responsive.
- **Audio feedback** — subtle Windows sound cues for click, drag, and emergency.
- **Start with Windows** — optional per-user registry auto-start.
- **Persistent settings** at `%APPDATA%\HandGestureMouse\settings.json` and a
  rotating log at `%APPDATA%\HandGestureMouse\logs\app.log`.

---

## Tech stack

| Layer            | Technology                                  |
| ---------------- | ------------------------------------------- |
| Language         | Python 3.10+ (developed on 3.14)            |
| Hand tracking    | MediaPipe Tasks (Hand Landmarker)           |
| Video I/O        | OpenCV (`opencv-contrib-python`)            |
| Numerics         | NumPy                                       |
| Mouse control    | PyAutoGUI                                   |
| GUI              | CustomTkinter (Tkinter)                     |
| Global hotkey    | pynput                                      |
| System tray      | pystray                                     |
| Imaging          | Pillow                                      |
| Packaging        | PyInstaller + Inno Setup                    |
| Tests            | pytest, pytest-cov                          |

---

## Supported gestures

The webcam feed is **mirrored** (selfie view): move your hand right and the cursor
moves right. All thresholds are tunable in Settings; the calibration wizard tunes
the pinch distances for your hand.

| Gesture          | How to perform it                                              | Result                                  |
| ---------------- | ------------------------------------------------------------- | --------------------------------------- |
| **Move**         | Point with the index finger extended (others curled)          | Cursor follows your fingertip           |
| **Left Click**   | Quick thumb + index pinch and release                         | Single left click                       |
| **Double Click** | Two quick thumb + index pinches in succession                 | Double left click (two rapid clicks)    |
| **Right Click**  | Thumb + middle-finger pinch (index finger raised)             | Context/right click                     |
| **Drag & Drop**  | Press and **hold** the thumb + index pinch, move, then release| Left-button drag; release to drop       |
| **Scroll**       | Raise index + middle fingers ("V") and move the hand up/down  | Scroll up / down                        |

Emergency stop (not a gesture): global hotkey `Ctrl+Alt+E`, the **STOP** button,
or the top-left corner trip.

---

## Installation & setup

### Option A — Prebuilt application (no Python required)

1. Run `HandGestureMouse-Setup.exe` (Inno Setup installer). It installs the app, a
   Start Menu shortcut, and an uninstaller.
2. **or** use the portable one-folder build: unzip
   `HandGestureMouse-1.0.0-portable-win64.zip` and run
   `HandGestureMouse.exe` (keep the `_internal` folder next to it).

No Python and no extra downloads are needed — the MediaPipe model ships inside the
package.

> On managed machines an AppLocker/WDAC policy may block unsigned binaries run
> from outside `%ProgramFiles%`. Use the installer, which places files under
> `%ProgramFiles%`.

### Option B — From source

**Prerequisites:** Windows 10/11 (x64), Python 3.10+, and a webcam.

**1. Create a virtual environment and install dependencies**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**2. Hand model**

The MediaPipe model (`hand_landmarker.task`, ~7.5 MB) is included in
`src\handgesturemouse\resources\models\`. If it is missing or you want to
re-fetch and verify it:

```powershell
.\.venv\Scripts\python.exe scripts\download_model.py
```

This downloads `hand_landmarker.task` into
`src\handgesturemouse\resources\models\` and verifies its integrity.

**3. Run**

```powershell
.\.venv\Scripts\python.exe main.py
```

Raise a hand in view and point — mouse control is active on launch.

---

## Build & packaging

### Portable executable (PyInstaller)

The recommended output is a **one-folder** build (faster startup, easier to debug):

```powershell
.\.venv\Scripts\python.exe -m PyInstaller packaging\HandGestureMouse.spec --noconfirm --clean
```

Output:

```
dist\HandGestureMouse\HandGestureMouse.exe
dist\HandGestureMouse\_internal\    (runtime, resources, model, icons)
```

For a **single-file** executable, set `ONE_FILE = True` at the top of
`packaging\HandGestureMouse.spec`.

**One-command build** (venv, deps, model, icon, tests, then PyInstaller):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Pass `-OneFile` for a single-file build or `-SkipTests` to skip tests.

### Installer (Inno Setup)

1. Build the folder distribution first (above).
2. Install [Inno Setup 6](https://jrsoftware.org/isdl.php):

   ```powershell
   winget install --id JRSoftware.InnoSetup -e
   ```

3. Compile the installer (`winget` installs Inno Setup per-user):

   ```powershell
   & "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
   # per-machine install instead:
   # & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
   ```

The installer is written to `packaging\Output\HandGestureMouse-Setup.exe`. It
bundles the whole folder build (executable, `_internal`, model, icons), installs
to `%ProgramFiles%\HandGestureMouse` (or a per-user location when elevation is
declined), creates Start Menu/desktop shortcuts, registers a standard uninstaller,
and requires **no Python** on the target machine.

For distribution, a `release\` folder collects the deliverables:
`HandGestureMouse-Setup.exe`, `HandGestureMouse-1.0.0-portable-win64.zip`,
`README.md`, `RELEASE_NOTES.md`, and `SHA256SUMS.txt`.

---

## Architecture

```
main.py                      # entry point; adds src/ to sys.path and runs the app
src/handgesturemouse/
  app.py                     # Application: wiring, global hotkey, event loop, lifecycle
  config/
    defaults.py              # default settings + validation/coercion helpers
    settings_manager.py      # load/save/atomic-write settings.json, change listeners
  core/
    geometry.py              # landmark math + finger-extension / pinch helpers
    hand_tracker.py          # MediaPipe HandLandmarker wrapper (VIDEO mode + annotate)
    gesture_controller.py    # state machine -> MouseCommand (move/click/drag/scroll)
    coordinate_mapper.py     # normalized landmark coords -> screen pixels
    cursor_smoothing.py      # EMA smoothing + dead zone
    mouse_controller.py      # PyAutoGUI wrapper, fail-safe, release-all safety
    pipeline.py              # background worker thread: capture -> track -> control
    eco.py                   # EcoThrottle + MotionDetector (battery saver)
    calibration.py           # pinch-threshold calibration session (metric based)
    reconnect.py             # camera reconnect backoff state machine
    screens.py               # Win32 multi-monitor enumeration + region resolution
  camera/
    camera_manager.py        # OpenCV camera open/read/release (buffer + timeouts)
  gui/
    theme.py                 # colors, fonts, apply_theme()
    main_window.py           # window shell, navigation, event dispatch, footer credit
    dashboard.py             # live controls/status
    camera_view.py           # live annotated preview (reconnect/feedback badges)
    settings_view.py         # tunable parameters + calibration launcher
    calibration_dialog.py    # two-step calibration wizard (modal)
    instructions_view.py     # usage help
    tray.py                  # optional system-tray icon (pystray wrapper)
  utils/
    logger.py                # console + rotating-file logging
    paths.py                 # resource & user-data paths (source and frozen)
    feedback.py              # non-blocking audio feedback (winsound)
    autostart.py             # Windows Run-key auto-start management
  resources/
    models/hand_landmarker.task   # MediaPipe model (downloaded by scripts/)
    icons/app.ico, app.png
tests/                       # pytest suite
scripts/
  download_model.py          # fetch + verify the MediaPipe model
  make_icon.py               # generate app.ico / app.png
  build_windows.ps1          # one-command Windows build
packaging/
  HandGestureMouse.spec      # PyInstaller spec (one-dir or one-file)
  installer.iss              # Inno Setup installer script
```

### Runtime model

- The **Tk GUI runs on the main thread**.
- A single **`PipelineWorker` background thread** does the heavy lifting:
  camera capture → MediaPipe inference → gesture classification → mouse control.
- The worker and GUI communicate through a bounded `queue.Queue` of events
  (`status`, `frame`, `state`, `error`, `emergency`, plus `feedback`,
  `camera_state`, and `calibration`/`calibration_result`); the GUI drains the
  queue with a periodic `after()` callback. This keeps the UI responsive and
  avoids Tkinter thread-safety issues.
- The camera runs while the app is open; **Start / Pause / Stop** control only
  whether the mouse is being driven.
- A lightweight **system-tray icon** runs on its own thread for background mode.

---

## Settings reference

Settings live at `%APPDATA%\HandGestureMouse\settings.json` and are editable from
the **Settings** tab.

| Key                       | Default      | Meaning                                             |
| ------------------------- | ------------ | --------------------------------------------------- |
| `pinch_threshold`         | `0.30`       | Distance below which a pinch starts                 |
| `pinch_hold_threshold`    | `0.36`       | Distance below which a pinch is considered held     |
| `click_hold_time`         | `0.35` s     | Hold time that turns a pinch into a drag            |
| `gesture_cooldown`        | `0.35` s     | Minimum time between repeated gestures              |
| `cursor_sensitivity`      | `1.0`        | Cursor travel multiplier                            |
| `cursor_smoothing`        | `0.55`       | EMA smoothing factor (higher = smoother/slower)     |
| `scroll_sensitivity`      | `30.0`       | Scroll speed multiplier                             |
| `max_fps`                 | `30`         | Maximum processing frame rate                       |
| `emergency_hotkey`        | `ctrl+alt+e` | Global stop hotkey (set to `esc` if you prefer)     |
| `mirror_input`            | `true`       | Selfie-mirror the camera                            |
| `num_hands`               | `1`          | Number of hands to track                            |
| `auto_open_camera`        | `true`       | Open the camera on startup                          |
| `enable_tray`             | `true`       | Show a system-tray icon for background operation    |
| `minimize_to_tray`        | `true`       | Minimizing hides the window to the tray             |
| `close_to_tray`           | `true`       | Closing the window hides to the tray instead of quit|
| `enable_audio_feedback`   | `true`       | Play subtle sound cues for gestures                 |
| `auto_start_windows`      | `false`      | Start automatically when you sign in to Windows     |
| `start_control_on_launch` | `true`       | Begin controlling the mouse as soon as the app opens|
| `show_tray_notifications` | `true`       | Show a toast when the window is hidden to the tray  |
| `eco_mode`                | `true`       | Throttle tracking when no hand is present           |
| `eco_idle_seconds`        | `45`         | Idle seconds before eco throttling engages          |
| `eco_fps`                 | `5`          | Tracking rate while eco-throttled                   |
| `target_display`          | `primary`    | Controlled monitor: `primary`, `secondary`, `span`  |

---

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite runs headless (no camera or display required) and covers gesture
classification, coordinate mapping, settings persistence/validation, mouse-safety
behaviour, camera lifecycle, hand-tracker error handling, hotkey parsing,
system-tray lifecycle, resource/user-data paths, packaging/installer consistency,
and the feature modules (auto-start registry, eco FPS throttle, reconnect
backoff, multi-monitor regions, calibration, audio feedback, tray notifications,
camera buffer/reuse, frame-loss tolerance, on-frame gesture badge).

With coverage:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=handgesturemouse
```

---

## Offline & privacy

- All inference happens on-device via MediaPipe/OpenCV.
- No telemetry, analytics, accounts, or network calls at runtime.
- The only network access is the one-time `scripts\download_model.py` step (and
  dependency installation). You may commit the model file yourself and skip it.
- Camera frames and mouse usage are never stored or transmitted.

---

## Troubleshooting

| Symptom                                   | Fix                                                                 |
| ----------------------------------------- | ------------------------------------------------------------------- |
| "MediaPipe Tasks is not installed"        | Install requirements and run `scripts\download_model.py`.            |
| Camera does not open                      | Close other apps using the camera; check Windows camera permissions. |
| Cursor barely moves / too jumpy           | Adjust `cursor_sensitivity` and `cursor_smoothing` in Settings.      |
| Accidental clicks                         | Increase `pinch_threshold` / `gesture_cooldown`.                     |
| Need to stop immediately                  | Press `Ctrl+Alt+E`, click **STOP**, or move the cursor to the top-left corner. |
| Executable won't run (enterprise machine) | An AppLocker/WDAC policy may block unsigned binaries outside `%ProgramFiles%`. Install via the Inno Setup installer. |
| No tray icon appears                      | The tray may be disabled by policy. Disable `enable_tray` and use **Exit Application** to quit. |
| Closing the window hides the app          | Intended (`close_to_tray`). Use **Exit Application** or set `close_to_tray` to `false`. |
| "Camera Disconnected - Reconnecting..."   | The camera was unplugged or is in use. Buttons release and the app retries every 2 s (5 attempts). |
| No sound cues                             | Enable **Audio feedback** in Settings; check the Windows sound volume. |
| Auto-start does not stick                 | Registry access may be restricted by policy; the app reports this without crashing. |
| Mouse does not move on launch             | Ensure `start_control_on_launch` is on, or press **Start Control**.   |
| Camera stutters or briefly drops          | Single-frame buffer + delayed-frame tolerance help; close other camera apps or lower `max_fps`. |
| Cursor jumps between monitors             | Set **Monitor to control** to `primary` (or a specific display) instead of `span`. |

---

## Limitations

- Windows-only (mouse control and packaging target Windows).
- A single hand is tracked by default.
- Lighting, camera quality, and background clutter affect accuracy.
- Gesture thresholds may need tuning per user/camera; the **calibration wizard**
  helps, but you can still fine-tune the pinch sliders manually.
- In eco mode the expensive inference is throttled to `eco_fps` while a
  lightweight motion check keeps wake-up latency under ~40 ms.
