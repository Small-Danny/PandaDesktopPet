"""test_status_card_and_quotes.py — Verification of Status Card and Warm Quotes."""
import os
import sys
import tkinter as tk
from pathlib import Path

# Fix sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.status_card import PandaStatusCard, get_passion_tier, layout_badge_pills
from app.personalities import (
    WARM_QUOTES,
    get_member_badge,
    get_random_chat_quote,
    get_random_warm_quote,
)


EXPECTED_COUNTS = {"chorong": 62, "bomi": 61, "eunji": 64, "namjoo": 61, "hayoung": 61}


def test_warm_quotes_loaded():
    assert len(WARM_QUOTES) == 5, f"Expected 5 members, got {len(WARM_QUOTES)}"
    for m, expected in EXPECTED_COUNTS.items():
        assert m in WARM_QUOTES, f"Missing {m} in quotes"
        assert len(WARM_QUOTES[m]) == expected, f"Expected {expected} quotes for {m}, got {len(WARM_QUOTES[m])}"
        for q in WARM_QUOTES[m]:
            assert q.get("quote_category") == "COMPANION_LINE"
            for lang in ("zh", "ko", "en"):
                assert len(q.get(lang, "").strip()) > 0

    print("[PASS] 309 companion lines verified across 5 members in 3 languages!")


def test_quote_retrieval():
    for lang in ["zh_TW", "ko", "en"]:
        badge, quote = get_random_chat_quote("bomi", lang=lang)
        assert len(badge) > 0
        assert len(quote) > 0
        warm = get_random_warm_quote("eunji", lang=lang)
        assert len(warm) > 0
    print("[PASS] Dynamic quote retrieval verified for zh_TW, ko, en!")


def test_status_card_lifecycle():
    root = tk.Tk()
    root.withdraw()

    # Test initialization near pet
    card = PandaStatusCard(
        parent=root,
        char_key="chorong",
        char_name="初瓏 (Chorong)",
        badge_desc="🐱 貓咪控 ｜ 🧹 打掃狂人",
        passion_points=150,
        companion_start_time=1000.0,
        feed_count=3,
        anchor_x=500,
        anchor_y=400,
        lang="zh_TW",
    )
    root.update()

    # Verify geometry placed near pet
    win_x = card.window.winfo_x()
    win_y = card.window.winfo_y()
    assert win_x > 0 and win_y > 0, "Card window coordinates should be valid"
    assert card.avatar_thumb is not None, "Avatar thumbnail should be generated"

    # Test drag math
    class MockEvent:
        x_root = 600
        y_root = 450
        x = 50
        y = 50

    card.on_drag_begin(MockEvent())
    assert card.drag_offset_x == MockEvent.x_root - card.window.winfo_x()
    assert card.drag_offset_y == MockEvent.y_root - card.window.winfo_y()

    MockEvent.x_root = 650
    MockEvent.y_root = 500
    card.on_drag_move(MockEvent())
    root.update()
    card.on_drag_end(MockEvent())
    assert card.drag_offset_x is None

    # Test dynamic refresh on member switch
    card.refresh(
        char_key="bomi",
        char_name="普美 (Bomi)",
        badge_desc="🐶 狗狗狂熱 ｜ 🏕️ 露營愛好者",
        passion_points=260,
        companion_start_time=1000.0,
        feed_count=4,
        lang="ko",
    )
    root.update()
    assert card.char_key == "bomi"
    assert card.avatar_thumb is not None

    card.close()
    root.destroy()
    print("[PASS] Status card spawn, drag, avatar thumbnail, and dynamic refresh passed!")


def test_badge_layout_shrinks_then_wraps_never_drops():
    measure = lambda text, pt: len(text) * pt      # 1 design px per glyph point
    tiers = ((8, 12, 6), (7, 8, 4))
    pt, pills = layout_badge_pills(["aaaa", "bbbb", "cccc"], measure, 0, 200, tiers, 10)
    assert pt == 8 and [row for _x, row, _w, _t in pills] == [0, 0, 0]
    pt, pills = layout_badge_pills(["a" * 7] * 3, measure, 0, 190, tiers, 10)
    assert pt == 7 and [row for _x, row, _w, _t in pills] == [0, 0, 0]   # 8pt overflows, 7pt fits
    pt, pills = layout_badge_pills(["a" * 10] * 3, measure, 0, 190, tiers, 10)
    assert pt == 7 and [row for _x, row, _w, _t in pills] == [0, 0, 1]   # wraps, nothing dropped
    assert all(x + w <= 190 for x, _row, w, _t in pills)
    pt, pills = layout_badge_pills(["a" * 40], measure, 0, 100, tiers, 10)
    assert pills[0][2] == 100 and pills[0][3].endswith("…")              # one overlong pill is shortened
    assert measure(pills[0][3], pt) + 8 <= 100
    print("[PASS] Badge layout shrinks, then wraps, never drops!")


