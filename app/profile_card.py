"""app/profile_card.py — Dedicated High-Texture Apink Member Profile Card (成員自我介紹小卡).

Features:
- Borderless rounded card with glassmorphism aesthetics and transparent keying (#ff00fe).
- Full 5-member carousel navigation (Prev / Next, and direct jump via pagination dots).
- Authentic verified Apink data from MEMBER_PROFILE_SPEC.md:
  - Upgraded Eunji "Soul Vocalist NO.1" (靈魂大主唱 NO.1) stature.
  - Position & talents, official quotes, favorite foods, and funny taboos.
- Multi-lingual (zh_TW, ko, en) dynamic rendering.
- Interactive "Say Hello" button triggering pet toast & cheer celebration.
- Window dragging, smooth lifecycle management, and zero memory leaks.
"""
from __future__ import annotations

import math
import re
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional
from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.paths import resource_dir
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, scale_canvas, ui_scale
from app.resource_store import open_resource_image, resource_exists
from app.sprites import SpriteLibrary
from app.status_card import MEMBER_THEMES, clean_badge_text, layout_badge_pills

BG_TRANSPARENT = "#ff00fe"
ROOT = resource_dir()

AVATAR_BOX_X1 = 20
AVATAR_BOX_Y1 = 58
AVATAR_BOX_X2 = 126
AVATAR_BOX_Y2 = 154
AVATAR_BOX_W = AVATAR_BOX_X2 - AVATAR_BOX_X1
AVATAR_BOX_H = AVATAR_BOX_Y2 - AVATAR_BOX_Y1
AVATAR_DISPLAY_PX = 84
AVATAR_CHEER_FRAME_MS = 180
BADGE_TIERS = ((8, 18, 8), (7, 12, 5))     # (pt, pill padding, gap) tried in order
BADGE_ROW_STEP = 30                        # design px between wrapped badge rows
TEXT_GAP = 3                               # design px between a row title and its text

_TEXT_HEIGHT_CACHE: dict[tuple[str, tuple, int, float], float] = {}
_RIGHT_COLUMN_LAYOUT_CACHE: dict[tuple[str, str, float, tuple], dict] = {}
_MEMBER_AVATAR_PIL_CACHE: dict[tuple[str, int], tuple[Optional[Image.Image], tuple[Image.Image, ...]]] = {}

MEMBERS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")

