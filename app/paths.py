"""paths.py — Unified path resolution for development and frozen PyInstaller EXE."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """Returns the writable directory where settings, logs, and user data reside.
    
    In development: the PandaDesktopPet project root.
    In frozen EXE: the directory where the .exe executable is located.
    """
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(os.path.abspath(sys.executable)))
    # app/paths.py -> parent of app is project root
    return Path(__file__).resolve().parents[1]


def is_developer_mode(settings=None) -> bool:
    """True when preview / debug menus should be shown.

    Running from source is developer mode; the packaged EXE is the end-user build and
    hides them. PANDA_DEV=1/0 wins, then a boolean ``developer_mode`` in settings.json.
    """
    override = os.environ.get("PANDA_DEV", "").strip().lower()
    if override in ("1", "true", "yes", "on"):
        return True
    if override in ("0", "false", "no", "off"):
        return False
    chosen = (settings or {}).get("developer_mode")
    if isinstance(chosen, bool):
        return chosen
    return not getattr(sys, "frozen", False)


USER_DATA_FILES = ("settings.json", "runtime.json")


def user_data_dir() -> Path:
    """Returns the folder holding settings.json + runtime.json (nickname, birthday, stats).

    PANDA_DATA_DIR wins (tests, portable setups). Otherwise %APPDATA%\\PandaDesktopPet,
    so personal data never sits next to the bundled art or inside the git checkout.
    Without APPDATA (non-Windows) it stays in the legacy ``work`` folder.
    """
    override = os.environ.get("PANDA_DATA_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return app_dir() / "work"
    return Path(appdata) / "PandaDesktopPet"


def adopt_legacy_user_data(target: Path, legacy: Path) -> list[str]:
    """Copy settings/runtime from the old ``work`` folder on the first run; returns copied names.

    Only when the new folder has no settings.json yet. The legacy files are left
    in place: an older pet may still be running on them.
    """
    target, legacy = Path(target), Path(legacy)
    if target.resolve() == legacy.resolve() or (target / "settings.json").exists():
        return []
    if not (legacy / "settings.json").is_file():
        return []
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in USER_DATA_FILES:
        source = legacy / name
        if source.is_file():
            (target / name).write_bytes(source.read_bytes())
            copied.append(name)
    return copied


def resource_dir() -> Path:
    """Returns the base directory for read-only bundled assets (work/characters, icons).
    
    In development: the PandaDesktopPet project root.
    In frozen EXE: PyInstaller temporary unpacked directory (_MEIPASS).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(os.path.dirname(os.path.abspath(sys.executable)))
    return Path(__file__).resolve().parents[1]

