"""Fixes from the 2026-11-08 user pass: party casts, new year clock, member menu, food scroll, bubble art."""
from __future__ import annotations

import gc
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp())

from app.action_frames import load_exact_action  # noqa: E402
from app.anniversary_scene import photo_index  # noqa: E402
from app.food_panel import FoodCafePanel, filter_foods_by_tab  # noqa: E402
from app.main import RES_ROOT, PandaPet  # noqa: E402
from app.new_year_countdown import NewYearCountdown  # noqa: E402
from app.pink_context_menu import build_pet_context_menu_items  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402

MEMBERS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")


class RegistryTest(unittest.TestCase):
    def test_new_actions_play_on_the_desktop(self) -> None:
        lib = SpriteLibrary(RES_ROOT)
        for member, action in (("bomi", "special_taekwondo"), ("eunji", "special_boxing"),
                               ("namjoo", "special_boxing"), ("bomi", "interaction_drag")):
            loaded = load_exact_action(lib, member, action)
            self.assertIsNotNone(loaded, f"{member}.{action}")
            self.assertEqual(len(loaded.frames), 4)
        for member in MEMBERS:
            self.assertIsNotNone(load_exact_action(lib, member, "special_cheer_lightstick"), member)
            self.assertIsNotNone(load_exact_action(lib, member, "festival_christmas"), member)
        self.assertIsNotNone(load_exact_action(lib, None, "secret_clover_visitor", scale_member="chorong"))


class PetTest(unittest.TestCase):
    def setUp(self) -> None:
        # This module creates several Tk interpreters in series. Dispose of any
        # unreachable widgets on the Tk thread before creating the next one.
        gc.collect()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        PersistenceService(Path(tmp.name)).save(dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong"),
                                                dict(DEFAULT_RUNTIME))
        # Tray setup has its own native-thread lifecycle tests. Here only the
        # pet's UI behavior is under test.
        with mock.patch("app.main.PandaSystemTray"):
            self.pet = PandaPet(data_dir=Path(tmp.name))
        self.addCleanup(self.pet.close)
        self.pet.speech.hold(True)

    def test_birthday_cast_uses_birthday_actions_not_lightsticks(self) -> None:
        with mock.patch("app.main.GroupCelebration") as party:
            self.pet.celebrate_together()
        self.assertEqual(self.pet.coord.action, "special_birthday")
        self.assertEqual(party.call_args.kwargs["action"], "special_birthday")
        self.assertEqual(len(party.call_args.args[2]), 4)

    def test_419_brings_the_hidden_visitor(self) -> None:
        self.pet.preview_anniversary_event()
        scene = self.pet.anniversary_scene
        self.assertEqual(self.pet.window.state(), "withdrawn")
        self.assertEqual(len(scene.frames), 5)
        self.assertFalse(scene.visitor_shown)
        scene._t0 -= 2.1
        scene._tick()
        self.assertTrue(scene.visitor_shown)
        self.assertEqual(photo_index(2.5), 4)                  # everyone greets her
        self.assertLess(photo_index(3.3), 4)
        self.pet._close_group_celebration()
        self.assertIsNone(self.pet.anniversary_scene)
        self.assertNotEqual(self.pet.window.state(), "withdrawn")

    def test_birthday_has_no_hidden_visitor(self) -> None:
        self.pet.preview_birthday_event()
        self.addCleanup(self.pet._close_group_celebration)
        party = self.pet.group_celebration
        deadline = time.monotonic() + 10       # cold guests load over a few Tk turns
        while party.loading and time.monotonic() < deadline:
            self.pet.root.update()
            time.sleep(0.005)
        self.assertEqual(party.members_shown, 4)

    def test_christmas_is_all_five_in_costume(self) -> None:
        with mock.patch("app.main.GroupCelebration") as party:
            self.pet.preview_christmas_event()
        self.assertTrue("christmas" in self.pet.coord.action or "xmas" in self.pet.coord.action)
        pick = party.call_args.kwargs["action"]
        for member in MEMBERS:
            self.assertRegex(pick(member), "festival_christmas|xmas_special_v6/" + member)

    def test_christmas_idle_can_show_a_single_image_pose(self) -> None:
        import datetime
        self.pet.calendar.clock.now = lambda: datetime.datetime(2026, 12, 24, 12, 0)
        with mock.patch("app.main.random.random", side_effect=[0.0, 0.9]), \
                mock.patch.object(self.pet.coord, "submit") as submit:
            self.pet._maybe_festival_action(1000.0)
        self.assertIn("xmas_special_v6/chorong_", submit.call_args.args[0].action)

    def test_new_year_clock_then_celebration(self) -> None:
        with mock.patch.object(self.pet, "_celebrate_new_year") as party:
            self.pet.preview_new_year_countdown()
            clock = self.pet.new_year_clock
            self.assertIsInstance(clock, NewYearCountdown)
            self.assertEqual(clock.canvas.itemcget(clock.digits, "text"), "10")
            party.assert_not_called()
            clock._t0 -= 11
            clock._tick()
            party.assert_called_once()
        self.assertIsNone(self.pet.new_year_clock)

    def test_menu_groups_moves_by_member(self) -> None:
        items = build_pet_context_menu_items(self.pet)
        flyout = next(i for i in items if i.tag_id == "row_special").submenu
        members = [i for i in flyout if i.submenu]
        self.assertEqual(len(members), 5)
        bomi = members[1].submenu
        self.assertEqual(len(bomi), 5)                                  # back, gorilla, taekwondo, mukbang, lightstick
        self.assertEqual(len([i for i in bomi[0].submenu if i.submenu]), 5)   # back returns to the members
        with mock.patch.object(self.pet, "trigger_special_action") as run:
            bomi[2].command()
        run.assert_called_once_with("special_taekwondo", "bomi")


class FoodScrollTest(unittest.TestCase):
    def test_wheel_reaches_the_last_row(self) -> None:
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        panel = FoodCafePanel(root)
        self.addCleanup(panel.close)
        self.assertEqual(panel.active_tab, "meal")              # three category tabs, no "all"
        last = filter_foods_by_tab("meal")[-1]["id"]
        panel.scroll_rows(99)                                   # 30 meals = 5 rows: nothing hidden
        self.assertTrue(panel.canvas.find_withtag(f"food_{last}"))
        self.assertTrue(panel.canvas.find_withtag("food_chicken_feet"))
        panel.select_tab("drink")
        self.assertTrue(panel.canvas.find_withtag("food_americano"))


if __name__ == "__main__":
    unittest.main()
