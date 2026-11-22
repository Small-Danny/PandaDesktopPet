"""Reviewed white-face contours in normalized source pixels.

Reference: work/evidence/1116_wave5_fix/before. Targets distinguish standing,
profile walking and sleeping / long-gown poses. Never detect a lightstick or
fur hat as a face at runtime. All scaling is shared by desktop and standby.
"""
from __future__ import annotations

import hashlib
import json

FACE_WIDTHS = {'bomi.cameo_greet_wave': 158.0,
 'bomi.cheer': 151.0,
 'bomi.daily_greeting': 154.0,
 'bomi.dome_baseball_cheer': 147.0,
 'bomi.festival_christmas': 158.0,
 'bomi.festival_lantern': 146.5,
 'bomi.festival_lunar_ny': 159.5,
 'bomi.festival_mid_autumn': 153.5,
 'bomi.festival_new_year': 146.0,
 'bomi.idle': 158.0,
 'bomi.musical_bow': 127.0,
 'bomi.musical_pose': 121,
 'bomi.musical_step': 127.5,
 'bomi.musical_swish': 121.0,
 'bomi.sleep': 119.0,
 'bomi.special_birthday': 157.0,
 'bomi.special_cheer_lightstick': 158.5,
 'bomi.walk': 134.5,
 'bomi.walk_left': 134.5,
 'chorong.cheer': 150.0,
 'chorong.daily_greeting': 150.0,
 'chorong.dome_baseball_cheer': 144.0,
 'chorong.festival_christmas': 153.0,
 'chorong.festival_lantern': 141.5,
 'chorong.festival_lunar_ny': 152.0,
 'chorong.festival_mid_autumn': 154.0,
 'chorong.festival_new_year': 169.5,
 'chorong.idle': 152.0,
 'chorong.musical_bow': 123.0,
 'chorong.musical_pose': 122,
 'chorong.musical_step': 123.5,
 'chorong.musical_swish': 120.5,
 'chorong.sleep': 133.5,
 'chorong.special_birthday': 151.0,
 'chorong.special_cheer_lightstick': 151.0,
 'chorong.walk': 135.0,
 'eunji.cameo_greet_wave': 143.5,
 'eunji.cheer': 143.0,
 'eunji.daily_greeting': 137.0,
 'eunji.dome_baseball_cheer': 132.0,
 'eunji.dome_concert_blue_varsity': 137.0,
 'eunji.dome_concert_opening': 118.0,
 'eunji.dome_concert_pinstripe': 134.5,
 'eunji.dome_concert_red_leather': 126.5,
 'eunji.dome_concert_rock_vest': 128.0,
 'eunji.dome_concert_star_jacket': 146.5,
 'eunji.dome_concert_white_dress': 145.0,
 'eunji.dome_concert_white_tee': 131.5,
 'eunji.festival_christmas': 147.0,
 'eunji.festival_lantern': 158.0,
 'eunji.festival_lunar_ny': 146.5,
 'eunji.festival_mid_autumn': 140.5,
 'eunji.festival_new_year': 151.0,
 'eunji.fortune_student': 139.0,
 'eunji.fortune_tarot_reader': 140.0,
 'eunji.idle': 147.0,
 'eunji.musical_bow': 130.0,
 'eunji.musical_pose': 122,
 'eunji.musical_step': 121.5,
 'eunji.musical_swish': 128.0,
 'eunji.sleep': 112.0,
 'eunji.special_birthday': 144.5,
 'eunji.special_cheer_lightstick': 147.0,
 'eunji.walk': 131.0,
 'eunji.walk_left': 131.0,
 'hayoung.cameo_greet_wave': 155.0,
 'hayoung.cheer': 145.0,
 'hayoung.daily_greeting': 151.5,
 'hayoung.dome_baseball_cheer': 144.5,
 'hayoung.festival_christmas': 155.0,
 'hayoung.festival_lantern': 146.5,
 'hayoung.festival_lunar_ny': 157.0,
 'hayoung.festival_mid_autumn': 147.5,
 'hayoung.festival_new_year': 155.5,
 'hayoung.idle': 156.5,
 'hayoung.musical_bow': 127.0,
 'hayoung.musical_pose': 123,
 'hayoung.musical_step': 122.5,
 'hayoung.musical_swish': 130.0,
 'hayoung.sleep': 127.5,
 'hayoung.special_birthday': 154.5,
 'hayoung.special_cheer_lightstick': 157.0,
 'hayoung.walk': 132.0,
 'namjoo.cameo_greet_wave': 160.5,
 'namjoo.cheer': 150.0,
 'namjoo.daily_greeting': 157.0,
 'namjoo.dome_baseball_cheer': 153.0,
 'namjoo.festival_christmas': 162.0,
 'namjoo.festival_lantern': 152.5,
 'namjoo.festival_lunar_ny': 161.5,
 'namjoo.festival_mid_autumn': 157.0,
 'namjoo.festival_new_year': 164.0,
 'namjoo.idle': 161.0,
 'namjoo.musical_bow': 129.0,
 'namjoo.musical_pose': 121,
 'namjoo.musical_step': 120.5,
 'namjoo.musical_swish': 117.5,
 'namjoo.sleep': 122.0,
 'namjoo.special_birthday': 158.0,
 'namjoo.special_cheer_lightstick': 160.0,
 'namjoo.walk': 137.0}

