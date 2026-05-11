# macro.py — keystroke macro recorder and player.
#
# MacroRecorder captures keyboard events (key name + inter-key delay) using
# the pynput library.  MacroPlayer replays them through the typing engine's
# SendInput path.  Mouse clicks are recorded as {CLICK:x,y} tokens.
#
# If pynput is not installed the recorder degrades gracefully (is_available=False).

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

try:
    from pynput import keyboard as _pkb
    from pynput import mouse as _pmouse
    _PYNPUT_OK = True
except ImportError:
    _PYNPUT_OK = False

try:
    from engine.send_input import send_char, send_key_vk
    _SEND_OK = True
except Exception:  # noqa: BLE001
    _SEND_OK = False

try:
    import pyautogui as _pag
    _PAG_OK = True
except ImportError:
    _PAG_OK = False


# ──────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────

@dataclass
class MacroEvent:
    kind: str        # "key" | "click"
    value: str       # key name or "x,y"
    delay_ms: float  # milliseconds since previous event


@dataclass
class Macro:
    name: str
    events: list[MacroEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "events": [asdict(e) for e in self.events]}

    @staticmethod
    def from_dict(d: dict) -> "Macro":
        events = [MacroEvent(**e) for e in d.get("events", [])]
        return Macro(name=d.get("name", "Unnamed"), events=events)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_json(s: str) -> "Macro":
        return Macro.from_dict(json.loads(s))


# ──────────────────────────────────────────────────────────────────────
# Recorder
# ──────────────────────────────────────────────────────────────────────

class MacroRecorder:
    """Records keyboard + mouse click events into a Macro."""

    @property
    def is_available(self) -> bool:
        return _PYNPUT_OK

    def __init__(self) -> None:
        self._events: list[MacroEvent] = []
        self._last_time: float = 0.0
        self._kb_listener: object = None
        self._ms_listener: object = None
        self._recording = False
        self._stop_key: Optional[str] = None  # key that stops recording

    def start(self, stop_key: str = "f6") -> None:
        """Begin recording. Press *stop_key* to stop."""
        if not _PYNPUT_OK or self._recording:
            return
        self._events = []
        self._last_time = time.monotonic()
        self._recording = True
        self._stop_key = stop_key.lower()

        self._kb_listener = _pkb.Listener(
            on_press=self._on_key_press,
            suppress=False,
        )
        self._ms_listener = _pmouse.Listener(
            on_click=self._on_click,
        )
        self._kb_listener.start()   # type: ignore[union-attr]
        self._ms_listener.start()   # type: ignore[union-attr]

    def stop(self) -> Macro:
        """Stop recording and return the captured Macro."""
        self._recording = False
        if self._kb_listener:
            try:
                self._kb_listener.stop()   # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
        if self._ms_listener:
            try:
                self._ms_listener.stop()   # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
        return Macro(name="Recorded Macro", events=list(self._events))

    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _elapsed_ms(self) -> float:
        now = time.monotonic()
        ms = (now - self._last_time) * 1000.0
        self._last_time = now
        return ms

    def _on_key_press(self, key: object) -> Optional[bool]:
        if not self._recording:
            return False

        try:
            # pynput KeyCode
            name = key.char if hasattr(key, "char") and key.char else key.name  # type: ignore[union-attr]
        except AttributeError:
            name = str(key)

        if name and name.lower() == self._stop_key:
            self._recording = False
            return False  # stop listener

        self._events.append(MacroEvent(
            kind="key",
            value=str(name) if name else "",
            delay_ms=self._elapsed_ms(),
        ))
        return None  # continue

    def _on_click(self, x: int, y: int, button: object, pressed: bool) -> None:
        if not self._recording or not pressed:
            return
        self._events.append(MacroEvent(
            kind="click",
            value=f"{x},{y}",
            delay_ms=self._elapsed_ms(),
        ))


# ──────────────────────────────────────────────────────────────────────
# Player
# ──────────────────────────────────────────────────────────────────────

class MacroPlayer:
    """Replays a Macro. Runs in a daemon thread."""

    def __init__(self, root: object) -> None:
        self._root = root
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def play(
        self,
        macro: Macro,
        repeat: int = 1,
        on_done: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(macro, repeat, on_done, on_error),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(
        self,
        macro: Macro,
        repeat: int,
        on_done: Optional[Callable[[], None]],
        on_error: Optional[Callable[[str], None]],
    ) -> None:
        try:
            for _ in range(repeat if repeat > 0 else 10 ** 9):
                if self._stop.is_set():
                    break
                for event in macro.events:
                    if self._stop.is_set():
                        break
                    # Inter-event delay
                    delay_s = event.delay_ms / 1000.0
                    end = time.monotonic() + delay_s
                    while time.monotonic() < end:
                        if self._stop.is_set():
                            return
                        time.sleep(0.005)

                    if event.kind == "key":
                        self._play_key(event.value)
                    elif event.kind == "click" and _PAG_OK:
                        try:
                            x, y = event.value.split(",")
                            _pag.click(int(x), int(y))
                        except Exception:  # noqa: BLE001
                            pass

            if on_done and not self._stop.is_set():
                self._root.after(0, on_done)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            if on_error:
                self._root.after(0, on_error, str(exc))  # type: ignore[union-attr]

    def _play_key(self, name: str) -> None:
        if not name:
            return
        if _SEND_OK and len(name) == 1:
            send_char(name)
        elif _PAG_OK:
            try:
                _pag.press(name)
            except Exception:  # noqa: BLE001
                pass
