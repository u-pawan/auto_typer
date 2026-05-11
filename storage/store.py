# store.py — JSON-backed persistence for profiles, settings, and scripts (v2).
#
# v2 additions:
#   • Portable mode: if portable.flag exists beside the exe, store data there
#   • Profile encryption: Fernet symmetric encryption with PBKDF2 key derivation
#   • Integrity check: SHA-256 hash of settings content stored in a sidecar file
#   • ProfileStore.reorder(): persist drag-to-reorder changes
#   • ProfileStore.set_profile_hotkey(): save per-profile hotkey
#   • ScriptStore: save/load multi-step scripts
#   • Graceful degradation if cryptography library is not installed

import json
import os
import sys
import uuid
import hashlib
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


# ──────────────────────────────────────────────────────────────────────
# Data directory resolution (portable vs. %APPDATA%)
# ──────────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    """Return the directory where data files are stored.

    Portable mode: if a 'portable.flag' file sits next to the running
    executable, store data in that same directory.
    Otherwise, use %APPDATA%/AutoTyper/ (created if absent).
    """
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "portable.flag").exists():
        d = exe_dir / "AutoTyper_data"
    else:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        d = base / "AutoTyper"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ──────────────────────────────────────────────────────────────────────
# Defaults
# ──────────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS: dict[str, Any] = {
    "hotkey":               "f6",
    "default_delay_ms":     80,
    "default_jitter_ms":    15,
    "default_start_delay_s": 3,
    "default_font_size":    11,
    "minimize_on_start":    False,
    "play_sounds":          False,
    "launch_at_startup":    False,
    "dark_mode":            False,
    "auto_lock":            False,
    "auto_lock_minutes":    5,
    "encrypt_profiles":     False,
}


def _new_profile(
    name: str, text: str, delay_ms: int, jitter_ms: int,
    start_delay_s: int, repeat_count: int, paste_mode: bool,
    word_by_word: bool = False, expand_variables: bool = True,
    hotkey: str = "",
) -> dict[str, Any]:
    return {
        "id":              str(uuid.uuid4()),
        "name":            name,
        "text":            text,
        "delay_ms":        delay_ms,
        "jitter_ms":       jitter_ms,
        "start_delay_s":   start_delay_s,
        "repeat_count":    repeat_count,
        "paste_mode":      paste_mode,
        "word_by_word":    word_by_word,
        "expand_variables": expand_variables,
        "hotkey":          hotkey,
        "created_at":      datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# Encryption helpers
# ──────────────────────────────────────────────────────────────────────

_SALT = b"AutoTyper_v2_salt_2026"  # fixed salt (profiles are not high-security)


def _derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _encrypt(data: str, password: str) -> str:
    key = _derive_key(password)
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()


def _decrypt(token: str, password: str) -> str:
    key = _derive_key(password)
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()


# ──────────────────────────────────────────────────────────────────────
# Settings Store
# ──────────────────────────────────────────────────────────────────────

class SettingsStore:
    def __init__(self) -> None:
        self._path = _data_dir() / "settings.json"
        self._hash_path = _data_dir() / "settings.hash"
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                raw = self._path.read_text(encoding="utf-8")
                # Integrity check
                if self._hash_path.exists():
                    stored_hash = self._hash_path.read_text().strip()
                    actual_hash = hashlib.sha256(raw.encode()).hexdigest()
                    if stored_hash != actual_hash:
                        # File may have been tampered; reset to defaults
                        self._data = {}
                    else:
                        self._data = json.loads(raw)
                else:
                    self._data = json.loads(raw)
            except Exception:  # noqa: BLE001
                self._data = {}
        for k, v in DEFAULT_SETTINGS.items():
            self._data.setdefault(k, v)

    def save(self) -> None:
        raw = json.dumps(self._data, indent=2)
        self._path.write_text(raw, encoding="utf-8")
        # Write integrity hash
        self._hash_path.write_text(
            hashlib.sha256(raw.encode()).hexdigest(), encoding="utf-8"
        )

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
        self._path = _data_dir() / "profiles.json"
        self._profiles: list[dict[str, Any]] = []
        self._password: Optional[str] = None
        self.load()

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def set_encryption_password(self, password: str) -> None:
        """Enable encryption for all future saves."""
        if not _CRYPTO_OK:
            return
        self._password = password if password else None
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("encrypted"):
                # Encrypted blob — can't decrypt without password; defer
                self._profiles = []
            elif isinstance(data, list):
                self._profiles = data
            else:
                self._profiles = []
        except Exception:  # noqa: BLE001
            self._profiles = []

    def unlock(self, password: str) -> bool:
        """Decrypt profiles with the given password. Returns True on success."""
        if not _CRYPTO_OK or not self._path.exists():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not (isinstance(data, dict) and data.get("encrypted")):
                return True  # not encrypted
            decrypted = _decrypt(data["blob"], password)
            self._profiles = json.loads(decrypted)
            self._password = password
            return True
        except Exception:  # noqa: BLE001
            return False

    def _save(self) -> None:
        raw = json.dumps(self._profiles, indent=2)
        if self._password and _CRYPTO_OK:
            blob = _encrypt(raw, self._password)
            payload = json.dumps({"encrypted": True, "blob": blob})
            self._path.write_text(payload, encoding="utf-8")
        else:
            self._path.write_text(raw, encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def all(self) -> list[dict[str, Any]]:
        return list(self._profiles)

    def add(
        self, name: str, text: str, delay_ms: int, jitter_ms: int,
        start_delay_s: int, repeat_count: int, paste_mode: bool,
        word_by_word: bool = False, expand_variables: bool = True,
        hotkey: str = "",
    ) -> dict[str, Any]:
        p = _new_profile(name, text, delay_ms, jitter_ms, start_delay_s,
                          repeat_count, paste_mode, word_by_word,
                          expand_variables, hotkey)
        self._profiles.append(p)
        self._save()
        return p

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

    def reorder(self, new_order: list[dict[str, Any]]) -> None:
        """Persist a new ordering (from drag-to-reorder)."""
        self._profiles = new_order
        self._save()

    def set_profile_hotkey(self, profile_id: str, hotkey: str) -> bool:
        for p in self._profiles:
            if p["id"] == profile_id:
                p["hotkey"] = hotkey
                self._save()
                return True
        return False

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_to_file(self, profile_id: str, file_path: str) -> bool:
        p = self.get(profile_id)
        if p is None:
            return False
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2)
        return True

    def import_from_file(self, file_path: str) -> Optional[dict[str, Any]]:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        required = {"name", "text", "delay_ms", "jitter_ms",
                    "start_delay_s", "repeat_count", "paste_mode"}
        if not required.issubset(data.keys()):
            raise ValueError("Invalid profile file — missing required fields.")
        p = _new_profile(
            name=data["name"], text=data["text"],
            delay_ms=int(data["delay_ms"]), jitter_ms=int(data["jitter_ms"]),
            start_delay_s=int(data["start_delay_s"]),
            repeat_count=int(data["repeat_count"]),
            paste_mode=bool(data["paste_mode"]),
            word_by_word=bool(data.get("word_by_word", False)),
            expand_variables=bool(data.get("expand_variables", True)),
            hotkey=data.get("hotkey", ""),
        )
        self._profiles.append(p)
        self._save()
        return p


# ──────────────────────────────────────────────────────────────────────
# Script Store  (multi-step scripts)
# ──────────────────────────────────────────────────────────────────────

class ScriptStore:
    """Persists named multi-step scripts."""

    def __init__(self) -> None:
        self._path = _data_dir() / "scripts.json"
        self._scripts: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                self._scripts = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self._scripts = []

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._scripts, indent=2), encoding="utf-8")

    def all(self) -> list[dict[str, Any]]:
        return list(self._scripts)

    def add(self, name: str, steps: list[dict]) -> None:
        self._scripts.append({"id": str(uuid.uuid4()), "name": name, "steps": steps})
        self._save()

    def delete(self, script_id: str) -> None:
        self._scripts = [s for s in self._scripts if s["id"] != script_id]
        self._save()
