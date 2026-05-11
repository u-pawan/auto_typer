# scripts_tab.py — Multi-step scripts tab.
#
# A script is an ordered list of steps, each with:
#   • Text to type (or a special command like {PAUSE:2})
#   • Delay before this step (seconds)
#   • Individual speed/jitter overrides (optional)
#
# Scripts are saved to storage as part of the profiles JSON under a
# separate "scripts" key.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json
from typing import Callable, Any, Optional


class ScriptsTab(ttk.Frame):
    """Tab for building and running multi-step typing scripts."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_run_script: Callable[[list[dict]], None],
        on_stop: Callable[[], None],
        script_store: Any,
        theme: Any,
    ) -> None:
        super().__init__(parent)
        self._on_run = on_run_script
        self._on_stop = on_stop
        self._store = script_store
        self._theme = theme
        self._steps: list[dict] = []
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        P = {"padx": 10, "pady": 4}

        ttk.Label(self, text="Multi-Step Script",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", **P)
        ttk.Label(
            self,
            text=(
                "Each step types its text, then waits the specified gap before the next step.\n"
                "Use {PAUSE:N} as the text to insert a pure pause of N seconds."
            ),
            foreground="gray", font=("Segoe UI", 9),
        ).pack(anchor="w", padx=10)

        # ── Step list ─────────────────────────────────────────────────
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(
            list_frame, yscrollcommand=sb.set,
            font=("Consolas", 10), height=8,
            selectmode="single", relief="solid", bd=1,
        )
        sb.configure(command=self._listbox.yview)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._theme.register(self._listbox, "listbox")

        # ── Step editor ───────────────────────────────────────────────
        editor = ttk.LabelFrame(self, text="Step Editor", padding=8)
        editor.pack(fill="x", **P)

        ttk.Label(editor, text="Text / command:").grid(row=0, column=0, sticky="w")
        self._text_var = tk.StringVar()
        ttk.Entry(editor, textvariable=self._text_var, width=40).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4)

        ttk.Label(editor, text="Gap before (s):").grid(row=1, column=0, sticky="w", pady=3)
        self._gap_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(editor, from_=0, to=300, increment=0.5,
                    width=7, textvariable=self._gap_var).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(editor, text="Speed (ms):").grid(row=1, column=2, sticky="w", padx=6)
        self._speed_var = tk.IntVar(value=80)
        ttk.Spinbox(editor, from_=0, to=500, width=6,
                    textvariable=self._speed_var).grid(row=1, column=3, sticky="w")

        # ── Edit buttons ──────────────────────────────────────────────
        eb = ttk.Frame(self)
        eb.pack(**P)
        for label, cmd in [
            ("➕ Add Step",    self._add_step),
            ("✏️ Update",      self._update_step),
            ("⬆️ Move Up",    self._move_up),
            ("⬇️ Move Down",  self._move_down),
            ("🗑 Remove",     self._remove_step),
            ("🧹 Clear All",  self._clear_all),
        ]:
            tk.Button(eb, text=label, font=("Segoe UI", 9),
                      relief="flat", padx=7, pady=3,
                      cursor="hand2", command=cmd).pack(side="left", padx=2)

        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # ── Script file controls ──────────────────────────────────────
        sf = ttk.Frame(self)
        sf.pack(**P)
        for label, cmd in [
            ("💾 Save Script",  self._save_script),
            ("📂 Load Script",  self._load_script),
        ]:
            tk.Button(sf, text=label, font=("Segoe UI", 9),
                      relief="flat", padx=8, pady=3,
                      cursor="hand2", command=cmd).pack(side="left", padx=3)

        # ── Run controls ──────────────────────────────────────────────
        rf = ttk.Frame(self)
        rf.pack(**P)
        self._run_btn = tk.Button(
            rf, text="▶  Run Script",
            bg="#28a745", fg="white",
            activebackground="#218838", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=14, pady=5, cursor="hand2",
            command=self._run,
        )
        self._run_btn.pack(side="left", padx=4)
        tk.Button(
            rf, text="■  Stop",
            bg="#dc3545", fg="white",
            activebackground="#c82333", activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", padx=14, pady=5, cursor="hand2",
            command=self._on_stop,
        ).pack(side="left", padx=4)

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self._status_var,
                  font=("Segoe UI", 10, "bold")).pack(pady=2)

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def _add_step(self) -> None:
        text = self._text_var.get().strip()
        if not text:
            messagebox.showwarning("Empty", "Enter some text for the step.")
            return
        step = {
            "text":     text,
            "gap_s":    float(self._gap_var.get()),
            "delay_ms": int(self._speed_var.get()),
        }
        self._steps.append(step)
        self._refresh_list()

    def _update_step(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            return
        self._steps[idx] = {
            "text":     self._text_var.get().strip(),
            "gap_s":    float(self._gap_var.get()),
            "delay_ms": int(self._speed_var.get()),
        }
        self._refresh_list()

    def _move_up(self) -> None:
        idx = self._selected_idx()
        if idx is None or idx == 0:
            return
        self._steps[idx - 1], self._steps[idx] = self._steps[idx], self._steps[idx - 1]
        self._refresh_list()
        self._listbox.selection_set(idx - 1)

    def _move_down(self) -> None:
        idx = self._selected_idx()
        if idx is None or idx >= len(self._steps) - 1:
            return
        self._steps[idx], self._steps[idx + 1] = self._steps[idx + 1], self._steps[idx]
        self._refresh_list()
        self._listbox.selection_set(idx + 1)

    def _remove_step(self) -> None:
        idx = self._selected_idx()
        if idx is None:
            return
        self._steps.pop(idx)
        self._refresh_list()

    def _clear_all(self) -> None:
        if self._steps and messagebox.askyesno("Clear", "Remove all steps?"):
            self._steps.clear()
            self._refresh_list()

    def _on_select(self, _e=None) -> None:
        idx = self._selected_idx()
        if idx is None:
            return
        s = self._steps[idx]
        self._text_var.set(s["text"])
        self._gap_var.set(s["gap_s"])
        self._speed_var.set(s["delay_ms"])

    def _selected_idx(self) -> Optional[int]:
        sel = self._listbox.curselection()
        return sel[0] if sel else None

    def _refresh_list(self) -> None:
        self._listbox.delete(0, "end")
        for i, s in enumerate(self._steps, 1):
            preview = s["text"][:40] + ("…" if len(s["text"]) > 40 else "")
            self._listbox.insert("end",
                f"{i:02d}.  [{s['gap_s']:.1f}s gap | {s['delay_ms']}ms]  {preview}")

    # ------------------------------------------------------------------
    # Save / load script files
    # ------------------------------------------------------------------

    def _save_script(self) -> None:
        if not self._steps:
            messagebox.showwarning("Empty", "Add at least one step first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Save script",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._steps, f, indent=2)
            messagebox.showinfo("Saved", f"Script saved to:\n{path}")

    def _load_script(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Load script",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Expected a list of steps.")
            self._steps = data
            self._refresh_list()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Load failed", str(exc))

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run(self) -> None:
        if not self._steps:
            messagebox.showwarning("Empty script", "Add at least one step first.")
            return
        self._status_var.set("Running…")
        self._on_run(list(self._steps))

    def set_status(self, text: str) -> None:
        self._status_var.set(text)
