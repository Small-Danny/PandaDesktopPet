"""Isolated X5 host wiring checks; all pet settings use a temporary directory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.main import PandaPet
from app.platform.win32 import WindowsDesktopAdapter, WorkArea


class FakeDesktop:
    def __init__(self):
        self.positions = []

    def enumerate_monitors(self):
        return ((WorkArea(-1920,-120,0,1080),WorkArea(-1920,-120,0,1040)),
                (WorkArea(0,0,1920,1080),WorkArea(0,0,1920,1040)))

    def position_without_activation(self,hwnd,x,y):
        self.positions.append((x,y))

    def set_noactivate(self,hwnd):
        pass

    def show_without_activation(self,hwnd):
        pass


class DebugPlatformIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name in ("PandaSystemTray","GlobalHotkeyManager","WindowsNotificationMonitor"):
            patch = mock.patch("app.main."+name)
            patch.start()
            self.addCleanup(patch.stop)
        self.pet = PandaPet(data_dir=Path(self.temp.name))
        self.addCleanup(self.pet.close)
        self.pet.window.update()
        self.pet._dismiss_toast()

    def test_debug_force_all_base_actions_pause_step_release(self):
        pet = self.pet
        pet.open_debug_panel()
        panel = pet.debug_panel
        for action in ("idle","walk","cheer","sleep"):
            panel.bindings.play(action)
            self.assertEqual(pet.state,action)
            self.assertEqual(pet.coord.snapshot().active.request.kind,"debug.force")
        panel.bindings.step(1)
        self.assertTrue(pet._debug_paused)
        index = pet.frame_idx
        # Cancel the already scheduled animation before driving it manually.
        pet.window.after_cancel(pet._loop_after["animate"])
        pet.animate()
        self.assertEqual(pet.frame_idx,index)
        panel.bindings.release()
        self.assertFalse(pet._debug_paused)
        self.assertIsNone(pet._debug_event_id)

    def test_time_offset_does_not_change_monotonic_and_closes_cleanly(self):
        pet = self.pet
        pet.open_debug_panel()
        panel = pet.debug_panel
        before_wall,before_mono = pet.clock.now(),pet.clock.monotonic()
        panel.bindings.shift_hours(24)
        self.assertAlmostEqual((pet.clock.now()-before_wall).total_seconds(),86400,delta=1)
        self.assertLess(pet.clock.monotonic()-before_mono,1)
        panel.close()
        panel.close()
        self.assertEqual(pet.clock.offset_seconds,0)
        self.assertIsNone(panel._timer)
        self.assertTrue(pet.root.winfo_exists())

    def test_panel_switch_uses_temp_settings_and_updates_hud(self):
        pet = self.pet
        pet.open_debug_panel()
        panel = pet.debug_panel
        panel.member.set("eunji")
        panel._switch()
        self.assertEqual(pet.char_key,"eunji")
        self.assertEqual(panel.bindings.snapshot()["member"],"eunji")
        self.assertTrue((Path(self.temp.name)/"settings.json").is_file())
        with self.assertRaises(ValueError):
            panel.bindings.play("unapproved_action")

    def test_member_pick_survives_polling_but_follows_external_switch(self):
        pet = self.pet
        pet.switch_character("eunji")
        pet.open_debug_panel()
        panel = pet.debug_panel
        panel._refresh()
        self.assertEqual(panel.member.get(), "eunji")
        panel.member.set("bomi")            # picked, not applied yet
        for _ in range(3):
            panel._refresh()
        self.assertEqual(panel.member.get(), "bomi")
        pet.switch_character("hayoung")     # switched from the tray / menu
        panel._refresh()
        self.assertEqual(panel.member.get(), "hayoung")

    def test_hud_keeps_scroll_pauses_and_copies_readable_json(self):
        import json, re
        pet = self.pet
        pet.open_debug_panel()
        panel = pet.debug_panel
        self.assertEqual(panel._cursor_key, pet.settings.get("mouse_cursor", "paw_smooth"))
        panel._refresh()
        data = json.loads(panel.hud.get("1.0", "end"))
        self.assertRegex(data["wall_time"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertNotIn("cache_bytes", data)
        self.assertIn("cache_mb", data)
        for key in ("pet_size", "display_px", "ui_scale", "canvas", "frame_pad",
                    "bubble_theme", "satiety", "data_dir"):
            self.assertIn(key, data)
        self.assertEqual(Path(data["data_dir"]), Path(self.temp.name))
        panel.hud.configure(height=4)
        pet.window.update()
        panel.hud.yview_moveto(0.5)
        top = panel.hud.yview()[0]
        self.assertGreater(top, 0)
        pet.x += 1                          # content changes -> rewritten in place
        panel._refresh()
        self.assertAlmostEqual(panel.hud.yview()[0], top, delta=0.05)
        panel.hud_paused.set(True)
        before = panel.hud.get("1.0", "end")
        pet.x += 1
        panel._refresh()
        self.assertEqual(panel.hud.get("1.0", "end"), before)
        panel.copy_json()
        self.assertEqual(json.loads(pet.window.clipboard_get())["position"], [pet.x, pet.y])
        self.assertFalse(re.search(r"\d{4}-\d{2}-\d{2}T", pet.window.clipboard_get()))

    def test_force_special_action_step_and_release(self):
        pet = self.pet
        pet.switch_character("eunji")
        pet.open_debug_panel()
        panel = pet.debug_panel
        specials = pet._debug_special_actions()
        self.assertTrue(specials)
        self.assertTrue(set(specials) <= set(panel.action_box.cget("values")))
        action = next(a for a in specials if pet._action_frames("eunji", a) and len(pet._action_frames("eunji", a)[0]) > 1)
        panel.action.set(action)
        panel._play()
        snap = pet.coord.snapshot()
        self.assertEqual(snap.active.request.kind, "debug.force")
        self.assertEqual(pet._visual_action(), action)
        self.assertGreater(snap.active.request.duration_s, 600)
        panel.bindings.step(1)
        self.assertTrue(pet._debug_paused)
        self.assertEqual(pet.frame_idx, 1)
        panel.bindings.release()
        self.assertIsNone(pet._debug_event_id)
        self.assertIsNone(pet.coord.snapshot().active)

    def test_festival_costume_is_offered_when_approved(self):
        from app.action_frames import available_actions
        pet = self.pet
        for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
            pet.switch_character(member)
            approved = available_actions(pet.sprites, member, ("festival_christmas",))
            self.assertEqual("festival_christmas" in pet._debug_special_actions(), bool(approved))

    def test_holiday_jump_and_keep_state_on_close(self):
        pet = self.pet
        pet.open_debug_panel()
        panel = pet.debug_panel
        year = pet.clock.now().year
        panel.jump_to(12, 31, 23, 59)
        self.assertAlmostEqual(
            (pet.clock.now() - __import__("datetime").datetime(year, 12, 31, 23, 59)).total_seconds(), 0, delta=2)
        panel.restore_on_close.set(False)
        offset = pet.clock.offset_seconds
        panel.close()
        self.assertEqual(pet.clock.offset_seconds, offset)
        pet.clock.offset_seconds = 0

    def test_panel_follows_pet_language(self):
        from app.tools.debug_panel import TEXT
        pet = self.pet
        pet.lang = "ko"
        pet.open_debug_panel()
        self.assertEqual(pet.debug_panel.window.title(), TEXT["ko"]["title"])
        self.assertEqual(set(TEXT), {"zh_TW", "ko", "en"})
        self.assertTrue(all(set(TEXT[lang]) == set(TEXT["zh_TW"]) for lang in TEXT))

    def test_show_from_tray_never_requests_focus(self):
        pet = self.pet
        pet.hide_to_tray()
        with mock.patch.object(pet.window,"focus_force") as focus:
            pet.show_from_tray()
            pet.window.update()
        focus.assert_not_called()

    def test_drag_and_roam_use_negative_monitor_work_area(self):
        pet = self.pet
        backend = FakeDesktop()
        pet.desktop = WindowsDesktopAdapter(backend=backend)
        pet.x,pet.y = 100,100
        pet.drag_begin(SimpleNamespace(x_root=110,y_root=110))
        pet.drag_move(SimpleNamespace(x_root=-1500,y_root=80))
        self.assertEqual((pet.x,pet.y),(-1510,70))
        self.assertEqual(backend.positions[-1],(-1510,70))
        pet.end_drag()
        pet.x,pet.y = -1919,9999
        pet._dismiss_toast()
        pet._set_ambient("walk")
        pet.step_walk()
        self.assertGreaterEqual(pet.x,-1920)
        self.assertLessEqual(pet.y+pet.height,1040)


if __name__=="__main__":
    unittest.main()
