"""Display-time sprite polish: one resize, crisp closed outline, alpha and anchors unchanged.

Run:  python -m unittest tests.test_sprite_polish -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sprite_polish import (  # noqa: E402
    RIM_LUM,
    alpha_bleed,
    defringe_light_frame,
    edge_ring,
    fringe_ratio,
    lock_fringe,
    polish_frame,
    prepare_ulw_source,
    purify_white,
)
from app.sprites import (  # noqa: E402
    ALPHA_THRESHOLD,
    SpriteLibrary,
    prepare_frame,
    rescale_about_feet,
    scale_to_display,
)

OUTLINE = (60, 20, 70)
FUR = (190, 160, 210)


def _panda(rim: tuple[int, int, int] | None = (215, 205, 220)) -> Image.Image:
    """256x256 frame: lavender body, 4 px dark outline, optional 1 px pale rim outside it."""
    im = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    if rim:
        d.ellipse((59, 79, 197, 244), fill=rim + (255,))
    d.ellipse((60, 80, 196, 243), fill=OUTLINE + (255,))
    d.ellipse((64, 84, 192, 239), fill=FUR + (255,))
    d.ellipse((90, 110, 166, 200), fill=(250, 250, 249, 255))   # near-white face
    return im


def _alpha_box(im: Image.Image):
    return im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()


class ScaleToDisplayTest(unittest.TestCase):
    def test_single_resize_matches_old_geometry(self) -> None:
        for scale in (0.95, 1.0, 1.23):
            for size in (144, 192, 240):
                with self.subTest(scale=scale, size=size):
                    old = prepare_frame(rescale_about_feet(_panda(), scale), size)
                    new = scale_to_display(_panda(), scale, size)
                    self.assertEqual(new.size, old.size)
                    for a, b in zip(_alpha_box(new), _alpha_box(old)):
                        self.assertLessEqual(abs(a - b), 1)
                    hist = new.getchannel("A").histogram()
                    self.assertEqual(sum(hist[1:255]), 0)


class PolishTest(unittest.TestCase):
    def test_pale_prop_edge_uses_its_local_colour(self) -> None:
        im = Image.new("RGBA", (12, 8))
        local = (213, 162, 111, 255)
        im.putpixel((2, 3), OUTLINE + (255,))
        im.putpixel((8, 3), local)
        im.putpixel((9, 3), (239, 207, 170, 255))
        im.putpixel((10, 3), (255, 242, 210, 255))
        out = lock_fringe(im, outline=OUTLINE)
        self.assertEqual(out.getpixel((10, 3)), local)
        self.assertEqual(out.getchannel("A").tobytes(), im.getchannel("A").tobytes())

    def test_soft_rim_becomes_outline_and_alpha_is_untouched(self) -> None:
        for size in (144, 192, 240):
            with self.subTest(size=size):
                frame = scale_to_display(_panda(), 1.0, size)
                width = 2 if size >= 220 else 1
                self.assertGreater(fringe_ratio(frame, 1), 0.3)
                out = polish_frame(frame, size)
                self.assertEqual(out.size, frame.size)
                self.assertIsNone(ImageChops.difference(out.getchannel("A"), frame.getchannel("A")).getbbox())
                self.assertLess(fringe_ratio(out, 1), 0.02)
                self.assertLess(fringe_ratio(out, width, threshold=130), 0.02)

    def test_interior_colours_are_kept(self) -> None:
        frame = scale_to_display(_panda(), 1.0, 240)
        out = polish_frame(frame, 240)
        cx, cy = out.width // 2, round(240 * 225 / 256)        # fur below the face
        r, g, b, _ = out.getpixel((cx, cy))
        self.assertLess(max(abs(r - FUR[0]), abs(g - FUR[1]), abs(b - FUR[2])), 25)
        self.assertEqual(out.getpixel((cx, round(240 * 150 / 256)))[:3], (255, 255, 255))

    def test_missing_outline_is_closed_with_frame_outline_colour(self) -> None:
        im = _panda(rim=None)
        ImageDraw.Draw(im).rectangle((150, 75, 200, 130), fill=FUR + (255,))  # ear with no outline
        # Test the fallback on exact flat pixels. Resampling the patch first
        # creates a real gradient, which has its own local-outline contract.
        out = lock_fringe(im, outline=OUTLINE)
        ring = edge_ring(out.getchannel("A"), 1)
        px, rp = out.load(), ring.load()
        pale = [px[x, y] for y in range(out.height) for x in range(out.width)
                if rp[x, y] and sum(px[x, y][:3]) / 3 > RIM_LUM + 60]
        self.assertEqual(pale, [])

    def test_purify_white_only_near_white(self) -> None:
        im = Image.new("RGBA", (3, 1))
        im.putdata([(246, 247, 250, 255), (240, 250, 250, 255), (250, 250, 250, 0)])
        out = purify_white(im)
        self.assertEqual([out.getpixel((x, 0)) for x in range(3)],
                         [(255, 255, 255, 255), (240, 250, 250, 255), (250, 250, 250, 0)])

    def test_empty_frame(self) -> None:
        empty = Image.new("RGBA", (222, 192), (0, 0, 0, 0))
        self.assertEqual(polish_frame(empty, 192).getbbox(), None)

    def test_cropped_processing_preserves_partial_alpha_and_large_canvas(self):
        im = Image.new("RGBA", (640, 640), (0, 0, 0, 0))
        im.paste(_panda(), (180, 180))
        im.putpixel((300, 300), (250, 250, 250, 150))
        out = polish_frame(im, 384)
        self.assertEqual(out.size, im.size)
        self.assertIsNone(ImageChops.difference(out.getchannel("A"), im.getchannel("A")).getbbox())

    def test_alpha_bleed_eliminates_hidden_transparent_garbage_before_lanczos(self):
        im = Image.new("RGBA", (64, 64), (255, 0, 254, 0))
        ImageDraw.Draw(im).ellipse((16, 16, 48, 48), fill=OUTLINE + (255,))
        bled = alpha_bleed(im)
        resized = bled.resize((40, 40), Image.Resampling.LANCZOS)
        resized.putalpha(resized.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0))
        r1 = edge_ring(resized.getchannel("A"), 1)
        px, rp = resized.load(), r1.load()
        for y in range(resized.height):
            for x in range(resized.width):
                if rp[x, y]:
                    r, g, b, _ = px[x, y]
                    self.assertLess(r, 90)
                    self.assertLess(b, 100)

    def test_large_second_ring_mid_grey_fringe_and_bubble_defringe(self):
        im = _panda(rim=None)
        d = ImageDraw.Draw(im)
        # 2px outer ring at 240px with luminance 105..125 next to dark outline (60,20,70)
        d.ellipse((58, 78, 198, 245), fill=(115, 110, 120, 255))
        d.ellipse((60, 80, 196, 243), fill=OUTLINE + (255,))
        d.ellipse((64, 84, 192, 239), fill=FUR + (255,))
        out = lock_fringe(im, width=2, outline=OUTLINE)
        r2 = edge_ring(out.getchannel("A"), 2)
        px, rp = out.load(), r2.load()
        mid_grey = [px[x, y] for y in range(out.height) for x in range(out.width)
                    if rp[x, y] and 95 < (0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2]) < 130]
        self.assertEqual(mid_grey, [])

        # Decorated bubble frame: pale outer pixel at canvas boundary x=0 pulled to local border colour
        bubble = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        border_rgb = (204, 51, 86, 255)
        pale_rgb = (242, 180, 195, 255)
        ImageDraw.Draw(bubble).rectangle((0, 4, 28, 28), fill=(255, 240, 245, 255))
        for y in range(4, 29):
            bubble.putpixel((0, y), pale_rgb)
            bubble.putpixel((1, y), border_rgb)
        cleaned = defringe_light_frame(bubble)
        self.assertEqual(cleaned.getpixel((0, 16)), border_rgb)
        self.assertEqual(cleaned.getchannel("A").tobytes(), bubble.getchannel("A").tobytes())

    def test_ulw_8bit_cleans_baked_white_rim_and_feathers_binary_contour(self) -> None:
        # Simulate a 256x256 1-bit sprite with a baked pale/white cutout halo around dark outline
        im = _panda(rim=(240, 240, 244))
        prepared = prepare_ulw_source(im)
        self.assertGreater(
            sum(prepared.getchannel("A").histogram()[1:255]),
            50,
            "Expected 1-bit contour to gain smooth 8-bit antialiased alpha",
        )
        # Scale near 1:1 (240px) and polish with binary_alpha=False, edge_refine=True
        scaled = scale_to_display(im, 1.0, 240, binary_alpha=False, edge_refine=True)
        out = polish_frame(scaled, 240, binary_alpha=False, edge_refine=True)
        self.assertIsNone(ImageChops.difference(out.getchannel("A"), scaled.getchannel("A")).getbbox())
        # Both opaque rim and semi-transparent edge pixels must stay outline-dark (no white halo)
        ring_solid = edge_ring(out.getchannel("A").point(lambda v: 255 if v >= 200 else 0), 1)
        px, rp = out.load(), ring_solid.load()
        pale_solid = [
            px[x, y]
            for y in range(out.height)
            for x in range(out.width)
            if rp[x, y] and (0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2]) > 140
        ]
        self.assertEqual(pale_solid, [])
        semi_bright = [
            px[x, y]
            for y in range(out.height)
            for x in range(out.width)
            if 0 < px[x, y][3] < 200 and (0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2]) > 140
        ]
        self.assertEqual(semi_bright, [])

    def test_edge_refine_off_preserves_small_and_colorkey_and_skips_soft_sources(self) -> None:
        im = _panda(rim=(240, 240, 244))
        # edge_refine=True must have zero effect when binary_alpha=True (ColorKey path)
        ck_off = polish_frame(scale_to_display(im, 1.0, 240, binary_alpha=True, edge_refine=False), 240, binary_alpha=True, edge_refine=False)
        ck_on = polish_frame(scale_to_display(im, 1.0, 240, binary_alpha=True, edge_refine=True), 240, binary_alpha=True, edge_refine=True)
        self.assertEqual(ck_off.tobytes(), ck_on.tobytes())

        # Sources already containing semi-transparent pixels are skipped by prepare_ulw_source
        soft = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        ImageDraw.Draw(soft).ellipse((6, 6, 26, 26), fill=(60, 20, 70, 255))
        soft.putpixel((10, 10), (200, 180, 190, 120))
        self.assertEqual(prepare_ulw_source(soft).tobytes(), alpha_bleed(soft).tobytes())

    def test_soft_binarize_cleans_pale_semi_alpha_cutout_halo(self) -> None:
        # Simulate a soft-alpha cutout sprite with a pale semi-transparent rim (40% of library)
        im = _panda(rim=(235, 235, 242))
        px_in = im.load()
        for y in range(im.height):
            for x in range(im.width):
                if px_in[x, y] == (235, 235, 242, 255):
                    px_in[x, y] = (235, 235, 242, 160)
        out_raw = prepare_ulw_source(im, soft_binarize=False)
        out_soft = prepare_ulw_source(im, soft_binarize=True)
        # Without soft_binarize, pale alpha=160 rim stays pale; with soft_binarize=True it is cleaned.
        self.assertGreater(fringe_ratio(out_raw), fringe_ratio(out_soft))
        self.assertLess(fringe_ratio(out_soft), 0.05)
        for display_px in (144, 288):
            with self.subTest(display_px=display_px):
                scaled = scale_to_display(im, 1.0, display_px, binary_alpha=False, edge_refine=True)
                polished = polish_frame(scaled, display_px, binary_alpha=False, edge_refine=True)
                px = polished.load()
                semi_bright = [
                    px[x, y]
                    for y in range(polished.height)
                    for x in range(polished.width)
                    if 0 < px[x, y][3] < 200 and (0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2]) > 140
                ]
                self.assertEqual(semi_bright, [])


class LibraryTest(unittest.TestCase):
    def test_polish_flag(self) -> None:
        self.assertTrue(SpriteLibrary(ROOT).polish)
        self.assertFalse(SpriteLibrary(ROOT, polish=False).polish)
        lib = SpriteLibrary(ROOT, binary_alpha=False, edge_refine=True)
        self.assertTrue(lib.edge_refine)
        peer = lib.with_binary_alpha(True)
        self.assertTrue(peer.edge_refine)
        lib.set_edge_refine(False)
        self.assertFalse(peer.edge_refine)


if __name__ == "__main__":
    unittest.main()
