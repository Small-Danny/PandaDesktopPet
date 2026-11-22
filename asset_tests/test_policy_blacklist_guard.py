"""Regression guard for the 2026-11-22 class-A asset audit.

1. The quarantine blacklist in work/PROP_SPRITES_MAPPING.md (section 三) is enforced by
   exact defective bytes: neither the listed path nor any byte-identical copy elsewhere
   may be approved while it still carries those bytes. A listed path may come back only
   after it was repaired (different bytes).
2. Byte-identical copies of blocked files are never approved under another path, except
   for the explicit identity-only renames below (bytes are fine, only the name was wrong).
3. No approved file has a "washed-out" enclosed transparent hole: interior transparency
   (>200 px) whose rim is largely fill colour rather than dark outline (a white belly or
   face flooded away through a crop line). Legitimate arm/prop gaps are rimmed by outline.
4. No new straight crop-line edges: long perfectly straight alpha edges made of light
   (non-outline) pixels. Pre-existing hits are frozen in KNOWN_FLAT_EDGE_PENDING and await
   visual review; anything new fails.

Checks 3 and 4 decode every frame, so they only scan approved bytes that are not in
tests/data/art_scan_clean_20261122.json (the full approved set scanned clean on
2026-11-22). New or changed approvals are always scanned. Set PANDA_FULL_ART_SCAN=1 to
rescan everything (about 6 minutes).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parents[1]
CHAR = ROOT / "work" / "characters"
POLICY = ROOT / "work" / "asset_review_policy.json"
MAPPING = ROOT / "work" / "PROP_SPRITES_MAPPING.md"

# Defective bytes recorded on 2026-11-22 for every blacklist entry (before any repair).
BLACKLIST_DEFECT_SHA256 = {
    "bomi/pets_special_v6/bomi_frisbee_white_puppy_sugar.png": "2e1d50e4d14ae2fab4b9b43dfbeb08df1ede23c12d513686acc464791dcd00dd",
    "eunji/situational_all1/eunji_walk_joy.png": "804ec2cd46a2ca9cd476aaae5af413a4043c52d818947ee699b021c24fc6a1fe",
    "eunji/situational_all1/eunji_wink_cheer.png": "c8481276200f6d9eb316cfff8e5d4a96d801a5e94513e35f8b1d589aee7b3514",
    "namjoo/situational_all1/namjoo_sleep_sit.png": "2025182c1b42d32dbd26d5fce3871cc38ca6d68f043aaad8a1f70542cdd5711a",
    "hayoung/situational_all1/hayoung_soccer_triumph.png": "c1944e30e58f39e0cbe1f9c52e93051c298b39424bb9e0a45ae2495f5b4ba92a",
    "hayoung/situational_all1/hayoung_victory_bounce.png": "adc9398e07bcba14f8ed5cff2a6fcbc9413070bd50f065f82fe6ea7ba6d9e9f3",
    "eunji/walk_v3_04.png": "74afdefb37082f4f2ce565e44f8a8588ccaeefedd43f6cdfc4c0e5a382dbca61",
    "hayoung/walk_v3_02.png": "36f46acf51b7e7c103a8b55edc876efa081bba1fcd502ba36e333eda2be963a0",
}

# Approved path -> blocked path with identical bytes. The blocked copy carries a wrong
# member name; the art itself is Chorong (archive 初瓏6.jpg) and was renamed.
IDENTITY_ONLY_RENAMES = {
    "shared/situational_all_v2/chorong_camp_puppy.png": "bomi/situational_upgraded/bomi_camp_sugar_puppy.png",
    "shared/situational_all_v2/chorong_sing_handheld_mic.png": "eunji/situational_upgraded/eunji_sing_handheld_mic.png",
    "shared/situational_all_v2/chorong_sit_wave_happy.png": "eunji/situational_upgraded/eunji_sit_listen_music.png",
    "shared/situational_all_v2/chorong_gamer_headset.png": "hayoung/situational_upgraded/hayoung_gamer_controller.png",
    "shared/situational_all_v2/chorong_gamer_headset_sit.png": "hayoung/situational_upgraded/hayoung_gamer_controller_sit.png",
    "shared/situational_all_v2/chorong_soccer_scarf.png": "hayoung/situational_upgraded/hayoung_soccer_scarf_ball.png",
    "shared/situational_all_v2/chorong_flamingo_swimring.png": "namjoo/situational_upgraded/namjoo_flamingo_swimring.png",
    "shared/situational_all_v2/chorong_food_feast.png": "namjoo/situational_upgraded/namjoo_street_food_feast.png",
}

# Approved files that already showed a straight light edge on 2026-11-22. They are queued
# for visual review (most are //3 grid crops of situational sheets); do not add to this list
# without looking at the frame.
KNOWN_FLAT_EDGE_PENDING = frozenset({
    "bomi/lifestyle_v6_2/bomi_variety_belly_laugh.png",
    "bomi/sequence_campfire_v6/bomi_campfire_blow_marshmallow.png",
    "bomi/situational_v6_2/bomi_chef_stew_pot.png",
    "chorong/stage2_20261108/christmas_gift/frame_01.png",
    "chorong/stage2_20261108/christmas_gift/frame_04.png",
    "eunji/sequence_hug_side_v7/eunji_hug_side_01.png",
    "eunji/sequence_hug_side_v7/eunji_hug_side_02.png",
    "eunji/sequence_hug_side_v7/eunji_hug_side_03.png",
    "eunji/sequence_hug_side_v7/eunji_hug_side_04.png",
    "eunji/sequence_sing_highnote_v6/eunji_sing_mic_tilt_head_high_note.png",
    "eunji/situational_v6/eunji_cap_sleep_pink_blanket.png",
    "eunji/situational_v6_3/eunji_cap_wink_cheer.png",
    "hayoung/situational_v6/hayoung_bakery_croissants_tower.png",
    "hayoung/situational_v6/hayoung_champion_golden_trophy.png",
    "hayoung/situational_v6_3/hayoung_headphone_vibing.png",
    "namjoo/stage2_20261108/feed_coriander/frame_02.png",
    "namjoo/stage2_20261108/feed_coriander/frame_03.png",
    "shared/anniversary_special_v6/anniv_group_duo_hug_celebration.png",
    "shared/interactions_duo/duo_bomi_hayoung_play_01.png",
    "shared/interactions_duo/duo_bomi_hayoung_play_03.png",
    "shared/situational_all3_v6/all3_r2_c3.png",
    "shared/situational_all4_v6/all4_r2_c3.png",
    "shared/situational_all_v2/chorong_food_feast.png",
    "shared/situational_all_v2/chorong_soccer_scarf.png",
    "shared/situational_all_v2/chorong_sofa_tabby_cat.png",
})

HOLE_MIN_AREA = 200
HOLE_MIN_DARK_RIM = 0.45          # any hole above HOLE_MIN_AREA
LARGE_HOLE_AREA = 1000
LARGE_HOLE_MIN_DARK_RIM = 0.75    # a face-sized hole needs an almost fully outlined rim
CLEAN_SCAN = ROOT / "tests" / "data" / "art_scan_clean_20261122.json"
_RUN = re.compile(rb"\xff{28,}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8-sig"))


def blacklist_paths() -> list[str]:
    text = MAPPING.read_text(encoding="utf-8")
    section = text.split("## 三、", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"`([^`]+\.png)`", section)


def washed_out_holes(im: Image.Image) -> list[tuple[int, float]]:
    alpha = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    w, h = alpha.size
    padded = Image.new("L", (w + 2, h + 2), 0)
    padded.paste(alpha, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)
    work = padded.crop((1, 1, w + 1, h + 1)).point(lambda v: 255 if v == 0 else 0)
    if ImageStat.Stat(work).sum[0] / 255 <= HOLE_MIN_AREA:
        return []
    dark = im.convert("RGB").convert("L").point(lambda v: 255 if v < 120 else 0)
    found = []
    while (box := work.getbbox()) is not None:
        px = work.load()
        seed = next((x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if px[x, y] == 255)
        one = work.copy()
        ImageDraw.floodfill(one, seed, 100)
        comp = one.point(lambda v: 255 if v == 100 else 0)
        work = ImageChops.subtract(work, comp)
        area = ImageStat.Stat(comp).sum[0] / 255
        if area <= HOLE_MIN_AREA:
            continue
        rim = ImageChops.subtract(comp.filter(ImageFilter.MaxFilter(3)), comp)
        n = ImageStat.Stat(rim).sum[0] / 255
        dark_rim = ImageStat.Stat(ImageChops.multiply(rim, dark)).sum[0] / 255 / n if n else 1.0
        if dark_rim < HOLE_MIN_DARK_RIM or (area >= LARGE_HOLE_AREA and dark_rim < LARGE_HOLE_MIN_DARK_RIM):
            found.append((int(area), round(dark_rim, 2)))
    return found


def flat_light_edges(im: Image.Image, light: int = 150, light_frac: float = 0.6) -> list[tuple[str, int, int]]:
    alpha = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    lum = im.convert("RGB").convert("L").point(lambda v: 255 if v >= light else 0)
    w, h = alpha.size
    hits = []
    for side, (dx, dy) in {"left": (1, 0), "right": (-1, 0), "top": (0, 1), "bottom": (0, -1)}.items():
        shifted = ImageChops.offset(alpha, dx, dy)
        if dx == 1:
            shifted.paste(0, (0, 0, 1, h))
        elif dx == -1:
            shifted.paste(0, (w - 1, 0, w, h))
        elif dy == 1:
            shifted.paste(0, (0, 0, w, 1))
        else:
            shifted.paste(0, (0, h - 1, w, h))
        edge = ImageChops.subtract(alpha, shifted)
        lit = ImageChops.multiply(edge, lum)
        if dx:
            edge = edge.transpose(Image.Transpose.TRANSPOSE)
            lit = lit.transpose(Image.Transpose.TRANSPOSE)
        eb, lb, rw = edge.tobytes(), lit.tobytes(), edge.size[0]
        for y in range(edge.size[1]):
            for m in _RUN.finditer(eb[y * rw:(y + 1) * rw]):
                s, e = m.span()
                if lb[y * rw + s:y * rw + e].count(b"\xff") / (e - s) >= light_frac:
                    hits.append((side, y, e - s))
    return hits


def scan_targets() -> list[str]:
    """Approved paths whose exact bytes have not been scanned clean before."""
    approved = _policy()["approved"]
    if os.environ.get("PANDA_FULL_ART_SCAN") == "1" or not CLEAN_SCAN.is_file():
        return sorted(approved)
    clean = set(json.loads(CLEAN_SCAN.read_text(encoding="utf-8"))["sha256"])
    return sorted(p for p, digest in approved.items() if digest not in clean)


# 2026-11-22 class-A re-cuts: edge pixels were locked to the outline colour at 256 px so the
# smooth-alpha (medium/large) display path, which skips lock_fringe, shows no pale halo.
CLASS_A_RECUT_PREFIXES = (
    "chorong/lifestyle_v6_1/chorong_", "chorong/special_v6_1/chorong_sp_", "chorong/daily_v1/daily_cat_cuddle/",
    "eunji/walk_v3_0", "bomi/pets_special_v6/bomi_frisbee", "shared/pets_special_v6/bomi_frisbee",
    "shared/interactions_duo/duo_chorong_namjoo_cozy_care", "bomi/situational_v6_3/bomi_birthday_wish",
)
CLASS_A_RECUT_MAX_FRINGE = 0.25  # approved-library median is ~0.33; the sparkle wand pose is the worst at 0.24


class BlacklistGuardTest(unittest.TestCase):
    def test_class_a_recuts_have_no_pale_fringe(self) -> None:
        from app.sprite_polish import fringe_ratio
        approved = _policy()["approved"]
        recuts = sorted(p for p in approved if p.startswith(CLASS_A_RECUT_PREFIXES))
        self.assertGreaterEqual(len(recuts), 30)
        bad = {}
        for rel in recuts:
            ratio = fringe_ratio(Image.open(CHAR / rel).convert("RGBA"))
            if ratio > CLASS_A_RECUT_MAX_FRINGE:
                bad[rel] = round(ratio, 3)
        self.assertEqual(bad, {}, "re-cut art with a pale edge halo (run lock_fringe at 256 px before approving)")

    def test_every_blacklist_entry_has_recorded_defect_bytes(self) -> None:
        listed = blacklist_paths()
        self.assertTrue(listed, "blacklist section not found in PROP_SPRITES_MAPPING.md")
        self.assertEqual(set(listed), set(BLACKLIST_DEFECT_SHA256),
                         "record the defective SHA-256 of every blacklist entry here")

    def test_blacklisted_bytes_are_never_approved(self) -> None:
        approved = _policy()["approved"]
        defects = set(BLACKLIST_DEFECT_SHA256.values())
        for path, digest in approved.items():
            self.assertNotIn(digest, defects, f"{path} carries blacklisted defective bytes")
        for path in CHAR.rglob("*.png"):
            rel = path.relative_to(CHAR).as_posix()
            if rel in approved:
                self.assertNotIn(_sha(path), defects, f"{rel} on disk carries blacklisted bytes")

    def test_blocked_bytes_are_not_approved_under_another_path(self) -> None:
        policy = _policy()
        by_hash: dict[str, list[str]] = {}
        for path, digest in policy["approved"].items():
            by_hash.setdefault(digest, []).append(path)
        for blocked in policy["blocked"]:
            path = CHAR / blocked
            if not path.is_file():
                continue
            for twin in by_hash.get(_sha(path), []):
                self.assertEqual(IDENTITY_ONLY_RENAMES.get(twin), blocked,
                                 f"{twin} is approved but byte-identical to blocked {blocked}")

    def test_no_washed_out_enclosed_holes_in_approved_art(self) -> None:
        bad = {}
        for rel in scan_targets():
            with Image.open(CHAR / rel) as im:
                holes = washed_out_holes(im.convert("RGBA"))
            if holes:
                bad[rel] = holes
        self.assertEqual(bad, {}, "approved art has enclosed transparent holes rimmed by fill colour")

    def test_no_new_straight_crop_edges_in_approved_art(self) -> None:
        new = []
        for rel in scan_targets():
            if rel in KNOWN_FLAT_EDGE_PENDING:
                continue
            with Image.open(CHAR / rel) as im:
                if flat_light_edges(im.convert("RGBA")):
                    new.append(rel)
        self.assertEqual(new, [], "approved art shows a straight light crop edge (cell-line cut)")

    def test_detectors_catch_the_known_defects(self) -> None:
        with Image.open(CHAR / "eunji/situational_all1/eunji_wink_cheer.png") as im:
            self.assertTrue(washed_out_holes(im.convert("RGBA")))
        with Image.open(CHAR / "shared/situational_all1/apink_group_cheer_double.png") as im:
            self.assertTrue(washed_out_holes(im.convert("RGBA")))
        with Image.open(CHAR / "hayoung/situational_v6_3/hayoung_victory_peace.png") as im:
            self.assertTrue(flat_light_edges(im.convert("RGBA")))
        # Legitimate arm/prop gaps (dark outline rim) are not defects.
        for rel in ("chorong/lifestyle_v6_1/chorong_double_lightstick.png",
                    "chorong/stage2_20261108/scene_beach/frame_03.png",
                    "namjoo/festival_christmas_20261108/frame_01.png"):
            with Image.open(CHAR / rel) as im:
                self.assertEqual(washed_out_holes(im.convert("RGBA")), [], rel)

    def test_clean_scan_baseline_only_lists_hashes(self) -> None:
        if CLEAN_SCAN.is_file():
            data = json.loads(CLEAN_SCAN.read_text(encoding="utf-8"))
            self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h) for h in data["sha256"]))


if __name__ == "__main__":
    unittest.main()
