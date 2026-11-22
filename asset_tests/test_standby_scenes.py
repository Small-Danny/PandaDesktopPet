"""Standby overlay scenes: render each scene, switch scenes, exit exactly once.

Needs a real Tk display. Run:  python tests/test_standby_scenes.py
Screenshots go to work/evidence/c5/standby_<scene>.png
"""
from __future__ import annotations

import datetime as dt
import random
import sys
import time
import tkinter as tk
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.paths import resource_dir  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import SCENES, PandaStandbyOverlay, pick_default_scene  # noqa: E402

EVIDENCE_DIR = ROOT / "work" / "evidence" / "c5"

# Match main.py: the real app is per-monitor DPI aware, so layout must be checked that way.
try:
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def _pump(root: tk.Tk, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


class _Env:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        sprites = SpriteLibrary(resource_dir()).load_member("chorong", self.root)
        self.frames = sprites.frames
        self.flipped = sprites.flipped("walk")
        self.closed = 0

    def on_close(self) -> None:
        self.closed += 1

    def make(self, scene: str | None, **kw) -> PandaStandbyOverlay:
        ov = self._make(scene, **kw)
        # Real mouse movement / clicks by someone at the PC must not make the test flaky.
        for win in [ov.win, *(cover["win"] for cover in ov.covers)]:
            win.unbind("<Motion>")
            win.unbind("<ButtonPress>")
        return ov

    def _make(self, scene: str | None, **kw) -> PandaStandbyOverlay:
        return PandaStandbyOverlay(
            parent=self.root,
            char_key="chorong",
            char_name="初瓏 (Chorong)",
            frames=self.frames,
            flipped_walk_frames=self.flipped,
            passion_points=2590,
            companion_minutes=42,
            on_close=self.on_close,
            lock_on_exit=False,
            show_panda_tags=kw.pop("show_panda_tags", False),
            wallpapers=kw.pop("wallpapers", ()),
            scene=scene,
            **kw,
        )


def _tk_errors(root: tk.Tk) -> list[str]:
    errors: list[str] = []
    root.report_callback_exception = lambda exc, val, tb: errors.append(f"{exc.__name__}: {val}")
    return errors


def test_pick_default_scene() -> None:
    assert pick_default_scene(dt.date(2026, 12, 3)) == "christmas"
    for day in range(1, 29):
        assert pick_default_scene(dt.date(2026, 6, day)) in SCENES
    assert pick_default_scene(dt.date(2026, 6, 5)) == pick_default_scene(dt.date(2026, 6, 5))
    assert pick_default_scene(dt.date(2026, 6, 5), random.Random(1)) in SCENES


def test_each_scene_renders_and_screenshots(save_screenshots: bool = True) -> None:
    from PIL import ImageGrab

    env = _Env()
    errors = _tk_errors(env.root)
    try:
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock:
            for scene in SCENES:
                env.closed = 0
                ov = env.make(scene, show_panda_tags=True)
                assert ov.scene == scene
                # Tag colour of Hayoung must be lemon yellow, not green.
                hy = next(p for p in ov.pandas if p["key"] == "hayoung")
                assert hy["color"].lower() == "#fff176", hy["color"]
                _pump(env.root, 1.5)
                assert ov.running and env.closed == 0
                if save_screenshots:
                    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
                    img = ImageGrab.grab(all_screens=True)
                    if img.width > 1280:
                        img = img.resize((1280, round(img.height * 1280 / img.width)))
                    img.save(EVIDENCE_DIR / f"standby_{scene}.png")
                ov.handle_exit(None)
                ov.handle_exit(None)  # idempotent
                assert env.closed == 1, env.closed
                _pump(env.root, 0.3)  # pending callbacks must not fire after destroy
            assert not lock.called
        assert not errors, errors
    finally:
        env.root.destroy()


def test_scene_switching_keeps_overlay_open() -> None:
    env = _Env()
    errors = _tk_errors(env.root)
    try:
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock:
            ov = env.make(None)
            assert ov.scene in SCENES
            _pump(env.root, 0.3)

            # set_scene for every scene
            for scene in SCENES:
                ov.set_scene(scene)
                _pump(env.root, 0.25)
                assert ov.scene == scene and ov.running and env.closed == 0
            try:
                ov.set_scene("nope")
                raise AssertionError("unknown scene must raise")
            except ValueError:
                pass

            # Simulated arrow keys cycle scenes without closing
            ov.set_scene("starfield")
            ov.win.focus_force()
            _pump(env.root, 0.2)
            ov.win.event_generate("<KeyPress-Right>", keysym="Right")
            _pump(env.root, 0.2)
            if ov.scene == "starfield":  # focus not granted by the WM: deliver directly
                ov.handle_key(_FakeKey("Right"))
            assert ov.scene == "campfire", ov.scene
            ov.handle_key(_FakeKey("Left"))
            ov.handle_key(_FakeKey("Left"))
            assert ov.scene == "practice_room", ov.scene
            ov.handle_key(_FakeKey("Right"))
            assert ov.scene == "starfield"
            ov.p_cheer_ticks = 6  # parade stops for a cheer, then walks on
            px = ov.px
            _pump(env.root, 0.4)
            assert ov.px == px and all(p["cheer"] for p in ov.pandas)
            deadline = time.monotonic() + 6.0
            while ov.p_cheer_ticks and ov.px == px and time.monotonic() < deadline:
                _pump(env.root, 0.05)
            assert ov.p_cheer_ticks == 0 or ov.px != px
            assert ov.running and env.closed == 0

            # Any other key exits and calls on_close exactly once
            ov.handle_key(_FakeKey("a"))
            assert not ov.running and env.closed == 1
            ov.handle_exit(None)
            assert env.closed == 1
            _pump(env.root, 0.3)

            # handle_exit(None) path
            ov2 = env.make("christmas")
            _pump(env.root, 0.3)
            ov2.handle_exit(None)
            assert env.closed == 2
            _pump(env.root, 0.3)
            assert not lock.called
        assert not errors, errors
    finally:
        env.root.destroy()


def test_overlay_uses_given_monitor_bounds() -> None:
    """Standby covers the pet's monitor when main passes its bounds."""
    from app.platform.win32 import WorkArea

    env = _Env()
    errors = _tk_errors(env.root)
    try:
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            ov = env.make("starfield", bounds=WorkArea(40, 30, 1320, 750))
            _pump(env.root, 0.4)
            assert (ov.sw, ov.sh) == (1280, 720), (ov.sw, ov.sh)
            assert (ov.win.winfo_rootx(), ov.win.winfo_rooty()) == (40, 30)
            assert ov.cx == 640 and ov.card_w <= 1280
            ov.handle_exit(None)
            _pump(env.root, 0.2)
        assert not errors, errors
    finally:
        env.root.destroy()


class _FakeKey:
    def __init__(self, keysym: str) -> None:
        self.keysym = keysym
        self.x = self.y = 0


if __name__ == "__main__":
    test_pick_default_scene()
    print("[PASS] pick_default_scene")
    test_scene_switching_keeps_overlay_open()
    print("[PASS] scene switching keeps overlay open; other key / handle_exit closes once")
    test_overlay_uses_given_monitor_bounds()
    print("[PASS] overlay sized/placed from given monitor bounds")
    test_each_scene_renders_and_screenshots()
    print(f"[PASS] all scenes rendered: {', '.join(SCENES)} -> {EVIDENCE_DIR}")
