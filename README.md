# AutoTyper

A Windows desktop application that automatically types text into any focused window — built with Python and tkinter.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)
[![Download](https://img.shields.io/github/downloads/u-pawan/auto_typer/total)](https://github.com/u-pawan/auto_typer/releases/latest)
[![Release](https://img.shields.io/github/v/release/u-pawan/auto_typer)](https://github.com/u-pawan/auto_typer/releases/latest)

---

## Features

### Typing Engine
- **Full Unicode support** — types any character including emoji and non-Latin scripts via Windows SendInput API
- **Character-by-character typing** — configurable speed from 0 to 500 ms per keystroke
- **Gaussian jitter** — natural ±N ms variation per keystroke (more human than uniform random)
- **Word-by-word mode** — separate inter-word delay for even more realistic output
- **Smart retry** — automatically retries failed keystrokes up to 2 times
- **Paste mode** — instant clipboard injection via Ctrl+V for large text blocks
- **Repeat mode** — type N times or loop infinitely (∞)
- **Start delay countdown** — time to switch to the target window before typing begins

### Special Key Tokens & Variables
- Inline special keys: `{ENTER}` `{TAB}` `{BACKSPACE}` `{ESC}` `{F1}`–`{F12}` and more
- Runtime variables that expand before typing: `{DATE}` `{TIME}` `{DATETIME}` `{CLIPBOARD}` `{COUNTER}` `{RANDOM:N}`

### Automation
- **Multi-step scripts** — chain multiple text blocks with per-step delays and speed settings
- **Macro recorder** — record real keystrokes (with timing) and replay them exactly
- **Scheduled typing** — set a clock time (HH:MM) to start automatically
- **Global hotkey** (default F6) — toggle start/stop from any window, even when AutoTyper is minimised

### Profile Management
- Save, load, export, and import named typing configurations
- **Drag-to-reorder** profiles in the list
- **Per-profile hotkeys** — assign a unique trigger key to each profile
- **Undo last load** — quickly revert to the previous profile

### UI & UX
- **Dark mode** — full light/dark theme switching across all widgets
- **Live character highlight** — the current character is highlighted in the text area as it is typed
- **Speed presets** — Slow / Human / Fast / Instant one-click buttons
- **Font size control** — resize the text area font independently
- **Keyboard shortcut cheat sheet** — press `?` to see all hotkeys and tokens
- Clean tabbed interface: Type · Profiles · Scripts · Macros · Settings

### Security
- **Profile encryption** — Fernet symmetric encryption with PBKDF2 key derivation
- **Settings integrity check** — SHA-256 hash sidecar detects tampering
- **Auto-lock** — clear sensitive data from memory after a configurable idle timeout
- **Failsafe** — moving the mouse to the top-left screen corner aborts typing immediately
- No keystrokes are logged or transmitted — all processing is local and offline

### Distribution
- **Auto-updater** — checks GitHub releases on startup and prompts when a new version is available
- **Portable mode** — place `portable.flag` next to the exe to store data beside it instead of `%APPDATA%`
- **Inno Setup installer script** included (`installer/setup.iss`) for a proper Windows installer

---

## Screenshots

> Type tab · Profiles tab · Scripts tab · Macros tab · Settings tab

_(Add screenshots here after first run)_

---

## Installation

### Option A — Run from source

**Prerequisites:** Windows 10/11 · Python 3.11+ ([python.org/downloads](https://python.org/downloads)) — check **"Add Python to PATH"** during install.

```bash
git clone https://github.com/u-pawan/auto_typer.git
cd auto_typer
pip install -r requirements.txt
python auto_typer.py
```

### Option B — Download the .exe

Go to [Releases](https://github.com/u-pawan/auto_typer/releases/latest) and download `AutoTyper.exe`. No Python required — double-click and run.

### Option C — Build it yourself

```bash
build.bat
```

Produces `dist\AutoTyper.exe` via PyInstaller. The build script installs all dependencies automatically.

---

## Quick Start

1. Launch AutoTyper
2. Type (or paste) your text in the **Text to type** box
3. Choose a speed preset or fine-tune the sliders
4. Click **▶ Start** (or press **F6**)
5. Switch to the target window during the countdown
6. Typing begins — press **F6** again to stop at any time

---

## Special Key Tokens

Insert these anywhere in your text field:

| Token | Action |
|-------|--------|
| `{ENTER}` | Press Enter |
| `{TAB}` | Press Tab |
| `{BACKSPACE}` | Press Backspace |
| `{DELETE}` | Press Delete |
| `{ESC}` | Press Escape |
| `{SPACE}` | Press Space |
| `{F1}`–`{F12}` | Function keys |
| `{UP}` `{DOWN}` `{LEFT}` `{RIGHT}` | Arrow keys |
| `{HOME}` `{END}` `{PGUP}` `{PGDN}` | Navigation keys |

**Example:** `Hello{ENTER}World{TAB}!`
→ types `Hello`, presses Enter, types `World`, presses Tab, types `!`

---

## Runtime Variables

These expand to live values right before typing starts:

| Variable | Expands to |
|----------|-----------|
| `{DATE}` | Today's date — `2026-05-11` |
| `{TIME}` | Current time — `14:32:07` |
| `{DATETIME}` | Date and time — `2026-05-11 14:32:07` |
| `{CLIPBOARD}` | Current clipboard contents |
| `{COUNTER}` | Auto-incrementing integer (resets each run) |
| `{RANDOM:N}` | Random integer from 1 to N |

**Example:** `Order #{COUNTER} placed at {TIME} on {DATE}`

---

## Multi-Step Scripts

The **Scripts** tab lets you build a sequence of typing steps:

1. Add steps with their text, gap before the step (seconds), and per-step speed
2. Use `{PAUSE:N}` as the text to insert a pure N-second pause
3. Reorder steps with Move Up / Move Down
4. Save and load scripts as `.json` files
5. Click **▶ Run Script** to execute all steps in order

---

## Macro Recorder

The **Macros** tab records real keystrokes with their exact timing:

1. Click **⏺ Record** — everything you type is captured
2. Press the configured stop key (default `F9`) to finish
3. Select the macro and click **▶ Play** to replay it
4. Save macros as `.json` files; load them back later

> Requires `pynput` to be installed for recording. Playback works independently.

---

## Scheduled Typing

On the **Type** tab, check **Schedule at:** and enter a time (HH:MM). AutoTyper will wait until that time today, then start the typing run automatically.

---

## Profiles

- **Save** — click **💾 Save Profile** on the Type tab to store the current text and settings
- **Load** — double-click a profile or select it and click **▶ Load**
- **Undo** — click **↩ Undo Load** to revert to the previous profile
- **Reorder** — drag profiles up and down in the list
- **Per-profile hotkey** — assign a key combo (e.g. `ctrl+shift+1`) to trigger a profile directly
- **Export / Import** — share profiles as standalone `.json` files

---

## Security

### Encryption
Enable **Encrypt profiles with password** in Settings and set a master password. Profiles are encrypted with [Fernet](https://cryptography.io/en/latest/fernet/) (AES-128-CBC + HMAC-SHA256) derived via PBKDF2 (390,000 iterations).

### Integrity check
The settings file is hashed with SHA-256 on every save. On load, the hash is verified — if it does not match, settings are reset to defaults to prevent acting on tampered values.

### Auto-lock
Configure an idle timeout in Settings. After that many minutes without typing activity, AutoTyper locks itself and minimises. Re-open to continue.

### Failsafe
Move the mouse to the **top-left corner of the screen** at any time to immediately abort typing (`pyautogui.FAILSAFE = True`). This cannot be disabled.

---

## Portable Mode

To store all data beside the executable instead of in `%APPDATA%\AutoTyper\`:

1. Create an empty file named `portable.flag` in the same folder as `AutoTyper.exe`
2. Data will be stored in `AutoTyper_data\` next to the exe

This makes the entire app self-contained for USB or shared-folder use.

---

## Project Structure

```
auto_typer/
├── auto_typer.py            # Main entry point — wires all components
├── engine/
│   ├── send_input.py        # Windows SendInput for full Unicode typing
│   ├── typer.py             # Core typing loop (daemon thread)
│   ├── hotkey.py            # Global hotkey manager
│   ├── special_keys.py      # {TOKEN} and escape-sequence parsing
│   ├── variables.py         # Runtime variable expansion
│   ├── scheduler.py         # Scheduled typing (fire at HH:MM)
│   ├── macro.py             # Keystroke macro recorder + player
│   └── updater.py           # GitHub auto-update checker
├── ui/
│   ├── theme.py             # Dark / light theme manager
│   ├── main_tab.py          # Type tab
│   ├── profiles_tab.py      # Profiles tab
│   ├── scripts_tab.py       # Multi-step scripts tab
│   ├── macro_tab.py         # Macro recorder tab
│   ├── settings_tab.py      # Settings tab
│   └── shortcuts_dialog.py  # Keyboard shortcut cheat sheet
├── storage/
│   └── store.py             # Encrypted JSON persistence + integrity check
├── installer/
│   └── setup.iss            # Inno Setup installer script
├── requirements.txt
└── build.bat                # One-click PyInstaller build
```

**Data directory:** `%APPDATA%\AutoTyper\` (or beside the exe in portable mode)

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pyautogui` | Failsafe + special key injection |
| `keyboard` | Global hotkey listener (works when app is unfocused) |
| `pyperclip` | Clipboard read/write for paste mode and `{CLIPBOARD}` variable |
| `pynput` | Macro recording (keyboard + mouse events) |
| `pystray` | System tray icon |
| `Pillow` | Tray icon image generation |
| `cryptography` | Profile encryption (Fernet + PBKDF2) |

All installed automatically by `pip install -r requirements.txt` or `build.bat`.

---

## Building an Installer

1. Build the exe: `build.bat`
2. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
3. Open `installer\setup.iss` in Inno Setup Compiler
4. Press **F9** to build
5. Output: `installer\AutoTyper_Setup.exe`

The installer adds a Start Menu shortcut, an optional desktop icon, an optional startup entry, and a proper uninstaller.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a pull request
