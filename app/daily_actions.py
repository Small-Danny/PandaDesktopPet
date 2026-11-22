"""daily_actions.py — What each member does on her own: signature moves, festival extras.

The signature pool runs every day; a festival only adds its own actions on top of it.
"""
from __future__ import annotations

import datetime as _dt
import random
from dataclasses import dataclass
from typing import Optional, Sequence

LIGHTSTICK = "special_cheer_lightstick"
SIGNATURE_POOL: dict[str, tuple[str, ...]] = {
    "chorong": ("special_cartwheel", "special_hapkido_kick", "special_blow_kiss", LIGHTSTICK),
    "bomi": ("special_gorilla", "special_taekwondo", LIGHTSTICK, "interaction_eat"),
    "eunji": ("special_sing_highnote", "special_guitar", "special_boxing", "standby_stretch"),
    # User directive (2026-11-10): Special moves must strictly be multi-frame animations (動圖) only.
    # Single-frame stills (Bird stage, tteokbokki, maltese) are excluded from the signature/special pool.
    "namjoo": (LIGHTSTICK, "special_boxing", "scene_flamingo"),
    "hayoung": ("special_soccer_kick", "special_gaming", LIGHTSTICK),
}
SIGNATURE_INTERVAL_S = (120.0, 240.0)
NATURAL_INTERVAL_S = (45.0, 110.0)
NATURAL_ANIMATION_SHARE = 0.45
RARE_SHARE = 0.06

FESTIVAL_COOLDOWN_S = 40.0

# Gregorian dates of the lunar calendar; a festival past this table simply does not run.
LUNAR_NEW_YEAR = {
    2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3), 2031: (1, 23),
    2032: (2, 11), 2033: (1, 31), 2034: (2, 19), 2035: (2, 8), 2036: (1, 28),
}
MID_AUTUMN = {
    2026: (9, 25), 2027: (9, 15), 2028: (10, 3), 2029: (9, 22), 2030: (9, 12), 2031: (10, 1),
    2032: (9, 19), 2033: (9, 8), 2034: (9, 27), 2035: (9, 16), 2036: (10, 4),
}

# From the Module D review (work/daily_animation_audit_20261108): chosen by opening each image.
# Keys are registry names, and many older file names do not describe their picture.
# reference/最後動圖 (2026-11-10): bored, yawn, surprise and side hug are everyday moods.
EVERYDAY_MOODS = ("daily_bored", "daily_yawn", "daily_surprise", "daily_hug_side")
NATURAL_ANIMATIONS: dict[str, tuple[str, ...]] = {
    "chorong": ('daily_greeting', 'daily_cat_cuddle', *EVERYDAY_MOODS),  # hot tea is 384 px: too small on the desktop, standby only
    "bomi": ('daily_greeting', *EVERYDAY_MOODS),
    "eunji": ('daily_greeting', 'daily_yawn_stretch', *EVERYDAY_MOODS),
    "namjoo": ('daily_greeting', *EVERYDAY_MOODS),
    "hayoung": ('daily_greeting', *EVERYDAY_MOODS),
}
NATURAL_POSES: dict[str, tuple[str, ...]] = {
    # walk_v3_* is drawn with salmon/coral patches (source 需求/初瓏4.jpg), not Chorong's pink.
    "chorong": ("walk_v2_04", "walk_v2_03", "situational_v6_3/chorong_graceful_bow", "actions_v7/chorong_cheer_wave", "situational_v6_3/chorong_blanket_cozy", "situational_v6_2/chorong_headband_cozy", "lifestyle_v6_1/chorong_couch_cuddle",),
    "bomi": ("walk_v2_03", "walk_v4_04", "walk_v2_01", "lifestyle_v6_2/bomi_double_heart_aegyo", "actions_v7/bomi_jump_cheer", "actions_v7/bomi_star_smile", "situational_v6_2/bomi_sunny_strut",),
    "eunji": ("walk_v2_02", "walk_v2_03", "walk_v2_01", "situational_v6_2/eunji_acoustic_guitar", "situational_v6_2/eunji_vocal_rest", "situational_v6_3/eunji_warm_hoodie_rest",),
    "namjoo": ("walk_v2_03", "walk_v2_04", "walk_v3_04", "actions_v7/namjoo_heart_walk", "situational_v6_2/namjoo_huge_heart_hug",),
    "hayoung": ("walk_v2_03", "walk_v2_04", "walk_v3_04", "actions_v7/hayoung_casual_relax", "situational_v6_2/hayoung_potato_gameboy", "situational_v6_3/hayoung_headphone_vibing",),
}
RARE_POSES: dict[str, tuple[str, ...]] = {
    "chorong": ("actions_v7/chorong_heart_tilt",),
    "bomi": ("situational_v6_2/bomi_chef_stew_pot",),
    "eunji": ("situational_v6_2/eunji_green_smoothie",),
    "namjoo": ("actions_v7/namjoo_mukbang_ready",),
    "hayoung": ("situational_v6_2/hayoung_manga_reader",),
}
# Reactions try their names in order: the drawn animation first, the older still as a fallback.
TAP_REACTION: dict[str, tuple[str, ...]] = {
    "chorong": ("daily_tap", "walk_v2_04",),
    "bomi": ("daily_tap", "walk_v4_04",),
    "eunji": ("daily_tap", "walk_v2_04",),
    "namjoo": ("daily_tap", "walk_v3_04",),
    "hayoung": ("daily_tap", "walk_v3_04",),
}
PAT_REACTION: dict[str, tuple[str, ...]] = {m: ("daily_pat", *TAP_REACTION[m]) for m in TAP_REACTION}
SULK_REACTION: dict[str, tuple[str, ...]] = {m: ("daily_sulk",) for m in TAP_REACTION}
FULL_REACTION: dict[str, tuple[str, ...]] = {m: ("daily_full",) for m in TAP_REACTION}

