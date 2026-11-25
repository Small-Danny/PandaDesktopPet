"""Versioned settings and runtime persistence, with recoverable file replacement.

Each file is atomic; save() is NOT a transaction across both files. Callers must
serialize access (one writer) and choose a writable base_dir outside bundled assets.
load() may repair corrupt files or migrate the legacy mixed settings.json.
I/O errors propagate; recovery/default decisions are logged and in recovery_events.
"""
from __future__ import annotations

import copy
import json
import logging
import math
import os
from pathlib import Path
import tempfile
import uuid

LOGGER = logging.getLogger(__name__)
DEFAULT_SETTINGS = {
    "mode": "auto", "manual_character": "chorong", "sedentary_interval_min": 60,
    "notify_relay": True, "standby_lock_workstation": True,
    "lang": "zh_TW", "standby_hotkey": "Ctrl+Shift+S",
    "standby_clock_position": "top_right",
    "onboarding_prompted": False,
    "pet_size": "medium",
    "text_size": "medium",
    "mouse_cursor": "paw_smooth",
    "fortune_reduced_motion": False,
    "notify_bubble_style": "banner",
}
VALID_PET_SIZES = frozenset({"small", "medium", "large"})
VALID_TEXT_SIZES = frozenset({"small", "medium", "large"})
VALID_STANDBY_CLOCK_POSITIONS = frozenset({"top_right", "top_left", "hidden"})
VALID_MOUSE_CURSORS = frozenset({"system", "paw_smooth", "mitten_smooth", "paw_pixel", "mitten_pixel"})
# Windows notification relay bubble: banner (default) / sticky note / standard (highlight off).
VALID_NOTIFY_BUBBLE_STYLES = frozenset({"banner", "sticky", "standard"})
DEFAULT_RUNTIME = {
    "fortune_salt": "",
    "fortune_daily": None,
    "cheer_passion": 0,
    "feed_count": 0,
    "companion_start_time": None,
    "total_companion_seconds": 0,
    "festival_welcome_seen": {},
}
RUNTIME_KEYS = frozenset(DEFAULT_RUNTIME)


class UnsupportedSchemaError(RuntimeError):
    """A newer schema must not be silently replaced with defaults."""


