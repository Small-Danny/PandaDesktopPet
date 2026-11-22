"""X6: supported-size corner preservation and real Tk fallback (isolated data)."""
from __future__ import annotations

import tempfile
from dataclasses import replace
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops, ImageDraw

from app.bubble import KawaiiSpeechBubble, _render_9slice, _binarize, _render_frame
from app.bubble_themes import THEMES
from app.sprite_polish import alpha_bleed, defringe_light_frame

ROOT = Path(__file__).resolve().parents[1]
SIZES = ((180,180),(180,400),(400,180),(400,400),(520,180),(520,400))


class NineSlicePixelsTests(unittest.TestCase):
    def test_one_row_band_survives_runtime_short_card_width(self):
        path = THEMES["lilac_mauve"].get_nine_slice_path()
        frame = THEMES["lilac_mauve"].frame_layout()
        # Runtime outer width380 minus12px card margins, not in the 48-size audit.
        geo = frame.geometry(368,0)
        self.assertGreater(geo.height-geo.cap_top-geo.cap_bottom,0)
        output = _render_frame(path,frame,replace(geo,height=400))
        self.assertTrue(all(output.getpixel((184,y))[3] == 255
            for y in range(geo.cap_top,400-geo.cap_bottom)))

    def test_eight_assets_at_six_sizes_preserve_uniformly_scaled_caps(self):
        count = 0
        for theme in THEMES.values():
            if not theme.nine_slice_file:
                continue
            path = ROOT/"work/bubbles"/theme.nine_slice_file
            with Image.open(path) as source:
                source = alpha_bleed(source.convert("RGBA"))
                frame = theme.frame_layout()
                for w,h in SIZES:
                    with self.subTest(theme=theme.key,size=(w,h)):
                        geo = frame.geometry(w,0)
                        actual_h = max(h,geo.height)
                        # A one-row source band must survive rounding at small widths.
                        # Otherwise an expanded card has a transparent horizontal gap.
                        self.assertGreater(geo.height-geo.cap_top-geo.cap_bottom,0)
                        scaled = source.resize((w,geo.height),Image.Resampling.LANCZOS)
                        output = _render_frame(path,frame,replace(geo,height=actual_h))
                        expected = defringe_light_frame(_binarize(scaled.copy()))
                        self.assertEqual(output.size,(w,actual_h))
                        self.assertEqual(output.mode,"RGBA")
                        if frame.right_cut is None:
                            pairs = (
                                ((0,0,w,geo.cap_top),(0,0,w,geo.cap_top)),
                                ((0,geo.height-geo.cap_bottom,w,geo.height),
                                 (0,actual_h-geo.cap_bottom,w,actual_h)),
                            )
                        else:   # the right half is cut at its own row, so each half keeps its caps
                            mid = w//2
                            shift = round((frame.right_cut-frame.band[0])*geo.scale)
                            pairs = (
                                ((0,0,mid,geo.cap_top),(0,0,mid,geo.cap_top)),
                                ((mid,0,w,geo.cap_top+shift),(mid,0,w,geo.cap_top+shift)),
                                ((0,geo.height-geo.cap_bottom,mid,geo.height),
                                 (0,actual_h-geo.cap_bottom,mid,actual_h)),
                                ((mid,geo.height-geo.cap_bottom+shift,w,geo.height),
                                 (mid,actual_h-geo.cap_bottom+shift,w,actual_h)),
                            )
                            self.assertTrue(all(output.getpixel((w*3//4,y))[3] == 255
                                for y in range(geo.cap_top+shift,actual_h-geo.cap_bottom+shift)))
                        for sb,db in pairs:
                            difference = ImageChops.difference(expected.crop(sb),output.crop(db))
                            self.assertFalse(any(difference.getextrema()[channel][1] for channel in range(4)))
                        self.assertEqual(len(output.tobytes()),w*actual_h*4)
                        self.assertTrue(all(not count or alpha in (0,255)
                            for alpha,count in enumerate(output.getchannel("A").histogram())))
                        self.assertTrue(all(output.getpixel((w//2,y))[3] == 255
                            for y in range(geo.cap_top,actual_h-geo.cap_bottom)))
                        count += 1
        self.assertEqual(count,48)

    def test_synthetic_semitransparent_pixels_not_alpha_multiplied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture.png"
            Image.new("RGBA",(100,100),(20,50,90,128)).save(path)
            result = _render_9slice(path,180,400,(10,10,10,10))
            self.assertEqual(result.getpixel((0,0)),(20,50,90,128))
            self.assertEqual(result.getchannel("A").getextrema(),(128,128))

    def test_render_missing_and_corrupt_file_are_errors_for_caller(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"missing.png"
            with self.assertRaises(OSError):
                _render_9slice(path,180,180,(45,45,45,45))
            path.write_bytes(b"not a png")
            with self.assertRaises(OSError):
                _render_9slice(path,180,180,(45,45,45,45))


class NineSliceFallbackTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def card(self):
        card = KawaiiSpeechBubble(self.root,400,700,192,"Fallback test","保留可讀文字 English 한국어",
                                  theme=THEMES["chorong_pink"],duration_ms=60000)
        self.addCleanup(card.dismiss)
        self.root.update()
        return card

    def assert_vector_fallback(self,card):
        self.assertFalse(hasattr(card,"_bg_photo"))
        self.assertTrue(any(card.canvas.type(item)=="polygon" and
                            card.canvas.itemcget(item,"fill")==card.theme.bg_fill
                            for item in card.canvas.find_all()))
        self.assertTrue(any(card.message_canvas.type(item)=="text" for item in card.message_canvas.find_all()))

    def test_missing_file_keeps_vector_card_and_message(self):
        with mock.patch("app.bubble_themes.BubbleTheme.get_nine_slice_path",return_value=Path("missing_x6.png")):
            self.assert_vector_fallback(self.card())

    def test_corrupt_png_keeps_vector_card_and_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"corrupt.png"
            path.write_bytes(b"broken PNG")
            with mock.patch("app.bubble_themes.BubbleTheme.get_nine_slice_path",return_value=path):
                self.assert_vector_fallback(self.card())

    def test_decode_exception_keeps_vector_card_and_message(self):
        with mock.patch("app.bubble._render_9slice",side_effect=OSError("injected decode failure")):
            self.assert_vector_fallback(self.card())


if __name__=="__main__":
    unittest.main()
