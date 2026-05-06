# store.py — JSON-backed persistence for profiles and settings.
#
# Files live in %APPDATA%/AutoTyper/ (created on first access).
# ProfileStore and SettingsStore expose simple load/save/CRUD operations
# with no external dependencies beyond the standard library.

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _appdata_dir() -> Path:
    """Return (and create) %APPDATA%/AutoTyper/."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    d = base / "AutoTyper"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ──────────────────────────────────────────────────────────────────────
# Default values
# ──────────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS: dict[str, Any] = {
    "hotkey": "f6",
    "default_delay_ms": 80,
    "default_jitter_ms": 15,
    "default_start_delay_s": 3,
    "minimize_on_start": False,
    "play_sounds": False,
    "launch_at_startup": False,
}


def _new_profile(
    name: str,
    text: str,
    delay_ms: int,
    jitter_ms: int,
    start_delay_s: int,
    repeat_count: int,
    paste_mode: bool,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "text": text,
        "delay_ms": delay_ms,
        "jitter_ms": jitter_ms,
        "start_delay_s": start_delay_s,
        "repeat_count": repeat_count,
        "paste_mode": paste_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# Settings Store
# ──────────────────────────────────────────────────────────────────────

class SettingsStore:
    def __init__(self) -> None:
        self._path = _appdata_dir() / "settings.json"
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:  # noqa: BLE001
                self._data = {}
        # Fill in any keys that are missing (first run or schema upgrade)
        for k, v in DEFAULT_SETTINGS.items():
            self._data.setdefault(k, v)

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def all(self) -> dict[str, Any]:
        return dict(self._data)


# ──────────────────────────────────────────────────────────────────────
# Profile Store
# ──────────────────────────────────────────────────────────────────────

class ProfileStore:
    def __init__(self) -> None:
        self._path = _appdata_dir() / "profiles.json"
        self._profiles: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._profiles = json.load(f)
            except Exception:  # noqa: BLE001
                self._profiles = []

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._profiles, f, indent=2)

    def all(self) -> list[dict[str, Any]]:
        return list(self._profiles)

    def add(
        self,
        name: str,
        text: str,
        delay_ms: int,
        jitter_ms: int,
        start_delay_s: int,
        repeat_count: int,
        paste_mode: bool,
    ) -> dict[str, Any]:
        profile = _new_profile(
            name, text, delay_ms, jitter_ms,
            start_delay_s, repeat_count, paste_mode,
        )
        self._profiles.append(profile)
        self._save()
        return profile

    def delete(self, profile_id: str) -> bool:
        before = len(self._profiles)
        self._profiles = [p for p in self._profiles if p["id"] != profile_id]
        if len(self._profiles) < before:
            self._save()
            return True
        return False

    def get(self, profile_id: str) -> Optional[dict[str, Any]]:
        for p in self._profiles:
            if p["id"] == profile_id:
                return p
        return None

    # ── Import / Export ───────────────────────────────────────────────

    def export_to_file(self, profile_id: str, file_path: str) -> bool:
        profile = self.get(profile_id)
        if profile is None:
            return False
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return True

    def import_from_file(self, file_path: str) -> Optional[dict[str, Any]]:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        # Validate required keys
        required = {"name", "text", "delay_ms", "jitter_ms",
                    "start_delay_s", "repeat_count", "paste_mode"}
        if not required.issubset(data.keys()):
            raise ValueError("Invalid profile file — missing required fields.")
        profile = _new_profile(
            name=data["name"],
            text=data["text"],
            delay_ms=int(data["delay_ms"]),
            jitter_ms=int(data["jitter_ms"]),
            start_delay_s=int(data["start_delay_s"]),
            repeat_count=int(data["repeat_count"]),
            paste_mode=bool(data["paste_mode"]),
        )
        self._profiles.append(profile)
        self._save()
        return profile
