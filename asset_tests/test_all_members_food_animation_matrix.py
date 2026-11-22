"""Unit test matrix verifying all 5 Apink members x 56 foods for animation & prop accuracy."""
import unittest
from unittest import mock
import tempfile
from pathlib import Path

from app.foods import FOOD_ITEMS, get_feed_animation
from app.daily_actions import FOOD_MEMBER_ANIMATIONS, EAT_REACTION, DRINK_REACTION
from app.main import PandaPet
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService


class AllMembersFoodAnimationMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        PersistenceService(Path(self.tmp.name)).save(
            dict(DEFAULT_SETTINGS, mode="manual", manual_character="bomi", onboarding_prompted=True),
            dict(DEFAULT_RUNTIME),
        )
        self.pet = PandaPet(data_dir=Path(self.tmp.name))
        self.addCleanup(self.pet.close)

    def test_generic_fallback_tables_are_strictly_empty(self) -> None:
        """Generic fallback tables must be empty so no member holds mismatched props."""
        self.assertEqual(EAT_REACTION, {})
        self.assertEqual(DRINK_REACTION, {})

    def test_eomuk_tang_never_shows_ramen_or_mango_ice_across_all_five_members(self) -> None:
        """User explicit bug report: Bomi eating fishcake soup showing ramen, Namjoo showing mango ice."""
        for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
            with self.subTest(member=member):
                self.pet.char_key = member
                self.pet.satiety = 20.0
                active = self.pet.coord.snapshot().active
                if active:
                    self.pet.coord.cancel(active.event_id)

                with mock.patch.object(self.pet, "trigger_cheer") as mock_cheer:
                    self.pet.feed("eomuk_tang")
                    # Each member now has her own fish cake soup (drawn 2026-11-10): no ramen, no mango ice
                    self.assertEqual(self.pet.coord.action, "feed_eomuk_tang")
                    mock_cheer.assert_not_called()

    def test_namjoo_smoothie_boba_separation(self) -> None:
        """User equates mango smoothie with mango ice; strawberry boba remains distinct."""
        self.pet.char_key = "namjoo"
        for food in ("tw_strawberry_boba",):
            with self.subTest(food=food):
                self.pet.satiety = 20.0
                active = self.pet.coord.snapshot().active
                if active:
                    self.pet.coord.cancel(active.event_id)
                exact = self.pet._action_frames("namjoo", f"feed_{food}")
                with mock.patch.object(self.pet, "trigger_cheer") as cheer:
                    self.pet.feed(food)
                    if exact is None:
                        cheer.assert_called_once()
                        self.assertNotIn(self.pet.coord.action,
                                         ("actions_v7/namjoo_mukbang_ready",
                                          "situational_v6_2/namjoo_gourmet_taster"))
                    else:
                        self.assertEqual(self.pet.coord.action, f"feed_{food}")
                        cheer.assert_not_called()

        # Mango smoothie/ice share art by the user's explicit naming convention.
        for food, expected in (("tw_brown_sugar_boba", "situational_v6_2/namjoo_gourmet_taster"),
                               ("tw_mango_shaved_ice", "actions_v7/namjoo_mukbang_ready"),
                               ("tw_mango_smoothie", "actions_v7/namjoo_mukbang_ready")):
            self.pet.satiety = 20.0
            active = self.pet.coord.snapshot().active
            if active:
                self.pet.coord.cancel(active.event_id)
            exact = self.pet._action_frames("namjoo", f"feed_{food}")
            self.pet.feed(food)
            self.assertEqual(self.pet.coord.action, f"feed_{food}" if exact else expected)

    def test_all_280_combinations_have_clean_resolutions(self) -> None:
        """All 5 members x 56 foods must either resolve to exact matching prop or cheer happily."""
        forbidden_ramen_for_non_noodle = {"interaction_eat", "situational_v6_3/bomi_ramen_slurp", "situational_v6/eunji_cap_slurp_ramen_pot"}
        forbidden_tea_for_non_tea = {"special_v6_1/chorong_sp_tea_sip", "situational_v6_3/hayoung_warm_tea_cozy"}
        noodle_foods = {"budae_jjigae", "tw_beef_noodle", "buldak", "jajangmyeon", "malatang"}
        tea_foods = {"tw_oolong_tea"}

        for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
            for food in FOOD_ITEMS:
                fid = food["id"]
                with self.subTest(member=member, food=fid):
                    self.pet.char_key = member
                    self.pet.satiety = 20.0
                    active = self.pet.coord.snapshot().active
                    if active:
                        self.pet.coord.cancel(active.event_id)

                    with mock.patch.object(self.pet, "trigger_cheer") as mock_cheer:
                        self.pet.feed(fid)
                        action = self.pet.coord.action
                        
                        # If cheer was triggered, no wrong prop was scheduled
                        if mock_cheer.called:
                            continue

                        # If an action was played, ensure non-noodles never played ramen
                        if fid not in noodle_foods:
                            self.assertNotIn(action, forbidden_ramen_for_non_noodle, f"{member} eating {fid} played ramen!")
                        # Ensure non-tea never played hot teacup
                        if fid not in tea_foods:
                            self.assertNotIn(action, forbidden_tea_for_non_tea, f"{member} drinking {fid} played teacup!")


if __name__ == "__main__":
    unittest.main()
