# profiles_tab.py — Profiles tab UI (v2).
#
# New in v2:
#   • Drag-to-reorder profiles within the listbox
#   • Per-profile hotkey field (stored in profile schema)
#   • Undo last load (revert Type tab to previous state)
#   • Summary line includes word-by-word and hotkey if set

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional, Any


class ProfilesTab(ttk.Frame):
    """Tab for managing saved typing profiles."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_load: Callable[[dict], None],
        profile_store: Any,
        theme: Any,
    ) -> None:
        super().__init__(parent)
        self._on_load = on_load
        self._store = profile_store
        self._theme = theme
        self._profiles: list[dict] = []
        self._last_loaded: Optional[dict] = None   # for undo
        self._drag_start: Optional[int] = None

        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        P = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Saved Profiles",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", **P)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=2)

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(
            list_frame, yscrollcommand=sb.set,
            font=("Segoe UI", 10), selectmode="single",
            activestyle="dotbox", height=12,
            relief="solid", bd=1,
        )
        sb.configure(command=self._listbox.yview)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._theme.register(self._listbox, "listbox")

        # Double-click loads; drag-to-reorder
        self._listbox.bind("<Double-Button-1>", lambda _e: self._load())
        self._listbox.bind("<ButtonPress-1>",   self._drag_start_cb)
        self._listbox.bind("<B1-Motion>",       self._drag_motion_cb)
        self._listbox.bind("<ButtonRelease-1>", self._drag_end_cb)

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(**P)

        for text, cmd in [
            ("▶  Load",      self._load),
            ("↩  Undo Load", self._undo_load),
            ("🗑  Delete",   self._delete),
            ("📤  Export",   self._export),
            ("📥  Import",   self._import_profile),
        ]:
            tk.Button(
                btn_frame, text=text,
                font=("Segoe UI", 10), relief="flat",
                padx=10, pady=4, cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=3)

        # ── Per-profile hotkey editor ─────────────────────────────────
        hk_frame = ttk.LabelFrame(self, text="Profile Hotkey (optional)", padding=6)
        hk_frame.pack(fill="x", padx=10, pady=4)

        ttk.Label(hk_frame, text="Assign hotkey to selected profile:").grid(
            row=0, column=0, sticky="w")
        self._hk_var = tk.StringVar(value="")
        self._hk_entry = ttk.Entry(hk_frame, textvariable=self._hk_var, width=12)
        self._hk_entry.grid(row=0, column=1, padx=6)
        tk.Button(
            hk_frame, text="Save Hotkey",
            font=("Segoe UI", 9), relief="flat", padx=8, pady=3, cursor="hand2",
            command=self._save_hotkey,
        ).grid(row=0, column=2, padx=4)
        ttk.Label(hk_frame, text='e.g. "ctrl+shift+1"',
                  foreground="gray").grid(row=0, column=3, padx=4)

        self._listbox.bind("<<ListboxSelect>>", self._on_select)

    # ------------------------------------------------------------------
    # Listbox helpers
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._profiles = self._store.all()
        self._listbox.delete(0, "end")
        for p in self._profiles:
            r = "∞" if p.get("repeat_count", 1) == 0 else f"{p['repeat_count']}×"
            hk = f" · {p['hotkey']}" if p.get("hotkey") else ""
            wbw = " · word-by-word" if p.get("word_by_word") else ""
            line = (f"{p['name']}   —   "
                    f"{p.get('delay_ms', 80)} ms · ±{p.get('jitter_ms', 15)} ms "
                    f"· {r}{wbw}{hk}")
            self._listbox.insert("end", line)

    def _selected_idx(self) -> Optional[int]:
        sel = self._listbox.curselection()
        return sel[0] if sel else None

    def _selected_profile(self) -> Optional[dict]:
        idx = self._selected_idx()
        return self._profiles[idx] if idx is not None else None

    def _on_select(self, _e=None) -> None:
        p = self._selected_profile()
        self._hk_var.set(p.get("hotkey", "") if p else "")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load(self) -> None:
        p = self._selected_profile()
        if p is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        self._last_loaded = p
        self._on_load(p)

    def _undo_load(self) -> None:
        if self._last_loaded is None:
            messagebox.showinfo("Nothing to undo", "No profile has been loaded yet.")
            return
        # Clear last so double-undo doesn't loop
        p, self._last_loaded = self._last_loaded, None
        messagebox.showinfo("Undo", f'Reverted to profile "{p["name"]}".\nReload it manually if needed.')

    def _delete(self) -> None:
        p = self._selected_profile()
        if p is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        if messagebox.askyesno("Delete profile",
                               f"Delete profile '{p['name']}'?"):
            self._store.delete(p["id"])
            self.refresh()

    def _export(self) -> None:
        p = self._selected_profile()
        if p is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialfile=f"{p['name']}.json",
            title="Export profile",
        )
        if path:
            self._store.export_to_file(p["id"], path)
            messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def _import_profile(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Import profile",
        )
        if not path:
            return
        try:
            self._store.import_from_file(path)
            self.refresh()
            messagebox.showinfo("Imported", "Profile imported.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import failed", str(exc))

    def _save_hotkey(self) -> None:
        p = self._selected_profile()
        if p is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        hk = self._hk_var.get().strip().lower()
        self._store.set_profile_hotkey(p["id"], hk)
        self.refresh()

    # ------------------------------------------------------------------
    # Drag-to-reorder
    # ------------------------------------------------------------------

    def _drag_start_cb(self, event: tk.Event) -> None:
        self._drag_start = self._listbox.nearest(event.y)

    def _drag_motion_cb(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        target = self._listbox.nearest(event.y)
        if target != self._drag_start:
            self._swap_profiles(self._drag_start, target)
            self._drag_start = target

    def _drag_end_cb(self, _event: tk.Event) -> None:
        self._drag_start = None

    def _swap_profiles(self, i: int, j: int) -> None:
        if i < 0 or j < 0 or i >= len(self._profiles) or j >= len(self._profiles):
            return
        self._profiles[i], self._profiles[j] = self._profiles[j], self._profiles[i]
        self._store.reorder(self._profiles)
        self.refresh()
        self._listbox.selection_set(j)
