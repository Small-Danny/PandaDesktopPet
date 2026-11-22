"""feed() records food discoveries in the same save, and the café panel is wired in.

Run:  python -m unittest tests.test_feed_food_log -v
"""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.food_log import outcomes  # noqa: E402
from app.main import FeedResult, PandaPet  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402


def _pet(member: str = "chorong", satiety: float = 50.0, save_ok: bool = True):
    saved = []

    def save():
        saved.append(1)
        return save_ok

    pet = types.SimpleNamespace(
        char_key=member, lang="zh_TW", satiety=satiety, last_satiety_update=time.time(),
        runtime={"cheer_passion": 0, "feed_count": 0}, feed_count=0,
        record_activity=lambda: None, save_settings=save,
        trigger_cheer=lambda **kw: None, _play_reaction=lambda *a, **k: False, _refresh_status_card=lambda: None,
        _refresh_food_panel=lambda: None, _toast=lambda msg, **kw: None,
    )
    pet._current_satiety = lambda: PandaPet._current_satiety(pet)
    return pet, saved


class FeedRecordsDiscoveryTest(unittest.TestCase):
    def test_outcomes_follow_the_food(self) -> None:
        for member, food, expected in (("chorong", "matcha_cake", "favourite"),
                                       ("eunji", "mint_choco", "disliked"),
                                       ("chorong", "jajangmyeon", "normal")):
            pet, saved = _pet(member)
            with self.subTest(member=member, food=food):
                result = PandaPet.feed(pet, food)
                self.assertEqual(result, FeedResult(expected, newly_unlocked=True, saved=True))
                self.assertEqual(outcomes(pet.runtime, member), {food: expected})
                self.assertEqual(saved, [1])          # stats and discovery: one save

    def test_second_feed_is_not_new(self) -> None:
        pet, _ = _pet()
        PandaPet.feed(pet, "jajangmyeon")
        self.assertFalse(PandaPet.feed(pet, "jajangmyeon").newly_unlocked)

    def test_full_refusal_records_nothing(self) -> None:
        pet, saved = _pet(satiety=100.0)
        self.assertEqual(PandaPet.feed(pet, "tteokbokki"), FeedResult("refused_full"))
        self.assertEqual(outcomes(pet.runtime, "chorong"), {})
        self.assertEqual(saved, [])

    def test_full_drink_records_the_real_relation(self) -> None:
        pet, _ = _pet(member="eunji", satiety=99.0)
        with mock.patch("random.choice", side_effect=lambda seq: seq[0]):
            result = PandaPet.feed(pet, "beer")
        self.assertTrue(result.drink_full)
        self.assertEqual(result.outcome, "favourite")
        self.assertEqual(outcomes(pet.runtime, "eunji"), {"beer": "favourite"})

    def test_failed_save_takes_the_discovery_back(self) -> None:
        pet, _ = _pet(save_ok=False)
        result = PandaPet.feed(pet, "jajangmyeon")
        self.assertEqual(result, FeedResult("normal", saved=False))
        self.assertEqual(outcomes(pet.runtime, "chorong"), {})
        self.assertEqual(pet.feed_count, 1)               # the feed itself still happened

    def test_failed_save_keeps_an_older_discovery(self) -> None:
        pet, _ = _pet()
        PandaPet.feed(pet, "jajangmyeon")
        pet.save_settings = lambda: False
        PandaPet.feed(pet, "jajangmyeon")
        self.assertEqual(outcomes(pet.runtime, "chorong"), {"jajangmyeon": "normal"})

    def test_unknown_food(self) -> None:
        pet, saved = _pet()
        self.assertEqual(PandaPet.feed(pet, "nope"), FeedResult("invalid"))
        self.assertEqual(saved, [])


