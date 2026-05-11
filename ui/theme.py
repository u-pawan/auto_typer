# theme.py — light / dark theme manager for AutoTyper.
#
# ThemeManager applies a colour palette to ttk.Style and tracks all plain
# tk widgets (Text, Button, Label, Frame, Listbox) so they can be
# re-coloured when the user toggles dark mode.
#
# Usage:
#   tm = ThemeManager(root)
#   tm.apply("dark")   # or "light"
#   tm.register(widget, role="text")  # optional: mark widget for re-colouring

import tkinter as tk
from tkinter import ttk
from typing import Literal

Mode = Literal["light", "dark"]

# ──────────────────────────────────────────────────────────────────────
# Colour palettes
# ──────────────────────────────────────────────────────────────────────

_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg":           "#f5f5f5",
        "fg":           "#1a1a1a",
        "entry_bg":     "#ffffff",
        "entry_fg":     "#1a1a1a",
        "select_bg":    "#0078d4",
        "select_fg":    "#ffffff",
        "button_bg":    "#e0e0e0",
        "button_fg":    "#1a1a1a",
        "banner_bg":    "#fff3cd",
        "banner_fg":    "#856404",
        "listbox_bg":   "#ffffff",
        "listbox_fg":   "#1a1a1a",
        "disabled_fg":  "#888888",
        "border":       "#cccccc",
        "tab_bg":       "#f0f0f0",
        "highlight":    "#cce5ff",
    },
    "dark": {
        "bg":           "#1e1e1e",
        "fg":           "#d4d4d4",
        "entry_bg":     "#2d2d2d",
        "entry_fg":     "#d4d4d4",
        "select_bg":    "#264f78",
        "select_fg":    "#ffffff",
        "button_bg":    "#3a3a3a",
        "button_fg":    "#d4d4d4",
        "banner_bg":    "#3b3000",
        "banner_fg":    "#ffd666",
        "listbox_bg":   "#2d2d2d",
        "listbox_fg":   "#d4d4d4",
        "disabled_fg":  "#666666",
        "border":       "#444444",
        "tab_bg":       "#252526",
        "highlight":    "#1a3a5c",
    },
}


class ThemeManager:
    """Applies and tracks dark/light themes across the whole application."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._mode: Mode = "light"
        self._style = ttk.Style(root)
        # Registry: list of (widget_ref, role)
        self._registry: list[tuple[tk.Widget, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> Mode:
        return self._mode

    def palette(self) -> dict[str, str]:
        return _PALETTES[self._mode]

    def apply(self, mode: Mode) -> None:
        self._mode = mode
        p = _PALETTES[mode]
        self._apply_ttk(p)
        self._apply_root(p)
        self._apply_registered(p)

    def toggle(self) -> Mode:
        new = "dark" if self._mode == "light" else "light"
        self.apply(new)
        return new

    def register(self, widget: tk.Widget, role: str = "default") -> None:
        """Track *widget* so it gets re-coloured on theme change."""
        self._registry.append((widget, role))

    # ------------------------------------------------------------------
    # Internal: apply to ttk styles
    # ------------------------------------------------------------------

    def _apply_ttk(self, p: dict[str, str]) -> None:
        s = self._style
        # Pick a neutral base theme
        for t in ("clam", "default"):
            if t in s.theme_names():
                s.theme_use(t)
                break

        # General widget background / foreground
        s.configure(".",
                     background=p["bg"],
                     foreground=p["fg"],
                     fieldbackground=p["entry_bg"],
                     troughcolor=p["bg"],
                     bordercolor=p["border"],
                     darkcolor=p["border"],
                     lightcolor=p["border"])

        s.configure("TFrame",       background=p["bg"])
        s.configure("TLabel",       background=p["bg"], foreground=p["fg"])
        s.configure("TLabelframe",  background=p["bg"], foreground=p["fg"])
        s.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
        s.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
        s.configure("TRadiobutton", background=p["bg"], foreground=p["fg"])

        s.configure("TEntry",
                     fieldbackground=p["entry_bg"],
                     foreground=p["entry_fg"],
                     insertcolor=p["fg"])

        s.configure("TSpinbox",
                     fieldbackground=p["entry_bg"],
                     foreground=p["entry_fg"])

        s.configure("TButton",
                     background=p["button_bg"],
                     foreground=p["button_fg"],
                     bordercolor=p["border"])
        s.map("TButton",
              background=[("active", p["select_bg"]), ("disabled", p["bg"])],
              foreground=[("active", p["select_fg"]), ("disabled", p["disabled_fg"])])

        s.configure("TNotebook",        background=p["tab_bg"], bordercolor=p["border"])
        s.configure("TNotebook.Tab",    background=p["tab_bg"], foreground=p["fg"],
                     padding=[10, 4])
        s.map("TNotebook.Tab",
              background=[("selected", p["bg"])],
              foreground=[("selected", p["fg"])])

        s.configure("TScrollbar",
                     background=p["button_bg"],
                     troughcolor=p["bg"],
                     arrowcolor=p["fg"])

        s.configure("TProgressbar",
                     background=p["select_bg"],
                     troughcolor=p["entry_bg"])

        s.configure("TScale",
                     background=p["bg"],
                     troughcolor=p["entry_bg"])

        s.configure("Horizontal.TScale", background=p["bg"])

    # ------------------------------------------------------------------
    # Internal: apply to root window
    # ------------------------------------------------------------------

    def _apply_root(self, p: dict[str, str]) -> None:
        self._root.configure(bg=p["bg"])

    # ------------------------------------------------------------------
    # Internal: apply to manually registered plain-tk widgets
    # ------------------------------------------------------------------

    def _apply_registered(self, p: dict[str, str]) -> None:
        for widget, role in list(self._registry):
            try:
                self._apply_widget(widget, role, p)
            except tk.TclError:
                pass  # widget was destroyed

    def _apply_widget(self, w: tk.Widget, role: str, p: dict[str, str]) -> None:
        try:
            if role == "text":
                w.configure(  # type: ignore[union-attr]
                    bg=p["entry_bg"], fg=p["entry_fg"],
                    insertbackground=p["fg"],
                    selectbackground=p["select_bg"],
                    selectforeground=p["select_fg"],
                )
            elif role == "listbox":
                w.configure(  # type: ignore[union-attr]
                    bg=p["listbox_bg"], fg=p["listbox_fg"],
                    selectbackground=p["select_bg"],
                    selectforeground=p["select_fg"],
                )
            elif role == "banner":
                w.configure(bg=p["banner_bg"], fg=p["banner_fg"])  # type: ignore[union-attr]
            elif role == "button_green":
                pass  # keep coloured buttons as-is
            elif role == "button_red":
                pass
            else:
                w.configure(bg=p["bg"], fg=p["fg"])  # type: ignore[union-attr]
        except tk.TclError:
            pass
