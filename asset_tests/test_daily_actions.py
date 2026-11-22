"""Daily signature moves and the festival extras layered on top of them."""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp())

from app.action_frames import available_actions, load_exact_action  # noqa: E402
from app.engine.coordinator import ActorState, EventRequest, Priority  # noqa: E402
from app.daily_actions import (  # noqa: E402
    DRINK_REACTION, EAT_REACTION, LUNAR_NEW_YEAR, MID_AUTUMN, NATURAL_ANIMATIONS, NATURAL_POSES, RARE_POSES, SCENE_ACTIONS,
    SIGNATURE_INTERVAL_S, SIGNATURE_POOL, TAP_REACTION, festival_on, pick_natural, pick_signature,
)
from app.main import RES_ROOT, PandaPet  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import SCENES as STANDBY_SCENES, scene_fits  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402

KNOWN_NEW_MOON = dt.datetime(2000, 1, 6, 18, 14)
SYNODIC_DAYS = 29.530588


def lunar_phase_days(day: dt.date) -> float:
    """Days since the last mean new moon."""
    return ((dt.datetime(day.year, day.month, day.day, 12) - KNOWN_NEW_MOON).total_seconds() / 86400) % SYNODIC_DAYS


class CalendarTableTest(unittest.TestCase):
    def test_new_years_fall_on_a_new_moon(self) -> None:
        for year, md in LUNAR_NEW_YEAR.items():
            phase = lunar_phase_days(dt.date(year, *md))
            self.assertLess(min(phase, SYNODIC_DAYS - phase), 2.0, year)

    def test_mid_autumns_fall_on_a_full_moon(self) -> None:
        for year, md in MID_AUTUMN.items():
            self.assertLess(abs(lunar_phase_days(dt.date(year, *md)) - SYNODIC_DAYS / 2), 2.0, year)

    def test_festival_windows(self) -> None:
        cases = {
            (2026, 11, 8): None, (2026, 12, 23): None, (2026, 12, 24): "christmas", (2026, 12, 25): "christmas",
            (2026, 12, 26): None, (2027, 2, 4): None, (2027, 2, 5): "lunar_ny", (2027, 2, 6): "lunar_ny",
            (2027, 2, 7): "lunar_ny", (2027, 2, 8): None, (2027, 2, 20): "lantern", (2027, 9, 15): "mid_autumn",
            (2027, 9, 16): None, (2027, 4, 19): None,
        }
        for ymd, key in cases.items():
            festival = festival_on(dt.date(*ymd))
            self.assertEqual(festival.key if festival else None, key, ymd)


