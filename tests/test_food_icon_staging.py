"""White highlights survive exterior-only food icon extraction."""
import unittest

from PIL import Image, ImageDraw
from tools.stage_food_icons import extract_icon


class FoodIconStagingTest(unittest.TestCase):
    def test_enclosed_white_is_opaque_at_both_runtime_sizes(self):
        source = Image.new("RGB", (180, 160), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((25, 20, 155, 140), fill="#3b1e1e")
        draw.rectangle((32, 27, 148, 133), fill="white")
        for size in (128, 64):
            with self.subTest(size=size):
                icon = extract_icon(source, size)
                self.assertEqual(icon.getpixel((size // 2, size // 2)), (255, 255, 255, 255))
                self.assertEqual(icon.getpixel((0, 0))[3], 0)
                self.assertEqual(set(icon.getchannel("A").tobytes()), {0, 255})

    def test_foreground_crossing_a_split_is_rejected(self):
        source = Image.new("RGB", (80, 80), "white")
        ImageDraw.Draw(source).rectangle((0, 20, 50, 60), fill="brown")
        with self.assertRaisesRegex(ValueError, "boundary-touching"):
            extract_icon(source, 128)

    def test_empty_cell_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            extract_icon(Image.new("RGB", (80, 80), "white"), 128)

    def test_separate_bottle_and_cup_components_are_both_preserved(self):
        source = Image.new("RGB", (80, 80), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((10, 20, 30, 60), fill="green")
        draw.rectangle((50, 40, 70, 60), fill="brown")
        for size in (128, 64):
            with self.subTest(size=size):
                icon = extract_icon(source, size)
                self.assertEqual(icon.getpixel((size // 4, size * 5 // 8))[3], 255)
                self.assertEqual(icon.getpixel((size * 3 // 4, size * 5 // 8))[3], 255)
                self.assertEqual(icon.getpixel((size // 2, size * 5 // 8))[3], 0)


if __name__ == "__main__":
    unittest.main()
