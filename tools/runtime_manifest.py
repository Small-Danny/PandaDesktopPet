"""The files the running pet reads from ``work/``: one list for the EXE build and the public export.

    python tools/runtime_manifest.py            # count and size
    python tools/runtime_manifest.py --list     # every relative path

Character frames the asset registry marks blocked/excluded are left out: the
resolver refuses them anyway (app/engine/assets.py), so shipping them only adds weight.
User data (settings.json, runtime.json) is never part of this list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_DIRS = (
    "work/characters",
    "work/foods",
    "work/bubbles",
    "work/ui_icons",
    "work/scenes",
    "work/standby_backgrounds",
    "work/rongdoong_processed_v2",   # legacy manifest fallback (app/sprites.py)
)
RUNTIME_FILES = (
    "work/asset_registry.json",
    "work/standby_backgrounds.json",
    "work/quotes.json",
    "work/apink成員暖心語錄.txt",
)
MEMBERS = ("bomi", "chorong", "eunji", "hayoung", "namjoo")
BASE_ACTIONS = ("idle", "walk", "cheer", "sleep")
SKIP_DIR_NAMES = frozenset({"source", "__pycache__", "private", "backup", "backups", "before", "logs"})
SKIP_SUFFIXES = (".bak", ".corrupt", ".tmp", ".log")
ASSET_SUFFIXES = {
    "work/foods": {".png"},
    "work/bubbles": {".png"},
    "work/ui_icons": {".png", ".cur"},
    "work/scenes": {".png"},
    "work/standby_backgrounds": {".png", ".jpg", ".jpeg"},
}


def private_asset_path(path: Path) -> bool:
    """Shared packaging boundary; never bundle user data or backup/log trees."""
    parts = [part.casefold() for part in path.parts]
    name = parts[-1] if parts else ""
    return (bool(SKIP_DIR_NAMES.intersection(parts))
            or any(part.startswith(("backup_", "private_")) for part in parts)
            or name.startswith(("settings.", "runtime.", "_preview"))
            or name.endswith(SKIP_SUFFIXES)
            or name.endswith("_preview.png"))


def checked_file(root: Path, relative: str) -> Path:
    """Only regular, present resources physically inside the selected root."""
    path = root / relative
    if private_asset_path(Path(relative)):
        raise ValueError(f"private asset path: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"resource escapes root: {relative}")
    if not path.is_file():
        raise FileNotFoundError(f"runtime resource missing: {relative}")
    return path


def character_records(root: Path = ROOT) -> dict:
    registry = json.loads(checked_file(root, "work/asset_registry.json").read_text(encoding="utf-8-sig"))
    return registry["files"]


def unapproved_character_files(root: Path = ROOT) -> set[str]:
    """Compatibility helper: known registry paths rejected by the resolver."""
    return {record["path"] for record in character_records(Path(root)).values()
            if record.get("review_status") != "approved" or record.get("runtime_ok") is not True}


def runtime_files(root: Path = ROOT) -> list[str]:
    """Deterministic, validated resources shared by source export and EXE build.

    New character PNGs are excluded until registered and hash-approved. Mandatory
    approved resources fail the build if missing or changed; no stale art is silently
    substituted. Legacy fallback permits only its original 4x4 named frame set.
    """
    root = Path(root)
    out: set[str] = set()
    for record in character_records(root).values():
        if record.get("review_status") != "approved" or record.get("runtime_ok") is not True:
            continue
        rel = record["path"]
        if (not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or Path(rel).drive
                or ".." in Path(rel).parts or Path(rel).suffix.lower() != ".png"):
            raise ValueError("invalid approved character path")
        relative = "work/characters/" + rel
        path = checked_file(root, relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256"):
            raise ValueError(f"approved character bytes changed: {relative}")
        out.add(relative)
    for member in MEMBERS:
        relative = f"work/characters/{member}/manifest.json"
        if (root / relative).is_file():
            checked_file(root, relative)
            out.add(relative)
    for name, suffixes in ASSET_SUFFIXES.items():
        for path in sorted((root / name).rglob("*")):
            relative = path.relative_to(root).as_posix()
            if private_asset_path(Path(relative)) or path.suffix.lower() not in suffixes or not path.is_file():
                continue
            checked_file(root, relative)
            out.add(relative)
    legacy = root / "work/rongdoong_processed_v2"
    if (legacy / "manifest.json").is_file():
        relative = "work/rongdoong_processed_v2/manifest.json"
        manifest = json.loads(checked_file(root, relative).read_text(encoding="utf-8-sig"))
        out.add(relative)
        allowed = {f"{action}_{i:02d}.png" for action in BASE_ACTIONS for i in range(1, 5)}
        for names in manifest.get("frames", {}).values():
            for name in names:
                if name not in allowed:
                    raise ValueError("unexpected legacy fallback frame")
                rel = f"work/rongdoong_processed_v2/{name}"
                checked_file(root, rel)
                out.add(rel)
    for relative in RUNTIME_FILES:
        checked_file(root, relative)
        out.add(relative)
    return sorted(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print every path")
    args = parser.parse_args()
    files = runtime_files()
    if args.list:
        print("\n".join(files))
    size = sum((ROOT / f).stat().st_size for f in files)
    print(f"{len(files)} files, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
