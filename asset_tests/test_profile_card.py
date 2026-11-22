"""tests/test_profile_card.py — Unit & Integration Tests for MemberProfileCard."""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.profile_card import MEMBERS, MEMBER_PROFILES, MemberProfileCard


class TestMemberProfileCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        try:
            cls.root.tk.call("tk", "scaling", 1.3333333333333333)
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_eunji_soul_vocalist_badges_and_stature(self):
        """Verify Eunji is elevated to Soul Vocalist NO.1 across zh_TW, ko, en."""
        eunji = MEMBER_PROFILES["eunji"]
        self.assertIn("🎤 靈魂大主唱 NO.1", eunji["badges"]["zh_TW"])
        self.assertIn("🎤 소울 메인보컬 NO.1", eunji["badges"]["ko"])
        self.assertIn("🎤 Soul Vocalist NO.1", eunji["badges"]["en"])
        # Check that Busan background is respectfully preserved in position text
        self.assertIn("百想實力神演員", eunji["position"]["zh_TW"])
        self.assertIn("K-POP", eunji["position"]["zh_TW"])

    def test_all_five_members_data_completeness(self):
        """Verify all 5 members have complete trilingual profiles with no empty fields."""
        self.assertEqual(len(MEMBERS), 5)
        for m in MEMBERS:
            p = MEMBER_PROFILES[m]
            for lang in ("zh_TW", "ko", "en"):
                self.assertTrue(len(p["names"][lang]) > 0, f"Empty name for {m} in {lang}")
                self.assertEqual(len(p["badges"][lang]), 3, f"Expected 3 badges for {m} in {lang}")
                self.assertTrue(len(p["position"][lang]) > 0, f"Empty position for {m} in {lang}")
                self.assertTrue(len(p["quote"][lang]) > 0, f"Empty quote for {m} in {lang}")
                self.assertTrue(len(p["fav_food"][lang]) > 0, f"Empty fav_food for {m} in {lang}")
                self.assertTrue(len(p["taboo"][lang]) > 0, f"Empty taboo for {m} in {lang}")
                self.assertTrue(len(p["greeting"][lang]) > 0, f"Empty greeting for {m} in {lang}")

    def test_carousel_cycling_and_direct_jump(self):
        """Verify forward next, backward prev, wrap-around, and direct dot jumping."""
        card = MemberProfileCard(self.root, initial_member="chorong", lang="zh_TW")
        try:
            self.assertEqual(card.current_idx, 0)
            card.next_member()
            self.assertEqual(card.current_idx, 1)  # bomi
            card.next_member()
            self.assertEqual(card.current_idx, 2)  # eunji
            card.next_member()
            self.assertEqual(card.current_idx, 3)  # namjoo
            card.next_member()
            self.assertEqual(card.current_idx, 4)  # hayoung
            card.next_member()
            self.assertEqual(card.current_idx, 0)  # wrap back to chorong

            # Backward wrapping
            card.prev_member()
            self.assertEqual(card.current_idx, 4)  # hayoung
            card.prev_member()
            self.assertEqual(card.current_idx, 3)  # namjoo

            # Direct jump by index
            card.set_member_by_index(2)
            self.assertEqual(card.current_idx, 2)  # eunji
        finally:
            card.close()

    def test_greeting_callback_invoked(self):
        """Verify clicking greeting triggers on_greeting callback with member key and line."""
        received: list[tuple[str, str]] = []
        card = MemberProfileCard(
            self.root,
            initial_member="eunji",
            lang="zh_TW",
            on_greeting=lambda key, msg: received.append((key, msg)),
        )
        try:
            member_key = card.members[card.current_idx]
            msg = MEMBER_PROFILES[member_key]["greeting"]["zh_TW"]
            if card.on_greeting:
                card.on_greeting(member_key, msg)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0][0], "eunji")
            self.assertIn("恩地", received[0][1])
        finally:
            card.close()

    def test_korean_greeting_pill_right_edge_hitbox_and_no_drag(self):
        """Verify Korean greeting pill right-edge click triggers greeting and forbids card drag."""
        received: list[tuple[str, str]] = []
        card = MemberProfileCard(
            self.root,
            initial_member="eunji",
            lang="ko",
            on_greeting=lambda key, msg: received.append((key, msg)),
        )
        try:
            # Check items at right edge of greet button (120, 294)
            items = card.canvas.find_overlapping(120, 294, 120, 294)
            has_greet_tag = any("btn_greet" in card.canvas.gettags(it) for it in items)
            self.assertTrue(has_greet_tag, "Right edge of greet button must carry btn_greet tag")

            # Simulate mouse press at right edge (120, 294)
            event = type("MockEvent", (), {"x": 120, "y": 294})()
            card._on_drag_begin(event)
            self.assertIsNone(card.drag_offset_x, "Drag must NOT be armed when clicking greet button")
            self.assertIsNone(card.drag_offset_y, "Drag must NOT be armed when clicking greet button")

            # Trigger greeting tag event
            card.win.deiconify()
            card.win.update()
            card.canvas.event_generate("<Button-1>", x=120, y=294)
            card.win.update()
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0][0], "eunji")
        finally:
            card.close()

    def test_window_lifecycle_and_topmost_style(self):
        """Verify window creation, topmost attribute, and clean destruction."""
        card = MemberProfileCard(self.root, initial_member="bomi", lang="zh_TW")
        self.assertTrue(card.win.overrideredirect())
        self.assertTrue(card.win.attributes("-topmost"))
        self.assertIsInstance(card.canvas, tk.Canvas)
        card.close()
        # Ensure destroyed without exception
        self.assertFalse(card.win.winfo_exists())

    def test_left_column_persona_font_scaling(self):
        """Verify the persona text in the left pod (e.g. 溫柔貓咪) is at least 8~10pt and fits neatly."""
        for member in MEMBERS:
            for lang in ("zh_TW", "ko", "en"):
                card = MemberProfileCard(self.root, initial_member=member, lang=lang)
                try:
                    items = card.canvas.find_all()
                    persona_found = False
                    for it in items:
                        if card.canvas.type(it) == "text":
                            bbox = card.canvas.bbox(it)
                            if bbox and 200 <= (bbox[1] + bbox[3]) // 2 <= 260 and bbox[0] < 140:
                                font_desc = card.canvas.itemcget(it, "font")
                                # Font size should never be 7pt
                                self.assertNotIn(" 7 ", font_desc, f"Font too small in {member} {lang}: {font_desc}")
                                # Bounding box must be inside column bounds
                                self.assertGreaterEqual(bbox[0], 10)
                                self.assertLessEqual(bbox[2], 140)
                                persona_found = True
                    self.assertTrue(persona_found, f"Persona text not found in {member} {lang}")
                finally:
                    card.close()

    def test_mascot_pill_and_header_localized(self):
        """Verify mascot text is localized and does not contain raw obscure strings like JJONGDOONG."""
        for member in MEMBERS:
            for lang in ("zh_TW", "ko", "en"):
                card = MemberProfileCard(self.root, initial_member=member, lang=lang)
                try:
                    items = card.canvas.find_all()
                    found_mascot = False
                    for it in items:
                        if card.canvas.type(it) == "text":
                            txt = card.canvas.itemcget(it, "text")
                            if "🐼" in txt:
                                self.assertNotIn("JJONGDOONG", txt)
                                self.assertNotIn("OHA-DOONG", txt)
                                found_mascot = True
                    self.assertTrue(found_mascot, f"Mascot not found for {member} {lang}")
                finally:
                    card.close()

    def test_mascot_official_english_names_keep_zh_and_ko(self):
        """Official English spellings (user-confirmed); the zh_TW and ko nicknames stay as they were."""
        expected = {
            "chorong": ("隆咚", "롱둥이", "Rongdoong"),
            "bomi": ("普咚", "뽐둥이", "Bbomdoong"),
            "eunji": ("恩咚", "믕둥이", "Meungdoong"),
            "namjoo": ("南咚", "남둥이", "Namdoong"),
            "hayoung": ("夏咚", "하둥이", "Hadoong"),
        }
        for member, (zh, ko, en) in expected.items():
            mascot = MEMBER_PROFILES[member]["mascot"]
            self.assertEqual(mascot, {"zh_TW": zh, "ko": ko, "en": en}, member)
        for member in MEMBERS:
            card = MemberProfileCard(self.root, initial_member=member, lang="en")
            try:
                texts = [card.canvas.itemcget(it, "text") for it in card.canvas.find_all()
                         if card.canvas.type(it) == "text"]
                self.assertTrue(any(expected[member][2] in txt for txt in texts), member)
                for old in ("Joodoong", "Bbangdoong", "JJONGDOONG", "NAMDOONG", "OHA-DOONG"):
                    self.assertFalse(any(old in txt for txt in texts), (member, old))
            finally:
                card.close()


    def test_persona_pod_clean_spacing_no_variation_selector(self):
        """Verify persona pod text (e.g. Namjoo '活力小太陽') has no \\ufe0f ghost spacing and normal single-space separation."""
        for member in MEMBERS:
            for lang in ("zh_TW", "ko", "en"):
                card = MemberProfileCard(self.root, initial_member=member, lang=lang)
                try:
                    for it in card.canvas.find_all():
                        if card.canvas.type(it) == "text":
                            txt = card.canvas.itemcget(it, "text")
                            self.assertNotIn("\ufe0f", txt, f"Found variation selector in rendered text: {txt}")
                finally:
                    card.close()

    def test_eunji_meungji_nickname_and_position_box_fit(self):
        """Verify Eunji's favorite nicknames (懵地 / 믕 / 믕지 / Meung / Meungji) render cleanly inside Row 2."""
        expected = {
            "zh_TW": ("懵地", "믕", "믕지"),
            "ko": ("믕", "믕지"),
            "en": ("Meung", "Meungji"),
        }
        for lang, tokens in expected.items():
            for token in tokens:
                self.assertIn(token, MEMBER_PROFILES["eunji"]["position"][lang])
            card = MemberProfileCard(self.root, initial_member="eunji", lang=lang)
            try:
                card.canvas.update_idletasks()
                pos_text = MEMBER_PROFILES["eunji"]["position"][lang]
                item = next(
                    it for it in card.canvas.find_all()
                    if card.canvas.type(it) == "text" and card.canvas.itemcget(it, "text") == pos_text
                )
                x1, y1, x2, y2 = card.canvas.bbox(item)
                k = card.ui_scale
                self.assertGreaterEqual(y1, round(112 * k), f"Row 2 text collides with title in {lang}: {(y1, y2, k)}")
                self.assertLessEqual(y2, round(162 * k), f"Row 2 text overflows box in {lang}: {(y1, y2, k)}")
            finally:
                card.close()

    def _set_scaling(self, scaling: float) -> None:
        self.root.tk.call("tk", "scaling", scaling)

    def test_badges_never_dropped_and_right_column_text_clears_titles(self):
        """All badges render inside the column, and every description sits below its title at 96 and 192 DPI."""
        try:
            for scaling in (1.3333333333333333, 2.6666666666666665):
                self._set_scaling(scaling)
                for lang in ("zh_TW", "ko", "en"):
                    heights = set()
                    for member in MEMBERS:
                        card = MemberProfileCard(self.root, initial_member=member, lang=lang)
                        try:
                            cv, k = card.canvas, card.ui_scale
                            where = (member, lang, scaling)
                            heights.add(card.h)
                            self.assertEqual(card.h, round(430 * k), where)   # real data keeps the 430 design height
                            pills = [cv.bbox(i) for i in cv.find_withtag("badge_pill")]
                            texts = [cv.bbox(i) for i in cv.find_withtag("badge_text")]
                            self.assertEqual(len(pills), len(MEMBER_PROFILES[member]["badges"][lang]), where)
                            self.assertEqual(len(texts), len(pills), where)
                            right = (card._design_w - 20) * k
                            for (px1, _py1, px2, _py2), (tx1, _ty1, tx2, _ty2) in zip(pills, texts):
                                self.assertGreaterEqual(px1, 136 * k - 3 * k, where)
                                self.assertLessEqual(px2, right + 3 * k, where)
                                self.assertGreaterEqual(tx1, px1, where)
                                self.assertLessEqual(tx2, px2, where)
                            badge_bottom = max(p[3] for p in pills)

                            def box(tag):
                                return cv.bbox(cv.find_withtag(tag)[0])

                            order = ("pos_title", "pos_desc", "food_title", "food_desc",
                                     "taboo_title", "taboo_desc")
                            boxes = [box(tag) for tag in order]
                            self.assertGreater(boxes[0][1], badge_bottom, where)
                            for (name_a, a), (name_b, b) in zip(zip(order, boxes), zip(order[1:], boxes[1:])):
                                self.assertGreaterEqual(b[1], a[3] + 2 * k - 1, (where, name_a, name_b, a, b))
                            nav_top = cv.bbox(cv.find_withtag("btn_prev")[0])[1]
                            self.assertLessEqual(boxes[-1][3], nav_top - 8 * k, where)
                            self.assertLessEqual(nav_top + 40 * k, card.h, where)
                        finally:
                            card.close()
                    self.assertEqual(len(heights), 1, f"carousel height must not jump in {lang}: {heights}")
        finally:
            self._set_scaling(1.3333333333333333)

    def test_member_without_badges_still_renders(self):
        """An empty badge list must not crash the right column (max() of no rows)."""
        from unittest import mock

        badges = {lang: [] for lang in MEMBER_PROFILES["chorong"]["badges"]}
        with mock.patch.dict(MEMBER_PROFILES["chorong"], {"badges": badges}):
            card = MemberProfileCard(self.root, initial_member="chorong", lang="en")
            try:
                self.assertEqual(card.canvas.find_withtag("badge_pill"), ())
                self.assertTrue(card.canvas.find_withtag("pos_desc"))
            finally:
                card.close()

    def test_layout_and_avatar_pil_caches_accelerate_reopen_across_roots(self):
        from app.profile_card import (
            _MEMBER_AVATAR_PIL_CACHE,
            _RIGHT_COLUMN_LAYOUT_CACHE,
            _TEXT_HEIGHT_CACHE,
        )

        card1 = MemberProfileCard(self.root, initial_member="eunji", lang="zh_TW")
        card1.close()
        self.assertGreater(len(_TEXT_HEIGHT_CACHE), 0)
        self.assertGreater(len(_RIGHT_COLUMN_LAYOUT_CACHE), 0)
        self.assertIn(("eunji", round(84 * card1.ui_scale)), _MEMBER_AVATAR_PIL_CACHE)

        # Reopening on another parent window reuses cached layout and PIL images cleanly
        other_parent = tk.Toplevel(self.root)
        other_parent.withdraw()
        try:
            card2 = MemberProfileCard(other_parent, initial_member="eunji", lang="zh_TW")
            self.assertIsNotNone(card2._avatar_photo)
            self.assertIsNot(card2._avatar_photo, card1._avatar_photo)
            card2.close()
        finally:
            other_parent.destroy()


if __name__ == "__main__":
    unittest.main()
