# main_tab.py — "Type" tab UI.
#
# Owns all widgets for configuring and triggering a typing run.
# Communicates upward via callbacks rather than direct parent references
# so that the tab logic stays self-contained.

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Callable, Optional


class MainTab(ttk.Frame):
    """The primary tab where users configure and start a typing run."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_save_profile: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_save_profile = on_save_profile
        self._char_count_var = tk.StringVar(value="0 characters")
        self._speed_var = tk.IntVar(value=80)
        self._jitter_var = tk.IntVar(value=15)
        self._delay_var = tk.IntVar(value=3)
        self._repeat_var = tk.StringVar(value="1")
        self._paste_mode_var = tk.BooleanVar(value=False)
        self._status_var = tk.StringVar(value="Idle")
        self._progress_var = tk.DoubleVar(value=0.0)
        self._total_chars: int = 0
        self._repeat_count: int = 1

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        PAD = {"padx": 10, "pady": 4}

        # ── Warning banner ────────────────────────────────────────────
        banner = tk.Label(
            self,
            text=(
                "⚠  AutoTyper injects keystrokes into any focused window. "
                "No input is logged. Use responsibly."
            ),
            bg="#fff3cd",
            fg="#856404",
            wraplength=480,
            justify="left",
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
        )
        banner.pack(fill="x", padx=10, pady=(10, 2))

        # ── Text area ─────────────────────────────────────────────────
        text_frame = ttk.LabelFrame(self, text="Text to type", padding=6)
        text_frame.pack(fill="both", expand=True, **PAD)

        self._text_area = tk.Text(
            text_frame,
            height=8,
            font=("Consolas", 11),
            wrap="word",
            relief="solid",
            bd=1,
            undo=True,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical",
                                  command=self._text_area.yview)
        self._text_area.configure(yscrollcommand=scrollbar.set)
        self._text_area.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._text_area.bind("<KeyRelease>", self._update_char_count)

        # Placeholder
        self._placeholder = "Type your text here… Use {ENTER}, {TAB}, {BACKSPACE} for special keys."
        self._set_placeholder()
        self._text_area.bind("<FocusIn>", self._clear_placeholder)
        self._text_area.bind("<FocusOut>", self._restore_placeholder)

        # Char count
        ttk.Label(self, textvariable=self._char_count_var,
                  font=("Segoe UI", 8), foreground="gray").pack(anchor="e", padx=14)

        # ── Sliders ───────────────────────────────────────────────────
        sliders_frame = ttk.Frame(self)
        sliders_frame.pack(fill="x", **PAD)

        self._speed_label = ttk.Label(sliders_frame, text="Speed:  80 ms / keystroke",
                                      width=28, anchor="w")
        self._speed_label.grid(row=0, column=0, sticky="w")
        ttk.Scale(sliders_frame, from_=10, to=500, orient="horizontal",
                  variable=self._speed_var, length=220,
                  command=lambda v: self._update_speed_label(int(float(v)))
                  ).grid(row=0, column=1, padx=6)

        self._jitter_label = ttk.Label(sliders_frame, text="Jitter:  ±15 ms",
                                       width=20, anchor="w")
        self._jitter_label.grid(row=1, column=0, sticky="w", pady=4)
        ttk.Scale(sliders_frame, from_=0, to=80, orient="horizontal",
                  variable=self._jitter_var, length=220,
                  command=lambda v: self._update_jitter_label(int(float(v)))
                  ).grid(row=1, column=1, padx=6)

        self._delay_label = ttk.Label(sliders_frame, text="Start delay:  3 s",
                                      width=20, anchor="w")
        self._delay_label.grid(row=2, column=0, sticky="w")
        ttk.Scale(sliders_frame, from_=1, to=10, orient="horizontal",
                  variable=self._delay_var, length=220,
                  command=lambda v: self._update_delay_label(int(float(v)))
                  ).grid(row=2, column=1, padx=6)

        # ── Repeat + paste ────────────────────────────────────────────
        opts_frame = ttk.Frame(self)
        opts_frame.pack(fill="x", **PAD)

        ttk.Label(opts_frame, text="Repeat:").grid(row=0, column=0, sticky="w")
        self._repeat_spin = ttk.Spinbox(
            opts_frame, from_=0, to=999, width=6,
            textvariable=self._repeat_var,
            format="%g",
        )
        self._repeat_spin.grid(row=0, column=1, padx=6, sticky="w")
        ttk.Label(opts_frame, text="(0 = ∞ infinite)",
                  foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Checkbutton(
            opts_frame,
            text="Paste mode  (instant — bypasses character-by-character typing)",
            variable=self._paste_mode_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=4)

        # ── Progress + status ─────────────────────────────────────────
        self._progress = ttk.Progressbar(self, variable=self._progress_var,
                                         maximum=100.0, length=480)
        self._progress.pack(fill="x", **PAD)

        ttk.Label(self, textvariable=self._status_var,
                  font=("Segoe UI", 10, "bold")).pack(**PAD)

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(**PAD)

        self._start_btn = tk.Button(
            btn_frame,
            text="▶  Start   F6",
            bg="#28a745", fg="white",
            activebackground="#218838", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=18, pady=6,
            cursor="hand2",
            command=self._on_start,
        )
        self._start_btn.grid(row=0, column=0, padx=6)

        self._stop_btn = tk.Button(
            btn_frame,
            text="■  Stop   F6",
            bg="#dc3545", fg="white",
            activebackground="#c82333", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=18, pady=6,
            cursor="hand2",
            state="disabled",
            command=self._on_stop,
        )
        self._stop_btn.grid(row=0, column=1, padx=6)

        tk.Button(
            btn_frame,
            text="💾  Save as Profile",
            font=("Segoe UI", 10),
            relief="flat", padx=10, pady=6,
            cursor="hand2",
            command=self._on_save_profile,
        ).grid(row=0, column=2, padx=6)

    # ------------------------------------------------------------------
    # Placeholder helpers
    # ------------------------------------------------------------------

    def _set_placeholder(self) -> None:
        self._text_area.insert("1.0", self._placeholder)
        self._text_area.configure(foreground="gray")
        self._placeholder_active = True

    def _clear_placeholder(self, _event: tk.Event = None) -> None:  # type: ignore[assignment]
        if getattr(self, "_placeholder_active", False):
            self._text_area.delete("1.0", "end")
            self._text_area.configure(foreground="black")
            self._placeholder_active = False

    def _restore_placeholder(self, _event: tk.Event = None) -> None:  # type: ignore[assignment]
        if not self._text_area.get("1.0", "end-1c").strip():
            self._set_placeholder()

    # ------------------------------------------------------------------
    # Slider label updaters
    # ------------------------------------------------------------------

    def _update_speed_label(self, v: int) -> None:
        self._speed_label.configure(text=f"Speed:  {v} ms / keystroke")

    def _update_jitter_label(self, v: int) -> None:
        self._jitter_label.configure(text=f"Jitter:  ±{v} ms")

    def _update_delay_label(self, v: int) -> None:
        self._delay_label.configure(text=f"Start delay:  {v} s")

    def _update_char_count(self, _event: tk.Event = None) -> None:  # type: ignore[assignment]
        if getattr(self, "_placeholder_active", False):
            self._char_count_var.set("0 characters")
            return
        n = len(self._text_area.get("1.0", "end-1c"))
        self._char_count_var.set(f"{n} characters")

    # ------------------------------------------------------------------
    # Public: state setters called by the app controller
    # ------------------------------------------------------------------

    def set_idle(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Idle")
        self._progress_var.set(0.0)

    def set_countdown(self, remaining: int) -> None:
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_var.set(f"Starting in {remaining}…")

    def set_typing(self, pass_num: int, repeat_count: int) -> None:
        label = "∞" if repeat_count == 0 else str(repeat_count)
        self._status_var.set(f"Typing… (pass {pass_num}/{label})")

    def set_progress(self, chars_done: int, total: int, pass_num: int,
                     repeat_count: int) -> None:
        if total > 0:
            pct = (chars_done / total) * 100.0
            self._progress_var.set(pct)
        label = "∞" if repeat_count == 0 else str(repeat_count)
        self._status_var.set(f"Typing… (pass {pass_num}/{label})")

    def set_done(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Done ✓")
        self._progress_var.set(100.0)

    def set_stopped(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Stopped")
        self._progress_var.set(0.0)

    def set_error(self, message: str) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set(f"Error: {message}")
        self._progress_var.set(0.0)

    # ------------------------------------------------------------------
    # Public: data getters
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        if getattr(self, "_placeholder_active", False):
            return ""
        return self._text_area.get("1.0", "end-1c")

    def get_delay_ms(self) -> int:
        return int(self._speed_var.get())

    def get_jitter_ms(self) -> int:
        return int(self._jitter_var.get())

    def get_start_delay_s(self) -> int:
        return int(self._delay_var.get())

    def get_repeat_count(self) -> int:
        try:
            v = int(self._repeat_var.get())
            return max(0, v)
        except ValueError:
            return 1

    def get_paste_mode(self) -> bool:
        return self._paste_mode_var.get()

    def load_profile(self, profile: dict) -> None:
        """Populate all controls from a saved profile dict."""
        self._clear_placeholder()
        self._text_area.delete("1.0", "end")
        self._text_area.insert("1.0", profile.get("text", ""))
        self._placeholder_active = False
        self._speed_var.set(profile.get("delay_ms", 80))
        self._update_speed_label(self._speed_var.get())
        self._jitter_var.set(profile.get("jitter_ms", 15))
        self._update_jitter_label(self._jitter_var.get())
        self._delay_var.set(profile.get("start_delay_s", 3))
        self._update_delay_label(self._delay_var.get())
        repeat = profile.get("repeat_count", 1)
        self._repeat_var.set(str(repeat))
        self._paste_mode_var.set(profile.get("paste_mode", False))
        self._update_char_count()

    def set_total_chars(self, n: int, repeat_count: int) -> None:
        self._total_chars = n
        self._repeat_count = repeat_count
