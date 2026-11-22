"""Tests for Taipei Dome scenes, trilingual cheering banner, and Eunji future dream effect."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw, ImageTk

from app import dome_stage
from app.action_frames import ActionFrames, available_actions, load_exact_action
from app.daily_actions import SCENE_ACTIONS
from app.engine.assets import AssetRegistry
from app.i18n import t
from app.main import RES_ROOT, PandaPet
from app.pink_context_menu import build_pet_context_menu_items
from app.platform.win32 import WorkArea
from app.sprites import SpriteLibrary
from app.standby import PandaStandbyOverlay, WallpaperSpec, load_wallpapers


def _make_member_rgba(color: tuple[int, int, int, int], *, size: int = 160, hat_top: int = 12) -> Image.Image:
    """Create a sprite with a tall hat peaking at `hat_top` and opaque feet near bottom."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = size // 2
    draw.rectangle((cx - 18, hat_top, cx + 18, hat_top + 28), fill=color)
    draw.ellipse((cx - 32, hat_top + 22, cx + 32, size - 8), fill=color)
    return img


def _flat_pixels(img: Image.Image):
    fn = getattr(img, "get_flattened_data", None)
    return fn() if callable(fn) else img.getdata()


def _collect_menu_labels(items, seen: set[int] | None = None) -> list[str]:
    seen = set() if seen is None else seen
    out: list[str] = []
    for item in items:
        if id(item) in seen or getattr(item, "is_separator", False):
            continue
        seen.add(id(item))
        out.append(item.label)
        if getattr(item, "submenu", None):
            out.extend(_collect_menu_labels(item.submenu, seen))
    return out


