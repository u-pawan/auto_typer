# typer.py — core typing loop; runs in a daemon thread, never touches the UI directly.
#
# The caller provides:
#   - text, options (delay, jitter, repeat_count, paste_mode, start_delay_s)
#   - stop_event (threading.Event) — set this to abort mid-type
#   - callbacks fired via root.after() so tkinter stays thread-safe:
#       on_countdown(seconds_remaining: int)
#       on_start(total_chars: int, repeat_count: int)
#       on_progress(chars_done: int, pass_num: int)
#       on_done()
#       on_stop()
#       on_error(message: str)

import time
import random
import threading
import pyperclip
from typing import Callable, Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except ImportError:
    _PYAUTOGUI_OK = False

from engine.special_keys import parse_text, Action


class TypingOptions:
    """All parameters that control a single typing run."""

    def __init__(
        self,
        delay_ms: int = 80,
        jitter_ms: int = 15,
        start_delay_s: int = 3,
        repeat_count: int = 1,   # 0 = infinite
        paste_mode: bool = False,
    ) -> None:
        self.delay_ms = delay_ms
        self.jitter_ms = jitter_ms
        self.start_delay_s = start_delay_s
        self.repeat_count = repeat_count
        self.paste_mode = paste_mode


class TyperEngine:
    """Manages the background typing thread."""

    def __init__(self, root: object) -> None:
        # root is the tk.Tk instance — used only for root.after() scheduling
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
        """Kick off a new typing run in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return  # already running

        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(text, options, on_countdown, on_start,
                  on_progress, on_done, on_stop, on_error),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the running thread to stop after the current character."""
        self.stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule(self, fn: Callable, *args) -> None:
        """Fire *fn* on the UI thread via root.after(0, ...)."""
        self._root.after(0, fn, *args)  # type: ignore[attr-defined]

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
        if not _PYAUTOGUI_OK:
            self._schedule(on_error, "pyautogui is not installed.")
            return

        try:
            # ── Countdown ────────────────────────────────────────────
            for remaining in range(opts.start_delay_s, 0, -1):
                if self.stop_event.is_set():
                    self._schedule(on_stop)
                    return
                self._schedule(on_countdown, remaining)
                time.sleep(1.0)

            if self.stop_event.is_set():
                self._schedule(on_stop)
                return

            actions = parse_text(text)
            total_chars = len(actions)
            repeat_count = opts.repeat_count  # 0 = infinite
            self._schedule(on_start, total_chars, repeat_count)

            pass_num = 0
            while True:
                pass_num += 1
                if repeat_count != 0 and pass_num > repeat_count:
                    break
                if self.stop_event.is_set():
                    self._schedule(on_stop)
                    return

                if opts.paste_mode:
                    self._do_paste(text, opts, on_progress, on_stop, pass_num)
                    if self.stop_event.is_set():
                        self._schedule(on_stop)
                        return
                else:
                    self._do_type(actions, opts, on_progress, on_stop, pass_num)
                    if self.stop_event.is_set():
                        self._schedule(on_stop)
                        return

            self._schedule(on_done)

        except pyautogui.FailSafeException:
            self._schedule(on_error, "Failsafe triggered (mouse moved to corner). Typing stopped.")
        except Exception as exc:  # noqa: BLE001
            self._schedule(on_error, f"Typing error: {exc}")

    def _do_paste(
        self,
        text: str,
        opts: TypingOptions,
        on_progress: Callable[[int, int], None],
        on_stop: Callable[[], None],
        pass_num: int,
    ) -> None:
        """Write text to clipboard and send Ctrl+V."""
        pyperclip.copy(text)
        if self.stop_event.is_set():
            return
        pyautogui.hotkey("ctrl", "v")
        self._schedule(on_progress, 1, pass_num)
        time.sleep(opts.delay_ms / 1000.0)

    def _do_type(
        self,
        actions: list[Action],
        opts: TypingOptions,
        on_progress: Callable[[int, int], None],
        on_stop: Callable[[], None],
        pass_num: int,
    ) -> None:
        """Type character by character, checking stop_event each time."""
        delay_s = opts.delay_ms / 1000.0
        jitter_s = opts.jitter_ms / 1000.0

        for idx, (kind, value) in enumerate(actions):
            if self.stop_event.is_set():
                return

            try:
                if kind == "key":
                    pyautogui.press(value)
                else:
                    # typewrite handles Unicode poorly for non-ASCII; use write
                    pyautogui.write(value, interval=0)
            except Exception as exc:  # noqa: BLE001
                # Re-raise so _run's outer handler catches it
                raise RuntimeError(f"Failed to type character {value!r}: {exc}") from exc

            self._schedule(on_progress, idx + 1, pass_num)

            # Compute per-character delay with jitter
            jitter = random.uniform(-jitter_s, jitter_s) if jitter_s > 0 else 0.0
            sleep_time = max(0.001, delay_s + jitter)

            # Sleep in small chunks so stop_event is checked frequently
            end = time.monotonic() + sleep_time
            while time.monotonic() < end:
                if self.stop_event.is_set():
                    return
                time.sleep(0.005)
