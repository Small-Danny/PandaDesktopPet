from __future__ import annotations

import unittest
from app.foods import (
    FOOD_ITEMS,
    feed_pet,
    get_food_name,
    get_food_desc,
    MEMBER_FAVORITE_REACTIONS_I18N,
    GENERIC_EAT_REACTIONS_I18N,
)
from app.personalities import get_member_badge, MEMBER_INFO
from app.status_card import MEMBER_THEMES, get_passion_tier
from app.i18n import t, get_member_display_name


class TestI18nFoodsAndStatus(unittest.TestCase):
    def test_hayoung_sweet_potato_lore(self) -> None:
        # Hayoung must have sweet potato as favorite
        sp = next(f for f in FOOD_ITEMS if f["id"] == "sweet_potato")
        self.assertIn("hayoung", sp.get("favorites", []))
        
        # Status card fav food
        fav_hayoung = MEMBER_THEMES["hayoung"]["fav_food"]
        self.assertIn("地瓜", fav_hayoung["zh_TW"])
        self.assertIn("군고구마", fav_hayoung["ko"])
        self.assertIn("Sweet Potato", fav_hayoung["en"])
        
        # Hayoung personality badge
        badge_zh = get_member_badge("hayoung", "zh_TW")
        badge_ko = get_member_badge("hayoung", "ko")
        badge_en = get_member_badge("hayoung", "en")
        self.assertIn("地瓜狂熱者", badge_zh)
        self.assertIn("군고구마 마니아", badge_ko)
        self.assertIn("Sweet Potato Fan", badge_en)
        self.assertIn("曼聯死忠粉", badge_zh)
        self.assertIn("맨유 찐팬", badge_ko)
        self.assertIn("Man Utd Fanatic", badge_en)

        # Hayoung also loves bread and tteokbokki, and does NOT have waffle/burger/strawberry as favorites
        bread = next(f for f in FOOD_ITEMS if f["id"] == "bread")
        self.assertIn("hayoung", bread.get("favorites", []))
        self.assertIn("麵包", fav_hayoung["zh_TW"])
        tb = next(f for f in FOOD_ITEMS if f["id"] == "tteokbokki")
        self.assertIn("hayoung", tb.get("favorites", []))
        for non_fav_id in ("waffle", "burger", "strawberry"):
            nf = next(f for f in FOOD_ITEMS if f["id"] == non_fav_id)
            self.assertNotIn("hayoung", nf.get("favorites", []))
        for word in ("鬆餅", "漢堡", "草莓"):
            self.assertNotIn(word, fav_hayoung["zh_TW"])

    def test_chorong_lore(self) -> None:
        # Chicken feet is universal favorite
        cf = next(f for f in FOOD_ITEMS if f["id"] == "chicken_feet")
        self.assertIn("chorong", cf.get("favorites", []))
        
        # Tteokbokki is favorite for Chorong
        tb = next(f for f in FOOD_ITEMS if f["id"] == "tteokbokki")
        self.assertIn("chorong", tb.get("favorites", []))
        
        # Status card fav food contains chicken feet and matcha and bread
        fav_chorong = MEMBER_THEMES["chorong"]["fav_food"]
        self.assertIn("雞爪", fav_chorong["zh_TW"])
        self.assertIn("抹茶", fav_chorong["zh_TW"])
        self.assertIn("말차", fav_chorong["ko"])
        self.assertIn("Matcha", fav_chorong["en"])
        self.assertNotIn("雞胸肉", fav_chorong["zh_TW"])

        # Matcha cake is favorite
        mc = next(f for f in FOOD_ITEMS if f["id"] == "matcha_cake")
        self.assertIn("chorong", mc.get("favorites", []))

    def test_bomi_lore(self) -> None:
        # Bomi loves Korean food: budae_jjigae, tteokbokki, eomuk_tang, kimchi_pork, jajangmyeon
        bj = next(f for f in FOOD_ITEMS if f["id"] == "budae_jjigae")
        self.assertIn("bomi", bj.get("favorites", []))
        tb = next(f for f in FOOD_ITEMS if f["id"] == "tteokbokki")
        self.assertIn("bomi", tb.get("favorites", []))
        jj = next(f for f in FOOD_ITEMS if f["id"] == "jajangmyeon")
        self.assertIn("bomi", jj.get("favorites", []))
        kp = next(f for f in FOOD_ITEMS if f["id"] == "kimchi_pork")
        self.assertIn("bomi", kp.get("favorites", []))
        
        # Bomi badge has Taekwondo 3rd dan
        badge_zh = get_member_badge("bomi", "zh_TW")
        badge_ko = get_member_badge("bomi", "ko")
        self.assertIn("跆拳道三段", badge_zh)
        self.assertIn("태권도 3단", badge_ko)

    def test_eunji_lore(self) -> None:
        # Eunji favorite is egg and budae jjigae, not tteokbokki
        egg = next(f for f in FOOD_ITEMS if f["id"] == "egg")
        self.assertIn("eunji", egg.get("favorites", []))
        tb = next(f for f in FOOD_ITEMS if f["id"] == "tteokbokki")
        self.assertNotIn("eunji", tb.get("favorites", []))
        
        # Status card
        fav_eunji = MEMBER_THEMES["eunji"]["fav_food"]
        self.assertIn("烤雞蛋", fav_eunji["zh_TW"])
        self.assertIn("달걀", fav_eunji["ko"])
        self.assertIn("Egg", fav_eunji["en"])
        
        # Badge
        badge_zh = get_member_badge("eunji", "zh_TW")
        self.assertIn("最愛吃雞蛋", badge_zh)

    def test_feed_multilingual_reactions(self) -> None:
        # Test feeding sweet potato to Hayoung in zh_TW, ko, en
        is_fav, react_zh = feed_pet("sweet_potato", "hayoung", lang="zh_TW")
        self.assertTrue(is_fav)
        self.assertIn("地瓜", react_zh)

        is_fav, react_ko = feed_pet("sweet_potato", "hayoung", lang="ko")
        self.assertTrue(is_fav)
        self.assertIn("군고구마", react_ko)

        is_fav, react_en = feed_pet("sweet_potato", "hayoung", lang="en")
        self.assertTrue(is_fav)
        self.assertIn("sweet potato", react_en.lower())

        # Test feeding egg to Eunji
        is_fav, react_zh = feed_pet("egg", "eunji", lang="zh_TW")
        self.assertTrue(is_fav)
        self.assertIn("蛋", react_zh)

        is_fav, react_ko = feed_pet("egg", "eunji", lang="ko")
        self.assertTrue(is_fav)
        self.assertIn("계란", react_ko)

    def test_all_universal_favorites_have_reactions(self) -> None:
        for f in FOOD_ITEMS:
            fid = f["id"]
            for m in f.get("favorites", []):
                is_fav, r_zh = feed_pet(fid, m, lang="zh_TW")
                is_fav, r_ko = feed_pet(fid, m, lang="ko")
                is_fav, r_en = feed_pet(fid, m, lang="en")
                self.assertTrue(is_fav)
                self.assertTrue(len(r_zh) > 0)
                self.assertTrue(len(r_ko) > 0)
                self.assertTrue(len(r_en) > 0)

    def test_passion_tier_i18n(self) -> None:
        lvl, tier_zh = get_passion_tier(1200, lang="zh_TW")
        lvl, tier_ko = get_passion_tier(1200, lang="ko")
        lvl, tier_en = get_passion_tier(1200, lang="en")
        self.assertIn("本命守護神", tier_zh)
        self.assertIn("최애 수호신", tier_ko)
        self.assertIn("Ultimate Guardian", tier_en)

    def test_disliked_foods(self) -> None:
        # Eunji dislikes coriander
        coriander = next(f for f in FOOD_ITEMS if f["id"] == "coriander")
        self.assertIn("eunji", coriander.get("disliked", []))

        is_fav, react_zh = feed_pet("coriander", "eunji", lang="zh_TW")
        self.assertFalse(is_fav)
        self.assertIn("香菜", react_zh)

        is_fav, react_ko = feed_pet("coriander", "eunji", lang="ko")
        self.assertFalse(is_fav)
        self.assertIn("고수", react_ko)

        # All members dislike stinky tofu
        stinky = next(f for f in FOOD_ITEMS if f["id"] == "stinky_tofu")
        for m in ["chorong", "bomi", "eunji", "namjoo", "hayoung"]:
            self.assertIn(m, stinky.get("disliked", []))
            is_fav, react = feed_pet("stinky_tofu", m, lang="zh_TW")
            self.assertFalse(is_fav)
            self.assertTrue(len(react) > 0)


if __name__ == "__main__":
    unittest.main()
