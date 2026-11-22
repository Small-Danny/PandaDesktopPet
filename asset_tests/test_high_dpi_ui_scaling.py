"""tests/test_high_dpi_ui_scaling.py — Regression checks for 96 DPI and 192 DPI (200%) UI scaling."""
from __future__ import annotations

import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.birthday_dialog import BirthdayDialog  # noqa: E402
from app.main import SETTINGS_DEFAULTS  # noqa: E402
from app.new_year_countdown import NewYearCountdown, TITLES as COUNTDOWN_TITLES  # noqa: E402
from app.pink_context_menu import (  # noqa: E402
    NotificationDrawerWindow,
    PinkContextMenu,
    build_pet_context_menu_items,
)
from app.platform.win32 import ui_scale  # noqa: E402
from app.profile_card import AVATAR_BOX_W, AVATAR_DISPLAY_PX, MemberProfileCard  # noqa: E402
from app.settings_panel import SettingsPanel  # noqa: E402
from app.status_card import PandaStatusCard  # noqa: E402


class _DummyMenuPet:
    lang = "zh_TW"
    char_key = "chorong"
    state = "idle"
    mode = "manual"
    hotkey_str = "Ctrl+Shift+S"
    settings = {
        "cameo_enabled": True,
        "standby_lock_workstation": True,
        "notify_privacy_mode": False,
        "notify_relay": True,
    }
    recent_notifications = [
        {"app_name": "LINE", "title": "Apink Official", "body": "2026 Concert"},
    ]

    def get_auto_character(self) -> str:
        return "chorong"

    def is_autostart_enabled(self) -> bool:
        return False

    def available_special_actions(self, member: str) -> tuple[str, ...]:
        return ("special_gorilla",) if member == "bomi" else ()


class HighDpiUiScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._prev_data_dir = os.environ.get("PANDA_DATA_DIR")
        os.environ["PANDA_DATA_DIR"] = cls._tmp_dir.name
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.root.tk.call("tk", "scaling", 96 / 72)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.root.destroy()
        finally:
            if cls._prev_data_dir is None:
                os.environ.pop("PANDA_DATA_DIR", None)
            else:
                os.environ["PANDA_DATA_DIR"] = cls._prev_data_dir
            cls._tmp_dir.cleanup()

    def _set_dpi(self, dpi: int) -> float:
        self.root.tk.call("tk", "scaling", dpi / 72)
        self.addCleanup(self.root.tk.call, "tk", "scaling", 96 / 72)
        return ui_scale(self.root)

    def _assert_all_text_inside_canvas(self, canvas: tk.Canvas, w: int, h: int, label: str) -> None:
        canvas.update_idletasks()
        for item in canvas.find_all():
            if canvas.type(item) != "text":
                continue
            bbox = canvas.bbox(item)
            self.assertIsNotNone(bbox, f"Missing bbox in {label}")
            x1, y1, x2, y2 = bbox
            txt = canvas.itemcget(item, "text")
            self.assertGreaterEqual(x1, 0, f"{label} left overflow {bbox} for {txt!r}")
            self.assertGreaterEqual(y1, 0, f"{label} top overflow {bbox} for {txt!r}")
            self.assertLessEqual(x2, w, f"{label} right overflow {bbox} > {w} for {txt!r}")
            self.assertLessEqual(y2, h, f"{label} bottom overflow {bbox} > {h} for {txt!r}")

    def test_countdown_no_tofu_and_scales_at_96_and_192_dpi(self) -> None:
        for dpi in (96, 192):
            scale = self._set_dpi(dpi)
            for lang in ("zh_TW", "ko", "en"):
                self.assertNotIn("🎆", COUNTDOWN_TITLES[lang])
                with self.subTest(dpi=dpi, lang=lang):
                    cd = NewYearCountdown(
                        self.root, 10, (400, 400, 192, 192), (0, 0, 1920, 1080), lang, lambda: None,
                    )
                    self.addCleanup(cd.cancel)
                    self.assertEqual(cd.width, round(220 * scale))
                    self.assertEqual(cd.height, round(112 * scale))
                    self._assert_all_text_inside_canvas(cd.canvas, cd.width, cd.height, f"countdown_{dpi}_{lang}")

    def test_birthday_dialog_scales_cleanly_at_96_and_192_dpi(self) -> None:
        for dpi in (96, 192):
            scale = self._set_dpi(dpi)
            for lang in ("zh_TW", "ko", "en"):
                with self.subTest(dpi=dpi, lang=lang):
                    dlg = BirthdayDialog(self.root, (4, 19), "Panda", lambda *_a: None, lang=lang)
                    self.addCleanup(dlg.close)
                    self.assertEqual(dlg.w, round(420 * scale))
                    self.assertEqual(dlg.h, round(290 * scale))
                    self._assert_all_text_inside_canvas(dlg.canvas, dlg.w, dlg.h, f"birthday_{dpi}_{lang}")
                    dlg.refresh_theme("eunji", lang=lang)
                    self.assertEqual(dlg.w, round(420 * scale))
                    self._assert_all_text_inside_canvas(dlg.canvas, dlg.w, dlg.h, f"birthday_refresh_{dpi}_{lang}")

    def test_profile_card_scales_and_keeps_avatar_greet_hitbox_at_192_dpi(self) -> None:
        scale = self._set_dpi(192)
        self.assertAlmostEqual(scale, 2.0, places=2)
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                card = MemberProfileCard(self.root, initial_member="eunji", lang=lang)
                self.addCleanup(card.close)
                self.assertEqual(card.w, round(520 * scale))
                self.assertEqual(card.h, round(430 * scale))
                bounds = card.avatar_bounds()
                self.assertIsNotNone(bounds)
                self.assertEqual(bounds[2], round(AVATAR_BOX_W * scale))
                self.assertIsNotNone(card._avatar_photo)
                self.assertEqual(card._avatar_photo.height(), round(AVATAR_DISPLAY_PX * scale))
                self._assert_all_text_inside_canvas(card.canvas, card.w, card.h, f"profile_{lang}")

                gx, gy = round(120 * scale), round(294 * scale)
                items = card.canvas.find_overlapping(gx, gy, gx, gy)
                self.assertTrue(any("btn_greet" in card.canvas.gettags(it) for it in items))
                ev = type("MockEvent", (), {"x": gx, "y": gy})()
                card._on_drag_begin(ev)
                self.assertIsNone(card.drag_offset_x)

    def test_status_card_scales_at_192_dpi_without_clipping(self) -> None:
        scale = self._set_dpi(192)
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                card = PandaStatusCard(
                    self.root,
                    char_key="chorong",
                    char_name="初瓏 (Chorong)",
                    badge_desc="🌸 溫暖隊長 ｜ 🥋 合氣道三段 ｜ 🐱 貓咪控",
                    passion_points=120,
                    companion_start_time=0.0,
                    total_companion_seconds=7200,
                    feed_count=8,
                    anchor_x=300,
                    anchor_y=300,
                    lang=lang,
                )
                self.addCleanup(card.close)
                self.assertEqual(card.w, round(470 * scale))
                self.assertEqual(card.h, round(400 * scale))
                self.assertEqual(card.avatar_frames[0].width(), round(76 * scale))
                self._assert_all_text_inside_canvas(card.canvas, card.w, card.h, f"status_{lang}")

    def test_settings_panel_scales_both_tabs_at_192_dpi(self) -> None:
        scale = self._set_dpi(192)
        store = dict(SETTINGS_DEFAULTS["appearance"], **SETTINGS_DEFAULTS["reminders"])
        for lang in ("zh_TW", "ko", "en"):
            for tab in ("appearance", "reminders"):
                with self.subTest(lang=lang, tab=tab):
                    panel = SettingsPanel(
                        self.root, lang=lang, char_key="eunji", initial_tab=tab, state=store,
                        work_area=(0, 0, 3200, 2000),
                    )
                    self.addCleanup(panel.close)
                    self.assertEqual(panel.w, round(600 * scale))
                    self.assertEqual(panel.h, round(744 * scale))
                    self._assert_all_text_inside_canvas(panel.canvas, panel.w, panel.h, f"settings_{tab}_{lang}")

    def test_context_menu_and_drawer_scale_at_192_dpi(self) -> None:
        scale = self._set_dpi(192)
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                pet = _DummyMenuPet()
                pet.lang = lang
                items = build_pet_context_menu_items(pet)
                menu = PinkContextMenu(
                    self.root, lang=lang, char_key="bomi", items=items,
                    anchor_x=100, anchor_y=100, work_area=(0, 0, 3200, 2000),
                )
                self.addCleanup(menu.close)
                self.assertEqual(menu.w, round(316 * scale))
                self._assert_all_text_inside_canvas(menu.canvas, menu.w, menu.h, f"menu_{lang}")
                self.assertTrue(menu.activate_item(3))
                self.assertIsNotNone(menu._sub_canvas)
                self._assert_all_text_inside_canvas(
                    menu._sub_canvas, round(324 * scale), menu._sub_canvas.winfo_reqheight(), f"submenu_{lang}",
                )

                drawer = NotificationDrawerWindow(
                    self.root, lang=lang, char_key="namjoo", items=pet.recent_notifications,
                    work_area=(0, 0, 3200, 2000),
                )
                self.addCleanup(drawer.close)
                self.assertEqual(drawer.w, round(460 * scale))
                self.assertEqual(drawer.h, round(480 * scale))
                self._assert_all_text_inside_canvas(drawer.canvas, drawer.w, drawer.h, f"drawer_{lang}")


if __name__ == "__main__":
    unittest.main()
