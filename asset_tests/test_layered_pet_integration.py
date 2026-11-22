"""tests/test_layered_pet_integration.py — Stage 2 verification for PandaPet + LayeredSpriteSurface."""
from __future__ import annotations

from contextlib import ExitStack
import gc
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import ImageTk  # noqa: E402

from app.action_frames import load_exact_action  # noqa: E402
from app.main import MEMBER_KEYS, PET_SIZE_MAP, PandaPet, pet_display_px  # noqa: E402
from app.platform.layered_surface import current_process_gdi_objects  # noqa: E402
from app.platform.win32 import ui_scale  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import PREPARED_ACTIONS, PREPARED_IMAGES, clear_standby_caches  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class Sprite8BitPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_standby_caches()

    def test_binary_alpha_false_preserves_8bit_antialiased_edges_across_sizes_and_bomi_left_walk(self) -> None:
        for px in (144, 192, 240):
            lib_8bit = SpriteLibrary(ROOT, display_px=px, equalize=True, binary_alpha=False)
            lib_1bit = SpriteLibrary(ROOT, display_px=px, equalize=True, binary_alpha=True)
            if lib_8bit.registry is None:
                self.skipTest("asset registry unavailable")
            for member in ("eunji", "bomi"):
                pil_8, _ = lib_8bit.load_member_pil(member)
                pil_1, _ = lib_1bit.load_member_pil(member)
                actions = ("idle", "walk", "walk_left") if member == "bomi" else ("idle", "walk")
                for act in actions:
                    im8 = pil_8[act][0]
                    im1 = pil_1[act][0]
                    self.assertEqual(im8.size, im1.size)
                    hist8 = im8.getchannel("A").histogram()
                    hist1 = im1.getchannel("A").histogram()
                    self.assertGreater(
                        sum(hist8[1:255]),
                        100,
                        f"Expected 8-bit intermediate alpha pixels for {member}.{act} at {px}px",
                    )
                    self.assertEqual(
                        sum(hist1[1:255]),
                        0,
                        f"Expected 1-bit binary alpha for {member}.{act} at {px}px",
                    )

    def test_prepared_caches_isolate_8bit_and_1bit_frames(self) -> None:
        lib_8 = SpriteLibrary(ROOT, display_px=192, equalize=True, binary_alpha=False)
        lib_1 = SpriteLibrary(ROOT, display_px=192, equalize=True, binary_alpha=True)
        if lib_8.registry is None:
            self.skipTest("asset registry unavailable")
        act_8 = load_exact_action(lib_8, "eunji", "feed_matcha_cake")
        act_1 = load_exact_action(lib_1, "eunji", "feed_matcha_cake")
        self.assertIsNotNone(act_8)
        self.assertIsNotNone(act_1)
        self.assertGreater(sum(act_8.frames[0].getchannel("A").histogram()[1:255]), 100)
        self.assertEqual(sum(act_1.frames[0].getchannel("A").histogram()[1:255]), 0)
        act_8_refined = load_exact_action(
            SpriteLibrary(ROOT, display_px=192, equalize=True, binary_alpha=False, edge_refine=True),
            "eunji",
            "feed_matcha_cake",
        )
        self.assertIsNotNone(act_8_refined)
        self.assertGreaterEqual(len(PREPARED_ACTIONS._items), 3)
        self.assertGreaterEqual(len(PREPARED_IMAGES._items), 2)


