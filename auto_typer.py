# auto_typer.py — AutoTyper v2.0 main entry point.
#
# Wires together: ThemeManager, TyperEngine, HotkeyManager, TypingScheduler,
# all UI tabs, ProfileStore, SettingsStore, ScriptStore, and the auto-updater.
# All cross-thread UI updates go through root.after(0, ...).

import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

# ── Dependency check ──────────────────────────────────────────────────
def _check_deps() -> None:
    missing = []
    for pkg in ("pyautogui", "pyperclip"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing dependencies",
            "Required packages not installed:\n\n"
            + "\n".join(f"  pip install {p}" for p in missing)
            + "\n\nInstall them and restart AutoTyper.",
        )
        root.destroy()
        sys.exit(1)

_check_deps()

# ── Internal imports ──────────────────────────────────────────────────
from engine.typer    import TyperEngine, TypingOptions
from engine.hotkey   import HotkeyManager
from engine.scheduler import TypingScheduler
from engine.updater  import check_for_update, CURRENT_VERSION
from storage.store   import ProfileStore, SettingsStore, ScriptStore
from ui.theme        import ThemeManager
from ui.main_tab     import MainTab
from ui.profiles_tab import ProfilesTab
from ui.settings_tab import SettingsTab
from ui.scripts_tab  import ScriptsTab
from ui.macro_tab    import MacroTab
from ui.shortcuts_dialog import show_shortcuts

try:
    import winsound as _ws
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
# Tray icon
# ──────────────────────────────────────────────────────────────────────

def _make_tray_image() -> "Image.Image":
    img = Image.new("RGB", (64, 64), "#0d6efd")
    ImageDraw.Draw(img).text((14, 16), "AT", fill="white")
    return img


# ──────────────────────────────────────────────────────────────────────
# Auto-lock
# ──────────────────────────────────────────────────────────────────────

class _AutoLocker:
    """Fires a callback after N minutes of no typing activity."""

    def __init__(self, on_lock: object) -> None:
        self._on_lock = on_lock
        self._minutes = 5
        self._enabled = False
        self._last_activity = time.monotonic()
        self._thread: threading.Thread | None = None

    def configure(self, enabled: bool, minutes: int) -> None:
        self._enabled = enabled
        self._minutes = minutes
        if enabled and (self._thread is None or not self._thread.is_alive()):
            self._thread = threading.Thread(target=self._watch, daemon=True)
            self._thread.start()

    def reset(self) -> None:
        self._last_activity = time.monotonic()

    def _watch(self) -> None:
        while self._enabled:
            time.sleep(30)
            idle = time.monotonic() - self._last_activity
            if self._enabled and idle >= self._minutes * 60:
                self._on_lock()  # type: ignore[call-arg]
                self._last_activity = time.monotonic()


# ──────────────────────────────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────────────────────────────

