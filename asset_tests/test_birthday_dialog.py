"""Headless tests for birthday_dialog parsing helpers.

Run:  python -m unittest tests.test_birthday_dialog -v
"""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.birthday_dialog import (  # noqa: E402
    BirthdayDialog,
    DEFAULT_NICKNAME,
    NICKNAME_MAX,
    clean_nickname,
    format_birthday,
    parse_birthday,
    read_birthday,
)


class TestBirthdayParsing(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(parse_birthday("3", "3"), (3, 3))
        self.assertEqual(parse_birthday(" 12 ", "31"), (12, 31))
        self.assertEqual(parse_birthday("2", "29"), (2, 29))  # leap-day birthdays allowed

    def test_invalid(self) -> None:
        for m, d in (("0", "1"), ("13", "1"), ("4", "31"), ("2", "30"), ("x", "1"), ("", "")):
            with self.assertRaises(ValueError, msg=(m, d)):
                parse_birthday(m, d)

    def test_round_trip(self) -> None:
        self.assertEqual(format_birthday(4, 19), "04-19")
        self.assertEqual(read_birthday("04-19"), (4, 19))
        self.assertEqual(format_birthday(None, None), "")
        for bad in ("", None, 419, "04/19", "13-01", "02-30"):
            self.assertIsNone(read_birthday(bad), bad)

    def test_nickname(self) -> None:
        self.assertEqual(clean_nickname("  小明  "), "小明")
        self.assertEqual(clean_nickname(""), DEFAULT_NICKNAME)
        self.assertEqual(len(clean_nickname("x" * 50)), NICKNAME_MAX)

    def test_rounded_card_dialog_widget_and_flow(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            saved: list[tuple] = []
            dlg = BirthdayDialog(
                root, (4, 19), "粉熊瓏", on_save=lambda *a: saved.append(a), lang="zh_TW"
            )
            self.assertTrue(dlg.win.overrideredirect())
            self.assertIsInstance(dlg.canvas, tk.Canvas)
            self.assertEqual(dlg.month.get(), "4")
            self.assertEqual(dlg.day.get(), "19")
            self.assertEqual(dlg.nickname.get(), "粉熊瓏")

            # Invalid date keeps dialog open and populates error text
            dlg.month.delete(0, "end")
            dlg.month.insert(0, "2")
            dlg.day.delete(0, "end")
            dlg.day.insert(0, "30")
            dlg.save()
            self.assertEqual(saved, [])
            self.assertTrue(len(dlg.error.cget("text")) > 0)

            # Valid date saves and closes
            dlg.day.delete(0, "end")
            dlg.day.insert(0, "29")
            dlg.nickname.delete(0, "end")
            dlg.nickname.insert(0, "Panda")
            dlg.save()
            self.assertEqual(saved, [(2, 29, "Panda")])

            # Clear action
            dlg2 = BirthdayDialog(
                root, (8, 13), "普美熊", on_save=lambda *a: saved.append(a), lang="ko"
            )
            dlg2.clear()
            self.assertEqual(saved[-1], (None, None, "普美熊"))

            # Test live refresh theme preserves user inputs and switches theme/language
            dlg3 = BirthdayDialog(
                root, (3, 3), "初瓏粉", on_save=lambda *a: saved.append(a), lang="zh_TW", member_key="chorong"
            )
            dlg3.month.delete(0, "end")
            dlg3.month.insert(0, "8")
            dlg3.day.delete(0, "end")
            dlg3.day.insert(0, "18")
            dlg3.nickname.delete(0, "end")
            dlg3.nickname.insert(0, "恩地大主唱")

            dlg3.refresh_theme("eunji", lang="ko")
            self.assertEqual(dlg3.member_key, "eunji")
            self.assertEqual(dlg3.lang, "ko")
            self.assertEqual(dlg3.month.get(), "8")
            self.assertEqual(dlg3.day.get(), "18")
            self.assertEqual(dlg3.nickname.get(), "恩地大主唱")
            self.assertEqual(dlg3.tx["title"], "내 생일 설정")
            dlg3.close()
        finally:
            root.destroy()

    def test_edge_fringe_cleanup_verified(self) -> None:
        from PIL import Image
        from tools.clean_edge_fringe import CHAR_DIR, find_edge_fringe_components

        for rel in (
            "bomi/situational_all1/bomi_walk_wink.png",
            "hayoung/situational_all1/hayoung_sleep_sit.png",
            "namjoo/actions_v7/namjoo_heart_cheer.png",
            "chorong/sleep_01.png",
        ):
            with Image.open(CHAR_DIR / rel) as im:
                fringe, _ = find_edge_fringe_components(im)
                self.assertEqual(fringe, [], f"Expected 0 fringe components in {rel}")

        # Verify Eunji singing mic keeps its left-side floating music note (non-zero alpha in x=8..24, y=68..94)
        with Image.open(CHAR_DIR / "eunji/situational_all1/eunji_sing_mic.png") as im:
            crop = im.convert("RGBA").crop((8, 68, 24, 94)).getchannel("A")
            self.assertIsNotNone(crop.getbbox())

    def test_dialog_normal_state_when_parent_visible_or_withdrawn(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            pet_win = tk.Toplevel(root)
            pet_win.deiconify()
            dlg = BirthdayDialog(pet_win, (4, 19), "Panda", lambda m, d, n: None)
            self.assertEqual(dlg.win.state(), "normal")
            self.assertTrue(dlg.win.winfo_exists())
            dlg.close()
            pet_win.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
