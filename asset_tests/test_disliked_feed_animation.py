"""A disliked food plays her exact drawing of that food first, else she sulks.

The outcome, satiety, passion and food log of a disliked feed stay as before; only
the animation choice changes. Member aliases (FOOD_MEMBER_ANIMATIONS) are ordinary
eating poses and must never stand in for a refusal.

Run:  python -m unittest tests.test_disliked_feed_animation -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

import app.main as main  # noqa: E402
from app.main import SATIETY_KEY, PandaPet  # noqa: E402
from app.daily_actions import SULK_REACTION  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402

MEMBER, FOOD = "chorong", "stinky_tofu"    # every member dislikes stinky tofu
SULK = SULK_REACTION[MEMBER][0]
FRAMES, FRAME_MS = 4, 180                  # a real 4-frame sheet: one pass is 0.72 s
ONE_PASS_S = FRAMES * FRAME_MS / 1000.0


class DislikedFeedAnimationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        settings = dict(DEFAULT_SETTINGS, mode="manual", manual_character=MEMBER)
        runtime = dict(DEFAULT_RUNTIME, **{SATIETY_KEY: {MEMBER: 50.0}}, cheer_passion=7)
        PersistenceService(self.dir).save(settings, runtime)
        self.pet = PandaPet(data_dir=self.dir)
        self.addCleanup(self.pet.close)
        self.assertEqual(self.pet.char_key, MEMBER)
        self.assertIn(MEMBER, next(f for f in main.FOOD_ITEMS if f["id"] == FOOD)["disliked"])

    def _feed(self, drawn: set[str], aliases: dict | None = None):
        """Feed FOOD with only `drawn` actions available; return (result, tried, submitted)."""
        tried, submitted = [], []

        def frames(member, action):
            tried.append(action)
            return ([object()] * FRAMES, FRAME_MS, (0, 0)) if action in drawn else None

        def submit(req):
            submitted.append(req)
            return mock.Mock(accepted=True)

        with mock.patch.object(self.pet, "_action_frames", side_effect=frames), \
                mock.patch.object(self.pet.coord, "submit", side_effect=submit), \
                mock.patch.dict(main.FOOD_MEMBER_ANIMATIONS, aliases or {}):
            result = self.pet.feed(FOOD)
        return result, tried, submitted

    def _assert_disliked_contract(self, result) -> None:
        self.assertEqual(result.outcome, "disliked")
        self.assertAlmostEqual(self.pet.satiety, 55.0, delta=0.1)       # disliked: +5
        self.assertEqual(self.pet.runtime["cheer_passion"], 8)           # disliked: +1
        self.assertTrue(result.saved)
        saved = PersistenceService(self.dir).load()[1]
        self.assertEqual(saved["food_log"][MEMBER][FOOD]["outcome"], "disliked")
        self.assertAlmostEqual(saved[SATIETY_KEY][MEMBER], 55.0, delta=0.1)

    def test_exact_drawing_plays_first(self) -> None:
        result, tried, submitted = self._feed({f"feed_{FOOD}", SULK})
        self.assertEqual(tried[0], f"feed_{FOOD}")
        self.assertEqual([r.action for r in submitted], [f"feed_{FOOD}"])
        self._assert_disliked_contract(result)

    def test_without_an_exact_drawing_she_sulks(self) -> None:
        result, tried, submitted = self._feed({SULK})
        self.assertEqual(tried, [f"feed_{FOOD}", SULK])
        self.assertEqual([r.action for r in submitted], [SULK])
        self._assert_disliked_contract(result)

    def test_member_alias_never_replaces_the_refusal(self) -> None:
        alias = "situational_v6_2/some_happy_eating_pose"
        result, tried, submitted = self._feed({alias, SULK}, aliases={(MEMBER, FOOD): (alias,)})
        self.assertNotIn(alias, tried)
        self.assertEqual([r.action for r in submitted], [SULK])
        self._assert_disliked_contract(result)

    def test_disliked_still_wins_over_a_full_stomach(self) -> None:
        self.pet.satiety = 100.0
        result, _, submitted = self._feed({f"feed_{FOOD}", SULK})
        self.assertEqual(result.outcome, "disliked")                   # not refused_full
        self.assertEqual([r.action for r in submitted], [f"feed_{FOOD}"])

    def test_exact_refusal_plays_the_full_reaction_time(self) -> None:
        _, _, submitted = self._feed({f"feed_{FOOD}", SULK})
        expected = self.pet._action_duration_s([object()] * FRAMES, FRAME_MS)
        self.assertGreater(expected, ONE_PASS_S)             # whole passes, not one flash
        self.assertAlmostEqual(submitted[0].duration_s, expected)

    def test_sulk_fallback_stays_a_single_pass(self) -> None:
        _, _, submitted = self._feed({SULK})
        self.assertAlmostEqual(submitted[0].duration_s, ONE_PASS_S)


if __name__ == "__main__":
    unittest.main()