# Dedicated situational food/drink sprites mapped to specific foods.
# STRICT WHITELIST ONLY: Every sprite below has been 100% visually audited frame-by-frame.
# Sprites whose filenames mislead (e.g. bomi_ramen_slurp has sunglasses, no noodles;
# chorong_sp_tea_sip has a wire, no tea) are strictly excluded and cleanly trigger cheer.
# (member, food_id) -> tuple of action names
FOOD_MEMBER_ANIMATIONS: dict[tuple[str, str], tuple[str, ...]] = {
    # User-defined equivalence (2026-11-12): mango smoothie = mango ice.
    # Strawberry boba still must not borrow the plain brown-pearl cup.
    # Missing exact feed_{id} art uses the food-neutral cheer, never another dish.
    # ── Namjoo (南珠) ──────────────────────────────────────────────────────────
    # 芒果冰沙與芒果冰依使用者定義共用素材；草莓珍奶不借用普通黑珍珠杯。
    ("namjoo", "tw_mango_smoothie"): ("actions_v7/namjoo_mukbang_ready",),
    ("namjoo", "tw_mango_shaved_ice"): ("actions_v7/namjoo_mukbang_ready",),
    ("namjoo", "tw_brown_sugar_boba"): ("situational_v6_2/namjoo_gourmet_taster",),
    # situational_v3 malatang/tteokbokki stills are blocked (source 南珠3.jpg puts Chorong's
    # collar on Namjoo); her own stage2 feed_malatang / feed_tteokbokki always play instead.

    # ── Bomi (普美) ────────────────────────────────────────────────────────────
    # 目視核對通過：銅鍋拉麵、吃拉麵。舊炸醬麵碗／沾臉頰姿勢缺痣，改走 feed_jajangmyeon。
    # The older jajangmyeon bowl/cheeks poses omit Bomi's identifying mole. Let the
    # exact approved feed_jajangmyeon animation take the normal food route.
    ("bomi", "budae_jjigae"): ("lifestyle_v6_2/bomi_ramen_brass_pot", "interaction_eat"),
    ("bomi", "tw_beef_noodle"): ("lifestyle_v6_2/bomi_ramen_brass_pot", "interaction_eat"),
    ("bomi", "buldak"): ("lifestyle_v6_2/bomi_ramen_brass_pot", "interaction_eat"),

    # ── Eunji (恩地) ───────────────────────────────────────────────────────────
    # 目視核對通過：戴帽吃鍋煮拉麵、戴帽喝冰美式
    ("eunji", "budae_jjigae"): ("situational_v6/eunji_cap_slurp_ramen_pot",),
    ("eunji", "tw_beef_noodle"): ("situational_v6/eunji_cap_slurp_ramen_pot",),
    ("eunji", "americano"): ("situational_v6/eunji_cap_iced_americano", "feed_americano"),

    # ── Hayoung (夏榮) ─────────────────────────────────────────────────────────
    # 目視核對通過：crispy_waffles_honey 圖面是現烤麵包可頌，bakery_croissants_tower 圖面是抱大草莓
    ("hayoung", "bread"): ("situational_v6/hayoung_crispy_waffles_honey",),
    ("hayoung", "strawberry"): ("situational_v6/hayoung_bakery_croissants_tower",),
}

