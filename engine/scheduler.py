# scheduler.py — scheduled typing: start a typing run at a specific clock time.
#
# TypingScheduler watches a target datetime in a background daemon thread and
# fires on_trigger() when the clock reaches it.  It can be cancelled at any time.
# The caller is responsible for hooking on_trigger to root.after() if needed.

import threading
import time
from datetime import datetime
from typing import Callable, Optional


class TypingScheduler:
    """Fire a callback at a specific wall-clock time."""

    _POLL_INTERVAL_S: float = 0.5

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(
        self,
        target: datetime,
        on_trigger: Callable[[], None],
        on_cancelled: Optional[Callable[[], None]] = None,
    ) -> None:
        """Start watching for *target*. Fires *on_trigger* when reached."""
        self.cancel()
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._watch,
            args=(target, on_trigger, on_cancelled),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Cancel a pending scheduled run."""
        self._cancel.set()
        self._thread = None

    def is_scheduled(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _watch(
        self,
        target: datetime,
        on_trigger: Callable[[], None],
        on_cancelled: Optional[Callable[[], None]],
    ) -> None:
        while not self._cancel.is_set():
            remaining = (target - datetime.now()).total_seconds()
            if remaining <= 0:
                if not self._cancel.is_set():
                    on_trigger()
                return
            # Sleep in short chunks so cancel is responsive
            time.sleep(min(self._POLL_INTERVAL_S, remaining))

        if on_cancelled:
            on_cancelled()
