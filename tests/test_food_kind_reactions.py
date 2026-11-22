"""Feeding a drink, coffee, alcohol or dessert gets a line that fits what was fed."""
from __future__ import annotations

import re
import string
import unittest
from unittest import mock

from app.foods import (
    DRINK_KINDS,
    FOOD_ITEMS,
    FOOD_KIND,
    KIND_REACTIONS_I18N,
    feed_pet,
    get_feed_animation,
    get_food_kind,
    get_food_name,
)

LANGS = ("zh_TW", "ko", "en")
HAN = re.compile(r"[一-鿿]")


def _food(food_id: str) -> dict:
    return next(f for f in FOOD_ITEMS if f["id"] == food_id)


class FoodKindTest(unittest.TestCase):
    def test_kind_table_only_names_real_foods(self) -> None:
        ids = {f["id"] for f in FOOD_ITEMS}
        self.assertEqual(set(FOOD_KIND) - ids, set())
        self.assertEqual(set(KIND_REACTIONS_I18N) - {"drink", "coffee", "alcohol", "dessert"}, set())

    def test_templates_complete_in_every_language(self) -> None:
        for kind, by_lang in KIND_REACTIONS_I18N.items():
            for lang in LANGS:
                with self.subTest(kind=kind, lang=lang):
                    lines = by_lang[lang]
                    self.assertGreaterEqual(len(lines), 2)
                    for line in lines:
                        fields = {f for _, f, _, _ in string.Formatter().parse(line) if f}
                        self.assertEqual(fields, {"food"}, line)
                        if lang != "zh_TW":
                            self.assertFalse(HAN.search(line), line)

    def test_animation_key(self) -> None:
        for food in FOOD_ITEMS:
            expected = "drink" if get_food_kind(food) in DRINK_KINDS else "eat"
            self.assertEqual(get_feed_animation(food), expected, food["id"])
        self.assertEqual(get_feed_animation(_food("soju")), "drink")
        self.assertEqual(get_feed_animation(_food("tteokbokki")), "eat")

    def test_non_favourite_drinks_get_drink_lines(self) -> None:
        # Members fed something that is not their favourite: soju / cola for Chorong.
        for food_id, kind in (("soju", "alcohol"), ("cola", "drink")):
            for lang in LANGS:
                with self.subTest(food=food_id, lang=lang):
                    food = _food(food_id)
                    with mock.patch("random.choice", side_effect=lambda seq: seq[0]):
                        _, line = feed_pet(food_id, "chorong", lang)
                    template = KIND_REACTIONS_I18N[kind][lang][0]
                    self.assertEqual(line, template.format(food=get_food_name(food, lang)))
                    self.assertIn(get_food_name(food, lang), line)
                    self.assertFalse(any(word in line for word in ("嚼", "Yum yum")), line)

    def test_meals_keep_member_lines(self) -> None:
        # A non-favourite meal still uses the member's own generic line.
        _, line = feed_pet("budae_jjigae", "hayoung", "en")
        self.assertTrue(line)
        self.assertNotIn("{food}", line)

    def test_coriander_follows_each_member(self) -> None:
        # User, 2026-11-07: Eunji and Chorong don't eat it; Bomi eats it ("like celery"). 2026-11-08: Namjoo and Hayoung do not either.
        coriander = _food("coriander")
        self.assertEqual(set(coriander["disliked"]), {"eunji", "chorong", "namjoo", "hayoung"})
        for lang in LANGS:
            _, bomi = feed_pet("coriander", "bomi", lang)
            self.assertIn({"zh_TW": "芹菜", "ko": "샐러리", "en": "celery"}[lang], bomi)
            for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
                with self.subTest(member=member, lang=lang):
                    is_fav, line = feed_pet("coriander", member, lang)
                    self.assertFalse(is_fav)
                    self.assertNotIn("不挑食", line)
                    if lang != "zh_TW":
                        self.assertFalse(HAN.search(line), line)


if __name__ == "__main__":
    unittest.main()
