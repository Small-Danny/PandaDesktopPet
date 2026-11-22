"""tests/test_cursor_manager.py — Unit tests for Kawaii Cursor Manager & Staged Cursor Files.

Validates:
1. Existence of all 4 cursor .cur files (multi-size: 32x32, 48x48) and master .png files in work/ui_icons/.
2. Win32 LoadCursorFromFileW loads valid, non-zero cursor handles for all 4 cursor types.
3. System default cursor loads valid handle (IDC_ARROW).
4. Validation and persistence of mouse_cursor setting in PersistenceService.
5. PandaPet cursor hover and set_mouse_cursor wiring.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.cursor_manager as cm
from app.storage.settings import DEFAULT_SETTINGS, VALID_MOUSE_CURSORS, PersistenceService


class TestCursorManager(unittest.TestCase):
    def test_packed_native_and_tk_cursor_share_materialized_file(self):
        key = "paw_smooth"
        raw = b"\x00\x00\x02\x00\x02\x00" + b"cursor fixture"
        with patch.object(cm, "_CURSOR_TEMP", None), patch.object(cm, "_CURSOR_PATHS", {}), \
                patch.object(cm, "_CURSOR_CACHE", {}), patch.object(cm, "get_cursor_path", return_value=None), \
                patch.object(cm, "read_resource_bytes", return_value=raw) as read, \
                patch.object(cm.ctypes.windll.user32, "LoadCursorFromFileW", return_value=123) as native, \
                patch.object(cm, "_load_cursor_from_bytes") as fallback:
            try:
                spec = cm.get_tkinter_cursor_spec(key)
                self.assertEqual(cm.load_cursor(key), 123)
                path, = cm._CURSOR_PATHS.values()
                self.assertEqual(path.read_bytes(), raw)
                self.assertIn(path.resolve().as_posix(), spec)
                native.assert_called_once_with(str(path.resolve()))
                read.assert_called_once()
                fallback.assert_not_called()
            finally:
                cm.cleanup_cursor_files()

    def test_cursor_refresh_covers_all_anniversary_dome_and_countdown_widgets(self):
        import tkinter as tk
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.main import PandaPet

        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.withdraw()

        def surface():
            win = tk.Toplevel(root)
            win.withdraw()
            return win, tk.Canvas(win)

        ann_win, ann_canvas = surface()
        vis_win, vis_canvas = surface()
        count_win, count_canvas = surface()
        actor_win, actor_canvas = surface()
        bubble_win, bubble_canvas = surface()
        anniversary = SimpleNamespace(win=ann_win, canvas=ann_canvas, vis_win=vis_win, vis_canvas=vis_canvas)
        countdown = SimpleNamespace(win=count_win, canvas=count_canvas)
        dome = SimpleNamespace(bubble_window=bubble_win, _bubble_canvas=bubble_canvas,
                               actor_windows={"eunji": actor_win, "bad": False},
                               _actor_canvases={"eunji": (actor_canvas, 14), "bad": (None,)})
        expected = ((anniversary, {ann_win, ann_canvas, vis_win, vis_canvas}),
                    (countdown, {count_win, count_canvas}),
                    (dome, {actor_win, actor_canvas, bubble_win, bubble_canvas}))
        for scene, widgets in expected:
            self.assertEqual(set(PandaPet._collect_panel_cursor_widgets(scene)), widgets)
        pet = SimpleNamespace(window=root, canvas=tk.Canvas(root), settings={},
                              anniversary_scene=anniversary, new_year_clock=countdown,
                              dome_preview=dome, _collect_panel_cursor_widgets=PandaPet._collect_panel_cursor_widgets)
        with patch.object(cm, "apply_cursor_to_widgets") as apply, patch.object(cm, "set_window_cursor"):
            for cursor_key in ("mitten_pixel", "system"):
                PandaPet.apply_mouse_cursor(pet, cursor_key)
                actual, applied_key = apply.call_args.args
                self.assertEqual(set(actual), set().union(*(widgets for _, widgets in expected)))
                self.assertEqual(applied_key, cursor_key)
                for scene, _ in expected:
                    self.assertEqual(scene._cursor_key, cursor_key)

    def test_exit_handler_restores_only_an_applied_global_cursor(self):
        import ctypes
        import runpy
        from unittest.mock import Mock, patch

        user32 = Mock()
        user32.SystemParametersInfoW.side_effect = [False, True]
        with patch("atexit.register") as register, patch.object(ctypes.windll, "user32", user32):
            isolated = runpy.run_path(cm.__file__)
            restore = isolated["restore_system_cursor_global"]
            register.assert_any_call(restore)
            self.assertTrue(restore())
            user32.SystemParametersInfoW.assert_not_called()
            restore.__globals__["_GLOBAL_APPLIED"] = True
            self.assertFalse(restore())
            self.assertTrue(restore())
            self.assertTrue(restore())
            self.assertEqual(user32.SystemParametersInfoW.call_count, 2)
            user32.SystemParametersInfoW.assert_called_with(cm.SPI_SETCURSORS, 0, 0, 0)

    def test_tk_cursor_path_with_spaces_loads(self):
        import shutil
        import tkinter as tk
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix="panda cursor ") as tmp:
            path = Path(tmp) / "custom cursor.cur"
            shutil.copyfile(cm.get_cursor_path("paw_smooth"), path)
            root = tk.Tk()
            try:
                root.withdraw()
                with patch.object(cm, "get_cursor_path", return_value=path):
                    spec = cm.get_tkinter_cursor_spec("paw_smooth")
                self.assertEqual(root.tk.splitlist(spec), (f"@{path.resolve().as_posix()}",))
                canvas = tk.Canvas(root, cursor=spec)
                self.assertEqual(str(canvas.cget("cursor")), spec)
            finally:
                root.destroy()

    @unittest.skipUnless((ROOT / "dist/PandaDesktopPet/_internal/assets.pak").is_file(),
                         "native packaged-cursor probe needs an existing assets.pak")
    def test_pak_cursor_surfaces_native_motion_and_temp_cleanup(self):
        import ctypes
        from unittest.mock import patch
        from app.main import PandaPet
        from app.group_celebration import GroupCelebration
        from app.cameo_view import CameoActorWindow
        from tests.test_wave6_regressions import pet_at

        u = ctypes.WinDLL('user32')
        u.GetCursor.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        u.SendMessageW.restype = ctypes.c_ssize_t
        packed = ROOT/'dist/PandaDesktopPet/_internal'
        cache = dict(cm._CURSOR_CACHE)
        raw_call = cm._CallWindowProc
        observed = []
        cm.cleanup_cursor_files()
        try:
            with patch.object(cm, 'RES_ROOT', packed), patch.object(cm, 'UI_ICONS_DIR', packed/'work/ui_icons'), tempfile.TemporaryDirectory() as td:
                cm._CURSOR_CACHE.clear()
                with patch.object(cm, 'read_resource_bytes', wraps=cm.read_resource_bytes) as read:
                    spec = cm.get_tkinter_cursor_spec('mitten_pixel')
                    from tkinter import Tcl
                    cursor, = Tcl().splitlist(spec)
                    self.assertTrue(cursor.startswith('@'))
                    path = Path(cursor[1:])
                    self.assertTrue(path.is_file())
                    self.assertEqual(cm.get_tkinter_cursor_spec('mitten_pixel'), spec)
                    self.assertEqual(read.call_count, 1)
                with pet_at(td) as pet:
                    pet.set_mouse_cursor('mitten_pixel')
                    pet._toast('cursor regression', duration_ms=60000)
                    pet.open_fortune_room()
                    first = pet.fortune_dialog
                    pet.open_fortune_room()
                    self.assertIs(first, pet.fortune_dialog)
                    group = GroupCelebration(pet.root, pet.sprites, ['bomi'], (500,400,192,192), (0,1800))
                    cameo = CameoActorWindow(pet.root, pet.sprites.load_member('hayoung', pet.root))
                    pet.group_celebration = group
                    pet.cameo_window = cameo
                    PandaPet._apply_cursor_to_panel(pet, group)
                    PandaPet._apply_cursor_to_panel(pet, cameo)
                    pet.root.update()
                    widgets = [pet.canvas, pet.active_bubble.canvas, first.canvas, group.windows[0][1], cameo.canvas]
                    for widget in widgets:
                        self.assertEqual(str(widget.cget('cursor')), spec)
                        self.assertIn(int(widget.winfo_id()), cm._HWND_HOOKS)
                    arrow = cm.load_cursor('system')
                    def observe(orig, hwnd, msg, wp, lp):
                        ret = raw_call(orig, hwnd, msg, wp, lp)
                        if msg == 0x0200:
                            observed.append(int(u.GetCursor() or 0))
                        return ret
                    with patch.object(cm, '_CallWindowProc', side_effect=observe):
                        for i in range(80):
                            cm.reapply_active_cursor('mitten_pixel')
                            u.SendMessageW(int(pet.canvas.winfo_id()), 0x0200, int(i >= 40), (60 << 16) | 60)
                    self.assertEqual(len(observed), 80)
                    self.assertNotIn(arrow, observed, 'original Tk procedure must not temporarily reset to IDC_ARROW')
                    pet.set_mouse_cursor('paw_pixel')
                    self.assertIn('paw_pixel', str(first.canvas.cget('cursor')))
                    first.close();pet.open_fortune_room()
                    self.assertIsNot(first, pet.fortune_dialog)
                    self.assertIn('paw_pixel', str(pet.fortune_dialog.canvas.cget('cursor')))
                    pet.set_mouse_cursor('system')
                    for widget in widgets[:-2] + [cameo.canvas, group.windows[0][1]]:
                        if widget.winfo_exists():
                            self.assertNotIn(int(widget.winfo_id()), cm._HWND_HOOKS)
                    group.close();cameo.destroy()
                self.assertFalse(path.exists(), 'PandaPet.close removes materialized cursor files')
            print('PAK_NATIVE_CURSOR_TRANSITIONS: 0/80 arrows (40 hover + 40 button motion)')
        finally:
            cm.cleanup_cursor_files()
            cm._CURSOR_CACHE.clear();cm._CURSOR_CACHE.update(cache)

    def test_stale_hook_entries_are_pruned_on_every_entry_point(self) -> None:
        """A hook whose HWND died without WM_NCDESTROY reaching us must not linger in _HWND_HOOKS."""
        dead = 0x7FFFFFF0
        self.assertFalse(cm._is_win32_window(dead))
        for call in (
            lambda: cm.apply_cursor_to_widgets((), "system"),
            lambda: cm.reset_window_cursor(dead),
            lambda: cm._install_cursor_hook(dead, "paw_smooth"),
            lambda: cm.release_cursor_hooks(()),
        ):
            cm._HWND_HOOKS[dead] = [0, None, "paw_smooth", 0]
            try:
                call()
                self.assertNotIn(dead, cm._HWND_HOOKS)
            finally:
                cm._HWND_HOOKS.pop(dead, None)

    def test_cursor_files_exist(self) -> None:
        """All 4 staged cursor types must have both .png and .cur files in work/ui_icons."""
        for key in ("paw_smooth", "mitten_smooth", "paw_pixel", "mitten_pixel"):
            cur_path = cm.get_cursor_path(key)
            self.assertIsNotNone(cur_path, f"Missing path for cursor key: {key}")
            self.assertTrue(cur_path.exists(), f"Missing cursor file: {cur_path}")
            png_path = cur_path.with_suffix(".png")
            self.assertTrue(png_path.exists(), f"Missing PNG preview file: {png_path}")

    def test_cursor_handles_load_valid(self) -> None:
        """Every cursor file must be a valid Win32 cursor that LoadCursorFromFileW accepts."""
        for key in ("paw_smooth", "mitten_smooth", "paw_pixel", "mitten_pixel", "system"):
            hcur = cm.load_cursor(key)
            self.assertNotEqual(hcur, 0, f"Failed to load cursor handle for: {key}")

    def test_settings_validation_and_persistence(self) -> None:
        """mouse_cursor setting must be validated against VALID_MOUSE_CURSORS."""
        self.assertIn("mouse_cursor", DEFAULT_SETTINGS)
        self.assertEqual(DEFAULT_SETTINGS["mouse_cursor"], "paw_smooth")
        for key in ("paw_smooth", "mitten_smooth", "paw_pixel", "mitten_pixel", "system"):
            self.assertIn(key, VALID_MOUSE_CURSORS)

        with tempfile.TemporaryDirectory() as td:
            svc = PersistenceService(Path(td))
            s, r = svc.load()
            self.assertEqual(s.get("mouse_cursor"), "paw_smooth")

            # Update to custom cursor
            s["mouse_cursor"] = "mitten_pixel"
            svc.save(s, r)
            s2, _ = svc.load()
            self.assertEqual(s2.get("mouse_cursor"), "mitten_pixel")

            # Invalid cursor key must raise ValueError
            s2["mouse_cursor"] = "invalid_style"
            with self.assertRaises(ValueError):
                svc.save(s2, r)

    def test_hovering_the_pet_never_touches_the_system_cursors(self) -> None:
        """Without the OS-wide option nothing system-wide may be called (it runs on every hover)."""
        from unittest import mock
        with mock.patch.object(cm, "_GLOBAL_APPLIED", False), mock.patch.object(cm.ctypes, "windll") as windll:
            self.assertTrue(cm.restore_system_cursor_global())
            windll.user32.SystemParametersInfoW.assert_not_called()
        with mock.patch.object(cm, "_GLOBAL_APPLIED", True), mock.patch.object(cm.ctypes, "windll") as windll:
            cm.restore_system_cursor_global()
            windll.user32.SystemParametersInfoW.assert_called_once()
            self.assertFalse(cm._GLOBAL_APPLIED)

    def test_tkinter_cursor_spec(self) -> None:
        """get_tkinter_cursor_spec returns @path format or empty string for system."""
        spec = cm.get_tkinter_cursor_spec("paw_smooth")
        self.assertTrue(spec.startswith("@"))
        self.assertTrue(spec.endswith("cursor_paw_smooth.cur"))
        self.assertEqual(cm.get_tkinter_cursor_spec("system"), "")

    def test_pandapet_cursor_integration(self) -> None:
        """PandaPet applies and changes canvas cursor natively without error."""
        from unittest import mock
        from app.main import PandaPet
        from app.storage.settings import DEFAULT_RUNTIME

        with tempfile.TemporaryDirectory() as td:
            PersistenceService(Path(td)).save(
                dict(DEFAULT_SETTINGS, mode="manual", manual_character="bomi", mouse_cursor="paw_smooth"),
                dict(DEFAULT_RUNTIME),
            )
            pet = PandaPet(data_dir=Path(td))
            self.addCleanup(pet.close)

            # 1. On init, canvas must have custom cursor
            init_cur = pet.canvas.cget("cursor")
            self.assertTrue(init_cur.startswith("@"))
            self.assertIn("cursor_paw_smooth.cur", init_cur)

            # 2. Switch to mitten_pixel
            pet.set_mouse_cursor("mitten_pixel")
            self.assertEqual(pet.settings.get("mouse_cursor"), "mitten_pixel")
            cur_now = pet.canvas.cget("cursor")
            self.assertIn("cursor_mitten_pixel.cur", cur_now)

            # 3. Switch to system
            pet.set_mouse_cursor("system")
            self.assertEqual(pet.settings.get("mouse_cursor"), "system")
            self.assertEqual(pet.canvas.cget("cursor"), "")

    def test_pak_hook_survives_wm_mousemove_and_mouse_clicks(self) -> None:
        """Under .pak mode (spec == ''), Tk WM_MOUSEMOVE/clicks must not overwrite custom HCURSOR back to IDC_ARROW."""
        import ctypes
        import ctypes.wintypes as wt
        from types import SimpleNamespace
        from unittest import mock
        from app.main import PandaPet
        from app.storage.settings import DEFAULT_RUNTIME

        u32 = ctypes.windll.user32
        u32.GetCursor.restype = ctypes.c_void_p
        u32.SetCursor.argtypes = [ctypes.c_void_p]
        u32.SetCursor.restype = ctypes.c_void_p
        u32.SendMessageW.argtypes = [ctypes.c_void_p, wt.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
        u32.SendMessageW.restype = ctypes.c_ssize_t

        cur_bytes = (ROOT / "work" / "ui_icons" / "cursor_paw_pixel.cur").read_bytes()
        mitten_bytes = (ROOT / "work" / "ui_icons" / "cursor_mitten_smooth.cur").read_bytes()
        orig_cache = dict(cm._CURSOR_CACHE)
        cm._CURSOR_CACHE.clear()
        try:
            with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as empty_ui:
                PersistenceService(Path(td)).save(
                    dict(DEFAULT_SETTINGS, mode="manual", manual_character="eunji", mouse_cursor="paw_pixel"),
                    dict(DEFAULT_RUNTIME),
                )

                def fake_read_bytes(rel: str, root=None) -> bytes:
                    if rel.endswith("cursor_paw_pixel.cur"):
                        return cur_bytes
                    if rel.endswith("cursor_mitten_smooth.cur"):
                        return mitten_bytes
                    return (ROOT / rel).read_bytes()

                with mock.patch.object(cm, "UI_ICONS_DIR", Path(empty_ui)), \
                     mock.patch.object(cm, "read_resource_bytes", side_effect=fake_read_bytes):
                    pet = PandaPet(data_dir=Path(td))
                    self.addCleanup(pet.close)
                    pet.window.update()
                    self.assertTrue(pet.canvas.cget("cursor").startswith("@"))
                    h_paw = cm.load_cursor("paw_pixel")
                    h_sys = cm.load_cursor("system")
                    self.assertNotEqual(h_paw, 0)

                    # Mapped outer frame + pet canvas + pink menu canvas must all keep h_paw on WM_MOUSEMOVE & clicks
                    pet.show_menu(SimpleNamespace(x_root=pet.x + 80, y_root=pet.y + 80))
                    pet.window.update()
                    self.assertIsNotNone(pet.pink_menu)

                    for widget in (pet.canvas, pet.pink_menu.canvas):
                        hwnd = int(widget.winfo_id())
                        self.assertIn(hwnd, cm._HWND_HOOKS)
                        u32.SetCursor(h_sys)
                        u32.SendMessageW(hwnd, cm.WM_SETCURSOR, hwnd, cm.HTCLIENT | (0x0200 << 16))
                        self.assertEqual(int(u32.GetCursor() or 0), h_paw)
                        u32.SendMessageW(hwnd, 0x0200, 0, (40 << 16) | 40)  # WM_MOUSEMOVE
                        self.assertEqual(int(u32.GetCursor() or 0), h_paw)
                        u32.SendMessageW(hwnd, 0x0201, 1, (40 << 16) | 40)  # WM_LBUTTONDOWN
                        self.assertEqual(int(u32.GetCursor() or 0), h_paw)
                        u32.SendMessageW(hwnd, 0x0202, 0, (40 << 16) | 40)  # WM_LBUTTONUP
                        self.assertEqual(int(u32.GetCursor() or 0), h_paw)

                    pet._close_pink_menu()
                    pet.set_mouse_cursor("mitten_smooth")
                    pet.window.update()
                    h_mitten = cm.load_cursor("mitten_smooth")
                    ch = int(pet.canvas.winfo_id())
                    u32.SetCursor(h_sys)
                    u32.SendMessageW(ch, 0x0200, 0, (45 << 16) | 45)
                    self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                    pet.set_mouse_cursor("system")
                    pet.window.update()
                    self.assertNotIn(ch, cm._HWND_HOOKS)
        finally:
            cm._CURSOR_CACHE.clear()
            cm._CURSOR_CACHE.update(orig_cache)


class TestCursorIsolationAndPanelHooks(unittest.TestCase):
    """Regression coverage for per-HWND isolation, wm_frame/<Map> hooks, and panel tab rebuilds."""

    @unittest.skipUnless(sys.platform == "win32", "Win32 HWND cursor hooks only apply on Windows")
    def test_wm_frame_hook_no_class_bleed_and_restore_default_tk_cursor(self) -> None:
        import ctypes
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        panel = tk.Toplevel(root)
        panel_canvas = tk.Canvas(panel, width=80, height=60)
        panel_canvas.pack()
        guide_text = tk.Text(panel, cursor="arrow", width=20, height=4)
        guide_text.pack()

        unhooked = tk.Toplevel(root)
        unhooked_canvas = tk.Canvas(unhooked, width=80, height=60)
        unhooked_canvas.pack()

        panel.deiconify()
        unhooked.deiconify()
        root.update_idletasks()
        root.update()

        u32 = ctypes.WinDLL("user32")
        get_cls = u32.GetClassLongPtrW
        get_cls.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_cls.restype = ctypes.c_void_p

        orig_top_cls = int(get_cls(int(unhooked.winfo_id()), cm.GCLP_HCURSOR) or 0)
        orig_child_cls = int(get_cls(int(unhooked_canvas.winfo_id()), cm.GCLP_HCURSOR) or 0)

        try:
            cm.apply_cursor_to_widgets((panel, panel_canvas, guide_text), "paw_smooth")
            root.update_idletasks()

            panel_hwnd = int(panel.winfo_id())
            canvas_hwnd = int(panel_canvas.winfo_id())
            text_hwnd = int(guide_text.winfo_id())
            frame_str = str(panel.wm_frame() or "").strip()
            frame_hwnd = int(frame_str, 16) if frame_str.startswith("0x") else (int(frame_str) if frame_str else 0)

            self.assertIn(panel_hwnd, cm._HWND_HOOKS)
            self.assertIn(canvas_hwnd, cm._HWND_HOOKS)
            self.assertIn(text_hwnd, cm._HWND_HOOKS)
            if frame_hwnd and frame_hwnd != panel_hwnd:
                self.assertIn(frame_hwnd, cm._HWND_HOOKS)
            self.assertNotIn(int(unhooked.winfo_id()), cm._HWND_HOOKS)
            self.assertNotIn(int(unhooked_canvas.winfo_id()), cm._HWND_HOOKS)

            # Shared WNDCLASS GCLP_HCURSOR must never bleed across unhooked windows.
            self.assertEqual(int(get_cls(int(unhooked.winfo_id()), cm.GCLP_HCURSOR) or 0), orig_top_cls)
            self.assertEqual(int(get_cls(int(unhooked_canvas.winfo_id()), cm.GCLP_HCURSOR) or 0), orig_child_cls)
            self.assertEqual(getattr(guide_text, "_default_tk_cursor", ""), "arrow")

            # Switching back to system must unhook HWNDs and restore explicit Tk cursors.
            cm.apply_cursor_to_widgets((panel, panel_canvas, guide_text), "system")
            self.assertEqual(guide_text.cget("cursor"), "arrow")
            self.assertNotIn(panel_hwnd, cm._HWND_HOOKS)
            self.assertNotIn(canvas_hwnd, cm._HWND_HOOKS)
            self.assertNotIn(text_hwnd, cm._HWND_HOOKS)
            if frame_hwnd and frame_hwnd != panel_hwnd:
                self.assertNotIn(frame_hwnd, cm._HWND_HOOKS)
        finally:
            try:
                panel.destroy()
            except Exception:
                pass
            try:
                unhooked.destroy()
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass

    @unittest.skipUnless(sys.platform == "win32", "Win32 HWND cursor hooks only apply on Windows")
    def test_pre_deiconify_map_hook_settings_tab_rebuild_and_no_enter_bind_leak(self) -> None:
        import tkinter as tk
        from app.main import PandaPet
        from app.settings_panel import SettingsPanel

        root = tk.Tk()
        root.withdraw()
        try:
            # 1. Pre-deiconify Toplevel (flyout pattern): <Map> must hook mapped wm_frame() once.
            fly = tk.Toplevel(root)
            fly.withdraw()
            fc = tk.Canvas(fly, width=60, height=40)
            fc.pack()
            cm.apply_cursor_to_widgets((fly, fc), "mitten_smooth")
            map_script = fly.bind("<Map>")
            fly.deiconify()
            root.update_idletasks()
            root.update()
            frame_str = str(fly.wm_frame() or "").strip()
            frame_hwnd = int(frame_str, 16) if frame_str.startswith("0x") else (int(frame_str) if frame_str else 0)
            self.assertIn(int(fly.winfo_id()), cm._HWND_HOOKS)
            self.assertIn(int(fc.winfo_id()), cm._HWND_HOOKS)
            if frame_hwnd:
                self.assertIn(frame_hwnd, cm._HWND_HOOKS)
            cm.apply_cursor_to_widgets((fly, fc), "mitten_smooth")
            self.assertEqual(fly.bind("<Map>"), map_script)
            fly.destroy()

            # 2. SettingsPanel tab rebuild: newly created Entry widgets must keep active cursor.
            sp = SettingsPanel(parent=root, state=dict(DEFAULT_SETTINGS), char_key="chorong", lang="zh_TW")
            sp._cursor_key = "mitten_smooth"
            cm.apply_cursor_to_widgets((sp.window, sp.canvas), "mitten_smooth")
            sp.switch_tab("reminders")
            root.update_idletasks()
            self.assertIsNotNone(sp.interval_entry)
            self.assertIsNotNone(sp.msg_entry)
            self.assertIn(int(sp.interval_entry.winfo_id()), cm._HWND_HOOKS)
            self.assertIn(int(sp.msg_entry.winfo_id()), cm._HWND_HOOKS)
            sp.close()
        finally:
            try:
                root.destroy()
            except Exception:
                pass

        # 3. Repeated _on_enter_pet hovers must not accumulate <Map> bindings.
        with tempfile.TemporaryDirectory() as tmp:
            pet = PandaPet(data_dir=tmp)
            try:
                initial_map_bind = pet.window.bind("<Map>")
                for _ in range(5):
                    pet._on_enter_pet()
                self.assertEqual(pet.window.bind("<Map>"), initial_map_bind)
            finally:
                pet.close()

    @unittest.skipUnless(sys.platform == "win32", "Win32 HWND cursor hooks only apply on Windows")
    def test_drag_and_wm_frame_setcursor_preserve_custom_cursor_in_pak_mode(self) -> None:
        import ctypes
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.main import PandaPet

        u32 = ctypes.WinDLL("user32")
        u32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u32.LoadCursorW.restype = ctypes.c_void_p
        u32.SetCursor.argtypes = [ctypes.c_void_p]
        u32.SetCursor.restype = ctypes.c_void_p
        u32.GetCursor.argtypes = []
        u32.GetCursor.restype = ctypes.c_void_p
        u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        u32.SendMessageW.restype = ctypes.c_ssize_t

        h_sys = int(u32.LoadCursorW(None, ctypes.c_void_p(cm.IDC_ARROW)) or 0)
        orig_cache = dict(cm._CURSOR_CACHE)
        orig_get_capture = cm._U32_GET_CAPTURE
        try:
            with patch("app.cursor_manager.get_tkinter_cursor_spec", return_value=""):
                with tempfile.TemporaryDirectory() as tmp:
                    pet = PandaPet(data_dir=tmp)
                    try:
                        pet.set_mouse_cursor("mitten_smooth")
                        pet.window.update()
                        self.assertEqual(pet.canvas.cget("cursor"), "")
                        h_mitten = cm.load_cursor("mitten_smooth")
                        self.assertTrue(h_mitten)

                        ch = int(pet.canvas.winfo_id())
                        frame_str = str(pet.window.wm_frame() or "").strip()
                        fh = int(frame_str, 16) if frame_str.startswith("0x") else (int(frame_str) if frame_str else ch)
                        self.assertIn(ch, cm._HWND_HOOKS)
                        self.assertIn(fh, cm._HWND_HOOKS)

                        # 1. wm_frame receiving HTNOWHERE / HTTRANSPARENT from hooked child keeps h_mitten
                        for ht in (cm.HTNOWHERE, cm.HTTRANSPARENT):
                            u32.SetCursor(h_sys)
                            ret = int(u32.SendMessageW(fh, cm.WM_SETCURSOR, ch, ht | (0x0200 << 16)))
                            self.assertEqual(ret, 1)
                            self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        # Non-client resize/titlebar hit-tests must remain free for native DefWindowProc
                        u32.SetCursor(h_sys)
                        u32.SendMessageW(fh, cm.WM_SETCURSOR, fh, 2 | (0x0200 << 16))  # HTCAPTION
                        self.assertEqual(int(u32.GetCursor() or 0), h_sys)

                        # 2. During captured drag, HTERROR / WM_WINDOWPOSCHANGED / WM_MOUSELEAVE preserve h_mitten
                        cm._U32_GET_CAPTURE = lambda: ch
                        u32.SetCursor(h_sys)
                        self.assertEqual(int(u32.SendMessageW(fh, cm.WM_SETCURSOR, fh, cm.HTERROR | (0x0201 << 16))), 1)
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        u32.SetCursor(h_sys)
                        u32.SendMessageW(ch, cm.WM_MOUSELEAVE, 0, 0)
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        u32.SetCursor(h_sys)
                        pet.x += 12
                        pet._place_pet()
                        pet.window.update_idletasks()
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)
                        cm._U32_GET_CAPTURE = orig_get_capture

                        # 3. Real PandaPet drag_begin -> drag_move -> _sync_frame_box -> end_drag cycle
                        u32.SetCursor(h_sys)
                        pet.drag_begin(SimpleNamespace(x_root=pet.x + 80, y_root=pet.y + 80))
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        u32.SetCursor(h_sys)
                        pet.drag_move(SimpleNamespace(x_root=pet.x + 96, y_root=pet.y + 92))
                        self.assertTrue(pet.dragging)
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        # Simulate idle / animation frame box switch while dragging (triggers _sync_frame_box + after_idle)
                        pet._frame_pad = (-1, -1, -1, -1)
                        u32.SetCursor(h_sys)
                        pet._sync_frame_box(pet._visual_action())
                        pet.window.update()
                        self.assertEqual(int(u32.GetCursor() or 0), h_mitten)

                        pet.end_drag()
                        self.assertIsNone(pet._drag_cursor_after)

                        pet.set_mouse_cursor("system")
                        pet.window.update()
                        self.assertNotIn(ch, cm._HWND_HOOKS)
                    finally:
                        cm._U32_GET_CAPTURE = orig_get_capture
                        pet.close()
        finally:
            cm._CURSOR_CACHE.clear()
            cm._CURSOR_CACHE.update(orig_cache)


if __name__ == "__main__":
    unittest.main()