@unittest.skipUnless(sys.platform == "win32", "Requires real Win32 desktop and ULW")
class LayeredPetIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="panda_ulw_pet_"))
        env = {key: str(Path(temp) / key) for key in ("PANDA_DATA_DIR", "LOCALAPPDATA", "APPDATA")}
        for value in env.values():
            Path(value).mkdir()
        self.stack.enter_context(patch.dict(os.environ, env))
        for target in (
            "app.main.PandaSystemTray",
            "app.main.GlobalHotkeyManager",
            "app.main.WindowsNotificationMonitor",
            "app.cursor_manager.apply_system_cursor_global",
            "app.cursor_manager.restore_system_cursor_global",
        ):
            self.stack.enter_context(patch(target, return_value=MagicMock()))
        self.stack.enter_context(patch("app.main.is_workstation_locked", return_value=False))
        self.stack.enter_context(patch("app.main.get_system_idle_seconds", return_value=0.0))
        self.data_dir = Path(env["PANDA_DATA_DIR"])
        PersistenceService(self.data_dir).save(
            dict(DEFAULT_SETTINGS, mode="manual", manual_character="eunji", onboarding_prompted=True),
            dict(DEFAULT_RUNTIME),
        )

    def test_pet_runs_on_layered_surface_across_sizes_members_drag_actions_menu_and_close(self) -> None:
        pet = PandaPet(data_dir=self.data_dir, use_layered=True)
        try:
            self.assertTrue(pet._use_ulw)
            self.assertIsNotNone(pet.layered_surface)
            self.assertFalse(pet.sprites.binary_alpha)
            self.assertEqual(str(pet.window.wm_attributes("-transparentcolor")), "")

            # Verify 8-bit smooth alpha on current PIL frame
            im = pet.current_pil_frame()
            self.assertIsNotNone(im)
            self.assertGreater(sum(im.getchannel("A").histogram()[1:255]), 100)

            # Test size switching small -> large -> medium (DPI-scaled physical px + threshold)
            scale = ui_scale(pet.window)
            for sz_key in ("small", "large", "medium"):
                pet.set_pet_size(sz_key)
                area = pet.desktop.work_area_for_point(pet.x + pet.width // 2, pet.y + pet.height)
                expected_px = pet_display_px(sz_key, scale, area)
                self.assertEqual(pet.sprites.display_px, expected_px)
                self.assertFalse(pet.sprites.binary_alpha)
                self.assertTrue(pet.sprites.edge_refine)  # every ULW size refines (2026-11-22)
                self.assertEqual((pet.layered_surface.width, pet.layered_surface.height), (pet.width, pet.height))
                im_sz = pet.current_pil_frame()
                self.assertIsNotNone(im_sz)
                self.assertGreater(sum(im_sz.getchannel("A").histogram()[1:255]), 100)

            # High-DPI threshold & multi-frame ULW composed cache invariants
            self.assertTrue(pet._want_edge_refine(144))
            self.assertTrue(pet._want_edge_refine(288))
            pet.frame_idx = 0
            pet._present_layered_pet()
            pet.frame_idx = 1
            pet._present_layered_pet()
            self.assertGreaterEqual(len(pet._ulw_composed_cache), 2)

            # Test Bomi left walk (MIRROR_UNSAFE directional walk_left)
            pet.switch_character("bomi")
            pet.set_state("walk")
            pet.direction = -1
            pet.animate()
            bomi_im = pet.current_pil_frame()
            self.assertIsNotNone(bomi_im)
            self.assertGreater(sum(bomi_im.getchannel("A").histogram()[1:255]), 100)

            # Test drag move updates authoritative surface position without losing frame
            pet.drag_begin(SimpleNamespace(x_root=pet.x + 20, y_root=pet.y + 20))
            pet.drag_move(SimpleNamespace(x_root=pet.x + 120, y_root=pet.y + 40))
            self.assertEqual((pet.layered_surface.x, pet.layered_surface.y), (pet.x - pet._frame_pad[0], pet.y - pet._frame_pad[1]))
            pet.end_drag()

            # Test large 384px action (_sync_frame_box expansion and shrink back)
            pet.switch_character("eunji")
            pet.satiety = 20.0
            pet.feed("matcha_cake")
            pet.animate()
            self.assertEqual(pet._visual_action(), "feed_matcha_cake")
            self.assertTrue(any(pet._frame_pad))
            exp_w = pet.width + pet._frame_pad[0] + pet._frame_pad[2]
            exp_h = pet.height + pet._frame_pad[1] + pet._frame_pad[3]
            self.assertEqual((pet.layered_surface.width, pet.layered_surface.height), (exp_w, exp_h))

            # Test right-click PinkContextMenu opens and closes cleanly
            pet.show_menu(SimpleNamespace(x_root=pet.x + 40, y_root=pet.y + 40))
            self.assertIsNotNone(pet.pink_menu)
            pet._close_pink_menu()
            self.assertIsNone(pet.pink_menu)

            # Test hide_to_tray / show_from_tray visibility sync
            pet.hide_to_tray()
            self.assertFalse(pet.layered_surface.visible)
            self.assertFalse(pet._pet_is_visible())
            pet.show_from_tray()
            self.assertTrue(pet.layered_surface.visible)

            # Let DWM / uxtheme settle, then verify 100 animate ticks leak 0 GDI handles
            pet.root.update()
            time.sleep(0.35)
            pet.root.update()
            g0 = current_process_gdi_objects()
            for _ in range(100):
                pet._present_layered_pet()
            g100 = current_process_gdi_objects()
            self.assertEqual(g100, g0)
        finally:
            surf = pet.layered_surface
            pet.close()
            self.assertTrue(surf.closed)

    def test_panda_disable_ulw_env_falls_back_to_colorkey(self) -> None:
        with patch.dict(os.environ, {"PANDA_DISABLE_ULW": "1"}):
            pet = PandaPet(data_dir=self.data_dir)
            try:
                self.assertFalse(pet._use_ulw)
                self.assertIsNone(pet.layered_surface)
                self.assertTrue(pet.sprites.binary_alpha)
                self.assertFalse(pet.sprites.edge_refine)
                self.assertEqual(str(pet.window.wm_attributes("-transparentcolor")).lower(), "#ff00fe")
            finally:
                pet.close()

    def test_stage3_cameo_celebration_dome_anniversary_use_8bit_ulw_and_zero_gdi_leak(self) -> None:
        pet = PandaPet(data_dir=self.data_dir, use_layered=True)
        try:
            self.assertTrue(pet._use_ulw)
            self.assertFalse(pet.sprites.binary_alpha)
            self.assertFalse(pet.guest_sprites.binary_alpha)

            # (a) Cameo fade-in on ULW: 8-bit intermediate alpha, no -transparentcolor or -alpha
            started = pet.start_cameo(manual=True, guest="bomi")
            self.assertTrue(started)
            self.assertIsNotNone(pet.cameo_window)
            self.assertIsNotNone(pet.cameo_window.surface)
            self.assertEqual(str(pet.cameo_window.win.wm_attributes("-transparentcolor")), "")
            cameo_pil = pet.cameo_window.sprites.get_pil("walk", -1)[0]
            self.assertGreater(
                sum(cameo_pil.getchannel("A").histogram()[1:255]),
                100,
                "Expected 8-bit antialiased alpha on ULW cameo sprite",
            )
            pet._stop_cameo()

            # (b) GroupCelebration on ULW: 8-bit frames + 20 open/close cycles have 0 GDI handle leak
            pet.celebrate_together(duration_ms=3000)
            self.assertIsNotNone(pet.group_celebration)
            while pet.group_celebration.loading:
                pet.group_celebration._load_step()
            self.assertGreater(len(pet.group_celebration.windows), 0)
            self.assertEqual(len(pet.group_celebration.surfaces), len(pet.group_celebration.windows))
            for win, _canvas, _item, frames, _fms, _pp in pet.group_celebration.windows:
                self.assertEqual(str(win.wm_attributes("-transparentcolor")), "")
                im = getattr(frames[0], "_pil_image", None) or ImageTk.getimage(frames[0])
                self.assertGreater(
                    sum(im.getchannel("A").histogram()[1:255]),
                    50,
                    "Expected 8-bit antialiased alpha on ULW GroupCelebration guest",
                )
            pet._close_group_celebration()
            pet.root.update()
            time.sleep(0.3)
            pet.root.update()

            for timer_key in ("glyph_warmup", "desktop_warmup", "standby_warmup", "festival_welcome", "onboarding"):
                tid = pet._loop_after.pop(timer_key, None)
                if tid is not None:
                    try:
                        pet.window.after_cancel(tid)
                    except Exception:
                        pass
            gc.collect()
            gdi_base = current_process_gdi_objects()
            for _ in range(20):
                pet.celebrate_together(duration_ms=3000)
                while pet.group_celebration and pet.group_celebration.loading:
                    pet.group_celebration._load_step()
                pet._close_group_celebration()
            gc.collect()
            pet.root.update()
            time.sleep(0.3)
            pet.root.update()
            gdi_after_20 = current_process_gdi_objects()
            self.assertLessEqual(
                gdi_after_20,
                gdi_base,
                f"Expected 0 GDI handle leak across 20 GroupCelebration cycles ({gdi_base} -> {gdi_after_20})",
            )

            # (c) DomeDesktopPreview on ULW: actor surfaces + bubble_window 8-bit soft shadow
            pet.preview_dome_baseball_event()
            prev = pet.dome_preview
            self.assertIsNotNone(prev)
            self.assertTrue(prev._use_ulw)
            self.assertEqual(len(prev.actor_surfaces), 5)
            self.assertIsNotNone(prev.bubble_surface)
            self.assertEqual(str(prev.bubble_window.wm_attributes("-transparentcolor")), "")
            self.assertIsNotNone(prev._bubble_pil)
            self.assertGreater(
                sum(prev._bubble_pil.getchannel("A").histogram()[1:255]),
                100,
                "Expected 8-bit soft shadow & antialiased edges on ULW Dome cheering bubble",
            )
            pet._close_group_celebration()
            self.assertTrue(prev.closed)

            # (d) AnniversaryScene 419 on ULW: 8-bit photo & visitor move via surface.move
            pet._open_anniversary_scene()
            scene = pet.anniversary_scene
            self.assertIsNotNone(scene)
            self.assertIsNotNone(scene.surface)
            self.assertEqual(str(scene.win.wm_attributes("-transparentcolor")), "")
            self.assertGreater(
                sum(scene.pil_frames[0].getchannel("A").histogram()[1:255]),
                100,
                "Expected 8-bit antialiased alpha on 419 group photo",
            )
            if scene.vis_surface is not None:
                scene._t0 = time.monotonic() - 2.3
                scene._tick()
                self.assertTrue(scene.vis_surface.visible)
                self.assertGreater(scene.vis_surface.x, 0)
            pet._close_group_celebration()
        finally:
            pet.close()

    def test_stage3_disable_ulw_fallback_uses_binary_alpha_across_all_guest_windows(self) -> None:
        with patch.dict(os.environ, {"PANDA_DISABLE_ULW": "1"}):
            pet = PandaPet(data_dir=self.data_dir)
            try:
                self.assertFalse(pet._use_ulw)
                self.assertTrue(pet.sprites.binary_alpha)
                self.assertFalse(pet.sprites.edge_refine)
                self.assertTrue(pet.guest_sprites.binary_alpha)

                # Cameo fallback
                self.assertTrue(pet.start_cameo(manual=True, guest="bomi"))
                self.assertIsNone(pet.cameo_window.surface)
                self.assertEqual(str(pet.cameo_window.win.wm_attributes("-transparentcolor")).lower(), "#ff00fe")
                im_c = ImageTk.getimage(pet.cameo_window.sprites.get("idle", 1)[0])
                self.assertEqual(sum(im_c.getchannel("A").histogram()[1:255]), 0)
                pet._stop_cameo()

                # GroupCelebration fallback
                pet.celebrate_together(duration_ms=3000)
                while pet.group_celebration.loading:
                    pet.group_celebration._load_step()
                self.assertEqual(len(pet.group_celebration.surfaces), 0)
                im_g = ImageTk.getimage(pet.group_celebration.windows[0][3][0])
                self.assertEqual(sum(im_g.getchannel("A").histogram()[1:255]), 0)
                pet._close_group_celebration()

                # DomeDesktopPreview fallback
                pet.preview_dome_baseball_event()
                self.assertFalse(pet.dome_preview._use_ulw)
                self.assertEqual(len(pet.dome_preview.actor_surfaces), 0)
                self.assertIsNone(pet.dome_preview.bubble_surface)
                self.assertEqual(sum(pet.dome_preview._bubble_pil.getchannel("A").histogram()[1:255]), 0)
                pet._close_group_celebration()

                # AnniversaryScene fallback
                pet._open_anniversary_scene()
                self.assertIsNone(pet.anniversary_scene.surface)
                self.assertEqual(sum(pet.anniversary_scene.pil_frames[0].getchannel("A").histogram()[1:255]), 0)
                pet._close_group_celebration()
            finally:
                pet.close()

    def test_i1_runtime_ulw_consecutive_failures_trigger_clean_colorkey_fallback(self) -> None:
        pet = PandaPet(data_dir=self.data_dir, use_layered=True)
        try:
            self.assertTrue(pet._use_ulw)
            self.assertIsNotNone(pet.layered_surface)
            pet.state = "walk"
            pet.target_roam_x = pet.x + 100
            f0 = pet.frame_idx

            with patch.object(pet.layered_surface, "present", side_effect=OSError(87, "UpdateLayeredWindow failed")):
                # Failure 1 & 2: stays on ULW, animate still advances frame_idx
                pet.animate()
                self.assertEqual(pet._ulw_fail_count, 1)
                self.assertTrue(pet._use_ulw)
                self.assertEqual(pet.frame_idx, f0 + 1)

                pet.animate()
                self.assertEqual(pet._ulw_fail_count, 2)
                self.assertTrue(pet._use_ulw)
                self.assertEqual(pet.frame_idx, f0 + 2)

                # Failure 3: triggers clean fallback to ColorKey without aborting animate()
                pet.animate()
                self.assertFalse(pet._use_ulw)
                self.assertIsNone(pet.layered_surface)
                self.assertTrue(pet.sprites.binary_alpha)
                self.assertFalse(pet.sprites.edge_refine)
                self.assertEqual(str(pet.window.wm_attributes("-transparentcolor")).lower(), "#ff00fe")
                self.assertEqual(pet.frame_idx, f0 + 3)

            # Subsequent animate ticks run cleanly on ColorKey with binary alpha
            pet.animate()
            self.assertEqual(pet.frame_idx, f0 + 4)
            im_after = ImageTk.getimage(pet.current_frame())
            self.assertEqual(sum(im_after.getchannel("A").histogram()[1:255]), 0)
        finally:
            pet.close()

    def test_i2_current_frame_and_current_pil_frame_match_across_all_members_states_and_directions(self) -> None:
        pet = PandaPet(data_dir=self.data_dir, use_layered=True)
        try:
            for member in MEMBER_KEYS:
                pet.switch_character(member)
                for state in ("idle", "walk", "cheer", "sleep"):
                    pet.state = state
                    for direction in (1, -1):
                        pet.direction = direction
                        pet.face_override = direction if state != "walk" else None
                        for idx in (0, 1, 3, 5):
                            pet.frame_idx = idx
                            tk_photo = pet.current_frame()
                            pil_im = pet.current_pil_frame()
                            self.assertIsNotNone(tk_photo)
                            self.assertIsNotNone(pil_im)
                            tk_im = ImageTk.getimage(tk_photo)
                            self.assertEqual(
                                tk_im.size,
                                pil_im.size,
                                f"Size mismatch for {member}.{state} dir={direction} idx={idx}",
                            )
                            self.assertEqual(
                                tk_im.getchannel("A").getbbox(),
                                pil_im.getchannel("A").getbbox(),
                                f"Alpha bbox mismatch for {member}.{state} dir={direction} idx={idx}",
                            )
                pet.face_override = None
        finally:
            pet.close()

    def test_i3_ulw_action_cache_respects_budget_and_skips_tk_photos_across_200_lookups(self) -> None:
        from app.action_cache import action_cache_budget
        from app.platform.layered_surface import ulw_composed_budget

        pet = PandaPet(data_dir=self.data_dir, use_layered=True)
        try:
            with patch("app.main.ui_scale", return_value=2.0):
                pet.set_pet_size("large")
            self.assertEqual(pet.sprites.display_px, 480)
            budget = action_cache_budget(480)
            actions = (
                "special_birthday", "special_cheer_lightstick", "festival_christmas",
                "festival_new_year", "musical_pose", "musical_step", "musical_bow",
                "musical_swish", "feed_matcha_cake", "feed_malatang", "feed_egg",
                "feed_kimchi_pork", "feed_buldak", "feed_budae_jjigae", "feed_burger",
                "feed_tw_beef_noodle", "feed_tw_xiaolongbao", "feed_americano",
                "feed_soju", "feed_whiskey", "daily_greeting", "daily_cat_cuddle",
                "daily_hug_side", "daily_bored", "daily_full", "daily_sulk",
                "daily_surprise", "daily_yawn", "scene_campfire", "scene_picnic",
                "scene_starfield", "scene_practice_room", "special_guitar",
                "special_boxing", "special_taekwondo", "special_gaming",
            )
            lookups = 0
            for act in actions:
                for m in MEMBER_KEYS:
                    for facing in (1, -1):
                        pet._visual_pil_frames_and_offset(m, act, facing)
                        lookups += 1
                        if lookups >= 200:
                            break
                    if lookups >= 200:
                        break
                if lookups >= 200:
                    break
            lru = pet._actions()
            self.assertLessEqual(lru.nbytes(), budget)
            self.assertGreater(lru.evictions, 0)
            self.assertEqual(lru.photo_count(), 0)
            snap = pet.memory_snapshot()
            self.assertLessEqual(snap["actions"]["mb"], round(budget / (1024 * 1024), 1))
            self.assertLessEqual(snap["ulw_composed_mb"], round(ulw_composed_budget(480) / (1024 * 1024), 1))

            # Verify ULW walk frames still advance pet.x across multi-frame walk ticks
            pet.active_bubble = None
            pet.settings["stay_in_place"] = False
            pet.dragging = False
            pet.standby_overlay = None
            pet.target_roam_x = None
            pet.x = 200
            pet._set_ambient("walk")
            pet.direction = 1
            pet.frame_idx = 0
            start_x = pet.x
            with patch.object(pet.window, "after", return_value="x"):
                for _ in range(4):
                    pet.animate()
            self.assertNotEqual(pet.x, start_x)
        finally:
            pet.close()


if __name__ == "__main__":
    unittest.main()