def _status_card(root, member, lang, badge_desc):
    return PandaStatusCard(
        parent=root, char_key=member, char_name=member, badge_desc=badge_desc,
        passion_points=150, companion_start_time=1000.0, feed_count=3, lang=lang,
    )


def test_status_card_badges_all_members_and_languages():
    root = tk.Tk()
    root.withdraw()
    try:
        for scaling in (1.3333333333333333, 2.6666666666666665):
            root.tk.call("tk", "scaling", scaling)
            for lang in ("zh_TW", "ko", "en"):
                for member in ("chorong", "bomi", "eunji", "namjoo", "hayoung"):
                    badge_desc = str(get_member_badge(member, lang))
                    traits = [t for t in badge_desc.replace("｜", "|").split("|") if t.strip()]
                    card = _status_card(root, member, lang, badge_desc)
                    try:
                        cv, k = card.canvas, card.ui_scale
                        where = (member, lang, scaling)
                        pills = [cv.bbox(i) for i in cv.find_withtag("badge_pill")]
                        texts = [cv.bbox(i) for i in cv.find_withtag("badge_text")]
                        assert len(pills) == len(texts) == len(traits), where
                        for (px1, _a, px2, _b), (tx1, _c, tx2, _d) in zip(pills, texts):
                            assert px1 >= 116 * k - 3 * k and px2 <= (card._design_w - 16) * k + 3 * k, (where, px1, px2)
                            assert tx1 >= px1 and tx2 <= px2, where
                        # Real data fits on one row: the card keeps its height
                        assert len({p[1] for p in pills}) == 1, where
                        assert card.h == round(card._design_h * k), where
                    finally:
                        card.close()

        root.tk.call("tk", "scaling", 1.3333333333333333)
        long_desc = " ｜ ".join(["🌸 An exceptionally long trait label"] * 3)
        card = _status_card(root, "chorong", "en", long_desc)
        try:
            cv = card.canvas
            pills = [cv.bbox(i) for i in cv.find_withtag("badge_pill")]
            assert len(pills) == 3 and len({p[1] for p in pills}) >= 2   # wrapped, nothing dropped
            assert card.h > round(card._design_h * card.ui_scale)         # the card grows instead
            assert all(p[2] <= (card._design_w - 16 + 3) * card.ui_scale for p in pills)
        finally:
            card.close()
    finally:
        root.destroy()
    print("[PASS] Status card badges: 5 members x 3 languages x 96/192 DPI, none dropped!")


def test_status_card_without_traits_draws_no_empty_pill():
    root = tk.Tk()
    root.withdraw()
    try:
        assert layout_badge_pills([], lambda text, pt: len(text) * pt, 0, 100, ((8, 12, 6),), 10) == (8, [])
        for desc in ("", "  ｜ "):
            card = _status_card(root, "chorong", "en", desc)
            try:
                assert card.canvas.find_withtag("badge_pill") == (), desc
                assert card.h == round(card._design_h * card.ui_scale), desc     # no extra badge row
            finally:
                card.close()
    finally:
        root.destroy()
    print("[PASS] Status card without traits keeps its height and draws no empty pill!")


def test_bomi_and_hayoung_wcag_aa_contrast_and_escape_binding():
    from app.status_card import MEMBER_THEMES

    def srgb_to_lin(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    def lum(hex_col: str) -> float:
        h = hex_col.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)

    def contrast(c1: str, c2: str) -> float:
        l1, l2 = lum(c1), lum(c2)
        if l1 < l2:
            l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    for member in ("bomi", "hayoung"):
        t = MEMBER_THEMES[member]
        for fg in (t["primary"], t["accent"]):
            for bg in ("#ffffff", t["soft_bg"], t["header_fill"], t["pill_fill"]):
                assert contrast(fg, bg) >= 4.5, f"{member} {fg} on {bg} < 4.5"
        assert contrast("#ffffff", t["primary"]) >= 4.5, f"{member} white on primary < 4.5"
        assert contrast("#ffffff", t["bar_fill"]) >= 4.5, f"{member} white on bar_fill < 4.5"

    root = tk.Tk()
    root.withdraw()
    try:
        closed = []
        card = PandaStatusCard(root, char_key="hayoung", on_close=lambda: closed.append(True))
        assert card.window.bind("<Escape>"), "Escape binding missing on PandaStatusCard"
        from app.status_card import _STATUS_AVATAR_PIL_CACHE
        assert ("hayoung", round(76 * card.ui_scale)) in _STATUS_AVATAR_PIL_CACHE
        card.close()
        assert closed == [True]
    finally:
        root.destroy()
    print("[PASS] Bomi & Hayoung WCAG AA contrast >= 4.5:1 and Escape binding verified!")


if __name__ == "__main__":
    test_warm_quotes_loaded()
    test_quote_retrieval()
    test_status_card_lifecycle()
    test_badge_layout_shrinks_then_wraps_never_drops()
    test_status_card_badges_all_members_and_languages()
    test_status_card_without_traits_draws_no_empty_pill()
    test_bomi_and_hayoung_wcag_aa_contrast_and_escape_binding()
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