class SaveSettingsResultTest(unittest.TestCase):
    def _pet(self, persist_ok=True, fail=False):
        store = mock.Mock()
        if fail:
            store.save.side_effect = OSError("disk full")
        return types.SimpleNamespace(_persist_ok=persist_ok, _persist_errors=[], store=store,
                                     settings={}, runtime={}, get_total_companion_seconds=lambda: 0)

    def test_result(self) -> None:
        self.assertTrue(PandaPet.save_settings(self._pet()))
        self.assertFalse(PandaPet.save_settings(self._pet(persist_ok=False)))
        failing = self._pet(fail=True)
        self.assertFalse(PandaPet.save_settings(failing))
        self.assertEqual(failing._persist_errors[0][0], "persist_save_failed")


class FoodPanelWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        pet_win = tk.Toplevel(self.root)
        pet_win.geometry("60x60+900+600")
        self.pet = types.SimpleNamespace(
            window=pet_win, food_panel=None, lang="zh_TW", char_key="eunji", runtime={},
            satiety=50.0, last_satiety_update=time.time(), record_activity=lambda: None,
            feed=lambda food_id: FeedResult("normal"),
            x=900, y=600, width=60, height=60,
            desktop=types.SimpleNamespace(work_area_for_point=lambda x, y: WorkArea(0, 0, 1920, 1040)),
        )
        self.pet.active_bubble = None
        for name in ("_current_satiety", "_on_food_panel_closed", "_refresh_food_panel", "_close_food_panel",
                     "_pet_work_area", "_lift_bubble"):
            setattr(self.pet, name, getattr(PandaPet, name).__get__(self.pet))

    def test_open_is_single_instance_and_close_clears(self) -> None:
        PandaPet.open_food_panel(self.pet)
        first = self.pet.food_panel
        self.assertIsNotNone(first)
        PandaPet.open_food_panel(self.pet)
        self.assertIs(self.pet.food_panel, first)
        self.pet._close_food_panel()
        self.assertIsNone(self.pet.food_panel)
        self.assertFalse(first.window.winfo_exists())

    def test_refresh_sends_the_saved_snapshot_per_member(self) -> None:
        self.pet.runtime["food_log"] = {"eunji": {"egg": {"outcome": "favourite", "first_fed": 1}}}
        PandaPet.open_food_panel(self.pet)
        panel = self.pet.food_panel
        self.addCleanup(self.pet._close_food_panel)
        self.assertEqual(panel.get_tile_badge("egg"), "favorite")
        self.pet.runtime["food_log"]["eunji"]["budae_jjigae"] = {"outcome": "normal", "first_fed": 2}
        self.assertIsNone(panel.get_tile_badge("budae_jjigae"))   # snapshot: nothing until main refreshes
        self.pet._refresh_food_panel()
        self.assertEqual(panel.get_tile_badge("budae_jjigae"), "tasted")
        self.pet.char_key = "hayoung"
        self.pet._refresh_food_panel()
        self.assertEqual(panel.char_key, "hayoung")
        self.assertIsNone(panel.get_tile_badge("egg"))       # per member

    def test_user_closing_the_panel_clears_the_reference(self) -> None:
        PandaPet.open_food_panel(self.pet)
        self.pet.food_panel.close()
        self.assertIsNone(self.pet.food_panel)

    @unittest.skipUnless(sys.platform == "win32", "z-order is checked with Win32")
    def test_opening_the_panel_keeps_a_showing_bubble_on_top(self) -> None:
        bubble = tk.Toplevel(self.root)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.geometry("300x150+700+300")
        bubble.update()
        self.pet.active_bubble = types.SimpleNamespace(window=bubble)
        PandaPet.open_food_panel(self.pet)
        self.addCleanup(self.pet._close_food_panel)
        self._assert_bubble_above(bubble)
        PandaPet.open_food_panel(self.pet)          # reopening the existing panel
        self._assert_bubble_above(bubble)

    def _assert_bubble_above(self, bubble: tk.Toplevel) -> None:
        for _ in range(5):
            self.root.update()
            time.sleep(0.02)
        user32 = ctypes.windll.user32
        hb, hp = (int(w.wm_frame(), 16) for w in (bubble, self.pet.food_panel.window))
        h = user32.GetTopWindow(0)
        while h and h not in (hb, hp):
            h = user32.GetWindow(h, 2)   # GW_HWNDNEXT
        self.assertEqual(h, hb)


if __name__ == "__main__":
    unittest.main()
