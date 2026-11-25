"""C6/C7 acceptance: speech-bubble text must never be clipped or covered.

Renders real KawaiiSpeechBubble windows for every theme x language (zh_TW / ko /
en) x length (short / medium / very long) and checks, from the canvas items:

  * every text run lies inside the window and inside the card;
  * no text touches the close button;
  * message lines fit the message viewport width (no horizontal clipping) and
    the scroll region reaches the last line;
  * long notifications become scrollable instead of growing past the screen;
  * decorated themes: no text (title, chips, footer) and no part of the white
    message card sits on frame ornaments / border pixels of the frame image the
    bubble actually drew;
  * decorated frames are never squashed: scaled uniformly to the card width,
    the rows above / below the stretch band are pixel-identical to that scale;
  * the frame art itself is usable: one single card, transparent outside the
    frame, and the stretch band / safe area contain no ornaments.

Plus the C7 notification behaviour: > 80 characters stay 8..10 s, hovering
pauses the countdown, leaving resumes it, and titles are just "✦ <full name>".

Needs a real Tk display.  Run:  python tests/test_long_notification_bubble.py
(or  python -m unittest tests.test_long_notification_bubble -v)
"""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:  # same DPI mode as the real app (main.py)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from PIL import Image, ImageChops  # noqa: E402

from app.bubble import RESUME_MIN_MS, KawaiiSpeechBubble, effective_duration_ms  # noqa: E402
from app.bubble_themes import THEMES  # noqa: E402
from app.i18n import t  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402
from app.sprite_polish import alpha_bleed, defringe_light_frame  # noqa: E402

ORNAMENT_DIST = 60         # RGB distance from the card interior colour = ornament / border
MAX_ORNAMENT_SHARE = 0.02  # at most 2 % of a text box may sit on ornament pixels

HEADERS = {"zh_TW": "✦ 吳夏榮", "ko": "✦ 오하영", "en": "✦ Oh Hayoung"}
CHIPS = {
    "zh_TW": "【專屬互動｜久坐提醒｜11 月 6 日】",
    "ko": "【전용 인터랙션｜장시간 앉음 알림】",
    "en": "【Exclusive｜Sedentary reminder｜Nov 6】",
}
FOOTER = {
    "zh_TW": "🍠 夏榮 ‧ 2026-11-06 01:00",
    "ko": "🍠 하영 ‧ 2026-11-06 01:00",
    "en": "🍠 Hayoung ‧ 2026-11-06 01:00",
}
BASE = {
    "zh_TW": "今天也是元氣滿滿的一天！記得喝水、伸展一下，Panda 們會一直陪著你喔～🐼💕",
    "ko": "오늘도 힘내요! 물 마시고 스트레칭도 잊지 마세요. 판다들이 항상 곁에 있을게요~ 🐼💕",
    "en": "Stay hydrated and stretch a little! The pandas will always be right here with you~ 🐼💕",
}
LONG_WORD = "https://www.youtube.com/@Apink_official/videos?feature=supercalifragilistic"


def messages(lang: str) -> dict[str, str]:
    return {
        "short": BASE[lang][:12],
        "medium": " ".join([BASE[lang]] * 3),
        "very_long": "\n".join([BASE[lang]] * 14 + [LONG_WORD]),
    }


