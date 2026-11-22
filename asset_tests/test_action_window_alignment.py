"""Real Tk regression for action entry/exit and synchronous replacement rendering.

Each test owns an isolated pet; operating-system hooks are mocked and its mapped
window is transparent. No user's pet process or persistent data is changed.
"""
from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from app.main import PandaPet, PET_SIZE_MAP, glyph_warmup_fonts
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService
from app.platform.win32 import WorkArea

MEMBERS = ('chorong', 'bomi', 'eunji', 'namjoo', 'hayoung')


class ActionWindowAlignmentTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='panda_alignment_'))
        env = {key: str(Path(temp) / key) for key in ('PANDA_DATA_DIR', 'LOCALAPPDATA', 'APPDATA')}
        for value in env.values():
            Path(value).mkdir()
        self.stack.enter_context(patch.dict(os.environ, env))
        self.stack.enter_context(patch.object(ctypes.windll.user32, 'LockWorkStation', return_value=True))
        monitor = self.stack.enter_context(patch('app.main.WindowsNotificationMonitor'))
        monitor.return_value.check_new_notifications.return_value = []
        for target in ('app.main.PandaSystemTray', 'app.main.GlobalHotkeyManager',
                       'app.main.PandaPet._toast', 'app.cursor_manager.apply_system_cursor_global',
                       'app.cursor_manager.restore_system_cursor_global'):
            self.stack.enter_context(patch(target))
        data = Path(env['PANDA_DATA_DIR'])
        PersistenceService(data).save(dict(DEFAULT_SETTINGS, mode='manual', manual_character='eunji',
                                           onboarding_prompted=True), dict(DEFAULT_RUNTIME))
        self.pet = PandaPet(data_dir=data)
        self.addCleanup(self.pet.close)
        if not getattr(self.pet, '_use_ulw', False):
            self.pet.window.attributes('-alpha', 0.0)
        self.pet.window.deiconify()
        self.pet.window.update_idletasks()
        self._cancel_timers()

    def _cancel_timers(self):
        for token in self.pet._loop_after.values():
            self.pet.window.after_cancel(token)
        self.pet._loop_after.clear()

    def _tick(self):
        self.pet.animate()
        self._cancel_timers()

    def _idle(self, member):
        active = self.pet.coord.snapshot().active
        if active:
            self.pet.coord.cancel(active.event_id)
        self.pet._set_ambient('idle')
        self.pet.switch_character(member)
        self.pet.x, self.pet.y = 400, 400
        self.pet._place_pet()
        self._tick()
        self.pet.window.update_idletasks()

    def _feed(self):
        self.pet.satiety = 20
        self.assertTrue(self.pet.feed('matcha_cake').saved)
        self.assertEqual(self.pet._visual_action(), 'feed_matcha_cake')

    def _assert_aligned_before_idle(self):
        # Intentionally NO update/update_idletasks: an action must not first draw
        # at the old window position while Tk still has a queued geometry change.
        p = self.pet
        self.assertEqual((p.window.winfo_x(), p.window.winfo_y()),
                         (int(p.x - p._frame_pad[0]), int(p.y - p._frame_pad[1])))
        rect = wintypes.RECT()
        self.assertTrue(ctypes.windll.user32.GetWindowRect(p._pet_hwnd(), ctypes.byref(rect)))
        expected_size = (p.width + p._frame_pad[0] + p._frame_pad[2],
                         p.height + p._frame_pad[1] + p._frame_pad[3])
        self.assertEqual((rect.left, rect.top),
                         (int(p.x - p._frame_pad[0]), int(p.y - p._frame_pad[1])))
        self.assertEqual((rect.right - rect.left, rect.bottom - rect.top), expected_size)
        self.assertEqual((p.canvas.winfo_width(), p.canvas.winfo_height()), expected_size)
        self.assertNotEqual(p.canvas.itemcget(p.image, 'state'), 'hidden')
        action = p._visual_action()
        offset = p._action_frames(p.char_key, action)[2] if action else (0, 0)
        self.assertEqual(tuple(p.canvas.coords(p.image)),
                         (p._frame_pad[0] + offset[0], p._frame_pad[1] + offset[1]))

    def test_all_members_all_sizes_enter_each_frame_and_exit_without_delayed_move(self):
        for size in PET_SIZE_MAP:
            self.pet.set_pet_size(size)
            for member in MEMBERS:
                with self.subTest(member=member, size=size):
                    self._idle(member)
                    self._feed()
                    for _ in range(4):
                        self._tick()
                        self._assert_aligned_before_idle()
                        self.pet.window.update_idletasks()
                    self.pet.coord.cancel(self.pet.coord.snapshot().active.event_id)
                    self._tick()
                    self._assert_aligned_before_idle()
                    self.assertEqual((self.pet.x, self.pet.y), (400, 400))

    def test_resizing_an_active_action_places_it_before_immediate_render(self):
        self._idle('eunji')
        self._feed()
        self._tick()
        for size in ('small', 'large', 'medium'):
            with self.subTest(size=size):
                self.pet.set_pet_size(size)
                self._assert_aligned_before_idle()
                self.pet.window.update_idletasks()

    def test_drag_clamps_base_box_independently_of_previous_action_padding(self):
        for area in (WorkArea(0, 0, 1280, 900), WorkArea(-1920, -200, 0, 880)):
            for size in PET_SIZE_MAP:
                self.pet.set_pet_size(size)
                for member in MEMBERS:
                    for right, bottom in ((False, False), (True, False),
                                          (False, True), (True, True)):
                        with self.subTest(area=area, size=size, member=member,
                                          right=right, bottom=bottom):
                            self.pet.end_drag()
                            self._idle(member)
                            self._feed()
                            self._tick()
                            self.assertTrue(any(self.pet._frame_pad))
                            self.pet.drag_begin(SimpleNamespace(x_root=440, y_root=440))
                            pointer = (area.right + 500 if right else area.left - 500,
                                       area.bottom + 500 if bottom else area.top - 500)
                            # Independent boundary expectation: do not call the same
                            # clamp helper as production to calculate the test oracle.
                            expected = (area.right - self.pet.width if right else area.left,
                                        area.bottom - self.pet.height if bottom else area.top)
                            with patch.object(self.pet.desktop, 'work_area_for_point', return_value=area):
                                self.pet.drag_move(SimpleNamespace(x_root=pointer[0], y_root=pointer[1]))
                                self.assertEqual((self.pet.x, self.pet.y), expected)
                                # Food -> drag -> idle keeps the same base position.
                                self._tick()
                                self.assertEqual((self.pet.x, self.pet.y), expected)
                                self.pet.end_drag()
                                self._tick()
                                self.assertEqual((self.pet.x, self.pet.y), expected)
                                self._assert_aligned_before_idle()

    def test_switching_member_places_replacement_before_immediate_render(self):
        for member in MEMBERS:
            self._idle('eunji')
            self._feed()
            self._tick()
            self.pet.window.update_idletasks()
            self.pet.switch_character(member)
            with self.subTest(member=member):
                self._assert_aligned_before_idle()
                self.pet.window.update_idletasks()

    def test_food_panel_and_menu_do_not_delay_action_geometry(self):
        self._idle('eunji')
        self.pet.open_food_panel()
        self.pet.food_panel.window.attributes('-alpha', 0.0)
        self.pet.window.update_idletasks()
        self.assertTrue(self.pet._has_active_subpanel())
        self._feed()
        self._tick()
        self._assert_aligned_before_idle()
        self.pet._close_food_panel()
        self._idle('eunji')
        self.pet._menu_active = True
        try:
            self._feed()
            self._tick()
            self._assert_aligned_before_idle()
        finally:
            self.pet._menu_active = False


    def test_geometry_flush_contains_the_new_frame_without_hiding_it(self):
        self._idle('eunji')
        if not getattr(self.pet, '_use_ulw', False):
            self.pet.window.attributes('-alpha', 0.8)
        self._feed()
        real_flush = self.pet.window.update_idletasks
        observed = []

        def check_flush():
            self.assertNotEqual(self.pet.canvas.itemcget(self.pet.image, 'state'), 'hidden')
            self.assertTrue(self.pet.window.winfo_viewable())
            if getattr(self.pet, '_use_ulw', False):
                expected_pil = self.pet._visual_pil_frames_and_offset('eunji', 'feed_matcha_cake')[0][0]
                self.assertIs(self.pet.current_pil_frame(), expected_pil)
                self.assertIsNotNone(self.pet.layered_surface)
                self.assertEqual(
                    (self.pet.layered_surface.width, self.pet.layered_surface.height),
                    (self.pet.width + self.pet._frame_pad[0] + self.pet._frame_pad[2],
                     self.pet.height + self.pet._frame_pad[1] + self.pet._frame_pad[3]),
                )
            else:
                expected = self.pet._action_frames('eunji', 'feed_matcha_cake')[0][0]
                self.assertEqual(self.pet.canvas.itemcget(self.pet.image, 'image'), str(expected))
                self.assertEqual(self.pet.window.attributes('-alpha'), 0)
            observed.append(True)
            real_flush()

        with patch.object(self.pet.window, 'update_idletasks', side_effect=check_flush):
            self._tick()
        self.assertTrue(observed)
        if not getattr(self.pet, '_use_ulw', False):
            self.assertAlmostEqual(self.pet.window.attributes('-alpha'), 0.8)
        self._assert_aligned_before_idle()

    def test_size_switch_resizes_the_base_box_only_while_transparent(self):
        """small -> medium -> large in the plain pose (pad stays 0) must not flash a black box."""
        self._idle('eunji')
        self.pet.set_pet_size('small')
        self._idle('eunji')
        use_ulw = bool(getattr(self.pet, '_use_ulw', False))
        if not use_ulw:
            self.pet.window.attributes('-alpha', 0.8)
        window = self.pet.window
        real_geometry = window.geometry
        resizes = []

        def watch_geometry(*args):
            if args:
                old = (window.winfo_width(), window.winfo_height())
                new = tuple(int(v) for v in args[0].split('+')[0].split('x'))
                if new != old:
                    alpha_val = 0.0 if use_ulw else float(window.attributes('-alpha'))
                    resizes.append((old, new, alpha_val))
            return real_geometry(*args)

        for size in ('medium', 'large'):
            with self.subTest(size=size), patch.object(window, 'geometry', side_effect=watch_geometry):
                resizes.clear()
                before = self.pet.width
                self.pet.set_pet_size(size)
                self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))
                self.assertGreater(self.pet.width, before)
                # Exactly one resize, made while the layered window was transparent or ULW-managed.
                self.assertEqual(len(resizes), 1, resizes)
                self.assertEqual(resizes[0][1], (self.pet.width, self.pet.height))
                self.assertEqual(resizes[0][2], 0.0)
                if use_ulw:
                    self.assertEqual(
                        (self.pet.layered_surface.width, self.pet.layered_surface.height),
                        (self.pet.width, self.pet.height),
                    )
                else:
                    self.assertAlmostEqual(float(window.attributes('-alpha')), 0.8)
                self._assert_aligned_before_idle()
                window.update_idletasks()

    def test_size_switch_rewarms_celebrations_at_the_new_size(self):
        """set_pet_size re-plans the idle desktop warmup (celebration looks) for the new px."""
        self._idle('eunji')
        self.pet.set_pet_size('small')
        self._cancel_timers()
        with patch.object(self.pet._desktop_warmup, 'schedule') as schedule:
            self.pet.set_pet_size('large')
            self.assertIn('desktop_warmup', self.pet._loop_after)
            self.pet._start_desktop_warmup()
        self.assertEqual(schedule.call_args.args[1], self.pet.sprites.display_px)
        self.assertGreater(self.pet.sprites.display_px, PET_SIZE_MAP['small'])
        self.assertEqual(len(self.pet._celebration_photos), 0)

    def test_glyph_warmup_runs_in_short_slices_then_frees_its_canvas(self):
        glyphs = ['✨', '💬', '🛠']
        with patch('app.main.warmup_glyphs', return_value=glyphs), \
             patch('app.main.GLYPH_WARMUP_SLICE_S', 0.0):
            self.pet._glyph_warmup_step()
            self.assertIn('glyph_warmup', self.pet._loop_after)     # one pair per slice, then yield
            steps = 1
            while 'glyph_warmup' in self.pet._loop_after and steps < 100:
                self._cancel_timers()
                self.pet._glyph_warmup_step()
                steps += 1
        self.assertEqual(steps, len(glyphs) * len(glyph_warmup_fonts(self.pet.lang)))
        self.assertIsNone(self.pet._glyph_warmup_canvas)
        self.assertFalse(self.pet._glyph_warmup_queue)
