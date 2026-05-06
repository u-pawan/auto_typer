# auto_typer.py — AutoTyper v1.0 main entry point.
#
# Builds the root Tk window, instantiates all tabs and engine components,
# wires their callbacks together, and starts the Tk event loop.
#
# All cross-thread UI updates go through root.after(0, ...) — tkinter is
# not thread-safe and must only be touched from the main thread.

import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# ── Dependency checks ─────────────────────────────────────────────────
def _check_deps() -> None:
    missing = []
    try:
        import pyautogui  # noqa: F401
    except ImportError:
        missing.append("pyautogui")
    try:
        import pyperclip  # noqa: F401
    except ImportError:
        missing.append("pyperclip")
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing dependencies",
            "The following packages are required but not installed:\n\n"
            + "\n".join(f"  pip install {p}" for p in missing)
            + "\n\nInstall them, then restart AutoTyper.",
        )
        root.destroy()
        sys.exit(1)


_check_deps()

# ── Internal imports (after dep check) ───────────────────────────────
from engine.typer import TyperEngine, TypingOptions
from engine.hotkey import HotkeyManager
from storage.store import ProfileStore, SettingsStore
from ui.main_tab import MainTab
from ui.profiles_tab import ProfilesTab
from ui.settings_tab import SettingsTab

try:
    import winsound as _winsound
    _WINSOUND_OK = True
except ImportError:
    _WINSOUND_OK = False

try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_OK = True
except ImportError:
    _TRAY_OK = False


# ──────────────────────────────────────────────────────────────────────
# Tray icon helpers
# ──────────────────────────────────────────────────────────────────────

def _make_tray_icon_image() -> "Image.Image":
    """Create a simple 64×64 icon for the system tray."""
    img = Image.new("RGB", (64, 64), color="#0d6efd")
    draw = ImageDraw.Draw(img)
    draw.text((18, 18), "AT", fill="white")
    return img


# ──────────────────────────────────────────────────────────────────────
# Main application class
# ──────────────────────────────────────────────────────────────────────

