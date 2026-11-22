"""Eunji's identity mole on the boxing frames the runtime actually loads (2026-11-22).

The 11:12 mole pass stamped special_boxing/frame_0N.png, but the registry plays
special_boxing/rescaled_smaller/frame_0N.png, so the user still saw a mole-less Eunji.
This pins the runtime frames: the registry must point at rescaled_smaller and each frame
must carry the official dot (core RGB 48,88,142) above the viewer-left eye patch.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "work" / "asset_registry.json"
# Dot centres from the stamping run (viewer-left eye patch, REL 0.43/0.24).
MOLE_AT = {1: (180, 232), 2: (180, 232), 3: (180, 232), 4: (157, 231)}
CORE = (48, 88, 142)


class EunjiBoxingMoleTest(unittest.TestCase):
    def test_runtime_boxing_frames_carry_the_mole(self) -> None:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        frames = reg["assets"]["eunji.special_boxing"]["frames"]
        self.assertEqual(len(frames), 4)
        for n, rel in enumerate(frames, 1):
            self.assertIn("special_boxing/rescaled_smaller/", rel)
            im = Image.open(ROOT / rel).convert("RGBA")
            x, y = MOLE_AT[n]
            near = [im.getpixel((x + dx, y + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
            best = min(sum(abs(a - b) for a, b in zip(p[:3], CORE)) for p in near)
            self.assertLess(best, 60, f"{rel}: no mole-coloured pixel near {(x, y)}")
            # The surrounding eye patch stays light blue (the dot is a dot, not a smear).
            ring = im.getpixel((x, y - 6))
            self.assertGreater(sum(ring[:3]) / 3, 150, rel)


if __name__ == "__main__":
    unittest.main()