class DomeTimelineAndBubbleTests(unittest.TestCase):
    def test_binary_alpha_preserves_legacy_rgba_at_every_alpha(self):
        from PIL import Image

        rgba = [(i, 255 - i, 93, i) for i in range(256)]
        source = Image.new("RGBA", (256, 1))
        source.putdata(rgba)
        expected = [(r, g, b, 255) if a >= 128 else (0, 0, 0, 0) for r, g, b, a in rgba]
        result = dome_stage._binary_alpha(source)
        self.assertEqual([result.getpixel((i, 0)) for i in range(256)], expected)

    def test_baseball_step_f3_extended_and_climax_scale(self) -> None:
        idx0, d0, s0 = dome_stage.dome_baseball_step(0)
        idx1, d1, s1 = dome_stage.dome_baseball_step(d0)
        idx2, d2, s2 = dome_stage.dome_baseball_step(d0 + d1)
        idx3, d3, s3 = dome_stage.dome_baseball_step(d0 + d1 + d2)
        idx_wrap, _, _ = dome_stage.dome_baseball_step(d0 + d1 + d2 + d3 + 10)

        self.assertEqual((idx0, idx1, idx2, idx3), (0, 1, 2, 3))
        self.assertEqual(idx_wrap, 0)
        # F3 extended at least 2x F1/F2 for reading comfort & CLIMAX scale boost
        self.assertGreaterEqual(d2, d0 * 2)
        self.assertGreaterEqual(d2, d1 * 2)
        self.assertGreater(s2, s1)
        self.assertGreater(s2, s0)
        self.assertGreater(s2, s3)

    def test_trilingual_bubble_renders_all_locales_with_heart_and_alpha_modes(self) -> None:
        for lang in ("zh_TW", "ko", "en"):
            path = dome_stage.resolve_font_path(lang)
            self.assertIsNotNone(path, f"expected usable system TTF font for {lang}")
            for frame_idx in range(4):
                rgba = dome_stage.render_dome_bubble_pil(
                    frame_idx, lang, dpi_scale=1.0, anim_scale=1.18 if frame_idx == 2 else 1.0,
                    binary_alpha=False,
                )
                bin_img = dome_stage.render_dome_bubble_pil(
                    frame_idx, lang, dpi_scale=1.0, anim_scale=1.18 if frame_idx == 2 else 1.0,
                    binary_alpha=True,
                )
                self.assertGreater(rgba.width, 100)
                self.assertGreater(rgba.height, 45)
                alphas_bin = set(_flat_pixels(bin_img.getchannel("A")))
                self.assertTrue(alphas_bin.issubset({0, 255}), f"binary_alpha had intermediate alpha: {alphas_bin - {0, 255}}")
                # Check ink pixels exist inside card
                dark_pixels = sum(
                    1 for r, g, b, a in _flat_pixels(rgba)
                    if a > 200 and r < 140 and g < 60 and b < 90
                )
                self.assertGreater(dark_pixels, 25, f"expected crisp rendered glyphs for {lang} frame {frame_idx}")
                if frame_idx == 2:
                    # F3 CLIMAX ★ badge renders crisp cream/gold star vector glyph (no tofu □)
                    gold_star_px = sum(
                        1 for r, g, b, a in _flat_pixels(rgba)
                        if a > 200 and r > 245 and g > 240 and b < 230
                    )
                    self.assertGreater(gold_star_px, 12, f"expected vector ★ badge pixels for {lang} frame 2")
                if frame_idx == 3:
                    # F4 contains bright rose vector heart ♥
                    pink_heart_px = sum(
                        1 for r, g, b, a in _flat_pixels(rgba)
                        if a > 200 and r > 200 and r > g + 80
                    )
                    self.assertGreater(pink_heart_px, 12, f"expected bright rose ♥ rendered for {lang}")

        # Verify DPI scaling increases pixel dimensions cleanly
        img_96 = dome_stage.render_dome_bubble_pil(2, "zh_TW", dpi_scale=1.0, max_width=900)
        img_192 = dome_stage.render_dome_bubble_pil(2, "zh_TW", dpi_scale=2.0, max_width=1400)
        self.assertGreater(img_192.width, img_96.width)
        self.assertGreater(img_192.height, img_96.height)

    def test_scene1_real_384_widths_stay_symmetrically_centered_and_tight_vertical_clamps(self) -> None:
        # 1920x1080 k=1.0 with real 384x384 display width 288; 3840x2160 k=2.0 with fw=576
        for sw, sh, k, fw in ((1920, 1080, 1.0, 288), (3840, 2160, 2.0, 576)):
            sizes = {m: (fw, fw) for m in dome_stage.DOME_STAGE_MEMBERS}
            slots = dome_stage.dome_baseball_standby_slots(sw, sh, sizes, ui_scale_factor=k)
            eunji_cx = slots["eunji"][0]
            self.assertLessEqual(abs(eunji_cx - sw // 2), 2, f"Scene 1 drifted off center at {(sw, sh, k)}: {slots}")
            xs = [slots[m][0] for m in dome_stage.DOME_STAGE_MEMBERS]
            for i in range(len(xs) - 1):
                self.assertGreaterEqual(xs[i + 1] - xs[i], fw)

        # Tight overhead space: sprite_top=90, gap=16, top_safe=30 => available max_bh=44
        boxes = [(200, 90, 380, 270)]
        max_bw, max_bh = dome_stage.available_dome_bubble_space(
            boxes, (0, 0, 800, 600), gap=16, top_safe_y=30, side_margin=16
        )
        self.assertEqual(max_bh, 44)
        bub = dome_stage.render_dome_bubble_pil(
            2, "zh_TW", dpi_scale=1.0, anim_scale=1.18, max_width=min(560, max_bw), max_height=max_bh
        )
        self.assertLessEqual(bub.height, 44)
        bx, by, bw, bh = dome_stage.compute_dome_bubble_rect(
            boxes, (bub.width, bub.height), (0, 0, 800, 600), gap=16, top_safe_y=30, side_margin=16
        )
        self.assertGreaterEqual(by, 30)
        self.assertLessEqual(by + bh, 74)

    def test_bubble_rect_never_overlaps_members_or_top_ui_across_dpis_and_ratios(self) -> None:
        scenarios = (
            (1920, 1080, 1.0),
            (3840, 2160, 2.0),
            (1366, 768, 1.0),
            (1080, 1440, 1.0),
            (1080, 1600, 1.25),
        )
        for sw, sh, k in scenarios:
            mw_base = 160 if sw == 1080 and k > 1.0 else 180
            sizes = {m: (round(mw_base * k), round(180 * k)) for m in dome_stage.DOME_STAGE_MEMBERS}
            slots = dome_stage.dome_baseball_standby_slots(sw, sh, sizes, ui_scale_factor=k)
            boxes = []
            for m in dome_stage.DOME_STAGE_MEMBERS:
                cx, fy = slots[m]
                mw, mh = sizes[m]
                boxes.append((cx - mw // 2, fy - mh, cx + mw // 2, fy))
            # Pairwise zero overlap across all 5 members
            sorted_boxes = sorted(boxes, key=lambda b: b[0])
            for idx in range(len(sorted_boxes) - 1):
                self.assertLessEqual(
                    sorted_boxes[idx][2],
                    sorted_boxes[idx + 1][0],
                    f"overlap in scenario {(sw, sh, k)}: {sorted_boxes}",
                )
            top_safe = round(72 * k)
            gap = round(16 * k)
            max_bw, max_bh = dome_stage.available_dome_bubble_space(
                boxes, (0, 0, sw, sh), gap=gap, top_safe_y=top_safe, side_margin=round(16 * k)
            )
            bub = dome_stage.render_dome_bubble_pil(
                2, "ko", dpi_scale=k, anim_scale=1.18, max_width=min(round(560 * k), max_bw), max_height=max_bh
            )
            bx, by, bw, bh = dome_stage.compute_dome_bubble_rect(
                boxes, (bub.width, bub.height), (0, 0, sw, sh),
                gap=gap, top_safe_y=top_safe, side_margin=round(16 * k),
            )
            min_member_top = min(b[1] for b in boxes)
            self.assertGreaterEqual(bx, 0)
            self.assertLessEqual(bx + bw, sw)
            self.assertGreaterEqual(by, top_safe)
            self.assertLessEqual(by + bh, min_member_top - gap + 1)

    def test_eunji_standby_flank_geometry_keeps_center_clear_and_flanks_lower(self) -> None:
        sizes = {m: (180, 180) for m in dome_stage.DOME_STAGE_MEMBERS}
        slots = dome_stage.eunji_dome_standby_slots(1920, 1080, sizes, ui_scale_factor=1.0)
        ex, efy = slots["eunji"]
        self.assertLess(abs(ex - 960), 40)
        for flank in dome_stage.EUNJI_FLANK_MEMBERS:
            fx, ffy = slots[flank]
            self.assertGreater(ffy, efy, f"{flank} should stand lower in audience than Eunji")
            if flank in dome_stage.EUNJI_LEFT_FLANK_MEMBERS:
                self.assertLess(fx + 90, ex - 90)
            else:
                self.assertGreater(fx - 90, ex + 90)

        # Portrait 1008x2128 @ k=2.0: fitted visible widths never push flanks onto center or off-screen
        p_sizes = {m: (144, 180) for m in dome_stage.DOME_STAGE_MEMBERS}
        p_slots = dome_stage.eunji_dome_standby_slots(1008, 2128, p_sizes, ui_scale_factor=2.0)
        p_boxes = [(m, p_slots[m][0] - 72, p_slots[m][0] + 72) for m in dome_stage.DOME_STAGE_MEMBERS]
        for idx in range(len(p_boxes) - 1):
            self.assertLessEqual(p_boxes[idx][2], p_boxes[idx + 1][1], f"Portrait standby overlap: {p_boxes}")
        self.assertGreaterEqual(p_boxes[0][1], 0)
        self.assertLessEqual(p_boxes[-1][2], 1008)

        d_slots = dome_stage.compute_desktop_eunji_slots(0, 0, 1008, 2032, p_sizes, ui_scale_factor=2.0)
        d_boxes = [(m, d_slots[m][0], d_slots[m][0] + 144) for m in dome_stage.DOME_STAGE_MEMBERS]
        for idx in range(len(d_boxes) - 1):
            self.assertLessEqual(d_boxes[idx][2], d_boxes[idx + 1][1], f"Portrait desktop overlap: {d_boxes}")
        self.assertGreaterEqual(d_boxes[0][1], 0)
        self.assertLessEqual(d_boxes[-1][2], 1008)

    def test_eunji_concert_sequencer_reads_only_approved_in_canonical_order(self) -> None:
        subset = ("dome_concert_white_tee", "dome_concert_white_dress", "dome_concert_red_leather")

        def fake_available(_lib, member, candidates):
            self.assertEqual(member, "eunji")
            return tuple(c for c in candidates if c in subset)

        approved = dome_stage.resolved_eunji_dome_outfits(object(), available_fn=fake_available)
        self.assertEqual(
            approved,
            ("dome_concert_white_dress", "dome_concert_red_leather", "dome_concert_white_tee"),
        )
        # Sequential stepping across F0..F3 per outfit
        seq = [
            dome_stage.dome_concert_step(i * dome_stage.DOME_CONCERT_FRAME_MS + 10, approved)
            for i in range(13)
        ]
        self.assertEqual(seq[0:4], [("dome_concert_white_dress", 0), ("dome_concert_white_dress", 1),
                                    ("dome_concert_white_dress", 2), ("dome_concert_white_dress", 3)])
        self.assertEqual(seq[4:8], [("dome_concert_red_leather", 0), ("dome_concert_red_leather", 1),
                                    ("dome_concert_red_leather", 2), ("dome_concert_red_leather", 3)])
        self.assertEqual(seq[12], ("dome_concert_white_dress", 0))

    def test_future_dream_wording_never_implies_past_concert(self) -> None:
        forbidden_substrings = (
            "已舉辦", "舉辦過", "曾舉辦", "結束了", "舉辦完", "完成個唱",
            "was held", "performed at", "completed", "had held", "already held",
            "열렸던", "마친", "끝난", "개최했",
        )
        keys = (
            "special_move_eunji_dome_dream",
            "preview_event_dome_eunji",
            "dome_eunji_dream_title",
            "dome_eunji_dream_msg",
        )
        for lang in ("zh_TW", "ko", "en"):
            for k in keys:
                val = t(k, lang)
                low = val.lower()
                for bad in forbidden_substrings:
                    self.assertNotIn(bad.lower(), low, f"{lang}:{k} contains past-tense phrase {bad!r}: {val!r}")
                if lang == "zh_TW":
                    self.assertTrue("未來" in val or "夢想" in val, f"missing future dream cue in {val!r}")
                elif lang == "ko":
                    self.assertTrue("미래" in val or "꿈" in val, f"missing future dream cue in {val!r}")
                else:
                    self.assertTrue("future" in low or "dream" in low, f"missing future dream cue in {val!r}")


class DomeGuiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_data_dir = os.environ.get("PANDA_DATA_DIR")
        os.environ["PANDA_DATA_DIR"] = self._tmp.name

    def tearDown(self) -> None:
        if self._old_data_dir is None:
            os.environ.pop("PANDA_DATA_DIR", None)
        else:
            os.environ["PANDA_DATA_DIR"] = self._old_data_dir
        self._tmp.cleanup()

    def _spawn_pet(self, *, developer_mode: bool = True) -> PandaPet:
        with (
            patch("app.main.is_developer_mode", return_value=developer_mode),
            patch("app.main.PandaSystemTray", return_value=MagicMock()),
            patch("app.main.GlobalHotkeyManager", return_value=MagicMock()),
            patch("app.main.WindowsNotificationMonitor", return_value=MagicMock()),
            patch("app.main.is_workstation_locked", return_value=False),
            patch("app.main.get_system_idle_seconds", return_value=0.0),
            patch("ctypes.windll.user32.LockWorkStation", create=True),
        ):
            pet = PandaPet(data_dir=Path(self._tmp.name))
        pet._close_group_celebration()
        pet.window.update_idletasks()
        return pet

    def test_eunji_personal_effect_gating_menu_and_shared_playback(self) -> None:
        pet = self._spawn_pet(developer_mode=False)
        try:
            # 1. Without approved dome outfits: not exposed & rejected cleanly
            with patch("app.main.available_actions", return_value=()):
                self.assertNotIn("special_eunji_dome_dream", pet.available_special_actions("eunji"))
                self.assertFalse(pet.trigger_special_action("special_eunji_dome_dream", "eunji"))

            # 2. With partial approved dome outfits: exposed on Eunji in Formal Enduser menu
            approved = ("dome_concert_white_dress", "dome_concert_star_jacket")
            frames_by_action = {
                "dome_concert_white_dress": ActionFrames(
                    "dome_concert_white_dress",
                    [_make_member_rgba((255, 220, 240, 255), size=192) for _ in range(4)],
                    260, False, (-10, -24),
                ),
                "dome_concert_star_jacket": ActionFrames(
                    "dome_concert_star_jacket",
                    [_make_member_rgba((180, 140, 255, 255), size=192) for _ in range(4)],
                    260, False, (-10, -24),
                ),
            }

            def fake_avail(_lib, member, candidates):
                if member == "eunji":
                    return tuple(c for c in candidates if c in approved or c == "special_sing_highnote")
                return ()

            def fake_load(_lib, member, action, **_kw):
                if member == "eunji":
                    return frames_by_action.get(action)
                return None

            with (
                patch("app.main.available_actions", side_effect=fake_avail),
                patch("app.main.load_exact_action", side_effect=fake_load),
                patch("app.pink_context_menu.is_developer_mode", return_value=False),
            ):
                pet.switch_character("eunji", mode="manual")
                self.assertIn("special_eunji_dome_dream", pet.available_special_actions("eunji"))
                self.assertNotIn("special_eunji_dome_dream", pet.available_special_actions("chorong"))
                self.assertFalse(pet.trigger_special_action("special_eunji_dome_dream", "chorong"))

                # Formal enduser menu includes Personal Effect, excludes Dev Dome Previews
                labels = _collect_menu_labels(build_pet_context_menu_items(pet))
                self.assertIn(t("special_move_eunji_dome_dream", pet.lang), labels)
                self.assertNotIn(t("preview_event_dome_baseball", pet.lang), labels)
                self.assertNotIn(t("preview_event_dome_eunji", pet.lang), labels)

                # Trigger personal effect & verify shared sequencer advances outfits + clean restore
                self.assertTrue(pet.trigger_special_action("special_eunji_dome_dream", "eunji"))
                self.assertEqual(pet._visual_action(), "dome_concert_white_dress")
                self.assertIsNotNone(pet.current_frame())
                eid = pet.coord.snapshot().active.event_id
                # Rewind t0 so elapsed crosses into second outfit (4 * 260ms = 1040ms)
                pet._eunji_dome_effect_state = (
                    eid,
                    pet._eunji_dome_effect_state[1] - 1.15,
                    pet._eunji_dome_effect_state[2],
                )
                self.assertEqual(pet._visual_action(), "dome_concert_star_jacket")
                # Cancel cleanly restores idle visual appearance
                pet.coord.cancel(eid, "test_done")
                self.assertIsNone(pet._visual_action())
        finally:
            try:
                pet.close()
            finally:
                try:
                    pet.root.destroy()
                except tk.TclError:
                    pass

    def test_desktop_dome_previews_spawn_sync_and_clean_up(self) -> None:
        pet = self._spawn_pet(developer_mode=True)
        try:
            action_bank = {
                "dome_baseball_cheer": [
                    _make_member_rgba((255, 130, 175, 255), size=192, hat_top=8) for _ in range(4)
                ],
                "dome_concert_white_dress": [
                    _make_member_rgba((255, 235, 248, 255), size=192, hat_top=14) for _ in range(4)
                ],
                "dome_concert_blue_varsity": [
                    _make_member_rgba((120, 185, 255, 255), size=192, hat_top=14) for _ in range(4)
                ],
                "special_cheer_lightstick": [
                    _make_member_rgba((255, 95, 165, 255), size=160, hat_top=16) for _ in range(4)
                ],
            }

            def fake_load(_lib, member, action, **_kw):
                ims = action_bank.get(action)
                return ActionFrames(action, list(ims), 200, False, (0, 0)) if ims else None

            def fake_avail(_lib, member, candidates):
                if member == "eunji":
                    return tuple(c for c in candidates if c in action_bank)
                return tuple(c for c in candidates if c == "special_cheer_lightstick")

            with (
                patch("app.main.load_exact_action", side_effect=fake_load),
                patch("app.main.available_actions", side_effect=fake_avail),
                patch.object(pet.desktop, "set_noactivate", wraps=pet.desktop.set_noactivate) as spy_noact,
            ):
                pet.preview_dome_baseball_event()
                prev1 = pet.dome_preview
                self.assertIsNotNone(prev1)
                self.assertEqual(set(prev1.actor_windows.keys()), set(dome_stage.DOME_STAGE_MEMBERS))
                self.assertIsNotNone(prev1.bubble_window)
                # set_noactivate called on all 6 windows with positive integer native HWND
                self.assertEqual(spy_noact.call_count, 6)
                for call in spy_noact.call_args_list:
                    hwnd_arg = call.args[0]
                    self.assertIsInstance(hwnd_arg, int)
                    self.assertGreater(hwnd_arg, 0)
                prev1.bubble_window.update_idletasks()
                bx = prev1.bubble_window.winfo_x()
                by = prev1.bubble_window.winfo_y()
                bh = prev1.bubble_window.winfo_height()
                min_actor_y = min(prev1.slots[m][1] for m in dome_stage.DOME_STAGE_MEMBERS)
                self.assertGreaterEqual(bx, prev1.area.left)
                self.assertLess(by + bh, min_actor_y + 12)  # strict clearance above tallest sprites

                # Re-trigger directly with Eunji concert preview tears down prev1 cleanly
                with patch.object(pet, "_toast", wraps=pet._toast) as spy_toast:
                    pet.preview_eunji_dome_event()
                    self.assertTrue(prev1.closed)
                    self.assertFalse(prev1._after_ids)
                    self.assertIsNotNone(pet.dome_preview)
                    self.assertIsNone(pet.dome_preview.bubble_window)
                    self.assertTrue(spy_toast.called)
                    header_arg = spy_toast.call_args.kwargs.get("header", "")
                    self.assertEqual(header_arg, t("dome_eunji_dream_title", pet.lang))
                    # Eunji stands higher / center than left & right flank members
                    es = pet.dome_preview.slots
                    self.assertLess(es["eunji"][1], es["chorong"][1])
                    self.assertLess(es["chorong"][0], es["bomi"][0])
                    self.assertLess(es["bomi"][0], es["eunji"][0])
                    self.assertLess(es["eunji"][0], es["namjoo"][0])
                    self.assertLess(es["namjoo"][0], es["hayoung"][0])

                # set_state("sleep") cancels active DomeDesktopPreview cleanly
                prev2 = pet.dome_preview
                pet.set_state("sleep", manual=True)
                self.assertTrue(prev2.closed)
                self.assertFalse(prev2._after_ids)
                self.assertIsNone(pet.dome_preview)

                # hide_to_tray() closes active preview without deiconifying the pet window
                pet.preview_dome_baseball_event()
                prev3 = pet.dome_preview
                pet.hide_to_tray()
                self.assertTrue(prev3.closed)
                self.assertFalse(prev3._after_ids)
                self.assertIsNone(pet.dome_preview)
                self.assertFalse(bool(pet.window.winfo_viewable()))
        finally:
            try:
                pet.close()
            finally:
                try:
                    pet.root.destroy()
                except tk.TclError:
                    pass

    def test_standby_dome_baseball_and_eunji_dream_stages(self) -> None:
        tmp_dir = Path(self._tmp.name)
        wp_baseball = tmp_dir / "dome_baseball.jpg"
        wp_eunji = tmp_dir / "dome_eunji.jpg"
        Image.new("RGB", (640, 360), (26, 48, 88)).save(wp_baseball)
        Image.new("RGB", (640, 360), (34, 18, 52)).save(wp_eunji)

        wallpapers = [
            WallpaperSpec("bg_standby_dome_baseball", wp_baseball, {"zh_TW": "臺北大巨蛋", "ko": "타이베이 돔", "en": "Taipei Dome"}),
            WallpaperSpec("bg_standby_eunji_dome_dream", wp_eunji, {"zh_TW": "恩地巨蛋夢想", "ko": "은지 돔 꿈", "en": "Eunji Dome Dream"}),
        ]

        root = tk.Tk()
        root.withdraw()

        def fake_load_standby(self_ov, _lib, member, _walk, only=None):
            requested = list(only or ())
            out = {}
            for name in requested:
                if name == "dome_baseball_cheer" or (member == "eunji" and name.startswith("dome_concert_")) or (member != "eunji" and name == "special_cheer_lightstick"):
                    ims = [_make_member_rgba((255, 160, 210, 255), size=180, hat_top=10) for _ in range(4)]
                    out[name] = {
                        "frames": [ImageTk.PhotoImage(im, master=self_ov.win) for im in ims],
                        "frame_ms": 220.0,
                        "tags": ("desktop_action", "standby"),
                        "offset": (-15, -30),
                        "anchor": (90, 172),
                        "alpha_bboxes": tuple(im.getchannel("A").getbbox() for im in ims),
                    }
            return out

        overlay = None
        try:
            with (
                patch("app.standby.load_wallpapers", return_value=wallpapers),
                patch.object(PandaStandbyOverlay, "_load_standby_actions", fake_load_standby),
            ):
                overlay = PandaStandbyOverlay(
                    root,
                    char_key="eunji",
                    char_name="Eunji",
                    frames={},
                    flipped_walk_frames=[],
                    scene="bg_standby_dome_baseball",
                    lang="ko",
                    wallpapers=wallpapers,
                )
                overlay.win.update_idletasks()
                bubble_items = overlay.canvas.find_withtag("dome_bubble")
                self.assertEqual(len(bubble_items), 1)
                bub_bbox = overlay.canvas.bbox(bubble_items[0])
                self.assertIsNotNone(bub_bbox)
                # Must stay strictly below Standby hint bottom and strictly above tallest panda cap pixel
                self.assertGreaterEqual(bub_bbox[1], overlay.hint_bottom)
                panda_tops = [overlay.canvas.coords(p["img_item"])[1] + 10 for p in overlay.pandas]
                self.assertLessEqual(bub_bbox[3], min(panda_tops) + 2)

                # Switch to Eunji Future Dome Dream scene
                overlay.set_scene("bg_standby_eunji_dome_dream")
                overlay.win.update_idletasks()
                self.assertEqual(overlay.canvas.find_withtag("dome_bubble"), ())
                self.assertTrue(overlay.canvas.find_withtag("dome_eunji_fx"))
                coords_by_key = {p["key"]: overlay.canvas.coords(p["img_item"]) for p in overlay.pandas}
                e_x, e_y = coords_by_key["eunji"]
                for flank in dome_stage.EUNJI_FLANK_MEMBERS:
                    fx, fy = coords_by_key[flank]
                    self.assertGreater(fy, e_y)
                self.assertLess(coords_by_key["chorong"][0], coords_by_key["bomi"][0])
                self.assertLess(coords_by_key["bomi"][0], e_x)
                self.assertLess(e_x, coords_by_key["namjoo"][0])
                self.assertLess(coords_by_key["namjoo"][0], coords_by_key["hayoung"][0])

                # Switch back to drawn starfield -> dome items deleted cleanly
                overlay.set_scene("starfield")
                self.assertEqual(overlay.canvas.find_withtag("dome_stage"), ())

                # Direct launch into bg_standby_eunji_dome_dream draws Scene 2 FX exactly once (9 items: 1 cone + 8 notes)
                overlay.handle_exit()
                overlay2 = PandaStandbyOverlay(
                    root,
                    char_key="eunji",
                    char_name="Eunji",
                    frames={},
                    flipped_walk_frames=[],
                    scene="bg_standby_eunji_dome_dream",
                    lang="zh_TW",
                    wallpapers=wallpapers,
                )
                try:
                    overlay2.win.update_idletasks()
                    self.assertEqual(len(overlay2.canvas.find_withtag("dome_eunji_fx")), 9)
                finally:
                    if overlay2.running:
                        overlay2.handle_exit()
                    self.assertFalse(overlay2._after_ids)
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            self.assertFalse(overlay._after_ids if overlay is not None else {})
            try:
                root.destroy()
            except tk.TclError:
                pass


class DomeRealRegistryEndToEndTests(unittest.TestCase):
    """Phase 2 end-to-end tests against real promoted registry & real wallpaper JPGs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_data_dir = os.environ.get("PANDA_DATA_DIR")
        os.environ["PANDA_DATA_DIR"] = self._tmp.name

    def tearDown(self) -> None:
        if self._old_data_dir is None:
            os.environ.pop("PANDA_DATA_DIR", None)
        else:
            os.environ["PANDA_DATA_DIR"] = self._old_data_dir
        self._tmp.cleanup()

    def _spawn_real_pet(self, *, developer_mode: bool = True) -> PandaPet:
        with (
            patch("app.main.is_developer_mode", return_value=developer_mode),
            patch("app.main.PandaSystemTray", return_value=MagicMock()),
            patch("app.main.GlobalHotkeyManager", return_value=MagicMock()),
            patch("app.main.WindowsNotificationMonitor", return_value=MagicMock()),
            patch("app.main.is_workstation_locked", return_value=False),
            patch("app.main.get_system_idle_seconds", return_value=0.0),
            patch("ctypes.windll.user32.LockWorkStation", create=True),
        ):
            pet = PandaPet(data_dir=Path(self._tmp.name))
        pet._close_group_celebration()
        pet.window.update_idletasks()
        return pet

    def test_real_registry_and_wallpapers_promoted(self) -> None:
        registry = AssetRegistry(RES_ROOT / "work/asset_registry.json", RES_ROOT)
        lib = SpriteLibrary(RES_ROOT)

        for member in dome_stage.DOME_STAGE_MEMBERS:
            spec = registry.resolve(member, dome_stage.DOME_BASEBALL_ACTION)
            self.assertEqual(spec.asset_id, f"{member}.{dome_stage.DOME_BASEBALL_ACTION}")
            self.assertEqual(tuple(spec.canvas), (384, 384))
            self.assertEqual(len(spec.frames), 4)
            self.assertIn("desktop_action", spec.tags)
            self.assertIn("standby", spec.tags)
            loaded = load_exact_action(lib, member, dome_stage.DOME_BASEBALL_ACTION)
            self.assertIsNotNone(loaded, f"missing real action {member}.dome_baseball_cheer")
            self.assertEqual(len(loaded.frames), 4)
            self.assertIn(dome_stage.DOME_BASEBALL_ACTION, SCENE_ACTIONS["bg_standby_dome_baseball"][member])

        resolved = dome_stage.resolved_eunji_dome_outfits(lib, available_fn=available_actions)
        self.assertEqual(resolved, dome_stage.EUNJI_DOME_CONCERT_OUTFITS)
        for outfit in dome_stage.EUNJI_DOME_CONCERT_OUTFITS:
            spec = registry.resolve("eunji", outfit)
            self.assertEqual(spec.asset_id, f"eunji.{outfit}")
            self.assertEqual(tuple(spec.canvas), (384, 384))
            self.assertEqual(len(spec.frames), 4)
            self.assertIn("desktop_action", spec.tags)
            self.assertIn("standby", spec.tags)
            loaded = load_exact_action(lib, "eunji", outfit)
            self.assertIsNotNone(loaded, f"missing real action eunji.{outfit}")
            self.assertEqual(len(loaded.frames), 4)
            self.assertIn(outfit, SCENE_ACTIONS["bg_standby_eunji_dome_dream"]["eunji"])

        for flank in dome_stage.EUNJI_FLANK_MEMBERS:
            loaded = load_exact_action(lib, flank, dome_stage.DOME_FLANK_CHEER_ACTION)
            self.assertIsNotNone(loaded, f"missing real flank action {flank}.{dome_stage.DOME_FLANK_CHEER_ACTION}")
            self.assertIn(dome_stage.DOME_FLANK_CHEER_ACTION, SCENE_ACTIONS["bg_standby_eunji_dome_dream"][flank])

        walls = {w.key: w for w in load_wallpapers(RES_ROOT)}
        self.assertIn("bg_standby_dome_baseball", walls)
        self.assertIn("bg_standby_eunji_dome_dream", walls)
        with Image.open(walls["bg_standby_dome_baseball"].path) as im_b:
            self.assertEqual(im_b.size, (2752, 1536))
        with Image.open(walls["bg_standby_eunji_dome_dream"].path) as im_e:
            self.assertEqual(im_e.size, (1376, 768))

        forbidden_past = ("已舉辦", "舉辦過", "曾舉辦", "結束了", "was held", "performed at", "completed", "열렸던", "마친", "개최했")
        for lang in ("zh_TW", "ko", "en"):
            lbl = walls["bg_standby_eunji_dome_dream"].label(lang)
            self.assertTrue(lbl)
            self.assertNotIn("?", lbl)
            for bad in forbidden_past:
                self.assertNotIn(bad.lower(), lbl.lower())

    def test_real_pet_eunji_dome_personal_effect_and_desktop_previews(self) -> None:
        pet = self._spawn_real_pet(developer_mode=True)
        try:
            pet.switch_character("eunji", mode="manual")
            self.assertIn(dome_stage.EUNJI_DOME_PERSONAL_ACTION, pet.available_special_actions("eunji"))
            self.assertTrue(pet.trigger_special_action(dome_stage.EUNJI_DOME_PERSONAL_ACTION, "eunji"))
            self.assertEqual(pet._visual_action(), dome_stage.EUNJI_DOME_CONCERT_OUTFITS[0])
            eid, t0, seq = pet._eunji_dome_effect_state
            self.assertEqual(seq, dome_stage.EUNJI_DOME_CONCERT_OUTFITS)
            outfit_span_s = (4 * dome_stage.DOME_CONCERT_FRAME_MS) / 1000.0
            for idx, expected_outfit in enumerate(dome_stage.EUNJI_DOME_CONCERT_OUTFITS):
                pet._eunji_dome_effect_state = (eid, t0 - idx * outfit_span_s - 0.05, seq)
                self.assertEqual(pet._visual_action(), expected_outfit)
                self.assertIsNotNone(pet.current_frame())
            pet.coord.cancel(eid, "test_real_done")
            self.assertIsNone(pet._visual_action())

            # Real desktop baseball preview: non-overlapping opaque bboxes + safe overhead bubble on F3 CLIMAX
            pet.preview_dome_baseball_event()
            prev_b = pet.dome_preview
            self.assertIsNotNone(prev_b)
            self.assertEqual(set(prev_b.actor_windows), set(dome_stage.DOME_STAGE_MEMBERS))
            self.assertIsNotNone(prev_b.bubble_window)
            prev_b._t0 = time.monotonic() - 1.5
            prev_b._render_step(schedule_next=False)
            prev_b.bubble_window.update_idletasks()
            opaque_boxes = []
            for m in dome_stage.DOME_STAGE_MEMBERS:
                entry = prev_b._member_actions[m][dome_stage.DOME_BASEBALL_ACTION]
                sx, sy = prev_b.slots[m]
                bb = entry["alpha_bboxes"][2]
                opaque_boxes.append((sx + bb[0], sy + bb[1], sx + bb[2], sy + bb[3]))
            opaque_boxes.sort(key=lambda b: b[0])
            for i in range(len(opaque_boxes) - 1):
                self.assertLessEqual(opaque_boxes[i][2], opaque_boxes[i + 1][0], f"real desktop sprite overlap: {opaque_boxes}")
            bx = prev_b.bubble_window.winfo_x()
            by = prev_b.bubble_window.winfo_y()
            bh = prev_b.bubble_window.winfo_height()
            self.assertGreaterEqual(bx, prev_b.area.left)
            self.assertLessEqual(by + bh, min(b[1] for b in opaque_boxes) + 2)

            # Real desktop Eunji dream preview + caption toast + non-overlap + portrait 1008x2032 @ k=2.0 check
            with patch.object(pet, "_toast", wraps=pet._toast) as spy_toast:
                pet.preview_eunji_dome_event()
                self.assertTrue(prev_b.closed)
                prev_e = pet.dome_preview
                self.assertIsNotNone(prev_e)
                self.assertEqual(prev_e._eunji_outfits, dome_stage.EUNJI_DOME_CONCERT_OUTFITS)
                self.assertTrue(spy_toast.called)
                self.assertEqual(spy_toast.call_args.kwargs.get("header"), t("dome_eunji_dream_title", pet.lang))
                self.assertEqual(spy_toast.call_args.args[0], t("dome_eunji_dream_msg", pet.lang))
                prev_e._render_step(schedule_next=False)
                e_boxes = {}
                for m in dome_stage.DOME_STAGE_MEMBERS:
                    entry = prev_e._primary_entry(m)
                    sx, sy = prev_e.slots[m]
                    bb = entry["alpha_bboxes"][0]
                    box = (sx + bb[0], sy + bb[1], sx + bb[2], sy + bb[3])
                    self.assertGreaterEqual(box[0], prev_e.area.left, f"{m} clipped left: {box}")
                    self.assertLessEqual(box[2], prev_e.area.right, f"{m} clipped right: {box}")
                    e_boxes[m] = box
                ordered = [e_boxes[m] for m in dome_stage.DOME_STAGE_MEMBERS]
                for i in range(len(ordered) - 1):
                    self.assertLessEqual(ordered[i][2], ordered[i + 1][0], f"desktop Eunji overlap: {e_boxes}")
                pet._close_group_celebration()
                self.assertTrue(prev_e.closed)
                self.assertFalse(prev_e._after_ids)

            # Forced portrait 1008x2032 @ k=2.0 check regardless of host display geometry
            portrait_area = WorkArea(0, 0, 1008, 2032)
            with (
                patch.object(pet.desktop, "work_area_for_point", return_value=portrait_area),
                patch("app.dome_stage.ui_scale", return_value=2.0),
            ):
                pet.preview_eunji_dome_event()
                prev_p = pet.dome_preview
                self.assertIsNotNone(prev_p)
                prev_p._render_step(schedule_next=False)
                p_boxes = {}
                for m in dome_stage.DOME_STAGE_MEMBERS:
                    entry = prev_p._primary_entry(m)
                    sx, sy = prev_p.slots[m]
                    bb = entry["alpha_bboxes"][0]
                    box = (sx + bb[0], sy + bb[1], sx + bb[2], sy + bb[3])
                    self.assertGreaterEqual(box[0], 0, f"portrait {m} clipped left: {box}")
                    self.assertLessEqual(box[2], 1008, f"portrait {m} clipped right: {box}")
                    p_boxes[m] = box
                p_ordered = [p_boxes[m] for m in dome_stage.DOME_STAGE_MEMBERS]
                for i in range(len(p_ordered) - 1):
                    self.assertLessEqual(p_ordered[i][2], p_ordered[i + 1][0], f"portrait Eunji overlap: {p_boxes}")
                pet._close_group_celebration()
        finally:
            try:
                pet.close()
            finally:
                try:
                    pet.root.destroy()
                except tk.TclError:
                    pass

    def test_real_standby_both_dome_scenes_end_to_end(self) -> None:
        wallpapers = load_wallpapers(RES_ROOT)
        root = tk.Tk()
        root.withdraw()
        overlay = None
        try:
            with patch("ctypes.windll.user32.LockWorkStation", create=True):
                overlay = PandaStandbyOverlay(
                    root,
                    char_key="eunji",
                    char_name="Eunji",
                    frames={},
                    flipped_walk_frames=[],
                    scene="bg_standby_dome_baseball",
                    lang="zh_TW",
                    wallpapers=wallpapers,
                    lock_on_exit=False,
                )
            overlay.win.unbind("<Motion>")
            overlay.win.unbind("<ButtonPress>")
            overlay.win.unbind("<Key>")
            overlay.finish_action_loading()
            overlay.win.update_idletasks()
            overlay._dome_state["t0"] = time.monotonic() - 1.5
            overlay._animate_dome_scene(reschedule=False)
            overlay.win.update_idletasks()

            vis_boxes: list[tuple[int, int, int, int]] = []
            for p in overlay.pandas:
                self.assertIn(dome_stage.DOME_BASEBALL_ACTION, p["actions"])
                act = p["actions"][dome_stage.DOME_BASEBALL_ACTION]
                self.assertEqual(len(act["frames"]), 4)
                dx, dy = (int(v) for v in overlay.canvas.coords(p["img_item"]))
                bb = act["alpha_bboxes"][2]
                vis_boxes.append((dx + bb[0], dy + bb[1], dx + bb[2], dy + bb[3]))
            vis_boxes.sort(key=lambda b: b[0])
            for i in range(len(vis_boxes) - 1):
                self.assertLessEqual(vis_boxes[i][2], vis_boxes[i + 1][0], f"Standby Scene 1 overlap: {vis_boxes}")

            bubble_items = overlay.canvas.find_withtag("dome_bubble")
            self.assertEqual(len(bubble_items), 1)
            bub_bbox = overlay.canvas.bbox(bubble_items[0])
            self.assertIsNotNone(bub_bbox)
            self.assertGreaterEqual(bub_bbox[1], overlay.hint_bottom)
            self.assertLessEqual(bub_bbox[3], min(b[1] for b in vis_boxes) + 2)

            overlay.set_scene("bg_standby_eunji_dome_dream")
            overlay.finish_action_loading()
            overlay._animate_dome_scene(reschedule=False)
            overlay.win.update_idletasks()
            self.assertEqual(overlay.canvas.find_withtag("dome_bubble"), ())
            self.assertEqual(len(overlay.canvas.find_withtag("dome_eunji_fx")), 9)
            by_key = {p["key"]: p for p in overlay.pandas}
            for outfit in dome_stage.EUNJI_DOME_CONCERT_OUTFITS:
                self.assertIn(outfit, by_key["eunji"]["actions"])
            e_coords = overlay.canvas.coords(by_key["eunji"]["img_item"])
            for flank in dome_stage.EUNJI_FLANK_MEMBERS:
                self.assertIn(dome_stage.DOME_FLANK_CHEER_ACTION, by_key[flank]["actions"])
                fx, fy = overlay.canvas.coords(by_key[flank]["img_item"])
                self.assertGreater(fy, e_coords[1])

            s2_boxes = {}
            for m in dome_stage.DOME_STAGE_MEMBERS:
                p = by_key[m]
                act_name = dome_stage.EUNJI_DOME_CONCERT_OUTFITS[0] if m == "eunji" else dome_stage.DOME_FLANK_CHEER_ACTION
                act = p["actions"][act_name]
                dx, dy = (int(v) for v in overlay.canvas.coords(p["img_item"]))
                bb = act["alpha_bboxes"][0]
                box = (dx + bb[0], dy + bb[1], dx + bb[2], dy + bb[3])
                self.assertGreaterEqual(box[0], 0, f"Standby Scene 2 {m} clipped left: {box}")
                self.assertLessEqual(box[2], overlay.sw, f"Standby Scene 2 {m} clipped right: {box}")
                s2_boxes[m] = box
            s2_ordered = [s2_boxes[m] for m in dome_stage.DOME_STAGE_MEMBERS]
            for i in range(len(s2_ordered) - 1):
                self.assertLessEqual(s2_ordered[i][2], s2_ordered[i + 1][0], f"Standby Scene 2 overlap: {s2_boxes}")

            overlay.set_scene("starfield")
            self.assertEqual(overlay.canvas.find_withtag("dome_stage"), ())
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            self.assertFalse(overlay._after_ids if overlay is not None else {})
            try:
                root.destroy()
            except tk.TclError:
                pass


if __name__ == "__main__":
    unittest.main()
