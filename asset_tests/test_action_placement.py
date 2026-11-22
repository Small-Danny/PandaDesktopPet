"""Every approved large-canvas action stands where the pet stands.

A cut that leaves the figure lower on its canvas makes the pet sink while the action plays
(reported for chorong's tteokbokki / gopchang). This loads each registered action exactly as
the pet draws it (scale, feet offset, polish) and compares it with idle:
no frame may sink below idle's feet, the median frame keeps idle's centre, and food
animations (standing still with a bowl) must also keep idle's feet and head line.
Jumps and hops may rise. New batches are covered as soon as they are registered.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.action_frames import load_exact_action
from app.sprites import SpriteLibrary

MEMBERS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")
PET_SIZES = (192,)                # the medium pet; placement scales with the size
# A prop reaches below the feet (lantern tassel, a pot / steamer / plate on the floor, a
# bowl held low, the practice-room metronome); her feet themselves stay on idle's line.
# Each pair was checked by eye against idle's feet line (2026-11-13, 56/56 foods).
# Per member: the same food drawn standing with a bowl for someone else must not sink.
PROP_BELOW_FEET = {
    "festival_lantern": {"chorong", "bomi", "eunji", "namjoo", "hayoung"},
    "feed_kr_kotdoritang": {"chorong"},              # pot on the floor beside her
    "feed_tw_beef_noodle": {"chorong", "hayoung"},   # low bowl; Hayoung F1 bowl is below both feet
    "feed_tw_brown_sugar_mochi": {"chorong", "bomi", "eunji", "namjoo", "hayoung"},  # plate on the floor
    "feed_tw_mala_dual_hotpot": {"chorong", "bomi", "namjoo", "hayoung"},  # stove / pot in front, seated behind it
    "feed_tw_potstickers": {"bomi"},                 # plate on the floor
    "feed_tw_taro_ball_grass_jelly": {"chorong"},    # bowl held low in F3/F4
    "feed_tw_xiaolongbao": {"chorong", "eunji", "namjoo", "hayoung"},  # steamer on the floor
    "scene_beach": {"hayoung"},                      # shovel and sand bucket in front on sand
    "scene_practice_room": {"chorong"},              # metronome and notes at her feet
}


def _median(values: list[float]) -> float:
    return sorted(values)[len(values) // 2]


class ActionPlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.libraries = {px: SpriteLibrary(ROOT, display_px=px, equalize=True) for px in PET_SIZES}
        registry = cls.libraries[PET_SIZES[0]].registry
        if registry is None:
            raise unittest.SkipTest("no asset registry")
        cls.actions = sorted((member, action) for member in MEMBERS for action in registry.actions(member))

    def _boxes(self, lib: SpriteLibrary, member: str, action: str):
        loaded = load_exact_action(lib, member, action)
        if loaded is None or loaded.offset == (0, 0):
            return None                                 # not playable / drawn on the pet canvas
        dx, dy = loaded.offset
        boxes = []
        for frame in loaded.frames:
            l, t, r, b = frame.getchannel("A").getbbox()
            boxes.append((l + dx, t + dy, r + dx, b + dy))
        return boxes

    def test_large_actions_keep_the_idle_feet_and_centre(self) -> None:
        checked = 0
        for px, lib in self.libraries.items():
            tol = max(3, px // 48)
            for member in MEMBERS:
                idle = load_exact_action(lib, member, "idle").frames[0].getchannel("A").getbbox()
                idle_cx = (idle[0] + idle[2]) / 2
                for m, action in self.actions:
                    if m != member:
                        continue
                    boxes = self._boxes(lib, member, action)
                    if boxes is None:
                        continue
                    checked += 1
                    bottoms = [b[3] - idle[3] for b in boxes]
                    centres = [(b[0] + b[2]) / 2 - idle_cx for b in boxes]
                    tops = [b[1] - idle[1] for b in boxes]
                    prop = member in PROP_BELOW_FEET.get(action, ())
                    with self.subTest(px=px, member=member, action=action, bottoms=bottoms, tops=tops):
                        if prop:
                            # The prop may reach down, but not so far that the whole figure sank
                            # with it or the canvas cut it (measured: at most 32 at 192 px).
                            self.assertLessEqual(max(bottoms), px * 3 // 16, "prop drops off the canvas")
                        else:
                            self.assertLessEqual(max(bottoms), tol, "sinks below idle's feet")
                        self.assertLessEqual(abs(_median(centres)), px / 8, "drifts sideways")
                        if action.startswith("feed_"):
                            if not prop:
                                self.assertLessEqual(abs(_median(bottoms)), tol, "feet off idle's line")
                            # Head line, median frame. Eating poses rise above idle's ears (raised
                            # paw, steam, a cap, a recoil from stinky tofu: measured up to 28 px at
                            # 192) and chorong's shorter-legged eating poses sit lower with the same
                            # head width (up to 16). A sunk figure or a wrongly scaled sheet falls
                            # outside these; this also keeps the prop actions' feet on the line.
                            self.assertGreaterEqual(_median(tops), -(px // 6), "taller than idle's size")
                            self.assertLessEqual(_median(tops), px // 10, "shorter than idle's size / sunk")
        self.assertGreater(checked, 100)


if __name__ == "__main__":
    unittest.main()
