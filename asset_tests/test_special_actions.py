"""Exact registry actions on the desktop pet: specials, the drag pose, lightstick cheer, group birthday.

The registry has none of these approved yet, so approved frames are faked through the
two loader functions main uses; the fallbacks are checked against the real registry.

Run:  python -m unittest tests.test_special_actions -v
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.action_frames import ActionFrames  # noqa: E402
from app.engine.contracts import ActorState  # noqa: E402
from app.group_celebration import guest_slots  # noqa: E402
from app.main import (  # noqa: E402
    BIRTHDAY_ACTION, CHEER_LIGHTSTICK_ACTION, DRAG_ACTION, SPECIAL_MIN_S, PandaPet,
)
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


def _color(i: int) -> tuple[int, int, int, int]:
    return (10 + i, 200, 30, 255)


class _FakeRegistry:
    """{(member, action): n_frames} approved; frame i is a flat colour _color(i).

    ``large`` = {(member, action): (offset, size)} for big desktop canvases.
    """

    def __init__(self, size: tuple[int, int], approved: dict[tuple[str, str], int], frame_ms: float = 180.0):
        self.size, self.approved, self.frame_ms = size, approved, frame_ms
        self.large: dict[tuple[str, str], tuple[tuple[int, int], tuple[int, int]]] = {}

    def load(self, library, member, action, scale_member=None):
        n = self.approved.get((member, action))
        if not n:
            return None
        offset, size = self.large.get((member, action), ((0, 0), self.size))
        return ActionFrames(action, tuple(Image.new("RGBA", size, _color(i)) for i in range(n)),
                            self.frame_ms, False, offset)

    def available(self, library, member, candidates):
        return tuple(a for a in candidates if (member, a) in self.approved)


class _PetCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        PersistenceService(self.dir).save(dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong"),
                                          dict(DEFAULT_RUNTIME))
        self.pet = PandaPet(data_dir=self.dir)
        self.addCleanup(self.pet.close)
        self.pet.speech.hold(True)                   # no bubble windows in these tests
        self.fake = _FakeRegistry((self.pet.width, self.pet.height), {
            ("chorong", "special_cartwheel"): 4,
            ("chorong", DRAG_ACTION): 4,
            ("namjoo", "special_hapkido_kick"): 3,
            ("namjoo", CHEER_LIGHTSTICK_ACTION): 4,
        })
        for target, fn in (("app.main.load_exact_action", self.fake.load),
                           ("app.main.available_actions", self.fake.available),
                           ("app.group_celebration.load_exact_action", self.fake.load)):
            patcher = mock.patch(target, side_effect=fn)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _shown_color(self) -> tuple:
        frame = self.pet.current_frame()
        return ImageTk.getimage(frame).getpixel((self.pet.width // 2, self.pet.height // 2))

    def _tick(self) -> int:
        """One animate() step without its timer; returns the delay it asked for."""
        self.pet._debug_paused = False
        with mock.patch.object(self.pet.window, "after", return_value="x") as after:
            self.pet.animate()
        return after.call_args.args[0]


class SpecialActionTest(_PetCase):
    def test_approved_special_plays_every_frame_in_order_at_its_speed(self) -> None:
        self.assertTrue(self.pet.trigger_special_action("special_cartwheel"))
        snap = self.pet.coord.snapshot()
        self.assertEqual((snap.actor_state, snap.action), (ActorState.SPECIAL, "special_cartwheel"))
        if self.pet._ulw_active():
            pils = self.pet._visual_pil_frames_and_offset("chorong", "special_cartwheel")[0]
            tokens = [id(im) for im in pils]
            seen = []
            tick_frames = []
            real_present = self.pet._present_layered_pet

            def record(pil_frame=None, image_xy=None):
                raw = pil_frame if pil_frame is not None else self.pet.current_pil_frame()
                tick_frames.append(tokens.index(id(raw)))
                return real_present(pil_frame, image_xy)

            with mock.patch.object(self.pet, "_present_layered_pet", side_effect=record):
                for _ in range(5):
                    tick_frames.clear()
                    self.assertEqual(self._tick(), 180)
                    seen.append(tick_frames[-1])
        else:
            names = [str(p) for p in self.pet._action_frames("chorong", "special_cartwheel")[0]]
            seen = []
            for _ in range(5):
                self.assertEqual(self._tick(), 180)
                seen.append(names.index(self.pet.canvas.itemcget(self.pet.image, "image")))
        self.assertEqual(seen, [0, 1, 2, 3, 0])
        self.assertEqual(self.pet.cycle_length(), 4)

    def test_it_lasts_whole_passes_of_at_least_the_minimum(self) -> None:
        self.pet.trigger_special_action("special_cartwheel")
        duration = self.pet.coord.snapshot().active.request.duration_s
        one_pass = 4 * 0.180
        self.assertAlmostEqual(duration, math.ceil(SPECIAL_MIN_S / one_pass) * one_pass)

    def test_first_frame_is_shown_first_even_mid_cycle(self) -> None:
        self.pet.frame_idx = 7
        self.pet.trigger_special_action("special_cartwheel")
        self._tick()
        self.assertEqual(self.pet.frame_idx, 1)                      # drew frame 0, then advanced

    def test_missing_action_changes_nothing(self) -> None:
        before = self.pet.coord.snapshot()
        self.assertFalse(self.pet.trigger_special_action("special_gorilla"))
        self.assertFalse(self.pet.trigger_special_action("idle"))       # base states are not specials
        self.assertFalse(self.pet.trigger_special_action("special_cartwheel", member="nobody"))
        after = self.pet.coord.snapshot()
        self.assertEqual((after.actor_state, after.action), (before.actor_state, before.action))
        self.assertEqual(self.pet.char_key, "chorong")

    def test_another_members_trick_switches_to_her_first(self) -> None:
        self.assertTrue(self.pet.trigger_special_action("special_hapkido_kick", member="namjoo"))
        self.assertEqual(self.pet.char_key, "namjoo")
        self.assertEqual(self.pet.coord.action, "special_hapkido_kick")
        self.assertEqual(self._shown_color(), _color(0))

    def test_menu_lists_only_approved_specials(self) -> None:
        self.assertEqual(self.pet.available_special_actions(), ("special_cartwheel",))
        self.assertEqual(self.pet.available_special_actions("namjoo"),
                         ("special_hapkido_kick", CHEER_LIGHTSTICK_ACTION))
        self.assertEqual(self.pet.available_special_actions("bomi"), ())

    def test_dragging_shows_the_drag_pose_and_lets_go(self) -> None:
        self.pet.dragging = True
        self.pet.coord.begin_user_interaction("drag")
        self.assertEqual(self.pet._visual_action(), DRAG_ACTION)
        self.assertEqual(self._shown_color(), _color(0))
        self.pet.end_drag()
        self.assertIsNone(self.pet._visual_action())
        self.assertNotIn(self._shown_color(), [_color(i) for i in range(4)])

    def test_large_canvas_grows_the_window_around_the_feet_and_shrinks_back(self) -> None:
        w, h = self.pet.width, self.pet.height
        self.fake.large[("chorong", "special_cartwheel")] = ((-20, -30), (w + 50, h + 40))
        base_xy = (self.pet.x, self.pet.y)
        self.pet.trigger_special_action("special_cartwheel")
        self._tick()
        self.assertEqual(self.pet._frame_pad, (20, 30, 30, 10))
        self.assertEqual((int(self.pet.canvas.cget("width")), int(self.pet.canvas.cget("height"))),
                         (w + 50, h + 40))
        self.assertEqual(tuple(self.pet.canvas.coords(self.pet.image)), (0.0, 0.0))
        self.assertEqual((self.pet.x, self.pet.y), base_xy)            # the base box did not move
        self.pet.root.update_idletasks()
        self.assertEqual((self.pet.window.winfo_x(), self.pet.window.winfo_y()),
                         (base_xy[0] - 20, base_xy[1] - 30))
        self.pet.coord.cancel(self.pet.coord.snapshot().active.event_id, "test")
        self._tick()
        self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))
        self.assertEqual((int(self.pet.canvas.cget("width")), int(self.pet.canvas.cget("height"))), (w, h))

    def test_dragging_a_padded_pet_keeps_the_padding(self) -> None:
        w, h = self.pet.width, self.pet.height
        self.fake.large[("chorong", DRAG_ACTION)] = ((-10, -40), (w + 20, h + 40))
        self.pet.dragging = True
        self.pet.coord.begin_user_interaction("drag")
        self._tick()
        self.pet.x, self.pet.y = 300, 400
        with mock.patch.object(self.pet.desktop, "position_without_activation", return_value=False):
            self.pet._place_pet()
        self.pet.root.update_idletasks()
        self.assertEqual((self.pet.window.winfo_x(), self.pet.window.winfo_y()), (290, 360))
        self.pet.end_drag()

    def test_member_without_a_drag_pose_keeps_her_idle_frame(self) -> None:
        self.pet.switch_character("bomi")
        self.pet.dragging = True
        self.pet.coord.begin_user_interaction("drag")
        self.assertIsNone(self.pet._visual_action())
        self.assertIn(self.pet.current_frame(), self.pet.frames["idle"])
        self.pet.end_drag()

    def test_cheer_uses_the_lightstick_when_she_has_one(self) -> None:
        self.pet.switch_character("namjoo")
        self.pet.set_state("cheer")
        snap = self.pet.coord.snapshot()
        self.assertEqual((snap.action, snap.active.request.kind), (CHEER_LIGHTSTICK_ACTION, "manual.cheer"))
        self.assertEqual(self._shown_color(), _color(0))

    def test_cheer_without_a_lightstick_is_the_base_cheer(self) -> None:
        self.pet.set_state("cheer")
        snap = self.pet.coord.snapshot()
        self.assertEqual((snap.actor_state, snap.action, snap.active.request.kind),
                         (ActorState.CHEER, None, "manual.cheer"))
        self.assertIn(self.pet.current_frame(), self.pet.frames["cheer"])


class GroupCelebrationTest(_PetCase):
    def setUp(self) -> None:
        super().setUp()
        # These assertions read the guests right after the call: no staggered loading.
        patcher = mock.patch("app.group_celebration.SYNC_BUDGET_S", 60.0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_slots_two_each_side_when_there_is_room(self) -> None:
        slots = guest_slots(1000, 200, 0, 1920, 4)
        self.assertEqual(slots, [660, 830, 1170, 1340])

    def test_slots_move_to_the_side_with_room(self) -> None:
        slots = guest_slots(10, 200, 0, 1920, 4)
        self.assertEqual(len(slots), 4)
        self.assertTrue(all(x > 10 for x in slots))
        self.assertTrue(all(0 <= x and x + 200 <= 1920 for x in slots))

    def test_slots_never_more_than_fit(self) -> None:
        self.assertEqual(guest_slots(0, 200, 0, 400, 4), [170])

    def test_four_guests_join_and_leave(self) -> None:
        self.pet.preview_birthday_event()
        party = self.pet.group_celebration
        self.assertIsNotNone(party)
        self.assertEqual(party.members_shown, 4)                    # base cheer: none has a birthday action
        windows = [w for w, *_ in party.windows]
        self.assertTrue(all(w.winfo_exists() for w in windows))
        self.pet._close_group_celebration()
        self.assertIsNone(self.pet.group_celebration)
        self.assertFalse(any(w.winfo_exists() for w in windows))

    def test_guest_with_a_birthday_action_plays_it(self) -> None:
        self.fake.approved[("bomi", BIRTHDAY_ACTION)] = 4
        self.pet.preview_user_birthday_event()
        rows = {id(w): (frames, ping) for w, _c, _i, frames, _ms, ping in self.pet.group_celebration.windows}
        pings = sorted(ping for _frames, ping in rows.values())
        self.assertEqual(pings, [False, True, True, True])         # bomi's own birthday frames, 3 base cheers
        self.pet._close_group_celebration()

    def test_large_guest_canvas_gets_its_own_size_and_feet_position(self) -> None:
        w, h = self.pet.width, self.pet.height
        self.fake.approved[("bomi", BIRTHDAY_ACTION)] = 4
        self.fake.large[("bomi", BIRTHDAY_ACTION)] = ((-25, -60), (w + 50, h + 70))
        self.pet.preview_birthday_event()
        self.pet.root.update_idletasks()
        party = self.pet.group_celebration
        area = self.pet.desktop.work_area_for_point(self.pet.x + w // 2, self.pet.y + h // 2)
        slots = guest_slots(self.pet.x, w, area.left, area.right, 4)
        big = [win for win, _c, _i, frames, _ms, ping in party.windows if not ping]
        self.assertEqual(len(big), 1)
        win = big[0]
        self.assertEqual((win.winfo_width(), win.winfo_height()), (w + 50, h + 70))
        # Variable-width guests reserve their full canvas, rather than the old
        # fixed-width slot grid which could overlap an expanded host or guest.
        self.assertGreaterEqual(win.winfo_x(), area.left)
        self.assertLessEqual(win.winfo_x() + win.winfo_width(), area.right)
        for other, *_ in party.windows:
            if other is not win:
                self.assertTrue(win.winfo_x() + win.winfo_width() <= other.winfo_x()
                                or other.winfo_x() + other.winfo_width() <= win.winfo_x())
        self.assertEqual(win.winfo_y() + 60, self.pet.y)            # feet on the pet's feet line
        self.pet._close_group_celebration()

    def test_narrow_screen_shrinks_the_host_with_her_guests(self) -> None:
        """2026-11-22 user report (laptop, 1600 logical px): the four guests were shrunk to
        fit but the host kept full size, so she looked a size bigger. Same factor now."""
        from app.platform.win32 import WorkArea
        w, h = self.pet.width, self.pet.height
        self.fake.approved[("chorong", BIRTHDAY_ACTION)] = 4
        full = self.pet._action_entry("chorong", BIRTHDAY_ACTION, 1)
        self.assertEqual(full.pil[0].size, (w, h))
        narrow = WorkArea(self.pet.x - 3 * w // 2, 0, self.pet.x + 5 * w // 2, 2000)   # ~3 guests wide
        with mock.patch.object(self.pet.desktop, "work_area_for_point", return_value=narrow):
            self.pet.celebrate_together(duration_ms=5000)
        party = self.pet.group_celebration
        self.assertLess(party.guest_scale, 1.0)
        self.assertEqual(self.pet._host_party_scale, party.guest_scale)
        shown = self.pet._action_entry("chorong", BIRTHDAY_ACTION, 1)
        s = party.guest_scale
        self.assertEqual(shown.pil[0].size, (round(w * s), round(h * s)))
        guest = party.windows[0][3][0]
        self.assertEqual((guest.width(), guest.height()), shown.pil[0].size)   # same size as a guest
        # Feet stay on the base box's feet point: the bottom edge moves with the scale only.
        from app.main import walk_feet_point
        fx, fy = walk_feet_point(self.pet.sprites.display_px)
        self.assertEqual(shown.offset, (round(fx - fx * s), round(fy - fy * s)))
        self.pet._close_group_celebration()
        self.assertEqual(self.pet._host_party_scale, 1.0)
        self.assertEqual(self.pet._action_entry("chorong", BIRTHDAY_ACTION, 1).pil[0].size, (w, h))

    def test_roomy_screen_keeps_the_host_full_size(self) -> None:
        self.fake.approved[("chorong", BIRTHDAY_ACTION)] = 4
        self.pet.celebrate_together(duration_ms=5000)
        self.assertEqual(self.pet.group_celebration.guest_scale, 1.0)
        self.assertEqual(getattr(self.pet, "_host_party_scale", 1.0), 1.0)
        self.pet._close_group_celebration()

    def test_host_plays_her_birthday_action_when_approved(self) -> None:
        self.fake.approved[("chorong", BIRTHDAY_ACTION)] = 4
        self.pet.preview_birthday_event()
        self.assertEqual(self.pet.coord.action, BIRTHDAY_ACTION)
        self.pet._close_group_celebration()

    def test_standby_takes_the_guests_away(self) -> None:
        self.pet.preview_birthday_event()
        windows = [w for w, *_ in self.pet.group_celebration.windows]
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            self.pet.settings["standby_lock_workstation"] = False
            self.pet.open_standby_screen()
            self.assertIsNone(self.pet.group_celebration)
            self.assertFalse(any(w.winfo_exists() for w in windows))
            self.pet.standby_overlay.handle_exit(None)

    def test_guests_close_themselves(self) -> None:
        self.pet.celebrate_together(duration_ms=50)
        windows = [w for w, *_ in self.pet.group_celebration.windows]
        deadline = 200
        while self.pet.group_celebration is not None and deadline:
            self.pet.root.update()
            self.pet.root.after(10)
            deadline -= 1
        self.assertIsNone(self.pet.group_celebration)
        self.assertFalse(any(w.winfo_exists() for w in windows))

    def test_celebrate_together_opens_all_guests_synchronously_without_stagger(self) -> None:
        # Undo setUp's SYNC_BUDGET_S patch to prove celebrate_together itself does not stagger.
        with mock.patch("app.group_celebration.SYNC_BUDGET_S", 0.0):
            self.pet.celebrate_together(duration_ms=1000)
        party = self.pet.group_celebration
        self.assertIsNotNone(party)
        self.assertFalse(party.loading)
        self.assertEqual(party.members_shown, 4)
        self.assertEqual(self.pet.frame_idx, 0)
        self.pet._close_group_celebration()

    def test_anniversary_scene_keeps_pet_withdrawn_while_toast_bubble_shows(self) -> None:
        self.pet.speech.hold(False)
        self.pet.tray = mock.MagicMock()
        fake_scene = mock.MagicMock()
        with mock.patch("app.main.AnniversaryScene", return_value=fake_scene):
            self.pet.preview_anniversary_event()
        self.assertIs(self.pet.anniversary_scene, fake_scene)
        self.assertEqual(self.pet.window.state(), "withdrawn")
        self.assertIsNotNone(self.pet.active_bubble)
        self.pet.tray.set_visible_state.assert_not_called()
        self.pet._on_anniversary_scene_done()
        self.assertIsNone(self.pet.anniversary_scene)
        self.assertNotEqual(self.pet.window.state(), "withdrawn")


class RealRegistryTest(unittest.TestCase):
    """What the approved registry gives today (no faking)."""

    def test_unregistered_actions_are_absent_not_idle(self) -> None:
        from app.action_frames import available_actions, load_exact_action
        from app.paths import resource_dir
        from app.sprites import SpriteLibrary
        lib = SpriteLibrary(resource_dir(), display_px=160)
        if lib.registry is None:
            self.skipTest("registry missing")
        self.assertIsNone(load_exact_action(lib, "chorong", "no_such_action"))
        self.assertEqual(available_actions(lib, "chorong", ("no_such_action",)), ())
        cheer = load_exact_action(lib, "chorong", "cheer")
        root = tk.Tk()
        self.addCleanup(root.destroy)
        base = lib.load_member("chorong", root)._pil["cheer"]
        # Same pixels as the pet's own base frames: same scale, same feet.
        self.assertEqual([im.tobytes() for im in cheer.frames], [im.tobytes() for im in base])
        self.assertEqual(cheer.offset, (0, 0))

    def test_large_canvas_needs_the_desktop_tag_and_lands_on_the_walk_feet(self) -> None:
        import dataclasses
        from app.action_frames import load_exact_action
        from app.paths import resource_dir
        from app.sprites import SpriteLibrary
        from app.standby import walk_feet_point
        lib = SpriteLibrary(resource_dir(), display_px=160)
        if lib.registry is None or lib.registry.resolve("chorong", "festival_christmas") is None:
            self.skipTest("no 384 action registered")
        original = lib.registry.resolve

        def tagged(member, action):
            spec = original(member, action)
            if spec is not None and action == "festival_christmas":
                spec = dataclasses.replace(spec, tags=tuple(spec.tags) + ("desktop_action",))
            return spec

        with mock.patch.object(lib.registry, "resolve", side_effect=tagged):
            big = load_exact_action(lib, "chorong", "festival_christmas")
        self.assertIsNotNone(big)
        dx, dy = big.offset
        self.assertLess(dx, 0)
        self.assertLess(dy, 0)                                     # taller than the base box
        feet_y = walk_feet_point(160)[1]
        for frame in big.frames:
            bottom = frame.getchannel("A").getbbox()[3] + dy
            self.assertLessEqual(abs(bottom - feet_y), 4)          # on the walk feet line


if __name__ == "__main__":
    unittest.main()
