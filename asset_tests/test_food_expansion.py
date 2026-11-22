"""美食小食堂擴充 V1.0: 29 new foods (3 candidates already existed and were skipped)."""
from __future__ import annotations

import os
import sys
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from app.foods import (  # noqa: E402
    DRINK_KINDS,
    FOOD_ITEMS,
    FOOD_PREFERENCE_SOURCES,
    MEMBER_FAVORITE_REACTIONS_I18N,
    feed_pet,
    get_food_desc,
    get_food_kind,
    get_food_name,
)

FOODS_DIR = Path(__file__).resolve().parents[1] / "work" / "foods"
ORIGINAL_IDS = [
    "chicken_feet", "americano", "fried_chicken", "samgyeopsal", "tteokbokki", "waffle", "cola",
    "whiskey", "beer", "soju", "gopchang", "matcha_cake", "jajangmyeon", "eomuk_tang", "egg",
    "budae_jjigae", "kimchi_pork", "malatang", "burger", "strawberry", "bread", "sweet_potato",
    "mint_choco", "buldak", "chicken_breast", "coriander", "stinky_tofu",
]
NEW_MEALS = [
    "tw_beef_noodle", "tw_beef_soup", "tw_xiaolongbao", "tw_mala_dual_hotpot", "tw_intestine_vermicelli",
    "tw_gua_bao", "tw_chicken_cutlet", "tw_scallion_pancake",
    "tw_chili_wontons", "kr_corn_cheese", "kr_kotdoritang", "tw_potstickers", "tw_century_egg_tofu",
]
NEW_DESSERTS = [
    "tw_mango_shaved_ice", "tw_douhua", "tw_pineapple_cake", "tw_taro_ball_grass_jelly", "tw_egg_cakes",
    "tw_peanut_icecream_roll", "tw_sweet_potato_balls", "tw_brown_sugar_mochi",
]
NEW_DRINKS = [
    "tw_brown_sugar_boba", "tw_strawberry_boba", "tw_white_soymilk", "tw_black_soymilk", "tw_oolong_tea",
    "tw_mango_smoothie", "tw_wintermelon_tea", "tw_lemon_aiyu",
]
NEW_IDS = NEW_MEALS + NEW_DESSERTS + NEW_DRINKS
BY_ID = {f["id"]: f for f in FOOD_ITEMS}


def _enclosed_holes(alpha: Image.Image) -> int:
    """Transparent pixels not reachable from the border (a hole punched into the food)."""
    w, h = alpha.size
    px = alpha.load()
    seen = set()
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y] == 0 and (x, y) not in seen:
                seen.add((x, y))
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if px[x, y] == 0 and (x, y) not in seen:
                seen.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[nx, ny] == 0:
                seen.add((nx, ny))
                queue.append((nx, ny))
    return sum(1 for y in range(h) for x in range(w) if px[x, y] == 0 and (x, y) not in seen)


class FoodExpansionTest(unittest.TestCase):
    def test_all_favorites_have_dedicated_reactions_in_each_language(self):
        for food in FOOD_ITEMS:
            for member in food["favorites"]:
                with self.subTest(food=food["id"], member=member):
                    lines = MEMBER_FAVORITE_REACTIONS_I18N[food["id"], member]
                    self.assertEqual(set(lines), {"zh_TW", "ko", "en"})
                    for lang, line in lines.items():
                        self.assertTrue(line.strip())
                        self.assertEqual(feed_pet(food["id"], member, lang), (True, line))

    def test_original_menu_is_kept_in_order_and_new_foods_follow(self) -> None:
        ids = [f["id"] for f in FOOD_ITEMS]
        self.assertEqual(ids[:len(ORIGINAL_IDS)], ORIGINAL_IDS)
        self.assertEqual(ids[len(ORIGINAL_IDS):], NEW_IDS)
        self.assertEqual(len(ids), len(set(ids)))

    def test_duplicate_candidates_were_not_added_again(self) -> None:
        for dup in ("kr_fried_chicken", "kr_budae_jjigae", "kr_tteokbokki"):
            self.assertNotIn(dup, BY_ID)

    def test_categories(self) -> None:
        kinds = [get_food_kind(f) for f in FOOD_ITEMS]
        self.assertEqual((kinds.count("meal"), kinds.count("dessert"), sum(k in DRINK_KINDS for k in kinds)),
                         (30, 13, 13))
        for fid in NEW_MEALS:
            self.assertEqual(get_food_kind(BY_ID[fid]), "meal", fid)
        for fid in NEW_DESSERTS:
            self.assertEqual(get_food_kind(BY_ID[fid]), "dessert", fid)
        for fid in NEW_DRINKS:
            self.assertEqual(get_food_kind(BY_ID[fid]), "drink", fid)

    def test_names_and_descriptions_in_three_languages(self) -> None:
        for fid in NEW_IDS:
            food = BY_ID[fid]
            names = {lang: get_food_name(food, lang) for lang in ("zh_TW", "ko", "en")}
            with self.subTest(food=fid):
                self.assertEqual(names["zh_TW"], food["name"])
                self.assertEqual(len(set(names.values())), 3)
                for lang in ("zh_TW", "ko", "en"):
                    self.assertTrue(get_food_desc(food, lang).strip())

    def test_favorites_only_where_a_source_is_recorded(self) -> None:
        for fid in NEW_IDS:
            food = BY_ID[fid]
            with self.subTest(food=fid):
                self.assertFalse(food["universal"])
                self.assertNotIn("disliked", food)        # "tried once, unsure" is not a dislike
                for member in food["favorites"]:
                    self.assertIn((fid, member), FOOD_PREFERENCE_SOURCES)
        self.assertEqual({k for k in FOOD_PREFERENCE_SOURCES}, {
            ("tw_beef_noodle", "eunji"), ("tw_chili_wontons", "namjoo"), ("tw_white_soymilk", "namjoo"),
            ("tw_black_soymilk", "namjoo"), ("kr_kotdoritang", "hayoung")})
        self.assertEqual(BY_ID["tw_century_egg_tofu"]["favorites"], [])

    def test_feeding_new_foods(self) -> None:
        for fid in NEW_IDS:
            for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
                for lang in ("zh_TW", "ko", "en"):
                    favorite, text = feed_pet(fid, member, lang)
                    with self.subTest(food=fid, member=member, lang=lang):
                        self.assertEqual(favorite, member in BY_ID[fid]["favorites"])
                        self.assertTrue(text.strip())
                        self.assertNotIn("{food}", text)

    def test_icons_exist_at_both_sizes_without_holes(self) -> None:
        for fid in NEW_IDS:
            for suffix, size in (("", 128), ("_64", 64)):
                path = FOODS_DIR / f"{fid}{suffix}.png"
                with self.subTest(icon=path.name):
                    self.assertTrue(path.exists())
                    with Image.open(path) as im:
                        self.assertEqual((im.mode, im.size), ("RGBA", (size, size)))
                        alpha = im.getchannel("A")
                        box = alpha.getbbox()
                        self.assertIsNotNone(box)
                        self.assertTrue(box[0] > 0 and box[1] > 0 and box[2] < size and box[3] < size)
                        # white plates, buns, tofu, soy milk stay opaque; the crab's open
                        # pincers enclose 2 background pixels and are the only gap allowed
                        self.assertLessEqual(_enclosed_holes(alpha), 2)


if __name__ == "__main__":
    unittest.main()
