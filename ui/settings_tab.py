# settings_tab.py — Settings tab UI (v2).
#
# New in v2:
#   • Dark mode toggle (delegates to ThemeManager)
#   • Font size default setting
#   • Auto-lock: clear sensitive profiles from memory after N minutes idle
#   • Encryption password field (for ProfileStore encryption)
#   • All new settings persisted via SettingsStore

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
from typing import Callable, Optional, Any

try:
    import winreg as _winreg
    _WINREG_OK = True
except ImportError:
    _WINREG_OK = False

_STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "AutoTyper"


def _set_startup(enabled: bool, exe_path: str) -> None:
    if not _WINREG_OK:
        return
    try:
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, _STARTUP_KEY, 0,
            _winreg.KEY_SET_VALUE,
        )
        if enabled:
            _winreg.SetValueEx(key, _APP_NAME, 0, _winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                _winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        _winreg.CloseKey(key)
    except Exception:  # noqa: BLE001
        pass


class SettingsTab(ttk.Frame):
    """Tab for global application settings."""

    def __init__(
        self,
        parent: ttk.Notebook,
        settings_store: Any,
        hotkey_manager: Any,
        theme: Any,
        on_hotkey_changed: Callable[[str], None],
        on_theme_changed: Callable[[str], None],
        on_encryption_changed: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._store = settings_store
        self._hkm = hotkey_manager
        self._theme = theme
        self._on_hotkey_changed = on_hotkey_changed
        self._on_theme_changed = on_theme_changed
        self._on_encryption_changed = on_encryption_changed
        self._recording = False

        s = settings_store.all()
        self._hotkey_var      = tk.StringVar(value=s.get("hotkey", "f6").upper())
        self._speed_var       = tk.IntVar(value=s.get("default_delay_ms", 80))
        self._jitter_var      = tk.IntVar(value=s.get("default_jitter_ms", 15))
        self._start_delay_var = tk.IntVar(value=s.get("default_start_delay_s", 3))
        self._font_size_var   = tk.IntVar(value=s.get("default_font_size", 11))
        self._minimize_var    = tk.BooleanVar(value=s.get("minimize_on_start", False))
        self._sounds_var      = tk.BooleanVar(value=s.get("play_sounds", False))
        self._startup_var     = tk.BooleanVar(value=s.get("launch_at_startup", False))
        self._dark_var        = tk.BooleanVar(value=s.get("dark_mode", False))
        self._auto_lock_var   = tk.BooleanVar(value=s.get("auto_lock", False))
        self._lock_mins_var   = tk.IntVar(value=s.get("auto_lock_minutes", 5))
        self._encrypt_var     = tk.BooleanVar(value=s.get("encrypt_profiles", False))
        self._enc_pass_var    = tk.StringVar(value="")

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        P  = {"padx": 10, "pady": 5}
        IP = {"padx": 6,  "pady": 3}

        # ── Hotkey ────────────────────────────────────────────────────
        hk = ttk.LabelFrame(self, text="Global Hotkey", padding=8)
        hk.pack(fill="x", **P)

        ttk.Label(hk, text="Current hotkey:").grid(row=0, column=0, sticky="w", **IP)
        self._hk_entry = ttk.Entry(hk, textvariable=self._hotkey_var,
                                   state="readonly", width=12,
                                   font=("Segoe UI", 11, "bold"))
        self._hk_entry.grid(row=0, column=1, sticky="w", **IP)
        self._rec_btn = tk.Button(
            hk, text="  Record new key  ",
            font=("Segoe UI", 9), relief="flat",
            padx=8, pady=3, cursor="hand2",
            command=self._start_recording,
        )
        self._rec_btn.grid(row=0, column=2, padx=8)
        self._rec_lbl = ttk.Label(hk, text="", foreground="#856404",
                                   font=("Segoe UI", 9, "italic"))
        self._rec_lbl.grid(row=1, column=0, columnspan=3, sticky="w", **IP)

        if not self._hkm.available:
            ttk.Label(hk, text="keyboard library not found — hotkeys disabled.",
                      foreground="red").grid(row=2, column=0, columnspan=3, **IP)

        # ── Appearance ────────────────────────────────────────────────
        ap = ttk.LabelFrame(self, text="Appearance", padding=8)
        ap.pack(fill="x", **P)

        ttk.Checkbutton(ap, text="Dark mode",
                        variable=self._dark_var,
                        command=self._toggle_dark).pack(anchor="w", **IP)
        df = ttk.Frame(ap)
        df.pack(anchor="w", **IP)
        ttk.Label(df, text="Default font size:").pack(side="left")
        ttk.Spinbox(df, from_=8, to=24, width=5,
                    textvariable=self._font_size_var).pack(side="left", padx=4)

        # ── Default typing values ─────────────────────────────────────
        dv = ttk.LabelFrame(self, text="Default Typing Values", padding=8)
        dv.pack(fill="x", **P)

        for i, (lbl, var, lo, hi) in enumerate([
            ("Default speed (ms/key):",   self._speed_var,       0, 500),
            ("Default jitter (ms):",      self._jitter_var,      0,  80),
            ("Default start delay (s):",  self._start_delay_var, 0,  10),
        ]):
            ttk.Label(dv, text=lbl).grid(row=i, column=0, sticky="w", **IP)
            ttk.Spinbox(dv, from_=lo, to=hi, width=8,
                        textvariable=var).grid(row=i, column=1, sticky="w", **IP)

        # ── Security ──────────────────────────────────────────────────
        sec = ttk.LabelFrame(self, text="Security", padding=8)
        sec.pack(fill="x", **P)

        enc_row = ttk.Frame(sec)
        enc_row.pack(anchor="w", **IP)
        ttk.Checkbutton(enc_row, text="Encrypt profiles with password",
                        variable=self._encrypt_var).pack(side="left")

        pass_row = ttk.Frame(sec)
        pass_row.pack(anchor="w", **IP)
        ttk.Label(pass_row, text="Encryption password:").pack(side="left")
        self._pass_entry = ttk.Entry(pass_row, textvariable=self._enc_pass_var,
                                      show="*", width=20)
        self._pass_entry.pack(side="left", padx=6)
        ttk.Label(pass_row, text="(leave blank to keep existing)",
                  foreground="gray").pack(side="left")

        lock_row = ttk.Frame(sec)
        lock_row.pack(anchor="w", **IP)
        ttk.Checkbutton(lock_row, text="Auto-lock after",
                        variable=self._auto_lock_var).pack(side="left")
        ttk.Spinbox(lock_row, from_=1, to=60, width=5,
                    textvariable=self._lock_mins_var).pack(side="left", padx=4)
        ttk.Label(lock_row, text="minutes idle").pack(side="left")

        # ── System options ────────────────────────────────────────────
        sys_f = ttk.LabelFrame(self, text="System", padding=8)
        sys_f.pack(fill="x", **P)

        ttk.Checkbutton(sys_f, text="Launch at Windows startup",
                        variable=self._startup_var).pack(anchor="w", **IP)
        ttk.Checkbutton(sys_f, text="Minimize to system tray when typing starts",
                        variable=self._minimize_var).pack(anchor="w", **IP)
        ttk.Checkbutton(sys_f, text="Play sound on start / stop",
                        variable=self._sounds_var).pack(anchor="w", **IP)

        # Failsafe notice
        ttk.Label(
            self,
            text="Failsafe: move mouse to top-left corner to abort typing instantly.",
            foreground="gray", font=("Segoe UI", 9),
        ).pack(anchor="w", padx=10, pady=2)

        # Save button
        tk.Button(
            self, text="💾  Save Settings",
            font=("Segoe UI", 11, "bold"),
            bg="#0d6efd", fg="white",
            activebackground="#0b5ed7", activeforeground="white",
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._save,
        ).pack(pady=6)

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        if not self._hkm.available:
            messagebox.showwarning("Unavailable", "keyboard library not installed.")
            return
        if self._recording:
            return
        self._recording = True
        self._rec_btn.configure(state="disabled")
        self._rec_lbl.configure(text="Press any key…")
        threading.Thread(target=self._record_thread, daemon=True).start()

    def _record_thread(self) -> None:
        key = self._hkm.record_next_key()
        self.after(0, self._finish_recording, key)

    def _finish_recording(self, key: Optional[str]) -> None:
        self._recording = False
        self._rec_btn.configure(state="normal")
        if key:
            self._hotkey_var.set(key.upper())
            self._rec_lbl.configure(text=f"Set to: {key.upper()}")
        else:
            self._rec_lbl.configure(text="Cancelled.")

    # ------------------------------------------------------------------
    # Dark mode
    # ------------------------------------------------------------------

    def _toggle_dark(self) -> None:
        mode = "dark" if self._dark_var.get() else "light"
        self._on_theme_changed(mode)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        hotkey = self._hotkey_var.get().lower()
        self._store.set("hotkey", hotkey)
        self._store.set("default_delay_ms",    int(self._speed_var.get()))
        self._store.set("default_jitter_ms",   int(self._jitter_var.get()))
        self._store.set("default_start_delay_s", int(self._start_delay_var.get()))
        self._store.set("default_font_size",   int(self._font_size_var.get()))
        self._store.set("minimize_on_start",   self._minimize_var.get())
        self._store.set("play_sounds",         self._sounds_var.get())
        self._store.set("launch_at_startup",   self._startup_var.get())
        self._store.set("dark_mode",           self._dark_var.get())
        self._store.set("auto_lock",           self._auto_lock_var.get())
        self._store.set("auto_lock_minutes",   int(self._lock_mins_var.get()))
        self._store.set("encrypt_profiles",    self._encrypt_var.get())
        self._store.save()

        self._on_hotkey_changed(hotkey)

        password = self._enc_pass_var.get()
        if self._encrypt_var.get() and password:
            self._on_encryption_changed(password)

        _set_startup(self._startup_var.get(), sys.executable)
        messagebox.showinfo("Saved", "Settings saved.")

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_minimize_on_start(self) -> bool:
        return self._minimize_var.get()

    def get_play_sounds(self) -> bool:
        return self._sounds_var.get()

    def get_auto_lock(self) -> bool:
        return self._auto_lock_var.get()

    def get_auto_lock_minutes(self) -> int:
        return int(self._lock_mins_var.get())
