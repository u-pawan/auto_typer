# macro_tab.py — Macro recorder / player UI.
#
# Lets users record a keystroke sequence (with timing), name it,
# save it to disk, and replay it.  Requires pynput to record;
# playback works without it via the MacroPlayer.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Callable, Optional
from engine.macro import MacroRecorder, MacroPlayer, Macro


class MacroTab(ttk.Frame):
    """Tab for recording and playing back keystroke macros."""

    def __init__(
        self,
        parent: ttk.Notebook,
        root: tk.Tk,
        theme: Any,
    ) -> None:
        super().__init__(parent)
        self._root = root
        self._theme = theme
        self._recorder = MacroRecorder()
        self._player = MacroPlayer(root)
        self._current_macro: Optional[Macro] = None
        self._macros: list[Macro] = []
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        P = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Macro Recorder",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", **P)

        if not self._recorder.is_available:
            ttk.Label(
                self,
                text=(
                    "pynput is not installed — recording is disabled.\n"
                    "Install with: pip install pynput\n"
                    "You can still load and play back saved macro files."
                ),
                foreground="#856404",
                background="#fff3cd",
                font=("Segoe UI", 9),
                justify="left",
                relief="flat",
                padx=8, pady=6,
            ).pack(fill="x", padx=10, pady=4)

        # ── Record controls ───────────────────────────────────────────
        rec = ttk.LabelFrame(self, text="Record", padding=8)
        rec.pack(fill="x", **P)

        self._status_var = tk.StringVar(value="Idle")
        ttk.Label(rec, textvariable=self._status_var,
                  font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w")

        self._rec_btn = tk.Button(
            rec, text="⏺  Record  (F9)",
            bg="#dc3545", fg="white",
            activebackground="#c82333", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._toggle_record,
        )
        self._rec_btn.grid(row=1, column=0, padx=4, pady=6)

        ttk.Label(rec, text="Stop key:").grid(row=1, column=1, sticky="w")
        self._stop_key_var = tk.StringVar(value="f9")
        ttk.Entry(rec, textvariable=self._stop_key_var, width=8).grid(
            row=1, column=2, padx=4)
        ttk.Label(rec, text="(press to stop recording)",
                  foreground="gray").grid(row=1, column=3, sticky="w")

        # ── Macro list ────────────────────────────────────────────────
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(
            list_frame, yscrollcommand=sb.set,
            font=("Segoe UI", 10), height=8,
            selectmode="single", relief="solid", bd=1,
        )
        sb.configure(command=self._listbox.yview)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._theme.register(self._listbox, "listbox")

        # ── Playback controls ─────────────────────────────────────────
        play = ttk.LabelFrame(self, text="Playback", padding=8)
        play.pack(fill="x", **P)

        ttk.Label(play, text="Repeat:").grid(row=0, column=0, sticky="w")
        self._repeat_var = tk.IntVar(value=1)
        ttk.Spinbox(play, from_=1, to=999, width=6,
                    textvariable=self._repeat_var).grid(row=0, column=1, padx=4)

        self._play_btn = tk.Button(
            play, text="▶  Play",
            bg="#28a745", fg="white",
            activebackground="#218838", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._play,
        )
        self._play_btn.grid(row=0, column=2, padx=8)

        tk.Button(
            play, text="■  Stop",
            bg="#6c757d", fg="white",
            activebackground="#5a6268", activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._stop_play,
        ).grid(row=0, column=3, padx=4)

        # ── File controls ─────────────────────────────────────────────
        fc = ttk.Frame(self)
        fc.pack(**P)
        for label, cmd in [
            ("💾 Save Macro", self._save_macro),
            ("📂 Load Macro", self._load_macro),
            ("🗑 Delete",     self._delete_macro),
        ]:
            tk.Button(fc, text=label, font=("Segoe UI", 9),
                      relief="flat", padx=8, pady=3,
                      cursor="hand2", command=cmd).pack(side="left", padx=3)

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def _toggle_record(self) -> None:
        if not self._recorder.is_available:
            messagebox.showwarning("Unavailable", "pynput is not installed.")
            return
        if self._recorder.is_recording():
            macro = self._recorder.stop()
            self._current_macro = macro
            self._macros.append(macro)
            self._refresh_list()
            self._status_var.set(
                f"Recorded {len(macro.events)} events. "
                f"Select it above and click Play, or save to file."
            )
            self._rec_btn.configure(text="⏺  Record  (F9)", bg="#dc3545")
        else:
            stop_key = self._stop_key_var.get().strip() or "f9"
            self._recorder.start(stop_key=stop_key)
            self._status_var.set(f"Recording… press {stop_key.upper()} to stop.")
            self._rec_btn.configure(text="⏹  Stop Recording", bg="#fd7e14")
            # Poll until recorder stops naturally (user pressed stop key)
            self._poll_record()

    def _poll_record(self) -> None:
        if self._recorder.is_recording():
            self._root.after(200, self._poll_record)
        else:
            if self._recorder.is_recording() is False:
                # May have stopped via stop_key
                self._rec_btn.configure(text="⏺  Record  (F9)", bg="#dc3545")

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _play(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            messagebox.showinfo("No selection", "Select a macro first.")
            return
        macro = self._macros[idx]
        repeat = int(self._repeat_var.get())
        self._status_var.set(f"Playing '{macro.name}'…")
        self._player.play(
            macro=macro,
            repeat=repeat,
            on_done=lambda: self._root.after(0, self._on_play_done),
            on_error=lambda e: self._root.after(0, self._on_play_error, e),
        )

    def _stop_play(self) -> None:
        self._player.stop()
        self._status_var.set("Stopped.")

    def _on_play_done(self) -> None:
        self._status_var.set("Playback complete.")

    def _on_play_error(self, msg: str) -> None:
        self._status_var.set(f"Error: {msg}")

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def _save_macro(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            messagebox.showinfo("No selection", "Select a macro first.")
            return
        macro = self._macros[idx]
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialfile=f"{macro.name}.json",
            title="Save macro",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(macro.to_json())
            messagebox.showinfo("Saved", f"Macro saved to:\n{path}")

    def _load_macro(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Load macro",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                macro = Macro.from_json(f.read())
            self._macros.append(macro)
            self._refresh_list()
            messagebox.showinfo("Loaded", f"Loaded macro: {macro.name}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load failed", str(exc))

    def _delete_macro(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            return
        self._macros.pop(idx)
        self._refresh_list()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        self._listbox.delete(0, "end")
        for m in self._macros:
            self._listbox.insert("end", f"{m.name}  ({len(m.events)} events)")

    def _selected_idx(self) -> Optional[int]:
        sel = self._listbox.curselection()
        return sel[0] if sel else None
