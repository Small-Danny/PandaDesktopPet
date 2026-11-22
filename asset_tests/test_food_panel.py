"""tests/test_food_panel.py — Unit & UI tests for FoodCafePanel (粉熊美食小食堂)."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import tkinter as tk
from tkinter import font as tkfont
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import food_log
from app.food_panel import FoodCafePanel, filter_foods_by_tab
from app.foods import DRINK_KINDS, FOOD_ITEMS, get_food_kind


class TestFoodCafePanel(unittest.TestCase):
    def test_tile_labels_fit_without_ellipsis_at_96_and_192_dpi(self):
        previous = self.root.tk.call("tk", "scaling")
        self.addCleanup(self.root.tk.call, "tk", "scaling", previous)
        for dpi in (96, 192):
            self.root.tk.call("tk", "scaling", dpi / 72)
            font = tkfont.Font(self.root, family="Microsoft JhengHei UI", size=8, weight="bold")
            for lang in ("zh_TW", "ko", "en"):
                view = SimpleNamespace(lang=lang, ui_scale=dpi / 96, _label_font=font)
                view._fit_tile_label = lambda text: FoodCafePanel._fit_tile_label(view, text)
                labels = {food["id"]: FoodCafePanel._tile_label(view, food) for food in FOOD_ITEMS}
                for food_id, label in labels.items():
                    with self.subTest(dpi=dpi, lang=lang, food=food_id):
                        self.assertNotIn("…", label)
                        self.assertLessEqual(len(label.splitlines()), 2)
                        self.assertTrue(all(font.measure(line) <= 78 * view.ui_scale for line in label.splitlines()))
                self.assertNotEqual(labels["tw_white_soymilk"], labels["tw_black_soymilk"])

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.root.destroy()
        except tk.TclError:
            pass

    def _tile_texts(self, panel: FoodCafePanel, food_id: str) -> list[str]:
        cv = panel.canvas
        items = cv.find_withtag(f"food_{food_id}")
        texts = []
        for item in items:
            if cv.type(item) == "text":
                texts.append(cv.itemcget(item, "text"))
        return texts

    def test_category_tabs_match_get_food_kind_and_preserve_order(self) -> None:
        all_foods = filter_foods_by_tab("all")
        meals = filter_foods_by_tab("meal")
        desserts = filter_foods_by_tab("dessert")
        drinks = filter_foods_by_tab("drink")

        self.assertEqual([f["id"] for f in all_foods], [f["id"] for f in FOOD_ITEMS])
        self.assertEqual(len(meals) + len(desserts) + len(drinks), len(FOOD_ITEMS))
        self.assertTrue(all(get_food_kind(f) == "meal" for f in meals))
        self.assertTrue(all(get_food_kind(f) == "dessert" for f in desserts))
        self.assertTrue(all(get_food_kind(f) in DRINK_KINDS for f in drinks))

    def test_locked_foods_hide_favorite_and_disliked_spoilers(self) -> None:
        panel = FoodCafePanel(
            self.root,
            lang="zh_TW",
            char_key="eunji",
            satiety_getter=lambda: 60.0,
            outcomes={},
            on_feed=lambda _fid: "normal",
            on_close=lambda: None,
        )
        try:
            for item in FOOD_ITEMS:
                fid = item["id"]
                self.assertIsNone(panel.get_tile_badge(fid))
                texts = " ".join(self._tile_texts(panel, fid))
                self.assertNotIn("💖", texts)
                self.assertNotIn("本命", texts)
                self.assertNotIn("⚡", texts)
                self.assertNotIn("避雷", texts)
                self.assertNotIn("✓", texts)
        finally:
            panel.close()

    def test_outcomes_dict_maps_stamps_and_overrides_static_favorites(self) -> None:
        # matcha_cake is in Chorong's static FOOD_ITEMS['favorites'], but outcomes says 'normal':
        # panel must strictly trust outcomes ('normal' -> 'tasted') and never infer from FOOD_ITEMS.
        outcomes_in = {
            "matcha_cake": "normal",
            "waffle": "favourite",
            "chicken_breast": "disliked",
        }
        panel = FoodCafePanel(
            self.root,
            lang="zh_TW",
            char_key="chorong",
            satiety_getter=lambda: 45.0,
            outcomes=outcomes_in,
            on_feed=lambda _fid: None,
            on_close=lambda: None,
        )
        try:
            self.assertEqual(panel.get_tile_badge("matcha_cake"), "tasted")
            self.assertEqual(panel.get_tile_badge("waffle"), "favorite")
            self.assertEqual(panel.get_tile_badge("chicken_breast"), "disliked")
            self.assertIsNone(panel.get_tile_badge("chicken_feet"))

            self.assertFalse(any("✓" in t for t in self._tile_texts(panel, "matcha_cake")))
            self.assertFalse(any("💖" in t for t in self._tile_texts(panel, "matcha_cake")))
            panel.select_tab("dessert")      # no "all" tab any more: waffle is a dessert
            self.assertTrue(any("💖" in t for t in self._tile_texts(panel, "waffle")))
            panel.select_tab("meal")
            self.assertTrue(any("⚡" in t for t in self._tile_texts(panel, "chicken_breast")))

            # Verify meal tab does not hardcode "韓式"
            meal_tab_texts = [
                panel.canvas.itemcget(i, "text")
                for i in panel.canvas.find_withtag("tab_meal")
                if panel.canvas.type(i) == "text"
            ]
            self.assertTrue(any("美味主食" in t for t in meal_tab_texts))
            self.assertFalse(any("韓式" in t for t in meal_tab_texts))

            # Refresh with food_log.outcomes(runtime, 'eunji')
            runtime: dict = {}
            food_log.record(runtime, "eunji", "egg", "favourite", 2000.0)
            food_log.record(runtime, "eunji", "mint_choco", "disliked", 2001.0)
            panel.refresh(char_key="eunji", outcomes=food_log.outcomes(runtime, "eunji"))
            self.assertEqual(panel.get_tile_badge("egg"), "favorite")
            self.assertEqual(panel.get_tile_badge("mint_choco"), "disliked")
            self.assertIsNone(panel.get_tile_badge("matcha_cake"))
        finally:
            panel.close()

    def test_trigger_feed_does_not_self_stamp_until_refresh(self) -> None:
        external_outcomes: dict[str, str] = {}
        fed_calls: list[str] = []
        closed_calls: list[bool] = []

        def fake_on_feed(fid: str) -> str:
            fed_calls.append(fid)
            # Even if external_outcomes is mutated before a save failure rollback,
            # trigger_feed must NOT self-stamp without an explicit refresh(outcomes=...).
            external_outcomes[fid] = "favourite"
            return "refused_full" if fid == "sweet_potato" else "favourite"

        panel = FoodCafePanel(
            self.root,
            lang="ko",
            char_key="hayoung",
            satiety_getter=lambda: 98.0,
            outcomes=external_outcomes,
            on_feed=fake_on_feed,
            on_close=lambda: closed_calls.append(True),
        )
        try:
            res1 = panel.trigger_feed("sweet_potato")
            self.assertEqual(res1, "refused_full")
            self.assertIsNone(panel.get_tile_badge("sweet_potato"))

            res2 = panel.trigger_feed("americano")
            self.assertEqual(res2, "favourite")
            # Still None until main calls refresh(outcomes=...) after save succeeds!
            self.assertIsNone(panel.get_tile_badge("americano"))

            panel.refresh(outcomes={"americano": "favourite"})
            self.assertEqual(panel.get_tile_badge("americano"), "favorite")
            self.assertEqual(fed_calls, ["sweet_potato", "americano"])
        finally:
            panel.close()
        self.assertEqual(len(closed_calls), 1)

    def test_work_area_negative_monitor_clamping_and_header_no_overlap(self) -> None:
        # A 1920x1040 logical work area, expressed in the same physical pixels
        # as the DPI-aware panel (also works when app.main enabled 200% DPI).
        k = max(1.0, min(4.0, self.root.winfo_fpixels("1i") / 96.0))
        left, bottom = -round(1920 * k), round(1040 * k)
        panel = FoodCafePanel(
            self.root,
            lang="zh_TW",
            char_key="chorong",
            satiety_getter=lambda: 98.0,
            outcomes={"matcha_cake": "favourite"},
            on_feed=lambda _fid: None,
            on_close=lambda: None,
            work_area=(left, 0, 0, bottom),
        )
        try:
            panel.window.update()
            x = panel.window.winfo_rootx()
            y = panel.window.winfo_rooty()
            w = panel.window.winfo_width()
            h = panel.window.winfo_height()
            self.assertEqual((w, h), (panel.w, panel.h))
            self.assertGreaterEqual(x, left)
            self.assertLessEqual(x + w, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y + h, bottom)

            # Verify no bbox overlap between satiety_full_hint and pokedex_pill across all 3 langs
            for lang in ("zh_TW", "ko", "en"):
                panel.set_language(lang)
                panel.window.update_idletasks()
                hint_box = panel.canvas.bbox("satiety_full_hint")
                pill_box = panel.canvas.bbox("pokedex_pill")
                self.assertIsNotNone(hint_box)
                self.assertIsNotNone(pill_box)
                # Ensure boxes do not intersect horizontally and vertically at the same time
                horiz_overlap = min(hint_box[2], pill_box[2]) > max(hint_box[0], pill_box[0])
                vert_overlap = min(hint_box[3], pill_box[3]) > max(hint_box[1], pill_box[1])
                self.assertFalse(
                    horiz_overlap and vert_overlap,
                    f"Overlap in {lang}: hint={hint_box}, pill={pill_box}",
                )

                # Also check 5th row bottom does not touch footer_bar top
                last_fid = FOOD_ITEMS[FoodCafePanel.COLS * FoodCafePanel.VISIBLE_ROWS - 1]["id"]
                last_tile_box = panel.canvas.bbox(f"food_{last_fid}")
                footer_box = panel.canvas.bbox("footer_bar")
                self.assertIsNotNone(last_tile_box)
                self.assertIsNotNone(footer_box)
                self.assertLess(last_tile_box[3], footer_box[1])
        finally:
            panel.close()

    def test_pil_icon_cache_accelerates_reopen_and_isolates_across_tk_roots(self) -> None:
        from unittest import mock
        from app.food_panel import _FOOD_ICON_PIL_CACHE

        panel1 = FoodCafePanel(self.root, lang="zh_TW", char_key="chorong")
        self.assertGreater(len(_FOOD_ICON_PIL_CACHE), 0)
        panel1.close()

        # Second open hits _FOOD_ICON_PIL_CACHE with zero open_resource_image calls
        with mock.patch("app.food_panel.open_resource_image") as m_open:
            panel2 = FoodCafePanel(self.root, lang="ko", char_key="bomi")
            self.assertEqual(m_open.call_count, 0)
            self.assertGreater(len(panel2._icon_cache), 0)
            panel2.close()

        # Simulate a brand-new Tk root after the previous one was destroyed:
        # PhotoImage instances must be bound to the new window without TclError.
        second_root = tk.Toplevel(self.root)
        second_root.withdraw()
        try:
            panel3 = FoodCafePanel(second_root, lang="en", char_key="eunji")
            self.assertGreater(len(panel3._icon_cache), 0)
            panel3.close()
        finally:
            second_root.destroy()


if __name__ == "__main__":
    unittest.main()
