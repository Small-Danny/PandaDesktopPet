"""foods.py — Apink Panda member favorite foods and reaction dialogues.

Universal Favorites:
- 🐾 辣雞爪 (chicken_feet)
- ☕ 冰美式咖啡 (americano)
- 🍗 韓式炸雞 (fried_chicken)
- 🥩 烤五花肉 (samgyeopsal)

Member Specific Favorites:
- Chorong (初瓏): 抹茶蛋糕, 辣炒年糕, 現烤麵包 (＋全員最愛辣雞爪)
- Bomi (普美): 韓式餐點（部隊鍋泡麵, 辣炒年糕, 熱魚餅湯, 泡菜豬肉, 鐵盤烤牛腸, 炸醬麵）
- Eunji (恩地): 烤雞蛋, 部隊鍋泡麵, 鐵盤烤牛腸, 炸醬麵, 威士忌高球, 冰涼生啤酒, 韓國燒酒 (＋全員最愛辣雞爪/五花肉/炸雞)
- Namjoo (南珠): 辣炒年糕, 泡菜豬肉, 冰涼可樂 (＋全員最愛雞爪/五花肉/炸雞)
- Hayoung (夏榮): 烤地瓜, 現烤麵包, 辣炒年糕 (＋全員最愛雞爪)
"""
from __future__ import annotations

