"""The settings panel is wired into the pet; the right-click menu has one entry for it.

Run:  python -m unittest tests.test_settings_wiring -v
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.i18n import t  # noqa: E402
from app.main import PandaPet  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class SettingsWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        settings = dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong")
        PersistenceService(self.dir).save(settings, dict(DEFAULT_RUNTIME))
        self.pet = PandaPet(data_dir=self.dir)
        self.addCleanup(self._close)

    def _close(self) -> None:
        if self.pet is not None:
            self.pet.close()

    def _saved(self) -> dict:
        return PersistenceService(self.dir).load()[0]

    def _labels(self) -> list[str]:
        menu = self.pet.menu
        return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                if menu.type(i) != "separator"]

    def test_menu_has_one_settings_entry_and_no_old_cascades(self) -> None:
        labels = self._labels()
        self.assertEqual(labels.count(t("settings_panel", "zh_TW")), 1)
        for old in ("bubble_theme", "pet_size_menu", "text_size_menu", "hourly_chime", "sedentary"):
            name = t(old, "zh_TW")
            with self.subTest(old=old):
                self.assertFalse([lbl for lbl in labels if name in lbl], labels)
        self.assertIn(t("food_cafe", "zh_TW"), labels)

    def test_open_is_single_instance_and_tab_follows(self) -> None:
        self.pet.open_settings_panel()
        first = self.pet.settings_panel
        self.assertIsNotNone(first)
        self.pet.open_settings_panel("reminders")
        self.assertIs(self.pet.settings_panel, first)
        self.assertEqual(first.active_tab, "reminders")
        first.close()                                       # the user closes it
        self.assertIsNone(self.pet.settings_panel)

    def test_panel_shows_what_main_kept(self) -> None:
        self.pet.open_settings_panel("reminders")
        panel = self.pet.settings_panel
        self.assertTrue(panel.apply_change("sedentary_message", "  喝水  "))
        self.assertEqual(panel.state["sedentary_message"], "喝水")      # cleaned by main
        self.assertEqual(self._saved()["sedentary_message"], "喝水")
        self.assertTrue(panel.apply_change("sedentary_interval_min", 90))
        self.assertEqual((panel.state["sedentary_interval_min"], self._saved()["sedentary_interval_min"]), (90, 90))
        self.assertFalse(panel.apply_change("sedentary_interval_min", 999))
        self.assertEqual(panel.state["sedentary_interval_min"], 90)
        self.assertTrue(panel.apply_change("hourly_chime", False))
        self.assertIs(self._saved()["hourly_chime"], False)
        self.assertTrue(panel.reset_section("reminders"))
        self.assertEqual(panel.state, dict(panel.state, hourly_chime=True, sedentary_interval_min=60,
                                           sedentary_message=""))
        self.assertEqual(self._saved()["sedentary_interval_min"], 60)

    def test_appearance_changes_reach_the_pet(self) -> None:
        self.pet.open_settings_panel()
        panel = self.pet.settings_panel
        self.assertTrue(panel.apply_change("pet_size", "large"))
        self.assertEqual(self.pet.width, self.pet.frames["idle"][0].width())
        self.assertEqual((panel.state["pet_size"], self._saved()["pet_size"]), ("large", "large"))
        self.assertTrue(panel.apply_change("bubble_theme", "ruby_velvet"))
        self.assertEqual(self._saved()["bubble_theme"], "ruby_velvet")
        self.assertFalse(panel.apply_change("bubble_theme", "no_such_theme"))
        self.assertEqual(panel.state["bubble_theme"], "ruby_velvet")

    def test_member_and_language_switch_refresh_the_panel(self) -> None:
        self.pet.open_settings_panel()
        panel = self.pet.settings_panel
        self.pet.switch_character("eunji")
        self.assertEqual(panel.char_key, "eunji")
        self.pet.set_language("ko")
        self.assertEqual(panel.lang, "ko")

    def test_preview_shows_the_reminder_and_keeps_the_countdown(self) -> None:
        self.pet.open_settings_panel("reminders")
        self.pet.sedentary_active_sec = 321
        self.assertTrue(self.pet.settings_panel.trigger_preview("sedentary"))
        self.assertEqual(self.pet.sedentary_active_sec, 321)

    @unittest.skipUnless(sys.platform == "win32", "z-order is checked with Win32")
    def test_opening_the_panel_keeps_a_showing_bubble_on_top(self) -> None:
        bubble = tk.Toplevel(self.pet.root)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.geometry("300x150+700+300")
        bubble.update()
        self.addCleanup(bubble.destroy)
        self.pet.active_bubble = types.SimpleNamespace(window=bubble)
        self.addCleanup(setattr, self.pet, "active_bubble", None)
        self.pet.open_settings_panel()                      # the panel lifts itself again on idle
        self._assert_bubble_above(bubble)
        self.pet.open_settings_panel("reminders")           # reopening the existing panel
        self._assert_bubble_above(bubble)

    def _assert_bubble_above(self, bubble) -> None:
        for _ in range(5):
            self.pet.root.update()
            time.sleep(0.02)
        user32 = ctypes.windll.user32
        hb, hp = (int(w.wm_frame(), 16) for w in (bubble, self.pet.settings_panel.window))
        h = user32.GetTopWindow(0)
        while h and h not in (hb, hp):
            h = user32.GetWindow(h, 2)   # GW_HWNDNEXT
        self.assertEqual(h, hb)

    def test_standby_and_close_take_the_panel_away(self) -> None:
        self.pet.open_settings_panel()
        win = self.pet.settings_panel.window
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock:
            self.pet.settings["standby_lock_workstation"] = False
            self.pet.open_standby_screen()
            self.assertIsNone(self.pet.settings_panel)
            self.assertFalse(win.winfo_exists())
            self.pet.standby_overlay.handle_exit(None)
            self.assertFalse(lock.called)
        self.pet.open_settings_panel()
        win = self.pet.settings_panel.window
        pet, self.pet = self.pet, None
        root = pet.root
        pet.close()
        self.assertIsNone(pet.settings_panel)
        try:
            self.assertFalse(win.winfo_exists())
        except Exception:
            pass                                             # root already destroyed: gone too
        del root

    def test_close_cancels_pending_lift_bubble_and_speech_pump_afters(self) -> None:
        self.pet.open_settings_panel()
        self.pet.open_settings_panel("reminders")
        self.pet._toast("hello")
        bubble = self.pet.active_bubble
        bubble.dismiss()  # actual close cancels its timer before notifying PandaPet
        self.assertIsNone(bubble.timer)
        self.assertIsNone(self.pet.active_bubble)
        self.assertIn("lift_bubble", self.pet._loop_after)
        self.assertIn("speech_pump", self.pet._loop_after)
        tracked_ids = {self.pet._loop_after["lift_bubble"], self.pet._loop_after["speech_pump"]}

        pet, self.pet = self.pet, None
        root = pet.root
        seen_pending_at_destroy: list[set[str]] = []
        orig_destroy = root.destroy

        def inspect_before_destroy() -> None:
            try:
                pending = set(root.tk.splitlist(root.tk.call("after", "info")))
            except tk.TclError:
                pending = set()
            seen_pending_at_destroy.append(pending & tracked_ids)
            orig_destroy()

        with mock.patch.object(root, "destroy", side_effect=inspect_before_destroy):
            pet.close()
        self.assertEqual(seen_pending_at_destroy, [set()])
        self.assertEqual(pet._loop_after, {})


if __name__ == "__main__":
    unittest.main()
