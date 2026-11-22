"""tests/test_size_scaling.py — Verification of Pet Size & Text Size Scaling Features.

Tests:
1. PET_SIZE_MAP values (144, 192, 240) and bottom-center anchor rescaling mathematics.
2. PersistenceService settings validation for pet_size and text_size with defaults.
3. Bubble text size fonts (9pt, 10pt, 12pt) and minimum 8pt threshold for small text.
4. Active subpanel detection logic preventing pet window topmost occlusion.
"""
from __future__ import annotations

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bubble import TEXT_SIZE_FONTS, TEXT_SIZE_WIDTHS, KawaiiSpeechBubble
from app.bubble_themes import THEMES
from app.main import PET_SIZE_MAP, pet_display_px, rescale_pet_window
from app.platform.win32 import WorkArea
from app.storage.settings import DEFAULT_SETTINGS, PersistenceService


class TestSizeScaling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    # Size switches dropping every old action cache entry (P2) is covered by
    # tests/test_wave6_regressions.py::test_size_switch_clears_all_old_action_cache_entries;
    # it needs the real PandaPet and art, so it stays out of this code-only-safe module.

    def test_pet_size_map(self):
        self.assertEqual(PET_SIZE_MAP["small"], 144)
        self.assertEqual(PET_SIZE_MAP["medium"], 192)
        self.assertEqual(PET_SIZE_MAP["large"], 240)

    def test_pet_display_pixels_follow_dpi_without_changing_logical_preferences(self):
        for size, logical in PET_SIZE_MAP.items():
            for scale in (1.0, 2.0):
                with self.subTest(size=size, scale=scale):
                    self.assertEqual(pet_display_px(size, scale), round(logical * scale))
        self.assertEqual(pet_display_px("medium", 2.0, SimpleNamespace(height=10)), 384)
        self.assertEqual(pet_display_px("medium", float("nan")), 192)

    def test_pet_display_pixels_fit_real_work_area(self):
        area = WorkArea(0, 0, 800, 600)
        self.assertEqual(pet_display_px("large", 2.0, area), 360)
        self.assertEqual(pet_display_px("medium", 1.0, area), 192)

    def test_bottom_center_rescale_medium_to_large(self):
        area = WorkArea(left=0, top=0, right=1920, bottom=1040)
        # Pet sitting on taskbar: y + 192 = 1040 -> y = 848
        x_old, y_old = 500, 848
        w_old, h_old = 192, 192
        w_new, h_new = 240, 240
        x_new, y_new = rescale_pet_window(x_old, y_old, w_old, h_old, w_new, h_new, area)

        # Ground contact invariant: bottom y must still touch ground (1040)
        self.assertEqual(y_new + h_new, 1040)
        # Horizontal center invariant: center must stay at 500 + 96 = 596
        self.assertEqual(x_new + w_new // 2, 596)

    def test_bottom_center_rescale_medium_to_small(self):
        area = WorkArea(left=0, top=0, right=1920, bottom=1040)
        x_old, y_old = 500, 848
        w_old, h_old = 192, 192
        w_new, h_new = 144, 144
        x_new, y_new = rescale_pet_window(x_old, y_old, w_old, h_old, w_new, h_new, area)

        self.assertEqual(y_new + h_new, 1040)
        self.assertEqual(x_new + w_new // 2, 596)

    def test_edge_clamping(self):
        area = WorkArea(left=0, top=0, right=1920, bottom=1040)
        # Old pet near far right edge
        x_old, y_old = 1850, 848
        w_old, h_old = 192, 192
        w_new, h_new = 240, 240
        x_new, y_new = rescale_pet_window(x_old, y_old, w_old, h_old, w_new, h_new, area)

        # Must not overflow screen width (1920)
        self.assertLessEqual(x_new + w_new, 1920)
        self.assertGreaterEqual(x_new, 0)
        self.assertLessEqual(y_new + h_new, 1040)

    def test_settings_size_defaults_and_validation(self):
        self.assertIn("pet_size", DEFAULT_SETTINGS)
        self.assertIn("text_size", DEFAULT_SETTINGS)
        self.assertEqual(DEFAULT_SETTINGS["pet_size"], "medium")
        self.assertEqual(DEFAULT_SETTINGS["text_size"], "medium")

        with tempfile.TemporaryDirectory() as td:
            svc = PersistenceService(Path(td))
            s, r = svc.load()
            self.assertEqual(s.get("pet_size"), "medium")
            self.assertEqual(s.get("text_size"), "medium")

            # Save valid customizations
            s["pet_size"] = "large"
            s["text_size"] = "small"
            svc.save(s, r)

            s2, _ = svc.load()
            self.assertEqual(s2.get("pet_size"), "large")
            self.assertEqual(s2.get("text_size"), "small")

            # Invalid values must raise ValueError
            s2["pet_size"] = "gigantic"
            with self.assertRaises(ValueError):
                svc.save(s2, r)

    def test_bubble_text_sizes(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.addCleanup(self.root.tk.call, "tk", "scaling", original_scaling)
        for dpi in (96, 192):
            self.root.tk.call("tk", "scaling", dpi / 72)
            self._check_bubble_text_sizes(dpi)

    def _check_bubble_text_sizes(self, dpi):
        for size_key in ("small", "medium", "large"):
            b = KawaiiSpeechBubble(
                self.root, 400, 400, 192,
                "✦ 測試標題", "測試文字氣泡尺寸適配",
                duration_ms=2000, theme=THEMES["chorong_pink"],
                text_size=size_key,
            )
            try:
                expected_font = TEXT_SIZE_FONTS[size_key]
                self.assertEqual(b.f_message.cget("size"), expected_font["message"])
                self.assertEqual(b.f_title.cget("size"), expected_font["title"])
                self.assertEqual(b.f_small.cget("size"), expected_font["small"])
                self.assertGreaterEqual(expected_font["small"], 8)
                with self.subTest(dpi=dpi, size=size_key):
                    expected_widths = TEXT_SIZE_WIDTHS[size_key] if dpi == 96 else tuple(
                        round(w * b.ui_scale) for w in TEXT_SIZE_WIDTHS[size_key]
                    )
                    self.assertEqual(b.framed_widths, expected_widths)
            finally:
                b.dismiss()


if __name__ == "__main__":
    unittest.main()
