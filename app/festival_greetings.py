"""Per-member trilingual greetings for the hanbok Lunar New Year, Lantern Festival and Mid-Autumn.

2026-11-22: New Year's Day and Christmas had their own speech, but these three festival
previews only toasted their menu title ("🧧 新年韓服拜年") as the message, and the real
festival day only had the generic "five pandas dressed up" line. Each member now says
something in her own voice; ``festival_greeting`` falls back to zh_TW / Chorong.
"""
from __future__ import annotations

FESTIVAL_GREETINGS: dict[str, dict[str, dict[str, str]]] = {
    "lunar_ny": {
        "chorong": {
            "zh_TW": "🧧 新年快樂！初瓏穿好韓服跟你拜年囉～新的一年也要好好照顧自己，我們一直都在你身邊💗",
            "ko": "🧧 새해 복 많이 받으세요! 초롱이가 한복 입고 세배드려요～ 올해도 건강 챙기고, 우리 늘 곁에 있을게요💗",
            "en": "🧧 Happy Lunar New Year! Chorong put on her hanbok to bow and wish you luck~ Take good care of yourself this year, we're always by your side 💗",
        },
        "bomi": {
            "zh_TW": "🧧 新年快樂～！普美元氣滿滿來拜年！今年也要一起大笑、一起運動、一起變得更健康喔💪✨",
            "ko": "🧧 새해 복 많이 받아요～! 보미가 에너지 가득 세배하러 왔어요! 올해도 같이 웃고 운동하고 더 건강해지자💪✨",
            "en": "🧧 Happy New Year~! Bomi's here to bow with full energy! Let's laugh, work out and get even healthier together this year 💪✨",
        },
        "eunji": {
            "zh_TW": "🧧 新年快樂！恩地穿韓服來跟你拜年～今年想唱更多好聽的歌給你聽，願你天天都有好心情🎤💙",
            "ko": "🧧 새해 복 많이 받으세요! 은지가 한복 입고 세배해요～ 올해는 더 좋은 노래 많이 들려줄게요, 매일 기분 좋은 일만 가득하길🎤💙",
            "en": "🧧 Happy Lunar New Year! Eunji bows in her hanbok~ I'll sing you even more songs this year, may every day bring you a good mood 🎤💙",
        },
        "namjoo": {
            "zh_TW": "🧧 新年快樂～南珠穿上漂亮韓服來拜年囉！紅包…不是啦，是滿滿的祝福要送給你💜🎀",
            "ko": "🧧 새해 복 많이 받으세요～ 남주가 예쁜 한복 입고 세배해요! 세뱃돈… 아니고, 복을 잔뜩 드릴게요💜🎀",
            "en": "🧧 Happy New Year~ Namjoo bows in her prettiest hanbok! Lucky money... no wait, a whole bag of blessings for you 💜🎀",
        },
        "hayoung": {
            "zh_TW": "🧧 新年快樂！忙內夏榮來拜年～今年也要吃得飽飽、睡得好好，地瓜跟福氣都分你一半🍠💛",
            "ko": "🧧 새해 복 많이 받으세요! 막내 하영이 세배드려요～ 올해도 잘 먹고 잘 자요, 고구마랑 복 반씩 나눠줄게요🍠💛",
            "en": "🧧 Happy Lunar New Year! Maknae Hayoung bows to you~ Eat well and sleep well this year, I'll share half my sweet potatoes and luck with you 🍠💛",
        },
    },
    "lantern": {
        "chorong": {
            "zh_TW": "🏮 元宵節快樂！初瓏提著燈籠來陪你～願這盞小燈照亮你今年每一條回家的路💗",
            "ko": "🏮 정월대보름이에요! 초롱이가 등불 들고 왔어요～ 이 작은 불빛이 올 한 해 집으로 가는 길을 밝혀주길💗",
            "en": "🏮 Happy Lantern Festival! Chorong brought a lantern for you~ May this little light brighten every road home this year 💗",
        },
        "bomi": {
            "zh_TW": "🏮 元宵節快樂～普美提燈籠衝第一！吃完湯圓一起去散步看燈吧，今年也要圓圓滿滿✨",
            "ko": "🏮 정월대보름 축하해요～ 보미가 등불 들고 일등으로 달려왔어요! 부럼 깨고 같이 달구경 산책 가요, 올해도 둥글둥글 원만하게✨",
            "en": "🏮 Happy Lantern Festival~ Bomi raced here first with her lantern! After the sweet rice balls let's go lantern-watching, here's to a well-rounded year ✨",
        },
        "eunji": {
            "zh_TW": "🏮 元宵節快樂！恩地在燈籠下為你唱一首小夜曲～願你的心願都像燈火一樣閃閃發亮🎤💙",
            "ko": "🏮 정월대보름이에요! 은지가 등불 아래서 세레나데 불러줄게요～ 소원이 다 불빛처럼 반짝반짝 이뤄지길🎤💙",
            "en": "🏮 Happy Lantern Festival! Eunji sings you a little serenade under the lanterns~ May all your wishes shine as bright as the lights 🎤💙",
        },
        "namjoo": {
            "zh_TW": "🏮 元宵節快樂～南珠的燈籠是不是最可愛？一起許願吧，湯圓要甜甜的、你也要甜甜的💜",
            "ko": "🏮 정월대보름 축하해요～ 남주 등불 제일 귀엽죠? 같이 소원 빌어요, 올해는 달콤한 일만 가득하길💜",
            "en": "🏮 Happy Lantern Festival~ Isn't Namjoo's lantern the cutest? Let's make a wish together, sweet rice balls and a sweet year for you 💜",
        },
        "hayoung": {
            "zh_TW": "🏮 元宵節快樂！夏榮的燈籠裡藏了一顆烤地瓜（開玩笑的啦）～猜燈謎猜對了就分你吃🍠💛",
            "ko": "🏮 정월대보름이에요! 하영이 등불 안에 군고구마 숨겨놨어요(농담이에요)～ 부럼 깨고 소원 꼭 빌어요🍠💛",
            "en": "🏮 Happy Lantern Festival! Hayoung hid a roasted sweet potato in her lantern (just kidding)~ Solve a lantern riddle and I'll share it 🍠💛",
        },
    },
    "mid_autumn": {
        "chorong": {
            "zh_TW": "🥮 中秋節快樂！初瓏陪你一起賞月～月亮圓圓的，願你和家人都平安團圓💗",
            "ko": "🥮 즐거운 추석 보내세요! 초롱이가 같이 달구경해요～ 보름달처럼 가족 모두 건강하고 행복하길💗",
            "en": "🥮 Happy Mid-Autumn Festival! Chorong is moon-gazing with you~ May you and your family be safe and together under the full moon 💗",
        },
        "bomi": {
            "zh_TW": "🥮 中秋節快樂～普美來報到！烤肉月餅都準備好了，吃飽飽再一起看最圓的月亮✨",
            "ko": "🥮 행복한 한가위 보내요～ 보미 출석! 송편이랑 맛있는 거 잔뜩 먹고 제일 둥근 달 같이 봐요✨",
            "en": "🥮 Happy Mid-Autumn~ Bomi reporting in! Barbecue and mooncakes are ready, let's eat up and watch the roundest moon together ✨",
        },
        "eunji": {
            "zh_TW": "🥮 中秋節快樂！今晚的月光好適合唱歌～恩地把最溫柔的一首送給你，願你被好好照顧🎤💙",
            "ko": "🥮 즐거운 추석이에요! 오늘 달빛이 노래하기 딱 좋네요～ 은지가 제일 따뜻한 노래 선물할게요, 늘 행복하길🎤💙",
            "en": "🥮 Happy Mid-Autumn Festival! Tonight's moonlight is perfect for singing~ Eunji dedicates her gentlest song to you, may you be well looked after 🎤💙",
        },
        "namjoo": {
            "zh_TW": "🥮 中秋節快樂～南珠在月亮下拍了好多張照片，最美的那張要跟你一起拍💜📸",
            "ko": "🥮 한가위 잘 보내요～ 남주가 달 아래서 사진 많이 찍었어요, 제일 예쁜 사진은 같이 찍어요💜📸",
            "en": "🥮 Happy Mid-Autumn~ Namjoo took so many photos under the moon, but the prettiest one is the one we take together 💜📸",
        },
        "hayoung": {
            "zh_TW": "🥮 中秋節快樂！夏榮的月餅是地瓜口味的～願你像滿月一樣圓滿，天天都開心🍠💛",
            "ko": "🥮 즐거운 추석 보내세요! 하영이 송편은 고구마 맛이에요～ 보름달처럼 마음도 꽉 차고 매일 행복하길🍠💛",
            "en": "🥮 Happy Mid-Autumn Festival! Hayoung's mooncake is sweet-potato flavored~ May your heart be as full as the moon and every day be happy 🍠💛",
        },
    },
}

PREVIEW_ACTION_FESTIVAL = {
    "festival_lunar_ny": "lunar_ny",
    "festival_lantern": "lantern",
    "festival_mid_autumn": "mid_autumn",
}


def festival_greeting(festival_key: str, member: str, lang: str) -> str | None:
    """The member's greeting for this festival in ``lang``; None for festivals without one."""
    by_member = FESTIVAL_GREETINGS.get(festival_key)
    if by_member is None:
        return None
    lines = by_member.get(member) or by_member["chorong"]
    return lines.get(lang) or lines["zh_TW"]