# Reviewed runtime multiframe actions with measurable frontal face contours.
# Feeding, oversized props and obscuring headwear retain their existing scale.
FACE_WIDTHS.update({
    "bomi.daily_bored": 155.5,
    "bomi.daily_full": 149.5,
    "bomi.daily_hug_side": 146.0,
    "bomi.daily_pat": 151.0,
    "bomi.daily_sulk": 149.0,
    "bomi.daily_surprise": 141.0,
    "bomi.daily_tap": 152.0,
    "bomi.daily_yawn": 153.0,
    "bomi.interaction_drag": 163.0,
    "bomi.interaction_eat": 158.0,
    "bomi.scene_beach": 148.5,
    "bomi.scene_cafe": 152.0,
    "bomi.scene_campfire": 157.5,
    "bomi.scene_moonlight": 148.0,
    "bomi.scene_picnic": 152.0,
    "bomi.scene_practice_room": 158.0,
    "bomi.scene_starfield": 156.5,
    "bomi.special_gorilla": 157.5,
    "bomi.special_taekwondo": 136.0,
    "bomi.winter_cocoa": 143.0,
    "chorong.daily_bored": 160.0,
    "chorong.daily_full": 157.0,
    "chorong.daily_hug_side": 141.5,
    "chorong.daily_pat": 150.0,
    "chorong.daily_sulk": 149.0,
    "chorong.daily_surprise": 152.0,
    "chorong.daily_tap": 155.0,
    "chorong.daily_yawn": 154.0,
    "chorong.interaction_drag": 152.0,
    "chorong.scene_beach": 154.5,
    "chorong.scene_cafe": 156.0,
    "chorong.scene_campfire": 151.0,
    "chorong.scene_moonlight": 155.0,
    "chorong.scene_picnic": 152.5,
    "chorong.scene_practice_room": 150.5,
    "chorong.scene_starfield": 151.0,
    "chorong.special_blow_kiss": 152.0,
    "chorong.special_cartwheel": 148.0,
    "chorong.special_hapkido_kick": 152.0,
    "chorong.standby_hot_tea": 149.0,
    "chorong.winter_cocoa": 150.0,
    "eunji.daily_bored": 145.0,
    "eunji.daily_full": 146.0,
    "eunji.daily_hug_side": 139.0,
    "eunji.daily_pat": 148.0,
    "eunji.daily_sulk": 146.0,
    "eunji.daily_surprise": 141.5,
    "eunji.daily_tap": 147.0,
    "eunji.daily_yawn": 143.0,
    "eunji.interaction_drag": 146.0,
    "eunji.scene_beach": 150.0,
    "eunji.scene_cafe": 140.0,
    "eunji.scene_campfire": 146.5,
    "eunji.scene_moonlight": 143.5,
    "eunji.scene_picnic": 147.0,
    "eunji.scene_practice_room": 146.0,
    "eunji.scene_starfield": 145.5,
    "eunji.special_boxing": 140.5,
    "eunji.special_guitar": 147.0,
    "eunji.special_sing_highnote": 146.5,
    "eunji.standby_stretch": 147.0,
    "eunji.winter_cocoa": 138.5,
    "hayoung.daily_bored": 153.5,
    "hayoung.daily_full": 146.0,
    "hayoung.daily_hug_side": 141.0,
    "hayoung.daily_pat": 153.5,
    "hayoung.daily_sulk": 152.5,
    "hayoung.daily_surprise": 148.5,
    "hayoung.daily_tap": 151.5,
    "hayoung.daily_yawn": 148.5,
    "hayoung.interaction_drag": 157.0,
    "hayoung.scene_beach": 152.0,
    "hayoung.scene_cafe": 149.5,
    "hayoung.scene_campfire": 155.0,
    "hayoung.scene_moonlight": 157.0,
    "hayoung.scene_picnic": 149.0,
    "hayoung.scene_practice_room": 154.5,
    "hayoung.scene_starfield": 158.0,
    "hayoung.special_gaming": 158.5,
    "hayoung.special_soccer_kick": 155.0,
    "hayoung.winter_cocoa": 148.0,
    "namjoo.daily_bored": 161.0,
    "namjoo.daily_full": 162.0,
    "namjoo.daily_hug_side": 144.5,
    "namjoo.daily_pat": 161.0,
    "namjoo.daily_sulk": 148.5,
    "namjoo.daily_surprise": 153.0,
    "namjoo.daily_tap": 151.0,
    "namjoo.daily_yawn": 155.5,
    "namjoo.interaction_drag": 163.0,
    "namjoo.scene_cafe": 156.0,
    "namjoo.scene_campfire": 161.0,
    "namjoo.scene_moonlight": 162.5,
    "namjoo.scene_picnic": 162.0,
    "namjoo.scene_practice_room": 157.5,
    "namjoo.scene_starfield": 159.0,
    "namjoo.special_boxing": 157.5,
    "namjoo.special_cheer_lightstick_alt": 162.5,
    "namjoo.winter_cocoa": 143.0,
    # Shared assets have member=None in AnimationSpec.
    "None.secret_clover_visitor": 156.0,
})