# Generic fallbacks: STRICTLY prop-neutral only.
# No member has a generic prop-free eating/drinking sprite in the assets.
# An item with a specific food prop (ramen bowl, teapot, mango shaved ice, etc.)
# must NEVER be a generic fallback.
# When empty, any food without a matching prop cleanly falls back to
# self.trigger_cheer(kind="feed") (joyful, prop-neutral cheer).
EAT_REACTION: dict[str, tuple[str, ...]] = {}
DRINK_REACTION: dict[str, tuple[str, ...]] = {}
# The gown poses/dances (reference/最後動圖/音樂劇) belong on the musical stage only. The 2026-11-10
# redraw added a curtain call for all five. The scene_* moves were drawn for their scene (2026-11-10).
SCENE_ACTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "bg_standby_musical_theater": {
        "chorong": ("musical_step", "musical_swish", "musical_bow", "musical_pose"),
        "bomi": ("musical_step", "musical_swish", "musical_bow", "musical_pose"),
        "eunji": ("musical_step", "musical_swish", "musical_bow", "musical_pose"),
        "namjoo": ("musical_step", "musical_swish", "musical_bow", "musical_pose"),
        "hayoung": ("musical_step", "musical_swish", "musical_bow", "musical_pose"),
    },
    "bg_standby_autumn_cafe": {
        "chorong": ("scene_cafe", "standby_hot_tea", "situational_v6_2/chorong_headband_cozy", "actions_v7/chorong_cheer_wave", ),
        "bomi": ("scene_cafe", "actions_v7/bomi_star_smile", ),
        "eunji": ("scene_cafe", "situational_v6_2/eunji_acoustic_guitar", ),
        "namjoo": ("scene_cafe", "actions_v7/namjoo_heart_walk", "situational_v6_2/namjoo_gourmet_taster", ),
        "hayoung": ("scene_cafe", "actions_v7/hayoung_casual_relax", ),
    },
    "bg_standby_moonlight_terrace": {
        "chorong": ("scene_moonlight", "situational_v6_3/chorong_blanket_cozy", ),
        "bomi": ("scene_moonlight", "situational_v6_2/bomi_sunny_strut", ),
        "eunji": ("scene_moonlight", "situational_v6_3/eunji_warm_hoodie_rest", "standby_stretch", ),
        "namjoo": ("scene_moonlight", ),
        "hayoung": ("scene_moonlight", "situational_v6_3/hayoung_headphone_vibing", ),
    },
    "bg_standby_spring_picnic": {
        "chorong": ("scene_picnic", "daily_cat_cuddle", "lifestyle_v6_1/chorong_couch_cuddle", "actions_v7/chorong_heart_tilt", "situational_v6_2/chorong_warm_teatime", ),
        "bomi": ("scene_picnic", "actions_v7/bomi_jump_cheer", "situational_v6_2/bomi_chef_stew_pot", "situational_v6_2/bomi_lemon_tea_sip", ),
        "eunji": ("scene_picnic", "daily_greeting", ),
        "namjoo": ("scene_picnic", "daily_greeting", ),
        "hayoung": ("scene_picnic", "actions_v7/hayoung_casual_relax", ),
    },
    "bg_standby_summer_beach": {
        "chorong": ("scene_beach", ),
        "bomi": ("scene_beach", ),
        "eunji": ("scene_beach", "situational_v6_2/eunji_green_smoothie", ),
        "namjoo": ("scene_flamingo", ),
        "hayoung": ("scene_beach", "special_soccer_kick", "situational_v6_2/hayoung_manga_reader", ),
    },
    # The drawn parade scenes (standby.SCENES keys), all five drawn for each (2026-11-13).
    "starfield": {m: ("scene_starfield", ) for m in ("chorong", "bomi", "eunji", "namjoo", "hayoung")},
    "campfire": {m: ("scene_campfire", ) for m in ("chorong", "bomi", "eunji", "namjoo", "hayoung")},
    "practice_room": {m: ("scene_practice_room", ) for m in ("chorong", "bomi", "eunji", "namjoo", "hayoung")},
    "concert_stage_audience": {
        "chorong": ("special_cheer_lightstick", ),
        "bomi": ("special_cheer_lightstick", "lifestyle_v6_2/bomi_slogan_towel_fist_pump", ),
        "namjoo": ("special_cheer_lightstick", "situational_v6_2/namjoo_huge_heart_hug", ),
        "hayoung": ("special_cheer_lightstick", ),
        "eunji": ("special_cheer_lightstick", "special_sing_highnote", ),
    },
    "bg_standby_dome_baseball": {
        "chorong": ("dome_baseball_cheer", ),
        "bomi": ("dome_baseball_cheer", ),
        "eunji": ("dome_baseball_cheer", ),
        "namjoo": ("dome_baseball_cheer", ),
        "hayoung": ("dome_baseball_cheer", ),
    },
    "bg_standby_eunji_dome_dream": {
        "chorong": ("special_cheer_lightstick", ),
        "bomi": ("special_cheer_lightstick", ),
        "namjoo": ("special_cheer_lightstick", ),
        "hayoung": ("special_cheer_lightstick", ),
        "eunji": (
            "dome_concert_opening",
            "dome_concert_white_dress",
            "dome_concert_blue_varsity",
            "dome_concert_red_leather",
            "dome_concert_star_jacket",
            "dome_concert_pinstripe",
            "dome_concert_rock_vest",
            "dome_concert_white_tee",
        ),
    },
    "bg_standby_eunji_fortune_room": {
        "chorong": ("special_cheer_lightstick", ),
        "bomi": ("special_cheer_lightstick", ),
        "namjoo": ("special_cheer_lightstick", ),
        "hayoung": ("special_cheer_lightstick", ),
        "eunji": ("fortune_tarot_reader", "fortune_student"),
    },
}


