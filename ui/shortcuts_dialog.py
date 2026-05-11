# shortcuts_dialog.py — keyboard shortcut cheat-sheet dialog.
#
# A small read-only dialog that lists all global hotkeys and in-app
# shortcuts so the user never has to guess.

import tkinter as tk
from tkinter import ttk


_SHORTCUTS: list[tuple[str, str]] = [
    # Category, description
    ("Global hotkeys", ""),
    ("F6",               "Toggle Start / Stop typing  (configurable in Settings)"),
    ("Mouse → top-left", "Failsafe: immediately abort typing"),
    ("", ""),
    ("Type tab", ""),
    ("Ctrl+Z",    "Undo last text edit"),
    ("Ctrl+A",    "Select all text in the text area"),
    ("", ""),
    ("Special key tokens", ""),
    ("{ENTER}",     "Press the Enter key"),
    ("{TAB}",       "Press the Tab key"),
    ("{BACKSPACE}", "Press Backspace"),
    ("{DELETE}",    "Press Delete"),
    ("{ESC}",       "Press Escape"),
    ("{F1}–{F12}", "Press a function key"),
    ("{UP/DOWN/LEFT/RIGHT}", "Arrow keys"),
    ("{HOME} {END}", "Navigation keys"),
    ("{PGUP} {PGDN}", "Page Up / Page Down"),
    ("", ""),
    ("Variable tokens", ""),
    ("{DATE}",        "Today's date  (YYYY-MM-DD)"),
    ("{TIME}",        "Current time  (HH:MM:SS)"),
    ("{DATETIME}",    "Date + time combined"),
    ("{CLIPBOARD}",   "Current clipboard contents"),
    ("{COUNTER}",     "Auto-incrementing number per keystroke"),
    ("{RANDOM:N}",    "Random integer between 1 and N"),
]


def show_shortcuts(parent: tk.Widget) -> None:
    """Open the shortcuts cheat-sheet as a modal dialog."""
    dlg = tk.Toplevel(parent)
    dlg.title("Keyboard Shortcuts & Tokens")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.focus_set()

    # Centre relative to parent
    dlg.update_idletasks()
    pw = parent.winfo_rootx()
    py = parent.winfo_rooty()
    dlg.geometry(f"560x480+{pw + 30}+{py + 30}")

    # Scrollable content
    canvas = tk.Canvas(dlg, highlightthickness=0)
    sb = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    frame = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
    frame.bind("<Configure>",
               lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(window_id, width=e.width))

    # Mouse-wheel scrolling
    dlg.bind_all("<MouseWheel>",
                 lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    for key, desc in _SHORTCUTS:
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=12, pady=1)
        if not key and not desc:
            ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=12, pady=4)
        elif not desc:
            # Category header
            ttk.Label(row, text=key,
                      font=("Segoe UI", 10, "bold"),
                      foreground="#0d6efd").pack(anchor="w")
        else:
            ttk.Label(row, text=key, width=26, anchor="w",
                      font=("Consolas", 9),
                      foreground="#c7254e").pack(side="left")
            ttk.Label(row, text=desc, anchor="w",
                      font=("Segoe UI", 9)).pack(side="left", fill="x")

    ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)
