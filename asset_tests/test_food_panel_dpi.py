"""Food Cafe geometry and real Canvas hit-testing at multiple Tk DPI settings.

Changes only this test interpreter's Tk scaling. No PandaPet instance, settings,
system DPI setting, or native desktop positioning is used.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.food_panel import FoodCafePanel
from app.platform.win32 import WorkArea


class FoodPanelDpiTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    @contextmanager
    def panel(self, dpi=192, lang="zh_TW", **callbacks):
        self.root.tk.call("tk", "scaling", dpi / 72)
        # No SetWindowPos calls and no visible panel over the user's work.
        with patch.object(FoodCafePanel, "_position_near_parent", lambda panel: None):
            panel = FoodCafePanel(
                self.root,
                lang=lang,
                char_key="eunji",
                work_area=WorkArea(0, 0, 3840, 2160),
                **callbacks,
            )
        panel.window.attributes("-topmost", False)
        panel.window.geometry(f"{panel.w}x{panel.h}+-10000+-10000")
        panel.window.update_idletasks()
        try:
            yield panel
        finally:
            panel.close()

    def test_geometry_images_headers_and_food_labels_across_three_languages_and_dpis(self):
        for dpi in (96, 144, 192):
            for lang in ("zh_TW", "ko", "en"):
                with self.subTest(dpi=dpi, lang=lang), self.panel(dpi, lang) as panel:
                    k = panel.ui_scale
                    self.assertAlmostEqual(k, dpi / 96, delta=.01)
                    self.assertEqual((panel.window.winfo_width(), panel.window.winfo_height()),
                                     (round(612 * k), round(658 * k)))
                    self.assertEqual((int(panel.canvas.cget("width")), int(panel.canvas.cget("height"))),
                                     (panel.w, panel.h))
                    self.assertTrue(panel._icon_cache)
                    self.assertEqual({(image.width(), image.height()) for image in panel._icon_cache.values()},
                                     {(round(46 * k), round(46 * k))})
                    cv = panel.canvas
                    texts = [i for i in cv.find_all() if cv.type(i) == "text"]
                    title = min(texts, key=lambda i: abs(cv.coords(i)[0] - 34 * k)
                                + abs(cv.coords(i)[1] - 37 * k))
                    member = min(texts, key=lambda i: abs(cv.coords(i)[0] - 235 * k)
                                 + abs(cv.coords(i)[1] - 38 * k))
                    self.assertLess(cv.bbox(title)[2], cv.bbox(member)[0])
                    for tab in panel.TABS:
                        panel.select_tab(tab)
                        # Covers every label, including long English/Korean names
                        # and the last row of the 30-item meal category.
                        for scroll in range(panel._max_scroll + 1):
                            panel.scroll_rows(scroll - panel._scroll_row)
                            for item in cv.find_all():
                                if cv.type(item) != "text":
                                    continue
                                tags = [tag for tag in cv.gettags(item) if tag.startswith("food_")]
                                if not tags:
                                    continue
                                polygons = [i for i in cv.find_withtag(tags[0]) if cv.type(i) == "polygon"]
                                self.assertEqual(len(polygons), 1)
                                tile, label = cv.bbox(polygons[0]), cv.bbox(item)
                                self.assertGreaterEqual(label[0], tile[0])
                                self.assertLessEqual(label[2], tile[2])
                                self.assertGreaterEqual(label[1], tile[1])
                                self.assertLessEqual(label[3], tile[3])

    def test_refresh_and_scroll_do_not_accumulate_coordinate_scaling(self):
        with self.panel() as panel:
            cv = panel.canvas
            original_close = cv.coords(cv.find_withtag("btn_close")[0])
            for _ in range(3):
                panel.refresh()
                panel.select_tab("dessert")
                panel.select_tab("meal")
                panel.scroll_rows(1)
                panel.scroll_rows(-1)
                self.assertEqual(cv.coords(cv.find_withtag("btn_close")[0]), original_close)

    @staticmethod
    def click(canvas, x, y):
        # Motion establishes Tk's real "current" item; ButtonPress dispatches
        # the tag binding at the same scaled pixel, without calling the callback.
        canvas.event_generate("<Motion>", x=round(x), y=round(y))
        canvas.event_generate("<ButtonPress-1>", x=round(x), y=round(y))
        if canvas.winfo_exists():  # The close button intentionally destroys it on press.
            canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
            canvas.update_idletasks()

    def test_scaled_canvas_clicks_select_tab_feed_and_close(self):
        for dpi in (96, 144, 192):
            fed, closed = [], []
            with self.subTest(dpi=dpi), self.panel(dpi, on_feed=fed.append,
                                                  on_close=lambda: closed.append(True)) as panel:
                panel.window.update()
                k, cv = panel.ui_scale, panel.canvas
                self.click(cv, 296 * k, 131 * k)
                self.assertEqual(panel.active_tab, "dessert")
                self.click(cv, 66 * k, 188 * k)
                self.assertEqual(fed, [panel.get_visible_foods()[0]["id"]])
                self.assertFalse(panel._dragging)
                self.click(cv, 569 * k, 38 * k)
                self.assertTrue(panel._closed)
                self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