@dataclass(frozen=True)
class Festival:
    key: str
    action: str
    chance: float  # per roam decision, on top of the daily signature moves


CHRISTMAS = Festival("christmas", "festival_christmas", 0.6)
LUNAR_NY = Festival("lunar_ny", "festival_lunar_ny", 0.4)
LANTERN = Festival("lantern", "festival_lantern", 0.4)
MID_AUTUMN_FESTIVAL = Festival("mid_autumn", "festival_mid_autumn", 0.4)
NEW_YEAR = Festival("new_year", "festival_new_year", 0.4)
MAJOR_FESTIVALS: tuple[Festival, ...] = (NEW_YEAR, LUNAR_NY, LANTERN, MID_AUTUMN_FESTIVAL, CHRISTMAS)


def festival_occurrence_key(day: _dt.date) -> Optional[tuple[Festival, str]]:
    """Return ``(Festival, occurrence_id)`` when ``day`` falls in a major festival window."""
    if (day.month, day.day) == (1, 1):
        return NEW_YEAR, f"new_year:{day.year}"
    if (day.month, day.day) in ((12, 24), (12, 25)):
        return CHRISTMAS, f"christmas:{day.year}"
    for year in (day.year, day.year + 1):       # the eve of an early New Year can fall a year before
        if year in LUNAR_NEW_YEAR:
            new_year = _dt.date(year, *LUNAR_NEW_YEAR[year])
            offset = (day - new_year).days
            if -1 <= offset <= 1:
                return LUNAR_NY, f"lunar_ny:{year}"
            if offset == 14:
                return LANTERN, f"lantern:{year}"
    if MID_AUTUMN.get(day.year) == (day.month, day.day):
        return MID_AUTUMN_FESTIVAL, f"mid_autumn:{day.year}"
    return None


def festival_on(day: _dt.date) -> Optional[Festival]:
    """Christmas 12/24-25, New Year 1/1, Seollal (eve to day after), Lantern 1/15, Mid-Autumn 8/15."""
    pair = festival_occurrence_key(day)
    return pair[0] if pair is not None else None


def pick_signature(available: Sequence[str], last: Optional[str]) -> Optional[str]:
    """A random move from the pool, never the one she just did (unless it is her only one)."""
    fresh = [action for action in available if action != last]
    if fresh:
        return random.choice(fresh)
    return available[0] if available else None


def pick_natural(animations: Sequence[str], poses: Sequence[str], rare: Sequence[str],
                 last: Optional[str]) -> Optional[str]:
    """A small everyday action: mostly animations and poses, a rare one now and then."""
    roll = random.random()
    if rare and roll < RARE_SHARE:
        return pick_signature(rare, last)
    pool = animations if animations and roll < RARE_SHARE + NATURAL_ANIMATION_SHARE else poses or animations
    return pick_signature(pool, last)
