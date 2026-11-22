"""Food identity regression: wrong bowl/cup props must not substitute another dish.

Exercises the real feed selection and reaction dispatch with an in-memory actor.
No Tk window, persisted settings, or source-art inference is involved.
"""
from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.daily_actions import FOOD_MEMBER_ANIMATIONS
from app.main import PandaPet


class FoodActor:
    def __init__(self, available):
        self.available = set(available)
        self.char_key, self.lang = "namjoo", "zh_TW"
        self.runtime, self.feed_count = {}, 0
        self.requested = []
        self.cheers = []
        self.coord = SimpleNamespace(submit=self.submit)

    def submit(self, request):
        self.requested.append(request.action)
        return SimpleNamespace(accepted=True)

    def record_activity(self):
        pass

    def _current_satiety(self):
        return 20.0

    def save_settings(self):
        return True

    def _action_frames(self, member, action):
        return ([object()], 180) if action in self.available else None

    def _play_reaction(self, *args, **kwargs):
        return PandaPet._play_reaction(self, *args, **kwargs)

    def trigger_cheer(self, **kwargs):
        self.cheers.append(kwargs)

    def _toast(self, *args, **kwargs):
        pass

    def _refresh_status_card(self):
        pass

    def _refresh_food_panel(self):
        pass


class FoodPropMappingTest(unittest.TestCase):
    def test_plain_boba_is_not_a_strawberry_boba_fallback(self):
        for food in ("tw_strawberry_boba",):
            with self.subTest(food=food):
                actor = FoodActor({"actions_v7/namjoo_mukbang_ready",
                                   "situational_v6_2/namjoo_gourmet_taster"})
                result = PandaPet.feed(actor, food)
                self.assertNotIn(("namjoo", food), FOOD_MEMBER_ANIMATIONS)
                self.assertEqual(actor.requested, [])
                self.assertEqual(len(actor.cheers), 1)
                self.assertEqual(actor.cheers[0]["kind"], "feed")
                self.assertTrue(result.saved)

    def test_future_exact_food_animation_still_has_first_priority(self):
        for food in ("tw_mango_smoothie", "tw_strawberry_boba"):
            with self.subTest(food=food):
                actor = FoodActor({"feed_" + food, "actions_v7/namjoo_mukbang_ready",
                                   "situational_v6_2/namjoo_gourmet_taster"})
                PandaPet.feed(actor, food)
                self.assertEqual(actor.requested, ["feed_" + food])
                self.assertEqual(actor.cheers, [])

    def test_visually_matching_shaved_ice_and_brown_pearl_drink_are_preserved(self):
        for food, action in (("tw_mango_smoothie", "actions_v7/namjoo_mukbang_ready"),
                             ("tw_mango_shaved_ice", "actions_v7/namjoo_mukbang_ready"),
                             ("tw_brown_sugar_boba", "situational_v6_2/namjoo_gourmet_taster")):
            with self.subTest(food=food):
                actor = FoodActor({action})
                PandaPet.feed(actor, food)
                self.assertEqual(actor.requested, [action])
                self.assertEqual(actor.cheers, [])


if __name__ == "__main__":
    unittest.main()
