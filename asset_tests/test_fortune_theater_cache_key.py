"""tests/test_fortune_theater_cache_key.py — cheap cache key for the fortune theater frames.

Opening the fortune dialog computes the theater cache key on the Tk thread every
time; a cache hit must resolve the resource store once and use relative keys,
not 24 x resource_exists + resource_stat_signature (each re-resolving paths).
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import fortune_room as room  # noqa: E402
from app import resource_store as rs  # noqa: E402


def _png(color: tuple[int, int, int], size=(16, 9)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _write_pak(pak_path: Path, files: dict[str, bytes]) -> None:
    header = rs.PAK_HEADER_STRUCT.size
    body = b""
    entries = {}
    for key, data in files.items():
        entries[key] = {"offset": header + len(body), "size": len(data), "raw_size": len(data),
                        "codec": rs.CODEC_STORE, "sha256": hashlib.sha256(data).hexdigest()}
        body += data
    toc = json.dumps({"format": 1, "entries": entries}).encode("utf-8")
    pak_path.write_bytes(rs.PAK_HEADER_STRUCT.pack(rs.PAK_MAGIC, header + len(body), len(toc)) + body + toc)


def _frames(count: int, color: tuple[int, int, int]) -> dict[str, bytes]:
    return {f"work/scenes/fortune_room/frame_{i:02d}.png": _png(color) for i in range(1, count + 1)}


class FortuneTheaterCacheKeyTests(unittest.TestCase):
    def setUp(self):
        room._THEATER_PIL.clear()
        rs.clear_store_cache()
        self.addCleanup(room._THEATER_PIL.clear)
        self.addCleanup(rs.clear_store_cache)

    def test_hit_resolves_store_once_without_per_frame_module_lookups(self):
        with tempfile.TemporaryDirectory(prefix="panda_fortune_folder_") as tmp:
            base = Path(tmp)
            for key, data in _frames(room.FORTUNE_THEATER_FRAME_COUNT, (120, 30, 90)).items():
                frame = base / key
                frame.parent.mkdir(parents=True, exist_ok=True)
                frame.write_bytes(data)
            first = room._scaled_theater_frames(base, 240, 135)
            self.assertEqual(len(first), room.FORTUNE_THEATER_FRAME_COUNT)
            with patch.object(room, "resource_store", wraps=room.resource_store) as store_fn, \
                    patch.object(room, "resource_exists", side_effect=AssertionError("per-frame resource_exists")), \
                    patch.object(rs, "resource_stat_signature", side_effect=AssertionError("per-frame stat lookup")), \
                    patch.object(room, "open_resource_image", side_effect=AssertionError("decoded on hit")):
                second = room._scaled_theater_frames(base, 240, 135)
            self.assertIs(first, second)
            self.assertEqual(store_fn.call_count, 1)

    def test_pak_hit_reuses_frames_and_rebuilt_pak_invalidates(self):
        with tempfile.TemporaryDirectory(prefix="panda_fortune_pak_") as tmp:
            base = Path(tmp)
            pak = base / rs.PAK_FILENAME
            _write_pak(pak, _frames(3, (200, 40, 90)))
            first = room._scaled_theater_frames(base, 32, 18)
            self.assertEqual(len(first), 3)
            self.assertEqual(first[0].size, (32, 18))
            self.assertIsInstance(rs.resource_store(base), rs.PakResourceStore)
            with patch.object(room, "open_resource_image", side_effect=AssertionError("decoded on hit")):
                self.assertIs(room._scaled_theater_frames(base, 32, 18), first)

            _write_pak(pak, _frames(4, (20, 160, 220)))
            rebuilt = room._scaled_theater_frames(base, 32, 18)
            self.assertIsNot(rebuilt, first)
            self.assertEqual(len(rebuilt), 4)
            self.assertEqual(rebuilt[0].getpixel((5, 5)), (20, 160, 220))

    def test_missing_frame_truncates_sequence(self):
        with tempfile.TemporaryDirectory(prefix="panda_fortune_pak_") as tmp:
            base = Path(tmp)
            files = _frames(5, (90, 90, 90))
            del files["work/scenes/fortune_room/frame_03.png"]
            _write_pak(base / rs.PAK_FILENAME, files)
            self.assertEqual(len(room._scaled_theater_frames(base, 16, 9)), 2)


if __name__ == "__main__":
    unittest.main()