MEMBER_PROFILES = {
    "chorong": {
        "names": {"zh_TW": "朴初瓏", "ko": "박초롱", "en": "Park Cho-Rong"},
        "full_title": {"zh_TW": "朴初瓏 Park Cho-Rong", "ko": "박초롱 Park Cho-Rong", "en": "Park Cho-Rong 朴初瓏"},
        "birthday": "1991.03.03",
        "astro": {"zh_TW": "雙魚座 ♓ ｜ O型", "ko": "물고기자리 ♓ ｜ O형", "en": "Pisces ♓ ｜ Type O"},
        "symbol": {"zh_TW": "🐱 溫柔貓咪 ‧ 🌸 柔和櫻粉", "ko": "🐱 온화한 고양이 ‧ 🌸 베이비 핑크", "en": "🐱 Gentle Cat ‧ 🌸 Baby Pink"},
        "mascot": {"zh_TW": "隆咚", "ko": "롱둥이", "en": "Rongdoong"},
        "badges": {
            "zh_TW": ["🥋 合氣道三段", "🐱 貓咪控", "🏠 最愛宅家"],
            "ko": ["🥋 합기도 3단", "🐱 고양이 집사", "🏠 집순이 리더"],
            "en": ["🥋 Hapkido 3rd Dan", "🐱 Cat Lover", "🏠 Homebody Leader"],
        },
        "position": {
            "zh_TW": "Apink 隊長、副唱、作詞才女、合氣道公認三段、全團精神支柱、家務整理狂人，人稱「瓏三歲」「瓏媽媽」。",
            "ko": "에이핑크 리더, 서브보컬, 작사가, 합기도 공인 3단, 든든한 롱리더 겸 청소 요정, 별명 '롱세살'·'롱마마'.",
            "en": "Apink Leader, Sub-vocalist, Lyricist, 3rd Dan Hapkido, Spiritual Pillar & Tidy Queen, a.k.a. \"Three-Year-Old Rong\" & \"Mama Rong\".",
        },
        "quote": {
            "zh_TW": "「只要大家相信我、跟著我走下去，我們就永遠是 Apink。」",
            "ko": "「우리가 서로를 믿고 함께 걷는다면, 에이핑크는 영원해요.」",
            "en": "“As long as we trust each other and walk together, Apink will last forever.”",
        },
        "fav_food": {
            "zh_TW": "濃郁抹茶蛋糕 🍵 ｜ 招牌Q彈雞爪 🐾 ｜ 現烤香酥麵包 🍞",
            "ko": "진한 말차 케이크 🍵 ｜ 쫄깃한 닭발 🐾 ｜ 갓 구운 빵 🍞",
            "en": "Rich Matcha Cake 🍵 ｜ Savory Chicken Feet 🐾 ｜ Fresh Bread 🍞",
        },
        "taboo": {
            "zh_TW": "減肥代餐雞胸肉 🥗、蟲子 🐛、髒亂不整理的桌面 🧹",
            "ko": "다이어트용 퍽퍽한 닭가슴살 🥗, 벌레 🐛, 어지러운 책상 🧹",
            "en": "Dry Diet Chicken Breast 🥗, Bugs 🐛, Messy Desks 🧹",
        },
        "greeting": {
            "zh_TW": "粉熊呀～今天也要平安幸福喔！隊長初瓏會一直陪著你的～🌸",
            "ko": "판다들～ 오늘도 무탈하고 행복해야 해요! 롱리더가 언제나 곁에 있을게요～🌸",
            "en": "Pandas~ Stay safe and happy today! Leader Chorong will always be right here with you~ 🌸",
        },
    },
    "bomi": {
        "names": {"zh_TW": "尹普美", "ko": "윤보미", "en": "Yoon Bo-Mi"},
        "full_title": {"zh_TW": "尹普美 Yoon Bo-Mi", "ko": "윤보미 Yoon Bo-Mi", "en": "Yoon Bo-Mi 尹普美"},
        "birthday": "1993.08.13",
        "astro": {"zh_TW": "獅子座 ♌ ｜ O型", "ko": "사자자리 ♌ ｜ O형", "en": "Leo ♌ ｜ Type O"},
        "symbol": {"zh_TW": "🐶 活潑小獵犬 ‧ 🍊 珊瑚蜜橘", "ko": "🐶 활발한 비글 ‧ 🍊 코랄 오렌지", "en": "🐶 Lively Beagle ‧ 🍊 Coral Orange"},
        "mascot": {"zh_TW": "普咚", "ko": "뽐둥이", "en": "Bbomdoong"},
        "badges": {
            "zh_TW": ["🥋 跆拳道三段", "💃 主舞擔當", "🏕 露營愛好者"],
            "ko": ["🥋 태권도 3단", "💃 메인댄서", "🏕 캠핑 마니아"],
            "en": ["🥋 Taekwondo 3rd Dan", "💃 Main Dancer", "🏕 Camping Lover"],
        },
        "position": {
            "zh_TW": "主領舞、領唱、綜藝之神、跆拳道公認三段、吃播百萬 YouTuber、戶外露營狂熱者。",
            "ko": "메인댄서, 리드보컬, 예능의 신, 태권도 공인 3단, 먹방 크리에이터, 감성 캠핑러.",
            "en": "Main Dancer, Lead Vocalist, Variety Legend, 3rd Dan Taekwondo, Mukbang Creator, Camping Master.",
        },
        "quote": {
            "zh_TW": "「不要吝嗇笑容，幸福自然會找到笑得最燦爛的那個人！화이팅！」",
            "ko": "「웃음을 아끼지 마세요, 행복은 웃는 얼굴을 찾아오니까요! 화이팅!」",
            "en": "“Never hold back your smile—happiness naturally finds those who laugh brightest!”",
        },
        "fav_food": {
            "zh_TW": "正宗韓式部隊鍋 🍲 ｜ 甜辣炒年糕與魚餅湯 🍢 ｜ 炸醬麵與烤牛腸 🍜",
            "ko": "얼큰 한식 부대찌개 🍲 ｜ 매콤 떡볶이·어묵탕 🍢 ｜ 짜장면·소곱창 🍜",
            "en": "Korean Army Stew 🍲 ｜ Tteokbokki & Fish Cake Soup 🍢 ｜ Jajangmyeon & Tripe 🍜",
        },
        "taboo": {
            "zh_TW": "安靜沉悶不能說話的場合 🤐、斷糧狀態 😱、沒有醬汁的乾麵",
            "ko": "말 못 하게 하는 조용한 분위기 🤐, 식량 고갈 😱, 소스 없는 면",
            "en": "Awkward Silent Rooms 🤐, Empty Fridge Emergency 😱, Sauce-less Noodles",
        },
        "greeting": {
            "zh_TW": "嗷嗚～今天也要元氣滿滿地大笑喔！普美把一整年份的活力都送給你！😆🎉",
            "ko": "와아아～ 오늘도 신나게 활짝 웃어봐요! 뽀미가 비타민 에너지를 듬뿍 쏩니다! 😆🎉",
            "en": "Woof~ Laugh out loud with super high energy today! Bomi is blasting mega happiness to you! 😆🎉",
        },
    },
    "eunji": {
        "names": {"zh_TW": "鄭恩地", "ko": "정은지", "en": "Jeong Eun-Ji"},
        "full_title": {"zh_TW": "鄭恩地 Jeong Eun-Ji", "ko": "정은지 Jeong Eun-Ji", "en": "Jeong Eun-Ji 鄭恩地"},
        "birthday": "1993.08.18",
        "astro": {"zh_TW": "獅子座 ♌ ｜ B型", "ko": "사자자리 ♌ ｜ B형", "en": "Leo ♌ ｜ Type B"},
        "symbol": {"zh_TW": "🎤 靈魂百靈鳥 ‧ 🌊 晴空湛藍", "ko": "🎤 소울 꾀꼬리 ‧ 🌊 스카이 블루", "en": "🎤 Soul Lark ‧ 🌊 Sky Blue"},
        "mascot": {"zh_TW": "恩咚", "ko": "믕둥이", "en": "Meungdoong"},
        "badges": {
            "zh_TW": ["🎤 靈魂大主唱 NO.1", "🥚 最愛吃雞蛋", "☀ 笑眼暖陽"],
            "ko": ["🎤 소울 메인보컬 NO.1", "🥚 달걀 사랑", "☀ 힐링 눈웃음"],
            "en": ["🎤 Soul Vocalist NO.1", "🥚 Egg Lover", "☀ Sunshine Smile"],
        },
        "position": {
            "zh_TW": "靈魂大主唱 NO.1、K-POP 殿堂級天籟、百想實力神演員（《請回答1997》《酒鬼都市》）、健身狂人，最愛暱稱「懵地」（믕／믕지），人稱「鄭卡戴珊」。",
            "ko": "소울 메인보컬 NO.1, K-POP 레전드 사이다 보컬, 믿고 보는 연기파 배우, 운동 광인, 최애 애칭 '믕'·'믕지', 별명 '정카다시안'.",
            "en": "Soul Vocalist NO.1, K-Pop Hall-of-Fame Vocalist, Acclaimed Lead Actress, Fitness Fanatic, fav nickname \"Meung\" / \"Meungji\", a.k.a. \"Jung Kardashian\".",
        },
        "quote": {
            "zh_TW": "「我的歌聲，是為了成為你們生活中隨時可以安心倚靠的避風港而存在的。」",
            "ko": "「제 노래가 여러분 삶에서 언제든 편히 기댈 수 있는 쉼표가 되길 바라요.」",
            "en": "“My singing exists to be a reassuring sanctuary where you can always lean and find rest.”",
        },
        "fav_food": {
            "zh_TW": "營養水煮蛋/烤雞蛋 🥚 ｜ 滋滋烤五花肉 🥩 ｜ 香辣雞爪 🐾 ｜ 部隊鍋與生啤 🍲",
            "ko": "단백질 구운 계란 🥚 ｜ 지글지글 삼겹살 🥩 ｜ 매운 닭발 🐾 ｜ 부대찌개·생맥주 🍲",
            "en": "Sauna Baked Eggs 🥚 ｜ Sizzling Pork Belly 🥩 ｜ Spicy Chicken Feet 🐾 ｜ Army Stew & Beer 🍲",
        },
        "taboo": {
            "zh_TW": "不能運動健身發洩 🚫、感冒失聲 😷、舞台假唱、搶走麥克風",
            "ko": "운동 못 하게 하기 🚫, 목 감기로 쉰 목소리 😷, 립싱크, 마이크 뺏기",
            "en": "Skipping Gym Day 🚫, Losing Singing Voice 😷, Lip-syncing, Stealing the Mic",
        },
        "greeting": {
            "zh_TW": "Hey 粉熊！累的時候就聽聽我的歌吧，恩地永遠為你唱出最溫暖的高音～🎵💪",
            "ko": "안녕 판다들! 지칠 땐 제 노래 들으면서 힘내요, 은지가 언제나 곁에서 노래할게요～🎵💪",
            "en": "Hey Pandas! Whenever you feel weary, lean on my songs. Eunji is always singing for you~ 🎵💪",
        },
    },
    "namjoo": {
        "names": {"zh_TW": "金南珠", "ko": "김남주", "en": "Kim Nam-Joo"},
        "full_title": {"zh_TW": "金南珠 Kim Nam-Joo", "ko": "김남주 Kim Nam-Joo", "en": "Kim Nam-Joo 金南珠"},
        "birthday": "1995.04.15",
        "astro": {"zh_TW": "牡羊座 ♈ ｜ B型", "ko": "양자리 ♈ ｜ B형", "en": "Aries ♈ ｜ Type B"},
        "symbol": {"zh_TW": "☀ 活力小太陽 ‧ 🍇 丁香紫", "ko": "☀ 인간 비타민 ‧ 🍇 라벤더 퍼플", "en": "☀ Vitamin Sunshine ‧ 🍇 Lavender Purple"},
        "mascot": {"zh_TW": "南咚", "ko": "남둥이", "en": "Namdoong"},
        "badges": {
            "zh_TW": ["🍽 美食鑑賞家", "☀ 活力小太陽", "🏊 水中人魚"],
            "ko": ["🍽 맛집 감별사", "☀ 인간 비타민", "🏊 수영 인어공주"],
            "en": ["🍽 Food Connoisseur", "☀ Vitamin Sunshine", "🏊 Freestyle Swimmer"],
        },
        "position": {
            "zh_TW": "領唱、領舞、團內維他命發電機、百老匯音樂劇女主角、大胃王美食鑑賞家、水中自由式健將。",
            "ko": "리드보컬, 리드댄서, 팀내 인간 비타민, 뮤지컬 배우, 프로 미식가, 수영 인어공주.",
            "en": "Lead Vocalist, Lead Dancer, Human Vitamin Energizer, Musical Actress, Food Connoisseur, Freestyle Swimmer.",
        },
        "quote": {
            "zh_TW": "「用吃美食的百分之百熱情，把全世界最明亮的維他命能量通通發射給你！☀」",
            "ko": "「맛있는 걸 먹을 때의 텐션 그대로! 온 세상에 사랑스러운 비타민 에너지를 팡팡 쏴드릴게요!☀」",
            "en": "“With the supreme joy of feasting, I'll launch endless vitamin positivity straight to you! ☀”",
        },
        "fav_food": {
            "zh_TW": "香辣過癮辣雞爪 🐾 ｜ 氣泡暢快冰可樂 🥤 ｜ 濃香泡菜炒豬肉 🥩 ｜ 經典炒年糕 🍢",
            "ko": "화끈하게 매운 닭발 🐾 ｜ 톡 쏘는 얼음 콜라 🥤 ｜ 매콤 김치제육 🥩 ｜ 쫄깃 떡볶이 🍢",
            "en": "Spicy Chicken Feet 🐾 ｜ Chilled Fizzy Cola 🥤 ｜ Spicy Pork Kimchi 🥩 ｜ Chewy Tteokbokki 🍢",
        },
        "taboo": {
            "zh_TW": "難吃沒味道的食物 🙅‍♀、嚴格禁食令、死氣沉沉冷場的氛圍",
            "ko": "맛없는 음식 🙅‍♀, 굶주림, 썰렁하고 가라앉은 분위기",
            "en": "Bland Flavorless Food 🙅‍♀, Starvation Diets, Dull & Lifeless Rooms",
        },
        "greeting": {
            "zh_TW": "哈囉～我是南珠！今天有沒有好好吃飯呀？記得一定要對自己好一點喔！☀💖",
            "ko": "안녕～ 남주예요! 오늘 맛있는 밥 든든하게 챙겨 먹었죠? 언제나 파이팅이에요! ☀💖",
            "en": "Hello~ Namjoo here! Did you have a delicious meal today? Always treat yourself kindly! ☀💖",
        },
    },
    "hayoung": {
        "names": {"zh_TW": "吳夏榮", "ko": "오하영", "en": "Oh Ha-Young"},
        "full_title": {"zh_TW": "吳夏榮 Oh Ha-Young", "ko": "오하영 Oh Ha-Young", "en": "Oh Ha-Young 吳夏榮"},
        "birthday": "1996.07.19",
        "astro": {"zh_TW": "巨蟹座 ♋ ｜ B型", "ko": "게자리 ♋ ｜ B형", "en": "Cancer ♋ ｜ Type B"},
        "symbol": {"zh_TW": "🎮 電競少女 ‧ 🍯 檸檬奶黃", "ko": "🎮 게임 여신 ‧ 🍯 레몬 옐로우", "en": "🎮 Elite Gamer ‧ 🍯 Lemon Yellow"},
        "mascot": {"zh_TW": "夏咚", "ko": "하둥이", "en": "Hadoong"},
        "badges": {
            "zh_TW": ["🍠 地瓜狂熱者", "🎮 電競少女忙內", "🔴 曼聯死忠粉"],
            "ko": ["🍠 꿀고구마 마니아", "🎮 만능 겜순이 막내", "🔴 맨유 찐팬"],
            "en": ["🍠 Sweet Potato Fan", "🎮 Gamer Maknae", "🔴 Man Utd Fanatic"],
        },
        "position": {
            "zh_TW": "副唱、團寵忙內、電競神級少女、英超曼聯死忠粉、成熟吐槽擔當，人稱「吳芙蘿迪蒂」。",
            "ko": "서브보컬, 사랑받는 만능 막내, 연예계 소문난 겜순이, 맨유 찐팬, 실세 막내, 별명 '오프로디테'.",
            "en": "Sub-vocalist, Golden Maknae, Elite Gamer Girl, Man Utd Fanatic, Witty Maknae on Top, a.k.a. \"Ohphrodite\".",
        },
        "quote": {
            "zh_TW": "「姐姐們是我的翅膀，而粉熊是我在人生排位賽裡永遠的 MVP 隊友！🏆」",
            "ko": "「언니들은 저의 날개이고, 판다들은 언제나 제 인생 랭크전의 든든한 MVP 팀원이에요!🏆」",
            "en": "“The unnies are my wings, and Pandas are forever my MVP teammates in the game of life! 🏆”",
        },
        "fav_food": {
            "zh_TW": "香甜現烤地瓜 🍠 ｜ 剛出爐現烤麵包 🍞 ｜ 甜辣辣炒年糕 🍢 ｜ 招牌雞爪 🐾",
            "ko": "달콤한 꿀 군고구마 🍠 ｜ 갓 구운 빵 🍞 ｜ 매콤달콤 떡볶이 🍢 ｜ 쫄깃한 닭발 🐾",
            "en": "Honey-Baked Sweet Potato 🍠 ｜ Fresh Baked Bread 🍞 ｜ Spicy Tteokbokki 🍢 ｜ Chicken Feet 🐾",
        },
        "taboo": {
            "zh_TW": "遊戲斷線延遲（Lag / Ping 999+）❌、排位賽連敗掉階、放涼變硬的地瓜 🍠❄",
            "ko": "게임 렉/핑 999+ ❌, 랭크전 연패 강등, 식어버린 딱딱한 고구마 🍠❄",
            "en": "Wi-Fi Lag / Ping 999+ ❌, Ranked Match Loss Streaks, Cold & Hardened Sweet Potatoes 🍠❄",
        },
        "greeting": {
            "zh_TW": "GGMU！忙內夏榮來為你開出勝利的一球囉！今天也要贏下所有的挑戰！🎮🔴⚽",
            "ko": "GGMU! 막내 하영이가 승리의 골을 날려줄게요! 오늘 하루도 랭크전 승리합시다! 🎮🔴⚽",
            "en": "GGMU! Maknae Hayoung kicks the winning goal for you! Let's win every match today! 🎮🔴⚽",
        },
    },
}