class PersistenceService:
    """load() returns (settings, runtime) as plain dicts; save() accepts those dicts.

    Disk format for both files is {"schema_version": 1, "data": {...}}.
    settings.json.bak/runtime.json.bak contain the previous valid file bytes.
    Corruption evidence is kept as <filename>.<uuid>.corrupt before any repair.
    File fsync precedes same-directory os.replace; this does not promise directory
    metadata durability through power loss on every Windows/filesystem combination.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.recovery_events: list[str] = []

    def _event(self, message: str) -> None:
        self.recovery_events.append(message)
        LOGGER.warning(message)

    @staticmethod
    def _validate(data: dict, kind: str, *, legacy: bool = False) -> None:
        if not isinstance(data, dict) or any(not isinstance(k, str) for k in data):
            raise ValueError(f"{kind}: expected a JSON object with string keys")
        # Reject NaN/Infinity and non-JSON objects even for extension fields.
        json.dumps(data, allow_nan=False)
        if kind == "settings":
            if not legacy and RUNTIME_KEYS.intersection(data):
                raise ValueError("runtime fields must be stored in runtime.json")
            for key, default in DEFAULT_SETTINGS.items():
                if key in data and type(data[key]) is not type(default):
                    raise ValueError(f"invalid type for {key}")
            if "mode" in data and data["mode"] not in ("auto", "manual"):
                raise ValueError("mode must be auto or manual")
            if "sedentary_interval_min" in data and data["sedentary_interval_min"] < 0:
                raise ValueError("sedentary_interval_min cannot be negative")
            if "pet_size" in data and data["pet_size"] not in VALID_PET_SIZES:
                raise ValueError("pet_size must be small, medium, or large")
            if "text_size" in data and data["text_size"] not in VALID_TEXT_SIZES:
                raise ValueError("text_size must be small, medium, or large")
            if "standby_clock_position" in data and data["standby_clock_position"] not in VALID_STANDBY_CLOCK_POSITIONS:
                raise ValueError(f"invalid standby_clock_position: {data['standby_clock_position']}")
            if "mouse_cursor" in data and data["mouse_cursor"] not in VALID_MOUSE_CURSORS:
                raise ValueError(f"invalid mouse_cursor: {data['mouse_cursor']}")
            if "notify_bubble_style" in data and data["notify_bubble_style"] not in VALID_NOTIFY_BUBBLE_STYLES:
                raise ValueError(f"invalid notify_bubble_style: {data['notify_bubble_style']}")
        elif DEFAULT_SETTINGS.keys() & data.keys():
            raise ValueError("settings fields must be stored in settings.json")
        if "festival_welcome_seen" in data:
            seen = data["festival_welcome_seen"]
            if not isinstance(seen, dict) or any(not isinstance(k, str) or type(v) is not bool for k, v in seen.items()):
                raise ValueError("festival_welcome_seen must be a map of string to bool")
        for key in ("cheer_passion", "feed_count", "total_companion_seconds"):
            if key in data and (type(data[key]) is not int or data[key] < 0):
                raise ValueError(f"{key} must be a nonnegative integer")
        if "companion_start_time" in data and data["companion_start_time"] is not None:
            value = data["companion_start_time"]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("companion_start_time must be a nonnegative timestamp or null")

    def _decode(self, raw: bytes, kind: str) -> tuple[dict, bool]:
        doc = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(doc, dict):
            raise ValueError("expected a JSON object")
        legacy = "schema_version" not in doc and kind == "settings"
        if not legacy:
            if "schema_version" not in doc:
                raise ValueError("missing schema_version")
            if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
                raise UnsupportedSchemaError(f"Unsupported schema in {kind}: {doc['schema_version']!r}")
            if set(doc) != {"schema_version", "data"}:
                raise ValueError("invalid envelope fields")
            doc = doc["data"]
        self._validate(doc, kind, legacy=legacy)
        return doc, legacy

    @staticmethod
    def _encode(data: dict) -> bytes:
        return (json.dumps({"schema_version": 1, "data": data}, ensure_ascii=False,
                           allow_nan=False, indent=2) + "\n").encode("utf-8")

    def _atomic_write(self, path: Path, raw: bytes) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=self.base_dir)
        temp = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _preserve_corrupt(self, path: Path, raw: bytes) -> None:
        evidence = path.with_name(f"{path.name}.{uuid.uuid4().hex}.corrupt")
        with evidence.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self._event(f"Preserved corrupt {path.name} as {evidence.name}")

    def _load_file(self, kind: str) -> tuple[dict, bool, bool]:
        path = self.base_dir / f"{kind}.json"
        corrupt = False
        for candidate in (path, path.with_suffix(".json.bak")):
            try:
                raw = candidate.read_bytes()
            except FileNotFoundError:
                continue
            try:
                data, legacy = self._decode(raw, kind)
            except (ValueError, UnicodeError) as error:
                self._preserve_corrupt(candidate, raw)
                self._event(f"Invalid {candidate.name}: {error}")
                corrupt = True
                continue
            if candidate != path:
                # Never rotate a corrupt primary over the known-good backup.
                self._atomic_write(path, raw)
                self._event(f"Recovered {path.name} from {candidate.name}")
            return data, legacy, True
        defaults = copy.deepcopy(DEFAULT_SETTINGS if kind == "settings" else DEFAULT_RUNTIME)
        if corrupt:
            self._atomic_write(path, self._encode(defaults))
            self._event(f"Restored defaults for {path.name}; no valid backup")
        return defaults, False, False

    def load(self) -> tuple[dict, dict]:
        """Read, recover, and idempotently split legacy settings if encountered."""
        self.recovery_events.clear()
        settings, legacy, _ = self._load_file("settings")
        runtime, _, runtime_exists = self._load_file("runtime")
        if legacy:
            migrated_runtime = {key: settings.pop(key) for key in RUNTIME_KEYS if key in settings}
            if not runtime_exists:
                runtime.update(migrated_runtime)
            # Runtime first: interruption leaves legacy settings available for retry;
            # an already-written runtime always takes precedence over legacy values.
            self.save(settings, runtime)
            self._event("Migrated legacy settings.json to separate versioned files")
        return {**copy.deepcopy(DEFAULT_SETTINGS), **settings}, {**copy.deepcopy(DEFAULT_RUNTIME), **runtime}

    def _save_file(self, kind: str, encoded: bytes) -> None:
        path = self.base_dir / f"{kind}.json"
        try:
            previous = path.read_bytes()
        except FileNotFoundError:
            previous = None
        if previous == encoded:
            return
        if previous is not None:
            try:
                self._decode(previous, kind)
            except (ValueError, UnicodeError):
                self._preserve_corrupt(path, previous)
            else:
                self._atomic_write(path.with_suffix(".json.bak"), previous)
        self._atomic_write(path, encoded)

    def save(self, settings: dict, runtime: dict) -> None:
        """Validate both before writing; failures propagate, and files commit separately."""
        self._validate(settings, "settings")
        self._validate(runtime, "runtime")
        settings_bytes, runtime_bytes = self._encode(settings), self._encode(runtime)
        self._save_file("runtime", runtime_bytes)
        self._save_file("settings", settings_bytes)
