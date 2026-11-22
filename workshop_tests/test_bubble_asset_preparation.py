"""Read-only checks of the existing asset preparation entry points.

Synthetic fixtures remain in memory. Actual prepare() checks read approved source
images and never call main(), save(), or overwrite work/bubbles assets.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bubble_art_under_test", ROOT / "tools/prepare_bubble_art.py")
ART = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ART)


def alpha_values(image):
    histogram = image.getchannel("A").histogram()
    return {index for index, count in enumerate(histogram) if count}


def synthetic_card():
    image = Image.new("RGB", (80, 70), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 71, 61), radius=12, fill="white", outline=(80, 30, 50), width=4)
    return image


class BubbleAssetPreparationTests(unittest.TestCase):
    def test_sealed_white_interior_survives_exterior_removal(self):
        source = synthetic_card()
        prepared = ART.make_transparent(source)
        self.assertEqual(prepared.mode, "RGBA")
        self.assertEqual(prepared.getpixel((prepared.width // 2, prepared.height // 2)),
                         (255, 255, 255, 255))
        self.assertEqual(prepared.getpixel((0, 0))[3], 0)
        self.assertLess(prepared.width, source.width)
        self.assertLess(prepared.height, source.height)
        self.assertEqual(alpha_values(prepared), {0, 255})

    def test_make_transparent_does_not_mutate_source(self):
        source = synthetic_card()
        before = source.tobytes()
        ART.make_transparent(source)
        self.assertEqual(source.tobytes(), before)
        self.assertEqual(source.mode, "RGB")

    def test_two_stacked_cards_are_split_at_white_gap(self):
        source = Image.new("RGB", (120, 170), "white")
        draw = ImageDraw.Draw(source)
        draw.rounded_rectangle((5, 4, 114, 69), radius=12, fill=(255, 240, 220), outline="brown", width=3)
        draw.rounded_rectangle((5, 94, 114, 164), radius=12, fill=(240, 220, 255), outline="purple", width=3)
        cards = ART.split_cards(source)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0].getpixel((60, cards[0].height // 2)), (255, 240, 220))
        self.assertEqual(cards[1].getpixel((60, cards[1].height // 2)), (240, 220, 255))

    def test_no_blank_separator_keeps_one_card(self):
        source = synthetic_card()
        self.assertEqual(len(ART.split_cards(source)), 1)

    def test_original_sheet_has_two_full_height_cards(self):
        with Image.open(ART.SOURCE / "bubble_ruby_velvet.png") as source:
            cards = ART.split_cards(source)
        self.assertEqual(len(cards), 2)
        self.assertEqual([card.size for card in cards], [(500, 264), (500, 272)])

    def test_original_backups_and_reference_still_match_x6_hashes(self):
        inventory = json.loads((ROOT / "work/evidence/x6/asset_inventory.json").read_text(encoding="utf-8"))
        original_rows = [row for row in inventory["records"] if row["path"].startswith("work/bubbles/")]
        self.assertEqual(len(original_rows), 8)
        for row in original_rows:
            backup = ART.SOURCE / Path(row["path"]).name
            with self.subTest(backup=backup.name):
                self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), row["sha256"])
        reference = next(row for row in inventory["records"]
                         if row["path"].endswith("\u80cc\u666f8.png"))
        self.assertEqual(hashlib.sha256((ROOT / reference["path"]).read_bytes()).hexdigest(),
                         reference["sha256"])

    def test_prepare_is_repeatable_binary_and_keeps_central_interior(self):
        snapshots = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(ART.SOURCE.glob("bubble_*.png"))}
        target_snapshots = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(ART.BUBBLES.glob("bubble_*.png"))}
        self.assertEqual(len(snapshots), 8)
        for path in snapshots:
            with self.subTest(asset=path.name):
                first = ART.prepare(path.name)
                second = ART.prepare(path.name)
                self.assertEqual(first.width, 500)
                self.assertLess(first.height, 330)  # A single card, not two stacked frames.
                self.assertEqual(first.mode, "RGBA")
                self.assertEqual(first.size, second.size)
                self.assertEqual(first.tobytes(), second.tobytes())
                self.assertEqual(alpha_values(first), {0, 255})
                alpha = first.getchannel("A")
                central = alpha.crop((first.width // 3, first.height // 3,
                                      2 * first.width // 3, 2 * first.height // 3))
                self.assertEqual(central.getextrema(), (255, 255))
                self.assertTrue(all(alpha.getpixel(point) == 0 for point in
                                    ((0, 0), (first.width - 1, 0),
                                     (0, first.height - 1), (first.width - 1, first.height - 1))))
        for path, expected in {**snapshots, **target_snapshots}.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected,
                             f"prepare() modified a file: {path}")

    def test_lilac_and_strawberry_are_independent_of_member_frames(self):
        lilac = ART.prepare("bubble_lilac_mauve.png")
        strawberry = ART.prepare("bubble_ruby_velvet.png")
        lr, lg, lb, la = lilac.getpixel((lilac.width // 2, lilac.height // 2))
        rr, rg, rb, ra = strawberry.getpixel((strawberry.width // 2, strawberry.height // 2))
        self.assertGreater(lb, lg)
        self.assertGreater(rr, rb)
        self.assertEqual((la, ra), (255, 255))
        for name, member in (("bubble_lilac_mauve.png", "bubble_namjoo_purple.png"),
                             ("bubble_ruby_velvet.png", "bubble_bomi_coral.png")):
            self.assertNotEqual(ART.prepare(name).tobytes(), ART.prepare(member).tobytes())

    def test_decorative_frames_use_background6_not_background8(self):
        from unittest.mock import patch
        # Observe the actual read path, not only the crop constants.
        real_open = ART.Image.open
        for name in ART.BACKGROUND6_NAMES:
            with patch.object(ART.Image, "open", wraps=real_open) as opened:
                ART.prepare(name)
            opened.assert_called_once_with(ART.BACKGROUND6)

    def test_original_reference_crops_have_margin_and_keep_strong_outlines(self):
        expected = {"bubble_ruby_velvet.png": (840, 5, 1665, 455),
                    "bubble_lilac_mauve.png": (5, 450, 830, 935)}
        for name, box in expected.items():
            self.assertEqual(ART.ORIGINAL_CARDS.get(name), box)
        with Image.open(ART.BACKGROUND6) as reference:
            self.assertEqual(reference.size, (1672, 941))
            for name, box in expected.items():
                with self.subTest(asset=name):
                    crop = reference.convert("RGB").crop(box)
                    edge = [crop.getpixel((x, y))
                            for x in range(crop.width) for y in (0, crop.height - 1)]
                    edge += [crop.getpixel((x, y))
                             for y in range(1, crop.height - 1) for x in (0, crop.width - 1)]
                    self.assertTrue(all(min(rgb) >= 245 and max(rgb) - min(rgb) <= 14 for rgb in edge),
                                    "crop cuts into visible artwork at its outer edge")
                    result = ART.make_transparent(crop)
                    # Preserve strong contours, including star/skewer outlines,
                    # before the separate canonical-width resampling step.
                    source_dark = sum(min(rgb) < 160 for rgb in crop.get_flattened_data())
                    result_dark = sum(alpha == 255 and min(red, green, blue) < 160
                                      for red, green, blue, alpha in result.get_flattened_data())
                    self.assertEqual(result_dark, source_dark)


if __name__ == "__main__":
    unittest.main()
