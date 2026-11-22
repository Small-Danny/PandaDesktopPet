"""tests/test_satiety_and_aegyo.py — Test Satiety Decay, Feeding Boost, and Hunger Aegyo System.
"""
import unittest
from app.foods import (
    SATIETY_MAX,
    SATIETY_HUNGRY_THRESHOLD,
    SATIETY_STARVING_THRESHOLD,
    SATIETY_DECAY_SECONDS_PER_PERCENT,
    SATIETY_FEED_BOOST,
    SATIETY_FAV_FEED_BOOST,
    MEMBER_HUNGER_AEGYO_QUOTES,
    get_hunger_aegyo_quote,
)


class TestSatietyAndAegyo(unittest.TestCase):
    def test_satiety_constants(self):
        self.assertEqual(SATIETY_MAX, 100.0)
        self.assertEqual(SATIETY_HUNGRY_THRESHOLD, 30.0)
        self.assertEqual(SATIETY_STARVING_THRESHOLD, 10.0)
        self.assertEqual(SATIETY_DECAY_SECONDS_PER_PERCENT, 720.0)
        self.assertEqual(SATIETY_FEED_BOOST, 20.0)
        self.assertEqual(SATIETY_FAV_FEED_BOOST, 35.0)

    def test_member_hunger_aegyo_quotes_completeness(self):
        members = ["chorong", "bomi", "eunji", "namjoo", "hayoung"]
        for m in members:
            self.assertIn(m, MEMBER_HUNGER_AEGYO_QUOTES)
            quotes = MEMBER_HUNGER_AEGYO_QUOTES[m]
            self.assertGreaterEqual(len(quotes), 3, f"{m} should have at least 3 hunger aegyo quotes")
            for q in quotes:
                for lang in ("zh_TW", "ko", "en"):
                    self.assertIn(lang, q, f"Missing {lang} in quote for {m}")
                    self.assertTrue(len(q[lang]) > 5, f"Quote too short for {m} in {lang}")

    def test_get_hunger_aegyo_quote(self):
        for lang in ("zh_TW", "ko", "en"):
            q = get_hunger_aegyo_quote("bomi", lang=lang)
            self.assertIsInstance(q, str)
            self.assertTrue(len(q) > 0)


if __name__ == "__main__":
    unittest.main()
