"""Headless tests: every member is drawn at the same visible size.

Run:  python -m unittest tests.test_sprite_equalize -v
"""
from __future__ import annotations

import sys
import statistics
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import MEMBER_KEYS  # noqa: E402
from app.sprites import (  # noqa: E402
    ALPHA_THRESHOLD,
    BODY_PX,
    CANVAS_SRC,
    SpriteLibrary,
    body_height,
    prepare_frame,
    rescale_about_feet,
)
from tests.visual_helpers import white_face_width


def _box(im: Image.Image):
    return im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()


def _figure(top: int, half_w: int = 40) -> Image.Image:
    """Synthetic 256x256 frame: a body from ``top`` down to the feet at y=244."""
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((128 - half_w, top, 128 + half_w - 1, 243), fill=(255, 0, 0, 255))
    return im


class TestRescale(unittest.TestCase):
    def test_feet_stay_put_and_height_scales(self) -> None:
        out = rescale_about_feet(_figure(top=144), 1.5)          # 100 px tall -> 150
        self.assertEqual(out.size, CANVAS_SRC)
        left, top, right, bottom = _box(out)
        self.assertEqual(bottom, 244)                             # same feet line
        self.assertAlmostEqual(bottom - top, 150, delta=1)
        self.assertAlmostEqual((left + right) / 2, CANVAS_SRC[0] / 2, delta=1)  # centred

    def test_median_ignores_one_raised_arm_frame(self) -> None:
        frames = [_figure(144), _figure(144), _figure(44)]
        self.assertEqual(body_height(frames), 100)

    def test_prepare_frame_keeps_aspect(self) -> None:
        im = prepare_frame(Image.new("RGBA", CANVAS_SRC), 192)
        self.assertEqual(im.size, (round(CANVAS_SRC[0] * 192 / CANVAS_SRC[1]), 192))


class TestRealMembers(unittest.TestCase):
    """Uses the repo's approved registry art."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lib = SpriteLibrary(ROOT)
        if cls.lib.registry is None:
            raise unittest.SkipTest("asset registry unavailable")

    def test_standing_face_balance_and_no_clipping(self) -> None:
        heights = {}
        faces = {}
        for member in MEMBER_KEYS:
            raw = self.lib._load_registry(member)
            if raw is None:
                self.skipTest(f"{member} not in registry")
            pil = self.lib._equalize(member, raw)
            heights[member] = body_height(pil["idle"])
            faces[member] = statistics.median(white_face_width(im) for im in pil["idle"])
            for action, frames in pil.items():
                for im in frames:
                    left, top, right, _ = _box(im)
                    self.assertTrue(left > 0 and top > 0 and right < im.width,
                                    f"{member}.{action} touches the canvas edge")
        for member, width in faces.items():
            self.assertAlmostEqual(width, 152, delta=6, msg=f"{member}: {faces}")
        self.assertLessEqual(max(heights.values())-min(heights.values()), 33, heights)


if __name__ == "__main__":
    unittest.main(verbosity=2)
