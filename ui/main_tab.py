# main_tab.py — "Type" tab UI (v2).
#
# New in v2:
#   • Speed presets: Slow / Human / Fast / Instant buttons
#   • Live preview: current character highlighted in the text area
#   • Font size control for the text area
#   • Word-by-word mode checkbox + word delay slider
#   • Expand variables checkbox ({DATE}, {TIME}, {CLIPBOARD}, etc.)
#   • Scheduled typing: optional time picker (HH:MM)
#   • Keyboard shortcut cheat-sheet button (?)

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui.theme import ThemeManager

# Speed presets: (label, delay_ms, jitter_ms)
_PRESETS = [
    ("Slow",    220, 40),
    ("Human",    80, 15),
    ("Fast",     30,  5),
    ("Instant",   0,  0),
]


class MainTab(ttk.Frame):
    """Primary tab: text input, typing options, start/stop controls."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_save_profile: Callable[[], None],
        on_show_shortcuts: Callable[[], None],
        theme: "ThemeManager",
    ) -> None:
        super().__init__(parent)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_save_profile = on_save_profile
        self._on_show_shortcuts = on_show_shortcuts
        self._theme = theme

        # Control variables
        self._speed_var      = tk.IntVar(value=80)
        self._jitter_var     = tk.IntVar(value=15)
        self._delay_var      = tk.IntVar(value=3)
        self._repeat_var     = tk.StringVar(value="1")
        self._paste_var      = tk.BooleanVar(value=False)
        self._word_var       = tk.BooleanVar(value=False)
        self._word_delay_var = tk.IntVar(value=200)
        self._expand_var     = tk.BooleanVar(value=True)
        self._font_size_var  = tk.IntVar(value=11)
        self._char_count_var = tk.StringVar(value="0 characters")
        self._status_var     = tk.StringVar(value="Idle")
        self._progress_var   = tk.DoubleVar(value=0.0)
        self._schedule_var   = tk.BooleanVar(value=False)
        self._sched_h_var    = tk.StringVar(value="00")
        self._sched_m_var    = tk.StringVar(value="00")

        # Internal state
        self._total_chars: int = 0
        self._repeat_count: int = 1
        self._placeholder_active: bool = True
        self._placeholder = (
            "Type your text here…\n"
            "Use {ENTER} {TAB} {BACKSPACE} for special keys.\n"
            "Variables: {DATE} {TIME} {CLIPBOARD} {COUNTER} {RANDOM:100}"
        )

        self._build()
        theme.register(self, "default")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        P = {"padx": 10, "pady": 3}

        # ── Warning banner ────────────────────────────────────────────
        self._banner = tk.Label(
            self,
            text=(
                "AutoTyper injects keystrokes into any focused window. "
                "No input is logged. Failsafe: move mouse to top-left corner."
            ),
            bg="#fff3cd", fg="#856404",
            wraplength=480, justify="left",
            font=("Segoe UI", 9), padx=10, pady=5,
        )
        self._banner.pack(fill="x", padx=10, pady=(8, 2))
        self._theme.register(self._banner, "banner")

        # ── Text area ─────────────────────────────────────────────────
        tf = ttk.LabelFrame(self, text="Text to type", padding=6)
        tf.pack(fill="both", expand=True, padx=10, pady=2)

        self._text_area = tk.Text(
            tf, height=7,
            font=("Consolas", self._font_size_var.get()),
            wrap="word", relief="solid", bd=1, undo=True,
        )
        sb = ttk.Scrollbar(tf, orient="vertical", command=self._text_area.yview)
        self._text_area.configure(yscrollcommand=sb.set)
        self._text_area.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._theme.register(self._text_area, "text")

        self._text_area.tag_configure("current_char",
                                       background="#0078d4", foreground="white")
        self._set_placeholder()
        self._text_area.bind("<FocusIn>",  self._clear_placeholder)
        self._text_area.bind("<FocusOut>", self._restore_placeholder)
        self._text_area.bind("<KeyRelease>", self._update_char_count)

        # Font size + char count row
        meta_row = ttk.Frame(self)
        meta_row.pack(fill="x", padx=12)
        ttk.Label(meta_row, text="Font size:").pack(side="left")
        ttk.Spinbox(meta_row, from_=8, to=24, width=4,
                    textvariable=self._font_size_var,
                    command=self._update_font).pack(side="left", padx=4)
        ttk.Label(meta_row, textvariable=self._char_count_var,
                  foreground="gray").pack(side="right")

        # ── Speed presets ─────────────────────────────────────────────
        pre_frame = ttk.Frame(self)
        pre_frame.pack(fill="x", **P)
        ttk.Label(pre_frame, text="Preset:").pack(side="left")
        for label, delay, jitter in _PRESETS:
            tk.Button(
                pre_frame, text=label,
                font=("Segoe UI", 9), relief="flat",
                padx=8, pady=3, cursor="hand2",
                command=lambda d=delay, j=jitter: self._apply_preset(d, j),
            ).pack(side="left", padx=3)
        self._theme.register(pre_frame, "default")

        # ── Sliders ───────────────────────────────────────────────────
        sliders = ttk.Frame(self)
        sliders.pack(fill="x", **P)

        self._speed_lbl = ttk.Label(sliders, text="Speed:  80 ms / key", width=24, anchor="w")
        self._speed_lbl.grid(row=0, column=0, sticky="w")
        ttk.Scale(sliders, from_=0, to=500, orient="horizontal",
                  variable=self._speed_var, length=220,
                  command=lambda v: self._update_speed_lbl(int(float(v)))
                  ).grid(row=0, column=1, padx=6)

        self._jitter_lbl = ttk.Label(sliders, text="Jitter:  ±15 ms", width=18, anchor="w")
        self._jitter_lbl.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Scale(sliders, from_=0, to=80, orient="horizontal",
                  variable=self._jitter_var, length=220,
                  command=lambda v: self._update_jitter_lbl(int(float(v)))
                  ).grid(row=1, column=1, padx=6)

        self._delay_lbl = ttk.Label(sliders, text="Start delay:  3 s", width=18, anchor="w")
        self._delay_lbl.grid(row=2, column=0, sticky="w")
        ttk.Scale(sliders, from_=0, to=10, orient="horizontal",
                  variable=self._delay_var, length=220,
                  command=lambda v: self._update_delay_lbl(int(float(v)))
                  ).grid(row=2, column=1, padx=6)

        # ── Options row ───────────────────────────────────────────────
        opt1 = ttk.Frame(self)
        opt1.pack(fill="x", **P)

        ttk.Label(opt1, text="Repeat:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(opt1, from_=0, to=999, width=6,
                    textvariable=self._repeat_var).grid(row=0, column=1, padx=4)
        ttk.Label(opt1, text="(0 = ∞)", foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Checkbutton(opt1, text="Paste mode",
                        variable=self._paste_var).grid(row=0, column=3, padx=10)
        ttk.Checkbutton(opt1, text="Expand variables",
                        variable=self._expand_var).grid(row=0, column=4, padx=4)

        opt2 = ttk.Frame(self)
        opt2.pack(fill="x", **P)
        ttk.Checkbutton(opt2, text="Word-by-word mode",
                        variable=self._word_var).grid(row=0, column=0, sticky="w")
        self._word_delay_lbl = ttk.Label(opt2, text="Word gap: 200 ms", width=18)
        self._word_delay_lbl.grid(row=0, column=1, padx=6)
        ttk.Scale(opt2, from_=50, to=2000, orient="horizontal",
                  variable=self._word_delay_var, length=160,
                  command=lambda v: self._word_delay_lbl.configure(
                      text=f"Word gap: {int(float(v))} ms")
                  ).grid(row=0, column=2, padx=4)

        # ── Scheduled typing ──────────────────────────────────────────
        sched = ttk.Frame(self)
        sched.pack(fill="x", **P)
        ttk.Checkbutton(sched, text="Schedule at:",
                        variable=self._schedule_var).grid(row=0, column=0)
        ttk.Spinbox(sched, from_=0, to=23, width=3, format="%02.0f",
                    textvariable=self._sched_h_var).grid(row=0, column=1, padx=2)
        ttk.Label(sched, text=":").grid(row=0, column=2)
        ttk.Spinbox(sched, from_=0, to=59, width=3, format="%02.0f",
                    textvariable=self._sched_m_var).grid(row=0, column=3, padx=2)
        ttk.Label(sched, text="(HH:MM today)", foreground="gray").grid(row=0, column=4, padx=4)

        # ── Progress + status ─────────────────────────────────────────
        self._progress = ttk.Progressbar(self, variable=self._progress_var,
                                          maximum=100.0)
        self._progress.pack(fill="x", padx=10, pady=2)
        ttk.Label(self, textvariable=self._status_var,
                  font=("Segoe UI", 10, "bold")).pack(pady=2)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = ttk.Frame(self)
        btn_row.pack(pady=4)

        self._start_btn = tk.Button(
            btn_row, text="▶  Start   F6",
            bg="#28a745", fg="white",
            activebackground="#218838", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=14, pady=5, cursor="hand2",
            command=self._on_start,
        )
        self._start_btn.grid(row=0, column=0, padx=5)

        self._stop_btn = tk.Button(
            btn_row, text="■  Stop   F6",
            bg="#dc3545", fg="white",
            activebackground="#c82333", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=14, pady=5, cursor="hand2",
            state="disabled", command=self._on_stop,
        )
        self._stop_btn.grid(row=0, column=1, padx=5)

        tk.Button(
            btn_row, text="💾  Save Profile",
            font=("Segoe UI", 10), relief="flat",
            padx=10, pady=5, cursor="hand2",
            command=self._on_save_profile,
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            btn_row, text="?",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=8, pady=5, cursor="hand2",
            command=self._on_show_shortcuts,
        ).grid(row=0, column=3, padx=2)

    # ------------------------------------------------------------------
    # Placeholder
    # ------------------------------------------------------------------

    def _set_placeholder(self) -> None:
        self._text_area.insert("1.0", self._placeholder)
        self._text_area.configure(foreground="gray")
        self._placeholder_active = True

    def _clear_placeholder(self, _e=None) -> None:
        if self._placeholder_active:
            self._text_area.delete("1.0", "end")
            self._text_area.configure(foreground=self._theme.palette()["entry_fg"])
            self._placeholder_active = False

    def _restore_placeholder(self, _e=None) -> None:
        if not self._text_area.get("1.0", "end-1c").strip():
            self._set_placeholder()

    # ------------------------------------------------------------------
    # Label updaters
    # ------------------------------------------------------------------

    def _update_speed_lbl(self, v: int) -> None:
        self._speed_lbl.configure(text=f"Speed:  {v} ms / key")

    def _update_jitter_lbl(self, v: int) -> None:
        self._jitter_lbl.configure(text=f"Jitter:  ±{v} ms")

    def _update_delay_lbl(self, v: int) -> None:
        self._delay_lbl.configure(text=f"Start delay:  {v} s")

    def _update_char_count(self, _e=None) -> None:
        if self._placeholder_active:
            self._char_count_var.set("0 characters")
            return
        n = len(self._text_area.get("1.0", "end-1c"))
        self._char_count_var.set(f"{n:,} characters")

    def _update_font(self) -> None:
        size = self._font_size_var.get()
        self._text_area.configure(font=("Consolas", size))

    def _apply_preset(self, delay: int, jitter: int) -> None:
        self._speed_var.set(delay)
        self._jitter_var.set(jitter)
        self._update_speed_lbl(delay)
        self._update_jitter_lbl(jitter)

    # ------------------------------------------------------------------
    # Live preview: highlight character at index
    # ------------------------------------------------------------------

    def highlight_char(self, index: int) -> None:
        """Highlight the character at *index* in the text area."""
        self._text_area.tag_remove("current_char", "1.0", "end")
        if index < 0:
            return
        try:
            pos = f"1.0 + {index} chars"
            self._text_area.tag_add("current_char", pos, f"{pos} + 1 chars")
            self._text_area.see(pos)
        except tk.TclError:
            pass

    def clear_highlight(self) -> None:
        self._text_area.tag_remove("current_char", "1.0", "end")

    # ------------------------------------------------------------------
    # State setters (called from app controller via root.after)
    # ------------------------------------------------------------------

    def set_idle(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Idle")
        self._progress_var.set(0.0)
        self.clear_highlight()

    def set_countdown(self, remaining: int) -> None:
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_var.set(f"Starting in {remaining}…")

    def set_scheduled(self, at: str) -> None:
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_var.set(f"Scheduled for {at} — waiting…")

    def set_typing(self, pass_num: int, repeat_count: int) -> None:
        label = "∞" if repeat_count == 0 else str(repeat_count)
        self._status_var.set(f"Typing… (pass {pass_num}/{label})")

    def set_progress(self, chars_done: int, total: int,
                     pass_num: int, repeat_count: int) -> None:
        pct = (chars_done / total * 100.0) if total > 0 else 0.0
        self._progress_var.set(pct)
        label = "∞" if repeat_count == 0 else str(repeat_count)
        self._status_var.set(f"Typing… (pass {pass_num}/{label})")
        self.highlight_char(chars_done)

    def set_done(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Done ✓")
        self._progress_var.set(100.0)
        self.clear_highlight()

    def set_stopped(self) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("Stopped")
        self._progress_var.set(0.0)
        self.clear_highlight()

    def set_error(self, message: str) -> None:
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set(f"Error: {message}")
        self._progress_var.set(0.0)
        self.clear_highlight()

    def set_total_chars(self, n: int, repeat_count: int) -> None:
        self._total_chars = n
        self._repeat_count = repeat_count

    # ------------------------------------------------------------------
    # Data getters
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        if self._placeholder_active:
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
            return max(0, int(self._repeat_var.get()))
        except ValueError:
            return 1

    def get_paste_mode(self) -> bool:
        return self._paste_var.get()

    def get_word_by_word(self) -> bool:
        return self._word_var.get()

    def get_word_delay_ms(self) -> int:
        return int(self._word_delay_var.get())

    def get_expand_variables(self) -> bool:
        return self._expand_var.get()

    def get_schedule(self) -> Optional[str]:
        """Return "HH:MM" if scheduled mode is on, else None."""
        if not self._schedule_var.get():
            return None
        h = self._sched_h_var.get().zfill(2)
        m = self._sched_m_var.get().zfill(2)
        return f"{h}:{m}"

    # ------------------------------------------------------------------
    # Profile loader
    # ------------------------------------------------------------------

    def load_profile(self, profile: dict) -> None:
        self._clear_placeholder()
        self._text_area.delete("1.0", "end")
        self._text_area.insert("1.0", profile.get("text", ""))
        self._placeholder_active = False
        self._speed_var.set(profile.get("delay_ms", 80))
        self._update_speed_lbl(self._speed_var.get())
        self._jitter_var.set(profile.get("jitter_ms", 15))
        self._update_jitter_lbl(self._jitter_var.get())
        self._delay_var.set(profile.get("start_delay_s", 3))
        self._update_delay_lbl(self._delay_var.get())
        self._repeat_var.set(str(profile.get("repeat_count", 1)))
        self._paste_var.set(profile.get("paste_mode", False))
        self._word_var.set(profile.get("word_by_word", False))
        self._expand_var.set(profile.get("expand_variables", True))
        self._update_char_count()