class PoolTest(unittest.TestCase):
    def test_every_listed_move_is_approved_and_loads(self) -> None:
        lib = SpriteLibrary(RES_ROOT)
        for member, pool in SIGNATURE_POOL.items():
            self.assertEqual(available_actions(lib, member, pool), pool, member)
            for action in pool:
                self.assertIsNotNone(load_exact_action(lib, member, action), f"{member}.{action}")

    def test_festival_actions_load_for_everyone(self) -> None:
        lib = SpriteLibrary(RES_ROOT)
        for member in SIGNATURE_POOL:
            for action in ("festival_new_year", "festival_christmas", "festival_lunar_ny", "festival_lantern", "festival_mid_autumn"):
                self.assertIsNotNone(load_exact_action(lib, member, action), f"{member}.{action}")

    def test_every_daily_entry_is_playable(self) -> None:
        lib = SpriteLibrary(RES_ROOT)
        tables = (NATURAL_ANIMATIONS, NATURAL_POSES, RARE_POSES, TAP_REACTION, EAT_REACTION, DRINK_REACTION, *SCENE_ACTIONS.values())
        for table in tables:
            for member, actions in table.items():
                for action in actions:
                    self.assertIsNotNone(load_exact_action(lib, member, action), f"{member}.{action}")

    def test_musical_stage_has_the_redrawn_eunji_and_a_curtain_call_for_all(self) -> None:
        from app.engine.assets import AssetRegistry
        registry = AssetRegistry(RES_ROOT / "work/asset_registry.json", RES_ROOT)
        # Her first step/pose had Namjoo's face; the user redrew both (2026-11-10).
        for action in ("musical_step", "musical_pose"):
            self.assertTrue(all("/v2/" in f for f in registry.resolve("eunji", action).frames), action)
        lib = SpriteLibrary(RES_ROOT)
        self.assertIn("musical_step", SCENE_ACTIONS["bg_standby_musical_theater"]["namjoo"])
        for member, actions in SCENE_ACTIONS["bg_standby_musical_theater"].items():
            self.assertIn("musical_bow", actions, member)
            self.assertEqual(len(load_exact_action(lib, member, "musical_bow").frames), 4, member)

    def test_new_foods_and_scene_moves_are_drawn_for_all_five(self) -> None:
        """reference/最後動圖/補圖 (2026-11-10): each food plays its own feed_ animation first."""
        lib = SpriteLibrary(RES_ROOT)
        for member in SIGNATURE_POOL:
            for action in ("feed_matcha_cake", "feed_jajangmyeon", "feed_eomuk_tang", "christmas_gift", "winter_cocoa"):
                self.assertEqual(len(load_exact_action(lib, member, action).frames), 4, f"{member}.{action}")
        drawn = {
            "bg_standby_autumn_cafe": tuple(SIGNATURE_POOL),
            "bg_standby_moonlight_terrace": tuple(SIGNATURE_POOL),
            "bg_standby_spring_picnic": tuple(SIGNATURE_POOL),
            "bg_standby_summer_beach": ("chorong", "bomi", "eunji", "hayoung"),
        }
        others = [s for s in (*STANDBY_SCENES, *SCENE_ACTIONS) if s]
        for scene, members in drawn.items():
            action = {"bg_standby_autumn_cafe": "scene_cafe", "bg_standby_moonlight_terrace": "scene_moonlight",
                      "bg_standby_summer_beach": "scene_beach", "bg_standby_spring_picnic": "scene_picnic"}[scene]
            for member in members:
                self.assertIn(action, SCENE_ACTIONS[scene][member], f"{scene} {member}")
                self.assertEqual(len(load_exact_action(lib, member, action).frames), 4, f"{member}.{action}")
                self.assertTrue(scene_fits(action, ("desktop_action",), member, scene), f"{scene} {member}")
                for other in others:
                    if other != scene:
                        self.assertFalse(scene_fits(action, ("desktop_action",), member, other), f"{member}.{action} leaked into {other}")
        self.assertIn("scene_flamingo", SCENE_ACTIONS["bg_standby_summer_beach"]["namjoo"])

    def test_natural_pick_avoids_the_last_action(self) -> None:
        for _ in range(60):
            self.assertNotEqual(pick_natural(("a", "b"), ("c", "d"), ("e", "f"), "a"), "a")

    def test_eunji_daily_yawn_stretch_is_approved_and_alongside_daily_yawn(self) -> None:
        import json
        from app.engine.assets import AssetRegistry
        self.assertIn("daily_yawn", NATURAL_ANIMATIONS["eunji"])
        self.assertIn("daily_yawn_stretch", NATURAL_ANIMATIONS["eunji"])
        policy = json.loads((RES_ROOT / "work/asset_review_policy.json").read_text("utf-8-sig"))
        registry = AssetRegistry(RES_ROOT / "work/asset_registry.json", RES_ROOT)
        spec = registry.resolve("eunji", "daily_yawn_stretch")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.action, "daily_yawn_stretch")
        self.assertEqual(len(spec.frames), 4)
        for frame_path in spec.frames:
            rel = frame_path.removeprefix("work/characters/")
            self.assertIn(rel, policy["approved"])
            self.assertIn(rel, policy["preserve_canvas"])
        lib = SpriteLibrary(RES_ROOT)
        loaded = load_exact_action(lib, "eunji", "daily_yawn_stretch")
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.frames), 4)

    def test_interaction_only_reactions_stay_out_of_the_random_pool(self) -> None:
        for member, actions in {**EAT_REACTION}.items():
            self.assertFalse(set(actions) & set(NATURAL_ANIMATIONS[member]))
        self.assertNotIn("interaction_eat", NATURAL_POSES["bomi"])

    def test_never_repeats_the_last_move(self) -> None:
        pool = SIGNATURE_POOL["chorong"]
        for _ in range(50):
            self.assertNotEqual(pick_signature(pool, pool[0]), pool[0])
        self.assertEqual(pick_signature(("only",), "only"), "only")
        self.assertIsNone(pick_signature((), None))


class PetTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        PersistenceService(Path(tmp.name)).save(
            dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong", onboarding_prompted=True),
            dict(DEFAULT_RUNTIME))
        self.pet = PandaPet(data_dir=Path(tmp.name))
        self.addCleanup(self.pet.close)
        self.pet.speech.hold(True)
        self.submit = mock.patch.object(self.pet.coord, "submit", wraps=self.pet.coord.submit)
        self.spy = self.submit.start()
        self.addCleanup(self.submit.stop)
        for target, kwargs in ((self.pet.window, {"winfo_viewable": True}),):
            patcher = mock.patch.multiple(target, **{k: mock.Mock(return_value=v) for k, v in kwargs.items()})
            patcher.start()
            self.addCleanup(patcher.stop)
        idle = mock.patch("app.main.get_system_idle_seconds", return_value=0)
        idle.start()
        self.addCleanup(idle.stop)
        self.pet.last_user_activity = 0
        self.pet.next_roam_time = float("inf")

    def on(self, *ymd: int) -> None:
        self.pet.calendar.clock.now = lambda: dt.datetime(*ymd, 12, 0)

    def kinds(self) -> list[str]:
        return [call.args[0].kind for call in self.spy.call_args_list]

    def test_signature_fires_on_an_ordinary_day(self) -> None:
        self.on(2026, 11, 8)
        self.pet.next_signature_at = 0
        self.pet.check_roam_ai()
        req = self.spy.call_args.args[0]
        self.assertEqual((req.kind, req.priority), ("daily.signature", Priority.SPONTANEOUS))
        self.assertIn(req.action, SIGNATURE_POOL["chorong"])
        wait = self.pet.next_signature_at - time.time()
        self.assertTrue(SIGNATURE_INTERVAL_S[0] - 5 <= wait <= SIGNATURE_INTERVAL_S[1], wait)

    def test_signature_waits_until_due_and_can_be_turned_off(self) -> None:
        self.on(2026, 11, 8)
        self.pet.next_signature_at = float("inf")
        self.pet.check_roam_ai()
        self.pet.next_signature_at = 0
        self.pet.settings["daily_signature_enabled"] = False
        self.pet.check_roam_ai()
        self.assertEqual(self.kinds(), [])

    def test_no_show_while_something_else_is_playing(self) -> None:
        self.on(2026, 11, 8)
        self.pet.coord.submit(EventRequest(kind="user.test", priority=Priority.USER, state=ActorState.SPECIAL,
                                           action="special_cartwheel", duration_s=5))
        self.pet.next_signature_at = 0
        self.pet.check_roam_ai()
        self.assertNotIn("daily.signature", self.kinds())

    def test_user_action_replaces_a_running_signature(self) -> None:
        self.on(2026, 11, 8)
        self.pet.next_signature_at = 0
        self.pet.check_roam_ai()
        self.assertTrue(self.pet.trigger_special_action("special_blow_kiss"))
        self.assertEqual(self.pet.coord.action, "special_blow_kiss")

    def test_natural_action_waits_near_a_signature(self) -> None:
        self.on(2026, 11, 8)
        self.pet.next_natural_at = 0
        self.pet.next_signature_at = time.time() + 5
        self.pet.check_roam_ai()
        self.assertEqual(self.kinds(), [])
        self.pet.next_signature_at = time.time() + 200
        self.pet.check_roam_ai()
        self.assertEqual(self.kinds(), ["daily.natural"])
        self.assertEqual(self.spy.call_args.args[0].priority, Priority.SPONTANEOUS)

    def test_tap_gives_a_short_reaction_once(self) -> None:
        body = (0, self.pet.height - 10)
        self.pet.drag_start = body
        self.pet.drag_end(None)
        self.assertEqual(self.kinds(), ["interaction.tap"])
        req = self.spy.call_args.args[0]
        self.assertEqual((req.priority, req.action), (Priority.USER, "daily_tap"))
        frames, frame_ms = self.pet._action_frames("chorong", "daily_tap")[:2]
        self.assertAlmostEqual(req.duration_s, len(frames) * frame_ms / 1000.0)   # one pass, not a loop
        self.pet.drag_start = body
        self.pet.drag_end(None)
        self.assertEqual(self.kinds(), ["interaction.tap"])

    def test_click_on_the_head_is_a_pat(self) -> None:
        self.pet.drag_start = (0, 10)
        self.pet.drag_end(None)
        self.assertEqual((self.kinds(), self.spy.call_args.args[0].action), (["interaction.pat"], "daily_pat"))

    def test_each_food_plays_its_own_animation_first(self) -> None:
        self.assertTrue(self.pet._play_reaction(EAT_REACTION, "feed", 2.8, first=("feed_gopchang",)))
        self.assertEqual(self.pet.coord.action, "feed_gopchang")

    def test_food_without_its_own_animation_falls_back(self) -> None:
        # A dish nobody drew (every real food gets drawn sooner or later): the table plays.
        custom_table = {"chorong": ("lifestyle_v6_1/chorong_teacup_relax",)}
        self.assertIsNone(self.pet._action_frames("chorong", "feed_synthetic_missing_dish"))
        self.assertTrue(self.pet._play_reaction(custom_table, "feed", 2.8, first=("feed_synthetic_missing_dish",)))
        self.assertEqual(self.pet.coord.action, "lifestyle_v6_1/chorong_teacup_relax")

    def _without_exact_feed(self):
        """Pretend no member has her own feed_<food> drawing: the alias/cheer path."""
        real = self.pet._action_frames
        return mock.patch.object(self.pet, "_action_frames",
                                 side_effect=lambda m, a: None if a.startswith("feed_") else real(m, a))

    def _fed(self, member: str, food_id: str) -> tuple[str | None, bool]:
        """(action submitted, cheered) for one feed from a hungry, idle pet."""
        self.pet.char_key = member
        self.pet.satiety = 20.0
        active = self.pet.coord.snapshot().active
        if active:
            self.pet.coord.cancel(active.event_id)
        before = self.pet.coord.action
        with mock.patch.object(self.pet, "trigger_cheer") as cheer:
            self.pet.feed(food_id)
        action = self.pet.coord.action
        return (None if cheer.called and action == before else action), cheer.called

    def test_every_member_has_the_new_reactions(self) -> None:
        drawn = ("daily_tap", "daily_pat", "daily_sulk", "daily_full", "daily_bored", "daily_yawn", "daily_surprise",
                 *(f"feed_{f}" for f in ("samgyeopsal", "waffle", "gopchang", "chicken_feet", "fried_chicken", "soju",
                                         "americano", "tteokbokki", "beer", "cola", "whiskey")))
        for member in SIGNATURE_POOL:
            with self.subTest(member):
                self.assertEqual(available_actions(self.pet.sprites, member, drawn), drawn)
        self.assertEqual(available_actions(self.pet.sprites, "bomi", ("daily_hug_side",)), ("daily_hug_side",))

    def test_generic_feed_tables_are_prop_neutral(self) -> None:
        # Generic drink and eat tables are empty so no member holds an unrelated prop
        self.assertFalse(self.pet._play_reaction(DRINK_REACTION, "feed", 2.8))
        self.assertFalse(self.pet._play_reaction(EAT_REACTION, "feed", 2.8))

    def test_member_without_a_reaction_keeps_the_cheer(self) -> None:
        self.assertFalse(self.pet._play_reaction(EAT_REACTION, "feed", 2.8))

    def run_festival(self, *ymd: int) -> list[str]:
        self.on(*ymd)
        self.pet.next_signature_at = float("inf")
        self.pet.next_roam_time = 0
        with mock.patch("app.main.random.random", return_value=0.0):
            self.pet.check_roam_ai()
        return [call.args[0].action for call in self.spy.call_args_list]

    def test_each_festival_adds_its_action(self) -> None:
        for ymd, action in (((2027, 1, 1), "festival_new_year"), ((2026, 12, 24), "festival_christmas"),
                            ((2027, 2, 6), "festival_lunar_ny"), ((2027, 2, 20), "festival_lantern"),
                            ((2027, 9, 15), "festival_mid_autumn")):
            with self.subTest(ymd):
                self.spy.reset_mock()
                self.pet.next_festival_at = 0
                self.assertEqual(self.run_festival(*ymd), [action])
                self.pet.coord.begin_user_interaction("drag")   # clears the stage for the next date
                self.pet.coord.end_user_interaction()

    def test_ordinary_day_has_no_festival_action(self) -> None:
        self.assertEqual([a for a in self.run_festival(2026, 11, 8) if a and a.startswith("festival_")], [])

    def test_festival_toggle_is_independent(self) -> None:
        self.pet.settings["festival_auto_enabled"] = False
        self.assertEqual([a for a in self.run_festival(2026, 12, 24) if a and a.startswith("festival_")], [])
        self.pet.target_roam_x = None
        self.pet._set_ambient("idle")
        self.pet.next_signature_at = 0
        self.pet.next_roam_time = float("inf")
        self.spy.reset_mock()
        self.pet.check_roam_ai()
        self.assertEqual(self.kinds(), ["daily.signature"])

    def test_auto_signature_pauses_while_festival_costume_is_active(self) -> None:
        self.on(2026, 12, 25)
        self.pet.next_signature_at = 0
        self.pet.check_roam_ai()
        self.assertEqual(self.kinds(), [])
        self.assertEqual(self.pet._visual_action(), "festival_christmas")
        # Manual signature trigger still temporarily overrides the costume and restores cleanly.
        self.assertTrue(self.pet.trigger_special_action("special_blow_kiss"))
        self.assertEqual(self.pet._visual_action(), "special_blow_kiss")
        while (active := self.pet.coord.snapshot().active) is not None:
            self.pet.coord.cancel(active.event_id, "test_done")
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

    def test_real_419_opens_the_photo_for_nine_seconds(self) -> None:
        self.on(2027, 4, 19)
        self.pet.calendar.check_user_birthday = lambda *_a, **_k: None
        self.pet.poll_calendar()
        self.pet.coord.on_frame_boundary()
        requests = [call.args[0] for call in self.spy.call_args_list if call.args[0].kind.endswith("apink419")]
        self.assertEqual(requests[0].duration_s, 9.0)
        self.assertIsNotNone(self.pet.anniversary_scene)
        self.pet._close_group_celebration()

    def test_host_keeps_the_festival_costume_as_long_as_the_party(self) -> None:
        self.pet.preview_festival_event("festival_lunar_ny", "lunar")
        req = next(c.args[0] for c in self.spy.call_args_list if c.args[0].kind == "celebrate.together")
        self.assertEqual(req.action, "festival_lunar_ny")
        self.assertGreaterEqual(req.duration_s, 8.0)
        self.pet._close_group_celebration()

    def test_419_toggle_off_keeps_the_plain_greeting(self) -> None:
        self.on(2027, 4, 19)
        self.pet.settings["festival_auto_enabled"] = False
        self.pet.poll_calendar()
        self.assertIsNone(self.pet.anniversary_scene)


    def test_namjoo_and_chorong_menus_offer_their_drawn_signature_moves(self) -> None:
        """User directive (2026-11-10): Special moves must strictly be multi-frame animations (動圖) only."""
        from app.i18n import t
        from app.pink_context_menu import build_pet_context_menu_items
        from app.action_frames import load_exact_action
        wanted = {"namjoo": ("scene_flamingo",),
                  "chorong": ("daily_cat_cuddle",), "bomi": ("interaction_eat",)}
        for member, actions in wanted.items():
            self.assertEqual(tuple(a for a in actions if a in self.pet.available_special_actions(member)), actions)
            for act in actions:
                loaded = load_exact_action(self.pet.sprites, member, act)
                self.assertIsNotNone(loaded, f"{member} {act} should load")
                self.assertGreater(len(loaded.frames), 1, f"{member} {act} must be multi-frame animation (動圖)")
        items = build_pet_context_menu_items(self.pet)
        labels, seen, stack = [], set(), [items]
        while stack:                         # each member's "back" row links to the parent list again
            rows = stack.pop()
            if id(rows) in seen:
                continue
            seen.add(id(rows))
            for row in rows:
                labels.append(row.label)
                if getattr(row, "submenu", None):
                    stack.append(row.submenu)
        for key in ("special_move_flamingo", "special_move_cat", "special_move_mukbang"):
            self.assertIn(t(key, "zh_TW"), labels)
            for lang in ("ko", "en"):
                self.assertNotEqual(t(key, lang), key)
        self.assertTrue(self.pet.trigger_special_action("scene_flamingo", "namjoo"))
        self.assertEqual((self.pet.char_key, self.pet.coord.action), ("namjoo", "scene_flamingo"))

    def test_food_prop_matching_for_smoothie_boba_and_eomuk(self) -> None:
        """User report (2026-11-10): eomuk_tang must NOT play mango smoothie, and mango smoothie must NOT play boba.

        Her own feed_<food> drawing always comes first; only without it does the member alias
        (or the prop-neutral cheer) play, and an alias never crosses to another dish."""
        for food in ("tw_mango_smoothie", "tw_brown_sugar_boba", "tw_strawberry_boba", "eomuk_tang", "malatang"):
            with self.subTest(food=food):
                self.assertEqual(self._fed("namjoo", food), (f"feed_{food}", False))
        with self._without_exact_feed():
            # Mango smoothie = mango ice (user definition): the mukbang mango ice, never boba.
            self.assertEqual(self._fed("namjoo", "tw_mango_smoothie"), ("actions_v7/namjoo_mukbang_ready", False))
            self.assertEqual(self._fed("namjoo", "tw_brown_sugar_boba"), ("situational_v6_2/namjoo_gourmet_taster", False))
            # Strawberry boba never borrows the plain brown-pearl cup; fish cake soup never a smoothie/boba.
            self.assertEqual(self._fed("namjoo", "tw_strawberry_boba"), (None, True))
            self.assertEqual(self._fed("namjoo", "eomuk_tang"), (None, True))
            # The collared situational_v3 still is blocked: no exact art -> food-neutral cheer.
            self.assertEqual(self._fed("namjoo", "malatang"), (None, True))

    def test_all_five_members_food_prop_accuracy_and_neutral_cheer(self) -> None:
        """Verify all 5 members: no wrong props (e.g. Bomi fishcake soup != ramen, Chorong soymilk != tea)."""
        exact = (("bomi", "eomuk_tang"), ("bomi", "jajangmyeon"), ("chorong", "tw_white_soymilk"),
                 ("chorong", "tw_oolong_tea"), ("eunji", "eomuk_tang"), ("hayoung", "eomuk_tang"), ("hayoung", "bread"))
        for member, food in exact:
            with self.subTest(member=member, food=food):
                self.assertEqual(self._fed(member, food), (f"feed_{food}", False))
        # Beef noodle: her own drawing once registered, else (below) the ramen pot she was drawn with.
        for member in ("bomi", "eunji"):
            if self.pet._action_frames(member, "feed_tw_beef_noodle") is not None:
                self.assertEqual(self._fed(member, "tw_beef_noodle"), ("feed_tw_beef_noodle", False))
        with self._without_exact_feed():
            self.assertEqual(self._fed("bomi", "tw_beef_noodle"), ("lifestyle_v6_2/bomi_ramen_brass_pot", False))
            self.assertEqual(self._fed("eunji", "tw_beef_noodle"), ("situational_v6/eunji_cap_slurp_ramen_pot", False))
            # Without their own drawing: never the ramen for fish cake soup, never tea for soymilk/oolong.
            for member, food in (("bomi", "eomuk_tang"), ("eunji", "eomuk_tang"), ("hayoung", "eomuk_tang"),
                                 ("chorong", "tw_white_soymilk"), ("chorong", "tw_oolong_tea")):
                with self.subTest(member=member, food=food, exact="missing"):
                    self.assertEqual(self._fed(member, food), (None, True))
            # Hayoung's bread falls back to her croissant-and-waffle art (an actual bread prop).
            self.assertEqual(self._fed("hayoung", "bread"), ("situational_v6/hayoung_crispy_waffles_honey", False))

    def test_stay_in_place_toggle_and_roam_suppression(self) -> None:
        """Verify stay_in_place setting toggles cleanly and halts roaming and walking."""
        self.pet.settings["stay_in_place"] = False
        self.pet.toggle_stay_in_place()
        self.assertTrue(self.pet.settings.get("stay_in_place"))
        self.assertIsNone(self.pet.target_roam_x)

        # Force roam AI check while stay_in_place is active
        self.pet.next_roam_time = 0
        self.pet.next_signature_at = float("inf")
        self.pet.last_user_activity = 0
        self.pet.check_roam_ai()
        self.assertIsNone(self.pet.target_roam_x, "Roaming target must not be assigned when pinned")
        self.assertNotEqual(self.pet.state, "walk", "Pet must not enter walking state when pinned")

        # Walk step must not advance or drift x coordinate
        orig_x = self.pet.x
        self.pet.step_walk()
        self.assertEqual(self.pet.x, orig_x, "Pet x position must stay constant when pinned")

        # Toggle back off
        self.pet.toggle_stay_in_place()
        self.assertFalse(self.pet.settings.get("stay_in_place"))

    def test_scheme2_all_day_festival_costume_transitions_and_midnight_revert(self) -> None:
        """Scheme 2: holiday costume stays on for idle/cheer/tap/walk, pauses for sleep/special, reverts at midnight."""
        def on_dt(year: int, month: int, day: int, hour: int = 12, minute: int = 0, second: int = 0) -> None:
            self.pet.calendar.clock.now = lambda: dt.datetime(year, month, day, hour, minute, second)
            self.pet.poll_calendar()

        # 12/23 -> everyday outfit
        on_dt(2026, 12, 23, 23, 59, 55)
        self.assertIsNone(self.pet._visual_action())
        self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))

        # 12/24 -> Christmas enters Scheme 2 automatically
        on_dt(2026, 12, 24, 0, 0, 2)
        self.assertEqual(self.pet._visual_action(), "festival_christmas")
        self.assertNotEqual(self.pet._frame_pad, (0, 0, 0, 0))

        # Walk left & right keep Christmas costume and flip left-facing frames
        self.pet._set_ambient("walk")
        self.pet.direction = 1
        self.assertEqual(self.pet._visual_action(), "festival_christmas")
        self.assertEqual(self.pet._visual_facing("festival_christmas"), 1)
        right_frame = self.pet.current_frame()
        self.pet.direction = -1
        self.pet.animate()
        self.assertEqual(self.pet._visual_action(), "festival_christmas")
        self.assertEqual(self.pet._visual_facing("festival_christmas"), -1)
        left_frame = self.pet.current_frame()
        self.assertIsNot(right_frame, left_frame)

        # Deep sleep uses sleep sprite via animate() (restores base box), waking restores costume
        self.pet._set_ambient("sleep")
        self.assertIsNone(self.pet._visual_action())
        self.pet.animate()
        self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))
        self.pet._set_ambient("idle")
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

        # Dragging and explicit special moves pause the holiday costume, then restore it cleanly
        self.pet.dragging = True
        self.pet.animate()
        self.assertNotEqual(self.pet._visual_action(), "festival_christmas")
        self.pet.dragging = False
        self.pet.animate()
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

        self.assertTrue(self.pet.trigger_special_action("special_blow_kiss"))
        self.pet.animate()
        self.assertEqual(self.pet._visual_action(), "special_blow_kiss")
        while (active := self.pet.coord.snapshot().active) is not None:
            self.pet.coord.cancel(active.event_id, "test_done")
        self.pet.animate()
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

        # Light tap keeps holiday cheer without dropping back into everyday clothes
        self.pet._next_tap_at = 0.0
        self.pet._react_to_tap(head=True)
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

        # Toggle off -> everyday; toggle on -> Christmas back immediately
        self.pet.toggle_festival_auto()
        self.assertIsNone(self.pet._visual_action())
        self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))
        self.pet.toggle_festival_auto()
        self.assertEqual(self.pet._visual_action(), "festival_christmas")

        # 12/26 midnight -> auto-reverts to everyday clothes and cancels any active festival.* action
        on_dt(2026, 12, 26, 0, 0, 1)
        self.assertIsNone(self.pet._visual_action())
        self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))

        # New Year, Lunar NY, Lantern (384x416), Mid-Autumn each activate and auto-revert next day
        for active_ymd, after_ymd, expected_act in (
            ((2027, 1, 1), (2027, 1, 2), "festival_new_year"),
            ((2027, 2, 5), (2027, 2, 8), "festival_lunar_ny"),
            ((2027, 2, 20), (2027, 2, 21), "festival_lantern"),
            ((2027, 9, 15), (2027, 9, 16), "festival_mid_autumn"),
        ):
            with self.subTest(expected_act=expected_act):
                on_dt(*active_ymd, 10, 0, 0)
                self.assertEqual(self.pet._visual_action(), expected_act)
                on_dt(*after_ymd, 0, 0, 5)
                self.assertIsNone(self.pet._visual_action())
                self.assertEqual(self.pet._frame_pad, (0, 0, 0, 0))

    def test_scheme2_all_five_members_and_sizes_plus_new_year_isolation(self) -> None:
        """All 5 members x 3 sizes wear active festival costumes; 1/1 never borrows Hanbok."""
        from app.daily_actions import SIGNATURE_POOL

        # 1. All 5 members on Lantern (384x416, bottom-extended) across all 3 sizes + MIRROR_UNSAFE guard
        from app.sprites import DIRECTIONAL_WALK_LEFT, MIRROR_UNSAFE
        from contextlib import nullcontext
        area = self.pet.desktop.work_area_for_point(self.pet.x, self.pet.y)
        for size_key in ("small", "medium", "large"):
            self.pet.set_pet_size(size_key)
            self.pet.x = area.left + max(40, (area.width - self.pet.width) // 2)
            for member in SIGNATURE_POOL:
                with self.subTest(size=size_key, member=member):
                    self.pet.switch_character(member, mode="manual")
                    self.pet.calendar.clock.now = lambda: dt.datetime(2027, 2, 20, 14, 15, 0)
                    self.pet.poll_calendar()
                    self.pet.coord.on_frame_boundary()
                    while (active := self.pet.coord.snapshot().active) is not None:
                        self.pet.coord.cancel(active.event_id, "test_ready")
                        self.pet.coord.on_frame_boundary()
                    self.assertEqual(self.pet._visual_action(), "festival_lantern")
                    self.pet._set_ambient("walk")
                    self.pet.direction = 1
                    self.pet.animate()
                    self.assertEqual(self.pet._visual_action(), "festival_lantern")
                    self.assertGreater(sum(self.pet._frame_pad), 0)
                    self.pet.direction = -1
                    no_mirror = (mock.patch("PIL.Image.Image.transpose", side_effect=AssertionError(f"{member} must not mirror"))
                                 if member in MIRROR_UNSAFE else nullcontext())
                    with no_mirror:
                        self.pet.animate()
                    expected = "walk_left" if member in DIRECTIONAL_WALK_LEFT else "festival_lantern"
                    self.assertEqual(self.pet._visual_action(), expected)
                    pad = self.pet._frame_pad
                    if member in DIRECTIONAL_WALK_LEFT:
                        self.assertEqual(sum(pad), 0)
                    else:
                        self.assertGreater(sum(pad), 0)
                    self.assertEqual(int(self.pet.canvas["width"]), self.pet.width + pad[0] + pad[2])
                    self.assertEqual(int(self.pet.canvas["height"]), self.pet.height + pad[1] + pad[3])
                    left_frame = self.pet.current_frame()
                    unflipped_frames = self.pet._action_frames(member, expected)[0]
                    flipped_frames = self.pet._flipped_action_frames(member, expected)[0]
                    if member in MIRROR_UNSAFE:
                        self.assertEqual(self.pet._visual_facing(expected), 1)
                        self.assertIn(left_frame, unflipped_frames)
                    else:
                        self.assertEqual(self.pet._visual_facing("festival_lantern"), -1)
                        self.assertIn(left_frame, flipped_frames)
                        self.assertNotIn(left_frame, unflipped_frames)
                    self.pet.direction = 1
                    self.pet._set_ambient("idle")

        # 2. Dec 31 jittered countdown -> 01/01 (no festival_new_year yet => everyday + lightstick, NEVER hanbok)
        self.pet.set_pet_size("medium")
        self.pet.switch_character("chorong", mode="manual")
        toasts = []
        with mock.patch.object(self.pet, "_toast", side_effect=lambda *a, **kw: toasts.append((a, kw))), \
             mock.patch.object(self.pet, "_start_new_year_clock") as start_clk, \
             mock.patch("app.main.GroupCelebration") as grp:
            for ts in (
                (2026, 12, 31, 23, 29, 55),
                (2026, 12, 31, 23, 30, 2),   # jittered past :00!
                (2026, 12, 31, 23, 30, 3),   # same minute must not double fire
                (2026, 12, 31, 23, 59, 12),  # jittered past :10!
                (2026, 12, 31, 23, 59, 23),  # jittered past :20!
            ):
                self.pet.calendar.clock.now = lambda t=ts: dt.datetime(*t)
                self.pet._check_new_year_countdown()
            # 23:30 (1x), 23:59:12 -> 48s (1x), 23:59:23 -> 37s (1x)
            self.assertEqual(len(toasts), 3)
            self.assertEqual(toasts[1][1].get("badge_text"), "48s ⏰")
            self.assertEqual(toasts[2][1].get("badge_text"), "37s ⏰")
            self.pet.calendar.clock.now = lambda: dt.datetime(2026, 12, 31, 23, 59, 45)
            self.pet._check_new_year_countdown()
            start_clk.assert_called_once_with(15)
            # Clock started != celebrated: cancelling clock/entering standby keeps Jan 1 catchup intact
            self.assertFalse(self.pet._new_year_celebrated)
            self.pet._close_new_year_clock()
            self.pet.standby_overlay = object()
            self.pet.calendar.clock.now = lambda: dt.datetime(2027, 1, 1, 0, 1, 0)
            self.pet._check_new_year_countdown()
            grp.assert_not_called()
            self.pet.standby_overlay = None

            # Missed-midnight Jan 1 catchup with real approved festival_new_year art -> Scheme 2 + group party + Jan 2 revert
            self.pet.calendar.clock.now = lambda: dt.datetime(2027, 1, 1, 0, 5, 0)
            self.pet.poll_calendar()
            self.assertEqual(self.pet._active_festival_costume(), "festival_new_year")
            self.assertEqual(self.pet._visual_action(), "festival_new_year")
            self.pet._check_new_year_countdown()
            grp.assert_called_once()
            for member in SIGNATURE_POOL:
                self.assertEqual(grp.call_args.kwargs["action"](member), "festival_new_year")
            while (active := self.pet.coord.snapshot().active) is not None:
                self.pet.coord.cancel(active.event_id, "test_done")
            self.assertEqual(self.pet._visual_action(), "festival_new_year")

            # Midnight into Jan 2 -> reverts back to None cleanly
            self.pet.calendar.clock.now = lambda: dt.datetime(2027, 1, 2, 0, 0, 1)
            self.pet.poll_calendar()
            self.assertIsNone(self.pet._visual_action())

            # Defensive fallback when festival_new_year art is unavailable: everyday clothes + lightstick, NEVER hanbok
            real_frames = self.pet._action_frames
            self.pet.calendar.clock.now = lambda: dt.datetime(2028, 1, 1, 0, 5, 0)
            self.pet._new_year_celebrated = False
            self.pet._new_year_celebrated_year = None
            self.pet._ny_countdown_year = None
            grp.reset_mock()
            with mock.patch.object(
                self.pet,
                "_action_frames",
                side_effect=lambda m, a: None if a == "festival_new_year" else real_frames(m, a),
            ):
                self.pet.poll_calendar()
                self.assertIsNone(self.pet._active_festival_costume())
                self.assertIsNone(self.pet._visual_action())          # everyday clothes, never festival_lunar_ny
                self.pet._check_new_year_countdown()
                self.assertEqual(self.pet._visual_action(), "special_cheer_lightstick")
                grp.assert_called_once()
                self.assertEqual(grp.call_args.kwargs["action"]("bomi"), "special_cheer_lightstick")
                while (active := self.pet.coord.snapshot().active) is not None:
                    self.pet.coord.cancel(active.event_id, "test_done")
                self.assertIsNone(self.pet._visual_action())

        # All 5 members actually wear approved festival_new_year across Jan 1
        for member in SIGNATURE_POOL:
            with self.subTest(new_year_member=member):
                self.pet.switch_character(member, mode="manual")
                self.pet.calendar.clock.now = lambda: dt.datetime(2027, 1, 1, 12, 0, 0)
                self.pet.poll_calendar()
                self.assertEqual(self.pet._visual_action(), "festival_new_year")
        self.pet.calendar.clock.now = lambda: dt.datetime(2027, 1, 2, 0, 0, 1)
        self.pet.poll_calendar()
        self.assertIsNone(self.pet._visual_action())


if __name__ == "__main__":
    unittest.main()
