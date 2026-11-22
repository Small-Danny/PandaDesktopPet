"""Clicking "greet" on the profile card must leave the greeting bubble above the card.

Run:  python -m unittest tests.test_profile_card_bubble -v
"""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import PandaPet  # noqa: E402
from app.profile_card import MemberProfileCard  # noqa: E402


def _pump(root: tk.Tk, n: int = 10) -> None:
    for _ in range(n):
        root.update()
        time.sleep(0.02)


@unittest.skipUnless(sys.platform == "win32", "z-order is checked with Win32")
class GreetBubbleZOrderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.pet = tk.Toplevel(self.root)
        self.pet.overrideredirect(True)
        self.pet.attributes("-topmost", True)
        self.pet.geometry("60x60+5+900")

    def _bubble(self) -> tk.Toplevel:
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        b.geometry("300x150+750+300")
        b.update()                       # mapped before the click handler returns, like the real bubble
        return b

    def _higher(self, a: tk.Toplevel, b: tk.Toplevel) -> tk.Toplevel:
        user32 = ctypes.windll.user32
        ha, hb = (int(w.wm_frame(), 16) for w in (a, b))
        h = user32.GetTopWindow(0)
        while h:
            if h in (ha, hb):
                return a if h == ha else b
            h = user32.GetWindow(h, 2)   # GW_HWNDNEXT
        self.fail("windows not found in z-order")

    def test_greet_click_does_not_raise_card_over_bubble(self) -> None:
        shown = {}
        card = MemberProfileCard(parent=self.pet, initial_member="bomi", lang="zh_TW",
                                 on_greeting=lambda *_: shown.setdefault("bubble", self._bubble()))
        _pump(self.root)
        x1, y1, x2, y2 = card.canvas.bbox("btn_greet")
        x, y = (x1 + x2) // 2, (y1 + y2) // 2
        card.canvas.event_generate("<Motion>", x=x, y=y)
        card.canvas.event_generate("<ButtonPress-1>", x=x, y=y)
        _pump(self.root)
        self.assertIn("bubble", shown)
        self.assertIs(self._higher(shown["bubble"], card.win), shown["bubble"])

    def test_dragging_elsewhere_still_raises_card(self) -> None:
        card = MemberProfileCard(parent=self.pet, initial_member="bomi", lang="zh_TW", on_greeting=None)
        _pump(self.root)
        other = self._bubble()
        card.canvas.event_generate("<Motion>", x=5, y=card.h // 2)
        card.canvas.event_generate("<ButtonPress-1>", x=5, y=card.h // 2)
        _pump(self.root)
        self.assertIs(self._higher(other, card.win), card.win)

    def test_pet_lifts_active_bubble(self) -> None:
        bubble_win = self._bubble()
        card = MemberProfileCard(parent=self.pet, initial_member="bomi", lang="zh_TW", on_greeting=None)
        card.win.lift()
        _pump(self.root)
        fake = types.SimpleNamespace(active_bubble=types.SimpleNamespace(window=bubble_win))
        PandaPet._lift_bubble(fake)
        _pump(self.root)
        self.assertIs(self._higher(bubble_win, card.win), bubble_win)
        PandaPet._lift_bubble(types.SimpleNamespace(active_bubble=None))   # no bubble: no error


if __name__ == "__main__":
    unittest.main()
