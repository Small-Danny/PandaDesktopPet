"""Standby wallpapers (approved, hash-checked images) and parade stops with standby actions.

Run:  python -m unittest tests.test_standby_wallpapers -v
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
import sys
import tempfile
import time
import tkinter as tk
import unittest
from PIL import ImageTk
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from app.paths import resource_dir  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import (  # noqa: E402
    SCENES, PandaStandbyOverlay, WallpaperSpec, action_allowed, cover_image, display_action_frame,
    load_wallpapers, pick_pause_actions, scene_fits, secret_visitor_allowed, standby_contexts, walk_feet_point,
    STANDBY_BINARY_ALPHA, STANDBY_EDGE_REFINE,
)
from app.sprites import scale_to_display  # noqa: E402
from app.daily_actions import SCENE_ACTIONS  # noqa: E402


def _figure(canvas: int, feet_y: int) -> Image.Image:
    """A 120x200 'body' standing on (canvas/2, feet_y), plus a 40 px hat above it."""
    im = Image.new("RGBA", (canvas, canvas))
    cx = canvas // 2
    im.paste((200, 80, 120, 255), (cx - 60, feet_y - 200, cx + 60, feet_y))
    im.paste((20, 20, 200, 255), (cx - 20, feet_y - 240, cx + 20, feet_y - 200))
    return im


def _placed_bbox(frame: Image.Image, offset: tuple[int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = frame.getchannel("A").getbbox()
    return x1 + offset[0], y1 + offset[1], x2 + offset[0], y2 + offset[1]

APP_WALLPAPERS = ["bg_standby_autumn_cafe", "bg_standby_moonlight_terrace", "bg_standby_spring_picnic",
                  "bg_standby_summer_beach", "concert_stage_audience", "bg_standby_christmas",
                  "bg_standby_musical_theater", "bg_standby_dome_baseball", "bg_standby_eunji_dome_dream",
                  "bg_standby_eunji_fortune_room"]
SECRET_POLICY = {"mode": "easter_egg_only", "allowed_contexts": ["concert_stage_audience", "anniversary_0419"],
                 "allow_random_cameo": False, "expose_name_in_ui": False}


def _jpg(path: Path, size=(320, 180), color=(200, 120, 160)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LoadWallpapersTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _manifest(self, backgrounds, schema=1) -> None:
        (self.root / "work").mkdir(exist_ok=True)
        (self.root / "work" / "standby_backgrounds.json").write_text(
            json.dumps({"schema_version": schema, "backgrounds": backgrounds}), encoding="utf-8")

    def _entry(self, key="bg_beach", rel="work/bg/beach.jpg", sha=None, status="approved", size=(320, 180), **kw):
        real = _jpg(self.root / rel) if (self.root / rel).resolve().is_relative_to(self.root) else "0"
        return dict(key=key, path=rel, sha256=sha or real, width=size[0], height=size[1], status=status, **kw)

    def test_no_manifest_means_no_wallpapers(self) -> None:
        self.assertEqual(load_wallpapers(self.root), ())

    def test_only_approved_hash_matching_entries_under_work(self) -> None:
        outside = self.root.parent / f"{self.root.name}_outside.jpg"
        _jpg(outside)
        self.addCleanup(outside.unlink)
        self._manifest([
            self._entry(labels={"zh_TW": "海灘", "en": "Beach", "ko": 3}),
            self._entry(key="bg_cafe", rel="work/bg/cafe.jpg", sha="0" * 64),          # changed bytes
            self._entry(key="bg_moon", rel="work/bg/moon.jpg", status="review_pending"),  # not approved
            self._entry(key="bg_sea", rel="work/bg/sea.jpg", size=(1920, 1080)),      # size differs
            self._entry(key="bg_out", rel=f"../{outside.name}"),                       # outside the app
            self._entry(key="bg_beach", rel="work/bg/beach2.jpg"),                     # duplicate key
            self._entry(key="christmas", rel="work/bg/xmas.jpg"),                      # drawn scene name
            {"key": "bg_broken"},
        ])
        walls = load_wallpapers(self.root)
        self.assertEqual([w.key for w in walls], ["bg_beach"])
        self.assertEqual(walls[0].path, (self.root / "work/bg/beach.jpg").resolve())
        self.assertEqual((walls[0].label("en"), walls[0].label("ko")), ("Beach", "海灘"))   # bad label dropped

    def test_unknown_schema_or_bad_json_is_ignored(self) -> None:
        self._manifest([self._entry()], schema=2)
        self.assertEqual(load_wallpapers(self.root), ())
        (self.root / "work" / "standby_backgrounds.json").write_text("{", encoding="utf-8")
        self.assertEqual(load_wallpapers(self.root), ())

    def test_the_apps_approved_wallpapers_load(self) -> None:
        # work/standby_backgrounds.json, approved 2026-11-08 (six 2752x1536 photos).
        walls = load_wallpapers()
        self.assertEqual([w.key for w in walls], APP_WALLPAPERS)
        for w in walls:
            with self.subTest(key=w.key):
                self.assertTrue(all(w.labels.get(lang) for lang in ("zh_TW", "ko", "en")))
                self.assertNotIn("?", w.label("zh_TW") + w.label("ko"))


class PureRulesTest(unittest.TestCase):
    def test_cover_fills_and_keeps_the_middle(self) -> None:
        im = Image.new("RGB", (400, 100), "red")
        im.paste((0, 0, 255), (150, 0, 250, 100))                  # blue middle band
        out = cover_image(im, 200, 200)
        self.assertEqual(out.size, (200, 200))
        self.assertEqual(out.getpixel((100, 100)), (0, 0, 255))

    def test_contexts(self) -> None:
        self.assertEqual(standby_contexts("bg_beach", dt.date(2026, 7, 1)), {"bg_beach"})
        self.assertIn("christmas", standby_contexts("starfield", dt.date(2026, 12, 3)))
        self.assertIn("anniversary_0419", standby_contexts("starfield", dt.date(2027, 4, 19)))

    def test_action_context_tags(self) -> None:
        self.assertTrue(action_allowed(("standby",), {"starfield"}))
        self.assertFalse(action_allowed(("desktop_action", "standby", "context:christmas"), {"starfield"}))
        self.assertTrue(action_allowed(("context:christmas", "context:bg_xmas"), {"bg_xmas"}))

    def test_secret_visitor_only_in_its_contexts(self) -> None:
        normal = dt.date(2026, 11, 8)
        self.assertTrue(secret_visitor_allowed(SECRET_POLICY, "concert_stage_audience", normal))
        self.assertTrue(secret_visitor_allowed(SECRET_POLICY, "starfield", dt.date(2027, 4, 19)))
        self.assertFalse(secret_visitor_allowed(SECRET_POLICY, "starfield", normal))
        self.assertFalse(secret_visitor_allowed(dict(SECRET_POLICY, mode="random"), "concert_stage_audience", normal))
        self.assertFalse(secret_visitor_allowed(None, "concert_stage_audience", normal))
        self.assertFalse(secret_visitor_allowed({"mode": "easter_egg_only"}, "concert_stage_audience", normal))

    def test_pause_plan(self) -> None:
        plan = pick_pause_actions({"chorong": [], "eunji": ["guitar"]}, random.Random(1))
        self.assertIsNone(plan["chorong"])                    # nothing allowed: cheer
        picks = {pick_pause_actions({"eunji": ["guitar"]}, random.Random(s))["eunji"] for s in range(40)}
        self.assertEqual(picks, {"guitar", None})             # sometimes the action, sometimes a cheer


class ActionPlacementTest(unittest.TestCase):
    SIZE, SCALE = 192, 0.95      # the 256 figure still fits the walk canvas (1.1 would clip its hat)

    def test_256_action_lands_where_the_walk_pipeline_puts_it(self) -> None:
        art = _figure(256, 244)
        frame, feet = display_action_frame(art, (128, 244), self.SCALE, self.SIZE)
        wx, wy = walk_feet_point(self.SIZE)
        expected = scale_to_display(art, self.SCALE, self.SIZE).getchannel("A").getbbox()
        for a, b in zip(_placed_bbox(frame, (wx - feet[0], wy - feet[1])), expected):
            self.assertLessEqual(abs(a - b), 1)

    def test_384_canvas_keeps_the_body_size_and_the_feet(self) -> None:
        small, f_small = display_action_frame(_figure(256, 244), (128, 244), self.SCALE, self.SIZE)
        big, f_big = display_action_frame(_figure(384, 372), (192, 372), self.SCALE, self.SIZE)
        wx, wy = walk_feet_point(self.SIZE)
        a = _placed_bbox(small, (wx - f_small[0], wy - f_small[1]))
        b = _placed_bbox(big, (wx - f_big[0], wy - f_big[1]))
        for u, v in zip(a, b):
            self.assertLessEqual(abs(u - v), 1)                     # same body, same feet: not shrunk
        self.assertGreater(big.height, self.SIZE)                    # taller than a walk frame
        self.assertEqual(set(big.getchannel("A").get_flattened_data()) - {0, 255}, set())   # colour-key safe

    def test_tall_hat_is_kept_where_the_walk_canvas_would_clip_it(self) -> None:
        art = _figure(384, 372)
        frame, feet = display_action_frame(art, (192, 372), 1.1, self.SIZE)
        wx, wy = walk_feet_point(self.SIZE)
        top = _placed_bbox(frame, (wx - feet[0], wy - feet[1]))[1]
        self.assertLess(top, 0)                                      # rises above the walk frame
        self.assertEqual(frame.getchannel("A").getbbox()[1] > 0, True)  # nothing cut off at the top


class PreparedCacheKeyTest(unittest.TestCase):
    """Same PNG bytes, new calibration in the registry: the prepared standby frames are redone."""

    def test_recalibrated_frames_miss_the_prepared_cache(self) -> None:
        import types
        from app.standby import PREPARED_IMAGES, _source_signature
        records = {f"f{i}.png": {"sha256": "ab" * 32, "normalization_mode": "bbox", "normalization_scale": 1.0,
                                 "alpha_bbox": [10, 20, 120, 240], "source_size": [256, 256],
                                 "normalized_size": [256, 256], "anchor": [128, 244]} for i in range(2)}
        registry = types.SimpleNamespace(_record=lambda path: records[path])
        spec = types.SimpleNamespace(asset_id="eunji.guitar", member="eunji", action="guitar", frames=tuple(records), fps=4, tags=("standby",),
                                     anchor=(128, 244), canvas=(256, 256))
        loads = []

        def load_animation(s):
            loads.append(s)
            return s, [_figure(256, 244), _figure(256, 244)]

        library = types.SimpleNamespace(registry=registry, polish=False, display_px=192,
                                        cache=types.SimpleNamespace(load_animation=load_animation))
        prepare = lambda: PandaStandbyOverlay._prepared_action(None, library, spec, 0.95)   # noqa: E731
        PREPARED_IMAGES.clear()
        self.addCleanup(PREPARED_IMAGES.clear)
        prepare()
        prepare()
        self.assertEqual((len(loads), PREPARED_IMAGES.hits), (1, 1))      # unchanged: a cache hit
        base = _source_signature(registry, spec)
        for field, value in (("normalization_scale", 2.0), ("normalization_mode", "preserve_canvas"),
                             ("anchor", [128, 200]), ("alpha_bbox", [0, 0, 256, 244])):
            with self.subTest(field=field):
                old = records["f1.png"][field]
                records["f1.png"][field] = value
                self.assertNotEqual(_source_signature(registry, spec), base)
                n = len(loads)
                prepare()
                self.assertEqual(len(loads), n + 1)                       # decoded again, not the old pixels
                records["f1.png"][field] = old
        self.assertEqual(_source_signature(registry, spec), base)
        self.assertNotEqual(_source_signature(registry, _with(spec, anchor=(192, 372))), base)
        self.assertIsNone(_source_signature(registry, _with(spec, frames=("missing.png",))))
        self.assertIsNone(_source_signature(object(), spec))              # a registry without _record


def _with(ns, **changes):
    import types
    return types.SimpleNamespace(**{**vars(ns), **changes})


class OverlayTest(unittest.TestCase):
    """Real overlay on a real Tk root (the parade uses the approved sprites)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()
        sprites = SpriteLibrary(resource_dir()).load_member("chorong", cls.root)
        cls.frames, cls.flipped = sprites.frames, sprites.flipped("walk")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wall = WallpaperSpec("bg_test", Path(cls.tmp.name) / "w.jpg", {"zh_TW": "測試桌布", "en": "Test"})
        _jpg(cls.wall.path, (640, 360), (10, 200, 30))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()
        cls.tmp.cleanup()

    def _overlay(self, finish_actions: bool = True, **kw) -> PandaStandbyOverlay:
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            ov = PandaStandbyOverlay(self.root, "chorong", "初瓏", self.frames, self.flipped,
                                     lock_on_exit=False, **kw)
        if finish_actions:         # the actions load after opening; most tests stage them up front
            ov.finish_action_loading()
        # Someone using the PC (mouse or keyboard) must not close it mid-test.
        ov.win.unbind("<Motion>")
        ov.win.unbind("<ButtonPress>")
        ov.win.unbind("<Key>")
        ov.max_performers = 5      # the stop-cap has its own test; the older tests stage all five
        self.addCleanup(ov.handle_exit)
        self.root.update()
        return ov

    def test_the_apps_wallpapers_follow_the_drawn_scenes(self) -> None:
        ov = self._overlay(scene="starfield")                      # wallpapers from the app's manifest
        self.assertEqual(ov.scenes, SCENES + tuple(APP_WALLPAPERS))
        ov.set_scene("bg_standby_christmas")
        self.assertEqual(ov.scene_label(), "聖誕小木屋")

    def test_without_wallpapers_the_scenes_are_unchanged(self) -> None:
        ov = self._overlay(scene="campfire", wallpapers=())
        self.assertEqual(ov.scenes, SCENES)
        self.assertEqual(ov.scene, "campfire")

    def test_wallpaper_scene_shows_the_image_and_cycles(self) -> None:
        ov = self._overlay(scene="practice_room", wallpapers=[self.wall], lang="en")
        self.assertEqual(ov.scenes, SCENES + ("bg_test",))
        self.assertEqual(ov.cycle_scene(1), "bg_test")
        images = [i for i in ov.canvas.find_withtag("bg") if ov.canvas.type(i) == "image"]
        self.assertEqual(len(images), 1)
        photo = ov._wallpaper_cache["bg_test"]
        self.assertEqual((photo.width(), photo.height()), (ov.sw, ov.sh))
        self.assertIn("Test", ov.canvas.itemcget(ov.scene_hint_item, "text"))
        self.assertLess(ov.canvas.find_all().index(images[0]),                  # backdrop under the parade
                        ov.canvas.find_all().index(ov.pandas[0]["img_item"]))
        self.assertEqual(ov.cycle_scene(1), "starfield")                        # wraps to the drawn scenes
        self.assertEqual(ov.cycle_scene(-1), "bg_test")
        self.assertEqual(len(ov._wallpaper_cache), 1)                           # decoded once

    def test_hints_get_a_dark_backing_on_photos(self) -> None:
        ov = self._overlay(scene="bg_test", wallpapers=[self.wall])
        order = ov.canvas.find_all()
        image = next(i for i in ov.canvas.find_withtag("bg") if ov.canvas.type(i) == "image")
        backing = [i for i in ov.canvas.find_withtag("bg") if ov.canvas.type(i) == "polygon"]
        self.assertEqual(len(backing), 1)
        self.assertLess(order.index(image), order.index(backing[0]))          # above the photo
        self.assertLess(order.index(backing[0]), order.index(ov.hint_item))   # under the text
        bx1, by1, bx2, by2 = ov.canvas.bbox(backing[0])
        for item in (ov.hint_item, ov.scene_hint_item):
            x1, y1, x2, y2 = ov.canvas.bbox(item)
            self.assertTrue(bx1 <= x1 and x2 <= bx2 and by1 <= y1 and y2 <= by2, item)
        ov.set_scene("starfield")                                             # drawn scenes: no backing
        self.assertFalse([i for i in ov.canvas.find_withtag("bg") if ov.canvas.type(i) == "polygon"
                          and ov.canvas.bbox(i)[1] < ov.hint_bottom and ov.canvas.itemcget(i, "fill") == "#141826"])

    def test_unreadable_wallpaper_falls_back_to_the_starfield(self) -> None:
        bad = WallpaperSpec("bg_bad", Path(self.tmp.name) / "missing.jpg")
        ov = self._overlay(scene="bg_bad", wallpapers=[bad])
        self.assertTrue(ov.running)
        self.assertEqual(ov.scene, "bg_bad")
        self.assertFalse([i for i in ov.canvas.find_withtag("bg") if ov.canvas.type(i) == "image"])

    def _fake_action(self, ov, member, name, tags=("standby",), n=4, frame_ms=390.0):
        h = ov.pandas[0]["ph"]
        frames = [tk.PhotoImage(master=ov.win, width=ov.pandas[0]["pw"], height=h) for _ in range(n)]
        panda = next(p for p in ov.pandas if p["key"] == member)
        # The only action: real approved ones (e.g. December's) must not change the pick.
        panda["actions"] = {name: {"frames": frames, "frame_ms": frame_ms, "tags": tuple(tags)}}
        return frames

    def _play_stop(self, ov, member):
        ov._cancel_all_timers()                                   # drive the parade by hand
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov._start_pause()
        ov.rng.random.return_value = 1.0                          # no new stop afterwards
        panda = next(p for p in ov.pandas if p["key"] == member)
        shown, x0, length = [], ov.px, ov.p_cheer_ticks
        for _ in range(length):
            ov.animate_pandas()
            shown.append(ov.canvas.itemcget(panda["img_item"], "image"))
        self.assertEqual(ov.px, x0)                                # stood still the whole stop
        return shown, length

    def test_parade_stop_plays_each_frame_of_the_action_then_walks_on(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=())
        for p in ov.pandas:      # only eunji performs (chorong's real hot tea came later)
            p["actions"] = {}
        f = [str(x) for x in self._fake_action(ov, "eunji", "guitar")]     # 390 ms = 3 ticks per frame
        shown, length = self._play_stop(ov, "eunji")
        self.assertEqual(ov.pause_plan["eunji"], "guitar")
        self.assertIsNone(ov.pause_plan["chorong"])               # no standby action: cheer
        self.assertEqual(length, 18)                              # 4 x 390 ms < the 18-tick minimum
        self.assertEqual(shown, [f[0]] * 3 + [f[1]] * 3 + [f[2]] * 3 + [f[3]] * 9)   # then holds the last
        x0 = ov.px
        ov.animate_pandas()
        self.assertNotEqual(ov.px, x0)                             # walking again

    def test_offset_action_is_drawn_at_its_feet_and_walks_back_into_line(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=())
        for p in ov.pandas:      # only eunji performs (chorong's real hot tea came later)
            p["actions"] = {}
        self._fake_action(ov, "eunji", "guitar")
        eunji = next(p for p in ov.pandas if p["key"] == "eunji")
        eunji["actions"]["guitar"]["offset"] = (-30, -64)          # e.g. a 384 canvas with a tall hat
        i = ov.pandas.index(eunji)
        ov._cancel_all_timers()
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov._start_pause()
        ov.rng.random.return_value = 1.0
        ov.animate_pandas()
        cur_x = ov.px + i * (ov.pandas[0]["pw"] + ov.gap)
        self.assertEqual(ov.canvas.coords(eunji["img_item"]), [cur_x - 30.0, ov.py - 64.0])
        chorong = ov.pandas[0]
        self.assertEqual(ov.canvas.coords(chorong["img_item"]), [float(ov.px), float(ov.py)])   # cheering: in line
        while ov.p_cheer_ticks:
            ov.animate_pandas()
        ov.animate_pandas()                                          # first walking tick
        cur_x = ov.px + i * (ov.pandas[0]["pw"] + ov.gap)
        self.assertEqual(ov.canvas.coords(eunji["img_item"]), [float(cur_x), float(ov.py)])

    def test_one_tick_frames_start_at_the_first_frame(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=())
        f = [str(x) for x in self._fake_action(ov, "eunji", "guitar", frame_ms=130.0)]
        shown, _ = self._play_stop(ov, "eunji")
        self.assertEqual(shown[:4], f)

    def test_long_action_stop_lasts_a_full_pass_at_its_fps(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=())
        f = [str(x) for x in self._fake_action(ov, "eunji", "tea", n=8, frame_ms=500.0)]   # 2 fps
        shown, length = self._play_stop(ov, "eunji")
        self.assertEqual(length, math.ceil(8 * 500 / 130))        # 4 s, longer than the minimum
        self.assertEqual([s for i, s in enumerate(shown) if i == 0 or s != shown[i - 1]], f)
        self.assertEqual(shown[-1], f[-1])
        self.assertEqual(shown.index(f[1]), math.ceil(500 / 130))  # by elapsed time, not rounded ticks

    def test_stop_loops_holds_or_returns_to_cheer_by_action(self) -> None:
        """Past one pass a loop cycles, a finishing pose holds, a one-off hands back to the cheer."""
        for flags, expected in (
            ({"loop": True, "hold": False}, lambda f: [f[i % 4] for i in range(18)]),
            ({"loop": False, "hold": True}, lambda f: f + [f[3]] * 14),
            ({"loop": False, "hold": False}, None),
        ):
            with self.subTest(**flags):
                ov = self._overlay(scene="starfield", wallpapers=())
                for p in ov.pandas:
                    p["actions"] = {}
                f = [str(x) for x in self._fake_action(ov, "eunji", "move", frame_ms=130.0)]
                next(p for p in ov.pandas if p["key"] == "eunji")["actions"]["move"].update(flags)
                shown, length = self._play_stop(ov, "eunji")
                self.assertEqual(length, 18)
                if expected is not None:
                    self.assertEqual(shown, expected(f))
                else:
                    cheer = {str(x) for x in next(p for p in ov.pandas if p["key"] == "eunji")["cheer"]}
                    self.assertEqual(shown[:4], f)
                    self.assertTrue(shown[4:] and all(s in cheer for s in shown[4:]), shown[4:])

    def test_action_entry_classifies_stop_playback(self) -> None:
        import types
        from app.standby import PAUSE_HOLD_END, PAUSE_ONCE_THEN_CHEER

        ov = self._overlay(scene="starfield", wallpapers=())
        lib = types.SimpleNamespace(display_px=ov.sprite_px)
        im = Image.new("RGBA", (8, 8), (255, 0, 0, 255))

        def entry(action, n):
            spec = types.SimpleNamespace(action=action, fps=4.0, tags=("standby",))
            return ov._action_entry(lib, spec, ([im] * n, (4, 8)))

        self.assertEqual((entry("scene_cafe", 4)["loop"], entry("scene_cafe", 4)["hold"]), (True, False))
        self.assertEqual((entry("musical_bow", 4)["loop"], entry("musical_bow", 4)["hold"]), (False, True))
        self.assertEqual((entry("christmas_gift", 4)["loop"], entry("christmas_gift", 4)["hold"]), (False, False))
        self.assertEqual((entry("scene_cafe", 1)["loop"], entry("scene_cafe", 1)["hold"]), (False, True))
        lib = SpriteLibrary(resource_dir())
        if lib.registry is not None:      # every listed name is a real approved multi-frame action
            for name in PAUSE_HOLD_END | PAUSE_ONCE_THEN_CHEER:
                owners = [m for m in ("chorong", "bomi", "eunji", "namjoo", "hayoung")
                          if (s := lib.registry.resolve(m, name)) is not None and s.action == name]
                self.assertTrue(owners, name)
                self.assertTrue(all(len(lib.registry.resolve(m, name).frames) > 1 for m in owners), name)

    def test_context_action_only_in_its_context(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=(), today=dt.date(2026, 7, 1))
        self._fake_action(ov, "bomi", "xmas_gift", tags=("desktop_action", "standby", "context:christmas"))
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov._start_pause()
        self.assertIsNone(ov.pause_plan["bomi"])
        ov.today = dt.date(2026, 12, 20)
        ov._start_pause()
        self.assertEqual(ov.pause_plan["bomi"], "xmas_gift")

    def test_loader_uses_exact_approved_actions_at_the_parade_scale(self) -> None:
        # Pretend the approved "cheer" is tagged standby and "tea" (not in the registry) is too:
        # cheer loads at the walk height, tea would resolve to a basic fallback and is skipped.
        ov = self._overlay(scene="starfield", wallpapers=())
        lib = SpriteLibrary(resource_dir(), display_px=ov.sprite_px)
        if lib.registry is None:
            self.skipTest("registry missing")
        walk = lib.load_member("eunji", ov.win).get("walk")
        with mock.patch.object(lib.registry, "actions", return_value=("cheer", "tea")):
            actions = ov._load_standby_actions(lib, "eunji", walk)
        own = set(SCENE_ACTIONS.get("starfield", {}).get("eunji", ()))   # the scene's own move loads too
        self.assertEqual(set(actions) - own, {"cheer"})
        frames = actions["cheer"]["frames"]
        self.assertEqual(len(frames), 4)
        self.assertAlmostEqual(actions["cheer"]["frame_ms"], 130.0, places=1)   # registry fps 7.69
        # Same pixels as the parade's own cheer frame (same scale, feet on the same point).
        own = lib.load_member("eunji", ov.win)._pil["cheer"][0]
        got = ImageTk.getimage(frames[0])
        dx, dy = actions["cheer"]["offset"]
        for a, b in zip(_placed_bbox(got, (dx, dy)), own.getchannel("A").getbbox()):
            self.assertLessEqual(abs(a - b), 2)

    def test_real_christmas_actions_load_for_all_five_only_in_december(self) -> None:
        # Approved 384 canvases (tags standby + context:christmas), registered 2026-11-08.
        ov = self._overlay(scene="starfield", wallpapers=(), today=dt.date(2026, 12, 24))
        lib = SpriteLibrary(resource_dir(), display_px=ov.sprite_px, binary_alpha=STANDBY_BINARY_ALPHA,
                            edge_refine=STANDBY_EDGE_REFINE)   # same pipeline as the overlay
        if lib.registry is None:
            self.skipTest("registry missing")
        self.assertEqual(len(ov.pandas), 5)
        for p in ov.pandas:
            with self.subTest(member=p["key"]):
                action = p["actions"]["festival_christmas"]
                self.assertEqual(len(action["frames"]), 4)
                self.assertAlmostEqual(action["frame_ms"], 180.0, places=1)
                self.assertEqual(action["tags"], ("desktop_action", "standby", "context:christmas"))
                # Feet on the parade line (the art's lowest prop may sit up to 3 px below them).
                # Feet line = the solid figure (alpha >= 128): standby frames are soft-alpha
                # since 2026-11-22 and their faint anti-aliased rim adds a pixel to getbbox().
                solid = lambda im: im.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
                walk = solid(lib.load_member(p["key"], ov.win)._pil["walk"][0]).getbbox()
                for frame in action["frames"]:
                    x1, y1, x2, y2 = solid(ImageTk.getimage(frame)).getbbox()
                    placed = (x1 + action["offset"][0], y1 + action["offset"][1],
                              x2 + action["offset"][0], y2 + action["offset"][1])
                    self.assertLessEqual(abs(placed[3] - walk[3]), 4)
        # Every stop, whatever the dice say: a member who "just cheers" used to stop in her
        # everyday outfit (Chorong and Eunji in the cabin, reported 2026-11-10).
        for roll in (0.0, 0.99):
            ov.rng = mock.Mock(random=mock.Mock(return_value=roll), choice=lambda seq: seq[0])
            ov._start_pause()
            self.assertEqual(ov.pause_plan, {p["key"]: "festival_christmas" for p in ov.pandas})
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov.today = dt.date(2026, 11, 8)
        ov._start_pause()
        self.assertNotIn("festival_christmas", set(ov.pause_plan.values()))

    def test_other_monitors_get_a_cover_with_the_scene_but_no_clock(self) -> None:
        """With two screens the second one used to stay a normal desktop.

        2026-11-22: the cover no longer draws a centred white clock/date (unreadable on photos).
        """
        import types
        from app.platform.win32 import WorkArea
        photo_scene = next(iter(load_wallpapers()))
        ov = self._overlay(scene=photo_scene.key, bounds=WorkArea(0, 0, 640, 480),
                           other_bounds=(WorkArea(640, 0, 1040, 300),))
        self.assertEqual(len(ov.covers), 1)
        cover = ov.covers[0]
        cover["win"].unbind("<Motion>")
        cover["win"].unbind("<ButtonPress>")
        cover["win"].unbind("<Key>")
        self.assertEqual((cover["w"], cover["h"]), (400, 300))
        self.assertTrue(cover["canvas"].find_withtag("bg"))                  # the same photo backdrop
        ov.update_clock()
        self.assertIsNone(cover["clock"])
        self.assertIsNone(cover["date"])
        self.assertFalse([i for i in cover["canvas"].find_all() if cover["canvas"].type(i) == "text"])
        ov.set_scene("starfield")                                            # a drawn scene: full static backdrop
        self.assertTrue(cover["canvas"].find_withtag("bg"))
        self.assertEqual(cover["canvas"].cget("bg"), ov.canvas.cget("bg"))
        # Moving the mouse on the other screen ends standby too (screen coordinates).
        ov._created_at -= 10
        ov.handle_motion(types.SimpleNamespace(x=5, y=5, x_root=700, y_root=50))
        ov.handle_motion(types.SimpleNamespace(x=200, y=5, x_root=900, y_root=50))
        self.assertFalse(ov.running)
        self.assertFalse(cover["win"].winfo_exists())


    def test_the_christmas_cabin_dresses_all_five_in_any_month(self) -> None:
        from app.standby import CHRISTMAS_SETS
        ov = self._overlay(scene="bg_standby_christmas", today=dt.date(2026, 11, 10))
        if not all(s in p["actions"] for p in ov.pandas for s in CHRISTMAS_SETS):
            self.skipTest("Christmas actions not registered")
        # Each stop all five share one set: the outfit, unwrapping presents, or scarves and hot cocoa.
        for pick, expected in ((lambda seq: seq[0], "festival_christmas"), (lambda seq: seq[1], "christmas_gift"),
                               (lambda seq: seq[-1], "winter_cocoa")):
            for roll in (0.0, 0.5, 0.99):
                ov.rng = mock.Mock(random=mock.Mock(return_value=roll), choice=pick)
                ov._start_pause()
                self.assertEqual(ov.pause_plan, {p["key"]: expected for p in ov.pandas}, (expected, roll))
        # Nowhere else: a summer beach in July has none of them.
        ov.set_scene("bg_standby_summer_beach")
        ov.today = dt.date(2026, 7, 1)
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov._start_pause()
        self.assertFalse(set(ov.pause_plan.values()) & set(CHRISTMAS_SETS))

    def test_drawn_parade_scenes_play_their_own_moves_only_there(self) -> None:
        # Registered 2026-11-13 as plain desktop_action; SCENE_ACTIONS makes them the scene's extras.
        drawn = {"starfield": "scene_starfield", "campfire": "scene_campfire", "practice_room": "scene_practice_room"}
        ov = self._overlay(scene="starfield", wallpapers=(), today=dt.date(2026, 7, 1))
        if not all(drawn["starfield"] in p["actions"] for p in ov.pandas):
            self.skipTest("drawn scene actions not registered")
        self.assertEqual(len(ov.pandas), 5)
        for scene, action in drawn.items():
            ov.set_scene(scene)
            for p in ov.pandas:
                with self.subTest(scene=scene, member=p["key"]):
                    info = p["actions"][action]
                    self.assertEqual(len(info["frames"]), 4)
                    self.assertTrue(scene_fits(action, info["tags"], p["key"], scene))
                    for other in drawn:
                        if other != scene:
                            self.assertFalse(scene_fits(action, info["tags"], p["key"], other))
            real_rng, ov.rng = ov.rng, mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
            ov._start_pause()
            ov.rng = real_rng                                     # the next scene draws its own sky
            self.assertEqual(ov.pause_plan, {p["key"]: action for p in ov.pandas}, scene)

    def test_musical_stage_all_five_dance_despite_the_performer_cap(self) -> None:
        from app.standby import MAX_PAUSE_PERFORMERS
        dances = {"musical_step", "musical_swish", "musical_bow"}
        ov = self._overlay(scene="bg_standby_musical_theater", today=dt.date(2026, 7, 1))
        ov.max_performers = MAX_PAUSE_PERFORMERS                  # the real cap, not the tests' five
        if not all(dances <= set(p["actions"]) for p in ov.pandas):
            self.skipTest("musical actions not registered")
        self.assertEqual(len(ov.pandas), 5)
        for pick in (lambda seq: seq[0], lambda seq: seq[-1]):
            for roll in (0.0, 0.99):
                ov.rng = mock.Mock(random=mock.Mock(return_value=roll), choice=pick)
                ov._start_pause()
                self.assertEqual(set(ov.pause_plan), {p["key"] for p in ov.pandas})
                for key, action in ov.pause_plan.items():
                    self.assertIn(action, dances, (key, roll))        # never the static musical_pose

    def test_actions_load_after_the_window_opens(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=(), finish_actions=False)
        if getattr(ov, "_library", None) is None or ov._library.registry is None:
            self.skipTest("registry missing")
        self.assertTrue(ov.actions_loading())                      # the window did not wait for them
        self.assertIn("load_actions", ov._after_ids)
        self.assertTrue(any(not p["actions"] for p in ov.pandas))
        deadline = time.monotonic() + 30
        while ov.actions_loading() and time.monotonic() < deadline:
            self.root.update()                                     # the after() steps load them
            time.sleep(0.005)
        self.assertFalse(ov.actions_loading())
        pending = set(ov.win.tk.splitlist(ov.win.tk.call("after", "info")))
        self.assertNotIn(ov._after_ids.get("load_actions"), pending)      # no further load step
        self.assertTrue(all("scene_starfield" in p["actions"] for p in ov.pandas))

    def test_early_scene_change_stop_and_exit_while_actions_load(self) -> None:
        ov = self._overlay(scene="starfield", wallpapers=(), finish_actions=False)
        if getattr(ov, "_library", None) is None or ov._library.registry is None:
            self.skipTest("registry missing")
        self.assertTrue(ov.actions_loading())
        ov.set_scene("campfire")                                   # the queue now loads the campfire's
        self.assertTrue(ov.actions_loading())
        ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        ov._start_pause()                                          # a stop finishes the loading first
        self.assertFalse(ov.actions_loading())
        self.assertNotIn("load_actions", ov._after_ids)
        self.assertTrue(all("scene_campfire" in p["actions"] for p in ov.pandas))
        ov.finish_action_loading()                                 # nothing left: a no-op
        ov.dismiss()
        self.assertFalse(ov.running)
        self.assertEqual(ov._after_ids, {})
        ov.finish_action_loading()                                 # after closing: still safe
        ov._load_next_action()

        ov2 = self._overlay(scene="starfield", wallpapers=(), finish_actions=False)
        self.assertTrue(ov2.actions_loading())
        ov2.dismiss()                                              # closed before anything loaded
        self.assertEqual(ov2._after_ids, {})
        before = {k: len(p["actions"]) for k, p in ((p["key"], p) for p in ov2.pandas)}
        self.root.update()
        self.assertEqual(before, {p["key"]: len(p["actions"]) for p in ov2.pandas})

    def test_second_window_reuses_the_prepared_images(self) -> None:
        from app.standby import PREPARED_IMAGES, _FITTED_WALLPAPERS
        PREPARED_IMAGES.clear()
        _FITTED_WALLPAPERS.clear()
        first = self._overlay(scene=self.wall.key, wallpapers=[self.wall])
        if first._library.registry is None:
            self.skipTest("registry missing")
        hits, misses, fitted = PREPARED_IMAGES.hits, PREPARED_IMAGES.misses, dict(_FITTED_WALLPAPERS)
        # An exact desktop action can be an input to a prepared member. Reopening
        # standby needs the complete member, not that intermediate action again.
        standby_entries = {key for key in PREPARED_IMAGES._items if key[0] in ("member", "action")}
        self.assertGreater(misses, 0)
        self.assertEqual(len(fitted), 1)
        first.dismiss()
        self.root.update()
        self.assertFalse(first.running)

        with mock.patch.object(PREPARED_IMAGES, "get", wraps=PREPARED_IMAGES.get) as get_prepared:
            second = self._overlay(scene=self.wall.key, wallpapers=[self.wall])
        self.assertTrue(standby_entries)
        self.assertEqual({call.args[0] for call in get_prepared.call_args_list}, standby_entries)
        self.assertGreaterEqual(PREPARED_IMAGES.hits - hits, len(standby_entries))
        self.assertEqual(PREPARED_IMAGES.misses, misses)
        self.assertEqual(list(_FITTED_WALLPAPERS), list(fitted))       # the fitted wallpaper is reused
        self.assertIs(_FITTED_WALLPAPERS[next(iter(fitted))], next(iter(fitted.values())))
        # Fresh PhotoImages on the new window: drawing them must not hit a dead master.
        for p in second.pandas:
            second.canvas.itemconfigure(p["img_item"], image=p["walk"][0])
            for info in p["actions"].values():
                second.canvas.itemconfigure(p["img_item"], image=info["frames"][0])
        photo = second._wallpaper_cache[self.wall.key]
        second.canvas.create_image(0, 0, anchor="nw", image=photo)
        self.root.update()

    def test_lunar_ny_lantern_mid_autumn_and_jan1_standby_pauses_and_revert(self) -> None:
        for active_ymd, after_ymd, expected in (
            ((2027, 1, 1), (2027, 1, 2), "festival_new_year"),
            ((2027, 2, 6), (2027, 2, 8), "festival_lunar_ny"),
            ((2027, 2, 20), (2027, 2, 21), "festival_lantern"),
            ((2027, 9, 15), (2027, 9, 16), "festival_mid_autumn"),
        ):
            with self.subTest(expected=expected):
                ov = self._overlay(scene="starfield", wallpapers=(), today=dt.date(*active_ymd))
                if ov._library.registry is None:
                    self.skipTest("registry missing")
                ov.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
                ov._start_pause()
                self.assertEqual(ov.pause_plan, {p["key"]: expected for p in ov.pandas})
                ov.today = dt.date(*after_ymd)
                ov._start_pause()
                self.assertNotIn(expected, set(ov.pause_plan.values()))

        # Jan 1 with approved art uses festival_new_year, and without approved art never uses Lunar NY hanbok
        ov_ny = self._overlay(scene="starfield", wallpapers=(), today=dt.date(2027, 1, 1))
        ov_ny.finish_action_loading()
        for p in ov_ny.pandas:
            p.get("actions", {}).pop("festival_new_year", None)
        ov_ny.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        with mock.patch.object(ov_ny, "_load_festival_action", return_value=None):
            ov_ny._start_pause()
        self.assertNotIn("festival_lunar_ny", set(ov_ny.pause_plan.values()))
        self.assertNotIn("festival_new_year", set(ov_ny.pause_plan.values()))

        # Live midnight rollover via update_clock() (today=None, _today_fixed=False) enters and exits Lunar NY
        class _FakeDT(dt.datetime):
            current = dt.datetime(2027, 2, 4, 23, 59, 59)
            @classmethod
            def now(cls, tz=None):
                return cls.current
        ov_live = self._overlay(scene="starfield", wallpapers=(), today=None)
        ov_live._after_id = "cancel-clock"  # prevent reschedule loop during direct test call
        ov_live.win.after = lambda *_a, **_k: "timer"
        ov_live.rng = mock.Mock(random=mock.Mock(return_value=0.0), choice=lambda seq: seq[0])
        with mock.patch("app.standby.datetime.datetime", _FakeDT):
            _FakeDT.current = dt.datetime(2027, 2, 4, 23, 59, 59)
            ov_live.update_clock()
            ov_live._start_pause()
            self.assertNotIn("festival_lunar_ny", set(ov_live.pause_plan.values()))

            _FakeDT.current = dt.datetime(2027, 2, 5, 0, 0, 2)
            ov_live.update_clock()
            ov_live._start_pause()
            self.assertEqual(ov_live.pause_plan, {p["key"]: "festival_lunar_ny" for p in ov_live.pandas})

            _FakeDT.current = dt.datetime(2027, 2, 8, 0, 0, 2)
            ov_live.update_clock()
            ov_live._start_pause()
            self.assertNotIn("festival_lunar_ny", set(ov_live.pause_plan.values()))


