"""tests/test_settings_panel.py — Unit tests for the Default + Custom SettingsPanel UI.

Run:  python -m unittest tests.test_settings_panel -v
"""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import SETTINGS_DEFAULTS, clean_reminder_text  # noqa: E402
from app.settings_panel import SettingsPanel, THEME_KEYS_ORDER  # noqa: E402


class SettingsPanelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_appearance_tab_default_and_custom_selections_via_ssot_refresh(self) -> None:
        changes: list[tuple[str, object]] = []
        resets: list[str] = []
        store = dict(SETTINGS_DEFAULTS["appearance"], **SETTINGS_DEFAULTS["reminders"])
        panel_ref: list[SettingsPanel] = []

        def on_change(k: str, v: object) -> bool:
            changes.append((k, v))
            store[k] = v
            panel_ref[0].refresh(state=store)
            return True

        def on_reset(sec: str) -> bool:
            resets.append(sec)
            store.update(SETTINGS_DEFAULTS[sec])
            panel_ref[0].refresh(state=store)
            return True

        panel = SettingsPanel(
            self.root,
            lang="zh_TW",
            char_key="chorong",
            state=store,
            on_change=on_change,
            on_reset=on_reset,
        )
        panel_ref.append(panel)
        self.addCleanup(panel.close)

        self.assertTrue(panel.is_section_default("appearance"))
        self.assertEqual(len(THEME_KEYS_ORDER), 9)

        texts = [
            panel.canvas.itemcget(i, "text")
            for i in panel.canvas.find_all()
            if panel.canvas.type(i) == "text"
        ]
        joined = "\n".join(texts)
        self.assertIn("草莓馬卡龍甜點風", joined)
        self.assertIn("丁香紫霧優雅風", joined)

        self.assertTrue(panel.apply_change("bubble_theme", "ruby_velvet"))
        self.assertFalse(panel.is_section_default("appearance"))
        self.assertEqual(panel.state["bubble_theme"], "ruby_velvet")

        self.assertTrue(panel.apply_change("pet_size", "large"))
        self.assertTrue(panel.apply_change("text_size", "small"))
        self.assertEqual(
            changes,
            [("bubble_theme", "ruby_velvet"), ("pet_size", "large"), ("text_size", "small")],
        )

        self.assertTrue(panel.reset_section("appearance"))
        self.assertEqual(resets, ["appearance"])
        self.assertTrue(panel.is_section_default("appearance"))
        self.assertEqual(panel.state["bubble_theme"], "auto")

    def test_reminders_tab_preserves_controller_normalized_ssot_and_previews(self) -> None:
        changes: list[tuple[str, object]] = []
        previews: list[str] = []
        store = dict(SETTINGS_DEFAULTS["appearance"], **SETTINGS_DEFAULTS["reminders"])
        panel_ref: list[SettingsPanel] = []

        def on_change(k: str, v: object) -> bool:
            if k == "sedentary_message":
                cleaned = clean_reminder_text(v)
                if cleaned is None:
                    return False
                store[k] = cleaned
            else:
                store[k] = v
            changes.append((k, store[k]))
            panel_ref[0].refresh(state=store)
            return True

        panel = SettingsPanel(
            self.root,
            lang="zh_TW",
            char_key="eunji",
            initial_tab="reminders",
            state=store,
            on_change=on_change,
            on_preview=lambda kind: (previews.append(kind) or True),
        )
        panel_ref.append(panel)
        self.addCleanup(panel.close)

        self.assertEqual(panel.active_tab, "reminders")
        self.assertTrue(panel.is_section_default("reminders"))
        self.assertIsNotNone(panel.interval_entry)
        self.assertIsNotNone(panel.msg_entry)

        # Enter custom interval 75 minutes
        panel.interval_entry.delete(0, "end")
        panel.interval_entry.insert(0, "75")
        self.assertTrue(panel._submit_custom_interval())
        self.assertEqual(panel.state["sedentary_interval_min"], 75)
        self.assertFalse(panel.is_section_default("reminders"))

        # Enter padded custom reminder note -> controller strips it, panel keeps stripped SSOT!
        panel.msg_entry.delete(0, "end")
        panel.msg_entry.insert(0, "  記得喝水休息一下喔！\n ")
        self.assertTrue(panel._submit_custom_message())
        self.assertEqual(panel.state["sedentary_message"], "記得喝水休息一下喔！")
        self.assertEqual(panel.msg_entry.get(), "記得喝水休息一下喔！")

        # Toggle hourly chime
        self.assertTrue(panel.apply_change("hourly_chime", False))
        self.assertFalse(panel.state["hourly_chime"])

        # Preview reminder
        self.assertTrue(panel.trigger_preview("sedentary"))
        self.assertEqual(previews, ["sedentary"])

    def test_rejected_changes_and_negative_work_area_clamping(self) -> None:
        panel = SettingsPanel(
            self.root,
            initial_tab="reminders",
            on_change=lambda k, v: False,
            work_area=(-1920, 0, 0, 1080),
        )
        self.addCleanup(panel.close)

        # Placed inside the negative secondary monitor work area
        x, y = panel.last_clamped_pos
        self.assertGreaterEqual(x, -1920)
        self.assertLessEqual(x + panel.w, 0)

        panel.interval_entry.delete(0, "end")
        panel.interval_entry.insert(0, "999")
        self.assertFalse(panel._submit_custom_interval())
        self.assertEqual(panel.state["sedentary_interval_min"], 60)
        self.assertTrue(panel.canvas.find_withtag("interval_error_text"))

        panel.interval_entry.delete(0, "end")
        panel.interval_entry.insert(0, "not_an_int")
        self.assertFalse(panel._submit_custom_interval())
        self.assertEqual(panel.state["sedentary_interval_min"], 60)
        self.assertTrue(panel.canvas.find_withtag("interval_error_text"))

    def test_no_mo_ren_and_clear_bubble_only_scope_and_compact_work_area_fit(self) -> None:
        from app.settings_panel import PANEL_I18N
        for key, table in PANEL_I18N.items():
            self.assertNotIn("默認", table.get("zh_TW", ""), f"{key} still contains 默認")
        self.assertIn("說話氣泡", PANEL_I18N["sec_bubble_theme"]["zh_TW"])
        self.assertIn("說話氣泡", PANEL_I18N["sec_text_size"]["zh_TW"])

        for lang in ("zh_TW", "ko", "en"):
            panel = SettingsPanel(
                self.root,
                lang=lang,
                initial_tab="reminders",
                work_area=(0, 0, 1920, 1080),
            )
            self.addCleanup(panel.close)
            panel.canvas.update_idletasks()
            desc_box = panel.canvas.bbox("pet_first_desc")
            priv_box = panel.canvas.bbox("btn_toggle_privacy")
            self.assertIsNotNone(desc_box)
            self.assertIsNotNone(priv_box)
            self.assertLess(desc_box[3], priv_box[1], f"pet_first_desc overlaps privacy in {lang}")
            b60 = [panel.canvas.bbox(i) for i in panel.canvas.find_withtag("interval_60")]
            self.assertEqual(len(b60), 2)
            rect_box, txt_box = b60[0], b60[1]
            self.assertGreaterEqual(txt_box[0], rect_box[0])
            self.assertLessEqual(txt_box[2], rect_box[2])

    def test_all_nine_theme_cards_fit_without_clipping_or_wrapping_and_fast_refresh(self) -> None:
        for lang in ("zh_TW", "ko", "en"):
            for sel in ("auto", "classic", "chorong_pink"):
                panel = SettingsPanel(
                    self.root,
                    lang=lang,
                    initial_tab="appearance",
                    state={"bubble_theme": sel},
                    work_area=(0, 0, 1920, 1080),
                )
                self.addCleanup(panel.close)
                panel.canvas.update_idletasks()
                classic_txt = panel.canvas.itemcget("theme_txt_classic", "text")
                self.assertNotIn("(Classic)", classic_txt)
                for tkey in THEME_KEYS_ORDER:
                    bg_box = panel.canvas.bbox(f"theme_bg_{tkey}")
                    txt_box = panel.canvas.bbox(f"theme_txt_{tkey}")
                    self.assertIsNotNone(bg_box)
                    self.assertIsNotNone(txt_box)
                    self.assertGreaterEqual(txt_box[0], bg_box[0])
                    self.assertLessEqual(txt_box[2], bg_box[2] - round(4 * panel.ui_scale))
                    self.assertGreaterEqual(txt_box[1], bg_box[1])
                    self.assertLessEqual(txt_box[3], bg_box[3])
                    if tkey == "classic":
                        self.assertLessEqual((txt_box[3] - txt_box[1]) / panel.ui_scale, 22.0)

                # Same-tab state refresh updates in-place without rebuilding canvas items
                before_ids = panel.canvas.find_all()
                panel.refresh(state={"bubble_theme": "ruby_velvet", "pet_size": "large"})
                after_ids = panel.canvas.find_all()
                self.assertEqual(before_ids, after_ids)
                self.assertIn("✓", panel.canvas.itemcget("theme_txt_ruby_velvet", "text"))
                panel.close()

    def test_persistent_named_fonts_single_click_dispatcher_and_1366x728_high_dpi_fit(self) -> None:
        prev_scaling = self.root.tk.call("tk", "scaling")
        self.addCleanup(self.root.tk.call, "tk", "scaling", prev_scaling)
        for dpi in (96, 144, 192):
            self.root.tk.call("tk", "scaling", dpi / 72)
            for lang in ("zh_TW", "ko", "en"):
                for tab in ("appearance", "reminders"):
                    panel = SettingsPanel(
                        self.root,
                        lang=lang,
                        initial_tab=tab,
                        work_area=(0, 0, 1366, 728),
                    )
                    self.addCleanup(panel.close)
                    panel.canvas.update_idletasks()
                    self.assertGreater(len(panel._fonts), 0)
                    # Verify no tag_bind callbacks are attached on any tag
                    self.assertEqual(panel.canvas.tag_bind("btn_close"), ())
                    if tab == "reminders":
                        d_box = panel.canvas.bbox("pet_first_desc")
                        p_box = panel.canvas.bbox("btn_toggle_privacy")
                        self.assertLess(d_box[3], p_box[1], (dpi, lang, d_box, p_box))
                    for item in panel.canvas.find_all():
                        if panel.canvas.type(item) == "text":
                            x1, y1, x2, y2 = panel.canvas.bbox(item)
                            self.assertGreaterEqual(x1, 0, (dpi, lang, tab))
                            self.assertLessEqual(x2, panel.w, (dpi, lang, tab))
                            self.assertGreaterEqual(y1, 0, (dpi, lang, tab))
                            self.assertLessEqual(y2, panel.h, (dpi, lang, tab))
                    panel.close()


    def test_notification_guide_opens_once_in_each_language_and_closes_with_the_panel(self) -> None:
        from app.notif_guide import GUIDE
        apps = ("LINE", "Telegram", "Teams", "Outlook", "Gmail")
        self.assertEqual({len(v) for v in GUIDE.values()}, {len(GUIDE["zh_TW"])})
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                panel = SettingsPanel(self.root, lang=lang, char_key="eunji",
                                      state=dict(SETTINGS_DEFAULTS["appearance"], **SETTINGS_DEFAULTS["reminders"]),
                                      initial_tab="reminders")
                self.addCleanup(panel.close)
                self.assertTrue(panel.canvas.find_withtag("btn_notif_guide"))
                self.assertTrue(panel.open_notif_guide())
                guide = panel.notif_guide
                self.assertTrue(panel.open_notif_guide())            # a second click lifts the same window
                self.assertIs(panel.notif_guide, guide)
                text = guide.text.get("1.0", "end")
                for app in apps:
                    self.assertIn(app, text)
                self.assertEqual(guide.text.cget("state"), "disabled")
                panel.close()
                self.assertTrue(guide.closed)


if __name__ == "__main__":
    unittest.main()
