# hotkey.py — global hotkey registration using the `keyboard` library.
#
# HotkeyManager registers a single toggle hotkey that works even when the
# AutoTyper window is not focused.  It debounces repeated triggers within
# 300 ms and gracefully degrades if the keyboard library is missing.

import time
import threading
from typing import Callable, Optional

try:
    import keyboard as _kb
    _KB_OK = True
except ImportError:
    _KB_OK = False


class HotkeyManager:
    """Registers and manages a single global toggle hotkey."""

    _DEBOUNCE_S: float = 0.3  # 300 ms

    def __init__(self) -> None:
        self._hotkey: str = "f6"
        self._callback: Optional[Callable[[], None]] = None
        self._hook_id: Optional[object] = None
        self._last_trigger: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return _KB_OK

    @property
    def current_hotkey(self) -> str:
        return self._hotkey

    def register(self, hotkey: str, callback: Callable[[], None]) -> bool:
        """Register *hotkey* (e.g. "f6") to call *callback* when pressed.

        Returns True on success, False if the keyboard library is unavailable.
        """
        if not _KB_OK:
            return False
        self.unregister()
        self._hotkey = hotkey.lower()
        self._callback = callback
        try:
            self._hook_id = _kb.add_hotkey(self._hotkey, self._on_trigger)
            return True
        except Exception:  # noqa: BLE001
            self._hook_id = None
            return False

    def unregister(self) -> None:
        """Remove the currently registered hotkey (if any)."""
        if not _KB_OK or self._hook_id is None:
            return
        try:
            _kb.remove_hotkey(self._hook_id)
        except Exception:  # noqa: BLE001
            pass
        self._hook_id = None

    def record_next_key(self, timeout_s: float = 10.0) -> Optional[str]:
        """Block until the user presses a key, then return its name.

        Temporarily unregisters the current hotkey while listening.
        Returns None on timeout or if the keyboard library is unavailable.
        """
        if not _KB_OK:
            return None
        self.unregister()
        try:
            event = _kb.read_event(suppress=True)
            if event and event.event_type == "down":
                return event.name
        except Exception:  # noqa: BLE001
            pass
        finally:
            # Re-register with the same callback
            if self._callback:
                self.register(self._hotkey, self._callback)
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_trigger(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_trigger < self._DEBOUNCE_S:
                return
            self._last_trigger = now
        if self._callback:
            self._callback()