UI_TEXT = {
    "zh_TW": {
        "title": "Apink 成員自我介紹小卡",
        "prev": "◀ 上一位",
        "next": "下一位 ▶",
        "greet": "聽她打招呼 🌸",
        "fav_food": "🍱 最愛美食",
        "taboo": "⚡ 趣味避雷",
        "position": "隊內定位與專長",
        "mascot_tag": "🐼 吉祥物 ‧ ",
    },
    "ko": {
        "title": "Apink 멤버 프로필 카드",
        "prev": "◀ 이전",
        "next": "다음 ▶",
        "greet": "인사 듣기 🌸",
        "fav_food": "🍱 최애 음식",
        "taboo": "⚡ 절대 금지",
        "position": "포지션 및 특기",
        "mascot_tag": "🐼 마스코트 ‧ ",
    },
    "en": {
        "title": "Apink Member Profile Card",
        "prev": "◀ Prev",
        "next": "Next ▶",
        "greet": "Say Hello 🌸",
        "fav_food": "🍱 Favorite Foods",
        "taboo": "⚡ Fun Taboos",
        "position": "Position & Talents",
        "mascot_tag": "🐼 Mascot: ",
    },
}


def _font_family(lang: str) -> str:
    if lang == "ko":
        return "Malgun Gothic"
    if lang == "en":
        return "Segoe UI"
    return "Microsoft JhengHei"


