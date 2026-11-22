"""app/engine/calendar.py — Holiday, Birthday, and Reminder Event Scheduler.

Lead Implementation: Antigravity.
Integrates with engine/contracts.py:
- Emits EventRequest with Priority.SYSTEM (L3)
- Supports Clock protocol and debug time offset
- Tracks daily limits and cooldowns
- Non-blocking, pure logic, headless-testable
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.engine.contracts import (
    ActorState,
    Clock,
    EventRequest,
    MEMBER_KEYS,
    Priority,
    SystemClock,
)

# ─────────────────────────────────────────────────────────────────────────────
# Birthday & Holiday Metadata
# ─────────────────────────────────────────────────────────────────────────────
USER_BIRTHDAY_GREETINGS: Dict[str, str] = {
    "chorong": "親愛的朋友 {nickname}，生日快樂！🎂 感謝你來到這個世界上，也感謝你的青春裡有 Apink 的旋律。隊長初瓏願你的新一歲每天都被溫柔與平安擁抱～謝謝你一直默默守護我們！🌸💖",
    "bomi": "嗷嗚～今天全宇宙最重要的 VIP 就是 {nickname} 啦！🎉 生日快樂！今天的減肥菜單通通作廢，炸醬麵、炸雞隨便吃！普美要把一整年份的大笑元氣通通灌注給你，許的願望全都要成真喔！啾咪！🍗😆",
    "eunji": "Hey {nickname}！祝你生日大快樂啊！🎤 又平安健康地長大了一歲，真替你驕傲！今天恩地把最高音的祝福唱給你聽，願你走過的每一條路都繁花似錦！今晚記得跟重要的人乾一杯喔！乾杯～🍻🎵",
    "namjoo": "最最可愛的 {nickname} 生日快樂！☀️ 今天南珠小太陽只為你一個人升起！把所有的煩惱都丟掉，吃口甜甜的蛋糕，接收滿滿的幸運維他命！今年一定要成為全世界最幸福的人喔～😋💖",
    "hayoung": "忙內夏榮祝 {nickname} 生日快樂！🎮 今天在人生的排位賽裡，你就是全場 MVP！剛出爐香噴噴的烤地瓜分你最大的一塊～今天不用努力工作，盡情享受屬於你的狂歡派對吧！耶～🍠🏆",
}

# Stretch reminders (written for this app, not member quotes).
SEDENTARY_LINES: Dict[str, List[str]] = {
    "zh_TW": [
        "⏰ 已經專注工作好一陣子囉！起身活動筋骨、喝口溫水吧～",
        "🐾 伸個懶腰～不要忘記眨眨眼睛放鬆一下！",
        "🍵 休息一下下！初瓏提醒您：愛護身體才能走得更長遠唷～",
        "💪 普美應援：站起來動一動！我們繼續加油！",
    ],
    "ko": [
        "⏰ 꽤 오래 집중했어요! 일어나서 스트레칭하고 따뜻한 물 한 잔 마셔요～",
        "🐾 기지개 쭉～ 눈도 깜빡깜빡 쉬어주는 거 잊지 마요!",
        "🍵 잠깐 쉬어가요! 초롱이의 알림: 몸을 아껴야 더 멀리 갈 수 있어요～",
        "💪 보미 응원: 일어나서 몸 좀 움직여요! 우리 계속 힘내요!",
    ],
    "en": [
        "⏰ You've been focused for a while! Stand up, stretch and sip some warm water~",
        "🐾 Big stretch~ Don't forget to blink and rest your eyes!",
        "🍵 Take a little break! Chorong's reminder: look after yourself to go the distance~",
        "💪 Bomi cheering: stand up and move around! Let's keep going!",
    ],
}

USER_BIRTHDAY_GREETINGS_I18N: Dict[str, Dict[str, str]] = {
    "chorong": {
        "zh_TW": "親愛的朋友 {nickname}，生日快樂！🎂 感謝你來到這個世界上，也感謝你的青春裡有 Apink 的旋律。隊長初瓏願你的新一歲每天都被溫柔與平安擁抱～謝謝你一直默默守護我們！🌸💖",
        "ko": "소중한 우리 {nickname}, 생일 축하해요!🎂 세상에 태어나줘서, 그리고 에이핑크의 노래를 함께해 줘서 진심으로 고마워요. 롱리더가 온 마음 다해 따뜻함과 평온을 빌어줄게요～ 사랑해요!🌸💖",
        "en": "Dearest {nickname}, Happy Birthday! 🎂 Thank you for gracing the world with your presence, and for letting Apink be the soundtrack of your youth. May your new year be wrapped in gentle peace and joy~ 🌸💖",
    },
    "bomi": {
        "zh_TW": "嗷嗚～今天全宇宙最重要的 VIP 就是 {nickname} 啦！🎉 生日快樂！今天的減肥菜單通通作廢，炸醬麵、炸雞隨便吃！普美要把一整年份的大笑元氣通通灌注給你，許的願望全都要成真喔！啾咪！🍗😆",
        "ko": "와아아～ 오늘 우주 최고의 주인공은 바로 {nickname}!🎉 생일 축하해요! 오늘만큼은 다이어트 금지, 짜장면에 치킨 맘껏 먹는 날이에요! 뽀미의 웃음 비타민 풀충전해서 쏩니다! 뿅!🍗😆",
        "en": "Woof! The official VIP of the universe today is {nickname}! 🎉 Happy Birthday! Forget diets today—eat all the Jajangmyeon and fried chicken you crave! Bomi sends a million megawatts of laughter your way! Chu! 🍗😆",
    },
    "eunji": {
        "zh_TW": "Hey {nickname}！祝你生日大快樂啊！🎤 又平安健康地長大了一歲，真替你驕傲！今天恩地把最高音的祝福唱給你聽，願你走過的每一條路都繁花似錦！今晚記得跟重要的人乾一杯喔！乾杯～🍻🎵",
        "ko": "야～ 우리 {nickname}! 생일 축하한다!🎤 건강하게 한 살 더 멋지게 자라줘서 뿌듯해! 오늘 은지가 시원한 3단 고음 축가 불러줄게. 걷는 길마다 꽃길만 펼쳐지길. 시원하게 짠하자!🍻🎵",
        "en": "Hey {nickname}! Happy Birthday to you! 🎤 So proud to see you grow another wonderful year. Eunji's belting out a personal high-note anthem for you today! May flowers bloom along every path you tread. Cheers! 🍻🎵",
    },
    "namjoo": {
        "zh_TW": "最最可愛的 {nickname} 生日快樂！☀️ 今天南珠小太陽只為你一個人升起！把所有的煩惱都丟掉，吃口甜甜的蛋糕，接收滿滿的幸運維他命！今年一定要成為全世界最幸福的人喔～😋💖",
        "ko": "세상에서 제일 사랑스러운 {nickname}, 생일 축하해요!☀️ 오늘 남주 해님은 오직 당신만을 위해 떠올랐어요! 달콤한 케이크 한입 베어 물고 행복 바이러스 듬뿍 받기 약속! 세상에서 제일 행복해요～😋💖",
        "en": "Dearest {nickname}, Happy Birthday! ☀️ Namjoo's sunshine is shining exclusively for you today! Toss away all worries, take a huge bite of sweet cake, and absorb pure joy. You deserve the absolute happiest year! 😋💖",
    },
    "hayoung": {
        "zh_TW": "忙內夏榮祝 {nickname} 生日快樂！🎮 今天在人生的排位賽裡，你就是全場 MVP！剛出爐香噴噴的烤地瓜分你最大的一塊～今天不用努力工作，盡情享受屬於你的狂歡派對吧！耶～🍠🏆",
        "ko": "막내 하영이가 우리 {nickname} 생일 축하해요!🎮 오늘 인생 랭크전의 단독 MVP는 바로 당신! 갓 구운 달콤한 군고구마 제일 큰 걸로 양보할게요～ 오늘은 열일 말고 신나게 즐겨요! 앗싸～🍠🏆",
        "en": "Maknae Hayoung wishes {nickname} the happiest birthday! 🎮 You're the unquestioned MVP in the ranked match of life today! Handing you the largest piping-hot sweet potato~ Have the ultimate victory blast today! 🍠🏆",
    },
}


@dataclass(frozen=True)
class SpecialDate:
    month: int
    day: int
    kind_suffix: str
    member: Optional[str]  # None for group anniversaries / general holidays
    title: str
    default_speech: str
    action: Optional[str] = None
    state: ActorState = ActorState.CHEER
    duration_s: float = 6.0
    title_i18n: Optional[Dict[str, str]] = None
    speech_i18n: Optional[Dict[str, str]] = None

    def get_speech(self, lang: str = "zh_TW") -> str:
        if self.speech_i18n and lang in self.speech_i18n:
            return self.speech_i18n[lang]
        return self.default_speech

    def get_title(self, lang: str = "zh_TW") -> str:
        if self.title_i18n and lang in self.title_i18n:
            return self.title_i18n[lang]
        return self.title


APINK_SPECIAL_DATES: Tuple[SpecialDate, ...] = (
    # Birthdays
    SpecialDate(
        month=3,
        day=3,
        kind_suffix="birthday.chorong",
        member="chorong",
        title="初瓏隊長生日 (Chorong Day)",
        title_i18n={
            "zh_TW": "初瓏隊長生日 (Chorong Day)",
            "ko": "초롱 리더 생일 (Chorong Day)",
            "en": "Leader Chorong Birthday",
        },
        default_speech="今天是初瓏隊長的生日！🎂 雖然平常總愛宅在家，但今天有粉熊們的祝福，心裡暖烘烘的～等等一定要吃上一大碗甜辣辣炒年糕慶祝！謝謝你們一直當初瓏最堅強的後盾～🐱💖",
        speech_i18n={
            "zh_TW": "今天是初瓏隊長的生日！🎂 雖然平常總愛宅在家，但今天有粉熊們的祝福，心裡暖烘烘的～等等一定要吃上一大碗甜辣辣炒年糕慶祝！謝謝你們一直當初瓏最堅強的後盾～🐱💖",
            "ko": "오늘은 우리 롱리더 초롱이의 생일이에요!🎂 평소엔 집순이지만 오늘은 팬더들의 사랑으로 마음이 몽글몽글해요～ 이따가 최애 떡볶이 꼭 챙겨 먹을게요! 언제나 초롱이 곁을 지켜줘서 고마워요～🐱💖",
            "en": "Today is Leader Chorong's birthday! 🎂 Though a homebody at heart, my soul is overflowing with Panda's love today~ Definitely celebrating with sweet & spicy tteokbokki later! Thank you for always being my warmest shelter~ 🐱💖",
        },
        action="birthday_cake",
        state=ActorState.CHEER,
    ),
    SpecialDate(
        month=4,
        day=15,
        kind_suffix="birthday.namjoo",
        member="namjoo",
        title="活力南珠生日 (Namjoo Day)",
        title_i18n={
            "zh_TW": "活力南珠生日 (Namjoo Day)",
            "ko": "비타민 남주 생일 (Namjoo Day)",
            "en": "Sunshine Namjoo Birthday",
        },
        default_speech="哇啊！今天是大明星金南珠的生日！☀️ 美食鑑賞家宣布今天全宇宙卡路里歸零～香辣雞爪、冰涼可樂通通安排上！謝謝大家給我滿滿的愛，小太陽會永遠為大家發光發熱！😋💖",
        speech_i18n={
            "zh_TW": "哇啊！今天是大明星金南珠的生日！☀️ 美食鑑賞家宣布今天全宇宙卡路里歸零～香辣雞爪、冰涼可樂通通安排上！謝謝大家給我滿滿的愛，小太陽會永遠為大家發光發熱！😋💖",
            "ko": "와아! 오늘은 비타민 남주의 생일이에요!☀️ 맛집 감별사가 선언합니다, 오늘 하루는 칼로리 제로! 매운 닭발이랑 시원한 콜라 파티할 거예요～ 큰 사랑 주셔서 감사해요, 언제나 환하게 빛나줄게요!😋💖",
            "en": "Yay! Today is Sunshine Namjoo's birthday! ☀️ The official food connoisseur declares zero calories for today—bring on the spicy chicken feet and ice-cold cola! Thank you for the endless love; I'll always shine bright for you! 😋💖",
        },
        action="birthday_cake",
        state=ActorState.CHEER,
    ),
    SpecialDate(
        month=7,
        day=19,
        kind_suffix="birthday.hayoung",
        member="hayoung",
        title="忙內夏榮生日 (Hayoung Day)",
        title_i18n={
            "zh_TW": "忙內夏榮生日 (Hayoung Day)",
            "ko": "막내 하영 생일 (Hayoung Day)",
            "en": "Maknae Hayoung Birthday",
        },
        default_speech="忙內夏榮今天過生日啦！🎮 姐姐們都祝我生日快樂了嗎？今天誰都不能阻止我吃熱騰騰的現烤地瓜跟剛出爐的麵包！不管是排位賽還是現實生活，有粉熊陪伴的每一天都是大吉大利～🍠✨",
        speech_i18n={
            "zh_TW": "忙內夏榮今天過生日啦！🎮 姐姐們都祝我生日快樂了嗎？今天誰都不能阻止我吃熱騰騰的現烤地瓜跟剛出爐的麵包！不管是排位賽還是現實生活，有粉熊陪伴的每一天都是大吉大利～🍠✨",
            "ko": "막내 하영이 생일 축하해 주세요!🎮 언니들 다 축하 메시지 보냈나 몰라～ 오늘만큼은 군고구마랑 갓 구운 빵 원 없이 먹을 거예요! 게임 랭크전도 일상도, 판다와 함께라면 늘 승리뿐이에요～🍠✨",
            "en": "It's Maknae Hayoung's birthday! 🎮 Wonder if all the unnies sent their wishes yet~ Nobody can stop me from devouring piping-hot sweet potatoes and freshly baked bread today! Victory in every game with Panda by my side~ 🍠✨",
        },
        action="birthday_cake",
        state=ActorState.CHEER,
    ),
    SpecialDate(
        month=8,
        day=13,
        kind_suffix="birthday.bomi",
        member="bomi",
        title="元氣普美生日 (Bomi Day)",
        title_i18n={
            "zh_TW": "元氣普美生日 (Bomi Day)",
            "ko": "비타민 뽀미 생일 (Bomi Day)",
            "en": "Energetic Bomi Birthday",
        },
        default_speech="大發！今天是我尹普美的生日耶！🎉 禮物不用多，給我一碗黑亮亮的炸醬麵和全雞大餐我就開心一整年～普美今天要把十年份的元氣通通回饋給粉熊！一起大笑過今天吧！화이팅！🍜🐶",
        speech_i18n={
            "zh_TW": "大發！今天是我尹普美的生日耶！🎉 禮物不用多，給我一碗黑亮亮的炸醬麵和全雞大餐我就開心一整年～普美今天要把十年份的元氣通通回饋給粉熊！一起大笑過今天吧！화이팅！🍜🐶",
            "ko": "대박! 오늘 뽀미 생일인 거 다들 아시죠?!🎉 선물 대신 윤기 흐르는 짜장면이랑 치킨 한 마리만 주면 일 년 내내 행복해요～ 받은 사랑 곱절로 보답할게요! 오늘 배꼽 빠지게 웃어봐요! 화이팅!🍜🐶",
            "en": "Daebak! It's Yoon Bomi's big day! 🎉 No fancy gifts needed—just a giant bowl of savory Jajangmyeon and crispy fried chicken! Giving all this vitamin energy right back to my Pandas. Let's laugh our hearts out today! 🍜🐶",
        },
        action="birthday_cake",
        state=ActorState.CHEER,
    ),
    SpecialDate(
        month=8,
        day=18,
        kind_suffix="birthday.eunji",
        member="eunji",
        title="主唱恩地生日 (Eunji Day)",
        title_i18n={
            "zh_TW": "主唱恩地生日 (Eunji Day)",
            "ko": "메인보컬 은지 생일 (Eunji Day)",
            "en": "Main Vocal Eunji Birthday",
        },
        default_speech="哈囉！今天是恩地的生日啦～🎤 感謝大家一路陪著我唱歌，你們的聲音就是我最好的共鳴箱！今晚要來杯冰涼高球配五花肉慶祝一下～希望我的歌聲能永遠成為你們生活裡的避風港！乾杯！🍻🎵",
        speech_i18n={
            "zh_TW": "哈囉！今天是恩地的生日啦～🎤 感謝大家一路陪著我唱歌，你們的聲音就是我最好的共鳴箱！今晚要來杯冰涼高球配五花肉慶祝一下～希望我的歌聲能永遠成為你們生活裡的避風港！乾杯！🍻🎵",
            "ko": "안녕! 오늘은 은지의 생일이에요～🎤 지금까지 제 목소리를 함께 울려준 우리 판다들 덕분에 노래해요! 오늘 밤엔 시원한 하이볼에 삼겹살 한 점 구워야겠어요～ 제 노래가 늘 여러분의 쉼표가 되길. 짠!🍻🎵",
            "en": "Hello there! It's Eunji's birthday! 🎤 Singing has meant everything because Panda's voices are my greatest resonator. Savoring a chilled highball and grilled pork belly tonight~ May my voice always be your sanctuary. Cheers! 🍻🎵",
        },
        action="birthday_cake",
        state=ActorState.CHEER,
    ),
    # Group Milestones & Holidays
    SpecialDate(
        month=4,
        day=19,
        kind_suffix="anniversary.apink419",
        member=None,
        title="Apink 出道週年紀念日 (419 Debut Anniversary)",
        title_i18n={
            "zh_TW": "Apink 出道週年紀念日 (419 Debut Anniversary)",
            "ko": "에이핑크 데뷔 기념일 (419 Debut Anniversary)",
            "en": "Apink Debut Anniversary",
        },
        default_speech="💖 419 是 Apink 和全體粉熊永遠的約定之日。走過十數載春華秋實，從最初的青澀到如今的默契，謝謝你們始終在台下揮舞著粉紅手燈，把每一個瞬間都變成了奇蹟。只要粉熊在，Apink 就永遠不會落幕。只要我們牽著手，那裡就是最燦爛的四月天。",
        speech_i18n={
            "zh_TW": "💖 419 是 Apink 和全體粉熊永遠的約定之日。走過十數載春華秋實，從最初的青澀到如今的默契，謝謝你們始終在台下揮舞著粉紅手燈，把每一個瞬間都變成了奇蹟。只要粉熊在，Apink 就永遠不會落幕。只要我們牽著手，那裡就是最燦爛的四月天。",
            "ko": "💖 4월 19일, 우리 에이핑크와 판다가 서로의 기적이 된 소중한 날이에요. 십수 년의 세월 동안 핑크빛 물결로 무대를 가득 채워줘서 고마워요. 판다가 있기에 에이핑크는 영원해요. 서로 손잡고 함께 걷는 모든 날이 찬란한 봄날입니다. 영원히 사랑해, 영원히 에이핑크!",
            "en": "💖 April 19th is the eternal promise between Apink and Pink Pandas. Over fifteen years of music and devotion, thank you for lighting up our universe with pink oceans. As long as Pandas are here, Apink will never fade. Walking hand in hand with you makes every day a blossoming spring.",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=8.0,
    ),
    SpecialDate(
        month=12,
        day=25,
        kind_suffix="holiday.christmas",
        member=None,
        title="聖誕節 (Merry Christmas)",
        title_i18n={
            "zh_TW": "聖誕節 (Merry Christmas)",
            "ko": "메리 크리스마스 (Merry Christmas)",
            "en": "Merry Christmas",
        },
        default_speech="🎄 叮叮噹～Merry Christmas！壁爐暖烘烘，窗外飄著小雪花～給努力了一整年的自己煮一杯熱可可吧！願聖誕的溫柔伴你一夜好眠～☕🎁",
        speech_i18n={
            "zh_TW": "🎄 叮叮噹～Merry Christmas！壁爐暖烘烘，窗外飄著小雪花～給努力了一整年的自己煮一杯熱可可吧！願聖誕的溫柔伴你一夜好眠～☕🎁",
            "ko": "🎄 메리 크리스마스! 난로는 따끈하고 창밖엔 하얀 눈이 내려요～ 고생한 나를 위해 달콤한 핫초코 한잔 선물해요! 따스하고 행복한 성탄절 보내요～☕🎁",
            "en": "🎄 Merry Christmas! A crackling fireplace and gentle snowflakes outside~ Treat yourself to a mug of hot cocoa. Wishing you a cozy, starlit Christmas Eve~ ☕🎁",
        },
        action="festival_christmas",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=4,
        day=18,
        kind_suffix="anniversary.solo.eunji",
        member="eunji",
        title="鄭恩地 Solo 出道紀念日 (Hopefully Sky)",
        title_i18n={
            "zh_TW": "鄭恩地 Solo 出道紀念日 (Hopefully Sky)",
            "ko": "정은지 솔로 데뷔일 (Hopefully Sky)",
            "en": "Jeong Eunji Solo Debut Anniversary",
        },
        default_speech="🌸 4/18 是恩地初次以個人歌手《Hopefully Sky》溫暖春天的日子。微風拂過耳際時，記得抬頭看看天空。有你們的聆聽，我的歌聲才能飛往更遠的地方～謝謝你們當我的晴空！🌱🎵",
        speech_i18n={
            "zh_TW": "🌸 4/18 是恩地初次以個人歌手《Hopefully Sky》溫暖春天的日子。微風拂過耳際時，記得抬頭看看天空。有你們的聆聽，我的歌聲才能飛往更遠的地方～謝謝你們當我的晴空！🌱🎵",
            "ko": "🌸 4월 18일, 은지가 《하늘바라기》로 첫 봄바람을 전했던 날이에요. 따스한 바람이 불어올 때면 하늘을 올려다보세요. 묵묵히 들어준 판다들이 있었기에 날아오를 수 있었어요. 언제나 고마워요!🌱🎵",
            "en": "🌸 April 18th is the anniversary of Eunji's solo debut Hopefully Sky. When a gentle spring breeze brushes your cheek, look up at the sky. Thank you for being the endless blue heaven that lets my voice soar! 🌱🎵",
        },
        action="special_sing_highnote",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=6,
        day=27,
        kind_suffix="anniversary.unit.bnn",
        member="bomi",
        title="Apink BnN 出道紀念日 (My Darling)",
        title_i18n={
            "zh_TW": "Apink BnN 出道紀念日 (My Darling)",
            "ko": "에이핑크 BnN 데뷔일 (My Darling)",
            "en": "Apink BnN Debut Anniversary",
        },
        default_speech="👭 6/27 是普美與南珠小分隊 BnN《My Darling》出道日！元氣雙人組上線～不管過多久，粉熊永遠是我們最寵溺的唯一 Darling！今天也要聽著輕快的歌聲甜蜜一整天喔～🍓✨",
        speech_i18n={
            "zh_TW": "👭 6/27 是普美與南珠小分隊 BnN《My Darling》出道日！元氣雙人組上線～不管過多久，粉熊永遠是我們最寵溺的唯一 Darling！今天也要聽著輕快的歌聲甜蜜一整天喔～🍓✨",
            "ko": "👭 6월 27일은 보미&남주 BnN 《My Darling》 데뷔일! 비타민 듀오 출동 완료～ 세월이 흘러도 판다는 우리의 영원한 달링인 거 알죠? 달콤한 멜로디 들으면서 행복한 하루 보내요～🍓✨",
            "en": "👭 June 27th is Apink BnN's (Bomi & Namjoo) debut with My Darling! The ultimate vitamin duo is here~ Pandas will forever be our sweetest darlings! Let the joyful rhythm brighten your entire day! 🍓✨",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=7,
        day=12,
        kind_suffix="anniversary.unit.chobom",
        member="chorong",
        title="初普 CHOBOM 出道紀念日 (Copycat)",
        title_i18n={
            "zh_TW": "初普 CHOBOM 出道紀念日 (Copycat)",
            "ko": "초봄 CHOBOM 데뷔일 (Copycat)",
            "en": "CHOBOM Debut Anniversary",
        },
        default_speech="🐱 7/12 是初瓏與普美 CHOBOM《Copycat》出道日！默契百分百的雙胞胎靈魂～連吃東西跟打哈欠都要互相模仿！今天跟著我們一起俏皮喵喵叫、踩著節奏搖擺吧～🐾💖",
        speech_i18n={
            "zh_TW": "🐱 7/12 是初瓏與普美 CHOBOM《Copycat》出道日！默契百分百的雙胞胎靈魂～連吃東西跟打哈欠都要互相模仿！今天跟著我們一起俏皮喵喵叫、踩著節奏搖擺吧～🐾💖",
            "ko": "🐱 7월 12일은 초롱&보미 초봄(CHOBOM) 《Copycat》 데뷔일! 눈빛만 봐도 통하는 영혼의 쌍둥이 자매～ 오늘은 우리 둘처럼 발걸음 가볍게, 장난기 넘치게 냥냥 펀치 날려봐요!🐾💖",
            "en": "🐱 July 12th marks CHOBOM's (Chorong & Bomi) debut with Copycat! Twin soulmates with flawless synergy~ Copying each other's smiles and dance moves! Shake off the routine and groove playfully like a cat today~ 🐾💖",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=8,
        day=21,
        kind_suffix="anniversary.solo.hayoung",
        member="hayoung",
        title="吳夏榮 Solo 出道紀念日 (Don't Make Me Laugh)",
        title_i18n={
            "zh_TW": "吳夏榮 Solo 出道紀念日 (Don't Make Me Laugh)",
            "ko": "오하영 솔로 데뷔일 (Don't Make Me Laugh)",
            "en": "Oh Hayoung Solo Debut Anniversary",
        },
        default_speech="🎮 8/21 是忙內夏榮 Solo 專輯《OH!》發行日！《Don't Make Me Laugh》那抹夏日的清爽笑容，是夏榮送給你們的專屬心動。今天也要看著夏榮開懷大笑喔～💛✨",
        speech_i18n={
            "zh_TW": "🎮 8/21 是忙內夏榮 Solo 專輯《OH!》發行日！《Don't Make Me Laugh》那抹夏日的清爽笑容，是夏榮送給你們的專屬心動。今天也要看著夏榮開懷大笑喔～💛✨",
            "ko": "🎮 8월 21일은 막내 하영이 솔로 앨범 《OH!》 데뷔일! 《Don't Make Me Laugh》의 청량한 미소 기억하시죠? 하영이가 건네는 상큼한 비타민 받고 오늘 하루 활짝 웃기로 약속해요～💛✨",
            "en": "🎮 August 21st celebrates Maknae Hayoung's solo debut with Don't Make Me Laugh! Bringing back that sparkling midsummer sweetness. Promise me you'll smile brightly all day long~ 💛✨",
        },
        action="special_gaming",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=9,
        day=7,
        kind_suffix="anniversary.solo.namjoo",
        member="namjoo",
        title="金南珠 Solo 出道紀念日 (Bird)",
        title_i18n={
            "zh_TW": "金南珠 Solo 出道紀念日 (Bird)",
            "ko": "김남주 솔로 데뷔일 (Bird)",
            "en": "Kim Namjoo Solo Debut Anniversary",
        },
        default_speech="👑 9/7 是南珠破繭成蝶、展翅高飛的《Bird》Solo 出道紀念日！無畏的目光與炙熱的舞台熱情，為你驅散所有迷茫。勇敢展翅吧，南珠永遠為你伴飛！🔥✨",
        speech_i18n={
            "zh_TW": "👑 9/7 是南珠破繭成蝶、展翅高飛的《Bird》Solo 出道紀念日！無畏的目光與炙熱的舞台熱情，為你驅散所有迷茫。勇敢展翅吧，南珠永遠為你伴飛！🔥✨",
            "ko": "👑 9월 7일은 남주가 당당하게 날아오른 《Bird》 솔로 데뷔일! 거침없는 무대 열정으로 여러분의 모든 불안을 날려버릴게요. 당당하게 날개를 펼쳐요, 남주가 곁에서 함께 날아줄게요!🔥✨",
            "en": "👑 September 7th commemorates Namjoo's fierce solo debut Bird! Fearless passion that breaks through every hesitation. Spread your wings with pride—Namjoo will always fly beside you! 🔥✨",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=12,
        day=31,
        kind_suffix="holiday.newyearseve",
        member=None,
        title="跨年夜 (New Year's Eve)",
        title_i18n={
            "zh_TW": "跨年夜 (New Year's Eve)",
            "ko": "연말 카운트다운 (New Year's Eve)",
            "en": "New Year's Eve",
        },
        default_speech="🎆 跨年夜到了！今晚一起倒數迎接新年吧！螢光棒充好電了嗎？回頭看看這一年，無論經歷了什麼風雨，你都堅持過來了！初瓏與 Apink 全員為你的努力用力鼓掌！準備好牽手迎接新年了嗎？👏💖",
        speech_i18n={
            "zh_TW": "🎆 跨年夜到了！今晚一起倒數迎接新年吧！螢光棒充好電了嗎？回頭看看這一年，無論經歷了什麼風雨，你都堅持過來了！初瓏與 Apink 全員為你的努力用力鼓掌！準備好牽手迎接新年了嗎？👏💖",
            "ko": "🎆 드디어 올해의 마지막 밤이에요! 오늘 밤 함께 새해 카운트다운해요! 응원봉 충전 완료했나요? 올 한 해 치열하게 달려온 당신, 정말 수고 많았어요. 에이핑크가 온 마음 다해 안아줄게요!👏💖",
            "en": "🎆 It's New Year's Eve! Let's count down to the new year together tonight! Lightsticks charged? Looking back on this year, you endured and shined through everything. Apink applauds you with all our hearts! 👏💖",
        },
        action="festival_new_year",
        state=ActorState.CHEER,
        duration_s=8.0,
    ),
    SpecialDate(
        month=1,
        day=1,
        kind_suffix="holiday.newyear",
        member=None,
        title="元旦新年 (Happy New Year)",
        title_i18n={
            "zh_TW": "元旦新年 (Happy New Year)",
            "ko": "새해 첫날 (Happy New Year)",
            "en": "New Year's Day",
        },
        default_speech="🎍 初升的太陽帶來全新希望！新年第一天，給自己一個大大的微笑吧～Apink 會繼續陪伴你度過每一個日常！晨光燦爛，出發囉！새해 복 많이 받으세요～🌅🌱",
        speech_i18n={
            "zh_TW": "🎍 初升的太陽帶來全新希望！新年第一天，給自己一個大大的微笑吧～Apink 會繼續陪伴你度過每一個日常！晨光燦爛，出發囉！새해 복 많이 받으세요～🌅🌱",
            "ko": "🎍 새해 첫 태양이 환하게 떠올랐어요! 첫날 아침, 활짝 웃으며 기분 좋게 시작해봐요～ 올 한 해도 에이핑크가 든든한 동반자가 되어줄게요! 새해 복 많이 받으세요～🌅🌱",
            "en": "🎍 The dawn brings fresh hopes! Greet the first morning of the year with a proud smile~ Apink will be your warmest daily companion. Happy New Year! 🌅🌱",
        },
        action="festival_new_year",
        state=ActorState.CHEER,
        duration_s=7.0,
    ),
    SpecialDate(
        month=1,
        day=5,
        kind_suffix="anniversary.first_win",
        member=None,
        title="Apink 歷史首座一位紀念日 (First Win Anniversary)",
        title_i18n={
            "zh_TW": "Apink 歷史首座一位紀念日 (First Win Anniversary)",
            "ko": "에이핑크 첫 1위 기념일 (First Win Anniversary)",
            "en": "Apink 1st Win Anniversary",
        },
        default_speech="🏆 1/5 是 Apink 憑藉《My My》拿到人生第一座一位的奇蹟之日！那天大家哭得連安可都唱不下去呢～這座獎盃是粉熊送給我們最珍貴的禮物，我們會一輩子銘記這份感動！✨",
        speech_i18n={
            "zh_TW": "🏆 1/5 是 Apink 憑藉《My My》拿到人生第一座一位的奇蹟之日！那天大家哭得連安可都唱不下去呢～這座獎盃是粉熊送給我們最珍貴的禮物，我們會一輩子銘記這份感動！✨",
            "ko": "🏆 1월 5일은 《My My》로 첫 1위를 거머쥔 기적 같은 날이에요! 무대 위에서 펑펑 울던 기억이 아직도 생생해요～ 판다가 만들어준 첫 1위, 평생 잊지 않고 보답할게요!✨",
            "en": "🏆 Jan 5th marks Apink's historic first music show win with My My! We cried so much on stage we could barely sing~ The first trophy Pandas gifted to us, forever cherished! ✨",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=8.0,
    ),
    SpecialDate(
        month=2,
        day=18,
        kind_suffix="anniversary.fandom.pinkpanda",
        member=None,
        title="粉熊誕生紀念日 (Pink Panda Fandom Day)",
        title_i18n={
            "zh_TW": "粉熊誕生紀念日 (Pink Panda Fandom Day)",
            "ko": "핑크판다 탄생일 (Pink Panda Fandom Day)",
            "en": "Pink Panda Official Fandom Day",
        },
        default_speech="🐼 2/18 是全體粉熊的專屬誕生紀念日！謝謝你們用粉紅色的手燈照亮了 Apink 的整片星空。因為有粉熊，我們的存在才有了意義！今天是屬於你的大日子，最愛你們了～💖",
        speech_i18n={
            "zh_TW": "🐼 2/18 是全體粉熊的專屬誕生紀念日！謝謝你們用粉紅色的手燈照亮了 Apink 的整片星空。因為有粉熊，我們的存在才有了意義！今天是屬於你的大日子，最愛你們了～💖",
            "ko": "🐼 2월 18일은 소중한 판다들의 탄생일! 핑크빛 응원봉으로 에이핑크의 우주를 가득 채워줘서 고마워요. 판다가 있기에 우리가 존재해요. 언제나 고맙고 사랑해요!💖",
            "en": "🐼 Feb 18th is the official Pink Panda Fandom Day! Thank you for lighting up Apink's universe with pink seas of light. You are our forever reason to sing. We love you always! 💖",
        },
        action="cheer",
        state=ActorState.CHEER,
        duration_s=8.0,
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Offset Clock (wraps any Clock, useful for Debug panel time shifting)
# ─────────────────────────────────────────────────────────────────────────────
class OffsetClock:
    """Clock adapter adding a fixed wall-clock offset (for debugging)."""

    def __init__(self, base: Clock, offset_seconds: float = 0.0) -> None:
        self.base = base
        self.offset_seconds = offset_seconds

    def now(self) -> _dt.datetime:
        return self.base.now() + _dt.timedelta(seconds=self.offset_seconds)

    def monotonic(self) -> float:
        # monotonic duration stays unaffected by calendar shifts
        return self.base.monotonic()

    def set_offset_hours(self, hours: float) -> None:
        self.offset_seconds = hours * 3600.0

    def set_target_date(self, year: int, month: int, day: int, hour: int = 12) -> None:
        current = self.base.now()
        target = _dt.datetime(year, month, day, hour, 0, 0)
        self.offset_seconds = (target - current).total_seconds()


# ─────────────────────────────────────────────────────────────────────────────
# Calendar Event Scheduler Engine
# ─────────────────────────────────────────────────────────────────────────────
class CalendarScheduler:
    """Evaluates time-based system events and produces Priority.SYSTEM EventRequests."""

    def __init__(
        self,
        clock: Optional[Clock] = None,
        dates: Sequence[SpecialDate] = APINK_SPECIAL_DATES,
        sedentary_interval_min: int = 45,  # 0 to disable
        enable_hourly_chime: bool = True,
        hourly_chime_range: Tuple[int, int] = (9, 22),  # 09:00 - 22:00
        user_birthday: Optional[Tuple[int, int]] = None,  # (month, day)
        user_nickname: str = "粉熊",
    ) -> None:
        self.clock: Clock = clock or SystemClock()
        self.dates = tuple(dates)
        self.sedentary_interval_min = sedentary_interval_min
        self.enable_hourly_chime = enable_hourly_chime
        self.hourly_chime_range = hourly_chime_range
        self.user_birthday = user_birthday
        self.user_nickname = user_nickname

        # Tracking state
        self._last_sedentary_check: float = self.clock.monotonic()
        self._last_chime_hour: Optional[int] = None
        self._triggered_dates_today: set[str] = set()
        self._last_date_str: str = ""

    def set_user_birthday(
        self, month: Optional[int], day: Optional[int], nickname: Optional[str] = None
    ) -> None:
        """Configure user's personal birthday so the 5 pandas can celebrate!"""
        if month is not None and day is not None:
            self.user_birthday = (month, day)
        else:
            self.user_birthday = None
        if nickname:
            self.user_nickname = nickname

    def check_user_birthday(self, active_member: str, lang: str = "zh_TW") -> Optional[EventRequest]:
        """Check if today is the user's personal birthday and celebrate!"""
        if not self.user_birthday:
            return None

        now = self.clock.now()
        self._reset_daily_tracker_if_needed(now)

        b_month, b_day = self.user_birthday
        if now.month == b_month and now.day == b_day:
            trigger_key = f"{self._last_date_str}:user_birthday"
            if trigger_key in self._triggered_dates_today:
                return None

            self._triggered_dates_today.add(trigger_key)

            templates = USER_BIRTHDAY_GREETINGS_I18N.get(active_member, {})
            template = templates.get(
                lang,
                USER_BIRTHDAY_GREETINGS.get(
                    active_member,
                    "祝親愛的 {nickname} 生日快樂！🎂 謝謝你一直以來的陪伴，今天你是全世界最棒的主角～",
                ),
            )
            speech = template.format(nickname=self.user_nickname)
            title_map = {
                "zh_TW": f"🎉 祝 {self.user_nickname} 生日快樂！",
                "ko": f"🎉 {self.user_nickname}님 생일을 축하해요!",
                "en": f"🎉 Happy Birthday, {self.user_nickname}!",
            }
            title = title_map.get(lang, f"🎉 祝 {self.user_nickname} 生日快樂！")

            return EventRequest(
                kind="calendar.birthday.user",
                priority=Priority.SYSTEM,
                state=ActorState.CHEER,
                action="birthday_cake",
                duration_s=8.0,
                daily_limit=1,
                wakes_sleep=True,
                payload={
                    "text": speech,
                    "title": title,
                    "target_member": active_member,
                    "is_user_birthday": True,
                },
                source="calendar.user_birthday",
            )
        return None

    def _get_today_str(self, now: _dt.datetime) -> str:
        return now.strftime("%Y-%m-%d")

    def _reset_daily_tracker_if_needed(self, now: _dt.datetime) -> None:
        today = self._get_today_str(now)
        if today != self._last_date_str:
            self._last_date_str = today
            self._triggered_dates_today.clear()
            self._last_chime_hour = None

    def check_special_dates(self, active_member: str, lang: str = "zh_TW") -> List[EventRequest]:
        """Check if today matches any birthday or anniversary."""
        now = self.clock.now()
        self._reset_daily_tracker_if_needed(now)

        results: List[EventRequest] = []
        for d in self.dates:
            if d.month == now.month and d.day == now.day:
                trigger_key = f"{self._last_date_str}:{d.kind_suffix}"
                if trigger_key in self._triggered_dates_today:
                    continue

                # Mark as triggered today
                self._triggered_dates_today.add(trigger_key)

                # Prioritize speech matching current active member or target member
                payload = {
                    "text": d.get_speech(lang),
                    "title": d.get_title(lang),
                    "target_member": d.member or active_member,
                    "is_birthday": "birthday" in d.kind_suffix,
                    "is_anniversary": "anniversary" in d.kind_suffix,
                }

                req = EventRequest(
                    kind=f"calendar.{d.kind_suffix}",
                    priority=Priority.SYSTEM,
                    state=d.state,
                    action=d.action,
                    duration_s=d.duration_s,
                    daily_limit=1,
                    wakes_sleep=True,
                    payload=payload,
                    source="calendar.special_date",
                )
                results.append(req)

        return results

    def check_hourly_chime(self, lang: str = "zh_TW") -> Optional[EventRequest]:
        """Check for top-of-the-hour chime during daytime."""
        if not self.enable_hourly_chime:
            return None

        now = self.clock.now()
        self._reset_daily_tracker_if_needed(now)

        start_h, end_h = self.hourly_chime_range
        # Check if we are in window and minute is 0 (or close to 0)
        if start_h <= now.hour <= end_h:
            if self._last_chime_hour != now.hour and now.minute == 0:
                self._last_chime_hour = now.hour
                hour_12 = now.hour % 12 or 12
                pm = now.hour >= 12
                if lang == "ko":
                    speech = (f"⏰ 정각 알림: 지금은 {'오후' if pm else '오전'} {hour_12}시예요! "
                              "수고 많았어요, 물 한 잔 마시고 쉬어가요～")
                elif lang == "en":
                    speech = (f"⏰ Hourly chime: it's {hour_12} {'PM' if pm else 'AM'}! "
                              "Great work — grab some water and take a short break~")
                else:
                    speech = f"⏰ 整點報時：現在是{'下午' if pm else '上午'} {hour_12} 點整！工作辛苦了，喝口水休息一下吧～"

                return EventRequest(
                    kind=f"calendar.chime.{now.hour}",
                    priority=Priority.SYSTEM,
                    state=ActorState.CHEER,
                    action=None,
                    duration_s=4.0,
                    daily_limit=1,
                    wakes_sleep=False,  # don't wake up sleeping panda
                    payload={"text": speech, "hour": now.hour, "type": "chime"},
                    source="calendar.hourly_chime",
                )
        return None

    def check_sedentary_reminder(
        self, user_active_monotonic: Optional[float] = None, lang: str = "zh_TW"
    ) -> Optional[EventRequest]:
        """Check if user has been sitting/working for too long."""
        if self.sedentary_interval_min <= 0:
            return None

        mono = self.clock.monotonic()
        interval_s = self.sedentary_interval_min * 60.0

        # Reference time is either the last time reminder fired or user activity
        elapsed = mono - self._last_sedentary_check
        if elapsed >= interval_s:
            self._last_sedentary_check = mono

            quotes = SEDENTARY_LINES.get(lang, SEDENTARY_LINES["zh_TW"])
            import random
            speech = random.choice(quotes)

            return EventRequest(
                kind="reminder.sedentary",
                priority=Priority.SYSTEM,
                state=ActorState.CHEER,
                action=None,
                duration_s=5.0,
                cooldown_s=interval_s * 0.8,
                wakes_sleep=False,
                payload={"text": speech, "type": "sedentary"},
                source="calendar.sedentary",
            )
        return None

    def poll_all_due_events(
        self,
        active_member: str,
        user_active_monotonic: Optional[float] = None,
        lang: str = "zh_TW",
    ) -> List[EventRequest]:
        """Single polling cycle checking all calendar & health triggers."""
        events: List[EventRequest] = []

        # 1. User's personal birthday (Highest emotional priority!)
        user_bday = self.check_user_birthday(active_member, lang=lang)
        if user_bday:
            events.append(user_bday)

        # 2. Apink special calendar dates (birthdays / anniversaries)
        events.extend(self.check_special_dates(active_member, lang=lang))

        # 3. Hourly chime
        chime = self.check_hourly_chime(lang=lang)
        if chime:
            events.append(chime)

        # 4. Sedentary reminder
        sedentary = self.check_sedentary_reminder(user_active_monotonic, lang=lang)
        if sedentary:
            events.append(sedentary)

        return events
