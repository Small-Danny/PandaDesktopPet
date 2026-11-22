"""All five members stay on stage at any pet size, screen width and DPI; guests never freeze Tk.

Run:  python -m unittest tests.test_celebration_roster -v
"""
from __future__ import annotations

import itertools
import time
import tkinter as tk
import unittest
from collections import OrderedDict
from unittest import mock

from PIL import Image

from app.action_frames import ActionFrames, load_exact_action, xmas_poses
from app.daily_actions import CHRISTMAS, LANTERN, MID_AUTUMN_FESTIVAL
from app.desktop_warmup import CELEBRATION_ACTIONS, DesktopWarmupManager, celebration_actions
from app.engine.contracts import MEMBER_KEYS
from app.group_celebration import (
    MIN_GUEST_SCALE, GroupCelebration, guest_frame_slots, roster_layout,
)
from app.main import PET_SIZE_MAP, RES_ROOT, glyph_warmup_fonts, warmup_glyphs
from app.sprites import SpriteLibrary


def _boxes(host_bounds, extents, slots, scale):
    boxes = [host_bounds]
    for (dx, fw), x in zip(extents, slots):
        left = x + dx
        boxes.append((left, left + max(1, round(fw * scale))))
    return sorted(boxes)


class RosterLayoutTest(unittest.TestCase):
    def assert_roster(self, host_bounds, area, extents):
        slots, scale = roster_layout(host_bounds, area, extents)
        self.assertNotIn(None, slots)
        self.assertGreaterEqual(scale, MIN_GUEST_SCALE)
        self.assertLessEqual(scale, 1.0)
        boxes = _boxes(host_bounds, extents, slots, scale)
        self.assertGreaterEqual(boxes[0][0], area[0])
        self.assertLessEqual(boxes[-1][1], area[1])
        for a, b in zip(boxes, boxes[1:]):
            self.assertLessEqual(a[1], b[0], (boxes, scale))          # never overlapping
        return slots, scale

    def test_greedy_slots_are_kept_when_they_hold_everyone(self):
        extents = [(-100, 430), (-25, 250), (-80, 360), (-10, 230)]
        self.assertEqual(roster_layout((900, 1200), (0, 2200), extents),
                         (guest_frame_slots((900, 1200), (0, 2200), extents), 1.0))
        # The single-guest contract of guest_frame_slots is unchanged.
        self.assertEqual(guest_frame_slots((0, 200), (0, 300), [(0, 400)]), [None])

    def test_screenshot_case_hayoung_is_seated(self):
        """Eunji's fireplace pose at 240 px, x=957, 1920 wide: greedy dropped Hayoung."""
        host = (957 - 38, 957 - 38 + 354)
        extents = [(14, 250), (-2, 281), (-31, 341), (-38, 353)]   # chorong, bomi, namjoo, hayoung
        self.assertIsNone(guest_frame_slots(host, (0, 1920), extents)[3])
        _slots, scale = self.assert_roster(host, (0, 1920), extents)
        self.assertEqual(scale, 1.0)                                # rebalancing alone suffices

    def test_too_narrow_shrinks_every_guest_evenly(self):
        extents = [(-40, 420)] * 4
        slots, scale = self.assert_roster((600, 1000), (0, 1366), extents)
        self.assertLess(scale, 1.0)

    def test_real_large_art_seats_all_five_on_every_screen(self):
        """Real registry canvases: large (240 px) at 100/125/150 % on 1920, and a 1366 laptop."""
        cases = ((1.0, 1920), (1.25, 1920), (1.5, 1920), (1.0, 1366))
        host = "eunji"
        guests = [m for m in MEMBER_KEYS if m != host]
        for scale, width in cases:
            px = round(PET_SIZE_MAP["large"] * scale)
            lib = SpriteLibrary(RES_ROOT, display_px=px, equalize=True)
            if lib.registry is None:
                self.skipTest("no approved registry")
            extents = {}

            def ext(member, action):
                if (member, action) not in extents:
                    loaded = load_exact_action(lib, member, action)
                    extents[(member, action)] = (None if loaded is None
                                                 else (loaded.offset[0], loaded.frames[0].width))
                return extents[(member, action)]

            looks = {m: [CHRISTMAS.action, *xmas_poses(lib, m)] for m in MEMBER_KEYS}
            combos = list(itertools.product(*(looks[m] for m in [host] + guests)))
            combos += [(a,) * 5 for a in ("musical_pose", MID_AUTUMN_FESTIVAL.action, LANTERN.action)]
            for combo in combos:
                he = ext(host, combo[0])
                guest_ext = [ext(m, a) for m, a in zip(guests, combo[1:])]
                if he is None or None in guest_ext:
                    continue
                for host_x in range(0, width - px + 1, max(40, width // 12)):
                    host_bounds = (max(0, host_x + he[0]), min(width, host_x + he[0] + he[1]))
                    with self.subTest(scale=scale, width=width, combo=combo, host_x=host_x):
                        self.assert_roster(host_bounds, (0, width), guest_ext)


def _fake_load(size=(100, 120), offset=(-10, -20)):
    calls = []

    def load(library, member, action, scale_member=None):
        calls.append((member, action))
        return ActionFrames(action, tuple(Image.new("RGBA", size, (200, 10, 10, 255)) for _ in range(2)),
                            100.0, True, offset)
    return load, calls


class GroupCelebrationWindowsTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.lib = mock.Mock(display_px=240)

    def _pump(self, party, timeout_s=3.0):
        deadline = time.monotonic() + timeout_s
        while party.loading and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.002)

    def test_stagger_starts_without_guests_then_seats_all_four(self):
        load, _calls = _fake_load()
        placed = []
        with mock.patch("app.group_celebration.load_exact_action", side_effect=load), \
             mock.patch("app.group_celebration.SYNC_BUDGET_S", 0.0):
            party = GroupCelebration(self.root, self.lib, ["chorong", "bomi", "namjoo", "hayoung"],
                                     (900, 500, 100, 100), (0, 1920), action="x", duration_ms=60000,
                                     on_placed=placed.append, stagger=True)
            self.assertTrue(party.loading)
            self.assertEqual(party.members_shown, 0)
            self._pump(party)
        self.assertFalse(party.loading)
        self.assertEqual(party.members_shown, 4)
        self.assertEqual(placed, [party])
        party.close()

    def test_close_while_loading_opens_nothing(self):
        load, calls = _fake_load()
        with mock.patch("app.group_celebration.load_exact_action", side_effect=load), \
             mock.patch("app.group_celebration.SYNC_BUDGET_S", 0.0):
            party = GroupCelebration(self.root, self.lib, ["chorong", "bomi", "namjoo", "hayoung"],
                                     (900, 500, 100, 100), (0, 1920), action="x", stagger=True)
            party.close()
            for _ in range(10):
                self.root.update()
        self.assertEqual(party.members_shown, 0)
        self.assertLessEqual(len(calls), 1)

    def test_without_stagger_guests_are_seated_in_the_constructor(self):
        load, _calls = _fake_load()
        with mock.patch("app.group_celebration.load_exact_action", side_effect=load), \
             mock.patch("app.group_celebration.SYNC_BUDGET_S", 0.0):
            party = GroupCelebration(self.root, self.lib, ["chorong", "bomi"],
                                     (900, 500, 100, 100), (0, 1920), action="x")
        self.assertEqual(party.members_shown, 2)
        party.close()

    def test_shrunk_guests_keep_their_feet_on_the_pet_feet_line(self):
        load, _calls = _fake_load(size=(400, 300), offset=(-50, -100))
        pet_y, h = 500, 200
        with mock.patch("app.group_celebration.load_exact_action", side_effect=load):
            party = GroupCelebration(self.root, self.lib, ["chorong", "bomi", "namjoo", "hayoung"],
                                     (600, pet_y, 200, h), (0, 1366), action="x", duration_ms=60000)
        self.root.update_idletasks()
        self.assertEqual(party.members_shown, 4)
        self.assertLess(party.guest_scale, 1.0)
        feet = round((h + 100) * party.guest_scale)                # base bottom inside the canvas
        for win, *_ in party.windows:
            self.assertEqual(win.winfo_width(), round(400 * party.guest_scale))
            self.assertLessEqual(abs(win.winfo_y() + feet - (pet_y + h)), 1)
            self.assertGreaterEqual(win.winfo_x(), 0)
            self.assertLessEqual(win.winfo_x() + win.winfo_width(), 1366)
        # Verify scaled PhotoImages have strictly binary alpha (0 or 255) so -transparentcolor #ff00fe never halos
        from PIL import ImageTk
        for _win, _canvas, _item, frames, _ms, _pp in party.windows:
            im = ImageTk.getimage(frames[0])
            hist = im.getchannel("A").histogram()
            self.assertEqual(sum(hist[1:255]), 0)
        party.close()

    def test_photo_cache_skips_decoding_on_the_next_party(self):
        load, calls = _fake_load()
        cache = OrderedDict()
        with mock.patch("app.group_celebration.load_exact_action", side_effect=load):
            for _ in range(2):
                party = GroupCelebration(self.root, self.lib, ["chorong", "bomi"], (900, 500, 100, 100),
                                         (0, 1920), action="x", photo_cache=cache)
                self.assertEqual(party.members_shown, 2)
                party.close()
        self.assertEqual(len(calls), 2)


class WarmupCoverageTest(unittest.TestCase):
    def test_idle_warmup_prepares_every_celebration_look_for_every_member(self):
        manager = DesktopWarmupManager()
        lib = SpriteLibrary(RES_ROOT, display_px=240)
        seen = []
        plan = {"gen": 1, "busy_check": None, "resource_root": RES_ROOT, "sprite_px": 240,
                "active_member": "eunji", "today": __import__("datetime").date(2026, 6, 1)}
        # Earlier tests in the same process may have filled the shared PREPARED cache;
        # this checks coverage, not the budget stop (that has its own tests).
        with mock.patch("app.desktop_warmup.warm_budget_exhausted", return_value=False), \
             mock.patch("app.desktop_warmup._prepare_member_pil"), \
             mock.patch.object(manager, "_yield_step", return_value=False), \
             mock.patch("app.desktop_warmup.load_exact_action",
                        side_effect=lambda library, m, a, **kw: seen.append((m, a, library.display_px))):
            manager._execute_plan(plan)
        for member in MEMBER_KEYS:
            for action in celebration_actions(lib, member):
                self.assertIn((member, action, 240), seen)
        self.assertIn("special_birthday", CELEBRATION_ACTIONS)
        self.assertIn("musical_pose", CELEBRATION_ACTIONS)
        self.assertTrue(any(a.startswith("xmas_special_v6/") for _m, a, _px in seen))

    def test_glyph_set_covers_the_panel_emoji(self):
        glyphs = set(warmup_glyphs())
        for ch in "✨💬🛠📏📝🕰⏰💌🔔💾⚡↺🌸🍊💎💜💛🍫🍇🫐":
            self.assertIn(ch, glyphs)
        self.assertNotIn("設", glyphs)
        self.assertNotIn("️", glyphs)
        self.assertEqual(glyph_warmup_fonts("zh_TW")[0][0], "Microsoft JhengHei")
        self.assertEqual(glyph_warmup_fonts("ko")[0][0], "Malgun Gothic")


if __name__ == "__main__":
    unittest.main()
