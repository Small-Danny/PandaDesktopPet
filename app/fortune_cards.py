"""Trilingual original fortune cards and companion persona lines."""
from dataclasses import dataclass

@dataclass(frozen=True)
class TarotCard:
    key: str
    badge: dict[str, str]
    title: dict[str, str]
    stars: str
    message: dict[str, str]
    lucky: dict[str, str]
    accent: str


BASE_TAROT_CARDS: tuple[TarotCard, ...] = (
    TarotCard(
        key="two_hearts",
        badge={"zh_TW": "愛情 · 陪伴牌", "ko": "사랑 · 동행 카드", "en": "Love · Companionship"},
        title={"zh_TW": "TWO HEARTS · 雙心共振", "ko": "TWO HEARTS · 두 마음의 공명", "en": "TWO HEARTS · Resonance"},
        stars="★★★★★",
        message={
            "zh_TW": "恩地微笑翻出這張閃閃發光的雙心牌！今天溫柔的交流特別有緣分，記得把暖意分享給重要的人喔。",
            "ko": "은지가 반짝이는 두 하트 카드를 뽑았어요! 오늘은 따뜻한 대화에 행운이 가득하니 소중한 사람에게 마음을 전해 보세요.",
            "en": "Eunji smiles as Two Hearts glows! Warm, honest words carry extra magic today—share a kind moment with someone dear.",
        },
        lucky={"zh_TW": "幸運色：粉熊珊瑚粉", "ko": "행운 컬러: 판다 코랄 핑크", "en": "Lucky color: Panda Coral Pink"},
        accent="#f472b6",
    ),
    TarotCard(
        key="the_star",
        badge={"zh_TW": "夢想 · 舞台牌", "ko": "꿈 · 무대 카드", "en": "Dream · Stage"},
        title={"zh_TW": "THE STAR · 星光舞台", "ko": "THE STAR · 별빛 무대", "en": "THE STAR · Spotlight"},
        stars="★★★★★",
        message={
            "zh_TW": "水晶球映出大巨蛋般的璀璨星海！手邊默默努力的事情正在發亮，照自己的節奏穩穩前進就對了。",
            "ko": "수정구슬 속에 반짝이는 별바다가 펼쳐졌어요! 꾸준히 해 온 일들이 곧 빛을 발할 거예요.",
            "en": "The crystal ball shimmers like a dome sea of stars! Quiet effort you've put in is ready to shine at your own pace.",
        },
        lucky={"zh_TW": "幸運色：恩地晴空藍", "ko": "행운 컬러: 은지 스카이 블루", "en": "Lucky color: Eunji Sky Blue"},
        accent="#38bdf8",
    ),
    TarotCard(
        key="wheel_of_panda",
        badge={"zh_TW": "好運 · 轉機牌", "ko": "행운 · 전환점 카드", "en": "Fortune · Serendipity"},
        title={"zh_TW": "WHEEL OF PANDA · 粉熊轉運", "ko": "WHEEL OF PANDA · 판다 행운의 수레바퀴", "en": "WHEEL OF PANDA · Good Turn"},
        stars="★★★★☆",
        message={
            "zh_TW": "星盤順著粉紅色星塵輕輕轉動～今天容易遇見意想不到的小確幸，放輕鬆迎接剛好的驚喜吧。",
            "ko": "핑크빛 별가루를 따라 운명의 수레바퀴가 돌아요~ 뜻밖의 소소한 행복이 찾아올 하루예요.",
            "en": "Stardust turns the wheel gently in pink light—expect a pleasant little coincidence or welcome surprise today.",
        },
        lucky={"zh_TW": "幸運小物：熱拿鐵／暖心音樂", "ko": "행운 아이템: 따뜻한 라떼 · 좋은 노래", "en": "Lucky charm: Warm latte & favorite song"},
        accent="#a78bfa",
    ),
    TarotCard(
        key="the_sun",
        badge={"zh_TW": "元氣 · 活力牌", "ko": "활력 · 에너지 카드", "en": "Vitality · Warmth"},
        title={"zh_TW": "THE SUN · 暖陽微笑", "ko": "THE SUN · 따스한 햇살", "en": "THE SUN · Bright Smile"},
        stars="★★★★★",
        message={
            "zh_TW": "水晶球散發著金黃暖光！今天精神特別清澈明亮，適合把卡關的小任務一口氣輕鬆解決。",
            "ko": "수정구슬이 따스한 황금빛으로 빛나요! 맑은 컨디션으로 밀린 일도 가볍게 해결할 수 있는 날이에요.",
            "en": "Golden light fills the crystal ball! Clear focus makes today great for breezing through any lingering task.",
        },
        lucky={"zh_TW": "幸運色：夏榮檸檬黃", "ko": "행운 컬러: 하영 레몬 옐로우", "en": "Lucky color: Lemon Gold"},
        accent="#fbbf24",
    ),
    TarotCard(
        key="moonlight_calm",
        badge={"zh_TW": "療癒 · 休息牌", "ko": "힐링 · 휴식 카드", "en": "Calm · Recharge"},
        title={"zh_TW": "MOONLIGHT · 靜謐微風", "ko": "MOONLIGHT · 달빛 산들바람", "en": "MOONLIGHT · Gentle Pause"},
        stars="★★★★☆",
        message={
            "zh_TW": "恩地幫你泡好一杯熱茶～這張牌提醒你別太急著趕路，給自己五分鐘伸個懶腰，靈感就會跟著回來。",
            "ko": "은지가 따뜻한 차를 건네며 건넨 카드예요~ 너무 서두르지 말고 잠깐 숨을 고르면 좋은 아이디어가 떠올라요.",
            "en": "A gentle reminder to breathe and stretch for five minutes—clear calm brings your best inspiration back.",
        },
        lucky={"zh_TW": "幸運動作：起身喝口水休息", "ko": "행운 행동: 물 한 잔 마시고 스트레칭", "en": "Lucky habit: Sip water & stretch"},
        accent="#818cf8",
    ),
    TarotCard(
        key="miracle_pink",
        badge={"zh_TW": "守護 · 奇蹟牌", "ko": "수호 · 기적 카드", "en": "Miracle · Guard"},
        title={"zh_TW": "LA VIE EN PINK · 花路同行", "ko": "LA VIE EN PINK · 꽃길 동행", "en": "LA VIE EN PINK · Panda Bless"},
        stars="★★★★★",
        message={
            "zh_TW": "五位熊貓一起送上滿滿祝福！今天做任何決定都可以相信自己的直覺，我們都在旁邊替你加油。",
            "ko": "다섯 판다가 함께 응원을 보내요! 오늘은 스스로의 직감을 믿고 나아가도 좋아요, 늘 옆에서 응원할게요.",
            "en": "All five pandas send their cheer! Trust your intuition today—your little panda crew is cheering right behind you.",
        },
        lucky={"zh_TW": "幸運語：Apink & PANDA", "ko": "행운 키워드: 에이핑크 & 판다", "en": "Lucky phrase: Apink & PANDA"},
        accent="#ec4899",
    ),
)

