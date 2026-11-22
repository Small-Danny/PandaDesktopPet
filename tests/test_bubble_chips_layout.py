"""tests/test_bubble_chips_layout.py — Regression verification for 3-chip single-row layout across all 5 members.

Verifies:
1. All 5 members (Chorong, Bomi, Eunji, Namjoo, Hayoung) in Chinese (zh_TW) fit their 3 profile chips
   on a single row without the 3rd chip dropping down to an orphan row.
2. The dynamic padding/gap allocation prevents overshoot at intermediate candidate widths.
3. Framed speech bubble automatically selects a width where chips stay on a single line.
"""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bubble import KawaiiSpeechBubble
from app.bubble_themes import THEMES
from app.personalities import MEMBER_INFO


class TestBubbleChipsLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()
        # The bubble widths are 96-DPI pixels. Tk takes its scaling from the display when
        # the first root is made, and that changes once anything has imported app.main
        # (SetProcessDpiAwareness, process-wide): pin the design DPI so order can't matter.
        cls.root.tk.call("tk", "scaling", 96 / 72)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def test_all_five_members_single_row_chips_zh_tw(self) -> None:
        """Every member's 3 badges in Traditional Chinese must fit on a single row."""
        member_themes = {
            "chorong": "chorong_pink",
            "bomi": "bomi_coral",
            "eunji": "eunji_comic",
            "namjoo": "namjoo_purple",
            "hayoung": "hayoung_yellow",
        }

        for member, theme_key in member_themes.items():
            theme = THEMES[theme_key]
            badge_str = MEMBER_INFO[member]["badges"]["zh_TW"]
            b = KawaiiSpeechBubble(
                self.root, 500, 500, 192,
                header=f"✦ {member}",
                message="測試對話氣泡單行排版",
                sub_badge=badge_str,
                theme=theme,
                text_size="medium",
            )
            try:
                # Get distinct Y positions of rendered chip boxes
                chip_y_coords = {box[1] for box in b.chip_boxes}
                self.assertEqual(
                    len(chip_y_coords), 1,
                    f"Member '{member}' ({theme_key}) has {len(chip_y_coords)} chip rows: {b.chip_boxes}"
                )
                self.assertEqual(len(b.chip_boxes), 3, f"Expected 3 chip boxes for {member}")
            finally:
                b.dismiss()

    def test_korean_chips_layout_no_orphan_rows_when_possible(self) -> None:
        """Korean chips for Chorong, Bomi, Namjoo, Hayoung fit on 1 row."""
        for member, theme_key in [
            ("chorong", "chorong_pink"),
            ("bomi", "bomi_coral"),
            ("namjoo", "namjoo_purple"),
            ("hayoung", "hayoung_yellow"),
        ]:
            theme = THEMES[theme_key]
            badge_str = MEMBER_INFO[member]["badges"]["ko"]
            b = KawaiiSpeechBubble(
                self.root, 500, 500, 192,
                header=f"✦ {member}",
                message="테스트 메시지입니다",
                sub_badge=badge_str,
                theme=theme,
                text_size="medium",
            )
            try:
                chip_y_coords = {box[1] for box in b.chip_boxes}
                self.assertEqual(
                    len(chip_y_coords), 1,
                    f"Member '{member}' in Korean has {len(chip_y_coords)} chip rows: {b.chip_boxes}"
                )
            finally:
                b.dismiss()

    def test_all_five_members_single_row_chips_at_192_dpi(self) -> None:
        """At 200% Windows DPI (192 DPI), chip row counts match 96 DPI and single-row badges stay 1 row."""
        member_themes = {
            "chorong": "chorong_pink",
            "bomi": "bomi_coral",
            "eunji": "eunji_comic",
            "namjoo": "namjoo_purple",
            "hayoung": "hayoung_yellow",
        }
        single_row_ko = {"chorong", "bomi", "namjoo", "hayoung"}
        rows_96: dict[tuple[str, str], int] = {}
        self.root.tk.call("tk", "scaling", 96 / 72)
        for member, theme_key in member_themes.items():
            for lang in ("zh_TW", "ko"):
                b = KawaiiSpeechBubble(
                    self.root, 500, 500, 192,
                    header=f"✦ {member}",
                    message="96 DPI baseline",
                    sub_badge=MEMBER_INFO[member]["badges"][lang],
                    theme=THEMES[theme_key],
                    text_size="medium",
                )
                try:
                    rows_96[(member, lang)] = len({box[1] for box in b.chip_boxes})
                finally:
                    b.dismiss()

        self.root.tk.call("tk", "scaling", 192 / 72)
        self.addCleanup(self.root.tk.call, "tk", "scaling", 96 / 72)
        for member, theme_key in member_themes.items():
            for lang in ("zh_TW", "ko"):
                with self.subTest(member=member, lang=lang):
                    b = KawaiiSpeechBubble(
                        self.root, 500, 500, 192,
                        header=f"✦ {member}",
                        message="192 DPI scaling check",
                        sub_badge=MEMBER_INFO[member]["badges"][lang],
                        theme=THEMES[theme_key],
                        text_size="medium",
                    )
                    try:
                        chip_y_coords = {box[1] for box in b.chip_boxes}
                        if lang == "zh_TW" or member in single_row_ko:
                            self.assertEqual(len(chip_y_coords), 1, f"{member} {lang} wrapped at 192 DPI: {b.chip_boxes}")
                        else:
                            self.assertLessEqual(
                                len(chip_y_coords),
                                rows_96[(member, lang)],
                                f"{member} {lang} regressed rows at 192 DPI: {len(chip_y_coords)} > {rows_96[(member, lang)]}",
                            )
                    finally:
                        b.dismiss()


if __name__ == "__main__":
    unittest.main()