class DomeBaseballBubbleSteadyTest(unittest.TestCase):
    """Real baseball stage: the banner keeps one bottom edge through the cheer, at 96 and 192 DPI."""

    def test_banner_bottom_holds_still_across_frames_and_skips_repeat_updates(self) -> None:
        from app import dome_stage
        from app.standby import _union_alpha_bbox

        wallpapers = load_wallpapers(resource_dir())
        if not any(w.key == "bg_standby_dome_baseball" for w in wallpapers):
            self.fail("approved Taipei Dome wallpaper missing")
        starts = [0.0]
        for _idx, dur, _scale in dome_stage.DOME_BASEBALL_TIMELINE[:-1]:
            starts.append(starts[-1] + dur)
        for scaling in (96 / 72, 192 / 72):
            with self.subTest(dpi=round(scaling * 72)):
                root = tk.Tk()
                root.withdraw()
                root.tk.call("tk", "scaling", scaling)
                try:
                    with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
                        ov = PandaStandbyOverlay(root, "eunji", "Eunji", {}, [], scene="bg_standby_dome_baseball",
                                                 lang="zh_TW", wallpapers=wallpapers, lock_on_exit=False)
                    for seq in ("<Motion>", "<ButtonPress>", "<Key>"):
                        ov.win.unbind(seq)
                    ov.finish_action_loading()
                    ov._cancel_all_timers()
                    bottoms, tops = set(), []
                    now = time.monotonic()
                    for start in starts:
                        ov._dome_state["t0"] = now - (start + 100) / 1000.0
                        ov._animate_dome_scene(reschedule=False)
                        bubble = ov.canvas.bbox(ov.canvas.find_withtag("dome_bubble")[0])
                        bottoms.add(bubble[3])
                        for p in ov.pandas:
                            info = p["actions"][dome_stage.DOME_BASEBALL_ACTION]
                            union = _union_alpha_bbox(info)
                            x, y = (int(v) for v in ov.canvas.coords(p["img_item"]))
                            tops.append((y + union[1], bubble[3]))
                    self.assertEqual(len(bottoms), 1, f"banner bottom moved between frames: {sorted(bottoms)}")
                    self.assertTrue(all(b <= top for top, b in tops), tops)   # never over a head
                    with mock.patch.object(ov.canvas, "coords", wraps=ov.canvas.coords) as coords:
                        ov._animate_dome_scene(reschedule=False)        # same frame, same window
                        self.assertEqual(coords.call_count, 0)
                    ov.handle_exit()
                finally:
                    root.destroy()


if __name__ == "__main__":
    unittest.main()
