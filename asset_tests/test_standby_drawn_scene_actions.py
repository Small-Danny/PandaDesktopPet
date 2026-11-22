"""The starfield / campfire / practice-room moves play in their own parade scene only.

Registered 2026-11-13 with the plain desktop_action tag (no context tag); the standby
loader adds them from SCENE_ACTIONS as the scene's extras. Loading and the parade stop
are covered by tests/test_standby_wallpapers.py (OverlayTest).

Run:  python -m unittest tests.test_standby_drawn_scene_actions -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.daily_actions import SCENE_ACTIONS  # noqa: E402
from app.paths import resource_dir  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import SCENES, scene_fits  # noqa: E402

MEMBERS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")
DRAWN = {"starfield": "scene_starfield", "campfire": "scene_campfire", "practice_room": "scene_practice_room"}


class SceneTableTest(unittest.TestCase):
    def test_keys_are_the_real_parade_scenes(self) -> None:
        for scene, action in DRAWN.items():
            self.assertIn(scene, SCENES)
            self.assertEqual(SCENE_ACTIONS[scene], {m: (action,) for m in MEMBERS})

    def test_each_move_fits_only_its_own_scene(self) -> None:
        others = [s for s in (*SCENES, *SCENE_ACTIONS) if s]
        for scene, action in DRAWN.items():
            for member in MEMBERS:
                with self.subTest(scene=scene, member=member):
                    self.assertTrue(scene_fits(action, ("desktop_action",), member, scene))
                    for other in others:
                        if other != scene:
                            self.assertFalse(scene_fits(action, ("desktop_action",), member, other), other)

    def test_registered_exactly_without_a_context_tag(self) -> None:
        registry = SpriteLibrary(resource_dir()).registry
        if registry is None:
            self.skipTest("registry missing")
        for action in DRAWN.values():
            for member in MEMBERS:
                with self.subTest(action=action, member=member):
                    spec = registry.resolve(member, action)
                    self.assertIsNotNone(spec)
                    self.assertEqual(spec.action, action)          # not a fallback
                    self.assertIn("desktop_action", spec.tags)
                    self.assertFalse([t for t in spec.tags if t.startswith("context:")])


if __name__ == "__main__":
    unittest.main()
