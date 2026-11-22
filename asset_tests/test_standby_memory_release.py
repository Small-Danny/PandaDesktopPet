"""Standby memory (2026-11-22): bounded wallpaper photos, released pixels on exit, gc after close.

User report: memory kept climbing under debug_run.bat. Measured cause: a closed standby
overlay lives in reference cycles, and pixel buffers do not trigger Python's gc, so each
session kept ~250 MB (230 -> 518 -> 778 -> 935 MB over three rounds).
"""
from __future__ import annotations

import datetime as dt
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from app.platform.win32 import WorkArea
from app.standby import (
    WALLPAPER_PHOTOS_KEPT, PandaStandbyOverlay, _trim_photo_cache, load_wallpapers,
    _FITTED_WALLPAPERS, _FITTED_WALLPAPER_LOCK, trim_fitted_wallpapers,
)
from app.action_cache import LazyPhotoList

ROOT = Path(__file__).resolve().parents[1]


class StandbyMemoryReleaseTest(unittest.TestCase):
    def test_trim_keeps_the_most_recent_entries(self) -> None:
        cache = {k: k for k in "abcd"}
        _trim_photo_cache(cache)
        self.assertEqual(list(cache), list("abcd")[-WALLPAPER_PHOTOS_KEPT:])

    def test_overlay_bounds_wallpaper_photos_and_releases_pixels_on_exit(self) -> None:
        wallpapers = load_wallpapers(ROOT)
        photo_scenes = [w.key for w in wallpapers if "fortune" not in w.key and "dome" not in w.key][:4]
        self.assertGreaterEqual(len(photo_scenes), 3)
        root = tk.Tk()
        root.withdraw()
        try:
            with patch("ctypes.windll.user32.LockWorkStation", create=True), \
                 patch("app.standby.PandaStandbyOverlay._watch_real_lock"):
                ov = PandaStandbyOverlay(
                    parent=root, char_key="chorong", char_name="Chorong", frames={},
                    flipped_walk_frames=[], lock_on_exit=False, scene=photo_scenes[0],
                    wallpapers=wallpapers, bounds=WorkArea(0, 0, 640, 480),
                    other_bounds=(WorkArea(640, 0, 1040, 300),), today=dt.date(2026, 11, 22),
                )
                for win in [ov.win, *(c["win"] for c in ov.covers)]:
                    win.unbind("<Motion>")
                    win.unbind("<ButtonPress>")
                for key in photo_scenes[1:]:
                    ov.set_scene(key)
                self.assertLessEqual(len(ov._wallpaper_cache), WALLPAPER_PHOTOS_KEPT)
                self.assertIn(photo_scenes[-1], ov._wallpaper_cache)
                self.assertLessEqual(len(ov.covers[0]["photos"]), WALLPAPER_PHOTOS_KEPT)
                ov.finish_action_loading()
                infos = [i for p in ov.pandas for i in p["actions"].values()]
                self.assertTrue(infos)
                # Tk images exist only for frames that were shown.
                self.assertTrue(all(isinstance(i["frames"], LazyPhotoList) for i in infos))
                self.assertLess(sum(i["frames"].created for i in infos), sum(len(i["frames"]) for i in infos))
                ov.handle_exit(None)
                self.assertEqual(ov._wallpaper_cache, {})
                self.assertEqual(ov.covers[0]["photos"], {})
                self.assertTrue(all(p["actions"] == {} for p in ov.pandas))
        finally:
            root.destroy()

    def test_pet_runs_a_gc_pass_after_standby_closes(self) -> None:
        from app.main import PandaPet
        calls = []
        fake = type("FakePet", (), {})()
        fake.window = None
        with patch("app.main.gc.collect", side_effect=lambda: calls.append(1)):
            PandaPet._schedule_memory_reclaim(fake)
        self.assertEqual(calls, [1])


    def test_idle_reclaim_keeps_only_the_last_fitted_wallpaper(self) -> None:
        from PIL import Image
        from app.main import PandaPet
        with _FITTED_WALLPAPER_LOCK:
            saved = dict(_FITTED_WALLPAPERS)
            _FITTED_WALLPAPERS.clear()
            for i in range(4):
                _FITTED_WALLPAPERS[("wp", i)] = Image.new("RGB", (100, 50))
        try:
            fake = type("FakePet", (), {})()
            fake.standby_overlay = object()          # standby still open: keep everything
            with patch("app.main.gc.collect"):
                PandaPet._reclaim_memory(fake)
            self.assertEqual(len(_FITTED_WALLPAPERS), 4)
            fake.standby_overlay = None
            with patch("app.main.gc.collect"):
                PandaPet._reclaim_memory(fake)
            self.assertEqual(list(_FITTED_WALLPAPERS), [("wp", 3)])
            self.assertEqual(trim_fitted_wallpapers(keep=0), 100 * 50 * 4)   # Pillow RGB is 4 bytes/px
        finally:
            with _FITTED_WALLPAPER_LOCK:
                _FITTED_WALLPAPERS.clear()
                _FITTED_WALLPAPERS.update(saved)


    def test_dome_preview_and_anniversary_scene_reclaim_on_close(self) -> None:
        from unittest.mock import MagicMock
        from app.main import PandaPet
        fake = MagicMock()
        fake.dome_preview = object()
        PandaPet._on_dome_preview_done(fake)
        self.assertIsNone(fake.dome_preview)
        fake.anniversary_scene = object()
        PandaPet._on_anniversary_scene_done(fake)
        self.assertIsNone(fake.anniversary_scene)
        self.assertEqual(fake._schedule_memory_reclaim.call_count, 2)


