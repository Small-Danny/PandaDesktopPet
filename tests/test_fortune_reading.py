import datetime as dt
import random
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.fortune_cards import (
    CARD_GUARDIANS, CHORONG_EGG_CARD, GUARDIAN_LINES_FINAL, GUARDIAN_TAGS_FINAL, TAROT_CARDS,
)
from app.bubble import KawaiiSpeechBubble
from app.bubble_themes import THEMES
from app.foods import get_food_name
from app.fortune_reading import (
    FOODS, Reading, daily_bubble_content, daily_fortune, egg_chance, food_is_safe, lucky_food, make_reading,
)
from app.i18n import get_member_display_name, t
from app.main import PandaPet, bubble_title
from app.platform.win32 import WorkArea


class FortuneReadingTest(unittest.TestCase):
    def test_complete_trilingual_deck_and_personas(self):
        self.assertEqual(len(TAROT_CARDS), 56)
        deck = (*TAROT_CARDS, CHORONG_EGG_CARD)
        self.assertEqual(len({card.key for card in deck}), 57)
        for card in deck:
            self.assertIn(len(card.stars), range(1, 6))
            for field in (card.title, card.badge, card.message, card.lucky):
                self.assertEqual(set(field), {"zh_TW", "ko", "en"})
                self.assertTrue(all(text.strip() for text in field.values()))
        self.assertEqual(GUARDIAN_TAGS_FINAL["chorong"]["zh_TW"], "操心隊長")
        self.assertTrue(all(len(lines) == 4 for lines in GUARDIAN_LINES_FINAL.values()))

    def test_daily_replay_and_repair(self):
        date = dt.date(2026, 11, 18)
        a, record = daily_fortune(date, "salt", None)
        self.assertEqual(daily_fortune(date, "salt", None), (a, record))
        self.assertEqual(daily_fortune(date, "new-salt", record), (a, record))
        repaired, saved = daily_fortune(date, "salt", {**record, "food_id": "soju"})
        self.assertEqual(repaired.card_id, a.card_id)
        self.assertEqual(repaired.guardian_id, a.guardian_id)
        self.assertNotEqual(saved["food_id"], "soju")
        self.assertTrue(food_is_safe(FOODS[repaired.food_id], repaired.guardian_id))
        for broken in ({**record, "card_id": []}, {**record, "line_id": True}, {"version": 0}):
            self.assertEqual(daily_fortune(date, "salt", broken), (a, record))
        tomorrow = dt.date(2026, 11, 19)
        self.assertEqual(daily_fortune(tomorrow, "salt", record)[1]["date"], tomorrow.isoformat())

    def test_weighted_buckets_and_empty_fallback(self):
        foods = [
            {"id": "favorite", "kind": "meal", "favorites": ["chorong"]},
            {"id": "other", "kind": "meal"},
            {"id": "banned", "kind": "alcohol", "universal": True},
            {"id": "disliked", "kind": "meal", "disliked": ["chorong"]},
        ]
        rng = random.Random(81)
        results = [lucky_food(rng, "chorong", foods) for _ in range(2000)]
        self.assertEqual(set(results), {"favorite", "other"})
        self.assertAlmostEqual(results.count("favorite") / 2000, .6, delta=.04)
        self.assertEqual(lucky_food(rng, "chorong", foods[1:]), "other")
        self.assertIsNone(lucky_food(rng, "chorong", foods[2:]))

    def test_hidden_card_and_hours(self):
        hours = (22, 23, 0, 4, 5)
        self.assertEqual([egg_chance(hour) for hour in hours], [.05, .15, .15, .15, .05])
        rng = random.Random(2)
        regular = make_reading(rng)
        self.assertNotEqual(make_reading(rng, regular.card_id).card_id, regular.card_id)
        egg = make_reading(rng, egg=True)
        self.assertEqual((egg.card_id, egg.guardian_id), (CHORONG_EGG_CARD.key, "chorong"))
        self.assertTrue(food_is_safe(FOODS[egg.food_id], "chorong"))

    def test_member_cards_always_align_with_matching_guardian(self):
        rng = random.Random(7)
        for _ in range(300):
            reading = make_reading(rng)
            if reading.card_id in CARD_GUARDIANS:
                self.assertEqual(reading.guardian_id, CARD_GUARDIANS[reading.card_id], reading.card_id)
        # Saved daily readings from before this rule are repaired on load.
        day = dt.date(2026, 11, 22)
        for card_id, expected_guardian in (("lucky_gamepad", "hayoung"), ("brave_compass", "bomi")):
            wrong_guardian = "namjoo" if expected_guardian != "namjoo" else "eunji"
            repaired, saved = daily_fortune(day, "salt", {
                "version": 1, "date": day.isoformat(), "card_id": card_id,
                "guardian_id": wrong_guardian, "food_id": "soju", "line_id": 2,
            })
            self.assertEqual(repaired.card_id, card_id)
            self.assertEqual(repaired.guardian_id, expected_guardian)
            self.assertEqual(saved["guardian_id"], expected_guardian)
            self.assertTrue(food_is_safe(FOODS[repaired.food_id], expected_guardian))

    def test_daily_bubble_uses_same_reading_even_after_failed_save(self):
        clock = Mock()
        clock.now.return_value = dt.datetime(2026, 11, 18, 12)
        pet = SimpleNamespace(calendar=SimpleNamespace(clock=clock), runtime={}, lang="en", char_key="namjoo",
                              save_settings=Mock(return_value=False), record_activity=Mock(), _toast=Mock())
        pet._today_fortune = lambda: PandaPet._today_fortune(pet)
        reading = pet._today_fortune()
        self.assertEqual(clock.now.call_count, 1)
        PandaPet.show_daily_fortune_bubble(pet)
        content = daily_bubble_content(reading, "en")
        self.assertEqual(pet._toast.call_args.args, (content["message"],))
        kwargs = pet._toast.call_args.kwargs
        self.assertEqual(kwargs["kind"], "fortune.daily")
        self.assertEqual(kwargs["speaker"], "eunji")
        self.assertEqual(pet.char_key, "namjoo")
        for field in ("header", "sub_badge", "badge_text"):
            self.assertEqual(kwargs[field], content[field])
        self.assertGreaterEqual(kwargs["duration_ms"], 8000)
        self.assertEqual(pet._today_fortune(), reading)
        pet.save_settings.assert_called_once()

    def test_daily_bubble_tells_the_whole_reading_in_every_language(self):
        """Category + stars, title, meaning, lucky hint, food and guardian, like the studio."""
        food_id = next(iter(FOODS))
        for card in TAROT_CARDS:
            for lang in ("zh_TW", "ko", "en"):
                with self.subTest(card=card.key, lang=lang):
                    content = daily_bubble_content(Reading(card.key, "namjoo", food_id, 0), lang)
                    self.assertEqual(content["header"], t("fortune_daily_title", lang))
                    self.assertEqual(content["sub_badge"], f"{card.badge[lang]} {card.stars}")
                    self.assertNotIn("｜", content["sub_badge"])  # one chip beside the header chip
                    self.assertEqual(content["message"].split("\n"), [card.title[lang], card.message[lang]])
                    hints = content["badge_text"].split("\n")
                    self.assertEqual(hints[:2], [
                        card.lucky[lang],
                        t("fortune_lucky_food", lang, food=get_food_name(FOODS[food_id], lang)),
                    ])
                    self.assertIn(get_member_display_name("namjoo", lang), hints[2])
                    self.assertIn(GUARDIAN_TAGS_FINAL["namjoo"][lang], hints[2])
                    self.assertNotIn("{", content["badge_text"])
        no_food = daily_bubble_content(Reading(TAROT_CARDS[0].key, "bomi", None, 0), "en")
        self.assertEqual(len(no_food["badge_text"].split("\n")), 2)