ARGON_FORTUNE_CARDS: tuple[TarotCard, ...] = (
    TarotCard(
        key="crystal_focus",
        badge={"zh_TW": "學業 · 專注牌", "ko": "학업 · 집중 카드", "en": "Study · Focus"},
        title={"zh_TW": "CRYSTAL OWL · 澄澈專注", "ko": "CRYSTAL OWL · 맑은 집중력", "en": "CRYSTAL OWL · Clear Focus"},
        stars="★★★★★",
        message={
            "zh_TW": "讀書與工作的思緒像水晶一樣透亮！先從最重要的一件小事動手，就能順暢進入高效專注狀態。",
            "ko": "공부와 업무 집중력이 수정처럼 맑아지는 날이에요! 가장 중요한 작은 일부터 시작하면 술술 풀릴 거예요.",
            "en": "Your mind is crystal clear for study and work! Start with one priority step and smooth flow will follow.",
        },
        lucky={"zh_TW": "幸運色：恩地晴空藍", "ko": "행운 컬러: 은지 스카이 블루", "en": "Lucky color: Eunji Sky Blue"},
        accent="#60a5fa",
    ),
    TarotCard(
        key="muse_melody",
        badge={"zh_TW": "靈感 · 創作牌", "ko": "영감 · 창작 카드", "en": "Muse · Creativity"},
        title={"zh_TW": "MELODY MUSE · 靈感旋律", "ko": "MELODY MUSE · 영감의 멜로디", "en": "MELODY MUSE · Spark of Art"},
        stars="★★★★★",
        message={
            "zh_TW": "音符在水晶球旁輕快跳躍～腦海閃過的奇妙點子別急著否定，隨手記下來會成為超棒的亮點。",
            "ko": "수정구슬 곁에 경쾌한 음표가 춤추고 있어요~ 문득 떠오른 아이디어를 메모해 두면 멋진 결과로 이어져요.",
            "en": "Musical notes dance around the crystal ball—jot down any sudden spark of an idea before it slips away.",
        },
        lucky={"zh_TW": "幸運小物：隨身筆記本／耳機", "ko": "행운 아이템: 작은 메모장 · 이어폰", "en": "Lucky charm: Pocket notebook & earphones"},
        accent="#38bdf8",
    ),
    TarotCard(
        key="noble_friend",
        badge={"zh_TW": "友情 · 貴人牌", "ko": "우정 · 귀인 카드", "en": "Friendship · Ally"},
        title={"zh_TW": "PINK CLOVER · 暖心貴人", "ko": "PINK CLOVER · 다정한 귀인", "en": "PINK CLOVER · Kind Ally"},
        stars="★★★★★",
        message={
            "zh_TW": "初瓏般的溫柔守護正在靠近！遇到猶豫的事不妨開口請教身邊夥伴，可靠的貴人就在你身邊。",
            "ko": "초롱처럼 다정한 든든함이 다가오고 있어요! 고민되는 일은 주변 동료에게 편하게 조언을 구해 보세요.",
            "en": "Gentle support is close at hand! Ask a trusted friend or teammate when in doubt—a kind ally is nearby.",
        },
        lucky={"zh_TW": "幸運色：初瓏櫻花粉", "ko": "행운 컬러: 초롱 벚꽃 핑크", "en": "Lucky color: Chorong Sakura Pink"},
        accent="#f472b6",
    ),
    TarotCard(
        key="golden_pocket",
        badge={"zh_TW": "荷包 · 豐盛牌", "ko": "재물 · 풍요 카드", "en": "Abundance · Reward"},
        title={"zh_TW": "GOLDEN ACORN · 豐收果實", "ko": "GOLDEN ACORN · 풍요의 열매", "en": "GOLDEN ACORN · Sweet Harvest"},
        stars="★★★★☆",
        message={
            "zh_TW": "點滴累積的付出準備結出金黃果實～今天適合整理收支或犒賞自己一份小點心，守住荷包更有福氣。",
            "ko": "차곡차곡 쌓아 온 노력이 황금빛 열매를 맺어요~ 지출을 가볍게 점검하고 작은 간식으로 스스로를 격려해 보세요.",
            "en": "Steady effort ripens into golden fruit—review your budget mindfully and treat yourself to a small snack.",
        },
        lucky={"zh_TW": "幸運色：夏榮蜂蜜黃", "ko": "행운 컬러: 하영 허니 옐로우", "en": "Lucky color: Hayoung Honey Yellow"},
        accent="#fbbf24",
    ),
    TarotCard(
        key="cozy_pillow",
        badge={"zh_TW": "舒壓 · 好眠牌", "ko": "휴식 · 꿀잠 카드", "en": "Rest · Sweet Dreams"},
        title={"zh_TW": "DREAM PILLOW · 雲朵好眠", "ko": "DREAM PILLOW · 구름 꿀잠", "en": "DREAM PILLOW · Cozy Slumber"},
        stars="★★★☆☆",
        message={
            "zh_TW": "水晶球浮現軟綿綿的雲朵～最近真的辛苦了，今晚提早放下手機好好睡一覺，充飽電明天更閃亮。",
            "ko": "수정구슬에 포근한 구름이 떠올랐어요~ 최근 많이 바빴다면 오늘 밤엔 일찍 눈을 붙이고 푹 쉬어 주세요.",
            "en": "Fluffy clouds drift across the crystal ball—put your phone down early tonight for a deep, restful sleep.",
        },
        lucky={"zh_TW": "幸運動作：睡前溫水泡腳／早睡", "ko": "행운 행동: 따뜻한 물 샤워 · 일찍 자기", "en": "Lucky habit: Early bedtime & warm blanket"},
        accent="#a78bfa",
    ),
    TarotCard(
        key="brave_compass",
        badge={"zh_TW": "勇氣 · 挑戰牌", "ko": "용기 · 도전 카드", "en": "Courage · Adventure"},
        title={"zh_TW": "BRAVE PAW · 勇敢跨步", "ko": "BRAVE PAW · 용기 있는 한 걸음", "en": "BRAVE PAW · Bold Step"},
        stars="★★★★★",
        message={
            "zh_TW": "普美滿滿的元氣為你應援！別害怕還沒發生的小困難，勇敢踏出第一步就會發現道路比想像更寬廣。",
            "ko": "보미의 활기찬 에너지가 응원해요! 시작도 전에 걱정하기보다 용기 내어 첫걸음을 내디디면 길이 열릴 거예요.",
            "en": "Bomi's bright energy cheers you on! Take that bold first step and you'll find the road wider than expected.",
        },
        lucky={"zh_TW": "幸運色：普美陽光珊瑚橘", "ko": "행운 컬러: 보미 선샤인 코랄", "en": "Lucky color: Bomi Sunshine Coral"},
        accent="#fb923c",
    ),
    TarotCard(
        key="breeze_stroll",
        badge={"zh_TW": "散步 · 轉運牌", "ko": "산책 · 기분전환 카드", "en": "Stroll · Fresh Air"},
        title={"zh_TW": "BREEZE PATH · 微風散步", "ko": "BREEZE PATH · 산들바람 산책", "en": "BREEZE PATH · Fresh Stroll"},
        stars="★★★★☆",
        message={
            "zh_TW": "感覺悶悶的時候就出門走走吧～換條路線吹吹微風或買杯喜歡的飲料，好心情與好運氣會一起跟上來。",
            "ko": "답답할 땐 잠깐 밖으로 나가 바람을 쐬어 보세요~ 가벼운 산책과 좋아하는 음료가 기분 좋은 행운을 불러와요.",
            "en": "Step outside for a short walk when things feel stuck—fresh air and a favorite drink invite good luck back.",
        },
        lucky={"zh_TW": "幸運動作：戶外散步十分鐘", "ko": "행운 행동: 10분 가벼운 산책", "en": "Lucky habit: A 10-minute outdoor walk"},
        accent="#34d399",
    ),
    TarotCard(
        key="gentle_umbrella",
        badge={"zh_TW": "從容 · 提醒牌", "ko": "여유 · 마인드 카드", "en": "Patience · Care"},
        title={"zh_TW": "SOFT UMBRELLA · 慢步從容", "ko": "SOFT UMBRELLA · 여유로운 걸음", "en": "SOFT UMBRELLA · Steady Pace"},
        stars="★★★☆☆",
        message={
            "zh_TW": "恩地輕聲提醒你今天別給自己太大壓力～偶爾進度慢一點也沒關係，溫柔對待自己才走得長遠。",
            "ko": "은지가 오늘은 스스로를 너무 다그치지 말라고 전해요~ 조금 천천히 가도 괜찮으니 마음을 편안히 가져 보세요.",
            "en": "Eunji gently reminds you not to rush yourself today—a kinder, steadier pace carries you much further.",
        },
        lucky={"zh_TW": "幸運小物：晴雨傘／溫熱草本茶", "ko": "행운 아이템: 우산 · 따뜻한 허브티", "en": "Lucky charm: Umbrella & warm herbal tea"},
        accent="#f9a8d4",
    ),
    TarotCard(
        key="sweet_feast",
        badge={"zh_TW": "美食 · 充電牌", "ko": "미식 · 충전 카드", "en": "Gourmet · Joy"},
        title={"zh_TW": "HAPPY TABLE · 美味充電", "ko": "HAPPY TABLE · 맛있는 충전", "en": "HAPPY TABLE · Tasty Recharge"},
        stars="★★★★☆",
        message={
            "zh_TW": "吃飽飽才有氣力繼續前進！今天適合享用熱騰騰的美味料理，讓味蕾的幸福感幫你把煩惱通通趕跑。",
            "ko": "맛있는 음식이 최고의 에너지가 되는 날이에요! 따뜻한 식사 한 끼로 지친 마음을 기분 좋게 채워 보세요.",
            "en": "Good food is the best fuel today! Enjoy a warm, delicious meal and let simple comfort melt stress away.",
        },
        lucky={"zh_TW": "幸運美食：熱湯麵／香脆點心", "ko": "행운 메뉴: 따뜻한 국물 요리 · 디저트", "en": "Lucky treat: Warm noodles & crispy snack"},
        accent="#fb923c",
    ),
    TarotCard(
        key="violet_crown",
        badge={"zh_TW": "自信 · 魅力牌", "ko": "자신감 · 매력 카드", "en": "Confidence · Charm"},
        title={"zh_TW": "VIOLET CROWN · 閃耀自信", "ko": "VIOLET CROWN · 빛나는 자신감", "en": "VIOLET CROWN · Radiant Crown"},
        stars="★★★★★",
        message={
            "zh_TW": "南珠小太陽般的笑容照亮全場！上台報告或表達想法時請大方展現自己，你的真誠就是最迷人的光芒。",
            "ko": "남주처럼 밝은 미소가 빛을 발하는 날이에요! 발표나 대화에서 당당하게 생각을 전하면 매력이 더욱 돋보여요.",
            "en": "Namjoo's sunny confidence lights the room! Speak up with a genuine smile—your sincerity is your best charm.",
        },
        lucky={"zh_TW": "幸運色：南珠夢幻星願紫", "ko": "행운 컬러: 남주 드림 퍼플", "en": "Lucky color: Namjoo Dream Purple"},
        accent="#c084fc",
    ),
    TarotCard(
        key="lucky_gamepad",
        badge={"zh_TW": "機智 · 破關牌", "ko": "기지 · 클리어 카드", "en": "Strategy · Clear"},
        title={"zh_TW": "STAGE CLEAR · 機智破關", "ko": "STAGE CLEAR · 기분 좋은 클리어", "en": "STAGE CLEAR · Quest Clear"},
        stars="★★★★☆",
        message={
            "zh_TW": "就像忙內夏榮打遊戲完美通關！今天遇到複雜問題只要拆成小步驟逐一擊破，就能輕鬆迎來勝利畫面。",
            "ko": "막내 하영이가 게임을 클리어하듯 명쾌한 날이에요! 복잡한 문제도 작은 단계로 나누어 하나씩 해결해 보세요.",
            "en": "Like Hayoung clearing a tricky game stage—break complex tasks into small steps and clear them one by one.",
        },
        lucky={"zh_TW": "幸運色：夏榮檸檬奶黃", "ko": "행운 컬러: 하영 레몬 옐로우", "en": "Lucky color: Hayoung Lemon Yellow"},
        accent="#facc15",
    ),
    TarotCard(
        key="feather_letter",
        badge={"zh_TW": "佳音 · 傳訊牌", "ko": "소식 · 연락 카드", "en": "Good News · Message"},
        title={"zh_TW": "SKY LETTER · 晴空佳音", "ko": "SKY LETTER · 푸른 하늘의 소식", "en": "SKY LETTER · Bluebird Note"},
        stars="★★★★☆",
        message={
            "zh_TW": "乘著微風的信鴿帶來好消息～等待中的回覆或主動寄出的問候會有溫暖回音，記得留意今天的訊息喔。",
            "ko": "기분 좋은 바람을 타고 반가운 소식이 찾아와요~ 기다리던 답장이나 먼저 건넨 안부에 따뜻한 메아리가 돌아올 거예요.",
            "en": "A pleasant breeze carries welcome news—a reply you've been waiting for or a kind check-in brings warm echoes.",
        },
        lucky={"zh_TW": "幸運動作：傳句暖心問候給朋友", "ko": "행운 행동: 반가운 안부 메시지 보내기", "en": "Lucky habit: Send a warm hello to a friend"},
        accent="#7dd3fc",
    ),
    TarotCard(
        key="harmony_tea",
        badge={"zh_TW": "傾聽 · 和諧牌", "ko": "경청 · 조화 카드", "en": "Harmony · Empathy"},
        title={"zh_TW": "WARM TEACUP · 靜心傾聽", "ko": "WARM TEACUP · 따뜻한 경청", "en": "WARM TEACUP · Warm Teacup"},
        stars="★★★☆☆",
        message={
            "zh_TW": "溝通遇到不同意見時，先喝口茶微笑傾聽吧～放慢語速多一分體諒，原本緊繃的氣氛就會柔和化解。",
            "ko": "의견이 다를 땐 따뜻한 차 한 모금과 함께 먼저 귀를 기울여 보세요~ 한 박자 천천히 말하면 분위기가 부드러워져요.",
            "en": "When views differ, sip warm tea and listen first—a slower, kinder tone softens tension into harmony.",
        },
        lucky={"zh_TW": "幸運飲品：溫熱抹茶／烏龍茶", "ko": "행운 음료: 따뜻한 말차 · 우롱차", "en": "Lucky drink: Warm matcha or oolong tea"},
        accent="#f472b6",
    ),
    TarotCard(
        key="lightstick_promise",
        badge={"zh_TW": "初心 · 約定牌", "ko": "초심 · 약속 카드", "en": "Promise · Panda"},
        title={"zh_TW": "PINK PROMISE · 初心閃耀", "ko": "PINK PROMISE · 변치 않는 초심", "en": "PINK PROMISE · Forever Glow"},
        stars="★★★★★",
        message={
            "zh_TW": "粉熊手燈在夜空中溫暖閃爍！回想當初讓你心動的目標，那份單純的熱情會繼續帶你走向更美的地方。",
            "ko": "밤하늘을 수놓은 핑크 응원봉처럼 초심이 반짝여요! 처음 설레었던 목표를 떠올리면 다시 힘차게 나아갈 수 있어요.",
            "en": "Pink lightsticks glow warmly in the night! Remember what first inspired you—that pure spark guides you onward.",
        },
        lucky={"zh_TW": "幸運小物：粉熊應援手燈", "ko": "행운 아이템: 판다 핑크 응원봉", "en": "Lucky charm: Pink Panda Lightstick"},
        accent="#ec4899",
    ),
    TarotCard(
        key="sword_cut_ties",
        badge={"zh_TW": "斷捨 · 清醒牌", "ko": "손절 · 팩폭 카드", "en": "Clean Cut · Truth"},
        title={"zh_TW": "CLEAR BLADE · 乾脆斷交", "ko": "CLEAR BLADE · 단호한 정리", "en": "CLEAR BLADE · Cut Ties"},
        stars="★★★☆☆",
        message={
            "zh_TW": "遇到一直消耗你、讓你不開心的朋友，就乾脆斷交吧！把寶貴真心留給懂得珍惜的人，恩地挺你。",
            "ko": "만날 때마다 기운 빠지고 불편하게 만드는 친구라면 미련 없이 정리해요! 소중한 마음은 아껴 주는 사람에게만 써요.",
            "en": "If a friend only drains your joy and makes you unhappy, cut ties cleanly! Save your heart for those who cherish you.",
        },
        lucky={"zh_TW": "幸運動作：清理社交與通訊錄", "ko": "행운 행동: 불편한 인간관계 정리하기", "en": "Lucky habit: Declutter draining contacts"},
        accent="#38bdf8",
    ),
    TarotCard(
        key="never_regret_star",
        badge={"zh_TW": "承諾 · 守護牌", "ko": "약속 · 진심 카드", "en": "Loyalty · Devotion"},
        title={"zh_TW": "TRUE STAR · 絕不後悔", "ko": "TRUE STAR · 후회 없는 선택", "en": "TRUE STAR · Never Regret"},
        stars="★★★★★",
        message={
            "zh_TW": "時間會證明一切！我們會努力成為絕對不讓你後悔喜歡、不讓你後悔支持的人，累了就放心靠過來吧。",
            "ko": "시간이 증명해 줄 거예요! 좋아하고 응원한 시간을 절대 후회하지 않게 만드는 사람이 될 테니 든든하게 믿어 주세요.",
            "en": "Time proves what is real! We'll always strive to be someone you never regret loving and supporting—lean on us.",
        },
        lucky={"zh_TW": "幸運色：恩地晴空湛藍", "ko": "행운 컬러: 은지 스카이 블루", "en": "Lucky color: Eunji Sky Blue"},
        accent="#60a5fa",
    ),
    TarotCard(
        key="mirror_fact_check",
        badge={"zh_TW": "直球 · 醒腦牌", "ko": "직구 · 현실조언 카드", "en": "Reality · Wake-Up"},
        title={"zh_TW": "FACT CHECK · 少嘆氣多動手", "ko": "FACT CHECK · 한숨보다 실행", "en": "FACT CHECK · Just Start"},
        stars="★★★☆☆",
        message={
            "zh_TW": "光坐著嘆氣事情可不會自己做完喔！先關掉分心的視窗專心做十分鐘，完成再喝冰美式犒賞自己。",
            "ko": "한숨만 쉰다고 일이 저절로 끝나진 않아요! 일단 딴짓 창부터 닫고 딱 10분만 집중한 뒤 시원한 아메리카노 마셔요.",
            "en": "Sighing at the screen won't finish the task! Close the distractions, focus for ten minutes, then grab iced coffee.",
        },
        lucky={"zh_TW": "幸運飲品：冰美式咖啡", "ko": "행운 음료: 아이스 아메리카노", "en": "Lucky drink: Iced Americano"},
        accent="#a78bfa",
    ),
    TarotCard(
        key="stop_overthinking",
        badge={"zh_TW": "理智 · 止損牌", "ko": "이성 · 생각멈춤 카드", "en": "Logic · Stop Worry"},
        title={"zh_TW": "MIND OFF · 停止內耗", "ko": "MIND OFF · 혼자 소설 금지", "en": "MIND OFF · Stop Scripting"},
        stars="★★★☆☆",
        message={
            "zh_TW": "別再腦補別人怎麼看你了，大家其實都很忙！與其內耗一整晚，不如去洗個熱水澡早點睡覺最實在。",
            "ko": "남들이 어떻게 볼지 혼자 소설 쓰지 말아요, 다들 자기 일로 바빠요! 고민할 시간에 따뜻한 샤워하고 푹 자는 게 최고예요.",
            "en": "Stop scripting imaginary worries about what others think—everyone is busy! Take a warm shower and sleep instead.",
        },
        lucky={"zh_TW": "幸運動作：關掉通知洗熱水澡", "ko": "행운 행동: 알림 끄고 따뜻한 샤워하기", "en": "Lucky habit: Mute alerts & warm shower"},
        accent="#818cf8",
    ),
    TarotCard(
        key="wallet_guardian",
        badge={"zh_TW": "理財 · 煞車牌", "ko": "지갑 · 방어 카드", "en": "Budget · Tough Love"},
        title={"zh_TW": "HOLD ON · 購物車冷靜", "ko": "HOLD ON · 장바구니 진정해", "en": "HOLD ON · Pause the Cart"},
        stars="★★★☆☆",
        message={
            "zh_TW": "看著購物車手癢了嗎？這張牌叫你先冷靜三天，省下衝動消費的錢拿去吃頓真正美味的大餐更划算！",
            "ko": "장바구니 보며 손이 근질근질하죠? 충동구매는 딱 사흘만 참아 보고, 그 돈으로 진짜 맛있는 음식을 먹는 게 훨씬 이득이에요!",
            "en": "Itching to impulse-buy? Wait three days before checking out—spending that on a truly great meal beats clutter!",
        },
        lucky={"zh_TW": "幸運動作：購物車冷靜三天", "ko": "행운 행동: 결제 전 사흘만 기다리기", "en": "Lucky habit: 3-day cool-down before buying"},
        accent="#facc15",
    ),
    TarotCard(
        key="fake_smile_shield",
        badge={"zh_TW": "界線 · 護盾牌", "ko": "경계 · 방패 카드", "en": "Boundary · Shield"},
        title={"zh_TW": "IRON SHIELD · 拒絕勉強", "ko": "IRON SHIELD · 억지 미소 금지", "en": "IRON SHIELD · Firm No"},
        stars="★★★★☆",
        message={
            "zh_TW": "不想笑的時候就別勉強自己陪笑！懂得堅定拒絕不合理的要求，你的善良才不會被當成理所當然。",
            "ko": "웃기 힘든 날엔 억지로 애써 웃지 않아도 돼요! 무리한 부탁은 단호하게 거절해야 내 다정함도 지킬 수 있어요.",
            "en": "Don't force a smile when you're tired! Saying a firm no to unfair demands protects your kindness from abuse.",
        },
        lucky={"zh_TW": "幸運語：溫柔而堅定地說不", "ko": "행운 키워드: 단호하고 깔끔한 거절", "en": "Lucky phrase: A polite and firm No"},
        accent="#38bdf8",
    ),
    TarotCard(
        key="past_delete_key",
        badge={"zh_TW": "翻篇 · 前進牌", "ko": "리셋 · 직진 카드", "en": "Reset · Move On"},
        title={"zh_TW": "DELETE KEY · 舊帳翻篇", "ko": "DELETE KEY · 지나간 일 삭제", "en": "DELETE KEY · Turn the Page"},
        stars="★★★★☆",
        message={
            "zh_TW": "已經翻篇的往事就別再拿出來虐自己啦！帥氣按下刪除鍵大步往前走，前面還有更棒的風景在等你。",
            "ko": "이미 지나간 일로 스스로를 괴롭히지 말아요! 과감하게 삭제 버튼을 누르고 앞으로 걸어가야 더 멋진 풍경을 만나죠.",
            "en": "Stop replaying old chapters just to hurt yourself! Hit delete on yesterday's regrets and walk toward better views.",
        },
        lucky={"zh_TW": "幸運小物：鍵盤 Delete 鍵", "ko": "행운 아이템: 깔끔하게 비운 휴지통", "en": "Lucky charm: A freshly cleared desktop"},
        accent="#c084fc",
    ),
    TarotCard(
        key="tough_workout_spark",
        badge={"zh_TW": "汗水 · 醒神牌", "ko": "운동 · 활력 카드", "en": "Sweat · Power"},
        title={"zh_TW": "POWER UP · 流汗最誠實", "ko": "POWER UP · 땀방울은 정직해", "en": "POWER UP · Honest Sweat"},
        stars="★★★★☆",
        message={
            "zh_TW": "覺得心情悶悶卡卡的？那是身體在抗議你坐太久啦！起來動一動流點汗，多巴胺可比煩惱誠實多了。",
            "ko": "기분이 괜히 처진다면 너무 오래 앉아 있었다는 신호예요! 자리에서 일어나 몸을 움직이면 머릿속이 훨씬 개운해질 거예요.",
            "en": "Feeling sluggish? Your body is protesting all that sitting! Stand up and stretch—endorphins never lie to you.",
        },
        lucky={"zh_TW": "幸運動作：深蹲或伸展五分鐘", "ko": "행운 행동: 가벼운 근력 운동 · 스트레칭", "en": "Lucky habit: 5 minutes of brisk stretching"},
        accent="#fb923c",
    ),
    TarotCard(
        key="late_night_scold",
        badge={"zh_TW": "熬夜 · 抓包牌", "ko": "야근 · 취침경고 카드", "en": "Curfew · Go Sleep"},
        title={"zh_TW": "BEDTIME NOW · 立刻去躺平", "ko": "BEDTIME NOW · 당장 이불 속으로", "en": "BEDTIME NOW · Lights Out"},
        stars="★★★☆☆",
        message={
            "zh_TW": "老實說，你是不是又打算熬夜滑手機？現在立刻去躺平！明天的皮膚跟精神會感謝今晚聽話的你。",
            "ko": "솔직히 말해요, 오늘 밤도 휴대폰 보며 늦게 잘 생각이었죠? 지금 당장 이불 속으로 들어가면 내일 아침 컨디션이 달라져요!",
            "en": "Be honest—were you planning to scroll past midnight again? Get under the covers now and thank yourself tomorrow!",
        },
        lucky={"zh_TW": "幸運動作：手機充好電放遠一點", "ko": "행운 행동: 머리맡에서 휴대폰 멀리 두기", "en": "Lucky habit: Put phone away from the pillow"},
        accent="#818cf8",
    ),
    TarotCard(
        key="busan_sea_courage",
        badge={"zh_TW": "海風 · 率真牌", "ko": "바닷바람 · 당당함 카드", "en": "Sea Breeze · Bold"},
        title={"zh_TW": "OCEAN WIND · 拍拍灰塵", "ko": "OCEAN WIND · 툭툭 털고 직진", "en": "OCEAN WIND · Brush It Off"},
        stars="★★★★★",
        message={
            "zh_TW": "像迎著爽朗海風一樣抬起頭！就算偶爾出點小錯天也不會塌下來，拍拍灰塵繼續唱自己的歌吧。",
            "ko": "시원한 바닷바람을 맞듯 어깨를 활짝 펴요! 작은 실수 하나로 세상이 무너지지 않으니 툭툭 털고 당당하게 나아가요.",
            "en": "Hold your head high like facing a fresh sea breeze! One small slip won't end the world—brush it off and keep going.",
        },
        lucky={"zh_TW": "幸運色：釜山海風湛藍", "ko": "행운 컬러: 시원한 오션 블루", "en": "Lucky color: Ocean Breeze Blue"},
        accent="#38bdf8",
    ),
    TarotCard(
        key="zero_excuse_start",
        badge={"zh_TW": "行動 · 破局牌", "ko": "실행 · 돌파 카드", "en": "Action · Breakthrough"},
        title={"zh_TW": "NO EXCUSE · 現在就開動", "ko": "NO EXCUSE · 지금 바로 시작", "en": "NO EXCUSE · Start Today"},
        stars="★★★★☆",
        message={
            "zh_TW": "別等什麼完美時機了，現在就是最好的時機！哪怕先完成百分之十，也比停在原地空想強上一百倍。",
            "ko": "완벽한 타이밍을 기다리지 말아요, 바로 지금이 시작할 때예요! 10퍼센트라도 일단 해내는 게 머릿속 고민보다 백배 나아요.",
            "en": "Stop waiting for the perfect moment—right now is enough! Finishing even ten percent beats a hundred hours of worry.",
        },
        lucky={"zh_TW": "幸運動作：五秒倒數後立刻動手", "ko": "행운 행동: 5초 세고 바로 시작하기", "en": "Lucky habit: Count 5-4-3-2-1 and begin"},
        accent="#f472b6",
    ),
    TarotCard(
        key="self_worth_diamond",
        badge={"zh_TW": "底氣 · 自愛牌", "ko": "자존감 · 보석 카드", "en": "Self-Worth · Gem"},
        title={"zh_TW": "DIAMOND SOUL · 無須討好", "ko": "DIAMOND SOUL · 흔들리지 않는 나", "en": "DIAMOND SOUL · Own Shine"},
        stars="★★★★★",
        message={
            "zh_TW": "你的價值不需要靠別人的打分來決定！懂你的人自然會看見你的閃耀，看不懂的人就讓他們路過吧。",
            "ko": "내 가치를 남들의 평가에 맡기지 말아요! 진가를 아는 사람은 자연히 알아볼 테니, 스쳐 갈 시선에 흔들리지 마세요.",
            "en": "Your worth isn't decided by someone else's scorecard! Those who matter see your shine—let the rest pass on by.",
        },
        lucky={"zh_TW": "幸運色：初瓏櫻粉與星鑽白", "ko": "행운 컬러: 다이아몬드 핑크", "en": "Lucky color: Diamond Rose Pink"},
        accent="#ec4899",
    ),
    TarotCard(
        key="warm_soup_shelter",
        badge={"zh_TW": "避風 · 暖湯牌", "ko": "위로 · 안식처 카드", "en": "Shelter · Warmth"},
        title={"zh_TW": "SAFE HARBOR · 卸下武裝", "ko": "SAFE HARBOR · 든든한 안식처", "en": "SAFE HARBOR · Warm Shelter"},
        stars="★★★★★",
        message={
            "zh_TW": "在外面逞強了一整天，回到這裡可以放心卸下武裝～不管今天過得如何，我們永遠是接住你的避風港。",
            "ko": "밖에서 하루 종일 애쓰느라 고생 많았어요~ 이곳에서만큼은 무거운 짐을 내려놓고 편안히 쉬어 가도 괜찮아요.",
            "en": "You've been strong all day out there—drop your armor here and rest easy knowing you always have a safe harbor.",
        },
        lucky={"zh_TW": "幸運美食：熱騰騰的韓式湯飯", "ko": "행운 메뉴: 속을 채우는 따뜻한 국밥", "en": "Lucky treat: Piping-hot comforting soup"},
        accent="#fbbf24",
    ),
    TarotCard(
        key="highnote_catharsis",
        badge={"zh_TW": "飆歌 · 暢快牌", "ko": "고음 · 스트레스해소 카드", "en": "High Note · Release"},
        title={"zh_TW": "HIGH NOTE · 三段高音清零", "ko": "HIGH NOTE · 시원한 고음 폭발", "en": "HIGH NOTE · Belt It Out"},
        stars="★★★★★",
        message={
            "zh_TW": "把心裡的悶氣化成三段高音通通喊出來吧！跟著喜歡的歌曲大聲哼唱，壞情緒一秒清零超痛快。",
            "ko": "답답한 마음은 시원한 3단 고음처럼 뻥 뚫어 버려요! 좋아하는 노래를 크게 따라 부르면 스트레스가 단번에 날아갈 거예요.",
            "en": "Belt out all your pent-up stress like a soaring high note! Sing along to your favorite track and reset your mood.",
        },
        lucky={"zh_TW": "幸運小物：播放清單最愛主打歌", "ko": "행운 아이템: 최애 플레이리스트 곡", "en": "Lucky charm: Your favorite power anthem"},
        accent="#60a5fa",
    ),
    TarotCard(
        key="honest_mirror_love",
        badge={"zh_TW": "真心 · 直球牌", "ko": "진심 · 직구 카드", "en": "Sincerity · Direct"},
        title={"zh_TW": "DIRECT HEART · 帥氣直球", "ko": "DIRECT HEART · 담백한 돌직구", "en": "DIRECT HEART · Speak True"},
        stars="★★★★☆",
        message={
            "zh_TW": "喜歡就大方說感謝，在乎就別拐彎抹角！坦率直接的真心話最能打動人，今天當個帥氣的直球選手吧。",
            "ko": "고마우면 고맙다고, 소중하면 소중하다고 솔직하게 표현해요! 돌려 말하기보다 담백한 진심 한마디가 마음을 움직여요.",
            "en": "If you're grateful or care deeply, say it straight! Honest, unvarnished warmth touches hearts better than riddles.",
        },
        lucky={"zh_TW": "幸運動作：直接說出感謝與稱讚", "ko": "행운 행동: 솔직한 칭찬 한마디 건네기", "en": "Lucky habit: Give a direct, honest compliment"},
        accent="#f9a8d4",
    ),
    TarotCard(
        key="eternal_encore",
        badge={"zh_TW": "安可 · 永恆牌", "ko": "앵콜 · 영원 카드", "en": "Encore · Forever"},
        title={"zh_TW": "ENCORE STAGE · 永遠同在", "ko": "ENCORE STAGE · 끝나지 않을 앵콜", "en": "ENCORE STAGE · Forever Us"},
        stars="★★★★★",
        message={
            "zh_TW": "舞台的燈光只要還有你在就不會熄滅！謝謝你一直陪在身邊，未來的每一場精彩安可我們都要一起走。",
            "ko": "당신이 함께해 주는 한 우리 무대의 불빛은 꺼지지 않아요! 언제나 곁을 지켜 줘서 고마워요, 앞으로의 앵콜도 함께해요.",
            "en": "As long as you're here, the stage lights will never fade! Thank you for staying by our side through every encore.",
        },
        lucky={"zh_TW": "幸運語：永遠的 Apink 與粉熊", "ko": "행운 키워드: 영원한 에이핑크 & 판다", "en": "Lucky phrase: Forever Apink & PANDA"},
        accent="#ec4899",
    ),
)