class PanelImageReleaseTest(unittest.TestCase):
    """Combo report (switch member + actions + bubbles + food panel): +56 Tk images per
    food-panel open and bubble art stayed alive until a full gc pass (572 vs 9 images)."""

    def test_food_panel_and_bubble_release_their_tk_images_on_close(self) -> None:
        import os
        import tempfile
        from unittest.mock import MagicMock
        os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))
        from app.main import PandaPet
        with patch("app.main.PandaSystemTray", return_value=MagicMock()),              patch("app.main.GlobalHotkeyManager", return_value=MagicMock()),              patch("app.main.WindowsNotificationMonitor", return_value=MagicMock()),              patch("app.main.is_workstation_locked", return_value=False),              patch("app.main.get_system_idle_seconds", return_value=0.0):
            pet = PandaPet(data_dir=Path(tempfile.mkdtemp(prefix="panda_test_")))
        try:
            names = lambda: set(pet.root.tk.call("image", "names"))
            pet.root.update()
            base = names()
            for _ in range(3):
                pet.open_food_panel()
                pet.root.update()
                panel = pet.food_panel
                self.assertTrue(panel._icon_cache)
                panel.close()
                self.assertEqual(panel._icon_cache, {})
                pet.root.update()
            self.assertLessEqual(len(names() - base), 2)
            pet._toast("hello", duration_ms=5000)
            pet.root.update()
            bubble = pet.active_bubble
            self.assertIsNotNone(bubble)
            self.assertTrue(bubble._image_refs)
            bubble.dismiss()
            self.assertEqual(bubble._image_refs, [])
            self.assertIsNone(bubble._bg_photo)
            pet.root.update()
            self.assertLessEqual(len(names() - base), 2)
        finally:
            pet.close()


if __name__ == "__main__":
    unittest.main()


