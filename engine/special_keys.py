# special_keys.py — maps escape sequences and {TOKEN} literals to pyautogui key names
#
# Two mechanisms:
#   1. ESCAPE_MAP: single-char Python escape sequences embedded in text
#   2. TOKEN_PATTERN: brace-wrapped tokens like {ENTER} the user types literally
#
# parse_text() returns a list of ("char", ch) or ("key", keyname) tuples that
# the typing engine iterates over.

import re
from typing import List, Tuple

# Maps Python escape chars → pyautogui press() key names
ESCAPE_MAP: dict[str, str] = {
    "\n": "enter",
    "\t": "tab",
    "\b": "backspace",
}

# Maps {TOKEN} strings (case-insensitive) → pyautogui key names
TOKEN_MAP: dict[str, str] = {
    "ENTER":     "enter",
    "RETURN":    "enter",
    "TAB":       "tab",
    "BACKSPACE": "backspace",
    "DELETE":    "delete",
    "DEL":       "delete",
    "SPACE":     "space",
    "ESC":       "escape",
    "ESCAPE":    "escape",
    "UP":        "up",
    "DOWN":      "down",
    "LEFT":      "left",
    "RIGHT":     "right",
    "HOME":      "home",
    "END":       "end",
    "PGUP":      "pageup",
    "PGDN":      "pagedown",
    "F1":  "f1",  "F2":  "f2",  "F3":  "f3",  "F4":  "f4",
    "F5":  "f5",  "F6":  "f6",  "F7":  "f7",  "F8":  "f8",
    "F9":  "f9",  "F10": "f10", "F11": "f11", "F12": "f12",
}

# Matches {TOKEN} anywhere in the text, e.g. {ENTER} or {F5}
_TOKEN_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")

Action = Tuple[str, str]  # ("char", ch) | ("key", keyname)


def parse_text(text: str) -> List[Action]:
    """Break *text* into a sequence of actions for the typing engine.

    Returns a list of tuples:
      ("char", single_char)   — type this character normally
      ("key",  pyautogui_key) — press this special key
    """
    actions: List[Action] = []
    # Split on {TOKEN} boundaries, processing the parts between tokens char-by-char
    parts = _TOKEN_RE.split(text)
    # _TOKEN_RE.split() interleaves plain strings and captured group matches:
    # "hello{ENTER}world" → ["hello", "ENTER", "world"]
    is_token = False
    for part in parts:
        if is_token:
            key = TOKEN_MAP.get(part.upper())
            if key:
                actions.append(("key", key))
            else:
                # Unknown token — type the braces literally
                for ch in "{" + part + "}":
                    actions.append(("char", ch))
        else:
            for ch in part:
                mapped = ESCAPE_MAP.get(ch)
                if mapped:
                    actions.append(("key", mapped))
                else:
                    actions.append(("char", ch))
        is_token = not is_token
    return actions