CLAUDE_SUPPLEMENT_CARDS: tuple[TarotCard, ...] = (
    TarotCard(
        key='plain_question',
        badge={'zh_TW': '清醒 · 直球牌', 'ko': '명쾌 · 직구 카드', 'en': 'Clarity · Straight Talk'},
        title={'zh_TW': 'PLAIN QUESTION · 直球一問', 'ko': 'PLAIN QUESTION · 돌직구 질문', 'en': 'PLAIN QUESTION · Ask It'},
        stars='★★★★☆',
        message={
            'zh_TW': '恩地把牌一翻：所以你到底想要什麼？今天別繞圈子，把真正的想法說清楚，對方反而更好幫你。',
            'ko': '은지가 카드를 뒤집으며 물어요. 그래서 진짜 원하는 게 뭐야? 오늘은 돌려 말하지 말고 솔직하게 말해 봐요.',
            'en': 'Eunji flips the card: so what do you actually want? Skip the hints today. Say it plainly so people can help you.',
        },
        lucky={'zh_TW': '幸運語：直接說就對了', 'ko': '행운 키워드: 그냥 말해 봐', 'en': 'Lucky phrase: Just say it'},
        accent='#22d3ee',
    ),
    TarotCard(
        key='snack_radar',
        badge={'zh_TW': '元氣 · 吃貨牌', 'ko': '기운 · 먹보 카드', 'en': 'Energy · Foodie'},
        title={'zh_TW': 'SNACK RADAR · 吃貨雷達', 'ko': 'SNACK RADAR · 먹보 레이더', 'en': 'SNACK RADAR · Fuel Up'},
        stars='★★★★☆',
        message={
            'zh_TW': '吃貨雷達嗶嗶作響！今天的好運藏在一頓好好吃的正餐裡，別再用零食隨便打發，吃飽才有力氣衝。',
            'ko': '먹보 레이더가 삐삐 울려요! 오늘의 행운은 제대로 챙겨 먹는 한 끼에 있어요. 과자로 때우지 말고 든든하게 먹어요.',
            'en': "The snack radar is beeping! Today's luck hides in a proper meal. Skip the snack-only lunch, eat well, then charge ahead.",
        },
        lucky={'zh_TW': '幸運時刻：準時吃午餐', 'ko': '행운의 시간: 제때 먹는 점심', 'en': 'Lucky time: Lunch on time'},
        accent='#fb7185',
    ),
    TarotCard(
        key='sunshine_volume',
        badge={'zh_TW': '人緣 · 陽光牌', 'ko': '인연 · 햇살 카드', 'en': 'Bonds · Sunshine'},
        title={'zh_TW': 'SUNSHINE UP · 陽光開到最大', 'ko': 'SUNSHINE UP · 햇살 볼륨 업', 'en': 'SUNSHINE UP · Turn It Up'},
        stars='★★★★★',
        message={
            'zh_TW': '水晶球亮得刺眼！今天你的熱情很有感染力，大方稱讚身邊的人一句，好心情會加倍回到你身上。',
            'ko': '수정구슬이 눈부시게 빛나요! 오늘은 당신의 열정이 전염되는 날. 주변 사람을 칭찬하면 좋은 기분이 두 배로 돌아와요.',
            'en': 'The crystal ball is blazing! Your warmth is contagious today. Give someone a real compliment; the good mood comes back.',
        },
        lucky={'zh_TW': '幸運色：南珠薰衣草紫', 'ko': '행운 컬러: 남주 라벤더', 'en': 'Lucky color: Namjoo Lavender'},
        accent='#c084fc',
    ),
    TarotCard(
        key='maknae_shortcut',
        badge={'zh_TW': '智慧 · 攻略牌', 'ko': '지혜 · 공략 카드', 'en': 'Wit · Shortcut'},
        title={'zh_TW': 'MAKNAE ROUTE · 忙內攻略', 'ko': 'MAKNAE ROUTE · 막내의 공략법', 'en': 'MAKNAE ROUTE · Smart Path'},
        stars='★★★★☆',
        message={
            'zh_TW': '忙內冷靜分析：這關不用硬闖，換條路走更快。今天適合找出最省力的方法，聰明偷懶也是一種實力。',
            'ko': '막내의 냉철한 분석: 이 판은 정면 돌파할 필요 없어요. 오늘은 가장 쉬운 길을 찾는 날, 똑똑한 요령도 실력이에요.',
            'en': "The maknae's calm analysis: no need to brute-force this level. Find the easiest path today. Working smart is a skill.",
        },
        lucky={'zh_TW': '幸運小物：耳機', 'ko': '행운 아이템: 헤드폰', 'en': 'Lucky charm: Headphones'},
        accent='#facc15',
    ),
    TarotCard(
        key='three_second_send',
        badge={'zh_TW': '溝通 · 冷靜牌', 'ko': '소통 · 진정 카드', 'en': 'Talk · Cool Head'},
        title={'zh_TW': 'THREE SECONDS · 送出前三秒', 'ko': 'THREE SECONDS · 전송 전 3초', 'en': 'THREE SECONDS · Before Send'},
        stars='★★★☆☆',
        message={
            'zh_TW': '牌上的手指停在送出鍵前！今天情緒上來時先深呼吸三秒，再讀一遍訊息，很多誤會就這樣省下來。',
            'ko': '카드 속 손가락이 전송 버튼 앞에서 멈췄어요! 욱할 때는 3초 숨 고르고 다시 읽어 봐요. 오해가 훨씬 줄어들어요.',
            'en': 'A finger hovers over Send! When emotions rise today, breathe for three seconds and reread. It saves misunderstandings.',
        },
        lucky={'zh_TW': '幸運語：先深呼吸', 'ko': '행운 키워드: 심호흡 먼저', 'en': 'Lucky phrase: Breathe first'},
        accent='#34d399',
    ),
    TarotCard(
        key='water_bottle_oracle',
        badge={'zh_TW': '健康 · 補水牌', 'ko': '건강 · 수분 카드', 'en': 'Health · Hydrate'},
        title={'zh_TW': 'WATER ORACLE · 補水神諭', 'ko': 'WATER ORACLE · 수분 신탁', 'en': 'WATER ORACLE · Drink Up'},
        stars='★★★★☆',
        message={
            'zh_TW': '水晶球裡出現一個滿滿的水壺。頭昏腦脹不一定是運氣差，可能只是太久沒喝水，起來倒一杯再回來。',
            'ko': '수정구슬에 물이 가득 찬 물병이 보여요. 머리가 멍한 건 운이 나빠서가 아니라 물을 안 마셔서일지도 몰라요.',
            'en': 'A full water bottle floats in the crystal ball. Feeling foggy may not be bad luck. You may just need a drink. Refill!',
        },
        lucky={'zh_TW': '幸運小物：大容量水壺', 'ko': '행운 아이템: 대용량 물병', 'en': 'Lucky charm: Big water bottle'},
        accent='#0ea5e9',
    ),
    TarotCard(
        key='rehearsal_room',
        badge={'zh_TW': '舞台 · 練習牌', 'ko': '무대 · 연습 카드', 'en': 'Stage · Practice'},
        title={'zh_TW': 'REHEARSAL · 練習室的燈', 'ko': 'REHEARSAL · 연습실의 불빛', 'en': 'REHEARSAL · Studio Lights'},
        stars='★★★★★',
        message={
            'zh_TW': '練習室的燈還亮著！今天多練一次的那一遍最有價值，不必追求完美，穩穩重複就會慢慢變成實力。',
            'ko': '연습실 불이 아직 켜져 있어요! 오늘 한 번 더 해 보는 그 연습이 가장 값져요. 완벽보다 꾸준함이 실력이 돼요.',
            'en': 'The practice room lights are still on! One extra run-through today matters most. Skip perfection; steady wins.',
        },
        lucky={'zh_TW': '幸運小物：運動毛巾', 'ko': '행운 아이템: 스포츠 타월', 'en': 'Lucky charm: Sports towel'},
        accent='#e879f9',
    ),
    TarotCard(
        key='leader_checklist',
        badge={'zh_TW': '計畫 · 隊長牌', 'ko': '계획 · 리더 카드', 'en': 'Plan · Leader'},
        title={'zh_TW': 'LEADER LIST · 隊長清單', 'ko': 'LEADER LIST · 리더의 체크리스트', 'en': 'LEADER LIST · Top Three'},
        stars='★★★★☆',
        message={
            'zh_TW': '隊長叉著腰看你的行程：太滿了！今天只挑三件最重要的事寫下來，其他明天再說，不准全部硬扛。',
            'ko': '리더가 허리에 손을 얹고 일정을 봐요. 너무 많잖아! 오늘은 제일 중요한 세 가지만 적고 나머지는 내일 해요.',
            'en': 'The leader checks your schedule, hands on hips: way too much! Pick the three most important things. The rest can wait.',
        },
        lucky={'zh_TW': '幸運小物：便利貼', 'ko': '행운 아이템: 포스트잇', 'en': 'Lucky charm: Sticky notes'},
        accent='#f9a8d4',
    ),
    TarotCard(
        key='small_win_stamp',
        badge={'zh_TW': '成就 · 集點牌', 'ko': '성취 · 도장 카드', 'en': 'Wins · Stamp Card'},
        title={'zh_TW': 'SMALL WINS · 小勝利集點', 'ko': 'SMALL WINS · 작은 승리 도장', 'en': 'SMALL WINS · Collect Them'},
        stars='★★★★☆',
        message={
            'zh_TW': '牌上蓋滿了可愛的小印章！今天做完的每件小事都算數，洗好碗、回完信，都替自己蓋一個章吧。',
            'ko': '카드에 귀여운 도장이 가득해요! 설거지 끝, 메일 답장 끝. 오늘 해낸 작은 일 하나하나에 도장을 찍어 줘요.',
            'en': 'The card is covered in cute stamps! Every small thing you finish today counts: dishes done, email sent. Stamp each one.',
        },
        lucky={'zh_TW': '幸運小物：獎勵貼紙', 'ko': '행운 아이템: 칭찬 스티커', 'en': 'Lucky charm: Reward stickers'},
        accent='#a3e635',
    ),
    TarotCard(
        key='comfy_outfit',
        badge={'zh_TW': '日常 · 自在牌', 'ko': '일상 · 편안함 카드', 'en': 'Daily · Comfort'},
        title={'zh_TW': 'COMFY FIT · 舒服最好看', 'ko': 'COMFY FIT · 편한 게 최고', 'en': 'COMFY FIT · Easy Style'},
        stars='★★★☆☆',
        message={
            'zh_TW': '牌面是一件軟綿綿的大帽T。今天不用為了別人的眼光硬撐，穿得舒服、心情放鬆，自然就會發光。',
            'ko': '카드에 포근한 후드티가 그려져 있어요. 오늘은 남의 시선보다 내가 편한 옷을 골라요. 편안할 때 더 빛나요.',
            'en': "The card shows a big, soft hoodie. No need to dress for anyone else today. Wear what's comfy; you shine more at ease.",
        },
        lucky={'zh_TW': '幸運小物：大帽T', 'ko': '행운 아이템: 오버핏 후드티', 'en': 'Lucky charm: Oversized hoodie'},
        accent='#94a3b8',
    ),
    TarotCard(
        key='borrowed_courage',
        badge={'zh_TW': '勇氣 · 求助牌', 'ko': '용기 · 도움 카드', 'en': 'Courage · Ask'},
        title={'zh_TW': 'BORROWED COURAGE · 借你勇氣', 'ko': 'BORROWED COURAGE · 용기 빌려줄게', 'en': 'BORROWED COURAGE · Lean In'},
        stars='★★★★★',
        message={
            'zh_TW': '五隻熊貓排成一排舉手！一個人卡住的事不用硬撐到底，今天開口請人幫忙，答案會比想像中更快出現。',
            'ko': '다섯 판다가 나란히 손을 들었어요! 혼자 막힌 일은 끝까지 버티지 말고 도움을 청해 봐요. 답이 생각보다 빨리 와요.',
            'en': "Five pandas raise their hands at once! Don't push through a stuck task alone. Ask for help; the answer comes sooner.",
        },
        lucky={'zh_TW': '幸運語：可以幫我嗎', 'ko': '행운 키워드: 도와줄래?', 'en': 'Lucky phrase: Can you help me?'},
        accent='#fbbf24',
    ),
    TarotCard(
        key='early_bird_seat',
        badge={'zh_TW': '時間 · 從容牌', 'ko': '시간 · 여유 카드', 'en': 'Time · Unhurried'},
        title={'zh_TW': 'EARLY BIRD · 早到十分鐘', 'ko': 'EARLY BIRD · 10분 일찍', 'en': 'EARLY BIRD · Ten Minutes Early'},
        stars='★★★☆☆',
        message={
            'zh_TW': '時鐘指針在牌上慢慢走。今天出門提早十分鐘，不用一路狂奔，從容到場的你，運氣也會穩穩跟上。',
            'ko': '카드 속 시곗바늘이 천천히 움직여요. 오늘은 10분 일찍 나가요. 뛰지 않고 여유 있게 도착하면 운도 따라와요.',
            'en': 'The clock hands move slowly on the card. Leave ten minutes early today. Arrive calm, not rushed, and luck stays steady.',
        },
        lucky={'zh_TW': '幸運時刻：提早十分鐘', 'ko': '행운의 시간: 10분 일찍', 'en': 'Lucky time: Ten minutes early'},
        accent='#67e8f9',
    ),
    TarotCard(
        key='window_seat_reset',
        badge={'zh_TW': '轉念 · 換位牌', 'ko': '전환 · 관점 카드', 'en': 'Mindset · New Angle'},
        title={'zh_TW': 'WINDOW SEAT · 換個位置想', 'ko': 'WINDOW SEAT · 자리 바꿔 보기', 'en': 'WINDOW SEAT · New View'},
        stars='★★★★☆',
        message={
            'zh_TW': '牌上的熊貓搬到了窗邊座位。想不通的事就先離開桌子走走，換個位置看，答案可能一直就在旁邊。',
            'ko': '카드 속 판다가 창가 자리로 옮겼어요. 풀리지 않는 일은 잠깐 자리를 떠나 봐요. 답은 바로 옆에 있었을지도 몰라요.',
            'en': "The panda on the card moved to the window seat. If something won't click, step away. The answer may be right beside you.",
        },
        lucky={'zh_TW': '幸運地點：窗邊座位', 'ko': '행운의 장소: 창가 자리', 'en': 'Lucky spot: By the window'},
        accent='#7dd3fc',
    ),
    TarotCard(
        key='desk_lost_found',
        badge={'zh_TW': '整理 · 尋物牌', 'ko': '정리 · 분실물 카드', 'en': 'Tidy · Lost & Found'},
        title={'zh_TW': 'LOST & FOUND · 失物招領', 'ko': 'LOST & FOUND · 분실물 센터', 'en': 'LOST & FOUND · Tidy Up'},
        stars='★★★☆☆',
        message={
            'zh_TW': '水晶球照出你桌上的小山！一直找不到的東西就在那堆裡，今天花十分鐘收一收，心裡也會跟著清爽。',
            'ko': '수정구슬에 책상 위 작은 산이 비쳐요! 계속 못 찾던 물건이 저기 있어요. 오늘 10분만 정리하면 마음도 개운해져요.',
            'en': 'The crystal ball shows the little mountain on your desk! What you keep losing is in there. Tidy for ten minutes today.',
        },
        lucky={'zh_TW': '幸運小物：收納盒', 'ko': '행운 아이템: 정리함', 'en': 'Lucky charm: Storage box'},
        accent='#d6d3d1',
    ),
    TarotCard(
        key='stretch_break',
        badge={'zh_TW': '健康 · 伸展牌', 'ko': '건강 · 스트레칭 카드', 'en': 'Health · Stretch'},
        title={'zh_TW': 'STRETCH BREAK · 伸個懶腰', 'ko': 'STRETCH BREAK · 기지개 타임', 'en': 'STRETCH BREAK · Reach Up'},
        stars='★★★★☆',
        message={
            'zh_TW': '牌上的熊貓伸了個大大的懶腰！坐太久肩膀都僵了，今天每隔一小時站起來動一動，好運才流得進來。',
            'ko': '카드 속 판다가 크게 기지개를 켜요! 너무 오래 앉아 있었어요. 한 시간마다 일어나서 몸을 풀어야 운도 들어와요.',
            'en': "The panda on the card takes a huge stretch! You've sat too long. Stand up once an hour today and let luck flow in.",
        },
        lucky={'zh_TW': '幸運動作：轉轉肩膀', 'ko': '행운 동작: 어깨 돌리기', 'en': 'Lucky move: Shoulder rolls'},
        accent='#4ade80',
    ),
    TarotCard(
        key='green_thumb',
        badge={'zh_TW': '耐心 · 栽培牌', 'ko': '인내 · 가꾸기 카드', 'en': 'Patience · Grow'},
        title={'zh_TW': 'GREEN THUMB · 幫植物澆水', 'ko': 'GREEN THUMB · 화분에 물 주기', 'en': 'GREEN THUMB · Water It'},
        stars='★★★★☆',
        message={
            'zh_TW': '水晶球裡冒出一片小嫩芽。今天適合照顧需要時間的事，每天澆一點水，不用急著看見結果，它正在長。',
            'ko': '수정구슬 속에 작은 새싹이 돋았어요. 오늘은 시간이 필요한 일을 돌보기 좋은 날. 조급해하지 마요, 자라는 중이에요.',
            'en': 'A tiny sprout appears in the crystal ball. Tend to something that needs time today. Water it a little. It is growing.',
        },
        lucky={'zh_TW': '幸運小物：小盆栽', 'ko': '행운 아이템: 작은 화분', 'en': 'Lucky charm: Small potted plant'},
        accent='#86efac',
    ),
    TarotCard(
        key='bookmark_pages',
        badge={'zh_TW': '充電 · 閱讀牌', 'ko': '충전 · 독서 카드', 'en': 'Recharge · Read'},
        title={'zh_TW': 'BOOKMARK · 書籤停在這裡', 'ko': 'BOOKMARK · 책갈피는 여기', 'en': 'BOOKMARK · Next Chapter'},
        stars='★★★☆☆',
        message={
            'zh_TW': '書籤還夾在上次那一頁！今天睡前讀個十頁就好，不用一次看完，讓腦袋從螢幕換到紙上休息一下。',
            'ko': '책갈피가 지난번 그 페이지에 꽂혀 있어요! 오늘은 자기 전에 열 쪽만 읽어요. 화면 대신 종이로 머리를 쉬게 해요.',
            'en': 'The bookmark is still where you left it! Read just ten pages before bed. Let your mind rest on paper, not a screen.',
        },
        lucky={'zh_TW': '幸運小物：書籤', 'ko': '행운 아이템: 책갈피', 'en': 'Lucky charm: Bookmark'},
        accent='#fcd34d',
    ),
    TarotCard(
        key='look_up_sky',
        badge={'zh_TW': '療癒 · 抬頭牌', 'ko': '힐링 · 하늘 카드', 'en': 'Healing · Look Up'},
        title={'zh_TW': 'LOOK UP · 抬頭看天空', 'ko': 'LOOK UP · 하늘 올려다보기', 'en': 'LOOK UP · Sky Break'},
        stars='★★★★★',
        message={
            'zh_TW': '恩地指著水晶球裡的晚霞說：抬頭看一下吧。今天別一直低頭趕路，替天空拍一張照，心情會鬆開來。',
            'ko': '은지가 수정구슬 속 노을을 가리켜요. 고개 한번 들어 봐. 오늘은 바쁘게 걷지만 말고 하늘 사진 한 장 찍어 봐요.',
            'en': 'Eunji points at the sunset in the crystal ball: look up for a second. Stop rushing head-down; snap a photo of the sky.',
        },
        lucky={'zh_TW': '幸運時刻：傍晚的天空', 'ko': '행운의 시간: 저녁 노을', 'en': 'Lucky time: Evening sky'},
        accent='#fdba74',
    ),
    TarotCard(
        key='backup_save',
        badge={'zh_TW': '防雷 · 備份牌', 'ko': '지뢰 회피 · 백업 카드', 'en': 'Safety · Backup'},
        title={'zh_TW': 'BACKUP · 記得存檔', 'ko': 'BACKUP · 백업 잊지 마', 'en': 'BACKUP · Save It'},
        stars='★★★☆☆',
        message={
            'zh_TW': '水晶球突然閃了一下藍光！今天做到一半的檔案記得存檔，重要的照片也備份一份，安心比後悔划算。',
            'ko': '수정구슬이 갑자기 파랗게 깜빡였어요! 작업 중인 파일은 꼭 저장하고, 소중한 사진도 백업해 둬요. 안심이 최고예요.',
            'en': 'The crystal ball flickers blue! Save that half-done file and back up the photos you love. Peace of mind beats regret.',
        },
        lucky={'zh_TW': '幸運小物：隨身碟', 'ko': '행운 아이템: USB 메모리', 'en': 'Lucky charm: USB drive'},
        accent='#93c5fd',
    ),
    TarotCard(
        key='one_new_word',
        badge={'zh_TW': '學習 · 單字牌', 'ko': '배움 · 단어 카드', 'en': 'Learning · New Word'},
        title={'zh_TW': 'ONE NEW WORD · 學一個新單字', 'ko': 'ONE NEW WORD · 새 단어 하나', 'en': 'ONE NEW WORD · Learn One'},
        stars='★★★★☆',
        message={
            'zh_TW': '牌面寫著一個你還不認識的字！今天只要學會一個新單字就好，下次聽到喜歡的歌，就會多聽懂一句。',
            'ko': '카드에 아직 모르는 단어가 적혀 있어요! 오늘은 새 단어 하나만 외워요. 좋아하는 노래에서 한 줄 더 들릴 거예요.',
            'en': "The card shows a word you don't know yet! Learn just one new word today. Your favorite song will make a bit more sense.",
        },
        lucky={'zh_TW': '幸運小物：單字小卡', 'ko': '행운 아이템: 단어 카드', 'en': 'Lucky charm: Flash cards'},
        accent='#c4b5fd',
    ),
)