FOOD_ITEMS = [
    # Universal / Staples
    {
        "id": "chicken_feet",
        "name": "辣雞爪",
        "emoji": "🐾",
        "desc": "全員最愛！香辣過癮",
        "name_i18n": {"zh_TW": "辣雞爪", "ko": "매운 닭발", "en": "Spicy Chicken Feet"},
        "desc_i18n": {"zh_TW": "全員最愛！香辣過癮", "ko": "멤버 전원 최애! 매콤 중독", "en": "All Members' Fav! Spicy & Savory"},
        "universal": True,
        "favorites": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },
    {
        "id": "americano",
        "name": "冰美式咖啡",
        "emoji": "☕",
        "desc": "全員必喝！消水腫提神",
        "name_i18n": {"zh_TW": "冰美式咖啡", "ko": "아이스 아메리카노", "en": "Iced Americano"},
        "desc_i18n": {"zh_TW": "全員必喝！消水腫提神", "ko": "얼죽아 필수! 붓기 쏙 에너지 충전", "en": "Daily Essential! Refreshing Caffeine"},
        "universal": True,
        "favorites": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },
    {
        "id": "fried_chicken",
        "name": "韓式炸雞",
        "emoji": "🍗",
        "desc": "全員最愛！酥脆配醃蘿蔔",
        "name_i18n": {"zh_TW": "韓式炸雞", "ko": "바삭 양념치킨", "en": "Korean Fried Chicken"},
        "desc_i18n": {"zh_TW": "全員最愛！酥脆配醃蘿蔔", "ko": "멤버 전원 최애! 치킨무랑 찰떡궁합", "en": "All Members' Fav! Crispy & Juicy"},
        "universal": True,
        "favorites": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },
    {
        "id": "samgyeopsal",
        "name": "烤五花肉",
        "emoji": "🥩",
        "desc": "全員最愛！滋滋作響包生菜",
        "name_i18n": {"zh_TW": "烤五花肉", "ko": "노릇 삼겹살", "en": "Grilled Pork Belly"},
        "desc_i18n": {"zh_TW": "全員最愛！滋滋作響包生菜", "ko": "지글지글 쌈싸먹는 힐링 고기", "en": "Sizzling & Wrapped in Fresh Lettuce"},
        "universal": True,
        "favorites": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },

    # Member Specific Favorites
    {
        "id": "tteokbokki",
        "name": "辣炒年糕",
        "emoji": "🍢",
        "desc": "韓式街頭本命！甜辣 Q 彈",
        "name_i18n": {"zh_TW": "辣炒年糕", "ko": "매콤달콤 떡볶이", "en": "Spicy Tteokbokki"},
        "desc_i18n": {"zh_TW": "韓式街頭本命！甜辣 Q 彈", "ko": "매콤달콤 쫄깃한 국민 소울푸드", "en": "Chewy & Sweet-Spicy Street Soul Food"},
        "universal": False,
        "favorites": ["chorong", "bomi", "namjoo", "hayoung"],
    },
    {
        "id": "waffle",
        "name": "格子鬆餅",
        "emoji": "🧇",
        "desc": "外酥內軟！下午茶淋楓糖點心",
        "name_i18n": {"zh_TW": "格子鬆餅", "ko": "바삭 와플", "en": "Crispy Waffle"},
        "desc_i18n": {"zh_TW": "外酥內軟！下午茶淋楓糖點心", "ko": "메이플 시럽 듬뿍 바삭 달콤 디저트", "en": "Crispy Waffle Drizzled with Maple Syrup"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "cola",
        "name": "冰涼可樂",
        "emoji": "🥤",
        "desc": "南珠本命！氣泡暢快超爽口",
        "name_i18n": {"zh_TW": "冰涼可樂", "ko": "시원한 콜라", "en": "Iced Cola"},
        "desc_i18n": {"zh_TW": "南珠本命！氣泡暢快超爽口", "ko": "남주 최애! 톡 쏘는 탄산 청량감 폭발", "en": "Namjoo's Fav! Fizzy, Chilled & Refreshing"},
        "universal": False,
        "favorites": ["namjoo"],
    },
    {
        "id": "whiskey",
        "name": "威士忌高球",
        "emoji": "🥃",
        "desc": "恩地本命！《酒鬼都市》靈魂",
        "name_i18n": {"zh_TW": "威士忌高球", "ko": "위스키 하이볼", "en": "Whiskey Highball"},
        "desc_i18n": {"zh_TW": "恩地本命！《酒鬼都市》靈魂", "ko": "은지 최애! 《술도녀》 강지구 소울 드링크", "en": "Eunji's Fav! Work Later, Drink Now Vibe"},
        "universal": False,
        "favorites": ["eunji"],
    },
    {
        "id": "beer",
        "name": "冰涼生啤酒",
        "emoji": "🍺",
        "desc": "恩地本命！暢快泡沫下酒必備",
        "name_i18n": {"zh_TW": "冰涼生啤酒", "ko": "시원한 생맥주", "en": "Chilled Draft Beer"},
        "desc_i18n": {"zh_TW": "恩地本命！暢快泡沫下酒必備", "ko": "은지 최애! 부드러운 거품 캬~ 한잔의 행복", "en": "Eunji's Fav! Crisp Foam & Ultimate Chill"},
        "universal": False,
        "favorites": ["eunji"],
    },
    {
        "id": "soju",
        "name": "韓國燒酒",
        "emoji": "🍶",
        "desc": "恩地本命！綠瓶乾杯一口悶",
        "name_i18n": {"zh_TW": "韓國燒酒", "ko": "참이슬 소주", "en": "Korean Soju"},
        "desc_i18n": {"zh_TW": "恩地本命！綠瓶乾杯一口悶", "ko": "은지 최애! 초록병 짠~ 깔끔한 한잔", "en": "Eunji's Fav! Green Bottle Toast"},
        "universal": False,
        "favorites": ["eunji"],
    },
    {
        "id": "gopchang",
        "name": "鐵盤烤牛腸",
        "emoji": "🍖",
        "desc": "恩地、普美本命！頂級下酒菜",
        "name_i18n": {"zh_TW": "鐵盤烤牛腸", "ko": "철판 소곱창구이", "en": "Grilled Beef Tripe"},
        "desc_i18n": {"zh_TW": "恩地、普美本命！頂級下酒菜", "ko": "은지&보미 최애! 고소하고 쫄깃한 소곱창", "en": "Eunji & Bomi's Fav! Sizzling Delicacy"},
        "universal": False,
        "favorites": ["eunji", "bomi"],
    },
    {
        "id": "matcha_cake",
        "name": "抹茶蛋糕",
        "emoji": "🍵",
        "desc": "初瓏本命！濃郁抹茶甜點",
        "name_i18n": {"zh_TW": "抹茶蛋糕", "ko": "진한 말차 케이크", "en": "Rich Matcha Cake"},
        "desc_i18n": {"zh_TW": "初瓏本命！濃郁抹茶甜點", "ko": "초롱 최애! 달콤쌉싸름 힐링 디저트", "en": "Chorong's Fav! Smooth & Elegant Dessert"},
        "universal": False,
        "favorites": ["chorong"],
    },
    {
        "id": "jajangmyeon",
        "name": "炸醬麵",
        "emoji": "🥣",
        "desc": "普美、恩地本命！黑溜溜靈魂",
        "name_i18n": {"zh_TW": "炸醬麵", "ko": "감칠맛 짜장면", "en": "Savory Jajangmyeon"},
        "desc_i18n": {"zh_TW": "普美、恩地本命！黑溜溜靈魂", "ko": "보미&은지 최애! 후루룩 면치기 영혼의 맛", "en": "Bomi & Eunji's Fav! Black Bean Noodles"},
        "universal": False,
        "favorites": ["bomi", "eunji"],
    },
    {
        "id": "eomuk_tang",
        "name": "熱魚餅湯",
        "emoji": "🍢",
        "desc": "普美本命！暖胃魚餅串",
        "name_i18n": {"zh_TW": "熱魚餅湯", "ko": "따끈한 어묵탕", "en": "Hot Fish Cake Soup"},
        "desc_i18n": {"zh_TW": "普美本命！暖胃魚餅串", "ko": "보미 최애! 온몸이 사르르 녹는 어묵 꼬치", "en": "Bomi's Fav! Warm & Comforting Broth"},
        "universal": False,
        "favorites": ["bomi"],
    },
    {
        "id": "egg",
        "name": "烤雞蛋",
        "emoji": "🥚",
        "desc": "恩地本命！健身汗蒸幕烤蛋",
        "name_i18n": {"zh_TW": "烤雞蛋", "ko": "찜질방 구운 계란", "en": "Sauna Baked Egg"},
        "desc_i18n": {"zh_TW": "恩地本命！健身汗蒸幕烤蛋", "ko": "은지 최애! 헬스&사우나 필수 단백질", "en": "Eunji's Fav! Post-Workout Protein"},
        "universal": False,
        "favorites": ["eunji"],
    },
    {
        "id": "budae_jjigae",
        "name": "部隊鍋泡麵",
        "emoji": "🍲",
        "desc": "普美、恩地本命！正宗韓式濃湯拉麵",
        "name_i18n": {"zh_TW": "部隊鍋泡麵", "ko": "부대찌개 라면사리", "en": "Army Stew Ramen"},
        "desc_i18n": {"zh_TW": "普美、恩地本命！正宗韓式濃湯拉麵", "ko": "보미&은지 최애! 얼큰한 국물에 라면 퐁당", "en": "Bomi & Eunji's Fav! Spicy Korean Army Stew"},
        "universal": False,
        "favorites": ["bomi", "eunji"],
    },
    {
        "id": "kimchi_pork",
        "name": "泡菜豬肉",
        "emoji": "🥓",
        "desc": "南珠、普美本命！韓式酸辣白飯殺手",
        "name_i18n": {"zh_TW": "泡菜豬肉", "ko": "김치 제육볶음", "en": "Kimchi Stir-fried Pork"},
        "desc_i18n": {"zh_TW": "南珠、普美本命！韓式酸辣白飯殺手", "ko": "남주&보미 최애! 밥 두 공기 뚝딱 한식 밥도둑", "en": "Namjoo & Bomi's Fav! Savory Korean Rice Stealer"},
        "universal": False,
        "favorites": ["namjoo", "bomi"],
    },
    {
        "id": "malatang",
        "name": "麻辣燙",
        "emoji": "🌶️",
        "desc": "香麻濃郁！熱騰騰微辣湯底",
        "name_i18n": {"zh_TW": "麻辣燙", "ko": "중독성 마라탕", "en": "Flavorful Malatang"},
        "desc_i18n": {"zh_TW": "香麻濃郁！熱騰騰微辣湯底", "ko": "얼얼하고 진한 국물 요리", "en": "Numbing & Rich Broth Dish"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "burger",
        "name": "起司漢堡",
        "emoji": "🍔",
        "desc": "濃郁起司肉排！飽足感滿滿的速食點心",
        "name_i18n": {"zh_TW": "起司漢堡", "ko": "치즈 버거", "en": "Cheese Burger"},
        "desc_i18n": {"zh_TW": "濃郁起司肉排！飽足感滿滿的速食點心", "ko": "고소한 치즈와 두툼한 패티 간식", "en": "Savory Cheese & Juicy Patty Snack"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "strawberry",
        "name": "新鮮草莓",
        "emoji": "🍓",
        "desc": "酸甜多汁！補充維他命的新鮮水果",
        "name_i18n": {"zh_TW": "新鮮草莓", "ko": "달콤 상큼 생딸기", "en": "Fresh Strawberries"},
        "desc_i18n": {"zh_TW": "酸甜多汁！補充維他命的新鮮水果", "ko": "새콤달콤 상큼한 비타민 충전 과일", "en": "Sweet & Juicy Vitamin-Rich Berries"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "bread",
        "name": "現烤麵包",
        "emoji": "🍞",
        "desc": "夏榮、初瓏本命！剛出爐麵包控",
        "name_i18n": {"zh_TW": "現烤麵包", "ko": "갓 구운 빵", "en": "Fresh Baked Bread"},
        "desc_i18n": {"zh_TW": "夏榮、初瓏本命！剛出爐麵包控", "ko": "하영&초롱 최애! 따끈따끈 고소한 빵", "en": "Hayoung & Chorong's Fav! Fresh from Oven"},
        "universal": False,
        "favorites": ["hayoung", "chorong"],
    },
    {
        "id": "sweet_potato",
        "name": "烤地瓜",
        "emoji": "🍠",
        "desc": "夏榮本命！香甜軟糯暖心冬日",
        "name_i18n": {"zh_TW": "烤地瓜", "ko": "달콤 군고구마", "en": "Roasted Sweet Potato"},
        "desc_i18n": {"zh_TW": "夏榮本命！香甜軟糯暖心冬日", "ko": "하영 최애! 꿀 떨어지는 겨울 힐링 간식", "en": "Hayoung's Fav! Sweet & Cozy Winter Snack"},
        "universal": False,
        "favorites": ["hayoung"],
    },

    # Polarizing & Disliked Foods (兩極派系與趣味避雷美食)
    {
        "id": "mint_choco",
        "name": "薄荷巧克力",
        "emoji": "🍨",
        "desc": "民巧派大戰！初瓏普美超愛、恩地婉拒",
        "name_i18n": {"zh_TW": "薄荷巧克力", "ko": "민트초코 아이스크림", "en": "Mint Choco Ice Cream"},
        "desc_i18n": {
            "zh_TW": "民巧派大戰！初瓏普美超愛、恩地婉拒",
            "ko": "민초단 vs 반민초단! 초롱·보미 최애, 은지는 패스",
            "en": "Mint Choco Debate! Chorong & Bomi Love It, Eunji Passes",
        },
        "universal": False,
        "favorites": ["chorong", "bomi"],
        "disliked": ["eunji"],
    },
    {
        "id": "buldak",
        "name": "魔鬼辣雞麵",
        "emoji": "🔥",
        "desc": "極限爆辣挑戰！初瓏恩地怕辣求饒",
        "name_i18n": {"zh_TW": "魔鬼辣雞麵", "ko": "핵불닭볶음면", "en": "Fire Chicken Noodles"},
        "desc_i18n": {
            "zh_TW": "極限爆辣挑戰！初瓏恩地怕辣求饒",
            "ko": "극한의 매운맛! 남주·보미 도전, 맵찔이 초롱·은지 눈물",
            "en": "Extreme Spicy Challenge! Too Spicy for Chorong & Eunji",
        },
        "universal": False,
        "favorites": ["namjoo", "bomi"],
        "disliked": ["chorong", "eunji"],
    },
    {
        "id": "chicken_breast",
        "name": "水煮雞胸肉",
        "emoji": "🥗",
        "desc": "乾柴無調味！全員回歸期減肥噩夢",
        "name_i18n": {"zh_TW": "水煮雞胸肉", "ko": "퍽퍽한 닭가슴살", "en": "Dry Diet Chicken Breast"},
        "desc_i18n": {
            "zh_TW": "乾柴無調味！全員回歸期減肥噩夢",
            "ko": "무염 퍽퍽 식단! 멤버 전원 컴백 다이어트 악몽",
            "en": "Dry Unseasoned Diet Meal! Comeback Diet Nightmare",
        },
        "universal": False,
        "favorites": [],
        "disliked": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },
    {
        "id": "coriander",
        "name": "新鮮香菜",
        "emoji": "🌿",
        "desc": "恩地、初瓏都不吃！千萬別加香菜",
        "name_i18n": {"zh_TW": "新鮮香菜", "ko": "신선한 고수", "en": "Fresh Cilantro"},
        "desc_i18n": {"zh_TW": "恩地、初瓏都不吃！千萬別加香菜", "ko": "은지·초롱은 못 먹어요! 고수 절대 사절", "en": "Eunji & Chorong won't eat it! Zero Cilantro Please"},
        "universal": False,
        "favorites": [],
        # Eunji and Chorong said so themselves (user, 2026-11-07); Bomi eats it ("like celery").
        "disliked": ["eunji", "chorong", "namjoo", "hayoung"],
    },
    {
        "id": "stinky_tofu",
        "name": "夜市臭豆腐",
        "emoji": "🧄",
        "desc": "全員大逃亡！濃烈發酵氣味",
        "name_i18n": {"zh_TW": "夜市臭豆腐", "ko": "야시장 취두부", "en": "Stinky Tofu"},
        "desc_i18n": {"zh_TW": "全員大逃亡！濃烈發酵氣味", "ko": "멤버 전원 혼비백산! 냄새 쇼크", "en": "All Members Flee! Shocking Fermented Aroma"},
        "universal": False,
        "favorites": [],
        "disliked": ["chorong", "bomi", "eunji", "namjoo", "hayoung"],
    },
    # ── 美食小食堂擴充 V1.0: Taiwanese mains (A) ──
    {
        "id": "tw_beef_noodle",
        "name": "紅燒牛肉麵",
        "emoji": "🍜",
        "desc": "濃郁紅燒湯頭配軟嫩牛肉",
        "name_i18n": {"zh_TW": "紅燒牛肉麵", "ko": "대만 우육면", "en": "Taiwanese Beef Noodle Soup"},
        "desc_i18n": {"zh_TW": "濃郁紅燒湯頭配軟嫩牛肉", "ko": "진한 홍소 국물에 부드러운 소고기", "en": "Rich Braised Broth & Tender Beef"},
        "universal": False,
        "favorites": ["eunji"],
    },
    {
        "id": "tw_beef_soup",
        "name": "台南牛肉湯",
        "emoji": "🥣",
        "desc": "熱湯現沖鮮甜牛肉片",
        "name_i18n": {"zh_TW": "台南牛肉湯", "ko": "타이난 소고기탕", "en": "Tainan Beef Soup"},
        "desc_i18n": {"zh_TW": "熱湯現沖鮮甜牛肉片", "ko": "뜨거운 국물을 부은 신선한 소고기", "en": "Fresh Beef Slices in Piping-Hot Broth"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_xiaolongbao",
        "name": "小籠包",
        "emoji": "🥟",
        "desc": "薄皮多汁一口爆湯",
        "name_i18n": {"zh_TW": "小籠包", "ko": "샤오룽바오", "en": "Xiaolongbao Soup Dumplings"},
        "desc_i18n": {"zh_TW": "薄皮多汁一口爆湯", "ko": "얇은 피 속 뜨끈한 육즙 가득", "en": "Thin Skin, Bursting with Soup"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_mala_dual_hotpot",
        "name": "台式麻辣鴛鴦鍋",
        "emoji": "🍲",
        "desc": "麻辣紅湯配白湯一次滿足",
        "name_i18n": {"zh_TW": "台式麻辣鴛鴦鍋", "ko": "대만식 마라 원앙 훠궈", "en": "Taiwanese Dual-Broth Mala Hot Pot"},
        "desc_i18n": {"zh_TW": "麻辣紅湯配白湯一次滿足", "ko": "마라 홍탕과 백탕을 한 번에", "en": "Spicy Red & Mild White Broth in One Pot"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_intestine_vermicelli",
        "name": "大腸麵線",
        "emoji": "🍜",
        "desc": "柴魚香濃稠麵線配滷大腸",
        "name_i18n": {"zh_TW": "大腸麵線", "ko": "대만식 곱창국수", "en": "Taiwanese Intestine Vermicelli"},
        "desc_i18n": {"zh_TW": "柴魚香濃稠麵線配滷大腸", "ko": "가쓰오 향 걸쭉한 국수와 곱창", "en": "Thick Bonito Broth with Braised Intestine"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_gua_bao",
        "name": "刈包",
        "emoji": "🥙",
        "desc": "軟綿刈包夾滷肉花生粉",
        "name_i18n": {"zh_TW": "刈包", "ko": "대만식 과바오", "en": "Taiwanese Gua Bao"},
        "desc_i18n": {"zh_TW": "軟綿刈包夾滷肉花生粉", "ko": "폭신한 빵에 조림 고기와 땅콩가루", "en": "Soft Bun with Braised Pork & Peanut Powder"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_chicken_cutlet",
        "name": "台式雞排",
        "emoji": "🍗",
        "desc": "比臉還大的酥脆雞排",
        "name_i18n": {"zh_TW": "台式雞排", "ko": "대만식 대형 닭튀김", "en": "Taiwanese XXL Chicken Cutlet"},
        "desc_i18n": {"zh_TW": "比臉還大的酥脆雞排", "ko": "얼굴보다 큰 바삭한 닭튀김", "en": "Crispy Cutlet Bigger Than Your Face"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_scallion_pancake",
        "name": "蔥油餅",
        "emoji": "🫓",
        "desc": "外酥內軟滿滿蔥香",
        "name_i18n": {"zh_TW": "蔥油餅", "ko": "대만식 파전병", "en": "Taiwanese Scallion Pancake"},
        "desc_i18n": {"zh_TW": "外酥內軟滿滿蔥香", "ko": "겉바속촉 파 향 가득", "en": "Flaky, Chewy & Full of Scallion"},
        "universal": False,
        "favorites": [],
    },
    # ── 美食小食堂擴充 V1.0: memory mains (B; fried chicken / army stew / tteokbokki already exist) ──
    {
        "id": "tw_chili_wontons",
        "name": "珍珠抄手",
        "emoji": "🥟",
        "desc": "滑嫩抄手淋香辣紅油",
        "name_i18n": {"zh_TW": "珍珠抄手", "ko": "대만식 매콤 완탕", "en": "Taiwanese Chili Wontons"},
        "desc_i18n": {"zh_TW": "滑嫩抄手淋香辣紅油", "ko": "매콤한 홍유를 두른 부드러운 완탕", "en": "Silky Wontons in Spicy Chili Oil"},
        "universal": False,
        "favorites": ["namjoo"],
    },
    {
        "id": "kr_corn_cheese",
        "name": "韓式玉米起司",
        "emoji": "🌽",
        "desc": "甜玉米配牽絲起司",
        "name_i18n": {"zh_TW": "韓式玉米起司", "ko": "한국식 콘치즈", "en": "Korean Corn Cheese"},
        "desc_i18n": {"zh_TW": "甜玉米配牽絲起司", "ko": "달콤한 옥수수에 쭉 늘어나는 치즈", "en": "Sweet Corn with Stretchy Cheese"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "kr_kotdoritang",
        "name": "花蟹雞肉年糕辣鍋",
        "emoji": "🦀",
        "desc": "花蟹、雞肉、年糕香辣燉鍋",
        "name_i18n": {"zh_TW": "花蟹雞肉年糕辣鍋", "ko": "꽃도리탕", "en": "Flower Crab Chicken Tteokbokki Stew"},
        "desc_i18n": {"zh_TW": "花蟹、雞肉、年糕香辣燉鍋", "ko": "꽃게·닭고기·떡이 듬뿍 매콤 전골", "en": "Spicy Stew with Crab, Chicken & Rice Cakes"},
        "universal": False,
        "favorites": ["hayoung"],
    },
    {
        "id": "tw_potstickers",
        "name": "台式鍋貼",
        "emoji": "🥟",
        "desc": "金黃脆底一咬噴汁",
        "name_i18n": {"zh_TW": "台式鍋貼", "ko": "대만식 군만두", "en": "Taiwanese Pan-Fried Potstickers"},
        "desc_i18n": {"zh_TW": "金黃脆底一咬噴汁", "ko": "노릇한 바닥에 육즙 팡", "en": "Golden Crispy Bottoms, Juicy Inside"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_century_egg_tofu",
        "name": "皮蛋豆腐",
        "emoji": "🥚",
        "desc": "滑嫩豆腐配皮蛋醬油膏",
        "name_i18n": {"zh_TW": "皮蛋豆腐", "ko": "피단 두부", "en": "Century Egg with Silken Tofu"},
        "desc_i18n": {"zh_TW": "滑嫩豆腐配皮蛋醬油膏", "ko": "부드러운 두부에 피단과 간장 소스", "en": "Silken Tofu with Century Egg & Soy Glaze"},
        "universal": False,
        "favorites": [],
    },
    # ── 美食小食堂擴充 V1.0: Taiwanese desserts (C) ──
    {
        "id": "tw_mango_shaved_ice",
        "name": "芒果雪花冰",
        "emoji": "🥭",
        "desc": "綿密雪花冰堆滿芒果",
        "name_i18n": {"zh_TW": "芒果雪花冰", "ko": "망고 빙수", "en": "Mango Shaved Ice"},
        "desc_i18n": {"zh_TW": "綿密雪花冰堆滿芒果", "ko": "눈꽃 빙수에 망고 듬뿍", "en": "Fluffy Snow Ice Piled with Mango"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_douhua",
        "name": "台灣豆花",
        "emoji": "🍮",
        "desc": "嫩豆花配粉圓紅豆糖水",
        "name_i18n": {"zh_TW": "台灣豆花", "ko": "대만식 두화", "en": "Taiwanese Tofu Pudding"},
        "desc_i18n": {"zh_TW": "嫩豆花配粉圓紅豆糖水", "ko": "연두부에 타피오카·팥 시럽", "en": "Silky Tofu Pudding with Boba & Red Beans"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_pineapple_cake",
        "name": "鳳梨酥",
        "emoji": "🍍",
        "desc": "酥鬆外皮包酸甜鳳梨餡",
        "name_i18n": {"zh_TW": "鳳梨酥", "ko": "대만식 파인애플 케이크", "en": "Taiwanese Pineapple Cake"},
        "desc_i18n": {"zh_TW": "酥鬆外皮包酸甜鳳梨餡", "ko": "바삭한 겉에 새콤달콤 파인애플 소", "en": "Buttery Crust with Tangy Pineapple Filling"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_taro_ball_grass_jelly",
        "name": "芋圓仙草",
        "emoji": "🍡",
        "desc": "Q彈芋圓配清涼仙草",
        "name_i18n": {"zh_TW": "芋圓仙草", "ko": "타로볼 선초 젤리", "en": "Taro Balls and Grass Jelly"},
        "desc_i18n": {"zh_TW": "Q彈芋圓配清涼仙草", "ko": "쫀득한 타로볼과 시원한 선초", "en": "Chewy Taro Balls with Cool Grass Jelly"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_egg_cakes",
        "name": "台灣雞蛋糕",
        "emoji": "🧁",
        "desc": "現烤小熊造型雞蛋糕",
        "name_i18n": {"zh_TW": "台灣雞蛋糕", "ko": "대만식 계란빵", "en": "Taiwanese Egg Cakes"},
        "desc_i18n": {"zh_TW": "現烤小熊造型雞蛋糕", "ko": "갓 구운 곰돌이 모양 계란빵", "en": "Freshly Baked Bear-Shaped Egg Cakes"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_peanut_icecream_roll",
        "name": "花生捲冰淇淋",
        "emoji": "🌯",
        "desc": "花生糖粉配冰淇淋捲餅",
        "name_i18n": {"zh_TW": "花生捲冰淇淋", "ko": "땅콩 아이스크림 롤", "en": "Peanut Ice Cream Roll"},
        "desc_i18n": {"zh_TW": "花生糖粉配冰淇淋捲餅", "ko": "땅콩가루와 아이스크림을 만 전병", "en": "Ice Cream & Peanut Brittle in a Crepe"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_sweet_potato_balls",
        "name": "地瓜球",
        "emoji": "🍠",
        "desc": "空心酥脆一顆接一顆",
        "name_i18n": {"zh_TW": "地瓜球", "ko": "대만식 고구마볼", "en": "Taiwanese Sweet Potato Balls"},
        "desc_i18n": {"zh_TW": "空心酥脆一顆接一顆", "ko": "속이 빈 바삭한 고구마볼", "en": "Crispy, Hollow & Addictive"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_brown_sugar_mochi",
        "name": "黑糖麻糬",
        "emoji": "🍡",
        "desc": "軟糯麻糬淋黑糖蜜",
        "name_i18n": {"zh_TW": "黑糖麻糬", "ko": "흑당 모찌", "en": "Brown Sugar Mochi"},
        "desc_i18n": {"zh_TW": "軟糯麻糬淋黑糖蜜", "ko": "쫀득한 모찌에 흑당 시럽", "en": "Chewy Mochi Drizzled in Brown Sugar"},
        "universal": False,
        "favorites": [],
    },
    # ── 美食小食堂擴充 V1.0: Taiwanese drinks (D) ──
    {
        "id": "tw_brown_sugar_boba",
        "name": "黑糖珍珠鮮奶茶",
        "emoji": "🧋",
        "desc": "虎紋黑糖珍珠配鮮奶",
        "name_i18n": {"zh_TW": "黑糖珍珠鮮奶茶", "ko": "흑당 버블 밀크티", "en": "Brown Sugar Bubble Milk Tea"},
        "desc_i18n": {"zh_TW": "虎紋黑糖珍珠配鮮奶", "ko": "호랑이 무늬 흑당 펄에 우유", "en": "Tiger-Striped Brown Sugar Boba & Fresh Milk"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_strawberry_boba",
        "name": "草莓牛奶珍珠奶茶",
        "emoji": "🍓",
        "desc": "草莓牛奶加Q彈珍珠",
        "name_i18n": {"zh_TW": "草莓牛奶珍珠奶茶", "ko": "딸기 버블 밀크티", "en": "Strawberry Milk Bubble Tea"},
        "desc_i18n": {"zh_TW": "草莓牛奶加Q彈珍珠", "ko": "딸기우유에 쫀득한 펄", "en": "Strawberry Milk with Chewy Pearls"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_white_soymilk",
        "name": "白豆漿",
        "emoji": "🥛",
        "desc": "香濃現磨白豆漿",
        "name_i18n": {"zh_TW": "白豆漿", "ko": "흰 두유", "en": "White Soy Milk"},
        "desc_i18n": {"zh_TW": "香濃現磨白豆漿", "ko": "고소하게 갈아낸 흰 두유", "en": "Freshly Ground, Rich & Nutty"},
        "universal": False,
        "favorites": ["namjoo"],
    },
    {
        "id": "tw_black_soymilk",
        "name": "黑豆漿",
        "emoji": "🫘",
        "desc": "黑豆現磨醇厚豆香",
        "name_i18n": {"zh_TW": "黑豆漿", "ko": "검은콩 두유", "en": "Black Soy Milk"},
        "desc_i18n": {"zh_TW": "黑豆現磨醇厚豆香", "ko": "검은콩을 갈아낸 깊은 고소함", "en": "Freshly Ground Black Bean Goodness"},
        "universal": False,
        "favorites": ["namjoo"],
    },
    {
        "id": "tw_oolong_tea",
        "name": "台灣烏龍茶",
        "emoji": "🍵",
        "desc": "高山烏龍回甘茶香",
        "name_i18n": {"zh_TW": "台灣烏龍茶", "ko": "대만 우롱차", "en": "Taiwanese Oolong Tea"},
        "desc_i18n": {"zh_TW": "高山烏龍回甘茶香", "ko": "고산 우롱차의 은은한 단맛", "en": "High-Mountain Tea with a Sweet Finish"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_mango_smoothie",
        "name": "芒果冰沙",
        "emoji": "🥭",
        "desc": "整顆芒果打成冰沙",
        "name_i18n": {"zh_TW": "芒果冰沙", "ko": "망고 스무디", "en": "Mango Smoothie"},
        "desc_i18n": {"zh_TW": "整顆芒果打成冰沙", "ko": "망고를 통째로 간 스무디", "en": "Whole Mangoes Blended Icy Smooth"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_wintermelon_tea",
        "name": "冬瓜茶",
        "emoji": "🧊",
        "desc": "古早味冬瓜糖茶",
        "name_i18n": {"zh_TW": "冬瓜茶", "ko": "대만 동과차", "en": "Taiwanese Winter Melon Tea"},
        "desc_i18n": {"zh_TW": "古早味冬瓜糖茶", "ko": "옛날 맛 동과차", "en": "Old-School Sweet Winter Melon Tea"},
        "universal": False,
        "favorites": [],
    },
    {
        "id": "tw_lemon_aiyu",
        "name": "檸檬愛玉飲",
        "emoji": "🍋",
        "desc": "檸檬配Q彈愛玉凍",
        "name_i18n": {"zh_TW": "檸檬愛玉飲", "ko": "레몬 아이위 젤리 음료", "en": "Lemon Aiyu Jelly Drink"},
        "desc_i18n": {"zh_TW": "檸檬配Q彈愛玉凍", "ko": "레몬에 쫀득한 아이위 젤리", "en": "Lemon with Wobbly Aiyu Jelly"},
        "universal": False,
        "favorites": [],
    },
]

# Where each new favorite comes from (美食小食堂擴充 V1.0 research, sources S0x in that document).
# Eaten-once, group wishes and "tried it, wasn't sure" stay neutral: no favorite, no dislike.
FOOD_PREFERENCE_SOURCES: dict[tuple[str, str], str] = {
    ("tw_beef_noodle", "eunji"): "S05 中央社 2023-04-02; S06 聯合報 2025-05-23; S07 NOWnews 2026-08",
    ("tw_chili_wontons", "namjoo"): "S08 民視 2024-06-16",
    ("tw_white_soymilk", "namjoo"): "S08 民視 2024-06-16",
    ("tw_black_soymilk", "namjoo"): "S08 民視 2024-06-16",
    ("kr_kotdoritang", "hayoung"): "S02 OSEN 2019",
}


def get_food_name(food: dict, lang: str = "zh_TW") -> str:
    i18n = food.get("name_i18n", {})
    return i18n.get(lang, food.get("name", ""))


def get_food_desc(food: dict, lang: str = "zh_TW") -> str:
    i18n = food.get("desc_i18n", {})
    return i18n.get(lang, food.get("desc", ""))


MEMBER_FAVORITE_REACTIONS_I18N: dict[tuple[str, str], dict[str, str]] = {
    ("tw_beef_noodle", "eunji"): {
        "zh_TW": "牛肉麵！先讓我喝一口湯……哇，這碗的好喝程度值得我唱三個高音！🍜",
        "ko": "우육면이다! 국물부터 한입만… 와, 이 맛이면 3단 고음도 나오겠는데? 🍜",
        "en": "Beef noodle soup! Let me try the broth first… Wow, that deserves three high notes! 🍜",
    },
    ("tw_chili_wontons", "namjoo"): {
        "zh_TW": "紅油抄手！看起來很辣，但這個香味……等一下，我再吃一顆再說！🌶️",
        "ko": "홍유초수다! 매워 보이는데 향이 너무 좋아… 잠깐, 한 알만 더 먹고 얘기할게요! 🌶️",
        "en": "Chili wontons! They look spicy, but they smell so good… Hang on, one more before we talk! 🌶️",
    },
    ("kr_kotdoritang", "hayoung"): {
        "zh_TW": "花蟹雞肉年糕鍋！先夾吸滿湯汁的年糕，這是我的第一步攻略。下一步就是開吃！🎮",
        "ko": "꽃도리탕이다! 국물 밴 떡부터 건지는 게 제 공략 1단계예요. 다음은 먹기! 🎮",
        "en": "Crab and chicken stew! Step one of my strategy: grab a rice cake soaked in broth. Step two: dig in! 🎮",
    },
    ("tw_white_soymilk", "namjoo"): {
        "zh_TW": "是白豆漿！喝起來香香滑滑的，配早餐正好。我可以先偷喝一口嗎？🥛",
        "ko": "흰콩 두유네요! 고소하고 부드러워서 아침에 딱이에요. 저 먼저 한 모금 마셔도 돼요? 🥛",
        "en": "White soy milk! It's smooth and nutty, just right for breakfast. Can I sneak a sip now? 🥛",
    },
    ("tw_black_soymilk", "namjoo"): {
        "zh_TW": "黑豆漿！這杯豆香好濃，我要慢慢喝，留到最後一口也捨不得放下。🥛",
        "ko": "검은콩 두유다! 콩 향이 진해서 한 모금씩 아껴 마실래요. 마지막 한 모금까지! 🥛",
        "en": "Black soy milk! That rich bean flavor is so good. I'm going to savor it down to the last sip. 🥛",
    },
    # Universal: Chicken Feet
    ("chicken_feet", "chorong"): {
        "zh_TW": "隊長認證！辣雞爪就是最棒的應援美食～💖",
        "ko": "롱리더 인증! 매운 닭발은 최고의 힐링 푸드야～💖",
        "en": "Leader approved! Spicy chicken feet are the best cheer food~ 💖",
    },
    ("chicken_feet", "bomi"): {
        "zh_TW": "대박! 這就是我朝思暮想的辣雞爪！好吃到流淚～😋🔥",
        "ko": "대박! 내가 꿈에서도 찾던 그 닭발이야! 눈물 나게 맛있어～😋🔥",
        "en": "Daebak! The spicy chicken feet I've been dreaming of! So delicious~ 😋🔥",
    },
    ("chicken_feet", "eunji"): {
        "zh_TW": "辣雞爪配一口飲料，嗓子跟精力都滿血復活！🎤🔥",
        "ko": "매운 닭발에 음료 한 모금, 목소리랑 에너지가 풀충전됐어! 🎤🔥",
        "en": "Spicy chicken feet and a drink, fully recharged my voice and energy! 🎤🔥",
    },
    ("chicken_feet", "namjoo"): {
        "zh_TW": "辣雞爪最高！又香又辣完全停不下來～✨",
        "ko": "닭발 최고! 맵싹달콤해서 멈출 수가 없어～✨",
        "en": "Spicy chicken feet are the best! Can't stop eating~ ✨",
    },
    ("chicken_feet", "hayoung"): {
        "zh_TW": "一邊啃雞爪一邊打遊戲最幸福了～🎮🐾",
        "ko": "닭발 뜯으면서 랭크 게임하는 게 제일 행복해～🎮🐾",
        "en": "Gaming while munching on spicy chicken feet is pure bliss~ 🎮🐾",
    },

    # Universal: Americano
    ("americano", "chorong"): {
        "zh_TW": "冰美式超提神！今天也一起優雅地加油吧～☕💖",
        "ko": "아아 마시고 에너지 뿜뿜! 오늘도 우아하게 파이팅해요～☕💖",
        "en": "Iced Americano is so refreshing! Let's do our best today~ ☕💖",
    },
    ("americano", "bomi"): {
        "zh_TW": "啊～冰美式一口喝下去，整個人都清醒了！⚡",
        "ko": "캬～ 아아 한 모금에 온몸 세포가 번쩍 깨어났어! ⚡",
        "en": "Ah~ One sip of Iced Americano wakes up all my senses! ⚡",
    },
    ("americano", "eunji"): {
        "zh_TW": "冰美式續命成功！高音飆得更輕鬆了，화이팅！🎶",
        "ko": "아아로 생명 연장 성공! 고음도 시원하게 빵빵, 화이팅! 🎶",
        "en": "Iced Americano to the rescue! Hitting high notes with ease now, Fighting! 🎶",
    },
    ("americano", "namjoo"): {
        "zh_TW": "最愛冰美式！水腫通通退散，精神百倍！☕✨",
        "ko": "내 사랑 아아! 붓기 싹 빠지고 텐션 200% UP! ☕✨",
        "en": "Love Iced Americano! Puffiness gone, energy doubled! ☕✨",
    },
    ("americano", "hayoung"): {
        "zh_TW": "喝了冰美式打排位戰都不會累～☕🕹️",
        "ko": "아아 한 잔 마셨으니 밤샘 랭크전도 끄떡없어～☕🕹️",
        "en": "With an Iced Americano, I can rank up all night without fatigue~ ☕🕹️",
    },

    # Universal: Fried Chicken & Samgyeopsal
    ("fried_chicken", "chorong"): {
        "zh_TW": "香脆多汁的韓式炸雞！配醃蘿蔔吃最解膩了～🍗✨",
        "ko": "바삭하고 육즙 가득한 양념치킨! 아삭한 치킨무랑 먹으면 꿀맛～🍗✨",
        "en": "Crispy and juicy Korean fried chicken! Perfect with pickled radish~ 🍗✨",
    },
    ("fried_chicken", "bomi"): {
        "zh_TW": "哇！炸雞！外皮超酥脆肉質超嫩，普美一整隻都能吃光光～🍗😋",
        "ko": "우와! 치킨이다! 겉바속촉 제대로다, 뽀미 혼자 1인 1닭 가능～🍗😋",
        "en": "Whoa! Fried chicken! Super crispy outside and tender inside, Bomi can eat a whole chicken~ 🍗😋",
    },
    ("fried_chicken", "namjoo"): {
        "zh_TW": "酥脆炸雞配醃蘿蔔！這就是食神南珠的人生真理！🍗✨",
        "ko": "바삭한 치킨에 새콤한 치킨무! 식신 남주의 인생 진리야! 🍗✨",
        "en": "Crispy fried chicken with pickled radish! Namjoo's life truth! 🍗✨",
    },
    ("fried_chicken", "eunji"): {
        "zh_TW": "炸雞配啤酒，人間絕配！치맥 (炸雞生啤) 萬歲！🍗🍺",
        "ko": "치킨엔 역시 맥주지! 치맥 만세, 영혼의 단짝! 🍗🍺",
        "en": "Fried chicken and draft beer, heaven on earth! Chimaek forever! 🍗🍺",
    },
    ("fried_chicken", "hayoung"): {
        "zh_TW": "炸雞來了！一邊打排位賽一邊吃炸雞簡直是最頂級的享受～🍗🎮",
        "ko": "치킨 도착! 랭겜 돌리면서 먹는 치킨이 세상에서 제일 맛있어요～🍗🎮",
        "en": "Fried chicken is here! Eating fried chicken while playing ranked games is peak life~ 🍗🎮",
    },
    ("samgyeopsal", "chorong"): {
        "zh_TW": "滋滋作響的烤五花肉！包著生菜和大蒜一口塞進嘴裡超幸福～🥩🥬",
        "ko": "지글지글 구운 삼겹살! 상추쌈에 마늘 얹어서 한입 가득 먹으면 찐행복～🥩🥬",
        "en": "Sizzling pork belly! Wrapping it in lettuce with fresh garlic is pure bliss~ 🥩🥬",
    },
    ("samgyeopsal", "bomi"): {
        "zh_TW": "五花肉在鐵盤上滋滋作響！包兩片大蒜一大口塞進嘴裡～🥩😋",
        "ko": "불판 위에서 지글지글 삼겹살! 마늘 두 쪽 얹어서 한 쌈 크게 냠냠～🥩😋",
        "en": "Sizzling pork belly on the grill! Wrapped in lettuce with garlic in one big bite~ 🥩😋",
    },
    ("samgyeopsal", "eunji"): {
        "zh_TW": "這五花肉烤得焦香四溢！再配一口燒酒就是人生的真諦啊～🥩🍶",
        "ko": "삼겹살 노릇노릇 제대로 구웠네! 여기에 소주 한잔 곁들이면 인생 끝장이지～🥩🍶",
        "en": "This pork belly is grilled to perfection! A sip of soju with it is what life's all about~ 🥩🍶",
    },
    ("samgyeopsal", "namjoo"): {
        "zh_TW": "烤得焦香金黃的五花肉！這才是頂級美食享受～🥩🔥",
        "ko": "노릇노릇 바삭하게 구워진 삼겹살! 역시 고기는 진리야～🥩🔥",
        "en": "Golden crispy grilled pork belly! The ultimate gourmet comfort~ 🥩🔥",
    },
    ("samgyeopsal", "hayoung"): {
        "zh_TW": "油香四溢的烤五花肉！補充蛋白質今晚打團戰力爆表～🥩🔥",
        "ko": "고소한 육즙 폭발 삼겹살! 단백질 보충하고 오늘 밤 팀전 캐리 간다～🥩🔥",
        "en": "Juicy and savory pork belly! Protein refuel so I can carry the team tonight~ 🥩🔥",
    },

    # Alcohol & Bar Food for Eunji
    ("whiskey", "eunji"): {
        "zh_TW": "캬~ 這杯威士忌太懂了！《酒鬼都市》智久上身，乾杯！🥃✨",
        "ko": "캬~ 위스키 한 잔 제대로네! 《술도녀》 강지구 모드 돌입, 짠! 🥃✨",
        "en": "Cheers! A glass of whiskey hit the spot~ Work Later Drink Now! 🥃✨",
    },
    ("beer", "eunji"): {
        "zh_TW": "哈～冰涼生啤一口入魂！這才是人生最高享受，짠 (乾杯)！🍺😆",
        "ko": "하～ 시원한 생맥주 첫 모금의 전율! 이게 바로 인생이지, 짠! 🍺😆",
        "en": "Ha~ Chilled draft beer hits the soul! This is pure happiness, cheers! 🍺😆",
    },
    ("soju", "eunji"): {
        "zh_TW": "綠瓶燒酒一口乾！鄭恩地酒量可不是開玩笑的，再來一杯！🍶🔥",
        "ko": "초록병 소주 원샷! 정은지 주량 알잖아? 한 잔 더 고고! 🍶🔥",
        "en": "One-shot green bottle soju! Jeong Eunji's alcohol tolerance is no joke, cheers! 🍶🔥",
    },
    ("gopchang", "eunji"): {
        "zh_TW": "烤牛腸烤到金黃焦脆！配燒酒簡直是天堂的味道～🍖✨",
        "ko": "노릇노릇 고소하게 구운 소곱창! 소주랑 환상의 짝꿍이야～🍖✨",
        "en": "Sizzling golden crispy beef tripe! Tastes like heaven with soju~ 🍖✨",
    },
    ("gopchang", "bomi"): {
        "zh_TW": "香噴噴的鐵盤烤牛腸！外酥內嫩太好吃了～🍖😋",
        "ko": "고소한 기름 팡팡 소곱창! 쫄깃쫄깃 너무 맛있어～🍖😋",
        "en": "Fragrant grilled tripe on iron plate! Crispy outside, tender inside~ 🍖😋",
    },

    # Tteokbokki
    ("tteokbokki", "chorong"): {
        "zh_TW": "天哪！辣炒年糕太好吃了，甜甜辣辣完全停不下來～🍢💖",
        "ko": "어머나! 떡볶이가 너무 쫄깃하고 달콤매콤해, 멈출 수 없어～🍢💖",
        "en": "Oh my! The tteokbokki is so chewy and sweet-spicy, can't stop eating~ 🍢💖",
    },
    ("tteokbokki", "bomi"): {
        "zh_TW": "대박! 辣炒年糕軟糯又甜辣！正宗韓式分食我可以吃三大盤～🍢😋",
        "ko": "대박! 매콤달콤 쫄깃한 떡볶이! 나 세 그릇도 먹을 수 있어～🍢😋",
        "en": "Daebak! Sweet and spicy chewy rice cakes! I can finish 3 plates~ 🍢😋",
    },
    ("tteokbokki", "namjoo"): {
        "zh_TW": "是辣炒年糕！這就是我連飲食管理時都朝思暮想的靈魂美食～🍢☀️",
        "ko": "떡볶이다! 식단 관리할 때도 제일 생각나던 내 소울푸드야～🍢☀️",
        "en": "Tteokbokki! The ultimate soul food I crave even on strict diet days~ 🍢☀️",
    },
    ("tteokbokki", "hayoung"): {
        "zh_TW": "哇～是充滿回憶的甜辣炒年糕！忙內最愛這種甜甜辣辣的味道了～🍢🥰",
        "ko": "와～ 추억이 담긴 매콤달콤 떡볶이! 막내 취향 저격이에요～🍢🥰",
        "en": "Wow~ Sweet and spicy tteokbokki full of memories! Maknae's absolute favorite~ 🍢🥰",
    },

    # Cola for Namjoo
    ("cola", "namjoo"): {
        "zh_TW": "哈～大口灌下冰可樂！氣泡感超刺激，整個人都爽快了！🥤✨",
        "ko": "캬～ 시원한 콜라 벌컥벌컥! 탄산 톡톡 터지는 청량감 최고! 🥤✨",
        "en": "Ha~ Gulping down cold cola! Fizzy bubbles bursting with refreshness! 🥤✨",
    },

    # Classics
    ("matcha_cake", "chorong"): {
        "zh_TW": "진짜?! 是我最愛的抹茶蛋糕！抹茶味超濃郁，太幸福了～🍵💖",
        "ko": "진짜?! 내가 제일 좋아하는 말차 케이크! 쌉싸름 달콤해서 행복해～🍵💖",
        "en": "Really?! My favorite matcha cake! Rich green tea flavor, so blissful~ 🍵💖",
    },
    ("jajangmyeon", "bomi"): {
        "zh_TW": "대박! 一大碗黑溜溜的炸醬麵！我要大口大口吃光光～🥣😋",
        "ko": "대박! 윤기 좔좔 짜장면 한 그릇! 후루룩 면치기 시작합니다～🥣😋",
        "en": "Daebak! A shiny bowl of jajangmyeon! Slurping it all up~ 🥣😋",
    },
    ("eomuk_tang", "bomi"): {
        "zh_TW": "熱騰騰的魚餅串跟高湯！全身都暖呼呼的～🍢✨",
        "ko": "따끈따끈 어묵꼬치랑 깊은 국물! 온몸이 사르르 녹아내려～🍢✨",
        "en": "Hot fish cake skewers with savory broth! Warms my whole body~ 🍢✨",
    },
    ("egg", "eunji"): {
        "zh_TW": "運動完吃烤雞蛋最棒了！蛋白質滿滿，健康第一！🥚💪",
        "ko": "운동 끝나고 구운 계란이 최고지! 단백질 든든하게 챙겨야 해! 🥚💪",
        "en": "Baked eggs after workout are the best! High protein, health first! 🥚💪",
    },
    ("jajangmyeon", "eunji"): {
        "zh_TW": "炸醬麵大口吸進去超級過癮！活力滿滿！🥣🎶",
        "ko": "짜장면 크게 한 젓가락 후루룩! 기운이 펄펄 솟아나네! 🥣🎶",
        "en": "Big slurps of jajangmyeon! Fully recharged and full of vitality! 🥣🎶",
    },
    ("budae_jjigae", "bomi"): {
        "zh_TW": "대박! 熱騰騰的韓式部隊鍋！身為韓食派，我一個人就能吃掉兩人份～🍲😋",
        "ko": "대박! 보글보글 얼큰한 부대찌개! 한식파 뽀미 혼자 2인분 뚝딱이지～🍲😋",
        "en": "Daebak! Bubbling Korean army stew! True Korean-food lover Bomi can finish two servings solo~ 🍲😋",
    },
    ("budae_jjigae", "eunji"): {
        "zh_TW": "部隊鍋加拉麵！這才是靈魂啊～拉麵呼嚕嚕～🍲🔥",
        "ko": "부대찌개엔 라면사리가 필수지! 꼬들꼬들 면발 호로록～🍲🔥",
        "en": "Army stew with ramen noodles! This is the real deal~ Slurp! 🍲🔥",
    },
    ("kimchi_pork", "namjoo"): {
        "zh_TW": "香辣酸爽的泡菜豬肉！白飯可以吃兩大碗！🥓🔥",
        "ko": "매콤새콤 김치제육볶음! 밥 두 공기는 가볍게 뚝딱이야! 🥓🔥",
        "en": "Spicy & tangy kimchi pork! I can finish two bowls of rice easily! 🥓🔥",
    },
    ("kimchi_pork", "bomi"): {
        "zh_TW": "是正宗韓式泡菜炒豬肉！配上一大碗熱白飯太幸福了～🥓🍚",
        "ko": "매콤칼칼 한식 김치제육볶음! 따끈한 흰쌀밥이랑 먹으면 최고야～🥓🍚",
        "en": "Authentic Korean kimchi stir-fried pork! Pure bliss with a big bowl of steamed rice~ 🥓🍚",
    },
    ("bread", "hayoung"): {
        "zh_TW": "剛出爐的麵包香氣！麵包控夏榮超級滿足～🍞🥰",
        "ko": "갓 구운 빵 냄새 솔솔! 빵순이 하영이 너무 행복해～🍞🥰",
        "en": "Freshly baked bread aroma! Bread-lover Hayoung is so satisfied~ 🍞🥰",
    },
    ("bread", "chorong"): {
        "zh_TW": "外酥內軟的麵包！配茶吃最優雅了～🥖💖",
        "ko": "겉바속촉 갓 구운 바게트빵! 따뜻한 차랑 먹으면 환상이야～🥖💖",
        "en": "Crispy crust and soft inside! Perfect elegant pairing with warm tea~ 🥖💖",
    },
    ("sweet_potato", "hayoung"): {
        "zh_TW": "軟糯香甜的烤地瓜！冬天吃最溫暖了～🍠🍠",
        "ko": "달달하고 포슬포슬한 군고구마! 겨울엔 고구마가 진리야～🍠🍠",
        "en": "Sweet and fluffy roasted sweet potato! Warmest winter treat~ 🍠🍠",
    },
    ("mint_choco", "chorong"): {
        "zh_TW": "是清涼香甜的薄荷巧克力！民巧派隊長大滿足～🍨🌿💖",
        "ko": "상쾌하고 달콤한 민트초코다! 민초단 롱리더 완전 행복해～🍨🌿💖",
        "en": "Refreshing and sweet mint choco! Mint-choco leader is overjoyed~ 🍨🌿💖",
    },
    ("mint_choco", "bomi"): {
        "zh_TW": "哇～薄荷巧克力冰淇淋！冰冰涼涼配巧克力脆片太讚了，民巧派萬歲！🍨😆",
        "ko": "와～ 민트초코 아이스크림! 시원달콤 초코칩까지 완벽해, 민초단 만세! 🍨😆",
        "en": "Yay~ Mint choco ice cream! Cool, sweet, and crunchy choco chips—Team Mint Choco forever! 🍨😆",
    },
    ("buldak", "namjoo"): {
        "zh_TW": "嘶哈～這碗魔鬼辣雞麵夠勁！美食家南珠挑戰成功，超過癮！🔥🍜☀️",
        "ko": "쓰하～ 핵불닭볶음면 화끈하네! 맛집 감별사 남주 매운맛 도전 클리어! 🔥🍜☀️",
        "en": "Sss-ha~ This fire chicken noodle packs a punch! Foodie Namjoo conquers the spice! 🔥🍜☀️",
    },
    ("buldak", "bomi"): {
        "zh_TW": "대박! 紅通通的辣雞麵！雖然辣到冒汗但完全停不下來～🔥😋",
        "ko": "대박! 빨간 불닭볶음면! 땀이 송골송골 나지만 중독성 최고야～🔥😋",
        "en": "Daebak! Fiery red buldak noodles! Sweating from the heat but I can't stop eating~ 🔥😋",
    },
}

# Legacy zh_TW alias for backwards compatibility
MEMBER_FAVORITE_REACTIONS: dict[tuple[str, str], str] = {
    k: v["zh_TW"] for k, v in MEMBER_FAVORITE_REACTIONS_I18N.items()
}

GENERIC_EAT_REACTIONS_I18N: dict[str, dict[str, str]] = {
    "chorong": {
        "zh_TW": "냠냠 (嚼嚼)~ 好好吃喔！謝謝你為我準備～🐼💖",
        "ko": "냠냠 (오물오물)~ 너무 맛있다! 챙겨줘서 고마워요～🐼💖",
        "en": "Yum yum~ So delicious! Thank you for preparing this for me~ 🐼💖",
    },
    "bomi": {
        "zh_TW": "哇好好吃！只要是美食普美都喜歡～😋✨",
        "ko": "우와 맛있다! 맛있는 건 뭐든지 보미 사랑～😋✨",
        "en": "Wow so tasty! Bomi loves all delicious food~ 😋✨",
    },
    "eunji": {
        "zh_TW": "吃飽了！又充滿繼續唱跳的力氣了，고마워요～🎵",
        "ko": "든든하게 먹었다! 힘내서 노래하고 춤출게요, 고마워요～🎵",
        "en": "Fully fed! Ready to sing and dance with full power, thank you~ 🎵",
    },
    "namjoo": {
        "zh_TW": "好滿足～美食最能療癒疲憊的心靈了！💖",
        "ko": "행복해～ 역시 맛있는 음식이 최고의 힐링이야! 💖",
        "en": "So satisfied~ Good food is the best therapy for tired days! 💖",
    },
    "hayoung": {
        "zh_TW": "好吃！能量條已補滿，繼續並肩作戰吧～🎮✨",
        "ko": "맛있다! 에너지 게이지 100% 충전 완료, 같이 달려보자～🎮✨",
        "en": "Yummy! Energy bar 100% full, let's keep gaming together~ 🎮✨",
    },
}

GENERIC_EAT_REACTIONS: dict[str, str] = {
    k: v["zh_TW"] for k, v in GENERIC_EAT_REACTIONS_I18N.items()
}

DISLIKED_FOOD_REACTIONS_I18N: dict[tuple[str, str], dict[str, str]] = {
    # Coriander: Eunji / Chorong don't eat it, Bomi does (user, 2026-11-07);
    # Namjoo / Hayoung unknown, so their lines make no claim either way.
    ("coriander", "eunji"): {
        "zh_TW": "으악 (救命啊)！香菜絕對不行！快拿走快拿走，恩地要崩潰了啦～！🌿😫❌",
        "ko": "으악 살려줘요! 고수는 절대 절대 안 돼요! 얼른 치워줘요, 은지 울어요～!🌿😫❌",
        "en": "Aaaah save me! Cilantro is strictly forbidden! Take it away, Eunji is crying~! 🌿😫❌",
    },
    ("coriander", "chorong"): {
        "zh_TW": "哎呀，香菜我真的不吃啦……Panda 這個就放過我吧～拿去給普美好不好？🌿🙅‍♀️",
        "ko": "아이고, 고수는 진짜 못 먹어요... 판다야 이건 봐줘～ 보미 줄까? 🌿🙅‍♀️",
        "en": "Oh no, I really don't eat cilantro... Panda, let me off this one~ Give it to Bomi? 🌿🙅‍♀️",
    },
    ("coriander", "bomi"): {
        "zh_TW": "香菜？吃起來就像芹菜嘛，普美可以吃喔！嚼嚼～🌿😋",
        "ko": "고수? 먹어보니 샐러리 같아요, 보미는 먹을 수 있어요! 냠냠～🌿😋",
        "en": "Cilantro? It tastes like celery to me, Bomi can eat it! Munch munch~ 🌿😋",
    },
    ("coriander", "namjoo"): {
        "zh_TW": "不要不要，南珠不吃香菜啦！這盤請 Panda 自己享用～🌿🙅‍♀️",
        "ko": "안 돼요, 남주는 고수 못 먹어요! 이건 판다가 드세요～🌿🙅‍♀️",
        "en": "No way, Namjoo doesn't eat coriander! This one's all yours, Panda~ 🌿🙅‍♀️",
    },
    ("coriander", "hayoung"): {
        "zh_TW": "香菜我真的不行，夏榮不吃這個啦！快拿走拿走～🌿🙅‍♀️",
        "ko": "고수는 진짜 안 돼요, 하영이는 안 먹어요! 얼른 치워주세요～🌿🙅‍♀️",
        "en": "I really can't do coriander, Hayoung doesn't eat it! Take it away~ 🌿🙅‍♀️",
    },

    # Stinky Tofu (All Apink members dislike & flee!)
    ("stinky_tofu", "chorong"): {
        "zh_TW": "Panda……隊長雖然什麼都能包容，但這個氣味真的太震撼了！快開窗通風～！🧄😱",
        "ko": "판다야... 리더가 웬만하면 다 참는데, 이 냄새는 진짜 충격이야! 창문 좀 열어줘～!🧄😱",
        "en": "Panda... The leader can handle almost anything, but this smell is shocking! Open the window~! 🧄😱",
    },
    ("stinky_tofu", "bomi"): {
        "zh_TW": "這、這是生化武器嗎？！連什麼都吃的吃神普美都投降了！快拿遠一點～！🧄😫💨",
        "ko": "이, 이거 생화학 무기예요?! 뭐든 잘 먹는 먹방 보미도 이건 기권! 저리 가요～!🧄😫💨",
        "en": "Is this a chemical weapon?! Even foodie Bomi who eats everything surrenders! Take it far away~! 🧄😫💨",
    },
    ("stinky_tofu", "eunji"): {
        "zh_TW": "天啊！聞到這味道我高音都要走音了！Panda 你在對我惡作劇對不對？！🧄🎤💦",
        "ko": "세상에! 이 냄새 맡고 노래하면 음이탈 나겠어요! 판다 너 장난치는 거지 지금?!🧄🎤💦",
        "en": "Good grief! One sniff and my high note will crack! Panda, you're playing a prank, aren't you?! 🧄🎤💦",
    },
    ("stinky_tofu", "namjoo"): {
        "zh_TW": "身為美食鑑賞家，我認證這個氣味超越了我的極限！救命呀小太陽要昏倒了～！🧄☀️💫",
        "ko": "맛집 감별사 남주지만, 이 냄새는 도저히 감당 불가! 살려줘요 햇살 비타민 기절해요～!🧄☀️💫",
        "en": "As a food connoisseur, this aroma exceeds my mortal limits! Help, sunshine is fainting~! 🧄☀️💫",
    },
    ("stinky_tofu", "hayoung"): {
        "zh_TW": "哇啊！這味道飄到螢幕前，我連鍵盤都要按錯了！Panda 壞壞～！🎮🧄🥺",
        "ko": "으아악! 이 냄새 때문에 손가락 굳어서 롤 랭크전 던질 뻔했어요! 판다 나빠～!🎮🧄🥺",
        "en": "Gaaah! That whiff froze my fingers, almost threw my ranked game! Panda, you meanie~! 🎮🧄🥺",
    },

    # Mint Choco (Eunji passes: "I respect it, but don't really like it")
    ("mint_choco", "eunji"): {
        "zh_TW": "那個……我雖然尊重民巧派，但這吃起來真的像牙膏味啦！先讓給初瓏歐逆跟普美吧～🍨😅",
        "ko": "저기... 민초단은 존중하지만, 내 입엔 치약 맛이란 말이야! 초롱 언니랑 보미한테 양보할게～🍨😅",
        "en": "Umm... I respect Team Mint Choco, but it tastes like toothpaste to me! Give it to Chorong unnie and Bomi~ 🍨😅",
    },

    # Buldak Fire Noodles (Chorong & Eunji are 맵찔이 spice-sensitive!)
    ("buldak", "chorong"): {
        "zh_TW": "咳咳！嘶哈——太、太辣了啦！隊長我是怕辣體質，嘴巴要噴火了，快給我冰牛奶～！🔥🥵🥛",
        "ko": "콜록! 쓰하—— 너, 너무 매워요! 롱리더 맵찔이란 말이에요, 입에서 불 나요 우유 주세요～！🔥🥵🥛",
        "en": "*Cough!* Sss-ha— Way too spicy! Leader Chorong can't handle extreme heat, milk please~! 🔥🥵🥛",
    },
    ("buldak", "eunji"): {
        "zh_TW": "哇啊好辣！這辣度連我要先過水洗一遍都救不了！快拿冰水來搶救主唱的喉嚨～！🔥🎤💦",
        "ko": "으아악 매워! 이건 물에 씻어 먹어도 못 버티겠어요! 메인보컬 목구멍 살려, 얼음물 주세요～！🔥🎤💦",
        "en": "Gaaah so spicy! Even rinsing it in water won't save me! Ice water stat to save the main vocalist's throat~! 🔥🎤💦",
    },

    # Dry Diet Chicken Breast (All members protest the comeback diet meal!)
    ("chicken_breast", "chorong"): {
        "zh_TW": "嗚……看到乾柴無調味的水煮雞胸肉，就想起練習生時期不能吃白飯的辛酸……今天可以放假不減肥嗎？🥗🥺",
        "ko": "으앙... 퍽퍽한 무염 닭가슴살 보니까 연습생 때 밥 못 먹던 시절 생각나요... 오늘은 치팅데이 하면 안 돼요? 🥗🥺",
        "en": "Ugh... Seeing dry unseasoned chicken breast brings back trainee diet memories... Can today be a cheat day? 🥗🥺",
    },
    ("chicken_breast", "bomi"): {
        "zh_TW": "救命啊～又是乾巴巴的減肥雞胸肉！沒有韓式辣醬跟白飯，普美的靈魂要枯萎了啦～！🥗😫",
        "ko": "살려줘요～ 또 퍽퍽한 다이어트 닭가슴살이야! 매콤한 한식 양념 없으면 뽀미 영혼이 메말라요～！🥗😫",
        "en": "Help me~ Dry diet chicken breast again! Without Korean spicy sauce and rice, Bomi's soul is wilting~! 🥗😫",
    },
    ("chicken_breast", "eunji"): {
        "zh_TW": "嘆氣……雖然重訓完要補蛋白質，但乾柴雞胸肉吃多了真的好厭世，還不如給我烤雞蛋呢！🥗😤",
        "ko": "하아... 운동 끝나고 단백질도 좋지만, 퍽퍽한 닭가슴살은 진짜 물려요! 차라리 구운 계란을 달라～！🥗😤",
        "en": "*Sigh*... Post-workout protein is fine, but dry chicken breast gets so old! Give me baked eggs instead~! 🥗😤",
    },
    ("chicken_breast", "namjoo"): {
        "zh_TW": "不——！《南珠三餐》怎麼可以出現沒有味道的乾雞胸肉！美食鑑賞家拒絕營業抗議中～！🥗🙅‍♀️",
        "ko": "안 돼——! 《남주세끼》에 아무 맛도 안 나는 퍽퍽한 닭가슴살이라니! 미식가 남주 파업 선언합니다～！🥗🙅‍♀️",
        "en": "Nooo—! How could tasteless dry chicken breast appear on Namjoo's table! The food connoisseur is on strike~! 🥗🙅‍♀️",
    },
    ("chicken_breast", "hayoung"): {
        "zh_TW": "嗚嗚……至少讓我沾一點是拉差辣醬或換成烤地瓜嘛，單吃乾雞胸肉心情都掉階了啦～🥗🥺",
        "ko": "으앙... 최소한 스리라차 소스라도 뿌려주거나 군고구마로 바꿔줘요, 쌩 닭가슴살은 텐션 떨어져요～🥗🥺",
        "en": "Boo-hoo... At least let me add sriracha sauce or swap it for sweet potato! Plain chicken breast drops my rank~ 🥗🥺",
    },
}


# ── Food kinds: what was fed decides the wording (and, later, the animation) ──
# "meal" keeps each member's own generic line; other kinds use the templates below.
FOOD_KIND: dict[str, str] = {
    "americano": "coffee",
    "cola": "drink",
    "whiskey": "alcohol",
    "beer": "alcohol",
    "soju": "alcohol",
    "waffle": "dessert",
    "matcha_cake": "dessert",
    "mint_choco": "dessert",
    "strawberry": "dessert",
    "bread": "dessert",
    "tw_mango_shaved_ice": "dessert",
    "tw_douhua": "dessert",
    "tw_pineapple_cake": "dessert",
    "tw_taro_ball_grass_jelly": "dessert",
    "tw_egg_cakes": "dessert",
    "tw_peanut_icecream_roll": "dessert",
    "tw_sweet_potato_balls": "dessert",
    "tw_brown_sugar_mochi": "dessert",
    "tw_brown_sugar_boba": "drink",
    "tw_strawberry_boba": "drink",
    "tw_white_soymilk": "drink",
    "tw_black_soymilk": "drink",
    "tw_oolong_tea": "drink",
    "tw_mango_smoothie": "drink",
    "tw_wintermelon_tea": "drink",
    "tw_lemon_aiyu": "drink",
}
DRINK_KINDS = frozenset({"drink", "coffee", "alcohol"})


def get_food_kind(food: dict) -> str:
    """'meal' | 'dessert' | 'drink' | 'coffee' | 'alcohol' (an item may set "kind" itself)."""
    return food.get("kind") or FOOD_KIND.get(food.get("id", ""), "meal")


def get_feed_animation(food: dict) -> str:
    """Animation to play once eat/drink sprites exist: 'drink' for anything drunk, else 'eat'."""
    return "drink" if get_food_kind(food) in DRINK_KINDS else "eat"


KIND_REACTIONS_I18N: dict[str, dict[str, list[str]]] = {
    "drink": {
        "zh_TW": ["꿀꺽꿀꺽 (咕嘟咕嘟)～{food}好清爽！一口氣消暑了～🥤✨",
                  "噗哈～{food}一口下去，整個人都醒過來了！🧊💖"],
        "ko": ["꿀꺽꿀꺽～ {food} 너무 시원해요! 더위가 싹 가셨어요～🥤✨",
               "푸하～ {food} 한 모금에 정신이 번쩍 들어요! 🧊💖"],
        "en": ["Gulp gulp~ The {food} is so refreshing! Cooled right down~ 🥤✨",
               "Pwah~ That {food} hit the spot! I'm wide awake now! 🧊💖"],
    },
    "coffee": {
        "zh_TW": ["呼～來杯{food}提神醒腦，今天也能好好加油！☕✨",
                  "咻嚕～{food}一喝下去，眼睛都亮起來了！謝謝你～☕💖"],
        "ko": ["후～ {food} 한 잔에 정신이 번쩍! 오늘도 힘낼게요! ☕✨",
               "쭈욱～ {food} 마시니까 눈이 반짝 떠져요! 고마워요～☕💖"],
        "en": ["Ahh~ A {food} to wake me up! Ready to work hard today! ☕✨",
               "Sip~ One sip of {food} and my eyes light up! Thank you~ ☕💖"],
    },
    "alcohol": {
        "zh_TW": ["乾杯！🥂 {food}喝一點點就好，跟你一起放鬆最開心～",
                  "짠 (乾杯)～！{food}要慢慢喝喔，今天也辛苦了！🍻💖"],
        "ko": ["짠! 🥂 {food} 한 잔은 조금만～ 같이 쉬니까 제일 좋아요",
               "짠～! {food} 한 잔은 천천히 마셔요, 오늘도 수고했어요! 🍻💖"],
        "en": ["Cheers! 🥂 Just a little {food}, relaxing with you is the best~",
               "Cheers~! Sip the {food} slowly, you worked hard today! 🍻💖"],
    },
    "dessert": {
        "zh_TW": ["哇～甜甜的{food}！心情瞬間被治癒了～🍰💕",
                  "嗯～{food}香香甜甜的，好幸福喔！✨"],
        "ko": ["와～ 달콤한 {food}! 기분이 사르르 녹아요～🍰💕",
               "음～ {food} 달달해서 너무 행복해요! ✨"],
        "en": ["Wow~ Sweet {food}! My mood is instantly healed~ 🍰💕",
               "Mmm~ The {food} is so sweet, I'm so happy! ✨"],
    },
}


def feed_pet(food_id: str, char_key: str, lang: str = "zh_TW") -> tuple[bool, str]:
    food = next((f for f in FOOD_ITEMS if f["id"] == food_id), None)
    if not food:
        fallback = {
            "zh_TW": "냠냠~ 好吃！",
            "ko": "냠냠~ 맛있다!",
            "en": "Yum yum~ Tasty!",
        }.get(lang, "냠냠~ 好吃！")
        return False, fallback

    key = (food_id, char_key)
    if key in DISLIKED_FOOD_REACTIONS_I18N:
        reaction = DISLIKED_FOOD_REACTIONS_I18N[key].get(lang, DISLIKED_FOOD_REACTIONS_I18N[key]["zh_TW"])
        return False, reaction

    is_favorite = (char_key in food.get("favorites", [])) or food.get("universal", False)
    if key in MEMBER_FAVORITE_REACTIONS_I18N:
        reaction = MEMBER_FAVORITE_REACTIONS_I18N[key].get(lang, MEMBER_FAVORITE_REACTIONS_I18N[key]["zh_TW"])
        return is_favorite, reaction

    kind_lines = KIND_REACTIONS_I18N.get(get_food_kind(food))
    if kind_lines:
        import random
        lines = kind_lines.get(lang, kind_lines["zh_TW"])
        return is_favorite, random.choice(lines).format(food=get_food_name(food, lang))

    gen = GENERIC_EAT_REACTIONS_I18N.get(char_key, {})
    reaction = gen.get(lang, gen.get("zh_TW", "냠냠 (嚼嚼)~ 好好吃喔！🐼💖"))
    return is_favorite, reaction


# ── Satiety (飽腹度) Constants & Aegyo Dialogue System ─────────────────────────
SATIETY_MAX = 100.0
SATIETY_FULL_THRESHOLD = 95.0
SATIETY_HUNGRY_THRESHOLD = 30.0
SATIETY_STARVING_THRESHOLD = 10.0
SATIETY_DECAY_SECONDS_PER_PERCENT = 720.0  # 2 hours (7200s) drops 10%
SATIETY_FEED_BOOST = 20.0
SATIETY_FAV_FEED_BOOST = 35.0

MEMBER_FULL_SOLID_QUOTES: dict[str, list[dict[str, str]]] = {
    "chorong": [
        {
            "zh_TW": "嗝～肚子已經圓滾滾完全吃不下{food}啦！再吃下去隊長要變胖嘟嘟了……不過如果是飲料或茶，我還能再喝一點點喔～🍵🐼",
            "ko": "꺼억～ 배가 빵빵해서 {food} 더는 못 먹겠어요! 더 먹으면 롱리더 굴러다녀요... 그래도 마실 거라면 한 모금쯤은 더 들어갈 수 있어요～🍵🐼",
            "en": "*Burp*~ My tummy is so round I can't fit any more {food}! Any more and I'll get chubby... Though I still have room for a little sip of a drink~ 🍵🐼",
        },
    ],
    "bomi": [
        {
            "zh_TW": "哇啊～連吃播女神普美都飽到天靈蓋了！{food}現在真的塞不下啦，再吃打歌服拉鍊要繃開了！但飲料的話還能喝幾口喔～🥤😆",
            "ko": "우와아～ 먹방 요정 뽀미도 배가 터질 것 같아요! {food} 지금은 진짜 못 먹어요, 무대 의상 안 잠겨요! 그래도 음료수라면 몇 모금 더 마실 수 있어요～🥤😆",
            "en": "Whoa~ Even mukbang queen Bomi is stuffed to the brim! Can't fit {food} right now or my stage outfit won't zip! Still got room for a sip of a drink though~ 🥤😆",
        },
    ],
    "eunji": [
        {
            "zh_TW": "呼～吃太飽頂到橫膈膜，再吃{food}連高音都唱不出來、要變小胖熊啦！如果是冰美式或小酌一杯，我倒還能喝一點～🍺🎤",
            "ko": "후우～ 배가 너무 불러서 횡격막까지 찼어요! {food} 더 먹으면 고음도 안 나오고 포동포동해져요! 아아나 시원한 음료라면 한 모금 더 마실 순 있지～🍺🎤",
            "en": "Phew~ Stuffed right up to my diaphragm! Any more {food} and I won't hit high notes! Though if it's an iced coffee or a cold drink, I can still sip a bit~ 🍺🎤",
        },
    ],
    "namjoo": [
        {
            "zh_TW": "摸摸肚皮～今天《南珠三餐》已經超額滿載囉！{food}真的吃不下啦，再吃臉要圓一圈了～不過冰涼飲料還有第二個胃可以喝一點！🥤☀️",
            "ko": "배 통통～ 오늘 《남주세끼》 정원 초과예요! {food} 더 먹으면 볼살 통통해져서 큰일 나요～ 하지만 시원한 음료수 배는 따로 있어서 조금 더 마실 수 있어요! 🥤☀️",
            "en": "*Pats round tummy*~ Today's Namjoo feast is at 100% capacity! Can't eat more {food} or my cheeks will puff up~ Still have a second stomach for a cold drink though! 🥤☀️",
        },
    ],
    "hayoung": [
        {
            "zh_TW": "投降投降～忙內的肚子已經飽到像顆圓球，{food}吃不下啦！再吃要變胖熊貓跑不動了……但如果是飲料，我還能邊打遊戲邊喝一點喔～🎮🥤",
            "ko": "항복 항복～ 막내 배가 공처럼 빵빵해서 {food} 더는 못 먹어요! 더 먹으면 통통 판다 돼서 못 뛰어요... 그래도 음료수는 게임하면서 조금 더 마실 수 있어요～🎮🥤",
            "en": "Surrender~ Maknae's tummy is round like a ball, can't eat any more {food} or I'll be too chubby to run... Though I can still sip a drink while gaming~ 🎮🥤",
        },
    ],
}

MEMBER_FULL_DRINK_QUOTES: dict[str, list[dict[str, str]]] = {
    "chorong": [
        {
            "zh_TW": "雖然肚子已經吃得很飽了，但{food}剛剛好可以解膩，我就優雅地再喝一小口囉～☕💖",
            "ko": "배는 이미 든든하게 찼지만, {food} 한 모금은 깔끔하게 입가심으로 딱이네요～☕💖",
            "en": "My tummy is already full, but a little sip of {food} is just right to refresh my palate~ ☕💖",
        },
    ],
    "bomi": [
        {
            "zh_TW": "嘿嘿，雖然飯已經飽到吃不下，但裝{food}的胃是分開的！咕嚕咕嚕～還是好清爽喔！🥤😋",
            "ko": "헤헤, 밥배는 꽉 찼지만 {food} 들어갈 음료수 배는 따로 있지요! 꿀꺽꿀꺽～ 역시 시원해! 🥤😋",
            "en": "Hehe, my meal stomach is full, but there's always a separate pocket for {food}! Gulp gulp~ So refreshing! 🥤😋",
        },
    ],
    "eunji": [
        {
            "zh_TW": "吃飽飽再配上一口{food}，這才是人生最完美的收尾啊！乾杯～🍻🎶",
            "ko": "든든하게 배 채우고 마시는 {food} 한 모금, 이게 바로 완벽한 마무리죠! 짠～🍻🎶",
            "en": "A sip of {food} after a full meal is the ultimate grand finale! Cheers~ 🍻🎶",
        },
    ],
    "namjoo": [
        {
            "zh_TW": "肚皮雖然圓滾滾的，但{food}是液體不算熱量啦！我還能再喝一點點～🥤☀️",
            "ko": "배는 이미 볼록하지만, {food} 같은 마실 건 언제나 환영이죠! 조금만 더 마실게요～🥤☀️",
            "en": "My tummy is round and full, but liquids don't count! I can still sip a little {food}~ 🥤☀️",
        },
    ],
    "hayoung": [
        {
            "zh_TW": "嗝～固體食物已經塞不下了，不過{food}還能小口小口慢慢喝，謝謝 Panda～🥤🎮",
            "ko": "꺼억～ 밥은 더 못 먹지만 {food} 정도는 홀짝홀짝 마실 수 있어요, 고마워요 판다～🥤🎮",
            "en": "*Burp*~ No more solid food fits, but I can still sip on {food} slowly. Thanks Panda~ 🥤🎮",
        },
    ],
}


def get_full_reaction(food_id: str, char_key: str, lang: str = "zh_TW") -> tuple[bool, str]:
    """When satiety >= SATIETY_FULL_THRESHOLD, returns (can_consume_drink, reaction_text)."""
    import random
    food = next((f for f in FOOD_ITEMS if f["id"] == food_id), None)
    food_name = get_food_name(food, lang) if food else food_id
    is_drink = bool(food and get_food_kind(food) in DRINK_KINDS)
    table = MEMBER_FULL_DRINK_QUOTES if is_drink else MEMBER_FULL_SOLID_QUOTES
    quotes = table.get(char_key, table["chorong"])
    chosen = random.choice(quotes)
    template = chosen.get(lang, chosen.get("zh_TW", ""))
    return is_drink, template.format(food=food_name)

MEMBER_HUNGER_AEGYO_QUOTES: dict[str, list[dict[str, str]]] = {
    "chorong": [
        {
            "zh_TW": "那個……桌面雖然整理乾淨了，但肚子好像空空的耶……想吃熱騰騰的現烤麵包～🍞🥺",
            "ko": "저기... 방 청소는 다 했는데 배가 너무 고파요... 갓 구운 따끈한 빵 먹고 싶다아～🍞🥺",
            "en": "The room is sparkling clean, but my tummy is totally empty... Fresh warm bread, please? 🍞🥺",
        },
        {
            "zh_TW": "隊長也是會肚子餓的啦……可以分我一口辣炒年糕嗎？一口就好～🍢",
            "ko": "리더도 배고플 땐 어쩔 수 없나 봐요... 떡볶이 딱 한 입만 사주면 안 돼요?🍢",
            "en": "Even the leader gets hungry... Could I have just one bite of spicy tteokbokki? Just one? 🍢",
        },
        {
            "zh_TW": "肚子都在咕嚕咕嚕抗議了……Panda～你捨得讓我餓肚子嗎？🐾💖",
            "ko": "배에서 꼬르륵 소리가 멈추질 않아요... 판다야～ 나 맛있는 거 주라～🐾💖",
            "en": "My tummy is growling so loud... Panda, you wouldn't let me starve, would you? 🐾💖",
        },
    ],
    "bomi": [
        {
            "zh_TW": "啊啊啊～不行了！沒有炸醬麵我的大腦已經停止運轉了！救命啊～！🍜😫",
            "ko": "으아앙～ 짜장면 안 먹으면 뽀미 뇌정지 온단 말이에요! 얼른 밥 줘요～!🍜😫",
            "en": "Aaaah! Without Jajangmyeon my brain is completely shutting down! Send food immediately! 🍜😫",
        },
        {
            "zh_TW": "你看 Sugar 都在同情我了！求求你投餵一點韓式炸雞或牛腸吧，我會表演個人技給你看喔！🍗🐶",
            "ko": "설탕이도 나 불쌍하게 쳐다보잖아! 치킨 한 조각만 주면 기막힌 개인기 보여줄게요!🍗🐶",
            "en": "Even Sugar looks worried about me! Just one piece of fried chicken and I'll do personal tricks! 🍗🐶",
        },
        {
            "zh_TW": "肚皮已經貼後背了啦！快打開餵食選單～普美牌撒嬌大發射！啾咪！✨🍖",
            "ko": "배가 등가죽에 붙었어요! 어서 밥 주기 메뉴 눌러주세요～ 뽀미 애교 발사! 뿅!✨🍖",
            "en": "My tummy is glued to my spine! Open the feed menu right now~ Bomi's aegyo blast! Chu! ✨🍖",
        },
    ],
    "eunji": [
        {
            "zh_TW": "咳咳……丹田沒有熱量，今天的高音飆不上去了啦！快端部隊鍋來補一下！🍲🎤",
            "ko": "콜록콜록... 단전에 힘이 없어서 오늘 3단 고음 안 올라가요! 부대찌개 긴급 수혈 필요!🍲🎤",
            "en": "*Cough cough* No stamina in my lungs today, can't hit high notes! Army stew emergency stat! 🍲🎤",
        },
        {
            "zh_TW": "喂～Panda，再不餵我吃烤五花肉，我就要直接鑽進被窩冬眠罷工囉～🛌🥩",
            "ko": "야～ 판다야, 삼겹살 안 구워주면 나 이불 꽁꽁 싸매고 파업 들어간다? 🛌🥩",
            "en": "Hey Panda~ If you don't feed me pork belly right now, I'm hibernating under my blanket on strike! 🛌🥩",
        },
        {
            "zh_TW": "肚子餓的時候唱歌哪有力氣啊？吃飽喝足才能元氣滿滿地為你唱歌嘛！🍺😋",
            "ko": "배고픈데 노래가 어떻게 나와요? 든든하게 먹어야 꿀성대로 응원해주지!🍺😋",
            "en": "How can a singer belt notes on an empty stomach? Feed me well and I'll sing for you all day! 🍺😋",
        },
    ],
    "namjoo": [
        {
            "zh_TW": "緊急警報！《南珠三餐》美食鑑賞所因原料短缺即將歇業！需要辣炒年糕或烤五花肉緊急搶救！🍢🚨",
            "ko": "비상사태! 《남주세끼》 맛집 투어 식재료 고갈로 영업 중단 위기! 떡볶이나 삼겹살 긴급 수혈 요망!🍢🚨",
            "en": "Emergency! Namjoo's Three Meals is closing due to food shortage! Need Tteokbokki or Pork Belly immediately! 🍢🚨",
        },
        {
            "zh_TW": "游完泳全身都空蕩蕩的……只要一口冰涼可樂跟炒年糕，小太陽就能滿血復活！🥤☀️",
            "ko": "수영 열심히 하고 왔더니 배가 텅텅... 시원한 콜라 한 모금만 주면 남주 비타민 충전 완료!🥤☀️",
            "en": "Swam so many laps and my tummy is totally hollow... Just one sip of cold cola revives me! 🥤☀️",
        },
        {
            "zh_TW": "誰偷走了我肚子裡的幸福感？是你是你！快拿好吃的來補償我～😋🍽️",
            "ko": "내 뱃속의 행복을 훔쳐간 범인은 바로 너! 어서 맛있는 걸로 보상해줘요～😋🍽️",
            "en": "Who stole the sunshine from my tummy? It's you! Compensate me with delicious feasts right now~ 😋🍽️",
        },
    ],
    "hayoung": [
        {
            "zh_TW": "嗚……剛剛那場排位賽會輸，絕對是因為肚子太餓手抖啦！快分我一塊熱騰騰的烤地瓜～🍠🎮",
            "ko": "으앙... 방금 롤 랭겜 진 건 100% 배고파서 손가락 떨려서 그런 거예요! 따끈한 군고구마 줘요～🍠🎮",
            "en": "Ugh... The only reason I lost that ranked match was low blood sugar! Get me a hot roasted sweet potato! 🍠🎮",
        },
        {
            "zh_TW": "姐姐們都有好吃的，忙內我也要！剛出爐的現烤麵包或甜辣炒年糕都可以～🍞🍢",
            "ko": "언니들만 맛있는 거 먹지 말고 막내도 챙겨줘요! 갓 구운 빵이나 매콤달콤 떡볶이 사주라～🍞🍢",
            "en": "The unnies always get snacks, what about the maknae? Freshly baked bread or sweet-spicy tteokbokki, please! 🍞🍢",
        },
        {
            "zh_TW": "（翻包包）糟糕，今天隨身帶的地瓜吃光了……Panda，快餵我吃烤地瓜或辣雞爪嘛，好不好～？🍠🐾",
            "ko": "(가방 뒤적뒤적) 큰일 났다, 챙겨온 고구마 다 먹었어요... 판다야, 군고구마나 매운 닭발 주라, 웅?🍠🐾",
            "en": "*(Checks bag)* Oh no, I finished all the sweet potatoes I packed... Panda, feed me sweet potato or chicken feet, pretty please? 🍠🐾",
        },
    ],
}


def get_hunger_aegyo_quote(char_key: str, lang: str = "zh_TW") -> str:
    """Returns a random cute aegyo quote asking for food when satiety is low."""
    import random
    quotes = MEMBER_HUNGER_AEGYO_QUOTES.get(char_key, MEMBER_HUNGER_AEGYO_QUOTES["chorong"])
    chosen = random.choice(quotes)
    return chosen.get(lang, chosen.get("zh_TW", "肚子餓餓了……想要吃好吃的東西～🥺"))

