# updater.py — checks GitHub releases API for a newer version of AutoTyper.
#
# Runs the check in a background thread so it never blocks the UI.
# Compares semantic versions (major.minor.patch).
# On a new version found, fires on_update_available(latest_version, release_url).

import json
import threading
import urllib.request
from typing import Callable, Optional

CURRENT_VERSION: str = "2.0.0"
_RELEASES_API: str = "https://api.github.com/repos/u-pawan/auto_typer/releases/latest"
_TIMEOUT_S: float = 8.0


def _parse_version(v: str) -> tuple[int, ...]:
    """Convert "1.2.3" → (1, 2, 3). Non-numeric parts become 0."""
    clean = v.lstrip("vV").strip()
    parts = []
    for p in clean.split(".")[:3]:
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_update(
    on_update_available: Callable[[str, str], None],
    on_up_to_date: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """Spawn a daemon thread to check for a newer release on GitHub.

    Callbacks are invoked from the background thread — callers must use
    root.after(0, ...) if they need to touch tkinter from these callbacks.
    """
    def _worker() -> None:
        try:
            req = urllib.request.Request(
                _RELEASES_API,
                headers={"User-Agent": f"AutoTyper/{CURRENT_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode())

            tag: str = data.get("tag_name", "")
            url: str = data.get("html_url", "")

            if not tag:
                if on_error:
                    on_error("No release tag found.")
                return

            latest = _parse_version(tag)
            current = _parse_version(CURRENT_VERSION)

            if latest > current:
                on_update_available(tag.lstrip("vV"), url)
            else:
                if on_up_to_date:
                    on_up_to_date()

        except Exception as exc:  # noqa: BLE001
            if on_error:
                on_error(str(exc))

    threading.Thread(target=_worker, daemon=True).start()