GUARDIAN_TAGS_FINAL: dict[str, dict[str, str]] = {
    "chorong": {"zh_TW": "操心隊長", "ko": "걱정 대장", "en": "Caring Leader"},
    "bomi": {"zh_TW": "暖心安慰", "ko": "다정한 위로", "en": "Gentle Comfort"},
    "eunji": {"zh_TW": "直球暖心", "ko": "돌직구 다정", "en": "Straight & Warm"},
    "namjoo": {"zh_TW": "安靜陪伴", "ko": "조용한 동행", "en": "Quiet Company"},
    "hayoung": {"zh_TW": "冷靜攻略", "ko": "냉철 공략", "en": "Cool Strategist"},
}

GUARDIAN_LINES_FINAL: dict[str, tuple[dict[str, str], ...]] = {
    "chorong": (
        {
            "zh_TW": "今天又在煩什麼？說吧，我陪你一起想辦法。",
            "ko": "오늘은 뭐가 고민이야? 말해 봐, 같이 방법 찾자.",
            "en": "What's weighing on you today? Tell me. We'll figure it out together.",
        },
        {
            "zh_TW": "聽你說完我都快哭了…沒關係，我們慢慢來。",
            "ko": "네 얘기 듣다가 나도 울 뻔했어… 괜찮아, 천천히 하자.",
            "en": "Hearing that almost made me cry too… It's okay. We'll take it slow.",
        },
        {
            "zh_TW": "熬夜對身體不好，熱水我放桌上了，喝完早點睡。",
            "ko": "밤새면 몸 상해. 따뜻한 물 책상에 뒀으니까 마시고 일찍 자.",
            "en": "Late nights are hard on you. Warm water's on your desk. Drink it and sleep early.",
        },
        {
            "zh_TW": "有事一定要跟我說，不要一個人撐著。",
            "ko": "무슨 일 있으면 꼭 말해. 혼자 버티지 말고.",
            "en": "If something's wrong, tell me. Don't carry it alone.",
        },
    ),
    "bomi": (
        {
            "zh_TW": "沒關係、沒關係，你已經很努力了。來，先抱一下。",
            "ko": "괜찮아, 괜찮아. 넌 이미 충분히 애썼어. 이리 와, 안아 줄게.",
            "en": "It's okay, it's okay. You've already worked so hard. Come here, hug first.",
        },
        {
            "zh_TW": "今天辛苦了！不管發生什麼，我都站在你這邊。",
            "ko": "오늘 고생 많았어! 무슨 일이 있어도 난 네 편이야.",
            "en": "You've had a long day! Whatever happened, I'm on your side.",
        },
        {
            "zh_TW": "你很好，真的很好。我說幾次都可以，直到你相信為止。",
            "ko": "넌 괜찮은 사람이야, 진짜로. 네가 믿을 때까지 몇 번이고 말해 줄게.",
            "en": "You're doing fine, truly. I'll keep saying it until you believe me.",
        },
        {
            "zh_TW": "肚子餓的時候不准做重要決定！先吃飽，再來煩惱。",
            "ko": "배고플 때 중요한 결정 금지! 일단 먹고 고민하자.",
            "en": "No big decisions on an empty stomach! Eat first, worry later.",
        },
    ),
    "eunji": (
        {
            "zh_TW": "這件事你自己也知道答案吧？知道就去做，我挺你。",
            "ko": "답은 너도 알잖아? 알면 해. 내가 편들어 줄게.",
            "en": "You already know the answer, right? Then do it. I've got your back.",
        },
        {
            "zh_TW": "哭完了嗎？好，那我們來想下一步怎麼辦。",
            "ko": "다 울었어? 좋아, 그럼 다음에 뭐 할지 같이 생각하자.",
            "en": "Done crying? Good. Now let's figure out the next step together.",
        },
        {
            "zh_TW": "卡在哪裡？說給我聽，我們一步一步拆開來。",
            "ko": "어디서 막혔어? 말해 봐, 하나씩 같이 풀어 보자.",
            "en": "Where are you stuck? Tell me, and we'll take it apart one step at a time.",
        },
        {
            "zh_TW": "你不是不行，是太累了。今天先休息，明天再說。",
            "ko": "못하는 게 아니라 지친 거야. 오늘은 쉬고 내일 하자.",
            "en": "You're not failing, you're tired. Rest today. We'll deal with it tomorrow.",
        },
    ),
    "namjoo": (
        {
            "zh_TW": "不想說也沒關係，我就坐在旁邊陪你。",
            "ko": "말 안 해도 괜찮아. 그냥 옆에 앉아 있을게.",
            "en": "You don't have to talk. I'll just sit here next to you.",
        },
        {
            "zh_TW": "想說的時候再說，我會一直聽到最後。",
            "ko": "말하고 싶을 때 말해. 끝까지 들을게.",
            "en": "Tell me when you're ready. I'll listen all the way to the end.",
        },
        {
            "zh_TW": "一起看一下窗外吧，等心情慢慢靜下來。",
            "ko": "같이 창밖 좀 보자. 마음이 가라앉을 때까지.",
            "en": "Let's look out the window together until things settle a little.",
        },
        {
            "zh_TW": "今天不用急著解決，有人陪著就好。",
            "ko": "오늘은 서두르지 않아도 돼. 곁에 누가 있으면 돼.",
            "en": "No need to fix it today. It's enough to have someone beside you.",
        },
    ),
    "hayoung": (
        {
            "zh_TW": "攻略提示：先做最簡單的那件，經驗值會自己漲。",
            "ko": "공략 팁: 제일 쉬운 것부터 해. 경험치는 알아서 올라.",
            "en": "Strategy tip: clear the easiest quest first. Your XP levels up on its own.",
        },
        {
            "zh_TW": "姐姐們都在忙，所以今天由我來守護你。很可靠吧？",
            "ko": "언니들이 다 바쁘니까 오늘은 내가 지켜 줄게. 든든하지?",
            "en": "The unnies are busy, so I'm on guard duty today. Reliable, right?",
        },
        {
            "zh_TW": "存檔很重要。累了就先存檔休息，不會從頭開始的。",
            "ko": "세이브는 중요해. 지치면 저장하고 쉬어. 처음부터 안 해.",
            "en": "Saving matters. Tired? Save and rest. You won't restart from zero.",
        },
        {
            "zh_TW": "冷靜分析：你擔心的事，大部分沒有想像中那麼糟。",
            "ko": "냉정하게 분석하면, 걱정하는 일 대부분은 생각만큼 나쁘지 않아.",
            "en": "Calm analysis: most of what you're worried about isn't as bad as it looks.",
        },
    ),
}

