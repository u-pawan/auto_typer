# typer.py — core typing loop; runs in a daemon thread, never touches the UI.
#
# v2 improvements over v1:
#   • Full Unicode via Windows SendInput (engine/send_input.py)
#   • Per-keystroke smart retry (up to 2 attempts on injection failure)
#   • Word-by-word mode: inter-word delays differ from inter-character delays
#   • Anti-detection jitter: character delay ≠ word delay, gaussian distribution
#   • Variable expansion via engine/variables.py before typing begins
#   • Paste mode now falls back to pyautogui if pyperclip is unavailable
#   • All timing slept in 5 ms chunks so stop_event is always responsive

import time
import random
import threading
from typing import Callable, Optional

try:
    import pyautogui as _pag
    _pag.FAILSAFE = True
    _pag.PAUSE = 0
    _PAG_OK = True
except ImportError:
    _PAG_OK = False

try:
    import pyperclip as _clip
    _CLIP_OK = True
except ImportError:
    _CLIP_OK = False

from engine.special_keys import parse_text, Action
from engine.send_input import send_char as _send_char
from engine.variables import expand, reset_counter


# ──────────────────────────────────────────────────────────────────────
# Options
# ──────────────────────────────────────────────────────────────────────

class TypingOptions:
    """All parameters that control a single typing run."""

    def __init__(
        self,
        delay_ms: int = 80,
        jitter_ms: int = 15,
        start_delay_s: int = 3,
        repeat_count: int = 1,    # 0 = infinite
        paste_mode: bool = False,
        word_by_word: bool = False,
        word_delay_ms: int = 200,  # extra pause between words in word-by-word mode
        expand_variables: bool = True,
        max_retries: int = 2,
    ) -> None:
        self.delay_ms = delay_ms
        self.jitter_ms = jitter_ms
        self.start_delay_s = start_delay_s
        self.repeat_count = repeat_count
        self.paste_mode = paste_mode
        self.word_by_word = word_by_word
        self.word_delay_ms = word_delay_ms
        self.expand_variables = expand_variables
        self.max_retries = max_retries


# ──────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────

class TyperEngine:
    """Manages the background typing thread."""

    def __init__(self, root: object) -> None:
        self._root = root
        self._thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        text: str,
        options: TypingOptions,
        on_countdown: Callable[[int], None],
        on_start: Callable[[int, int], None],
        on_progress: Callable[[int, int], None],
        on_done: Callable[[], None],
        on_stop: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(text, options, on_countdown, on_start,
                  on_progress, on_done, on_stop, on_error),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule(self, fn: Callable, *args: object) -> None:
        self._root.after(0, fn, *args)  # type: ignore[union-attr]

    def _run(
        self,
        text: str,
        opts: TypingOptions,
        on_countdown: Callable[[int], None],
        on_start: Callable[[int, int], None],
        on_progress: Callable[[int, int], None],
        on_done: Callable[[], None],
        on_stop: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        if not _PAG_OK:
            self._schedule(on_error, "pyautogui is not installed.")
            return

        try:
            # Expand variables once before the loop
            if opts.expand_variables:
                reset_counter()
                text = expand(text)

            # ── Countdown ────────────────────────────────────────────
            for remaining in range(opts.start_delay_s, 0, -1):
                if self.stop_event.is_set():
                    self._schedule(on_stop)
                    return
                self._schedule(on_countdown, remaining)
                self._interruptible_sleep(1.0)

            if self.stop_event.is_set():
                self._schedule(on_stop)
                return

            actions = parse_text(text)
            total = len(actions)
            repeat = opts.repeat_count
            self._schedule(on_start, total, repeat)

            pass_num = 0
            while True:
                pass_num += 1
                if repeat != 0 and pass_num > repeat:
                    break
                if self.stop_event.is_set():
                    self._schedule(on_stop)
                    return

                if opts.paste_mode:
                    self._do_paste(text, opts, on_progress, pass_num)
                else:
                    self._do_type(actions, opts, on_progress, pass_num)

                if self.stop_event.is_set():
                    self._schedule(on_stop)
                    return

            self._schedule(on_done)

        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name == "FailSafeException":
                self._schedule(on_error, "Failsafe triggered — mouse moved to corner.")
            else:
                self._schedule(on_error, f"Typing error: {exc}")

    # ------------------------------------------------------------------
    # Paste mode
    # ------------------------------------------------------------------

    def _do_paste(
        self,
        text: str,
        opts: TypingOptions,
        on_progress: Callable[[int, int], None],
        pass_num: int,
    ) -> None:
        if _CLIP_OK:
            _clip.copy(text)
            if not self.stop_event.is_set():
                _pag.hotkey("ctrl", "v")
        else:
            # Fallback: use pyautogui typewrite (ASCII only)
            _pag.typewrite(text, interval=opts.delay_ms / 1000.0)
        self._schedule(on_progress, 1, pass_num)

    # ------------------------------------------------------------------
    # Character-by-character typing
    # ------------------------------------------------------------------

    def _do_type(
        self,
        actions: list[Action],
        opts: TypingOptions,
        on_progress: Callable[[int, int], None],
        pass_num: int,
    ) -> None:
        delay_s   = opts.delay_ms / 1000.0
        jitter_s  = opts.jitter_ms / 1000.0
        word_s    = opts.word_delay_ms / 1000.0

        for idx, (kind, value) in enumerate(actions):
            if self.stop_event.is_set():
                return

            self._inject(kind, value, opts.max_retries)
            self._schedule(on_progress, idx + 1, pass_num)

            # Anti-detection: word boundary gets a different (longer) delay
            is_space = (kind == "char" and value == " ") or (kind == "key" and value in ("enter", "tab"))
            if opts.word_by_word and is_space:
                base_delay = word_s
            else:
                base_delay = delay_s

            # Gaussian jitter feels more natural than uniform
            if jitter_s > 0:
                jitter = random.gauss(0, jitter_s / 2)
                jitter = max(-jitter_s, min(jitter_s, jitter))
            else:
                jitter = 0.0

            self._interruptible_sleep(max(0.001, base_delay + jitter))

    # ------------------------------------------------------------------
    # Injection with retry
    # ------------------------------------------------------------------

    def _inject(self, kind: str, value: str, max_retries: int) -> None:
        for attempt in range(max(1, max_retries)):
            try:
                if kind == "key":
                    _pag.press(value)
                else:
                    # Use SendInput for full Unicode support
                    _send_char(value)
                return  # success
            except Exception:  # noqa: BLE001
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.02)  # brief pause before retry

    # ------------------------------------------------------------------
    # Interruptible sleep
    # ------------------------------------------------------------------

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep for *seconds* but wake early if stop_event is set."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.stop_event.is_set():
                return
            time.sleep(0.005)