CHORONG_BASEBALL_F3_SHA256 = 'a00386427516aa2f36181e16ea51098f3ac1478b35e34820a82a03fdd7797163'
LANTERN_F3 = {
    # SHA-256, split y, original feet y, downward offset for the upper segment.
    "bomi": ("21ec13b6640742de53d005e04b0b73a672a140dd788d37f31538524bdf9204d4", 167, 274, 108),
    "namjoo": ("e6d7ba18efb062ef1d3c4912f16dfcf88ca7cd9a783571931ca63be7f2fd1862", 214, 335, 62),
}

def face_target(action: str, member: str | None = None) -> float:
    if member == "eunji" and (action.startswith("dome_concert_") or action in ("fortune_tarot_reader", "fortune_student")):
        return 150.0
    if member == "eunji" and action == "dome_baseball_cheer":
        return 148.0  # cap needs headroom; 111px face at the 192px reference size
    if action in ("walk", "walk_left"):
        return 130.0  # projected profile; do not inflate it to a frontal face
    if action == "sleep" or action.startswith("musical_"):
        return 144.0
    return 152.0


def action_scale(member: str | None, action: str, fallback: float = 1.0) -> float:
    width = FACE_WIDTHS.get(f"{member}.{action}")
    return face_target(action, member) / width if width else fallback


def action_scale_factor(member: str | None, action: str, reference_scale: float) -> float:
    return action_scale(member, action, reference_scale) / reference_scale if reference_scale else 1.0


CALIBRATION_REVISION = hashlib.sha256(json.dumps(
    {"faces": FACE_WIDTHS, "targets": [152, 130, 144, 150, 148],
     "calibrated_frames": LANTERN_F3, "revision": 3},
    sort_keys=True).encode()).hexdigest()[:16]


def calibrated_frame(image, member: str | None, action: str, frame_index: int, source_sha256: str | None = None):
    """Move the head/arms as one block and compress the torso to the shared baseline."""
    if frame_index != 2:
        return image
    if action == "festival_lantern" and member in LANTERN_F3 and image.size == (384, 416):
        digest, split_y, feet_y, offset_y = LANTERN_F3[member]
    elif member == "chorong" and action == "dome_baseball_cheer" and image.size == (384, 384):
        digest, split_y, feet_y, offset_y = CHORONG_BASEBALL_F3_SHA256, 250, 372, 29
    else:
        return image
    if source_sha256 != digest:
        return image

    from PIL import Image
    baseline = 372
    lower_y = split_y + offset_y
    out = Image.new("RGBA", image.size)
    out.paste(image.crop((0, 0, 384, split_y)), (0, offset_y))
    lower = image.crop((0, split_y, 384, feet_y)).resize(
        (384, baseline - lower_y), Image.Resampling.LANCZOS)
    out.paste(lower, (0, lower_y))
    if feet_y == baseline:
        out.paste(image.crop((0, baseline, 384, image.height)), (0, baseline))
    return out