class CacheBudgetTest(unittest.TestCase):
    """2026-11-22 (Neno's breakdown of the live 567 MB process): count-only caches held
    full-size pixels for the whole session; they are byte-bounded now."""

    def test_ulw_source_cache_is_byte_bounded(self) -> None:
        from PIL import Image
        from app import sprite_polish
        with sprite_polish._ULW_SOURCE_CACHE_LOCK:
            saved = dict(sprite_polish._ULW_SOURCE_CACHE)
            sprite_polish._ULW_SOURCE_CACHE.clear()
        try:
            for i in range(12):        # 12 x 4 MB sources > 16 MB budget
                im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
                im.paste((30, 20, 20, 255), (100 + i, 100, 900, 900))     # dark outline
                im.paste((200, 100, 50, 255), (106 + i, 106, 894, 894))
                sprite_polish.prepare_ulw_source(im, soft_binarize=True)
            with sprite_polish._ULW_SOURCE_CACHE_LOCK:
                total = sum(sprite_polish._ulw_cache_bytes(v) for v in sprite_polish._ULW_SOURCE_CACHE.values())
            self.assertLessEqual(total, sprite_polish._ULW_SOURCE_CACHE_MAX_BYTES)
            self.assertGreater(total, 0)
        finally:
            with sprite_polish._ULW_SOURCE_CACHE_LOCK:
                sprite_polish._ULW_SOURCE_CACHE.clear()
                sprite_polish._ULW_SOURCE_CACHE.update(saved)

    def test_rgb_wallpapers_are_counted_at_four_bytes_per_pixel(self) -> None:
        from PIL import Image
        from app.standby import _image_byte_size
        self.assertEqual(_image_byte_size(Image.new("RGB", (10, 10))), 400)
        self.assertEqual(_image_byte_size(Image.new("L", (10, 10))), 100)

    def test_celebration_photo_cache_entry_size(self) -> None:
        from PIL import Image
        from app.group_celebration import PHOTO_CACHE_BYTES, _photo_cache_bytes

        class P:
            _pil_image = Image.new("RGBA", (200, 200))
        self.assertEqual(_photo_cache_bytes(([P(), P()], 100, (0, 0))), 2 * 200 * 200 * 4 * 2)
        self.assertLessEqual(PHOTO_CACHE_BYTES, 16 * 1024 * 1024)

    def test_ulw_composed_cache_does_not_pin_raw_frames(self) -> None:
        import inspect
        from app.main import PandaPet
        src = inspect.getsource(PandaPet)
        self.assertIn("weakref.ref(raw_frame)", src)
        self.assertNotIn("cache[cache_key] = (frame_im, raw_frame)", src)


class AuxiliaryUiReleaseTest(unittest.TestCase):
    """2026-11-22: closing auxiliary panels/menus releases Tk PhotoImages and pet references;
    ULW cameo never materializes Tk PhotoImages from LazyPhotoList."""

    def test_pink_context_menu_clears_icon_refs_on_close(self) -> None:
        from app.pink_context_menu import MenuItemSpec, PinkContextMenu
        root = tk.Tk()
        root.withdraw()
        try:
            menu = PinkContextMenu(
                root,
                lang="zh_TW",
                char_key="chorong",
                items=[MenuItemSpec("狀態", lambda: None, icon_name="icon_paws")],
                anchor_x=200,
                anchor_y=200,
            )
            root.update()
            self.assertTrue(menu._icon_refs)
            menu.close()
            self.assertEqual(menu._icon_refs, {})
        finally:
            root.destroy()

    def test_status_card_clears_avatar_frames_on_close(self) -> None:
        from app.status_card import PandaStatusCard
        root = tk.Tk()
        root.withdraw()
        try:
            card = PandaStatusCard(
                parent=root,
                char_key="chorong",
                char_name="初瓏",
                badge_desc="隊長",
                passion_points=10,
                companion_start_time=0.0,
                feed_count=1,
                anchor_x=200,
                anchor_y=200,
                lang="zh_TW",
            )
            root.update()
            self.assertTrue(card.avatar_frames)
            card.close()
            self.assertEqual(card.avatar_frames, [])
            self.assertIsNone(card.avatar_thumb)
        finally:
            root.destroy()

    def test_cameo_ulw_does_not_materialize_lazy_tk_photos(self) -> None:
        from PIL import Image
        from app.cameo_view import CameoActorWindow
        from app.engine.cameo import CameoFrame, CameoPhase
        from app.sprites import MemberSprites

        root = tk.Tk()
        root.withdraw()
        try:
            pil_frames = [Image.new("RGBA", (64, 64), (255, 100, 150, 255)) for _ in range(2)]
            lazy_idle = LazyPhotoList(pil_frames, master=root)
            lazy_walk = LazyPhotoList(pil_frames, master=root)
            sprites = MemberSprites(
                member="bomi",
                frames={"idle": lazy_idle, "walk": lazy_walk},
                source="registry",
                _pil={"idle": pil_frames, "walk": pil_frames},
            )
            win = CameoActorWindow(root, sprites, use_layered=True)
            try:
                self.assertTrue(win._use_ulw)
                self.assertEqual(lazy_idle.created, 0)
                win.render(
                    CameoFrame(
                        phase=CameoPhase.ENTER,
                        member="bomi",
                        action="walk",
                        x=100.0,
                        y=100.0,
                        facing=1,
                        alpha=1.0,
                    ),
                    now_ms=100.0,
                )
                self.assertEqual(lazy_idle.created, 0)
                self.assertEqual(lazy_walk.created, 0)
            finally:
                win.destroy()
        finally:
            root.destroy()

    def test_birthday_dialog_clears_pet_reference_on_close(self) -> None:
        import os
        import tempfile
        from unittest.mock import MagicMock
        os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))
        from app.main import PandaPet
        with patch("app.main.PandaSystemTray", return_value=MagicMock()), \
             patch("app.main.GlobalHotkeyManager", return_value=MagicMock()), \
             patch("app.main.WindowsNotificationMonitor", return_value=MagicMock()), \
             patch("app.main.is_workstation_locked", return_value=False), \
             patch("app.main.get_system_idle_seconds", return_value=0.0):
            pet = PandaPet(data_dir=Path(tempfile.mkdtemp(prefix="panda_test_")))
        try:
            pet.open_birthday_dialog()
            pet.root.update()
            self.assertIsNotNone(pet.birthday_dialog)
            pet.birthday_dialog.close()
            self.assertIsNone(pet.birthday_dialog)
        finally:
            pet.close()


