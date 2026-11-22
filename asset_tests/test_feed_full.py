"""Feeding a full pet: solid food is refused (no stats change), drinks are still sipped.

Run:  python -m unittest tests.test_feed_full -v
"""
from __future__ import annotations

import re
import string
import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import MEMBER_KEYS  # noqa: E402
from app.foods import (  # noqa: E402
    FOOD_ITEMS,
    get_food_name,
    MEMBER_FULL_DRINK_QUOTES,
    MEMBER_FULL_SOLID_QUOTES,
    SATIETY_FULL_THRESHOLD,
    get_full_reaction,
)
from app.i18n import t  # noqa: E402
from app.main import PandaPet  # noqa: E402

HAN = re.compile(r"[一-鿿]")


def _name(food_id: str, lang: str = "zh_TW") -> str:
    return get_food_name(next(f for f in FOOD_ITEMS if f["id"] == food_id), lang)


def _pet(member: str = "chorong", satiety: float = 100.0, updated_ago: float = 0.0, lang: str = "zh_TW"):
    shown, saved = [], []
    pet = types.SimpleNamespace(
        char_key=member, lang=lang, satiety=satiety,
        last_satiety_update=time.time() - updated_ago,
        runtime={"cheer_passion": 0, "feed_count": 0}, feed_count=0,
        record_activity=lambda: None,
        save_settings=lambda: saved.append(1),
        trigger_cheer=lambda **kw: None, _play_reaction=lambda *a, **k: False,
        _refresh_status_card=lambda: None,
        _refresh_food_panel=lambda: None,
        _toast=lambda msg, **kw: shown.append((msg, kw)),
    )
    pet._current_satiety = lambda: PandaPet._current_satiety(pet)
    return pet, shown, saved


class FullTemplatesTest(unittest.TestCase):
    def test_every_member_has_both_lines_in_three_languages(self) -> None:
        for table in (MEMBER_FULL_SOLID_QUOTES, MEMBER_FULL_DRINK_QUOTES):
            self.assertEqual(set(table), set(MEMBER_KEYS))
            for member, quotes in table.items():
                for quote in quotes:
                    for lang in ("zh_TW", "ko", "en"):
                        with self.subTest(member=member, lang=lang):
                            fields = {f for _, f, _, _ in string.Formatter().parse(quote[lang]) if f}
                            self.assertEqual(fields, {"food"})
                            if lang != "zh_TW":
                                self.assertFalse(HAN.search(quote[lang]), quote[lang])

    def test_kind_decides_table(self) -> None:
        self.assertTrue(get_full_reaction("cola", "bomi", "en")[0])
        self.assertFalse(get_full_reaction("tteokbokki", "bomi", "en")[0])


class FeedWhenFullTest(unittest.TestCase):
    def test_solid_food_is_refused_without_changes(self) -> None:
        pet, shown, saved = _pet(satiety=100.0, lang="en")
        PandaPet.feed(pet, "tteokbokki")
        self.assertEqual(len(shown), 1)
        msg, kw = shown[0]
        self.assertEqual(kw["kind"], "feed.full")
        self.assertEqual(kw["header"], t("feed_full_header", "en", food=_name("tteokbokki", "en")))
        self.assertIn(_name("tteokbokki", "en"), msg)
        self.assertEqual((pet.feed_count, pet.runtime["cheer_passion"], pet.satiety), (0, 0, 100.0))
        self.assertEqual(saved, [])

    def test_drink_is_still_sipped_with_full_line(self) -> None:
        pet, shown, saved = _pet(member="bomi", satiety=97.0)
        with mock.patch("random.choice", side_effect=lambda seq: seq[0]):
            PandaPet.feed(pet, "cola")
        msg, kw = shown[-1]
        self.assertEqual(kw["kind"], "feed")
        cola = _name("cola")
        self.assertEqual(msg, MEMBER_FULL_DRINK_QUOTES["bomi"][0]["zh_TW"].format(food=cola))
        self.assertEqual(kw["header"], t("feed_full_drink_header", "zh_TW", food=cola))
        self.assertEqual(pet.feed_count, 1)
        self.assertEqual(pet.satiety, 100.0)
        self.assertEqual(saved, [1])

    def test_disliked_reaction_wins_over_full(self) -> None:
        pet, shown, _ = _pet(member="eunji", satiety=100.0)
        PandaPet.feed(pet, "mint_choco")
        msg, kw = shown[-1]
        self.assertEqual(kw["header"], t("feed_disliked_header", "zh_TW", food=_name("mint_choco")))
        self.assertEqual(pet.feed_count, 1)

    def test_decay_since_last_update_counts(self) -> None:
        # 96 % stored, but updated 2 h ago -> about 86 % now: a normal feed.
        pet, shown, _ = _pet(satiety=96.0, updated_ago=7200.0)
        self.assertLess(PandaPet._current_satiety(pet), SATIETY_FULL_THRESHOLD)
        PandaPet.feed(pet, "tteokbokki")
        self.assertEqual(shown[-1][1]["kind"], "feed")
        self.assertEqual(pet.feed_count, 1)

    def test_boost_adds_to_decayed_value(self) -> None:
        # 50 % stored 2 h ago is 40 % now; a normal (non-favourite) meal (+20) gives 60, not 70.
        pet, _, _ = _pet(satiety=50.0, updated_ago=7200.0)
        PandaPet.feed(pet, "jajangmyeon")
        self.assertAlmostEqual(pet.satiety, 60.0, delta=0.1)


if __name__ == "__main__":
    unittest.main()
