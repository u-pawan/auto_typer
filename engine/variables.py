# variables.py — runtime variable expansion for text before typing.
#
# Supported variables (case-insensitive):
#   {DATE}       → current date  e.g. "2026-05-11"
#   {TIME}       → current time  e.g. "14:32:07"
#   {DATETIME}   → date + time   e.g. "2026-05-11 14:32:07"
#   {CLIPBOARD}  → current clipboard contents
#   {COUNTER}    → auto-incrementing integer, resets each run
#   {RANDOM:N}   → random integer 1–N  e.g. {RANDOM:100} → "42"
#
# expand(text) returns the text with all variables replaced.

import re
import random
from datetime import datetime
from typing import Optional

try:
    import pyperclip as _pyperclip
    _CLIP_OK = True
except ImportError:
    _CLIP_OK = False

# Matches {VAR} or {VAR:ARG}
_VAR_RE = re.compile(r"\{([A-Za-z]+)(?::([^}]*))?\}")

_counter: int = 0


def reset_counter() -> None:
    """Reset the {COUNTER} variable to 0 (call before each typing run)."""
    global _counter
    _counter = 0


def expand(text: str) -> str:
    """Replace all variable tokens in *text* with their current values."""
    now = datetime.now()

    def _replace(match: re.Match) -> str:
        global _counter
        name = match.group(1).upper()
        arg  = match.group(2) or ""

        if name == "DATE":
            return now.strftime("%Y-%m-%d")
        if name == "TIME":
            return now.strftime("%H:%M:%S")
        if name == "DATETIME":
            return now.strftime("%Y-%m-%d %H:%M:%S")
        if name == "CLIPBOARD":
            if _CLIP_OK:
                try:
                    return _pyperclip.paste() or ""
                except Exception:  # noqa: BLE001
                    return ""
            return ""
        if name == "COUNTER":
            _counter += 1
            return str(_counter)
        if name == "RANDOM":
            try:
                n = int(arg) if arg else 100
                return str(random.randint(1, max(1, n)))
            except ValueError:
                return match.group(0)  # return original token unchanged
        # Unknown variable — leave it as-is
        return match.group(0)

    return _VAR_RE.sub(_replace, text)