EGG_CHANCE_DAY = 0.05
EGG_CHANCE_NIGHT = 0.15
EGG_NIGHT_HOURS = frozenset({23, 0, 1, 2, 3, 4})
# (b) Secret interaction: click the crystal emblem this many times within the window.
EGG_EMBLEM_CLICKS = 3
EGG_EMBLEM_WINDOW_MS = 1500

CHORONG_EGG_TAG = {"zh_TW": "隱藏彩蛋 · 毒舌瓏瓏", "ko": "히든 · 독설 롱롱", "en": "Hidden · Tough-Love Rong"}

# Egg Chorong: v3.2 tough-love contrast lines.
CHORONG_EGG_LINES: tuple[dict[str, str], ...] = (
    {"zh_TW": "又熬夜？真是的…算了，熱水幫你倒好了，喝完再去忙。", "ko": "또 밤샜어? 정말… 됐어, 따뜻한 물 떠 놨으니까 마시고 해.", "en": "Up late again? Honestly… fine. I poured you warm water. Drink it, then get back to work."},
    {"zh_TW": "你又在煩這個？我想了三個辦法，你挑一個。", "ko": "또 그거 고민해? 방법 세 개 생각해 놨어, 하나 골라.", "en": "Worrying about that again? I came up with three fixes. Pick one."},
    {"zh_TW": "嘴上說你很煩，結果聽你講完我先哭了…好啦，一起哭完再想辦法。", "ko": "귀찮다더니 네 얘기 듣다가 내가 먼저 울었네… 됐어, 같이 울고 방법 찾자.", "en": "Said you were a handful, then cried first hearing you out… Okay. We cry together, then we fix it."},
    {"zh_TW": "嫌你很煩是真的，不放心你也是真的。好好吃飯。", "ko": "귀찮은 것도 진짜고, 걱정되는 것도 진짜야. 밥 잘 챙겨 먹어.", "en": "Yes, you're a handful. Yes, I worry about you. Both true. Eat properly."},
)

