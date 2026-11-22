"""Wave 6 behavior checks: persistence, packed cursors, idle work and cadence."""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
import ctypes
import datetime as dt
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import PandaPet, GlobalMode
from app.storage.settings import PersistenceService, DEFAULT_SETTINGS, DEFAULT_RUNTIME
from app.platform.win32 import WorkArea


@contextmanager
def pet_at(data, onboarding=True):
    if not (Path(data) / 'settings.json').exists():
        PersistenceService(Path(data)).save(dict(DEFAULT_SETTINGS, mode='manual', manual_character='eunji', onboarding_prompted=onboarding), dict(DEFAULT_RUNTIME))
    with patch('app.main.PandaSystemTray', return_value=MagicMock()), patch('app.main.GlobalHotkeyManager', return_value=MagicMock()), patch('app.main.WindowsNotificationMonitor', return_value=MagicMock()), patch('app.main.is_workstation_locked', return_value=False), patch('app.main.get_system_idle_seconds', return_value=0.0):
        pet = PandaPet(data_dir=Path(data))
    try:
        yield pet
    finally:
        pet.close()


class Wave6Regressions(unittest.TestCase):
    def test_size_switch_clears_all_old_action_cache_entries(self):
        with tempfile.TemporaryDirectory() as td, pet_at(td) as pet:
            old_px = pet.sprites.display_px
            for facing in (1, -1):
                pet._actions().put((pet.char_key, "feed_americano", old_px, facing), None)
            pet.set_pet_size("large")
            self.assertNotEqual(pet.sprites.display_px, old_px)
            self.assertTrue(all(key[2] != old_px for key in pet._actions().keys()))

    def test_cameo_guest_sets_noactivate_once_after_first_show(self):
        from app.cameo_view import CameoActorWindow

        photo = Mock()
        photo.width.return_value = photo.height.return_value = 192
        sprites = SimpleNamespace(frames={"idle": [photo]}, get=lambda *_: [photo],
                                  frame_ms=lambda *_: 180, offset=lambda *_: (0, 0))
        desktop = Mock()
        order = Mock()
        window = Mock()
        window.wm_frame.return_value = "0x1234"
        order.attach_mock(window.deiconify, "deiconify")
        order.attach_mock(desktop.set_noactivate, "set_noactivate")
        with patch("app.cameo_view.tk.Toplevel", return_value=window), patch("app.cameo_view.tk.Canvas"):
            view = CameoActorWindow(Mock(), sprites, desktop=desktop)
        frame = SimpleNamespace(action="idle", facing=1, x=100, y=100, alpha=1)
        view.render(frame, 0)
        view.render(frame, 180)
        self.assertEqual([call[0] for call in order.mock_calls], ["deiconify", "set_noactivate"])
        desktop.set_noactivate.assert_called_once_with(0x1234)

    def test_cursor_toast_uses_current_language(self):
        from app.i18n import LOCALES, t

        messages = set()
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                pet = Mock(lang=lang, settings={})
                self.assertIn("cursor_applied_toast", LOCALES[lang])
                PandaPet.set_mouse_cursor(pet, "mitten_pixel")
                cursor = t("cursor_mitten_pixel", lang)
                message = t("cursor_applied_toast", lang, cursor=cursor)
                pet._toast.assert_called_once_with(message, duration_ms=2500)
                self.assertIn(cursor, message)
                self.assertEqual(pet.settings["mouse_cursor"], "mitten_pixel")
                messages.add(message)
        self.assertEqual(len(messages), 3)

    def test_walk_arrival_at_current_position_preserves_both_facings(self):
        for x, target_x in ((150, 150), (0, -4), (1808, 2000)):
            for facing in (1, -1):
                with self.subTest(x=x, target_x=target_x, facing=facing):
                    pet = SimpleNamespace(active_bubble=None, settings={}, x=x, y=0, width=192, height=192,
                                          direction=facing, target_roam_x=target_x, state="walk", _set_ambient=Mock(),
                                          desktop=Mock(work_area_for_point=Mock(return_value=WorkArea(0, 0, 2000, 1080))))
                    PandaPet.step_walk(pet)
                    self.assertEqual((pet.x, pet.direction), (x, facing))
                    self.assertIsNone(pet.target_roam_x)
                    pet._set_ambient.assert_called_once_with("idle")

    def test_custom_cycle_length_stays_positive_for_empty_frames(self):
        pet = Mock(dragging=True, _visual_action=Mock(return_value="wave"),
                   _action_frames=Mock(return_value=([], 140, (0, 0))))
        self.assertEqual(PandaPet.cycle_length(pet), 1)

    def test_repeated_render_avoids_unchanged_canvas_uploads(self):
        from app.cameo_view import CameoActorWindow
        from app.engine.contracts import CameoPhase
        from app.group_celebration import GroupCelebration
        photo, next_photo = (Mock(width=Mock(return_value=192), height=Mock(return_value=192))
                             for _ in range(2))
        view = CameoActorWindow.__new__(CameoActorWindow)
        view.sprites = SimpleNamespace(get=lambda *a: [photo, next_photo], frame_ms=lambda *a: 140,
                                       offset=lambda *a: (0, 0))
        view.canvas, view.win, view.image = Mock(), Mock(), 1
        view._shown, view._alpha, view._photo, view._geometry = True, 1.0, None, None
        area = WorkArea(100, 0, 1000, 500)
        frame = SimpleNamespace(phase=CameoPhase.ENTER, action="walk", facing=1, x=90, y=100, alpha=0.1)
        view.render(frame, 0, area)
        view.canvas.coords.assert_called_once_with(1, -10, 0)
        view.win.geometry.assert_called_once_with("182x192+100+100")

        frame.x, frame.alpha = 96, 0.35
        view.render(frame, 40, area)
        self.assertEqual(view.canvas.itemconfigure.call_count,1)
        self.assertEqual(view.canvas.coords.call_count, 1)
        self.assertEqual(view.win.geometry.call_count, 1)
        view.win.attributes.assert_called_with("-alpha", 0.35)
        self.assertEqual(view.last_x, 90)
        view.canvas.configure.assert_not_called()

        frame.x = 105
        view.render(frame, 100, area)
        self.assertEqual(view.last_x - 90, 15)
        view.canvas.itemconfigure.assert_called_with(1, image=next_photo)
        view.canvas.coords.assert_called_with(1, 0, 0)
        view.win.geometry.assert_called_with("192x192+105+100")

        # A phase boundary updates the endpoint even with the same walk photo.
        frame.phase, frame.x, frame.alpha = CameoPhase.DONE, 1000, 0.0
        view.render(frame, 125, area)
        self.assertEqual(view.last_x, 1000)
        view.win.withdraw.assert_called_once()
        self.assertEqual(view.canvas.itemconfigure.call_count, 2)

        group=GroupCelebration.__new__(GroupCelebration);canvas=Mock()
        group.windows=[(Mock(),canvas,1,[photo,photo],140,False)]
        group.parent=Mock();group._t0=0;group._shown_photos={}
        with patch('app.group_celebration.time.monotonic',return_value=.03):
            group._tick();group._tick()
        self.assertEqual(canvas.itemconfigure.call_count,1)

    def test_portable_notices_visible_utf8_bom(self):
        from tools.build_provenance import write_portable_notices
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);write_portable_notices(ROOT,out)
            self.assertTrue((out/'README.txt').read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertEqual((out/'ASSETS-LICENSE.md').read_bytes(),(ROOT/'ASSETS-LICENSE.md').read_bytes())

    def test_onboarding_nickname_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as td:
            with pet_at(td, onboarding=False) as pet:
                pet._check_first_run_onboarding()
                dlg = pet.birthday_dialog
                self.assertIsNotNone(dlg)
                dlg.nickname.delete(0, 'end')
                dlg.nickname.insert(0, '測試粉熊 은지')
                dlg.clear()  # nickname is saved even when birthday is omitted
                self.assertEqual(pet.settings['user_nickname'], '測試粉熊 은지')
            with pet_at(td) as restarted:
                self.assertEqual(restarted.settings['user_nickname'], '測試粉熊 은지')
                self.assertTrue(restarted.settings['onboarding_prompted'])
                self.assertIsNone(restarted.birthday_dialog)
        print('ACCEPTANCE_1_ONBOARDING_PASS')

    def test_festival_frames_and_left_gaits_from_real_pak(self):
        from app.sprites import SpriteLibrary
        from app.action_frames import load_exact_action
        from app.engine.contracts import MEMBER_KEYS
        from app.resource_store import PakResourceStore
        root = ROOT / 'dist/PandaDesktopPet/_internal'
        for px in (192, 240, 384):
            library = SpriteLibrary(root, display_px=px)
            self.assertIsInstance(library.registry.store, PakResourceStore)
            for member in MEMBER_KEYS:
                base, _ = library.load_member_pil(member)
                left = base['walk_left'] if member == 'bomi' else [im.transpose(0) for im in base['walk']]
                self.assertEqual(len(left), 4)
                for im in left:
                    bb = im.getchannel('A').getbbox()
                    self.assertGreater(bb[0], 0)
                    self.assertLess(bb[2], im.width)
                for action in ('festival_christmas', 'festival_new_year', 'festival_lunar_ny', 'festival_lantern'):
                    frames = load_exact_action(library, member, action)
                    self.assertIsNotNone(frames, (member, action, px))
                    self.assertEqual(len(frames.frames), 4)
                    self.assertTrue(all(im.getchannel('A').getbbox() is not None for im in frames.frames))
        print('ACCEPTANCE_2_FESTIVAL_PAK_PASS')

    def test_countdown_milestones_and_persisted_jan1_dedup(self):
        def actor(now, seen):
            return SimpleNamespace(standby_overlay=None, calendar=SimpleNamespace(clock=SimpleNamespace(now=lambda: now)),
                _ny_countdown_year=None, _ny_announced_minutes=set(), _ny_announced_secs=set(),
                _new_year_celebrated_year=None, _new_year_celebrated=False, new_year_clock=None,
                lang='en', runtime={'festival_welcome_seen':seen}, coord=SimpleNamespace(mode=GlobalMode.NORMAL),
                dragging=False, _toast=Mock(), _start_new_year_clock=Mock(), _celebrate_new_year=Mock())
        pet = actor(dt.datetime(2026, 12, 31, 23, 30), {})
        for minute, second in ((30,0),(30,0),(59,10),(59,10),(59,20)):
            pet.calendar.clock.now = lambda m=minute,s=second: dt.datetime(2026,12,31,23,m,s)
            PandaPet._check_new_year_countdown(pet)
        self.assertEqual(pet._toast.call_count, 3)
        pet.calendar.clock.now = lambda: dt.datetime(2026,12,31,23,59,30)
        PandaPet._check_new_year_countdown(pet)
        pet._start_new_year_clock.assert_called_once_with(30)
        pet.calendar.clock.now = lambda: dt.datetime(2027,1,1,0,0)
        PandaPet._check_new_year_countdown(pet)
        pet._celebrate_new_year.assert_called_once_with(mark_welcome=True)
        with tempfile.TemporaryDirectory() as td:
            svc = PersistenceService(Path(td))
            svc.save(dict(DEFAULT_SETTINGS), dict(DEFAULT_RUNTIME, festival_welcome_seen={'new_year:2027':True}))
            _, runtime = svc.load()
            restarted = actor(dt.datetime(2027,1,1,12,0), runtime['festival_welcome_seen'])
            PandaPet._check_new_year_countdown(restarted)
            restarted._celebrate_new_year.assert_not_called()
        print('ACCEPTANCE_3_COUNTDOWN_PASS')

    def test_walk_frame_steps_scale_and_arrive_exactly(self):
        for px in (192,384):
            pet = SimpleNamespace(active_bubble=None,settings={},desktop=SimpleNamespace(work_area_for_point=lambda *a:WorkArea(0,0,2000,1080)),
                x=100.0,y=100,width=px,height=px,target_roam_x=None,direction=1,state='walk',
                sprites=SimpleNamespace(display_px=px),_visual_action=lambda:None,_place_pet=Mock())
            pet._set_ambient = lambda s:setattr(pet,'state',s)
            PandaPet.step_walk(pet)
            self.assertIsInstance(pet.x, int)
            self.assertEqual(pet.x, 100 + 7 * px // 192)
            target=pet.x+2;pet.target_roam_x=target
            for _ in range(3):
                if pet.state == 'walk':
                    PandaPet.step_walk(pet)
            self.assertEqual(pet.x,target)
            self.assertIsNone(pet.target_roam_x)
            self.assertEqual(pet.state,'idle')

    def test_walk_moves_only_on_new_frames_and_recovers_after_failure(self):
        pet = SimpleNamespace(
            _loop_after={}, _debug_paused=False, frame_idx=0, image=1,
            window=Mock(), state="walk", dragging=False, standby_overlay=None, char_key="eunji",
            direction=1, animate=Mock(), canvas=Mock(), coord=Mock(action=None),
            _shown_action=None, _shown_member="eunji", _shown_facing=1,
            _visual_action=lambda: None, _visual_facing=lambda _a: 1,
            current_frame=lambda: "gait_2", cycle_length=lambda: 4,
            step_walk=Mock(side_effect=RuntimeError("test failure")),
        )
        pet.canvas.itemcget.return_value = "gait_2"
        PandaPet.animate(pet)
        pet.step_walk.assert_not_called()

        pet.cycle_length = lambda: 1
        pet.walk_cycles = 0
        pet.target_roam_x = 150
        pet.step_walk.side_effect = None
        PandaPet.animate(pet)
        pet.step_walk.assert_called_once()
        self.assertEqual(pet.walk_cycles, 1)
        pet.step_walk.reset_mock()

        pet.cycle_length = lambda: 4
        pet.step_walk.side_effect = RuntimeError("test failure")
        pet.canvas.itemcget.return_value = "gait_1"
        with self.assertLogs("app.main", level="ERROR"):
            PandaPet.animate(pet)
        pet.step_walk.assert_called_once()
        self.assertIn("animate", pet._loop_after)
        self.assertEqual(pet.window.after.call_count, 3)
        pet.step_walk.reset_mock()
        pet._debug_paused = True
        PandaPet.animate(pet)
        pet.step_walk.assert_not_called()
        self.assertEqual(pet.window.after.call_count, 4)

    def test_bubble_geometry_after_walk_frame_step(self):
        with tempfile.TemporaryDirectory() as td, pet_at(td) as pet:
            pet._set_ambient("walk")
            pet.animate()
            self.assertIsInstance(pet.x, int)
            self.assertTrue(pet._toast("fortune test", duration_ms=2000))
            pet.window.update_idletasks()
            import re
            geometry = pet.active_bubble.window.geometry()
            self.assertRegex(geometry, r"^\d+x\d+[+-]\d+[+-]\d+$")

    def test_autostart_utf16_non_ascii_path_executes_in_wsh(self):
        import app.main as main
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'中文_한국어';(root/'app').mkdir(parents=True)
            script=root/'app/main.py';marker=script.with_suffix('.ok')
            script.write_text("from pathlib import Path; Path(__file__).with_suffix('.ok').write_text('ok',encoding='utf-8')",encoding='utf-8')
            startup=root/'startup';vbs=startup/'PandaDesktopPet.vbs'
            pet=SimpleNamespace(is_autostart_enabled=lambda:vbs.exists(),build_menu=Mock())
            with patch.object(main,'ROOT',root),patch.object(main,'STARTUP_DIR',startup),patch.object(main,'VBS_PATH',vbs):
                PandaPet.toggle_autostart(pet)
                self.assertTrue(vbs.read_bytes().startswith(b'\xff\xfe'))
                self.assertIn(str(root),vbs.read_text(encoding='utf-16'))
                # Wait for the harmless stub before removing its working directory.
                vbs.write_text(vbs.read_text(encoding='utf-16').replace(', 0, False', ', 0, True'), encoding='utf-16', newline='')
                env=dict(os.environ, PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH',''))
                result=subprocess.run(['cscript.exe','//Nologo',str(vbs)],capture_output=True,timeout=10,env=env)
                self.assertEqual(result.returncode,0,result.stderr)
                deadline=time.monotonic()+8
                while not marker.exists() and time.monotonic()<deadline:time.sleep(.025)
                self.assertTrue(marker.exists(),'WSH must launch the stub through the non-ASCII path')

    def test_idle_worker_nonblocking_cancellation_and_size_generation(self):
        from app.desktop_warmup import DesktopWarmupManager
        entered=threading.Event();release=threading.Event();manager=DesktopWarmupManager()
        def blocked(*args,**kwargs):entered.set();release.wait(3);kwargs['yield_fn']();return ({},'registry')
        try:
            with patch('app.desktop_warmup._prepare_member_pil',side_effect=blocked):
                start=time.monotonic();first=manager.schedule(ROOT,192,1,1,active_member='eunji')
                self.assertLess(time.monotonic()-start,.15)
                self.assertTrue(entered.wait(2))
                manager.cancel()
                second=manager.schedule(ROOT,384,1,1,active_member='bomi')
                self.assertGreater(second,first)
                release.set();manager.cancel()
        finally:
            release.set();manager.shutdown()
        self.assertFalse(manager._worker.is_alive())

    def test_desktop_action_cache_reused_and_size_invalidated(self):
        from app.sprites import SpriteLibrary
        import app.action_frames as af
        from app.standby import clear_standby_caches
        clear_standby_caches()
        library=SpriteLibrary(ROOT,display_px=192)
        first=af.load_exact_action(library,'eunji','special_boxing')
        self.assertIsNotNone(first)
        with patch.object(af,'_load_exact_action',wraps=af._load_exact_action) as load:
            second=af.load_exact_action(SpriteLibrary(ROOT,display_px=192),'eunji','special_boxing')
            load.assert_not_called()
            third=af.load_exact_action(SpriteLibrary(ROOT,display_px=240),'eunji','special_boxing')
            self.assertEqual(load.call_count,1)
        self.assertEqual(first.frames[0].tobytes(),second.frames[0].tobytes())
        self.assertNotEqual(first.frames[0].size,third.frames[0].size)

    def test_fortune_scaled_pil_cache_hit_and_dimensions(self):
        import app.fortune_room as room
        room._THEATER_PIL.clear()
        first=room._scaled_theater_frames(ROOT,240,135)
        with patch.object(room,'open_resource_image',wraps=room.open_resource_image) as opener:
            second=room._scaled_theater_frames(ROOT,240,135)
            opener.assert_not_called()
            third=room._scaled_theater_frames(ROOT,241,135)
            self.assertGreater(opener.call_count,0)
        self.assertIs(first,second)
        self.assertEqual(third[0].size,(241,135))

    def test_cameo_enter_expansion_paints_surface_without_unpainted_black_border(self):
        import tkinter as tk
        from PIL import Image
        from app.cameo_view import CameoActorWindow
        from app.engine.cameo import CameoFrame
        from app.engine.contracts import CameoPhase
        from app.sprites import SpriteLibrary

        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        area = WorkArea(100, 100, 500, 400)

        # 1. ULW mode: cropped DIBSection matches (view.w, view.h) with 8-bit alpha and no LWA attributes
        sprites_ulw = SpriteLibrary(ROOT, display_px=192, binary_alpha=False).load_member("bomi", root)
        view_ulw = CameoActorWindow(root, sprites_ulw, use_layered=True)
        self.addCleanup(view_ulw.destroy)
        for step, (x, alpha) in enumerate(((490, 0.05), (470, 0.25), (440, 0.55), (400, 0.85), (360, 1.0))):
            frame = CameoFrame(CameoPhase.ENTER, "bomi", "walk", x, 150, -1, alpha)
            view_ulw.render(frame, step * 100, area)
            self.assertEqual(view_ulw.win.winfo_width(), view_ulw.w)
            self.assertEqual(view_ulw.win.winfo_height(), view_ulw.h)
            if sys.platform == "win32":
                self.assertIsNotNone(view_ulw.surface)
                self.assertEqual(str(view_ulw.win.wm_attributes("-transparentcolor")), "")
                self.assertEqual((view_ulw.surface.width, view_ulw.surface.height), (view_ulw.w, view_ulw.h))
                self.assertAlmostEqual(view_ulw.surface.opacity, alpha)

        # 2. ColorKey fallback mode (use_layered=False): GDI PrintWindow has zero unpainted black border
        sprites_ck = SpriteLibrary(ROOT, display_px=192, binary_alpha=True).load_member("bomi", root)
        view = CameoActorWindow(root, sprites_ck, use_layered=False)
        self.addCleanup(view.destroy)
        for step, (x, alpha) in enumerate(((490, 0.05), (470, 0.25), (440, 0.55), (400, 0.85), (360, 1.0))):
            frame = CameoFrame(CameoPhase.ENTER, "bomi", "walk", x, 150, -1, alpha)
            view.render(frame, step * 100, area)
            self.assertEqual(view.win.winfo_width(), view.w)
            self.assertEqual(view.win.winfo_height(), view.h)
            if sys.platform == "win32":
                user32 = ctypes.windll.user32
                gdi32 = ctypes.windll.gdi32
                hwnd = int(view.win.wm_frame(), 0) if view.win.wm_frame() else view.win.winfo_id()
                hdc_win = user32.GetWindowDC(hwnd)
                hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
                hbmp = gdi32.CreateCompatibleBitmap(hdc_win, view.w, view.h)
                old = gdi32.SelectObject(hdc_mem, hbmp)
                user32.PrintWindow(hwnd, hdc_mem, 2)
                class _BMIH(ctypes.Structure):
                    _fields_ = [
                        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                        ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                        ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32),
                    ]
                bmi = _BMIH(ctypes.sizeof(_BMIH), view.w, -view.h, 1, 32, 0, 0, 0, 0, 0, 0)
                buf = ctypes.create_string_buffer(view.w * view.h * 4)
                gdi32.GetDIBits(hdc_mem, hbmp, 0, view.h, buf, ctypes.byref(bmi), 0)
                gdi32.SelectObject(hdc_mem, old)
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(hwnd, hdc_win)
                im = Image.frombuffer("RGBA", (view.w, view.h), buf, "raw", "BGRA", 0, 1)
                self.assertEqual(im.getchannel("A").histogram()[0], 0)


if __name__=='__main__':unittest.main()
