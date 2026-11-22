"""tools/pack_assets.py — Compile validated runtime assets into an indexed .pak file.

Packages every entry from ``tools.runtime_manifest.runtime_files(root)`` into a
single ``assets.pak`` binary container so the PyInstaller runtime bundle does not
expose loose PNG, JPG, or CUR asset files under ``_internal/``.

Already-compressed raster assets (.png, .jpg, .jpeg) use ``store`` (zero-copy
I/O, zero decompression RAM spike), while text/JSON/cursor binaries use ``zlib``
when compression reduces size.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.resource_store import CODEC_STORE, CODEC_ZLIB, PAK_HEADER_STRUCT, PAK_MAGIC, PakResourceStore
from tools.runtime_manifest import runtime_files

COMPRESSIBLE_SUFFIXES = frozenset({".json", ".txt", ".cur", ".yaml", ".yml"})


def pack_assets(root: Path, output_path: Path, rel_paths: tuple[str, ...] | list[str] | None = None) -> dict:
    """Write ``output_path`` containing all validated runtime resources from ``root``.

    Returns summary statistics including entry counts, raw/packed sizes, and
    destination path. Verifies readability of the written container before return.
    """
    base = Path(root).resolve()
    dest = Path(output_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rel_paths) if rel_paths is not None else runtime_files(base)

    entries: dict[str, dict] = {}
    total_raw = 0
    total_stored = 0
    tmp_dest = dest.with_suffix(dest.suffix + ".tmp")

    with tmp_dest.open("wb") as fh:
        fh.write(PAK_HEADER_STRUCT.pack(PAK_MAGIC, 0, 0))
        for raw_key in sorted(set(keys)):
            rel_key = raw_key.replace("\\", "/")
            src = (base / rel_key).resolve()
            src.relative_to(base)
            payload = src.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            codec = CODEC_STORE
            stored = payload
            if src.suffix.lower() in COMPRESSIBLE_SUFFIXES and len(payload) > 0:
                compressed = zlib.compress(payload, level=6)
                if len(compressed) < len(payload):
                    stored = compressed
                    codec = CODEC_ZLIB

            offset = fh.tell()
            fh.write(stored)
            entries[rel_key] = {
                "offset": offset,
                "size": len(stored),
                "raw_size": len(payload),
                "codec": codec,
                "sha256": digest,
            }
            total_raw += len(payload)
            total_stored += len(stored)

        toc_offset = fh.tell()
        toc_bytes = json.dumps({"format": 1, "entries": entries}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        fh.write(toc_bytes)
        fh.seek(0)
        fh.write(PAK_HEADER_STRUCT.pack(PAK_MAGIC, toc_offset, len(toc_bytes)))

    tmp_dest.replace(dest)

    # Read-back verification: ensure TOC and every entry digest validate cleanly.
    store = PakResourceStore(dest, base_root=base)
    with store.session():
        for rel_key, meta in entries.items():
            if store.sha256(rel_key) != meta["sha256"]:
                raise RuntimeError(f"pack verification failed for {rel_key}")

    return {
        "output": str(dest),
        "entry_count": len(entries),
        "raw_bytes": total_raw,
        "stored_bytes": total_stored,
        "toc_bytes": len(toc_bytes),
        "pak_bytes": dest.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile validated runtime assets into assets.pak")
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root containing work/ assets")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "assets.pak", help="Output .pak path")
    args = parser.parse_args(argv)
    summary = pack_assets(args.root, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