# One-time line shown when the egg is unlocked.
CHORONG_EGG_UNLOCK = {"zh_TW": "被你找到了？好啦，這是彩蛋。不准跟別人說。", "ko": "들켰네? 그래, 이스터에그야. 다른 사람한텐 비밀이야.", "en": "You found me? Fine, it's an easter egg. Don't tell anyone."}

# Hidden card: never part of the regular deck, never returned by pick_tarot_card().
CHORONG_EGG_CARD = TarotCard(
    key="tough_love_rong",
    badge={"zh_TW": "隱藏 · 彩蛋牌", "ko": "히든 · 이스터에그 카드", "en": "Hidden · Easter Egg"},
    title={"zh_TW": "TOUGH LOVE · 毒舌瓏瓏", "ko": "TOUGH LOVE · 독설 롱롱", "en": "TOUGH LOVE · Rong's Verdict"},
    stars="★★★★★",
    message={
        "zh_TW": "又來找我算？命運不是扭蛋，這張給我收下。今天照著做，做不到我再來念你…其實是擔心你啦。",
        "ko": "또 점 보러 왔어? 운명은 뽑기가 아니야. 이 카드 받아 두고 오늘은 이대로 해. 못 하면 또 잔소리할 거야.",
        "en": "Back for another reading? Fate isn't a gacha. Keep this card and follow it today, or I'll come back to nag you.",
    },
    lucky={"zh_TW": "幸運物：念完你才倒好的熱水", "ko": "행운 아이템: 잔소리 끝에 건넨 따뜻한 물", "en": "Lucky charm: Warm water after the nagging"},
    accent="#fb7185",
)
EGG_GOLD = "#fbbf24"  # gold rim / ribbon around the reveal panel while the egg card is shown

TAROT_CARDS = BASE_TAROT_CARDS + ARGON_FORTUNE_CARDS + CLAUDE_SUPPLEMENT_CARDS

# Cards whose copy or lucky color explicitly features a member must pair with that
# same member as guardian so the card text and guardian quote always align.
CARD_GUARDIANS: dict[str, str] = {
    "noble_friend": "chorong",
    "self_worth_diamond": "chorong",
    "leader_checklist": "chorong",
    "tough_love_rong": "chorong",
    "brave_compass": "bomi",
    "two_hearts": "eunji",
    "the_star": "eunji",
    "moonlight_calm": "eunji",
    "crystal_focus": "eunji",
    "gentle_umbrella": "eunji",
    "sword_cut_ties": "eunji",
    "never_regret_star": "eunji",
    "plain_question": "eunji",
    "look_up_sky": "eunji",
    "busan_sea_courage": "eunji",
    "highnote_catharsis": "eunji",
    "violet_crown": "namjoo",
    "sunshine_volume": "namjoo",
    "the_sun": "hayoung",
    "golden_pocket": "hayoung",
    "lucky_gamepad": "hayoung",
    "maknae_shortcut": "hayoung",
}