def _rgb_dist(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


def _ornament_share(img: Image.Image, box, interior) -> float:
    """Share of pixels inside ``box`` (in img coords) that are not plain interior."""
    x1, y1, x2, y2 = (max(0, round(v)) for v in box)
    x2, y2 = min(img.width, x2), min(img.height, y2)
    if x2 <= x1 or y2 <= y1:
        return 1.0  # entirely outside the card art: certainly not on the interior
    px = list(img.crop((x1, y1, x2, y2)).convert("RGBA").getdata())
    bad = sum(1 for p in px if p[3] < 255 or _rgb_dist(p, interior) > ORNAMENT_DIST)
    return bad / len(px)


def _intersects(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class _Render:
    """Rendered bubble + the geometry we need, in outer-canvas coordinates."""

    def __init__(self, root: tk.Tk, theme_key: str, lang: str, message: str) -> None:
        self.theme = THEMES[theme_key]
        # Pet near the bottom of the primary screen -> bubble above it (offset 0).
        sh = root.winfo_screenheight()
        self.b = KawaiiSpeechBubble(
            root, 600, sh - 300, 192, HEADERS[lang], message,
            sub_badge=CHIPS[lang], badge_text=FOOTER[lang],
            duration_ms=60_000, theme=self.theme,
        )
        root.update()
        b, c = self.b, self.b.canvas
        self.w, self.h = b.width, b.height
        self.art = b.card_image
        ox, oy = b.card_origin
        if self.art is not None:
            self.card = (ox, oy, ox + self.art.width, oy + self.art.height)
            self.interior = b.frame.interior
        else:
            self.card = (6, oy, self.w - 6, b.content_height - 24)
        self.origin = (ox, oy)
        self.close_box = c.bbox("close_btn")
        win_items = [i for i in c.find_all() if c.type(i) == "window"]
        msg_item = next(i for i in win_items if c.itemcget(i, "window") == str(b.message_canvas))
        self.viewport = c.bbox(msg_item)
        mc = b.message_canvas
        self.msg_w = int(mc.cget("width"))
        self.msg_scroll_h = float(str(mc.cget("scrollregion")).split()[3])
        self.msg_items = [mc.bbox(i) for i in mc.find_all() if mc.type(i) in ("text", "image")]
        skip_images = {str(getattr(b, "_bg_photo", "")), str(b.icon_thumb or "")}
        self.outer_texts = []
        for i in c.find_all():
            kind = c.type(i)
            if kind == "text":
                self.outer_texts.append((c.itemcget(i, "text"), c.bbox(i)))
            elif kind == "image" and c.itemcget(i, "image") not in skip_images:
                self.outer_texts.append(("<emoji>", c.bbox(i)))

    def close(self) -> None:
        self.b.dismiss()


class BubbleLayoutTest(unittest.TestCase):
    """Every check sees the same rendered cases (rendered once, measured, closed)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.cases = []
        for theme_key in THEMES:
            for lang in HEADERS:
                for length, msg in messages(lang).items():
                    r = _Render(cls.root, theme_key, lang, msg)
                    r.close()  # all geometry was captured in _Render.__init__
                    cls.cases.append((f"{theme_key}/{lang}/{length}", r, length))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def test_81_cases_rendered(self) -> None:
        self.assertEqual(len(self.cases), len(THEMES) * 3 * 3)
        framed = [name for name, r, _ in self.cases if r.art is not None]
        self.assertEqual(len(framed), 8 * 3 * 3, "every decorated theme must render its frame")

    def test_text_inside_window_and_card(self) -> None:
        for name, r, _ in self.cases:
            with self.subTest(case=name):
                for text, box in r.outer_texts:
                    self.assertTrue(0 <= box[0] and box[2] <= r.w and 0 <= box[1] and box[3] <= r.h,
                                    f"{text!r} {box} outside window {r.w}x{r.h}")
                    cx1, cy1, cx2, cy2 = r.card
                    self.assertTrue(cx1 <= box[0] and box[2] <= cx2 and cy1 <= box[1] and box[3] <= cy2,
                                    f"{text!r} {box} outside card {r.card}")
                    self.assertFalse(_intersects(box, r.close_box), f"{text!r} {box} under close button")

    def test_message_never_clipped(self) -> None:
        for name, r, length in self.cases:
            with self.subTest(case=name):
                for box in r.msg_items:
                    self.assertLessEqual(box[2], r.msg_w, f"message line {box} wider than viewport {r.msg_w}")
                bottom = max(b[3] for b in r.msg_items)
                self.assertGreaterEqual(r.msg_scroll_h + 2, bottom, "last line not reachable by scrolling")
                self.assertLessEqual(r.h, self.root.winfo_screenheight() - 20)
                if length == "very_long":
                    self.assertTrue(r.b.scrollable, "very long notification must scroll, not grow")
                if length == "short":
                    self.assertFalse(r.b.scrollable)

    def test_frame_never_squashed(self) -> None:
        """Uniform scale to the card width; only the stretch band may grow."""
        for name, r, _ in self.cases:
            if r.art is None:
                continue
            with self.subTest(case=name):
                layout = r.b.frame
                geo = layout.geometry(r.art.width, 0)
                self.assertGreaterEqual(r.art.height, geo.height, "card shorter than the scaled frame")
                with Image.open(r.theme.get_nine_slice_path()) as src:
                    scaled = alpha_bleed(src.convert("RGBA")).resize((geo.width, geo.height), Image.Resampling.LANCZOS)
                scaled.putalpha(scaled.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
                scaled = defringe_light_frame(scaled)
                w = geo.width
                mid = w // 2
                shift = 0 if layout.right_cut is None else round((layout.right_cut - layout.band[0]) * geo.scale)
                regions = (
                    ("top", (0, 0, w, geo.cap_top), (0, 0, w, geo.cap_top)),
                    ("bottom", (0, geo.height - geo.cap_bottom, w, geo.height),
                     (0, r.art.height - geo.cap_bottom, w, r.art.height)),
                ) if shift == 0 else (
                    ("top-left", (0, 0, mid, geo.cap_top), (0, 0, mid, geo.cap_top)),
                    ("top-right", (mid, 0, w, geo.cap_top + shift), (mid, 0, w, geo.cap_top + shift)),
                    ("bottom-left", (0, geo.height - geo.cap_bottom, mid, geo.height),
                     (0, r.art.height - geo.cap_bottom, mid, r.art.height)),
                    ("bottom-right", (mid, geo.height - geo.cap_bottom + shift, w, geo.height),
                     (mid, r.art.height - geo.cap_bottom + shift, w, r.art.height)),
                )
                for label, src_box, out_box in regions:
                    diff = ImageChops.difference(scaled.crop(src_box), r.art.crop(out_box))
                    self.assertEqual(max(hi for _, hi in diff.getextrema()), 0, f"{label} decoration deformed")

    def test_text_not_on_ornaments(self) -> None:
        for name, r, _ in self.cases:
            if r.art is None:
                continue
            with self.subTest(case=name):
                ox, oy = r.origin
                boxes = [(t, b) for t, b in r.outer_texts] + [("<message card>", r.viewport)]
                offenders = []
                for text, (x1, y1, x2, y2) in boxes:
                    share = _ornament_share(r.art, (x1 - ox, y1 - oy, x2 - ox, y2 - oy), r.interior)
                    if share > MAX_ORNAMENT_SHARE:
                        offenders.append(f"{text!r}@{(x1, y1, x2, y2)}={share:.0%}")
                self.assertEqual(offenders, [], "text / message card on frame ornaments")


class NineSliceArtTest(unittest.TestCase):
    """The source PNGs must be usable as decorated frames at all."""

    def arts(self):
        out = []
        for key, theme in THEMES.items():
            path = theme.get_nine_slice_path()
            if path is not None:
                with Image.open(path) as src:
                    out.append((key, path, src.convert("RGBA")))
        return out

    def test_single_card_per_file(self) -> None:
        for name, _, im in self.arts():
            with self.subTest(theme=name):
                # A sheet with two cards stacked vertically is taller than wide.
                self.assertLess(im.height / im.width, 0.8, f"{im.size}: looks like a multi-card sheet")

    def test_outside_of_frame_is_transparent(self) -> None:
        for name, _, im in self.arts():
            with self.subTest(theme=name):
                corners = [im.getpixel(p)[3] for p in
                           ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1))]
                self.assertEqual(corners, [0, 0, 0, 0],
                                 "opaque corners show as white squares on the desktop (colour-key window)")

    def test_stretched_edges_have_no_ornaments(self) -> None:
        """Only the band strip is stretched (along y): it must be ornament-free and alike."""
        for name, _, im in self.arts():
            with self.subTest(theme=name):
                layout = THEMES[name].frame_layout()
                x0, y0, x1, y1 = layout.safe
                b0, b1 = layout.band
                self.assertTrue(0 < b0 < b1 < im.height, f"band {layout.band} outside the frame")
                strip = layout.band_strip(im)
                # The strip extends the text area, so it must be plain across it.
                share = _ornament_share(strip, (x0, 0, x1, strip.height), layout.interior)
                self.assertLessEqual(share, MAX_ORNAMENT_SHARE, f"band has {share:.0%} ornament pixels")
                px = strip.load()
                bad = sum(1 for y in range(strip.height) for x in range(strip.width)
                          if _rgb_dist(px[x, y], px[x, 0]) > ORNAMENT_DIST or px[x, y][3] != px[x, 0][3])
                self.assertLessEqual(bad / (strip.width * strip.height), 0.05,
                                     "band rows differ: stretching smears them")

    def test_safe_area_is_plain(self) -> None:
        for name, path, im in self.arts():
            with self.subTest(theme=name):
                layout = THEMES[name].frame_layout()
                share = _ornament_share(im, layout.safe, layout.interior)
                self.assertLessEqual(share, MAX_ORNAMENT_SHARE, f"safe area {layout.safe}: {share:.0%} ornaments")
                width = layout.safe[2] - layout.safe[0]
                self.assertGreaterEqual(width, im.width * 0.55, "safe area too narrow for text")


class NotificationBehaviourTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)

    def test_dismiss_click_requires_press_and_release_on_the_bubble(self) -> None:
        closed = []
        bubble = KawaiiSpeechBubble(self.root, 500, 400, 192, "Notice", "Example",
                                    duration_ms=6000, on_close=lambda: closed.append(True))
        self.addCleanup(bubble.dismiss)
        self.root.update()
        widget = bubble.canvas
        x0, y0, x1, y1 = widget.bbox("close_btn")
        xy = {"x": (x0 + x1) // 2, "y": (y0 + y1) // 2}
        widget.event_generate("<ButtonRelease-1>", **xy)
        self.assertFalse(closed)
        widget.event_generate("<ButtonPress-1>", **xy)
        self.assertTrue(bubble.window.winfo_viewable())
        widget.event_generate("<ButtonRelease-1>", x=-10, y=-10)
        self.assertFalse(closed)
        widget.event_generate("<ButtonPress-1>", **xy)
        widget.event_generate("<ButtonRelease-1>", **xy)
        self.assertEqual(closed, [True])

    def test_long_text_stays_8_to_10_seconds(self) -> None:
        self.assertEqual(effective_duration_ms("字" * 80, 4200), 4200)
        self.assertEqual(effective_duration_ms("字" * 81, 4200), 8025)
        self.assertEqual(effective_duration_ms("字" * 500, 4200), 10000)
        self.assertEqual(effective_duration_ms("字" * 500, 15000), 15000)   # never shortened
        self.assertEqual(effective_duration_ms("a " * 80, 4200), 4200)      # spaces don't count

    def test_relay_styles_fit_safe_area_and_scroll_at_96_and_192_dpi(self) -> None:
        scaling = self.root.tk.call("tk", "scaling")
        self.addCleanup(self.root.tk.call, "tk", "scaling", scaling)
        area = WorkArea(0, 0, 1366, 728)
        desktop = mock.Mock()
        desktop.work_area_for_point.return_value = area
        for dpi in (96, 192):
            self.root.tk.call("tk", "scaling", dpi / 72)
            for theme_key in ("classic", "chorong_pink"):
                for lang in HEADERS:
                    for style in ("banner", "sticky", "standard"):
                        for long in (False, True):
                            with self.subTest(dpi=dpi, theme=theme_key, lang=lang, style=style, long=long):
                                message = (BASE[lang][:14] + "\r\n" + messages(lang)["very_long"] if long else
                                           t("windows_notif_privacy_msg", lang, app="Teams"))
                                chip = t("windows_notif_badge", lang)
                                bubble = KawaiiSpeechBubble(
                                    self.root, 600, 580, 144, HEADERS[lang], message,
                                    desktop=desktop, theme=THEMES[theme_key], duration_ms=60_000,
                                    sub_badge=f"{t('windows_notif_header', lang, app='Teams')}｜{chip}",
                                    notify_style=style, notify_tag=t("notify_sticky_tag", lang),
                                )
                                try:
                                    self.root.update()
                                    self._check_relay_layout(bubble, area, dpi, theme_key, style, long)
                                    outer_text = [bubble.canvas.itemcget(i, "text") for i in bubble.canvas.find_all()
                                                  if bubble.canvas.type(i) == "text"]
                                    self.assertIn(chip, outer_text)
                                finally:
                                    bubble.dismiss()

    def _check_relay_layout(self, bubble, area, dpi, theme_key, style, long) -> None:
        canvas, message = bubble.canvas, bubble.message_canvas
        self.assertAlmostEqual(bubble.ui_scale, dpi / 96, delta=0.02)
        self.assertEqual(bubble.card_image is not None, theme_key != "classic")
        self.assertEqual(bool(canvas.find_withtag("notify_badge")), style == "banner")
        self.assertEqual(bool(message.find_withtag("lead_band")), style == "banner" and long)
        self.assertEqual(bool(canvas.find_withtag("sticky_tag")), style == "sticky")
        self.assertEqual(bool(message.find_withtag("sticky_fold")), style == "sticky")
        if long:
            self.assertTrue(bubble.scrollable)
        bx, by = bubble.target_position
        self.assertLessEqual(bx + bubble.width, area.right)
        self.assertLessEqual(by + bubble.height, area.bottom)
        viewport = next(i for i in canvas.find_all() if canvas.type(i) == "window"
                        and canvas.itemcget(i, "window") == str(message))
        boxes = [canvas.bbox(viewport)]
        boxes.extend(canvas.bbox(tag) for tag in ("sticky_tag", "notify_badge") if canvas.find_withtag(tag))
        if bubble.card_image is not None:
            ox, oy = bubble.card_origin
            w, h = bubble.card_image.size
            geometry = bubble.frame.geometry(w, 0)
            x0, y0, x1, y1 = geometry.safe
            safe = (ox + x0, oy + y0, ox + x1, oy + y1 + h - geometry.height)
        else:
            safe = (0, 0, bubble.width, bubble.height)
        for x0, y0, x1, y1 in boxes:
            self.assertTrue(safe[0] - 1 <= x0 < x1 <= safe[2] + 1 and safe[1] <= y0 < y1 <= safe[3],
                            (safe, (x0, y0, x1, y1)))
        text_boxes = [message.bbox(i) for i in message.find_all() if message.type(i) in ("text", "image")]
        viewport_width = message.winfo_width()
        text_bottom = max(box[3] for box in text_boxes)
        self.assertTrue(all(0 <= box[0] < box[2] <= viewport_width for box in text_boxes))
        if bubble.scrollable:
            message.event_generate("<MouseWheel>", delta=-120)
            self.assertGreater(message.yview()[0], 0)
            message.yview_moveto(1)
            self.assertEqual(message.yview()[1], 1)
        self.assertLessEqual(text_bottom, message.canvasy(message.winfo_height()))
        if style == "sticky":
            self.assertLess(text_bottom, message.bbox("sticky_fold")[1])

    def test_hover_pauses_and_leave_resumes(self) -> None:
        for theme in ("classic", "hayoung_yellow"):
            with self.subTest(theme=theme):
                closed = []
                b = KawaiiSpeechBubble(self.root, 600, 700, 192, "✦ 吳夏榮", "滑鼠移上來就不會消失",
                                       duration_ms=300, theme=THEMES[theme], on_close=lambda: closed.append(1))
                self.addCleanup(b.dismiss)
                # Drive hover by hand: the real mouse may rest where the bubble appears.
                b.window.unbind("<Enter>")
                b.window.unbind("<Leave>")
                self.root.update()
                b._pause_timer()
                self.assertTrue(b.paused)
                self.pump(0.6)
                self.assertEqual(closed, [], "paused bubble must not time out")
                # Pointer still over the bubble (moving onto a child widget): stay paused.
                inside = (b.window.winfo_rootx() + 5, b.window.winfo_rooty() + 5)
                with mock.patch.object(b.window, "winfo_pointerxy", return_value=inside):
                    b._resume_timer()
                self.assertTrue(b.paused)
                with mock.patch.object(b.window, "winfo_pointerxy", return_value=(-99999, -99999)):
                    b._resume_timer()
                self.assertFalse(b.paused)
                self.pump(RESUME_MIN_MS / 1000 - 0.4)
                self.assertEqual(closed, [], "resumed bubble must stay readable a moment")
                self.pump(0.8)
                self.assertEqual(closed, [1])

    def test_title_is_only_the_member_name(self) -> None:
        from app.main import bubble_title
        self.assertEqual(bubble_title("", "", "chorong", "zh_TW"), ("✦ 朴初瓏", ""))
        self.assertEqual(bubble_title("🐼 初瓏 (Chorong)", "", "chorong", "zh_TW"), ("✦ 朴初瓏", ""))
        self.assertEqual(bubble_title("Apink 暖心語錄 💌", "", "bomi", "zh_TW"), ("✦ 尹普美", "暖心語錄 💌"))
        self.assertEqual(bubble_title("⏰ 夏榮 貼心提醒", "久坐", "hayoung", "zh_TW"),
                         ("✦ 吳夏榮", "⏰ 貼心提醒｜久坐"))
        self.assertEqual(bubble_title("🐼 하영", "", "hayoung", "ko"), ("✦ 오하영", ""))
        self.assertEqual(bubble_title("", "", "namjoo", "en"), ("✦ Kim Namjoo", ""))
        title, chips = bubble_title("🎂 普美生日快樂", "", "chorong", "zh_TW")
        self.assertEqual(chips, "🎂 普美生日快樂")  # someone else's name is kept
        self.assertNotIn("Apink", title)


if __name__ == "__main__":
    unittest.main(verbosity=2)