class DailyFortuneBubbleLayoutTest(unittest.TestCase):
    """The longest readings fit a 1080p work area at 100 % and 150 % in every text size."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.addCleanup(self.root.tk.call, "tk", "scaling", 96 / 72)

    def test_longest_readings_fit_without_scrolling(self):
        desktop = Mock()
        food_id = max(FOODS, key=lambda key: len(get_food_name(FOODS[key], "en")))
        for dpi in (96, 144):
            self.root.tk.call("tk", "scaling", dpi / 72)
            area = WorkArea(0, 0, 1920 * dpi // 96, 1040)
            desktop.work_area_for_point.return_value = area
            for lang in ("zh_TW", "ko", "en"):
                card = max(TAROT_CARDS, key=lambda c: len(c.message[lang]) + len(c.badge[lang]) + len(c.lucky[lang]))
                content = daily_bubble_content(Reading(card.key, "hayoung", food_id, 0), lang)
                header, chips = bubble_title(content["header"], content["sub_badge"], "eunji", lang)
                for size in ("small", "medium", "large"):
                    for theme in ("classic", "eunji_comic"):
                        with self.subTest(dpi=dpi, lang=lang, size=size, theme=theme):
                            bubble = KawaiiSpeechBubble(
                                self.root, 800, 700, 192, header, content["message"], chips,
                                content["badge_text"], duration_ms=60000, desktop=desktop,
                                theme=THEMES[theme], text_size=size,
                            )
                            try:
                                self.assertFalse(bubble.scrollable)
                                self.assertEqual(bubble.height, bubble.content_height)
                                self.assertLessEqual(bubble.height, area.height - 20)
                                self.assertTrue(bubble.chip_boxes)
                                for x, _y, w, _h, _lines in bubble.chip_boxes:
                                    self.assertGreaterEqual(x, 0)
                                    self.assertLessEqual(x + w, bubble.width)
                            finally:
                                bubble.dismiss()
