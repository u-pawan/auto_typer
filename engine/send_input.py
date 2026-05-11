# send_input.py — Windows SendInput API wrapper for Unicode keystroke injection.
#
# Uses ctypes to call user32.SendInput directly, which supports full Unicode
# (including emoji and non-Latin characters) without requiring pywin32 or admin.
# Replaces pyautogui.write() for character typing; pyautogui.press() is still
# used for named special keys (Enter, Tab, etc.).

import ctypes
from ctypes import wintypes
from typing import Optional

# ──────────────────────────────────────────────────────────────────────
# Windows API constants
# ──────────────────────────────────────────────────────────────────────

INPUT_KEYBOARD: int = 1
KEYEVENTF_UNICODE: int = 0x0004
KEYEVENTF_KEYUP: int = 0x0002
KEYEVENTF_EXTENDEDKEY: int = 0x0001

# Virtual key codes for common modifier / special keys
VK_SHIFT: int = 0x10
VK_CONTROL: int = 0x11
VK_MENU: int = 0x12  # Alt


# ──────────────────────────────────────────────────────────────────────
# C structures
# ──────────────────────────────────────────────────────────────────────

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_u",   _INPUT_UNION),
    ]


_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = [
    wintypes.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
]
_SendInput.restype = wintypes.UINT

_INPUT_SIZE = ctypes.sizeof(INPUT)


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def send_char(char: str) -> bool:
    """Inject a single Unicode character via SendInput.

    Returns True on success, False if SendInput reported an error.
    Handles surrogate pairs (astral-plane characters / emoji).
    """
    codepoint = ord(char)

    if codepoint <= 0xFFFF:
        # BMP character — one key-down + key-up event
        events = _make_unicode_events(codepoint)
    else:
        # Astral plane — encode as UTF-16 surrogate pair
        encoded = char.encode("utf-16-le")
        high = int.from_bytes(encoded[0:2], "little")
        low  = int.from_bytes(encoded[2:4], "little")
        events = _make_unicode_events(high) + _make_unicode_events(low)

    buf = (INPUT * len(events))(*events)
    sent = _SendInput(len(events), buf, _INPUT_SIZE)
    return sent == len(events)


def send_key_vk(vk: int, flags: int = 0) -> bool:
    """Send a virtual-key event (key-down + key-up)."""
    events = [
        INPUT(type=INPUT_KEYBOARD,
              _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, dwFlags=flags))),
        INPUT(type=INPUT_KEYBOARD,
              _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, dwFlags=flags | KEYEVENTF_KEYUP))),
    ]
    buf = (INPUT * 2)(*events)
    sent = _SendInput(2, buf, _INPUT_SIZE)
    return sent == 2


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _make_unicode_events(scan_code: int) -> list[INPUT]:
    return [
        INPUT(type=INPUT_KEYBOARD,
              _u=_INPUT_UNION(ki=KEYBDINPUT(
                  wScan=scan_code, dwFlags=KEYEVENTF_UNICODE))),
        INPUT(type=INPUT_KEYBOARD,
              _u=_INPUT_UNION(ki=KEYBDINPUT(
                  wScan=scan_code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))),
    ]
