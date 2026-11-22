"""2026-11-22: Eunji's dome solo concert showed a white/gray fringe the desktop pet never has.

The standby overlay built its SpriteLibrary with the defaults (binary alpha, no edge
refine), so every member on the dark stage wallpapers was a hard 0/255 cutout with the
light matte ring left on. Standby now uses the desktop pet's soft-alpha + edge-refine
pipeline, and the warmup prepares frames under the same cache key.
"""
from __future__ import annotations

import gc
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import standby  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402
from app.standby import PandaStandbyOverlay, load_wallpapers  # noqa: E402


class StandbySoftEdgeTests(unittest.TestCase):
    def test_standby_and_its_warmup_share_the_soft_edge_pipeline(self) -> None:
        self.assertFalse(standby.STANDBY_BINARY_ALPHA)
        self.assertTrue(standby.STANDBY_EDGE_REFINE)
        # A Tk root left by an earlier test must not be collected on the warmup thread
        # (Tcl_AsyncDelete aborts the process).
        gc.collect()
        seen = []
        real = standby.SpriteLibrary

        def spy(*args, **kwargs):
            lib = real(*args, **kwargs)
            seen.append((lib.binary_alpha, lib.edge_refine))
            return lib

        with patch("app.standby.SpriteLibrary", side_effect=spy), \
                patch("app.standby._prepare_member_pil", return_value=None):
            warm = standby.StandbyWarmupManager()
            warm.schedule(ROOT, 160, 1920, 1080, active_scene="starfield")
            warm.wait(30)
            warm.cancel()
        self.assertIn((False, True), seen)
        self.assertNotIn((True, False), seen)

    def test_dome_solo_members_have_anti_aliased_edges(self) -> None:
        root = tk.Tk()
        root.withdraw()
        overlay = None
        try:
            with (
                patch("ctypes.windll.user32.LockWorkStation", create=True),
                patch("app.standby.PandaStandbyOverlay._watch_real_lock"),
            ):
                overlay = PandaStandbyOverlay(
                    parent=root, char_key="eunji", char_name="Eunji", frames={},
                    flipped_walk_frames=[], lock_on_exit=False,
                    scene="bg_standby_eunji_dome_dream", wallpapers=load_wallpapers(ROOT),
                    bounds=WorkArea(0, 0, 1920, 1080),
                )
                self.assertFalse(overlay._library.binary_alpha)
                self.assertTrue(overlay._library.edge_refine)
                eunji = next(p for p in overlay.pandas if p["key"] == "eunji")
                overlay.finish_action_loading()
                self.assertTrue(eunji["actions"])
                for name, info in eunji["actions"].items():
                    im = info["frames"].pil[0]
                    alpha = im.getchannel("A").histogram()
                    soft = sum(alpha[1:255])
                    self.assertGreater(soft, 200, f"{name}: hard 0/255 cutout keeps the matte fringe")
        finally:
            if overlay is not None and overlay.running:
                overlay.handle_exit()
            try:
                root.destroy()
            except tk.TclError:
                pass
            del root, overlay
            gc.collect()


if __name__ == "__main__":
    unittest.main()