class AutoTyperApp:
    """Top-level controller: owns the window, engine, hotkey, and stores."""

    _WIN_W = 520
    _WIN_H = 640
    _WIN_MIN_W = 520
    _WIN_MIN_H = 580

    def __init__(self) -> None:
        self._settings = SettingsStore()
        self._profiles = ProfileStore()
        self._engine = TyperEngine(None)  # root set below
        self._hotkey = HotkeyManager()
        self._tray: object = None
        self._is_minimized_to_tray = False

        self._root = tk.Tk()
        self._engine._root = self._root  # inject after creation

        self._setup_window()
        self._build_ui()
        self._register_hotkey()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self._root.title("AutoTyper v1.0")
        self._root.resizable(True, True)
        self._root.minsize(self._WIN_MIN_W, self._WIN_MIN_H)

        # Centre on screen
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - self._WIN_W) // 2
        y = (sh - self._WIN_H) // 2
        self._root.geometry(f"{self._WIN_W}x{self._WIN_H}+{x}+{y}")

        # Apply ttk theme
        style = ttk.Style()
        for t in ("vista", "winnative", "clam", "default"):
            if t in style.theme_names():
                style.theme_use(t)
                break

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=4)

        self._main_tab = MainTab(
            self._notebook,
            on_start=self._start_typing,
            on_stop=self._stop_typing,
            on_save_profile=self._save_profile_dialog,
        )
        self._profiles_tab = ProfilesTab(
            self._notebook,
            on_load=self._load_profile,
            profile_store=self._profiles,
        )
        self._settings_tab = SettingsTab(
            self._notebook,
            settings_store=self._settings,
            hotkey_manager=self._hotkey,
            on_hotkey_changed=self._on_hotkey_changed,
        )

        self._notebook.add(self._main_tab,     text="  Type  ")
        self._notebook.add(self._profiles_tab, text="  Profiles  ")
        self._notebook.add(self._settings_tab, text="  Settings  ")

    # ------------------------------------------------------------------
    # Typing control
    # ------------------------------------------------------------------

    def _start_typing(self) -> None:
        if self._engine.is_running():
            return
        text = self._main_tab.get_text()
        if not text.strip():
            messagebox.showwarning("Empty text", "Please enter some text to type.")
            return

        opts = TypingOptions(
            delay_ms=self._main_tab.get_delay_ms(),
            jitter_ms=self._main_tab.get_jitter_ms(),
            start_delay_s=self._main_tab.get_start_delay_s(),
            repeat_count=self._main_tab.get_repeat_count(),
            paste_mode=self._main_tab.get_paste_mode(),
        )

        if self._settings_tab.get_minimize_on_start():
            self._minimize_to_tray()

        self._beep(start=True)
        self._engine.start(
            text=text,
            options=opts,
            on_countdown=self._on_countdown,
            on_start=self._on_typing_start,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_stop=self._on_stop,
            on_error=self._on_error,
        )

    def _stop_typing(self) -> None:
        self._engine.stop()

    def _toggle_typing(self) -> None:
        """Called by the global hotkey — toggles start/stop."""
        if self._engine.is_running():
            self._stop_typing()
        else:
            self._root.after(0, self._start_typing)

    # ------------------------------------------------------------------
    # Engine callbacks  (always called via root.after, so on UI thread)
    # ------------------------------------------------------------------

    def _on_countdown(self, remaining: int) -> None:
        self._main_tab.set_countdown(remaining)

    def _on_typing_start(self, total_chars: int, repeat_count: int) -> None:
        self._main_tab.set_total_chars(total_chars, repeat_count)
        self._main_tab.set_typing(1, repeat_count)

    def _on_progress(self, chars_done: int, pass_num: int) -> None:
        total = self._main_tab._total_chars
        repeat = self._main_tab._repeat_count
        self._main_tab.set_progress(chars_done, total, pass_num, repeat)

    def _on_done(self) -> None:
        self._main_tab.set_done()
        self._beep(start=False)
        if self._is_minimized_to_tray:
            self._restore_from_tray()

    def _on_stop(self) -> None:
        self._main_tab.set_stopped()
        self._beep(start=False)
        if self._is_minimized_to_tray:
            self._restore_from_tray()

    def _on_error(self, message: str) -> None:
        self._main_tab.set_error(message)
        if self._is_minimized_to_tray:
            self._restore_from_tray()
        messagebox.showerror("AutoTyper error", message)

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def _save_profile_dialog(self) -> None:
        text = self._main_tab.get_text()
        if not text.strip():
            messagebox.showwarning("Empty text", "Enter some text before saving a profile.")
            return
        name = simpledialog.askstring(
            "Save Profile", "Profile name:", parent=self._root
        )
        if not name or not name.strip():
            return
        self._profiles.add(
            name=name.strip(),
            text=text,
            delay_ms=self._main_tab.get_delay_ms(),
            jitter_ms=self._main_tab.get_jitter_ms(),
            start_delay_s=self._main_tab.get_start_delay_s(),
            repeat_count=self._main_tab.get_repeat_count(),
            paste_mode=self._main_tab.get_paste_mode(),
        )
        self._profiles_tab.refresh()
        messagebox.showinfo("Saved", f'Profile "{name.strip()}" saved.')

    def _load_profile(self, profile: dict) -> None:
        self._main_tab.load_profile(profile)
        self._notebook.select(self._main_tab)

    # ------------------------------------------------------------------
    # Hotkey
    # ------------------------------------------------------------------

    def _register_hotkey(self) -> None:
        key = self._settings.get("hotkey", "f6")
        if self._hotkey.available:
            self._hotkey.register(key, self._toggle_typing)

    def _on_hotkey_changed(self, new_key: str) -> None:
        if self._hotkey.available:
            self._hotkey.unregister()
            self._hotkey.register(new_key, self._toggle_typing)

    # ------------------------------------------------------------------
    # System tray
    # ------------------------------------------------------------------

    def _minimize_to_tray(self) -> None:
        if not _TRAY_OK:
            self._root.iconify()
            return
        self._root.withdraw()
        self._is_minimized_to_tray = True
        icon_img = _make_tray_icon_image()
        self._tray = pystray.Icon(
            "AutoTyper",
            icon_img,
            "AutoTyper",
            menu=pystray.Menu(
                pystray.MenuItem("Show", self._restore_from_tray),
                pystray.MenuItem("Stop Typing", lambda: self._root.after(0, self._stop_typing)),
                pystray.MenuItem("Quit", lambda: self._root.after(0, self._on_close)),
            ),
        )
        import threading
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _restore_from_tray(self) -> None:
        if self._tray:
            self._tray.stop()
            self._tray = None
        self._is_minimized_to_tray = False
        self._root.deiconify()
        self._root.lift()

    # ------------------------------------------------------------------
    # Sound
    # ------------------------------------------------------------------

    def _beep(self, start: bool) -> None:
        if not self._settings_tab.get_play_sounds():
            return
        if not _WINSOUND_OK:
            return
        freq, dur = (1000, 100) if start else (600, 100)
        try:
            _winsound.Beep(freq, dur)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._engine.stop()
        self._hotkey.unregister()
        if self._tray:
            self._tray.stop()
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AutoTyperApp()
    app.run()
