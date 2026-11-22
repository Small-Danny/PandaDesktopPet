"""tests/test_fortune_room.py — Eunji's Fortune Studio, Opening Dome Outfit, & Front Bomi integration tests."""
from __future__ import annotations

import datetime as dt
import os
import random
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_fortune_test_"))

from app import dome_stage, fortune_room  # noqa: E402
from app.action_frames import available_actions, load_exact_action  # noqa: E402
from app.daily_actions import SCENE_ACTIONS  # noqa: E402
from app.engine.assets import AssetRegistry  # noqa: E402
from app.i18n import t  # noqa: E402
from app.main import PandaPet  # noqa: E402
from app.pink_context_menu import build_pet_context_menu_items  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import PandaStandbyOverlay, SCENES, load_wallpapers, scene_fits  # noqa: E402
from tools.runtime_manifest import runtime_files  # noqa: E402


def finish_upload(root, dialog):
    deadline = time.monotonic() + 5
    while dialog._loading and time.monotonic() < deadline:
        root.update()
        time.sleep(0.002)
    if dialog._loading:
        raise AssertionError("fortune theater upload did not finish")


class FortuneAndNewDomeAssetsTests(unittest.TestCase):
    def test_fortune_registry_and_scene_scoping(self) -> None:
        reg = AssetRegistry(ROOT / "work" / "asset_registry.json", ROOT)
        lib = SpriteLibrary(ROOT)

        self.assertEqual(dome_stage.EUNJI_DOME_CONCERT_OUTFITS[0], "dome_concert_opening")
        self.assertEqual(
            SCENE_ACTIONS["bg_standby_eunji_dome_dream"]["eunji"][0],
            "dome_concert_opening",
        )

        # New Fortune actions + updated front Bomi baseball cheer
        for member, action, expected_tags in (
            ("bomi", "dome_baseball_cheer", {"desktop_action", "standby"}),
            ("eunji", "dome_concert_opening", {"desktop_action", "standby"}),
            ("eunji", "fortune_tarot_reader", {"desktop_action", "standby"}),
            ("eunji", "fortune_student", {"desktop_action", "standby"}),
            ("eunji", "fortune_love_reading", {"desktop_action"}),
        ):
            spec = reg.resolve(member, action)
            self.assertEqual(spec.asset_id, f"{member}.{action}")
            self.assertEqual(tuple(spec.canvas), (384, 384))
            self.assertEqual(len(spec.frames), 4)
            self.assertTrue(expected_tags.issubset(set(spec.tags)))
            if member == "eunji" and action == "fortune_love_reading":
                self.assertNotIn("standby", spec.tags)
                for scene in (*SCENES, *SCENE_ACTIONS):
                    self.assertFalse(scene_fits(action, spec.tags, member, scene))
            loaded = load_exact_action(lib, member, action)
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded.frames), 4)

        # Fortune Standby solo actions stay scoped to fortune room in Standby
        others = [s for s in (*SCENES, *SCENE_ACTIONS) if s != fortune_room.FORTUNE_ROOM_SCENE]
        for action in (fortune_room.FORTUNE_READER_ACTION, fortune_room.FORTUNE_STUDENT_ACTION):
            self.assertTrue(scene_fits(action, ("desktop_action", "standby"), "eunji", fortune_room.FORTUNE_ROOM_SCENE))
            for other in others:
                self.assertFalse(scene_fits(action, ("desktop_action", "standby"), "eunji", other))

        from app.standby import WALLPAPER_FX

        for dome_scene in ("bg_standby_dome_baseball", "bg_standby_eunji_dome_dream"):
            self.assertNotIn(dome_scene, WALLPAPER_FX)

        walls = {w.key: w for w in load_wallpapers(ROOT)}
        self.assertIn(fortune_room.FORTUNE_ROOM_SCENE, walls)
        with Image.open(walls[fortune_room.FORTUNE_ROOM_SCENE].path) as im:
            self.assertEqual(im.size, (2752, 1536))

        rt = set(runtime_files(ROOT))
        for idx in range(1, fortune_room.FORTUNE_THEATER_FRAME_COUNT + 1):
            self.assertIn(f"work/scenes/fortune_room/frame_{idx:02d}.png", rt)

    def test_fortune_standby_slots_preserve_center_table_corridor_and_no_overlap(self) -> None:
        sizes_wide = {m: (160, 195) for m in ("chorong", "bomi", "eunji", "student", "namjoo", "hayoung")}
        sizes_portrait = {m: (108, 120) for m in ("chorong", "bomi", "eunji", "student", "namjoo", "hayoung")}
        for sw, sh, k, sizes, min_gap in (
            (1920, 1080, 1.0, sizes_wide, 80.0),
            (3840, 2160, 2.0, sizes_wide, 80.0),
            (1008, 2032, 1.0, sizes_portrait, 150.0),
        ):
            slots = fortune_room.compute_fortune_standby_slots(
                sw, sh, sizes, include_student=True, ui_scale_factor=k
            )
            self.assertEqual(set(slots), set(sizes))
            ordered = ["chorong", "bomi", "eunji", "student", "namjoo", "hayoung"]
            boxes = []
            for m in ordered:
                cx, fy = slots[m]
                mw, mh = sizes[m]
                boxes.append((cx - mw // 2, fy - mh, cx + mw // 2, fy))
                self.assertGreaterEqual(boxes[-1][0], 0)
                self.assertLessEqual(boxes[-1][2], sw)
            for i in range(len(boxes) - 1):
                self.assertLessEqual(boxes[i][2], boxes[i + 1][0], f"overlap on {(sw, sh)}: {boxes}")
            # Crystal-ball table corridor between Eunji and Student remains wide open
            self.assertLess(boxes[2][2], boxes[3][0] - min_gap * k)

    def test_tarot_deck_trilingual_and_non_repeating(self) -> None:
        self.assertEqual(len(fortune_room.CHORONG_EGG_LINES),
                         len(fortune_room.GUARDIAN_LINES_FINAL["chorong"]))
        rng = random.Random(42)
        last = None
        seen = set()
        for _ in range(30):
            card = fortune_room.pick_tarot_card(rng, last_key=last)
            self.assertNotEqual(card.key, last)
            for lang in ("zh_TW", "ko", "en"):
                self.assertTrue(card.badge[lang].strip())
                self.assertTrue(card.title[lang].strip())
                self.assertTrue(card.message[lang].strip())
                self.assertTrue(card.lucky[lang].strip())
            seen.add(card.key)
            last = card.key
        self.assertGreaterEqual(len(seen), 4)


class FortuneRoomGuiTests(unittest.TestCase):
    def test_mouse_controls_survive_motion_language_and_focus_redraws(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        dlg = fortune_room.FortuneRoomDialog(root, res_root=ROOT)
        self.addCleanup(dlg.close)
        root.update()

        def point(tag):
            x0, y0, x1, y1 = dlg.canvas.bbox(tag)
            return {"x": (x0 + x1) // 2, "y": (y0 + y1) // 2}

        def click(tag, *, move=True):
            xy = point(tag)
            if move:
                dlg.canvas.event_generate("<Motion>", **xy)
            dlg.canvas.event_generate("<ButtonPress-1>", **xy)
            self.assertFalse(dlg._closed)
            dlg.canvas.event_generate("<ButtonRelease-1>", **xy)
            root.update()

        motion = point("btn_3")
        dlg.canvas.event_generate("<ButtonRelease-1>", **motion)
        dlg.canvas.event_generate("<ButtonPress-1>", **motion)
        self.assertFalse(dlg._reduced_motion)
        dlg.canvas.event_generate("<ButtonRelease-1>", **point("btn_1"))
        self.assertFalse(dlg._reduced_motion)

        click("btn_3")
        self.assertTrue(dlg._reduced_motion)
        click("btn_3", move=False)
        self.assertFalse(dlg._reduced_motion)
        click("btn_3", move=False)
        self.assertTrue(dlg._reduced_motion)
        click("btn_0")
        self.assertFalse(dlg._daily)
        self.assertTrue(dlg._revealed)
        dlg.set_language("ko")
        click("btn_1")
        self.assertTrue(dlg._daily)
        self.assertTrue(dlg._revealed)
        dlg.canvas.focus_force()
        root.update()
        old_slot = dlg._focus_slot
        dlg.canvas.event_generate("<Tab>")
        self.assertNotEqual(dlg._focus_slot, old_slot)
        click("btn_3")
        self.assertFalse(dlg._reduced_motion)
        dlg.canvas.event_generate("<ButtonRelease-1>", **point("close_btn"))
        self.assertFalse(dlg._closed)
        click("close_btn")
        self.assertTrue(dlg._closed)

    def test_forced_egg_clicks_never_drag_and_reveal_only_once(self):
        from types import SimpleNamespace
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        tick = [0.0]
        dlg = fortune_room.FortuneRoomDialog(root, monotonic=lambda: tick[0], res_root=ROOT)
        self.addCleanup(dlg.close)
        dlg.skip_animation()
        point = SimpleNamespace(x=dlg._s(25), y=dlg._s(28), x_root=100, y_root=100)

        def click(at):
            tick[0] = at
            dlg._on_drag_begin(point)
            self.assertIsNone(dlg._drag_offset)
            dlg._on_drag_end(point)

        click(0)
        dlg._on_drag_begin(point)
        moved = SimpleNamespace(**{**vars(point), "x_root": 100 + dlg._s(7)})
        dlg._on_drag_move(moved)
        dlg._on_drag_end(moved)
        click(.3)
        click(.5)
        self.assertFalse(dlg._egg_forced)
        click(1.7)
        self.assertTrue(dlg._egg_forced)
        dlg.draw_again()
        self.assertTrue(dlg._egg_pending)
        self.assertFalse(dlg._egg_shown)
        self.assertEqual(dlg.reading.guardian_id, "chorong")
        dlg.show_daily()
        dlg.skip_animation()
        self.assertFalse(dlg._egg_shown)
        dlg.draw_again()
        dlg.skip_animation()
        self.assertTrue(dlg._egg_shown)
        self.assertEqual(dlg.canvas.itemcget(dlg._reveal_outline, "outline"), fortune_room.EGG_GOLD)
        dlg.set_language("ko")
        self.assertEqual(dlg.canvas.itemcget(dlg._reveal_outline, "outline"), fortune_room.EGG_GOLD)
        dlg.draw_again()
        dlg.skip_animation()
        self.assertNotEqual(dlg.current_card.key, fortune_room.CHORONG_EGG_CARD.key)
        self.assertEqual(dlg.canvas.itemcget(dlg._reveal_outline, "outline"), "#6d28d9")
        dlg.close()
        self.assertIsNone(dlg._upload_id)
        root.update()

    def test_corrupt_media_reveals_instead_of_leaving_a_blank_dialog(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for relative in ("work/scenes/fortune_room/frame_01.png",
                             "work/standby_backgrounds/bg_standby_eunji_fortune_room.jpg"):
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"invalid image")
            dlg = fortune_room.FortuneRoomDialog(root, res_root=base)
            try:
                finish_upload(root, dlg)
                self.assertTrue(dlg._revealed)
                self.assertTrue(dlg.canvas.find_withtag("media_placeholder"))
                self.assertIsNone(dlg._after_id)
            finally:
                dlg.close()

    def test_egg_roll_boundary_and_keyboard_focus(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        for hour, roll, expected in ((12, .049, True), (12, .05, False),
                                     (23, .149, True), (5, .149, False)):
            dlg = fortune_room.FortuneRoomDialog(
                root, res_root=ROOT, clock=lambda: dt.datetime(2026, 11, 18, hour))
            try:
                dlg.skip_animation()
                with patch.object(dlg.rng, "random", return_value=roll):
                    self.assertEqual(dlg._move_focus(1), "break")
                    self.assertEqual(dlg._activate_focus(None), "break")
                self.assertEqual(dlg._egg_pending, expected)
                self.assertEqual(dlg._move_focus(-1), "break")
                self.assertEqual(dlg._focus_slot, 0)
            finally:
                dlg.close()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_data_dir = os.environ.get("PANDA_DATA_DIR")
        os.environ["PANDA_DATA_DIR"] = self._tmp.name
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._old_data_dir is None:
            os.environ.pop("PANDA_DATA_DIR", None)
        else:
            os.environ["PANDA_DATA_DIR"] = self._old_data_dir

    def test_fortune_dialog_playback_draw_summon_and_clean_close(self) -> None:
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(lambda: root.destroy() if root.winfo_exists() else None)
        errors: list[str] = []
        root.report_callback_exception = lambda exc, val, tb: errors.append(f"{exc.__name__}: {val}")

        summoned = []
        closed = []
        dlg = fortune_room.FortuneRoomDialog(
            root,
            lang="zh_TW",
            res_root=ROOT,
            on_summon_desktop=lambda: summoned.append(True),
            on_close=lambda: closed.append(True),
        )
        self.assertEqual(dlg._photos, [])
        finish_upload(root, dlg)
        self.assertEqual(len(dlg._photos), fortune_room.FORTUNE_THEATER_FRAME_COUNT)
        self.assertFalse(dlg._revealed)

        # Advance reveal deterministically through the end of the sequence
        dlg._cancel_playback()
        with patch.object(dlg, "_monotonic", return_value=dlg._playback_start + 3):
            dlg._tick_playback()
        self.assertTrue(dlg._revealed)
        self.assertIsNone(dlg._after_id)

        first_key = dlg.current_card.key
        dlg.draw_again()
        self.assertNotEqual(dlg.current_card.key, first_key)
        self.assertIsNotNone(dlg._after_id)

        dlg._summon_desktop()
        self.assertEqual(summoned, [True])

        dlg.close()
        self.assertTrue(dlg._closed)
        self.assertIsNone(dlg._after_id)
        self.assertEqual(closed, [True])
        root.update()
        self.assertFalse(errors, errors)

    def test_standby_fortune_room_stage_renders_and_cleans_up(self) -> None:
        wallpapers = load_wallpapers(ROOT)
        root = tk.Tk()
        root.withdraw()
        overlay = None
        try:
            with (
                patch("ctypes.windll.user32.LockWorkStation", create=True),
                patch("app.standby.PandaStandbyOverlay._watch_real_lock"),
            ):
                lib = SpriteLibrary(ROOT)
                base_pil, _ = lib.load_member_pil("chorong")
                from PIL import ImageTk

                frames = {a: [ImageTk.PhotoImage(im, master=root) for im in ims] for a, ims in base_pil.items() if a != "walk_left"}
                overlay = PandaStandbyOverlay(
                    parent=root,
                    char_key="eunji",
                    char_name="恩地 (Eunji)",
                    frames=frames,
                    flipped_walk_frames=frames.get("walk", []),
                    lock_on_exit=False,
                    show_panda_tags=True,
                    scene=fortune_room.FORTUNE_ROOM_SCENE,
                    wallpapers=wallpapers,
                    bounds=WorkArea(0, 0, 1920, 1080),
                    today=dt.date(2026, 11, 16),
                )
                for win in [overlay.win, *(c["win"] for c in overlay.covers)]:
                    win.unbind("<Motion>")
                    win.unbind("<ButtonPress>")
                overlay.finish_action_loading()
                overlay._animate_dome_scene(reschedule=False)
                root.update_idletasks()

                self.assertEqual(overlay.scene, fortune_room.FORTUNE_ROOM_SCENE)
                self.assertIsNotNone(overlay._fortune_student_item)
                # Switch away to starfield and verify stage guest canvas item is cleaned up
                overlay.set_scene("starfield")
                root.update_idletasks()
                self.assertIsNone(overlay._fortune_student_item)
                self.assertFalse(overlay.canvas.find_withtag("fortune_stage"))
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            self.assertFalse(overlay._after_ids if overlay is not None else {})
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_standby_fortune_room_never_flashes_plain_eunji_and_enters_together(self) -> None:
        """2026-11-22 user report: entering the room showed a capped Eunji (cheer fallback)
        and no braided student, then both popped in. Eunji now stays hidden until the
        reader and the student are both loaded, and those two load before the flanks."""
        wallpapers = load_wallpapers(ROOT)
        root = tk.Tk()
        root.withdraw()
        overlay = None
        try:
            with (
                patch("ctypes.windll.user32.LockWorkStation", create=True),
                patch("app.standby.PandaStandbyOverlay._watch_real_lock"),
            ):
                overlay = PandaStandbyOverlay(
                    parent=root, char_key="chorong", char_name="Chorong", frames={},
                    flipped_walk_frames=[], lock_on_exit=False, show_panda_tags=True,
                    scene=fortune_room.FORTUNE_ROOM_SCENE, wallpapers=wallpapers,
                    bounds=WorkArea(0, 0, 1920, 1080), today=dt.date(2026, 11, 16),
                )
                for win in [overlay.win, *(c["win"] for c in overlay.covers)]:
                    win.unbind("<Motion>")
                    win.unbind("<ButtonPress>")
                eunji = next(p for p in overlay.pandas if p["key"] == "eunji")
                self.assertNotIn(fortune_room.FORTUNE_READER_ACTION, eunji["actions"])
                overlay._animate_dome_scene(reschedule=False)
                for key in ("img_item", "tag_item", "tag_shadow"):
                    self.assertEqual(overlay.canvas.itemcget(eunji[key], "state"), "hidden", key)
                # 2026-11-22: the flanks wait with her so the whole room appears at once.
                for p in overlay.pandas:
                    self.assertEqual(overlay.canvas.itemcget(p["img_item"], "state"), "hidden", p["key"])
                # Eunji's two fortune actions finish before any flank starts loading.
                while fortune_room.FORTUNE_STUDENT_ACTION not in eunji["actions"]:
                    self.assertTrue(overlay._load_one_pending_action())
                    if fortune_room.FORTUNE_STUDENT_ACTION not in eunji["actions"]:
                        overlay._animate_dome_scene(reschedule=False)
                        self.assertEqual(overlay.canvas.itemcget(eunji["img_item"], "state"), "hidden")
                self.assertIn(fortune_room.FORTUNE_READER_ACTION, eunji["actions"])
                self.assertFalse(any(p["actions"] for p in overlay.pandas if p["key"] != "eunji"))
                overlay._animate_dome_scene(reschedule=False)
                for p in overlay.pandas:
                    self.assertNotEqual(overlay.canvas.itemcget(p["img_item"], "state"), "hidden", p["key"])
                reader = eunji["actions"][fortune_room.FORTUNE_READER_ACTION]["frames"]
                self.assertIn(overlay.canvas.itemcget(eunji["img_item"], "image"), {str(f) for f in reader})
                self.assertIsNotNone(overlay._fortune_student_item)
                overlay.set_scene("starfield")
                self.assertNotEqual(overlay.canvas.itemcget(eunji["img_item"], "state"), "hidden")
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_real_pet_fortune_special_moves_menu_and_dialog(self) -> None:
        with (
            patch("app.main.is_developer_mode", return_value=False),
            patch("app.main.PandaSystemTray", return_value=MagicMock()),
            patch("app.main.GlobalHotkeyManager", return_value=MagicMock()),
            patch("app.main.WindowsNotificationMonitor", return_value=MagicMock()),
            patch("app.main.is_workstation_locked", return_value=False),
            patch("app.main.get_system_idle_seconds", return_value=0.0),
            patch("ctypes.windll.user32.LockWorkStation", create=True),
        ):
            pet = PandaPet(data_dir=Path(self._tmp.name))
        second_dlg = None
        try:
            pet._close_group_celebration()
            avail = pet.available_special_actions("eunji")
            self.assertIn("fortune_tarot_reader", avail)
            self.assertIn("fortune_student", avail)
            self.assertIn("fortune_love_reading", avail)

            self.assertTrue(pet.trigger_special_action("fortune_love_reading", "eunji"))
            self.assertEqual(pet._visual_action(), "fortune_love_reading")

            items = build_pet_context_menu_items(pet)
            special_sub = items[3].submenu
            eunji_row = next(r for r in special_sub if "恩地" in r.label or "Eunji" in r.label)
            eunji_labels = {sub.label for sub in eunji_row.submenu}
            self.assertIn(t("special_move_eunji_fortune_love", pet.lang), eunji_labels)
            self.assertIn(t("special_move_eunji_fortune_room", pet.lang), eunji_labels)

            pet.open_fortune_room()
            first_dlg = pet.fortune_dialog
            self.assertIsNotNone(first_dlg)
            self.assertTrue(first_dlg.win.winfo_exists())
            self.assertEqual(first_dlg.lang, pet.lang)

            # Live language switch updates open dialog + re-opening preserves singleton & syncs
            pet.set_language("en")
            self.assertIs(pet.fortune_dialog, first_dlg)
            self.assertEqual(first_dlg.lang, "en")
            self.assertEqual(
                first_dlg.win.title(),
                fortune_room._CARD_UI_TEXT["en"]["title"],
            )
            pet.lang = "ko"
            pet.open_fortune_room()
            self.assertIs(pet.fortune_dialog, first_dlg)
            self.assertEqual(first_dlg.lang, "ko")
            self.assertFalse(first_dlg._closed)
            first_dlg.toggle_motion()
            self.assertTrue(pet.store.load()[0]["fortune_reduced_motion"])

            first_dlg.close()
            self.assertIsNone(pet.fortune_dialog)
            self.assertTrue(first_dlg._closed)
            self.assertIsNone(first_dlg._after_id)

            # Opening again creates a fresh dialog owned cleanly by pet.close()
            pet.open_fortune_room()
            second_dlg = pet.fortune_dialog
            self.assertIsNotNone(second_dlg)
            self.assertIsNot(second_dlg, first_dlg)
            self.assertTrue(second_dlg._reduced_motion)
        finally:
            try:
                pet.close()
            except Exception:
                pass
        if second_dlg is not None:
            self.assertTrue(second_dlg._closed)
            self.assertIsNone(second_dlg._after_id)
            self.assertIsNone(pet.fortune_dialog)

    def test_fortune_dialog_192dpi_compact_workarea_keeps_controls_inside_bounds(self) -> None:
        from PIL import ImageFont

        for dpi_mult, area_box in (
            (2.0, WorkArea(0, 0, 1280, 720)),
            (2.0, WorkArea(0, 0, 1920, 1080)),
            (2.0, WorkArea(-1008, 32, -24, 2032)),
            (1.0, WorkArea(0, 0, 1920, 1080)),
        ):
            for lang in ("zh_TW", "ko", "en"):
                root = tk.Tk()
                root.withdraw()
                try:
                    root.tk.call("tk", "scaling", dpi_mult * 96.0 / 72.0)
                    with patch(
                        "app.fortune_room.WindowsDesktopAdapter.work_area_for_point",
                        return_value=area_box,
                    ):
                        dlg = fortune_room.FortuneRoomDialog(
                            root,
                            lang=lang,
                            res_root=ROOT,
                            on_summon_desktop=lambda: None,
                        )
                    dlg.skip_animation()
                    dlg.win.update_idletasks()

                    self.assertLessEqual(dlg.w, area_box.width - 24)
                    self.assertLessEqual(dlg.h, area_box.height - 24)
                    self.assertEqual(dlg._media_w, round(480 * dlg._draw_scale))
                    self.assertEqual(dlg._media_h, round(270 * dlg._draw_scale))

                    for tag in ("close_btn", "action_buttons", "reveal_panel"):
                        bbox = dlg.canvas.bbox(tag)
                        self.assertIsNotNone(bbox, f"missing bbox for {tag} at {(dpi_mult, area_box, lang)}")
                        self.assertGreaterEqual(bbox[0], 0, (tag, bbox, dlg.w, dlg.h))
                        self.assertGreaterEqual(bbox[1], 0, (tag, bbox, dlg.w, dlg.h))
                        self.assertLessEqual(bbox[2], dlg.w, (tag, bbox, dlg.w, dlg.h))
                        self.assertLessEqual(bbox[3], dlg.h, (tag, bbox, dlg.w, dlg.h))

                    from app.fortune_cards import GUARDIAN_LINES_FINAL, GUARDIAN_TAGS_FINAL, CHORONG_EGG_LINES
                    from app.fortune_reading import FOODS, Reading, food_is_safe
                    from app.foods import get_food_name
                    cases = [(member, i, line[lang]) for member, lines in GUARDIAN_LINES_FINAL.items()
                             for i, line in enumerate(lines)]
                    member, line_id, _ = max(cases, key=lambda item: len(item[2]))
                    dlg._daily = False
                    for card in (*fortune_room.TAROT_CARDS, fortune_room.CHORONG_EGG_CARD):
                        egg = card == fortune_room.CHORONG_EGG_CARD
                        guardian = "chorong" if egg else member
                        line = (max(range(len(CHORONG_EGG_LINES)), key=lambda i: len(CHORONG_EGG_LINES[i][lang]))
                                if egg else line_id)
                        food = max((f for f in FOODS.values() if food_is_safe(f, guardian)),
                                   key=lambda f: len(get_food_name(f, lang)))
                        dlg.reading = Reading(card.key, guardian, food["id"], line)
                        dlg.current_card = card
                        dlg._egg_shown = egg
                        dlg._draw_reveal_contents()
                        rects = [dlg.canvas.bbox(tag) for tag in ("mode_chip", "card_badge", "card_title",
                                  "card_message", "card_lucky", "guardian_row", "food_row")]
                        label = (card.key, lang, area_box)
                        self.assertTrue(all(a[3] <= b[1] for a, b in zip(rects, rects[1:])), label)
                        x0, y0, x1, y1 = dlg._reveal_bounds
                        self.assertTrue(all(x0 <= a and y0 <= b and c <= x1 and d <= y1
                                            for a, b, c, d in rects), (label, rects, dlg._reveal_bounds))
                    self.assertLess(dlg.canvas.bbox("dialog_title")[2], dlg.canvas.bbox("close_btn")[0])
                    for index in range(len(dlg._focus_handlers) - 1):
                        outer = dlg.canvas.bbox(f"btn_{index}")
                        inner = dlg.canvas.bbox(f"btn_{index}_label")
                        self.assertGreaterEqual(inner[1], outer[1])
                        self.assertLessEqual(inner[3], outer[3])
                    dlg.close()
                finally:
                    try:
                        root.destroy()
                    except tk.TclError:
                        pass

        font_paths = {
            "zh_TW": Path(r"C:\Windows\Fonts\msjhbd.ttc"),
            "ko": Path(r"C:\Windows\Fonts\malgunbd.ttf"),
            "en": Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        }
        for lang, fpath in font_paths.items():
            if not fpath.is_file():
                continue
            fnt = ImageFont.truetype(str(fpath), 24)
            notdef = bytes(fnt.getmask("\uffff"))
            chars = set()
            for v in fortune_room._CARD_UI_TEXT[lang].values():
                chars.update(v)
            for card in (*fortune_room.TAROT_CARDS, fortune_room.CHORONG_EGG_CARD):
                for field in (card.badge, card.title, card.message, card.lucky):
                    chars.update(field[lang])
            for tag in (*GUARDIAN_TAGS_FINAL.values(), fortune_room.CHORONG_EGG_TAG, fortune_room.CHORONG_EGG_UNLOCK):
                chars.update(tag[lang])
            for lines in (*GUARDIAN_LINES_FINAL.values(), CHORONG_EGG_LINES):
                for line in lines:
                    chars.update(line[lang])
            chars.discard(" ")
            bad = [ch for ch in sorted(chars) if bytes(fnt.getmask(ch)) == notdef]
            self.assertEqual(bad, [], f"missing glyphs for {lang} in {fpath.name}: {bad}")

    def test_standby_fortune_fps_honors_registry_frame_ms(self) -> None:
        wallpapers = load_wallpapers(ROOT)
        root = tk.Tk()
        root.withdraw()
        overlay = None
        try:
            with (
                patch("ctypes.windll.user32.LockWorkStation", create=True),
                patch("app.standby.PandaStandbyOverlay._watch_real_lock"),
            ):
                lib = SpriteLibrary(ROOT)
                base_pil, _ = lib.load_member_pil("chorong")
                from PIL import ImageTk

                frames = {a: [ImageTk.PhotoImage(im, master=root) for im in ims] for a, ims in base_pil.items() if a != "walk_left"}
                overlay = PandaStandbyOverlay(
                    parent=root,
                    char_key="eunji",
                    char_name="恩地 (Eunji)",
                    frames=frames,
                    flipped_walk_frames=frames.get("walk", []),
                    lock_on_exit=False,
                    scene=fortune_room.FORTUNE_ROOM_SCENE,
                    wallpapers=wallpapers,
                    bounds=WorkArea(0, 0, 1920, 1080),
                    today=dt.date(2026, 11, 16),
                )
                for win in [overlay.win, *(c["win"] for c in overlay.covers)]:
                    win.unbind("<Motion>")
                    win.unbind("<ButtonPress>")
                overlay.finish_action_loading()

                eunji = next(p for p in overlay.pandas if p["key"] == "eunji")
                reader_info = eunji["actions"][fortune_room.FORTUNE_READER_ACTION]
                student_info = eunji["actions"][fortune_room.FORTUNE_STUDENT_ACTION]
                self.assertAlmostEqual(reader_info["frame_ms"], 250.0, places=2)
                self.assertAlmostEqual(student_info["frame_ms"], 1000.0 / 4.5, places=2)

                overlay._dome_state = {"t0": 100.0}
                seen_reader_imgs = []
                seen_student_imgs = []
                for ms in (0, 200, 260):
                    with patch("app.standby.time.monotonic", return_value=100.0 + ms / 1000.0):
                        overlay._animate_dome_scene(reschedule=False)
                    seen_reader_imgs.append(overlay.canvas.itemcget(eunji["img_item"], "image"))
                    seen_student_imgs.append(overlay.canvas.itemcget(overlay._fortune_student_item, "image"))
                # At 200ms (< 222.22ms & < 250ms), both remain on frame 0; at 260ms, both advance to frame 1
                self.assertEqual(seen_reader_imgs[0], seen_reader_imgs[1])
                self.assertNotEqual(seen_reader_imgs[0], seen_reader_imgs[2])
                self.assertEqual(seen_student_imgs[0], seen_student_imgs[1])
                self.assertNotEqual(seen_student_imgs[0], seen_student_imgs[2])
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            try:
                root.destroy()
            except tk.TclError:
                pass


if __name__ == "__main__":
    unittest.main()