class AutoTyperApp:
    _WIN_W, _WIN_H = 560, 680
    _MIN_W, _MIN_H = 520, 580

    def __init__(self) -> None:
        self._settings  = SettingsStore()
        self._profiles  = ProfileStore()
        self._scripts   = ScriptStore()
        self._engine    = TyperEngine(None)   # root assigned below
        self._hotkey    = HotkeyManager()
        self._scheduler = TypingScheduler()
        self._tray: object = None
        self._tray_hidden = False
        self._locker    = _AutoLocker(on_lock=self._on_auto_lock)

        # Build root window
        self._root = tk.Tk()
        self._engine._root = self._root

        self._theme = ThemeManager(self._root)

        self._setup_window()
        self._build_ui()
        self._register_hotkey()
        self._configure_auto_lock()
        self._check_updates()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Apply saved theme
        if self._settings.get("dark_mode", False):
            self._theme.apply("dark")

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self._root.title(f"AutoTyper v{CURRENT_VERSION}")
        self._root.resizable(True, True)
        self._root.minsize(self._MIN_W, self._MIN_H)
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - self._WIN_W) // 2
        y = (sh - self._WIN_H) // 2
        self._root.geometry(f"{self._WIN_W}x{self._WIN_H}+{x}+{y}")

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        nb = ttk.Notebook(self._root)
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        self._main_tab = MainTab(
            nb,
            on_start=self._start_typing,
            on_stop=self._stop_typing,
            on_save_profile=self._save_profile_dialog,
            on_show_shortcuts=lambda: show_shortcuts(self._root),
            theme=self._theme,
        )
        self._profiles_tab = ProfilesTab(
            nb,
            on_load=self._load_profile,
            profile_store=self._profiles,
            theme=self._theme,
        )
        self._settings_tab = SettingsTab(
            nb,
            settings_store=self._settings,
            hotkey_manager=self._hotkey,
            theme=self._theme,
            on_hotkey_changed=self._on_hotkey_changed,
            on_theme_changed=self._theme.apply,
            on_encryption_changed=self._on_encryption_changed,
        )
        self._scripts_tab = ScriptsTab(
            nb,
            on_run_script=self._run_script,
            on_stop=self._stop_typing,
            script_store=self._scripts,
            theme=self._theme,
        )
        self._macro_tab = MacroTab(nb, self._root, self._theme)

        nb.add(self._main_tab,     text="  Type  ")
        nb.add(self._profiles_tab, text="  Profiles  ")
        nb.add(self._scripts_tab,  text="  Scripts  ")
        nb.add(self._macro_tab,    text="  Macros  ")
        nb.add(self._settings_tab, text="  Settings  ")

    # ------------------------------------------------------------------
    # Typing control
    # ------------------------------------------------------------------

    def _start_typing(self) -> None:
        if self._engine.is_running():
            return
        text = self._main_tab.get_text()
        if not text.strip():
            messagebox.showwarning("Empty text", "Please enter some text first.")
            return

        opts = TypingOptions(
            delay_ms=self._main_tab.get_delay_ms(),
            jitter_ms=self._main_tab.get_jitter_ms(),
            start_delay_s=self._main_tab.get_start_delay_s(),
            repeat_count=self._main_tab.get_repeat_count(),
            paste_mode=self._main_tab.get_paste_mode(),
            word_by_word=self._main_tab.get_word_by_word(),
            word_delay_ms=self._main_tab.get_word_delay_ms(),
            expand_variables=self._main_tab.get_expand_variables(),
        )

        # Scheduled mode?
        schedule_time = self._main_tab.get_schedule()
        if schedule_time:
            self._schedule_typing(text, opts, schedule_time)
            return

        if self._settings_tab.get_minimize_on_start():
            self._minimize_to_tray()

        self._locker.reset()
        self._beep(start=True)
        self._engine.start(
            text=text, options=opts,
            on_countdown=self._on_countdown,
            on_start=self._on_typing_start,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_stop=self._on_stop,
            on_error=self._on_error,
        )

    def _stop_typing(self) -> None:
        self._engine.stop()
        self._scheduler.cancel()

    def _toggle_typing(self) -> None:
        if self._engine.is_running():
            self._stop_typing()
        else:
            self._root.after(0, self._start_typing)

    # ------------------------------------------------------------------
    # Scheduled typing
    # ------------------------------------------------------------------

    def _schedule_typing(self, text: str, opts: TypingOptions, at: str) -> None:
        now = datetime.now()
        try:
            h, m = map(int, at.split(":"))
        except ValueError:
            messagebox.showerror("Invalid time", f"Cannot parse time: {at}")
            return
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            messagebox.showerror("Invalid time", "Scheduled time is in the past.")
            return
        self._main_tab.set_scheduled(at)

        def _fire() -> None:
            self._root.after(0, self._engine.start,
                             text, opts,
                             self._on_countdown,
                             self._on_typing_start,
                             self._on_progress,
                             self._on_done,
                             self._on_stop,
                             self._on_error)

        self._scheduler.schedule(target, on_trigger=_fire,
                                 on_cancelled=lambda: self._root.after(
                                     0, self._main_tab.set_idle))

    # ------------------------------------------------------------------
    # Multi-step script runner
    # ------------------------------------------------------------------

    def _run_script(self, steps: list[dict]) -> None:
        """Run steps sequentially in a daemon thread."""
        def _worker() -> None:
            import time as _t
            for i, step in enumerate(steps):
                if self._engine.is_running():
                    break
                gap = step.get("gap_s", 1.0)
                _t.sleep(gap)
                text = step.get("text", "")
                # Handle pure pause token
                import re
                m = re.fullmatch(r"\{PAUSE:([0-9.]+)\}", text.strip())
                if m:
                    _t.sleep(float(m.group(1)))
                    continue
                delay = step.get("delay_ms", 80)
                opts = TypingOptions(
                    delay_ms=delay, jitter_ms=15,
                    start_delay_s=0, repeat_count=1,
                    expand_variables=True,
                )
                done_ev = threading.Event()
                self._engine.start(
                    text=text, options=opts,
                    on_countdown=lambda _r: None,
                    on_start=lambda _tc, _rc: None,
                    on_progress=lambda _cd, _pn: None,
                    on_done=lambda: done_ev.set(),
                    on_stop=lambda: done_ev.set(),
                    on_error=lambda _e: done_ev.set(),
                )
                done_ev.wait(timeout=600)
            self._root.after(0, self._scripts_tab.set_status, "Script complete.")

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Engine callbacks  (always on UI thread via root.after)
    # ------------------------------------------------------------------

    def _on_countdown(self, remaining: int) -> None:
        self._main_tab.set_countdown(remaining)

    def _on_typing_start(self, total: int, repeat: int) -> None:
        self._main_tab.set_total_chars(total, repeat)
        self._main_tab.set_typing(1, repeat)

    def _on_progress(self, chars_done: int, pass_num: int) -> None:
        total  = self._main_tab._total_chars
        repeat = self._main_tab._repeat_count
        self._main_tab.set_progress(chars_done, total, pass_num, repeat)

    def _on_done(self) -> None:
        self._main_tab.set_done()
        self._beep(start=False)
        if self._tray_hidden:
            self._restore_from_tray()

    def _on_stop(self) -> None:
        self._main_tab.set_stopped()
        self._beep(start=False)
        if self._tray_hidden:
            self._restore_from_tray()

    def _on_error(self, message: str) -> None:
        self._main_tab.set_error(message)
        if self._tray_hidden:
            self._restore_from_tray()
        messagebox.showerror("AutoTyper error", message)

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def _save_profile_dialog(self) -> None:
        text = self._main_tab.get_text()
        if not text.strip():
            messagebox.showwarning("Empty", "Enter some text before saving.")
            return
        name = simpledialog.askstring("Save Profile", "Profile name:",
                                      parent=self._root)
        if not name or not name.strip():
            return
        self._profiles.add(
            name=name.strip(), text=text,
            delay_ms=self._main_tab.get_delay_ms(),
            jitter_ms=self._main_tab.get_jitter_ms(),
            start_delay_s=self._main_tab.get_start_delay_s(),
            repeat_count=self._main_tab.get_repeat_count(),
            paste_mode=self._main_tab.get_paste_mode(),
            word_by_word=self._main_tab.get_word_by_word(),
            expand_variables=self._main_tab.get_expand_variables(),
        )
        self._profiles_tab.refresh()
        messagebox.showinfo("Saved", f'Profile "{name.strip()}" saved.')

    def _load_profile(self, profile: dict) -> None:
        self._main_tab.load_profile(profile)
        # Switch to Type tab
        self._root.nametowidget(self._main_tab.winfo_parent()).select(self._main_tab)

    # ------------------------------------------------------------------
    # Hotkey
    # ------------------------------------------------------------------

    def _register_hotkey(self) -> None:
        key = self._settings.get("hotkey", "f6")
        if self._hotkey.available:
            self._hotkey.register(key, self._toggle_typing)

    def _on_hotkey_changed(self, new_key: str) -> None:
        self._hotkey.unregister()
        if self._hotkey.available:
            self._hotkey.register(new_key, self._toggle_typing)

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def _on_encryption_changed(self, password: str) -> None:
        self._profiles.set_encryption_password(password)

    # ------------------------------------------------------------------
    # Auto-lock
    # ------------------------------------------------------------------

    def _configure_auto_lock(self) -> None:
        enabled = self._settings.get("auto_lock", False)
        minutes = self._settings.get("auto_lock_minutes", 5)
        self._locker.configure(enabled, minutes)

    def _on_auto_lock(self) -> None:
        self._root.after(0, self._do_lock)

    def _do_lock(self) -> None:
        messagebox.showinfo(
            "AutoTyper locked",
            "AutoTyper has locked due to inactivity.\n"
            "Re-open to continue.",
        )
        self._root.iconify()

    # ------------------------------------------------------------------
    # System tray
    # ------------------------------------------------------------------

    def _minimize_to_tray(self) -> None:
        if not _TRAY_OK:
            self._root.iconify()
            return
        self._root.withdraw()
        self._tray_hidden = True
        img = _make_tray_image()
        self._tray = pystray.Icon(
            "AutoTyper", img, "AutoTyper",
            menu=pystray.Menu(
                pystray.MenuItem("Show",        self._restore_from_tray),
                pystray.MenuItem("Stop Typing", lambda: self._root.after(0, self._stop_typing)),
                pystray.MenuItem("Quit",        lambda: self._root.after(0, self._on_close)),
            ),
        )
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _restore_from_tray(self) -> None:
        if self._tray:
            try:
                self._tray.stop()
            except Exception:  # noqa: BLE001
                pass
            self._tray = None
        self._tray_hidden = False
        self._root.deiconify()
        self._root.lift()

    # ------------------------------------------------------------------
    # Sound
    # ------------------------------------------------------------------

    def _beep(self, start: bool) -> None:
        if not self._settings_tab.get_play_sounds() or not _WINSOUND_OK:
            return
        freq, dur = (1000, 100) if start else (600, 100)
        try:
            _ws.Beep(freq, dur)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Auto-updater
    # ------------------------------------------------------------------

    def _check_updates(self) -> None:
        def _on_new(version: str, url: str) -> None:
            self._root.after(0, self._notify_update, version, url)

        check_for_update(on_update_available=_on_new)

    def _notify_update(self, version: str, url: str) -> None:
        if messagebox.askyesno(
            "Update available",
            f"AutoTyper v{version} is available.\n\nOpen the release page?",
        ):
            import webbrowser
            webbrowser.open(url)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._engine.stop()
        self._hotkey.unregister()
        self._scheduler.cancel()
        if self._tray:
            try:
                self._tray.stop()
            except Exception:  # noqa: BLE001
                pass
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AutoTyperApp()
    app.run()
