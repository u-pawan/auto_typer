# settings_tab.py — Settings tab UI.
#
# Exposes hotkey recording, default typing parameters, and OS-level
# options (startup, tray, sounds).  Writes through SettingsStore on Save.

import tkinter as tk
from tkinter import ttk, messagebox
import sys
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
        settings_store: Any,       # storage.store.SettingsStore
        hotkey_manager: Any,       # engine.hotkey.HotkeyManager
        on_hotkey_changed: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._store = settings_store
        self._hkm = hotkey_manager
        self._on_hotkey_changed = on_hotkey_changed
        self._recording = False

        # Control variables — loaded from store
        s = settings_store.all()
        self._hotkey_var = tk.StringVar(value=s.get("hotkey", "f6").upper())
        self._speed_var = tk.IntVar(value=s.get("default_delay_ms", 80))
        self._jitter_var = tk.IntVar(value=s.get("default_jitter_ms", 15))
        self._start_delay_var = tk.IntVar(value=s.get("default_start_delay_s", 3))
        self._minimize_var = tk.BooleanVar(value=s.get("minimize_on_start", False))
        self._sounds_var = tk.BooleanVar(value=s.get("play_sounds", False))
        self._startup_var = tk.BooleanVar(value=s.get("launch_at_startup", False))

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        PAD = {"padx": 10, "pady": 6}
        INNER = {"padx": 6, "pady": 3}

        # ── Hotkey ────────────────────────────────────────────────────
        hk_frame = ttk.LabelFrame(self, text="Global Hotkey", padding=8)
        hk_frame.pack(fill="x", **PAD)

        ttk.Label(hk_frame, text="Current hotkey:").grid(row=0, column=0, sticky="w", **INNER)
        self._hotkey_entry = ttk.Entry(
            hk_frame, textvariable=self._hotkey_var,
            state="readonly", width=12, font=("Segoe UI", 11, "bold"),
        )
        self._hotkey_entry.grid(row=0, column=1, sticky="w", **INNER)
        self._record_btn = tk.Button(
            hk_frame, text="  Record new key  ",
            font=("Segoe UI", 9), relief="flat",
            padx=8, pady=4, cursor="hand2",
            command=self._start_recording,
        )
        self._record_btn.grid(row=0, column=2, padx=8)

        self._record_label = ttk.Label(
            hk_frame, text="", foreground="#856404",
            font=("Segoe UI", 9, "italic"),
        )
        self._record_label.grid(row=1, column=0, columnspan=3, sticky="w", **INNER)

        if not self._hkm.available:
            ttk.Label(
                hk_frame,
                text="⚠  keyboard library not found — hotkeys disabled. "
                     "Install with: pip install keyboard",
                foreground="#721c24",
            ).grid(row=2, column=0, columnspan=3, sticky="w", **INNER)

        # ── Default typing values ─────────────────────────────────────
        def_frame = ttk.LabelFrame(self, text="Default Typing Settings", padding=8)
        def_frame.pack(fill="x", **PAD)

        rows = [
            ("Default speed (ms/key):", self._speed_var, 10, 500),
            ("Default jitter (ms):",    self._jitter_var, 0, 80),
            ("Default start delay (s):", self._start_delay_var, 1, 10),
        ]
        for i, (label, var, lo, hi) in enumerate(rows):
            ttk.Label(def_frame, text=label).grid(row=i, column=0, sticky="w", **INNER)
            ttk.Spinbox(def_frame, from_=lo, to=hi, width=8,
                        textvariable=var).grid(row=i, column=1, sticky="w", **INNER)

        # ── OS options ────────────────────────────────────────────────
        os_frame = ttk.LabelFrame(self, text="System Options", padding=8)
        os_frame.pack(fill="x", **PAD)

        ttk.Checkbutton(
            os_frame,
            text="Launch AutoTyper at Windows startup",
            variable=self._startup_var,
        ).pack(anchor="w", **INNER)
        ttk.Checkbutton(
            os_frame,
            text="Minimize to system tray when typing starts",
            variable=self._minimize_var,
        ).pack(anchor="w", **INNER)
        ttk.Checkbutton(
            os_frame,
            text="Play sound on start / stop  (winsound.Beep)",
            variable=self._sounds_var,
        ).pack(anchor="w", **INNER)

        # ── Failsafe notice ───────────────────────────────────────────
        ttk.Label(
            self,
            text=(
                "ℹ  Failsafe: move the mouse to the top-left screen corner "
                "at any time to immediately abort typing."
            ),
            foreground="gray",
            font=("Segoe UI", 9),
            wraplength=480,
        ).pack(anchor="w", padx=10, pady=(4, 0))

        # ── Save button ───────────────────────────────────────────────
        tk.Button(
            self,
            text="💾  Save Settings",
            font=("Segoe UI", 11, "bold"),
            bg="#0d6efd", fg="white",
            activebackground="#0b5ed7", activeforeground="white",
            relief="flat", padx=16, pady=6,
            cursor="hand2",
            command=self._save,
        ).pack(**PAD)

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        if not self._hkm.available:
            messagebox.showwarning("Unavailable", "keyboard library is not installed.")
            return
        if self._recording:
            return
        self._recording = True
        self._record_btn.configure(state="disabled")
        self._record_label.configure(text="Press any key…")
        # Run in a thread so we don't block the UI
        import threading
        threading.Thread(target=self._record_thread, daemon=True).start()

    def _record_thread(self) -> None:
        key = self._hkm.record_next_key()
        self.after(0, self._finish_recording, key)

    def _finish_recording(self, key: Optional[str]) -> None:
        self._recording = False
        self._record_btn.configure(state="normal")
        if key:
            self._hotkey_var.set(key.upper())
            self._record_label.configure(text=f"Hotkey set to: {key.upper()}")
        else:
            self._record_label.configure(text="Recording cancelled.")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        hotkey = self._hotkey_var.get().lower()
        self._store.set("hotkey", hotkey)
        self._store.set("default_delay_ms", int(self._speed_var.get()))
        self._store.set("default_jitter_ms", int(self._jitter_var.get()))
        self._store.set("default_start_delay_s", int(self._start_delay_var.get()))
        self._store.set("minimize_on_start", self._minimize_var.get())
        self._store.set("play_sounds", self._sounds_var.get())
        self._store.set("launch_at_startup", self._startup_var.get())
        self._store.save()

        # Update the registered hotkey
        self._on_hotkey_changed(hotkey)

        # Update startup registry entry
        _set_startup(self._startup_var.get(), sys.executable)

        messagebox.showinfo("Saved", "Settings saved successfully.")

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_minimize_on_start(self) -> bool:
        return self._minimize_var.get()

    def get_play_sounds(self) -> bool:
        return self._sounds_var.get()