class DrawnSceneCoverTest(unittest.TestCase):
    """2026-11-22: all 4 hand-drawn standby scenes render full static backdrops on secondary
    monitor covers without clock/date text, extra PhotoImages, or leaking items across switches."""

    def test_four_drawn_scenes_render_bg_items_on_secondary_covers(self) -> None:
        from app.standby import SCENES
        root = tk.Tk()
        root.withdraw()
        try:
            with patch("ctypes.windll.user32.LockWorkStation", create=True), \
                 patch("app.standby.PandaStandbyOverlay._watch_real_lock"):
                ov = PandaStandbyOverlay(
                    parent=root, char_key="chorong", char_name="Chorong", frames={},
                    flipped_walk_frames=[], lock_on_exit=False, scene=SCENES[0],
                    wallpapers=(), bounds=WorkArea(0, 0, 800, 600),
                    other_bounds=(WorkArea(800, 0, 1440, 480),), today=dt.date(2026, 11, 22),
                )
                try:
                    for win in [ov.win, *(c["win"] for c in ov.covers)]:
                        win.unbind("<Motion>")
                        win.unbind("<ButtonPress>")
                    cover = ov.covers[0]
                    canvas = cover["canvas"]
                    for scene in SCENES:
                        ov.set_scene(scene)
                        root.update_idletasks()
                        bg_items = canvas.find_withtag("bg")
                        self.assertGreaterEqual(len(bg_items), 15, f"{scene} cover should draw full backdrop")
                        self.assertIsNone(cover["clock"])
                        self.assertIsNone(cover["date"])
                        self.assertEqual(cover["photos"], {}, f"{scene} cover must not allocate PhotoImages")
                        # Ensure no clock/date text exists on cover canvas (stars/notes are symbols only).
                        for item_id in canvas.find_all():
                            if canvas.type(item_id) == "text":
                                txt = str(canvas.itemcget(item_id, "text"))
                                self.assertNotIn(":", txt, f"unexpected clock text on {scene} cover: {txt}")
                        # Primary scene tick function must remain intact for the primary canvas.
                        self.assertIsNotNone(ov._scene_tick_fn)
                finally:
                    ov.handle_exit(None)
        finally:
            root.destroy()