def _fit_font_size(
    fam: str,
    text: str,
    max_w: int,
    max_pt: int = 10,
    min_pt: int = 8,
    root: Optional[tk.Misc] = None,
) -> tuple[str, int, str]:
    """Calculates best fitting bold font size so text never wraps or clips."""
    import tkinter.font as tkfont
    for pt in range(max_pt, min_pt - 1, -1):
        try:
            f = tkfont.Font(root=root, family=fam, size=pt, weight="bold")
            if f.measure(text) <= max_w:
                return (fam, pt, "bold")
        except Exception:
            break
    return (fam, min_pt, "bold")


class MemberProfileCard:
    """Dedicated Glassmorphism Apink Member Profile Card with Carousel and Dragging."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_member: str = "chorong",
        lang: str = "zh_TW",
        on_greeting: Optional[Callable[[str, str], None]] = None,
        on_context_change: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_close = on_close
        self.members = MEMBERS
        self.current_idx = self.members.index(initial_member) if initial_member in self.members else 0
        self.lang = lang
        self.on_greeting = on_greeting
        self.on_context_change = on_context_change
        self._design_w, self._design_h = 520, 430
        self.drag_offset_x: Optional[int] = None
        self.drag_offset_y: Optional[int] = None
        self._drag_notified: bool = False
        self._closed: bool = False
        self._avatar_photo: Optional[tk.PhotoImage] = None
        self._current_avatar_frame: Optional[tk.PhotoImage] = None
        self._avatar_cheer_frames: list[tk.PhotoImage] = []
        self._avatar_item_id: Optional[int] = None
        self._avatar_anim_after_id: Optional[str] = None
        self._present_after_id: Optional[str] = None
        self._desktop = WindowsDesktopAdapter(fallback_bounds=lambda: WorkArea(
            0, 0, max(1, self.win.winfo_screenwidth()), max(1, self.win.winfo_screenheight())))

        self.win = tk.Toplevel(parent)
        try:
            # An override-redirect or withdrawn pet is not a normal managed owner window.
            top = parent.winfo_toplevel()
            if not top.overrideredirect() and top.winfo_viewable():
                self.win.transient(parent)
        except Exception:
            pass
        self.win.title("Apink Member Profile")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.configure(bg=BG_TRANSPARENT)
        try:
            self.win.attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.ui_scale = ui_scale(self.win)
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)
        self._sprite_lib = SpriteLibrary(ROOT, display_px=round(AVATAR_DISPLAY_PX * self.ui_scale))

        self.canvas = tk.Canvas(
            self.win,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_drag_begin)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.bind("<Left>", lambda _e: self.prev_member())
        self.win.bind("<Right>", lambda _e: self.next_member())
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.render_current()

        self.win.update_idletasks()
        try:
            px = int(parent.winfo_rootx()) + max(1, int(parent.winfo_width())) // 2
            py = int(parent.winfo_rooty()) + max(1, int(parent.winfo_height())) // 2
        except Exception:
            px, py = 600, 300
        work = self._desktop.work_area_for_point(px, py)
        cx, cy = work.clamp(
            work.left + (work.width - self.w) // 2,
            work.top + (work.height - self.h) // 3,
            self.w,
            self.h,
        )
        self.last_clamped_pos = (cx, cy)
        self.win.geometry(f"{self.w}x{self.h}+{max(0, cx)}+{max(0, cy)}")
        try:
            self.win.update_idletasks()
            frame = self.win.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.win.winfo_id())
            if not self._desktop.position_without_activation(hwnd, cx, cy) and cx >= 0 and cy >= 0:
                self.win.geometry(f"{self.w}x{self.h}+{cx}+{cy}")
        except Exception:
            pass
        self.win.deiconify()
        self.win.lift()
        # First creation may occur inside a native popup menu callback. Raise
        # once more after that callback unwinds, without taking keyboard focus.
        self._present_after_id = self.win.after_idle(self._present_after_menu)

    def _present_after_menu(self) -> None:
        self._present_after_id = None
        try:
            if not self._closed and self.win.winfo_exists():
                self.win.deiconify()
                self.win.lift()
        except tk.TclError:
            pass  # The card may have been closed before this idle callback.

    def _notify_context_change(self) -> None:
        if self.on_context_change is not None:
            try:
                self.on_context_change()
            except Exception:
                pass

    def avatar_bounds(self) -> Optional[tuple[int, int, int, int]]:
        """Return screen root (x, y, w, h) of the member avatar frame, or None if hidden/closed."""
        try:
            if self._closed or not hasattr(self, "win") or not self.win.winfo_exists():
                return None
            if not self.win.winfo_viewable():
                return None
            self.win.update_idletasks()
            rx = int(self.win.winfo_rootx()) + round(AVATAR_BOX_X1 * self.ui_scale)
            ry = int(self.win.winfo_rooty()) + round(AVATAR_BOX_Y1 * self.ui_scale)
            return (rx, ry, round(AVATAR_BOX_W * self.ui_scale), round(AVATAR_BOX_H * self.ui_scale))
        except Exception:
            return None

    def _stop_avatar_cheer(self, reset_to_idle: bool = True) -> None:
        if self._avatar_anim_after_id is not None:
            try:
                self.win.after_cancel(self._avatar_anim_after_id)
            except Exception:
                pass
            self._avatar_anim_after_id = None
        if reset_to_idle and not self._closed and self._avatar_item_id is not None and self._avatar_photo is not None:
            try:
                self._current_avatar_frame = self._avatar_photo
                self.canvas.itemconfigure(self._avatar_item_id, image=self._avatar_photo)
            except Exception:
                pass

    def play_avatar_cheer(self, cycles: int = 2) -> bool:
        """Play approved cheer frames inside the card avatar box without triggering context change."""
        self._stop_avatar_cheer(reset_to_idle=False)
        if self._closed or not hasattr(self, "win") or not self.win.winfo_exists():
            return False
        if self._avatar_item_id is None or not self._avatar_cheer_frames:
            return False
        seq = self._avatar_cheer_frames * max(1, int(cycles))
        try:
            self._current_avatar_frame = seq[0]
            self.canvas.itemconfigure(self._avatar_item_id, image=seq[0])
            if len(seq) > 1:
                self._avatar_anim_after_id = self.win.after(
                    AVATAR_CHEER_FRAME_MS,
                    lambda: self._step_avatar_cheer(seq, 1),
                )
            else:
                self._avatar_anim_after_id = self.win.after(
                    AVATAR_CHEER_FRAME_MS,
                    lambda: self._stop_avatar_cheer(reset_to_idle=True),
                )
            return True
        except Exception:
            self._stop_avatar_cheer(reset_to_idle=True)
            return False

    def _step_avatar_cheer(self, seq: list[tk.PhotoImage], idx: int) -> None:
        self._avatar_anim_after_id = None
        if self._closed or not hasattr(self, "win") or not self.win.winfo_exists() or self._avatar_item_id is None:
            return
        try:
            if idx < len(seq):
                frame = seq[idx]
                self._current_avatar_frame = frame
                self.canvas.itemconfigure(self._avatar_item_id, image=frame)
                self._avatar_anim_after_id = self.win.after(
                    AVATAR_CHEER_FRAME_MS,
                    lambda: self._step_avatar_cheer(seq, idx + 1),
                )
            else:
                self._current_avatar_frame = self._avatar_photo
                if self._avatar_photo is not None:
                    self.canvas.itemconfigure(self._avatar_item_id, image=self._avatar_photo)
        except Exception:
            pass

    def _on_drag_begin(self, event: tk.Event) -> None:
        # Check if click landed on an interactive element or within button bounds
        current_tags = set(self.canvas.gettags("current"))
        interactive_tags = {"btn_greet", "btn_prev", "btn_next", "btn_close", "btn_dot", "avatar_img"}
        if current_tags & interactive_tags:
            self.drag_offset_x = None
            self.drag_offset_y = None
            return

        # Explicit geometric hit-bounds check for greeting pill and nav controls
        btn_y1, btn_y2 = round(274 * self.ui_scale), round(314 * self.ui_scale)
        if round(16 * self.ui_scale) <= event.x <= round(130 * self.ui_scale) and btn_y1 <= event.y <= btn_y2:
            self.drag_offset_x = None
            self.drag_offset_y = None
            return
        if event.y >= round(360 * self.ui_scale) or (
            event.x >= self.w - round(40 * self.ui_scale) and event.y <= round(45 * self.ui_scale)
        ):
            self.drag_offset_x = None
            self.drag_offset_y = None
            return

        try:
            self.win.lift()
        except Exception:
            pass
        x_root = getattr(event, "x_root", getattr(event, "x", 0) + self.win.winfo_x())
        y_root = getattr(event, "y_root", getattr(event, "y", 0) + self.win.winfo_y())
        self.drag_offset_x = x_root - self.win.winfo_x()
        self.drag_offset_y = y_root - self.win.winfo_y()
        self._press_root = (x_root, y_root)
        self._drag_notified = False

    def _on_drag_move(self, event: tk.Event) -> None:
        if self.drag_offset_x is not None and self.drag_offset_y is not None:
            x_root = getattr(event, "x_root", getattr(event, "x", 0) + self.win.winfo_x())
            y_root = getattr(event, "y_root", getattr(event, "y", 0) + self.win.winfo_y())
            nx = x_root - self.drag_offset_x
            ny = y_root - self.drag_offset_y
            if not self._drag_notified:
                px, py = getattr(self, "_press_root", (x_root, y_root))
                if abs(x_root - px) + abs(y_root - py) < 4:
                    return
                self._drag_notified = True
                self._stop_avatar_cheer(reset_to_idle=True)
                self._notify_context_change()
            work = self._desktop.work_area_for_point(x_root, y_root)
            cx, cy = work.clamp(nx, ny, self.w, self.h)
            try:
                self.win.geometry(f"{self.w}x{self.h}+{cx}+{cy}")
            except tk.TclError:
                pass

    def _on_drag_end(self, _event: tk.Event) -> None:
        self.drag_offset_x = None
        self.drag_offset_y = None
        self._drag_notified = False

    def close(self) -> None:
        self._stop_avatar_cheer(reset_to_idle=False)
        if self._present_after_id is not None:
            try:
                self.win.after_cancel(self._present_after_id)
            except Exception:
                pass
            self._present_after_id = None
        first_close = not self._closed
        if first_close:
            self._closed = True
            self._notify_context_change()
        try:
            self.win.destroy()
        except Exception:
            pass
        # 2026-11-22 (Neno): the closed card kept its avatar photos (+5 Tk images / GDI)
        # and the pet kept the card itself until the next open.
        self._avatar_photo = self._current_avatar_frame = None
        self._avatar_cheer_frames.clear()
        callback, self.on_close = getattr(self, "on_close", None), None
        if first_close and callback is not None:
            try:
                callback()
            except Exception:
                log.exception("profile card on_close failed")

    def prev_member(self) -> None:
        self.current_idx = (self.current_idx - 1) % len(self.members)
        self.render_current()
        self._notify_context_change()

    def next_member(self) -> None:
        self.current_idx = (self.current_idx + 1) % len(self.members)
        self.render_current()
        self._notify_context_change()

    def set_member_by_index(self, idx: int) -> None:
        new_idx = idx % len(self.members)
        changed = new_idx != self.current_idx
        self.current_idx = new_idx
        self.render_current()
        if changed:
            self._notify_context_change()

    def _fit_window_height(self, design_h: int) -> None:
        """Grow or shrink the window in place when the content height changes."""
        new_h = round(design_h * self.ui_scale)
        if new_h == self.h:
            return
        self.h = new_h
        self.canvas.config(height=new_h)
        self.win.geometry(f"{self.w}x{new_h}")

    def _text_height(self, text: str, font: tuple, width: int | None = None) -> float:
        """Design-px height of *text* as it wraps once the canvas is scaled."""
        w_key = int(width) if width else 0
        scale_key = round(self.ui_scale, 4)
        cache_key = (text, tuple(font), w_key, scale_key)
        cached = _TEXT_HEIGHT_CACHE.get(cache_key)
        if cached is not None:
            return cached
        options = {"width": round(width * self.ui_scale)} if width else {}
        item = self.canvas.create_text(0, 0, anchor="nw", text=text, font=font, **options)
        bbox = self.canvas.bbox(item)
        self.canvas.delete(item)
        val = (bbox[3] - bbox[1]) / self.ui_scale if bbox else 0.0
        _TEXT_HEIGHT_CACHE[cache_key] = val
        return val

    def _right_column_layout(self, member_key: str) -> dict:
        """Right-column geometry in design px: text never touches its title.

        Extra lines first borrow the quote box's spare height; only then does the column grow.
        """
        profile = MEMBER_PROFILES[member_key]
        badges_sig = tuple(profile["badges"].get(self.lang, profile["badges"]["zh_TW"]))
        pos_sig = profile["position"].get(self.lang, profile["position"]["zh_TW"])
        quote_sig = profile["quote"].get(self.lang, profile["quote"]["zh_TW"])
        food_sig = profile["fav_food"].get(self.lang, profile["fav_food"]["zh_TW"])
        taboo_sig = profile["taboo"].get(self.lang, profile["taboo"]["zh_TW"])
        cache_key = (
            member_key,
            self.lang,
            round(self.ui_scale, 4),
            (badges_sig, pos_sig, quote_sig, food_sig, taboo_sig),
        )
        cached = _RIGHT_COLUMN_LAYOUT_CACHE.get(cache_key)
        if cached is not None:
            return cached
        layout = self._column_pass(member_key, quote_min=68)
        overflow = layout["row4"][5] - 348
        if overflow > 0:
            quote_top, quote_bottom = layout["quote"][:2]
            spare = quote_bottom - quote_top - layout["quote_need"]
            if spare > 0:
                layout = self._column_pass(member_key, quote_min=68 - min(spare, overflow))
        _RIGHT_COLUMN_LAYOUT_CACHE[cache_key] = layout
        return layout

    def _column_pass(self, member_key: str, quote_min: int) -> dict:
        import tkinter.font as tkfont
        profile = MEMBER_PROFILES[member_key]
        tx = UI_TEXT.get(self.lang, UI_TEXT["zh_TW"])
        fam = _font_family(self.lang)
        k = self.ui_scale
        rx1, rx2 = 136, self._design_w - 20
        fonts: dict[int, tkfont.Font] = {}

        def measure(text: str, pt: int) -> int:
            if pt not in fonts:
                fonts[pt] = tkfont.Font(root=self.win, family=fam, size=pt, weight="bold")
            return round(fonts[pt].measure(text) / k)

        badges = [clean_badge_text(b) for b in profile['badges'].get(self.lang, profile['badges']['zh_TW'])]
        badge_pt, pills = layout_badge_pills(badges, measure, rx1, rx2, BADGE_TIERS, 50)

        title_font, desc_font = (fam, 8, "bold"), (fam, 8)
        desc_w = rx2 - rx1 - 20

        def stack(title_y: float, title: str, desc: str) -> tuple[float, float]:
            """(desc_y, desc_bottom) for a description placed just under its title."""
            desc_y = title_y + self._text_height(title, title_font) + TEXT_GAP
            return desc_y, desc_y + self._text_height(desc, desc_font, desc_w)

        pos_title = f"🏷 {tx['position']}"
        pos_desc = profile['position'].get(self.lang, profile['position']['zh_TW'])
        pos_top = 92 + BADGE_ROW_STEP * max((row for _x, row, _w, _t in pills), default=0)
        pos_title_y = pos_top + 6
        pos_desc_y, pos_end = stack(pos_title_y, pos_title, pos_desc)
        pos_bottom = max(pos_top + 70, math.ceil(pos_end) + 5)

        quote_text = profile['quote'].get(self.lang, profile['quote']['zh_TW'])
        quote_font = (fam, 8, "italic" if self.lang == "en" else "bold")
        quote_top = pos_bottom + 8
        quote_h = self._text_height(quote_text, quote_font, rx2 - rx1 - 24)
        quote_need = math.ceil(quote_h + 16)
        quote_bottom = quote_top + max(quote_min, quote_need)

        food_desc = profile['fav_food'].get(self.lang, profile['fav_food']['zh_TW'])
        taboo_desc = profile['taboo'].get(self.lang, profile['taboo']['zh_TW'])
        row4_top = quote_bottom + 8
        food_title_y = row4_top + 7
        food_desc_y, food_end = stack(food_title_y, tx['fav_food'], food_desc)
        taboo_title_y = max(row4_top + 55, math.ceil(food_end) + 6)
        taboo_desc_y, taboo_end = stack(taboo_title_y, tx['taboo'], taboo_desc)
        row4_bottom = max(row4_top + 102, math.ceil(taboo_end) + 6)
        return {
            "rx1": rx1, "rx2": rx2, "desc_w": desc_w, "badge_pt": badge_pt, "pills": pills,
            "pos": (pos_top, pos_title_y, pos_desc_y, pos_bottom, pos_title, pos_desc),
            "quote": (quote_top, quote_bottom, quote_text, quote_font), "quote_need": quote_need,
            "row4": (row4_top, food_title_y, food_desc_y, taboo_title_y, taboo_desc_y, row4_bottom,
                     food_desc, taboo_desc),
        }

    def render_current(self) -> None:
        self._stop_avatar_cheer(reset_to_idle=False)
        self.canvas.delete("all")
        self._avatar_item_id = None
        member_key = self.members[self.current_idx]
        profile = MEMBER_PROFILES[member_key]
        theme = MEMBER_THEMES.get(member_key, MEMBER_THEMES["chorong"])
        tx = UI_TEXT.get(self.lang, UI_TEXT["zh_TW"])
        fam = _font_family(self.lang)

        w = self._design_w
        k = self.ui_scale
        # The tallest member sets the card height so the carousel never jumps.
        layouts = {m: self._right_column_layout(m) for m in self.members}
        lay = layouts[member_key]
        row4_bottom = max(item["row4"][5] for item in layouts.values())
        nav_y1 = max(368, row4_bottom + 20)
        nav_y2 = nav_y1 + 40
        h = nav_y2 + 22
        self._fit_window_height(h)

        # 1. Outer rounded card
        _draw_round_rect(
            self.canvas, 6, 6, w - 6, h - 6,
            r=22, fill=theme["soft_bg"], outline=theme["border"], width=2.5,
        )

        # 2. Header banner
        _draw_round_rect(
            self.canvas, 8, 8, w - 8, 48,
            r=18, fill=theme["header_fill"], outline=theme["border"], width=1.5,
        )

        title_text = f"✦ {profile['full_title'].get(self.lang, profile['full_title']['zh_TW'])}"
        self.canvas.create_text(
            22, 28, anchor="w",
            text=title_text,
            font=(fam, 12, "bold"),
            fill=theme["primary"],
        )

        # Mascot tag in header
        mascot_val = profile.get("mascot", "")
        m_name = mascot_val.get(self.lang, mascot_val.get("zh_TW", "")) if isinstance(mascot_val, dict) else str(mascot_val)
        mascot_display = f"{tx.get('mascot_tag', '🐼 ')}{m_name}"
        self.canvas.create_text(
            w - 52, 28, anchor="e",
            text=mascot_display,
            font=(fam, 9, "bold"),
            fill=theme["accent"],
        )

        # Close button '✕'
        close_id = self.canvas.create_text(
            w - 24, 28, anchor="center",
            text="✕", font=(fam, 13, "bold"), fill=theme["accent"], tags=("btn_close",),
        )
        self.canvas.tag_bind(close_id, "<Button-1>", lambda _e: self.close())

        # 3. Left Column: Avatar, Specs & Persona Pod
        av_x1, av_y1, av_x2, av_y2 = AVATAR_BOX_X1, AVATAR_BOX_Y1, AVATAR_BOX_X2, AVATAR_BOX_Y2
        _draw_round_rect(
            self.canvas, av_x1, av_y1, av_x2, av_y2,
            r=16, fill="#ffffff", outline=theme["border"], width=2,
        )

        # Load approved idle + cheer frames via cached PIL images (safe across Tk roots)
        self._avatar_photo = None
        self._avatar_cheer_frames = []
        avatar_px = max(16, round(AVATAR_DISPLAY_PX * k))
        pil_cache_key = (member_key, avatar_px)
        cached_pils = _MEMBER_AVATAR_PIL_CACHE.get(pil_cache_key)
        if cached_pils is None:
            idle_pil: Optional[Image.Image] = None
            cheer_pils: list[Image.Image] = []
            try:
                pil_dict, source = self._sprite_lib.load_member_pil(member_key)
                idle_list = pil_dict.get("idle")
                if idle_list:
                    idle_pil = idle_list[0]
                if source == "registry":
                    cheer_list = pil_dict.get("cheer")
                    if cheer_list:
                        cheer_pils = list(cheer_list)
            except Exception:
                avatar_path = ROOT / "work" / "characters" / member_key / "idle_01.png"
                if resource_exists(avatar_path):
                    try:
                        with open_resource_image(avatar_path) as im:
                            idle_pil = im.convert("RGBA").resize(
                                (avatar_px, avatar_px),
                                Image.Resampling.LANCZOS,
                            )
                    except Exception:
                        pass
            cached_pils = (idle_pil, tuple(cheer_pils))
            if idle_pil is not None:
                _MEMBER_AVATAR_PIL_CACHE[pil_cache_key] = cached_pils

        idle_pil, cheer_tuple = cached_pils
        if idle_pil is not None:
            try:
                self._avatar_photo = ImageTk.PhotoImage(idle_pil, master=self.win)
            except Exception:
                self._avatar_photo = None
        for c_im in cheer_tuple:
            try:
                self._avatar_cheer_frames.append(ImageTk.PhotoImage(c_im, master=self.win))
            except Exception:
                pass

        if self._avatar_photo is not None:
            self._current_avatar_frame = self._avatar_photo
            self._avatar_item_id = self.canvas.create_image(
                (av_x1 + av_x2) // 2,
                (av_y1 + av_y2) // 2,
                image=self._avatar_photo,
                tags=("avatar_img",),
            )

        cx = (av_x1 + av_x2) // 2

        # 3a. Birthday & Astro Row (Enlarged & Crisp)
        bday_str = f"🎂 {profile['birthday']}"
        astro_str = profile['astro'].get(self.lang, profile['astro']['zh_TW'])
        self.canvas.create_text(
            cx, 168, anchor="center",
            text=bday_str, font=(fam, 8, "bold"), fill=theme["accent"],
        )
        self.canvas.create_text(
            cx, 186, anchor="center",
            text=astro_str, font=(fam, 8, "bold"), fill="#555555",
        )

        # 3b. Concept & Persona Pod ("溫柔貓咪" 專屬舒適膠囊卡片，字級提升至 10pt/9pt)
        symbol_str = profile['symbol'].get(self.lang, profile['symbol']['zh_TW'])
        parts = symbol_str.split(" ‧ ")
        if len(parts) == 2:
            persona_str, color_str = parts[0].strip(), parts[1].strip()
        else:
            persona_str, color_str = symbol_str, ""

        persona_str = re.sub(r"^(\S+)\s+", r"\1 ", persona_str.replace("\ufe0f", "").replace("\u200d\u2640", "").replace("\u200d", "").strip())
        color_str = re.sub(r"^(\S+)\s+", r"\1 ", color_str.replace("\ufe0f", "").replace("\u200d\u2640", "").replace("\u200d", "").strip())

        _draw_round_rect(
            self.canvas, 16, 200, 130, 258,
            r=12, fill=theme["pill_fill"], outline=theme["border"], width=1.5,
        )
        f_persona = _fit_font_size(fam, persona_str, round(106 * k), max_pt=10, min_pt=8, root=self.win)
        self.canvas.create_text(
            cx, 218, anchor="center",
            text=persona_str, font=f_persona, fill=theme["primary"],
        )
        if color_str:
            f_color = _fit_font_size(fam, color_str, round(106 * k), max_pt=9, min_pt=8, root=self.win)
            self.canvas.create_text(
                cx, 240, anchor="center",
                text=color_str, font=f_color, fill=theme["accent"],
            )

        # 3c. "Say Hello" Interactive Pill Button (立體延伸)
        btn_y1, btn_y2 = 274, 314
        greet_bg = _draw_round_rect(
            self.canvas, 16, btn_y1, 130, btn_y2,
            r=14, fill=theme["header_fill"], outline=theme["primary"], width=1.5, tags=("btn_greet",),
        )
        greet_hitbox = self.canvas.create_rectangle(
            16, btn_y1, 130, btn_y2,
            fill="", outline="", tags=("btn_greet",),
        )
        greet_txt = self.canvas.create_text(
            cx, (btn_y1 + btn_y2) // 2,
            text=tx["greet"], font=(fam, 9, "bold"), fill=theme["primary"], tags=("btn_greet",),
        )

        def _trigger_greet() -> None:
            if self.on_greeting:
                shown = self.on_greeting(
                    member_key,
                    profile['greeting'].get(self.lang, profile['greeting']['zh_TW']),
                )
                if shown is True:
                    self.play_avatar_cheer(cycles=2)

        for item in (greet_bg, greet_hitbox, greet_txt):
            self.canvas.tag_bind(item, "<Button-1>", lambda _e: _trigger_greet())

        # 3d. Mascot Tag Pill
        _draw_round_rect(
            self.canvas, 16, 328, 130, 352,
            r=9, fill="#ffffff", outline=theme["glow"], width=1,
        )
        f_mascot = _fit_font_size(fam, mascot_display, round(106 * k), max_pt=8, min_pt=7, root=self.win)
        self.canvas.create_text(
            cx, 340, anchor="center",
            text=mascot_display, font=f_mascot, fill=theme["accent"],
        )

        # 4. Right Column: Badges, Role, Quote, Food, Taboo
        rx1, rx2, desc_w = lay["rx1"], lay["rx2"], lay["desc_w"]

        # Row 1: Badges (shrink before wrapping; never silently dropped)
        for bx, row, bw, clean_b in lay["pills"]:
            by = 60 + row * BADGE_ROW_STEP
            _draw_round_rect(
                self.canvas, bx, by, bx + bw, by + 24,
                r=10, fill=theme["pill_fill"], outline=theme["badge_border"], width=1.5,
                tags=("badge_pill",),
            )
            self.canvas.create_text(
                bx + bw // 2, by + 12,
                text=clean_b, font=(fam, lay["badge_pt"], "bold"), fill=theme["accent"],
                tags=("badge_text",),
            )

        # Row 2: Position & Talents Box
        pos_top, pos_title_y, pos_desc_y, pos_bottom, pos_title, pos_desc = lay["pos"]
        _draw_round_rect(
            self.canvas, rx1, pos_top, rx2, pos_bottom,
            r=12, fill="#ffffff", outline=theme["border"], width=1.5,
        )
        self.canvas.create_text(
            rx1 + 10, pos_title_y, anchor="nw",
            text=pos_title, font=(fam, 8, "bold"), fill=theme["primary"], tags=("pos_title",),
        )
        self.canvas.create_text(
            rx1 + 10, pos_desc_y, anchor="nw", width=desc_w,
            text=pos_desc, font=(fam, 8), fill="#333333", tags=("pos_desc",),
        )

        # Row 3: Signature Quote Box
        quote_top, quote_bottom, quote_text, quote_font = lay["quote"]
        _draw_round_rect(
            self.canvas, rx1, quote_top, rx2, quote_bottom,
            r=12, fill=theme["header_fill"], outline=theme["glow"], width=1.5,
        )
        self.canvas.create_text(
            (rx1 + rx2) // 2, (quote_top + quote_bottom) / 2, anchor="center", width=rx2 - rx1 - 24,
            text=quote_text, font=quote_font, fill=theme["primary"],
        )

        # Row 4: Food & Taboo (the box reaches the shared bottom so the nav bar stays put)
        row4_top, food_title_y, food_desc_y, taboo_title_y, taboo_desc_y, _end, food_desc, taboo_desc = lay["row4"]
        _draw_round_rect(
            self.canvas, rx1, row4_top, rx2, row4_bottom,
            r=12, fill="#ffffff", outline=theme["border"], width=1.5,
        )
        self.canvas.create_text(
            rx1 + 10, food_title_y, anchor="nw",
            text=tx['fav_food'], font=(fam, 8, "bold"), fill=theme["accent"], tags=("food_title",),
        )
        self.canvas.create_text(
            rx1 + 10, food_desc_y, anchor="nw", width=desc_w,
            text=food_desc, font=(fam, 8), fill="#444444", tags=("food_desc",),
        )
        self.canvas.create_text(
            rx1 + 10, taboo_title_y, anchor="nw",
            text=tx['taboo'], font=(fam, 8, "bold"), fill="#d32f2f", tags=("taboo_title",),
        )
        self.canvas.create_text(
            rx1 + 10, taboo_desc_y, anchor="nw", width=desc_w,
            text=taboo_desc, font=(fam, 8), fill="#555555", tags=("taboo_desc",),
        )

        # 5. Bottom Navigation Bar: Prev, Indicator Dots, Next

        # Prev Button
        btn_prev_bg = _draw_round_rect(
            self.canvas, 22, nav_y1, 126, nav_y2,
            r=14, fill=theme["header_fill"], outline=theme["border"], width=1.5, tags=("btn_prev",),
        )
        btn_prev_txt = self.canvas.create_text(
            74, (nav_y1 + nav_y2) // 2,
            text=tx["prev"], font=(fam, 9, "bold"), fill=theme["accent"], tags=("btn_prev",),
        )
        for item in (btn_prev_bg, btn_prev_txt):
            self.canvas.tag_bind(item, "<Button-1>", lambda _e: self.prev_member())

        # Next Button
        btn_next_bg = _draw_round_rect(
            self.canvas, w - 126, nav_y1, w - 22, nav_y2,
            r=14, fill=theme["bar_fill"], outline=theme["primary"], width=1.5, tags=("btn_next",),
        )
        btn_next_txt = self.canvas.create_text(
            w - 74, (nav_y1 + nav_y2) // 2,
            text=tx["next"], font=(fam, 9, "bold"), fill="#ffffff", tags=("btn_next",),
        )
        for item in (btn_next_bg, btn_next_txt):
            self.canvas.tag_bind(item, "<Button-1>", lambda _e: self.next_member())

        # 5 Indicator Dots with member colors
        dot_center_x = w // 2
        dot_y = (nav_y1 + nav_y2) // 2
        dot_spacing = 28
        start_x = dot_center_x - ((len(self.members) - 1) * dot_spacing) // 2

        for i, m_key in enumerate(self.members):
            dx = start_x + i * dot_spacing
            m_theme = MEMBER_THEMES.get(m_key, MEMBER_THEMES["chorong"])
            is_active = (i == self.current_idx)
            radius = 8 if is_active else 5
            fill_color = m_theme["primary"] if is_active else "#d6d6d6"
            outline_color = m_theme["accent"] if is_active else "#b0b0b0"
            tag = f"dot_{i}"
            dot_id = self.canvas.create_oval(
                dx - radius, dot_y - radius, dx + radius, dot_y + radius,
                fill=fill_color, outline=outline_color, width=1.5, tags=(tag,),
            )
            self.canvas.tag_bind(dot_id, "<Button-1>", lambda _e, target=i: self.set_member_by_index(target))
        scale_canvas(self.canvas, k)
