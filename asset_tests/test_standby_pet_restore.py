"""Standby return and display changes; real Tk, isolated data, no real OS lock."""
from unittest.mock import patch
from app.engine.contracts import GlobalMode
from app.platform.win32 import WorkArea
try:
    from tests import test_action_window_alignment as alignment
except ImportError:
    # Code-only exports keep these two modules together under asset_tests/.
    import test_action_window_alignment as alignment


class StandbyPetRestoreTest(alignment.ActionWindowAlignmentTest):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch('app.main.is_workstation_locked', return_value=False))
        self._idle('eunji')
        self.pet.window.update()

    def _standby_return(self):
        p = self.pet
        p.coord.set_mode(GlobalMode.STANDBY)
        p.speech.hold(True)
        p.window.withdraw()
        p.standby_overlay = None
        p.on_standby_closed()
        self.assertTrue(p._standby_resume_pending)
        self.assertEqual(p.coord.mode, GlobalMode.STANDBY)

    def _finish_resume(self):
        # Drive the queued callback deterministically, without sleeping or a real lock.
        aid = self.pet._loop_after.pop('standby_resume', None)
        if aid is not None:
            self.pet.window.after_cancel(aid)
        self.pet._resume_after_standby()
        if self.pet._standby_resume_pending and self.pet.window.winfo_viewable():
            # Let Map/Configure events run between callbacks, as mainloop does.
            self.pet.window.update()
            aid = self.pet._loop_after.pop('standby_resume', None)
            if aid is not None:
                self.pet.window.after_cancel(aid)
            self.pet._resume_after_standby()

    def test_standby_restores_mapped_pet_before_greeting_and_syncs_tray(self):
        p = self.pet
        self._standby_return()
        observed = []
        with patch.object(p, '_toast', side_effect=lambda *a, **k: observed.append(
                (p.window.winfo_viewable(), p.canvas.winfo_viewable()))):
            self._finish_resume()
        self.assertEqual(observed, [(1, 1)])
        self.assertEqual(p.coord.mode, GlobalMode.NORMAL)
        self.assertFalse(p._standby_resume_pending)
        p.tray.set_visible_state.assert_called_with(True)
        self._assert_aligned_before_idle()

    def test_locked_and_unknown_desktop_defer_without_greeting(self):
        p = self.pet
        self._standby_return()
        for value in (True, None, True):
            with patch('app.main.is_workstation_locked', return_value=value), patch.object(p, '_toast') as toast:
                self._finish_resume()
                toast.assert_not_called()
                self.assertFalse(p.window.winfo_viewable())
                self.assertEqual(p.coord.mode, GlobalMode.STANDBY)
                self.assertIn('standby_resume', p._loop_after)
        self._finish_resume()
        self.assertTrue(p.window.winfo_viewable())
        self.assertNotIn('standby_resume', p._loop_after)

    def test_unknown_desktop_is_bounded_but_true_lock_keeps_waiting(self):
        p = self.pet
        self._standby_return()
        with patch('app.main.is_workstation_locked', return_value=True):
            for _ in range(12):
                self._finish_resume()
        self.assertEqual(p._standby_unknown_count, 0)
        self.assertTrue(p._standby_resume_pending)
        with patch('app.main.is_workstation_locked', return_value=None), patch('app.main.log.warning') as warning:
            for _ in range(9):
                self._finish_resume()
                self.assertTrue(p._standby_resume_pending)
                self.assertFalse(p.window.winfo_viewable())
            self._finish_resume()
            self.assertFalse(p._standby_resume_pending)
            unknown_warnings = [c for c in warning.call_args_list
                                if str(c.args[0]).startswith('Desktop lock state unknown')]
            self.assertEqual(len(unknown_warnings), 1)
        self.assertEqual(p.coord.mode, GlobalMode.NORMAL)

    def test_restore_exceptions_have_backoff_log_limit_and_release_speech(self):
        p = self.pet
        self._standby_return()
        delays = []
        schedule = p._schedule_standby_resume
        def scheduled(delay_ms=500):
            delays.append(delay_ms)
            schedule(delay_ms)
        with patch.object(p, '_restore_pet_window', side_effect=OSError('display gone')), \
                patch.object(p, '_schedule_standby_resume', side_effect=scheduled), \
                patch('app.main.log.warning') as warning, patch.object(p.speech, 'hold', wraps=p.speech.hold) as hold:
            for _ in range(6):
                self._finish_resume()
            self.assertEqual(warning.call_count, 2)
            self.assertTrue(warning.call_args_list[0].kwargs['exc_info'])
            self.assertFalse(warning.call_args_list[-1].kwargs['exc_info'])
            hold.assert_called_with(False)
        self.assertEqual(delays, [500, 1000, 2000, 4000, 4000])
        self.assertFalse(p._standby_resume_pending)
        self.assertEqual(p.coord.mode, GlobalMode.NORMAL)
        self.assertNotIn('standby_resume', p._loop_after)
        p.tray.set_visible_state.assert_called_with(False)

    def test_tray_unknown_is_allowed_and_retry_failures_are_bounded(self):
        p = self.pet
        with patch('app.main.is_workstation_locked', return_value=None):
            p.show_from_tray()
            self.assertTrue(p.canvas.winfo_viewable())
        with patch.object(p, '_restore_pet_window', return_value=False), patch('app.main.log.warning') as warning:
            for _ in range(6):
                p.show_from_tray()
            self.assertNotIn('tray_restore', p._loop_after)
            self.assertEqual(warning.call_count, 2)
            self.assertEqual(p._tray_restore_failures, 6)
            p.tray.set_visible_state.assert_called_with(bool(p.window.winfo_viewable()))
        p.hide_to_tray()
        self.assertEqual(p._tray_restore_failures, 0)

    def test_removed_monitor_is_recovered_in_current_work_area(self):
        p = self.pet
        self._standby_return()
        p.x, p.y = 2800, 1700
        area = WorkArea(-1280, -100, 0, 900)
        with patch.object(p.desktop, 'work_area_for_point', return_value=area):
            self._finish_resume()
        self.assertEqual((p.x, p.y), area.clamp(2800, 1700, p.width, p.height))
        self._assert_aligned_before_idle()

    def test_visible_fixed_pet_rehomes_after_work_area_shrinks(self):
        p = self.pet
        p.x, p.y = 2000, 1800
        p.settings['stay_in_place'] = True
        area = WorkArea(0, 0, 800, 600)
        with patch.object(p.desktop, 'work_area_for_point', return_value=area):
            p._tick_1s_body()
        p.window.update_idletasks()
        self.assertEqual((p.x, p.y), (800 - p.width, 600 - p.height))
        self._assert_aligned_before_idle()

    def test_unlock_does_not_unhide_a_pet_hidden_to_tray(self):
        p = self.pet
        p.hide_to_tray()
        with patch('app.main.is_workstation_locked', return_value=True):
            p._tick_1s_body()
        with patch.object(p, '_restore_pet_window') as restore:
            p._tick_1s_body()
            restore.assert_not_called()
        self.assertFalse(p.window.winfo_viewable())

    def test_visible_pet_is_remapped_after_unlock(self):
        p = self.pet
        with patch('app.main.is_workstation_locked', return_value=True):
            p._tick_1s_body()
        with patch.object(p, '_restore_pet_window', wraps=p._restore_pet_window) as restore:
            p._tick_1s_body()
            restore.assert_called_once()
        self.assertTrue(p.window.winfo_viewable())

    def test_restore_keeps_active_action_padding(self):
        p = self.pet
        self._idle('eunji')
        self._feed()
        self._tick()
        p.x, p.y = 3000, 1900
        area = WorkArea(0, 0, 1000, 800)
        with patch.object(p.desktop, 'work_area_for_point', return_value=area):
            p._restore_pet_window()
        self._assert_aligned_before_idle()

    def test_restore_failure_retries_before_releasing_standby(self):
        self._standby_return()
        with patch.object(self.pet, '_restore_pet_window', side_effect=OSError('display changing')):
            self._finish_resume()
        self.assertEqual(self.pet.coord.mode, GlobalMode.STANDBY)
        self.assertTrue(self.pet._standby_resume_pending)
        self._finish_resume()
        self.assertEqual(self.pet.coord.mode, GlobalMode.NORMAL)

    def test_mapped_toplevel_with_unmapped_canvas_is_not_ready(self):
        self._standby_return()
        with patch.object(self.pet.canvas, 'winfo_viewable', return_value=False), \
                patch.object(self.pet, '_toast') as toast:
            self._finish_resume()
            toast.assert_not_called()
            self.assertTrue(self.pet._standby_resume_pending)
            self.assertEqual(self.pet.coord.mode, GlobalMode.STANDBY)
        self._finish_resume()
        self.assertFalse(self.pet._standby_resume_pending)

    def test_tray_wake_waits_for_canvas_and_hiding_cancels_retry(self):
        p = self.pet
        p.hide_to_tray()
        with patch.object(p.canvas, 'winfo_viewable', return_value=False), patch.object(p, '_toast') as toast:
            p.show_from_tray()
            toast.assert_not_called()
            self.assertIn('tray_restore', p._loop_after)
        p.hide_to_tray()
        self.assertNotIn('tray_restore', p._loop_after)
        self.assertFalse(p.window.winfo_viewable())
        p.show_from_tray()
        p.window.update()
        p.show_from_tray()
        self.assertTrue(p.canvas.winfo_viewable())
        p.tray.set_visible_state.assert_called_with(True)
