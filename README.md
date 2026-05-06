# AutoTyper

A Windows desktop application that automatically types text into any focused window — built with Python and tkinter.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Character-by-character typing** with configurable speed (10–500 ms/key)
- **Human-like jitter** — random ±N ms variation per keystroke
- **Special key tokens** — write `{ENTER}`, `{TAB}`, `{BACKSPACE}`, `{F5}`, etc. inline
- **Repeat mode** — type N times or loop infinitely (∞)
- **Paste mode** — instant clipboard injection via Ctrl+V
- **Global hotkey** (default F6) — toggle start/stop from any window
- **Start delay countdown** — time to switch to the target window before typing begins
- **Profile manager** — save, load, export, and import typing configurations
- **System tray support** — minimize while typing, restore via tray icon
- **Startup option** — register to launch at Windows login
- **Failsafe** — move mouse to top-left corner to abort immediately

---

## Screenshots

> Type tab · Profiles tab · Settings tab

_(Add screenshots here after first run)_

---

## Installation

### Prerequisites

- Windows 10 / 11
- Python 3.11 or newer — [python.org/downloads](https://python.org/downloads)
  - During install, check **"Add Python to PATH"**

### Install dependencies

```bash
cd auto_typer
pip install -r requirements.txt
```

### Run from source

```bash
python auto_typer.py
```

### Build a standalone .exe

```bash
build.bat
```

The executable is created at `dist\AutoTyper.exe`. No Python installation required on the target machine.

---

## Project Structure

```
auto_typer/
├── auto_typer.py          # Main entry point and app window
├── engine/
│   ├── typer.py           # Core typing loop (daemon thread)
│   ├── hotkey.py          # Global hotkey manager
│   └── special_keys.py    # {TOKEN} and escape-sequence parsing
├── ui/
│   ├── main_tab.py        # Type tab — text input, sliders, controls
│   ├── profiles_tab.py    # Profiles tab — save/load/export/import
│   └── settings_tab.py    # Settings tab — hotkey, defaults, OS options
├── storage/
│   └── store.py           # JSON persistence (profiles + settings)
├── requirements.txt
└── build.bat              # One-click PyInstaller build
```

Data files are stored in `%APPDATA%\AutoTyper\` (created automatically on first run).

---

## Usage

### Basic workflow

1. Launch AutoTyper
2. Type (or paste) your text in the **Text to type** box
3. Adjust speed, jitter, start delay, and repeat count
4. Click **▶ Start** (or press **F6**)
5. Switch to the target window during the countdown
6. Typing begins automatically — press **F6** again to stop

### Special key tokens

Insert these anywhere in your text:

| Token | Action |
|-------|--------|
| `{ENTER}` | Press Enter |
| `{TAB}` | Press Tab |
| `{BACKSPACE}` | Press Backspace |
| `{DELETE}` | Press Delete |
| `{ESC}` | Press Escape |
| `{F1}`–`{F12}` | Function keys |
| `{UP}` `{DOWN}` `{LEFT}` `{RIGHT}` | Arrow keys |
| `{HOME}` `{END}` `{PGUP}` `{PGDN}` | Navigation keys |

Example: `Hello{ENTER}World{TAB}!` types "Hello", presses Enter, types "World", presses Tab, types "!".

### Profiles

- Click **Save as Profile** on the Type tab to store current settings
- Switch to the **Profiles** tab to load, delete, export, or import profiles
- Double-click a profile to load it instantly

### Hotkey

Default hotkey is **F6**. To change it:
1. Go to the **Settings** tab
2. Click **Record new key**
3. Press the desired key
4. Click **Save Settings**

### Paste mode

Check **Paste mode** to skip character-by-character typing and instead write the full text to the clipboard, then send `Ctrl+V`. Useful for large blocks of text or when speed matters more than realism.

---

## Safety

- **Failsafe active** — move the mouse to the **top-left screen corner** at any time to abort typing immediately (`pyautogui.FAILSAFE = True`)
- The stop hotkey (F6) and Stop button interrupt typing between individual keystrokes (~50 ms response)
- No keystrokes are logged or transmitted — all processing is local

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pyautogui` | Keystroke injection via Windows SendInput |
| `keyboard` | Global hotkey listener (works when app is not focused) |
| `pyperclip` | Clipboard read/write for paste mode |
| `pystray` | System tray icon (optional) |
| `Pillow` | Tray icon image generation |

---

## Building from source

```bash
pip install pyinstaller
build.bat
```

PyInstaller bundles the app into a single `dist\AutoTyper.exe`. The build script handles all `--hidden-import` flags for the libraries above.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.
