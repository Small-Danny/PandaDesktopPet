"""personalities.py — Authentic Apink Member Personality Traits, Hobbies, and Warm Quotes.

Member Characteristics & Hobbies:
- Chorong (初瓏): 喜歡貓、喜歡待在家裡 (宅家)、喜歡打掃 (乾淨整理狂)
- Bomi (普美): 喜歡狗、喜歡出去露營 (露營車車長、戶外自然狂熱)
- Eunji (恩地): 喜歡睡覺 (被窩狂熱)、喜歡唱歌 (靈魂高音主唱)
- Namjoo (南珠): 喜歡游泳 (水中飛魚)、喜歡吃美食 (美食鑑賞家)
- Hayoung (夏榮): 喜歡看足球 (英超死忠球迷)、喜歡打電玩 (遊戲少女)

In addition, loads the tri-lingual companion lines (COMPANION_LINE) from
'work/quotes.json'. They are written for this program in each member's voice and
are not things the members actually said.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from app.paths import resource_dir
from app.resource_store import read_resource_bytes, resource_exists

ROOT = resource_dir()
QUOTES_JSON_PATH = ROOT / "work" / "quotes.json"
QUOTES_TXT_PATH = ROOT / "work" / "apink成員暖心語錄.txt"

# 1. Base Member Info & Characteristic Quotes
MEMBER_INFO: dict[str, dict[str, any]] = {
    "chorong": {
        "name": "初瓏 (Chorong)",
        "badges": {
            "zh_TW": "🥋 合氣道三段 ｜ 🐱 貓咪控 ｜ 🏠 最愛宅家",
            "ko": "🥋 합기도 3단 ｜ 🐱 고양이 집사 ｜ 🏠 집순이 리더",
            "en": "🥋 Hapkido 3rd Dan ｜ 🐱 Cat Lover ｜ 🏠 Homebody Leader",
        },
        "hobby_quotes": {
            "zh_TW": [
                "家裡用吸塵器吸得一塵不染，心情整個好舒暢～🧹✨",
                "好想摸摸小貓咪軟綿綿的肉球喔～喵嗚🐾🐱",
                "出門好累喔，還是窩在沙發上看劇最自在了～🛋️💖",
                "剛剛把桌面整理得乾乾淨淨，做事效率都變高了！🧽",
                "窗明几淨的家最讓人有安全感了～🌿",
            ],
            "ko": [
                "집 구석구석 청소기 돌리고 먼지 하나 없으니까 기분이 너무 상쾌해요～🧹✨",
                "말랑말랑한 고양이 젤리 만지고 싶다냥～야옹🐾🐱",
                "밖에 나가는 것보단 폭신한 소파에 누워 드라마 정주행하는 게 최고예요～🛋️💖",
                "방금 책상을 깔끔하게 정리했더니 집중력이 쑥쑥 올라가요!🧽",
                "반짝반짝 깨끗한 집이 주는 아늑함이 제일 좋아요～🌿",
            ],
            "en": [
                "Just vacuumed every corner until spotless! It feels so refreshing~ 🧹✨",
                "I really want to squish a fluffy kitty's soft paw pads~ Meow🐾🐱",
                "Going out is exhausting; curling up on the sofa watching dramas is the best~ 🛋️💖",
                "Tidying up my desk just now instantly boosted my productivity! 🧽",
                "A clean, sunny room always brings the warmest sense of peace~ 🌿",
            ],
        },
        "sleep_quotes": {
            "zh_TW": "家裡打掃得一塵不染，伸個懶腰閉上眼睛，安心睡個好覺囉～🌸💤",
            "ko": "집도 깨끗이 청소했으니, 기지개 켜고 눈 감고 포근하게 잘게요～🌸💤",
            "en": "The room is sparkling clean; stretching and closing my eyes to sleep well~ 🌸💤",
        },
        "cheer_quotes": {
            "zh_TW": "隊長在此！雖然很想宅在家，但會全力為你應援的！💖🔥",
            "ko": "리더 초롱이 등장! 집순이지만 온 힘을 다해 응원할게요! 💖🔥",
            "en": "Leader Chorong here! A homebody at heart, but cheering for you with all my power! 💖🔥",
        },
    },
    "bomi": {
        "name": "普美 (Bomi)",
        "badges": {
            "zh_TW": "🥋 跆拳道三段 ｜ 💃 主舞擔當 ｜ 🏕 露營愛好者",
            "ko": "🥋 태권도 3단 ｜ 💃 메인댄서 ｜ 🏕 캠핑 마니아",
            "en": "🥋 Taekwondo 3rd Dan ｜ 💃 Main Dancer ｜ 🏕 Camping Lover",
        },
        "hobby_quotes": {
            "zh_TW": [
                "汪汪！看到路邊搖尾巴的小狗狗，整顆心都融化了～🐶💖",
                "今天天氣超棒！好想開露營車去山林裡搭帳篷烤肉喔～🏕️🔥",
                "露營時在星空下煮一鍋部隊鍋泡麵，簡直是神仙日子！🌌🍲",
                "好想跟狗狗在草地上丟飛盤奔跑喔～🐕💨",
                "週末一起去露營野餐吧！裝備我都準備好囉～🚙✨",
            ],
            "ko": [
                "멍멍! 꼬리 흔드는 귀여운 댕댕이만 보면 심장이 사르르 녹아요～🐶💖",
                "오늘 날씨 대박! 캠핑카 몰고 숲속으로 훌쩍 떠나고 싶어요～🏕️🔥",
                "별빛 아래 캠핑장에서 끓여 먹는 부대찌개 라면은 진짜 천국의 맛!🌌🍲",
                "잔디밭에서 강아지랑 원반던지기 하면서 전력 질주하고 싶어요～🐕💨",
                "주말에 같이 감성 캠핑 떠나요! 풀세팅 장비 다 챙겨왔어요～🚙✨",
            ],
            "en": [
                "Woof woof! Seeing a puppy wagging its tail instantly melts my heart~ 🐶💖",
                "The weather is amazing today! Let's drive the campervan and set up tents in the woods~ 🏕️🔥",
                "Eating bubbling army stew ramen under the starry sky while camping is heaven! 🌌🍲",
                "I want to run across green grass throwing frisbees with happy puppies~ 🐕💨",
                "Let's go camping and picnicking this weekend! I've packed all the gear~ 🚙✨",
            ],
        },
        "sleep_quotes": {
            "zh_TW": "今天玩得太盡興啦～直接趴下呼呼大睡充電囉～💤✨",
            "ko": "오늘 너무 신나게 놀았어요～ 바로 엎드려 꿀잠 자고 충전할게요～💤✨",
            "en": "Had so much fun today~ Lying down to recharge with sweet sleep~ 💤✨",
        },
        "cheer_quotes": {
            "zh_TW": "大發！充滿戶外能量的普美應援來啦！화이팅！🔥😆",
            "ko": "대박! 비타민 넘치는 뽀미의 파워 응원 갑니다! 화이팅! 🔥😆",
            "en": "Daebak! Outdoor energy burst from Bomi is here! Hwaiting! 🔥😆",
        },
    },
    "eunji": {
        "name": "恩地 (Eunji)",
        "badges": {
            "zh_TW": "🎤 靈魂大主唱 NO.1 ｜ 🥚 最愛吃雞蛋 ｜ ☀ 笑眼暖陽",
            "ko": "🎤 소울 메인보컬 NO.1 ｜ 🥚 달걀 사랑 ｜ ☀ 힐링 눈웃음",
            "en": "🎤 Soul Vocalist NO.1 ｜ 🥚 Egg Lover ｜ ☀ Sunshine Smile",
        },
        "hobby_quotes": {
            "zh_TW": [
                "（哼唱中～🎵）啦啦啦～今天嗓音狀態超完美！🎤🎶",
                "天啊，床鋪跟被窩為什麼有這麼大的魔力～好想賴床喔～🛌😴",
                "唱完一首高音震撼的歌，整個人神清氣爽！🎵✨",
                "人生最高境界就是唱完歌直接鑽進被窩睡到自然醒～💤🛌",
                "累的時候就聽聽我的歌，深呼吸、好好睡一覺吧～🌿🎶",
            ],
            "ko": [
                "(흥얼흥얼～🎵) 라라라～ 오늘 목 상태 완전 최고예요! 🎤🎶",
                "이불 속이 세상에서 제일 따뜻해요～ 5분만 더 잘래요～🛌😴",
                "시원하게 고음 한 곡 뽑고 나면 온몸의 스트레스가 싹 풀려요! 🎵✨",
                "노래 실컷 부르고 이불 속으로 쏙 들어가 늦잠 자는 게 찐행복～💤🛌",
                "지칠 땐 제 노래 들으면서 심호흡하고 푹 자요～🌿🎶",
            ],
            "en": [
                "(Humming softly~ 🎵) La la la~ My vocal chords feel amazing today! 🎤🎶",
                "Why is bed so magnetically comfy~ Just 5 more minutes under the quilt~ 🛌😴",
                "Belting out a high note completely blows all stress away! 🎵✨",
                "Peak life happiness: singing your heart out, then sleeping in warm blankets until noon~ 💤🛌",
                "When you're weary, listen to my voice, take a deep breath, and rest well~ 🌿🎶",
            ],
        },
        "sleep_quotes": {
            "zh_TW": "今天唱得很盡興～直接閉上眼睛睡個香甜大頭覺～😴💤",
            "ko": "노래 실컷 불렀으니～ 눈 감고 포근하게 꿀잠 잘게요～😴💤",
            "en": "Singing was so fulfilling today~ Closing my eyes to enjoy a deep sweet sleep~ 😴💤",
        },
        "cheer_quotes": {
            "zh_TW": "鄭恩地的高音元氣發射！活力百分百，加油！🎤💥",
            "ko": "정은지의 사이다 고음 파워 발사! 백 퍼센트 힘내요! 🎤💥",
            "en": "Jeong Eunji's power high note launched! 100% cheer, you've got this! 🎤💥",
        },
    },
    "namjoo": {
        "name": "南珠 (Namjoo)",
        "badges": {
            "zh_TW": "🍽 美食鑑賞家 ｜ ☀ 活力小太陽 ｜ 🏊 水中人魚",
            "ko": "🍽 맛집 감별사 ｜ ☀ 비타민 햇살 ｜ 🏊 물속 인어",
            "en": "🍽 Food Connoisseur ｜ ☀ Vitamin Sunshine ｜ 🏊 Swimmer Mermaid",
        },
        "hobby_quotes": {
            "zh_TW": [
                "好想跳進冰涼的水裡自由式游個十趟喔～超解壓！🏊‍♀️💦",
                "聽說這附近新開了一家超厲害的美食店！等等就去朝聖～🍽️✨",
                "游完泳肚子咕嚕嚕叫，這時候吃什麼都人間美味！😋🌊",
                "吃好吃的東西就是人生最大的幸福，不接受反駁～💖🍕",
                "只要美食當前，所有的煩惱都會一秒煙消雲散！✨🥩",
            ],
            "ko": [
                "시원한 물속으로 풍덩 뛰어들어 자유형 10바퀴 돌고 싶어요～ 스트레스 싹!🏊‍♀️💦",
                "근처에 소문난 대박 맛집 생겼대요! 이따가 바로 달려갈 거예요～🍽️✨",
                "수영 신나게 하고 나면 배고파서 뭐든 꿀맛인 거 알죠?😋🌊",
                "맛있는 거 배부르게 먹는 게 세상에서 가장 큰 행복이에요～💖🍕",
                "맛있는 음식 한 입이면 모든 근심 걱정이 눈 녹듯 사라져요!✨🥩",
            ],
            "en": [
                "I want to jump into cool waters and do 10 laps of freestyle~ Best stress relief! 🏊‍♀️💦",
                "I heard an incredible gourmet spot just opened nearby! Heading there soon~ 🍽️✨",
                "After swimming laps, food tastes a hundred times more delicious! 😋🌊",
                "Eating good food is the purest happiness in life, no debates allowed~ 💖🍕",
                "One bite of great food makes all worries evaporate in a second! ✨🥩",
            ],
        },
        "sleep_quotes": {
            "zh_TW": "吃飽飽肚子暖洋洋，趴下進入甜美的夢鄉囉～💤💖",
            "ko": "든든하게 먹었더니 배가 따뜻해요～ 엎드려 꿀잠 잘게요～💤💖",
            "en": "Tummy warm and full, settling down into sweet dreams~ 💤💖",
        },
        "cheer_quotes": {
            "zh_TW": "活力小太陽南珠登場！用吃美食的熱情為你打氣～✨☀",
            "ko": "비타민 남주 등장! 맛있는 거 먹을 때의 텐션으로 응원해요～✨☀",
            "en": "Sunshine Namjoo here! Cheering you with the sheer joy of delicious feasts! ✨☀",
        },
    },
    "hayoung": {
        "name": "夏榮 (Hayoung)",
        "badges": {
            "zh_TW": "🍠 地瓜狂熱者 ｜ 🎮 電競少女忙內 ｜ 🔴 曼聯死忠粉",
            "ko": "🍠 군고구마 마니아 ｜ 🎮 게임 여신 막내 ｜ 🔴 맨유 찐팬",
            "en": "🍠 Sweet Potato Fan ｜ 🎮 Gamer Maknae ｜ 🔴 Man Utd Fanatic",
        },
        "hobby_quotes": {
            "zh_TW": [
                "昨晚曼聯的比賽真的太神了！GGMU！那記絕殺進球帥炸！⚽🔴",
                "今晚又有老特拉福德的直播了！準備好可樂跟烤地瓜熬夜為曼聯加油～⚽🍠",
                "打完一把排位賽吃一口剛出爐的現烤麵包，人生完美～🎮🍞",
                "曼聯是生命，電競是靈魂，誰懂我的快樂！🔴🕹️",
                "這球傳得太漂亮了！就像我們今天的默契一樣棒～🏃‍♀️⚽",
            ],
            "ko": [
                "어젯밤 맨유 경기 보셨어요? GGMU! 후반 추가시간 극장골 진짜 미쳤어요!⚽🔴",
                "오늘 밤 올드 트래퍼드 빅매치 생중계 있어요! 군고구마 들고 맨유 응원 대기 중～⚽🍠",
                "게임 랭크전 연승 달리고 갓 구운 빵 한입 베어 물면 극락～🎮🍞",
                "맨유는 심장, 게임은 소울! 이 짜릿함 다들 아시죠?🔴🕹️",
                "어시스트 패스 예술이었어요! 우리 오늘 환상의 호흡처럼요～🏃‍♀️⚽",
            ],
            "en": [
                "Did you see Manchester United's match last night? GGMU! That stoppage-time winner was insane! ⚽🔴",
                "Old Trafford big match streaming tonight! Roasted sweet potatoes ready to cheer Man Utd~ ⚽🍠",
                "Winning a ranked match and munching freshly baked bread: absolute bliss~ 🎮🍞",
                "Man Utd is heartbeat, gaming is soul! Glory Glory Man United! 🔴🕹️",
                "What an assist! Just like our flawless teamwork today~ 🏃‍♀️⚽",
            ],
        },
        "sleep_quotes": {
            "zh_TW": "打完一把精彩的比賽，心滿意足地趴下好好補眠囉～🎮💤",
            "ko": "멋진 경기 완주하고, 기분 좋게 엎드려 푹 잘게요～🎮💤",
            "en": "Finished a wonderful match, happily settling down to sleep~ 🎮💤",
        },
        "cheer_quotes": {
            "zh_TW": "GGMU！曼聯死忠粉夏榮為你開出勝利的絕殺球！🔴⚽🎯",
            "ko": "GGMU! 맨유 찐팬 하영이가 승리의 극장골을 날려줄게요! 🔴⚽🎯",
            "en": "GGMU! Man Utd fanatic Hayoung kicks the winning goal for you! 🔴⚽🎯",
        },
    },
}


def _load_all_warm_quotes() -> dict[str, list[dict[str, str]]]:
    """Loads the tri-lingual companion lines from quotes.json or apink成員暖心語錄.txt."""
    if resource_exists(QUOTES_JSON_PATH):
        try:
            raw = read_resource_bytes(QUOTES_JSON_PATH).decode("utf-8-sig")
            return json.loads(raw)
        except Exception:
            pass

    if resource_exists(QUOTES_TXT_PATH):
        try:
            content = read_resource_bytes(QUOTES_TXT_PATH).decode("utf-8-sig")
            sections = re.split(r"----------------------------------------------------------------------\n[一二三四五]、", content)
            members = ["chorong", "bomi", "eunji", "namjoo", "hayoung"]
            data: dict[str, list[dict[str, str]]] = {}
            for i, sec in enumerate(sections[1:]):
                if i >= len(members):
                    break
                m_key = members[i]
                entries = []
                blocks = re.split(r"\n(?=\d{2}\.)", sec)
                for block in blocks:
                    zh = re.search(r"\[中\]\s*(.+)", block)
                    ko = re.search(r"\[韓\]\s*(.+)", block)
                    en = re.search(r"\[英\]\s*(.+)", block)
                    if zh and ko and en:
                        entries.append({
                            "zh": zh.group(1).strip(),
                            "ko": ko.group(1).strip(),
                            "en": en.group(1).strip(),
                            "quote_category": "COMPANION_LINE",
                        })
                data[m_key] = entries
            # Cache on disk only when running from loose developer files
            if QUOTES_TXT_PATH.is_file():
                try:
                    QUOTES_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
            return data
        except Exception:
            pass

    return {}


WARM_QUOTES: dict[str, list[dict[str, str]]] = _load_all_warm_quotes()
# Attributed quotes are retired: their sources were never linked, so they were
# rewritten as companion lines in work/quotes.json. Kept empty for old imports.
VERIFIED_QUOTES: dict[str, list[dict]] = {}


def get_member_badge(char_key: str, lang: str = "zh_TW") -> str:
    """Returns localized personality badge."""
    info = MEMBER_INFO.get(char_key, MEMBER_INFO["chorong"])
    badges = info.get("badges", {})
    return badges.get(lang, badges.get("zh_TW", "Apink Pink Panda"))


def get_companion_line_badge(lang: str = "zh_TW") -> str:
    """Returns localized badge for original desktop companion lines (COMPANION_LINE)."""
    return {
        "zh_TW": "🐼 粉熊日常陪伴",
        "ko": "🐼 판다 일상 동행",
        "en": "🐼 Panda Daily Companion",
    }.get(lang, "🐼 粉熊日常陪伴")


def get_random_verified_quote(char_key: str, lang: str = "zh_TW") -> tuple[str, str, dict] | None:
    """Retired: no attributed quotes ship any more. Kept so old callers get None."""
    return None


def get_random_warm_quote(char_key: str, lang: str = "zh_TW") -> str:
    """Gets a random companion line (COMPANION_LINE) for the member."""
    quotes = WARM_QUOTES.get(char_key, [])
    if not quotes:
        quotes = WARM_QUOTES.get("chorong", [])
    if not quotes:
        return {
            "zh_TW": "謝謝你們成為我青春裡最燦爛的一頁 💖",
            "ko": "제 청춘의 가장 찬란한 페이지가 되어줘서 고마워요 💖",
            "en": "Thank you for being the brightest page of my youth 💖",
        }.get(lang, "謝謝你們成為我青春裡最燦爛的一頁 💖")

    entry = random.choice(quotes)
    lang_key = "ko" if lang == "ko" else ("en" if lang == "en" else "zh")
    return entry.get(lang_key, entry.get("zh", ""))


def get_random_chat_quote(char_key: str, lang: str = "zh_TW") -> tuple[str, str]:
    """Returns (badge, quote): a companion line or a hobby line, each with its own badge."""
    badge = get_member_badge(char_key, lang)
    companion_badge = get_companion_line_badge(lang)
    info = MEMBER_INFO.get(char_key, MEMBER_INFO["chorong"])

    # 70% companion line (COMPANION_LINE), 30% hobby line
    if random.random() < 0.70 and WARM_QUOTES.get(char_key):
        return companion_badge, get_random_warm_quote(char_key, lang)

    hobby_dict = info.get("hobby_quotes", {})
    quotes_list = hobby_dict.get(lang, hobby_dict.get("zh_TW", []))
    if quotes_list:
        return badge, random.choice(quotes_list)

    return companion_badge, get_random_warm_quote(char_key, lang)


def get_sleep_quote(char_key: str, lang: str = "zh_TW") -> str:
    info = MEMBER_INFO.get(char_key, MEMBER_INFO["chorong"])
    sq = info.get("sleep_quotes", {})
    return sq.get(lang, sq.get("zh_TW", "安心入睡中～💤"))


def get_cheer_quote(char_key: str, lang: str = "zh_TW") -> str:
    info = MEMBER_INFO.get(char_key, MEMBER_INFO["chorong"])
    cq = info.get("cheer_quotes", {})
    return cq.get(lang, cq.get("zh_TW", "加油加油！화이팅！💖"))
