# profiles_tab.py — Profiles tab UI.
#
# Lists saved profiles with summary lines, and provides Load, Delete,
# Export, and Import buttons.  Double-clicking a profile loads it.
# All persistence is delegated to ProfileStore; UI changes are local.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional, Any


class ProfilesTab(ttk.Frame):
    """Tab for managing saved typing profiles."""

    def __init__(
        self,
        parent: ttk.Notebook,
        on_load: Callable[[dict], None],
        profile_store: Any,  # storage.store.ProfileStore
    ) -> None:
        super().__init__(parent)
        self._on_load = on_load
        self._store = profile_store
        self._profiles: list[dict] = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        PAD = {"padx": 10, "pady": 6}

        ttk.Label(self, text="Saved Profiles",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", **PAD)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=2)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
            selectmode="single",
            activestyle="dotbox",
            height=14,
            relief="solid",
            bd=1,
        )
        scrollbar.configure(command=self._listbox.yview)
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._listbox.bind("<Double-Button-1>", lambda _e: self._load())

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(**PAD)

        for text, cmd in [
            ("▶  Load",   self._load),
            ("🗑  Delete", self._delete),
            ("📤  Export", self._export),
            ("📥  Import", self._import),
        ]:
            tk.Button(
                btn_frame,
                text=text,
                font=("Segoe UI", 10),
                relief="flat",
                padx=12, pady=5,
                cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the list from the store."""
        self._profiles = self._store.all()
        self._listbox.delete(0, "end")
        for p in self._profiles:
            repeat_label = "∞" if p.get("repeat_count", 1) == 0 else f"{p['repeat_count']}×"
            summary = (
                f"{p['name']}   —   "
                f"{p.get('delay_ms', 80)} ms · ±{p.get('jitter_ms', 15)} ms · {repeat_label}"
            )
            self._listbox.insert("end", summary)

    def _selected_profile(self) -> Optional[dict]:
        sel = self._listbox.curselection()
        if not sel:
            return None
        return self._profiles[sel[0]]

    def _load(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        self._on_load(profile)

    def _delete(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        if messagebox.askyesno(
            "Delete profile",
            f"Delete profile '{profile['name']}'?",
        ):
            self._store.delete(profile["id"])
            self.refresh()

    def _export(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{profile['name']}.json",
            title="Export profile",
        )
        if path:
            self._store.export_to_file(profile["id"], path)
            messagebox.showinfo("Exported", f"Profile saved to:\n{path}")

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import profile",
        )
        if not path:
            return
        try:
            self._store.import_from_file(path)
            self.refresh()
            messagebox.showinfo("Imported", "Profile imported successfully.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import failed", str(exc))
