"""Greeting another member from the profile card: bubble at her card, the pet stays out of it.

Run:  python -m unittest tests.test_profile_greeting -v
"""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import Priority  # noqa: E402
from app.engine.speech_queue import SpeechQueue, SpeechRequest  # noqa: E402
from app.main import PandaPet  # noqa: E402


def _pet(member: str = "chorong", bounds=(700, 300, 84, 84)):
    toasts, cheers, after = [], [], []
    pet = types.SimpleNamespace(
        char_key=member, lang="zh_TW", speech=SpeechQueue(),
        profile_card=types.SimpleNamespace(avatar_bounds=lambda: bounds),
        record_activity=lambda: None,
        trigger_cheer=lambda **kw: cheers.append(kw),
        _toast=lambda msg, **kw: toasts.append((msg, kw)) or True,
        _lift_bubble=lambda: None,
        root=types.SimpleNamespace(after_idle=lambda fn: None),
        window=types.SimpleNamespace(after=lambda ms, fn: after.append(fn)),
    )
    return pet, toasts, cheers, after


class GreetingTest(unittest.TestCase):
    def test_own_member_greets_from_the_pet(self) -> None:
        pet, toasts, cheers, _ = _pet("chorong")
        self.assertFalse(PandaPet._on_profile_greeting(pet, "chorong", "hi"))   # the pet greets, not the card
        msg, kw = toasts[0]
        self.assertNotIn("anchor", kw)
        self.assertNotIn("origin", kw)
        self.assertEqual(kw["speaker"], "chorong")
        self.assertEqual(cheers, [{"cycles": 2}])

    def test_other_member_greets_from_her_card(self) -> None:
        pet, toasts, cheers, _ = _pet("chorong")
        self.assertTrue(PandaPet._on_profile_greeting(pet, "eunji", "annyeong"))
        msg, kw = toasts[0]
        self.assertEqual(msg, "annyeong")
        self.assertEqual((kw["anchor"], kw["anchor_size"]), ((700, 300), (84, 84)))
        self.assertEqual(kw["origin"], "profile_card")
        self.assertEqual(kw["speaker"], "eunji")
        self.assertEqual(kw["priority"], Priority.USER)
        self.assertEqual(cheers, [])                      # Chorong does not cheer for Eunji

    def test_no_card_spot_no_bubble(self) -> None:
        pet, toasts, cheers, _ = _pet("chorong", bounds=None)
        self.assertFalse(PandaPet._on_profile_greeting(pet, "eunji", "x"))
        self.assertEqual((toasts, cheers), ([], []))
        pet.profile_card = None
        PandaPet._on_profile_greeting(pet, "eunji", "x")
        self.assertEqual(toasts, [])

    def test_not_queued_while_held(self) -> None:
        pet, toasts, _, _ = _pet("chorong")
        pet.speech.hold(True)
        self.assertFalse(PandaPet._on_profile_greeting(pet, "eunji", "x"))
        self.assertEqual(toasts, [])


class RenderAtCardTest(unittest.TestCase):
    def _pet(self, viewable: bool):
        window = mock.Mock()
        window.winfo_viewable.return_value = viewable
        coord = mock.Mock()
        pet = types.SimpleNamespace(
            window=window, coord=coord, x=10, y=20, width=192, height=240, lang="zh_TW",
            char_key="chorong", settings={}, tray=mock.Mock(), active_bubble=None,
            _close_bubble_window=lambda: None, ensure_topmost=lambda: None,
            _set_ambient=mock.Mock(), _on_bubble_closed=lambda b: None,
        )
        from app.engine.contracts import ActorState
        coord.snapshot.return_value = types.SimpleNamespace(ambient_state=ActorState.WALK)
        return pet

    def _render(self, pet, req):
        with mock.patch("app.main.KawaiiSpeechBubble") as bubble:
            PandaPet._render_bubble(pet, req)
        return bubble.call_args.kwargs

    def test_card_bubble_targets_the_avatar_and_leaves_the_pet(self) -> None:
        pet = self._pet(viewable=False)
        kw = self._render(pet, SpeechRequest("x", speaker="eunji", anchor=(700, 300),
                                             anchor_size=(84, 84), origin="profile_card"))
        self.assertEqual((kw["target_x"], kw["target_y"], kw["sprite_w"], kw["sprite_h"]), (700, 300, 84, 84))
        pet.window.deiconify.assert_not_called()          # pet in the tray stays there
        pet._set_ambient.assert_not_called()              # and keeps walking

    def test_pet_bubble_unchanged(self) -> None:
        pet = self._pet(viewable=False)
        kw = self._render(pet, SpeechRequest("x"))
        self.assertEqual((kw["target_x"], kw["target_y"], kw["sprite_w"], kw["sprite_h"]), (10, 20, 192, 240))
        pet.window.deiconify.assert_called_once()
        pet._set_ambient.assert_called_once_with("idle")

    def test_bad_anchor_size_falls_back_to_the_sprite(self) -> None:
        pet = self._pet(viewable=True)
        kw = self._render(pet, SpeechRequest("x", anchor=(1, 2), anchor_size=(0, 84), origin="profile_card"))
        self.assertEqual((kw["sprite_w"], kw["sprite_h"]), (192, 240))


class ContextChangedTest(unittest.TestCase):
    def _pet(self):
        pet, _, _, after = _pet()
        closed = []
        pet._dismiss_toast = lambda: (closed.append(1), pet.speech.closed())
        pet._pump_speech = "pump"
        return pet, closed, after

    def test_card_bubble_closes_and_an_interrupted_notice_returns(self) -> None:
        pet, closed, after = self._pet()
        notice = SpeechRequest("LINE", priority=Priority.SYSTEM, duration_ms=5000)
        pet.speech.offer(notice)
        pet.speech.offer(SpeechRequest("hi", origin="profile_card"))   # USER preempts, notice requeued
        PandaPet._on_profile_context_changed(pet)
        self.assertEqual(closed, [1])
        self.assertEqual(after, ["pump"])
        self.assertEqual(pet.speech.next_ready().text, "LINE")

    def test_other_bubbles_are_left_alone(self) -> None:
        for current in (None, SpeechRequest("LINE", priority=Priority.SYSTEM), SpeechRequest("fed")):
            pet, closed, after = self._pet()
            if current is not None:
                pet.speech.offer(current)
            with self.subTest(current=current):
                PandaPet._on_profile_context_changed(pet)
                self.assertEqual((closed, after), ([], []))
                self.assertIs(pet.speech.current, current)


@unittest.skipUnless(sys.platform == "win32", "z-order is checked with Win32")
class RealCardTest(unittest.TestCase):
    """The real profile card wired to the pet's greeting / context handlers."""

    def setUp(self) -> None:
        from app.profile_card import MemberProfileCard
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        # LIFO cleanup: cancel mock host.after(400, lambda) before root.destroy tears down Toplevel commands.
        self.addCleanup(self._cancel_pending_afters)
        host = tk.Toplevel(self.root)
        host.overrideredirect(True)
        host.geometry("60x60+5+900")
        shown = []

        def render(req):                       # a real topmost window where the bubble would be
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            x, y = req.anchor or (0, 0)
            win.geometry(f"200x80+{x}+{max(0, y - 90)}")
            win.update()
            pet.active_bubble = types.SimpleNamespace(window=win)
            shown.append(req)

        def dismiss():
            bubble, pet.active_bubble = pet.active_bubble, None
            if bubble is not None:
                bubble.window.destroy()
            pet.speech.closed()

        pet = types.SimpleNamespace(
            char_key="chorong", lang="zh_TW", speech=SpeechQueue(), active_bubble=None,
            record_activity=lambda: None, trigger_cheer=lambda **kw: self.fail("the pet cheered"),
            _render_bubble=render, _dismiss_toast=dismiss, _pump_speech=lambda: None,
            root=self.root, window=host,
        )
        for name in ("_toast", "_lift_bubble", "_on_profile_greeting", "_on_profile_context_changed"):
            setattr(pet, name, getattr(PandaPet, name).__get__(pet))
        pet.profile_card = MemberProfileCard(parent=host, initial_member="eunji", lang="zh_TW",
                                             on_greeting=pet._on_profile_greeting,
                                             on_context_change=pet._on_profile_context_changed)
        self.pet, self.card, self.shown = pet, pet.profile_card, shown
        self._pump()

    def _cancel_pending_afters(self) -> None:
        try:
            pending = self.root.tk.call("after", "info")
        except tk.TclError:
            return
        for aid in self.root.tk.splitlist(pending):
            try:
                # Cancel Tcl timer without desyncing child Toplevel._tclCommands prior to root.destroy().
                self.root.tk.call("after", "cancel", aid)
            except tk.TclError:
                pass

    def _pump(self) -> None:
        for _ in range(8):
            self.root.update()
            time.sleep(0.02)

    def _greet(self) -> None:
        cv = self.card.canvas
        x1, y1, x2, y2 = cv.bbox("btn_greet")
        x, y = (x1 + x2) // 2, (y1 + y2) // 2
        cv.event_generate("<Motion>", x=x, y=y)
        cv.event_generate("<ButtonPress-1>", x=x, y=y)
        cv.event_generate("<ButtonRelease-1>", x=x, y=y)
        self._pump()

    def _bubble_above_card(self) -> bool:
        user32 = ctypes.windll.user32
        hb, hc = (int(w.wm_frame(), 16) for w in (self.pet.active_bubble.window, self.card.win))
        h = user32.GetTopWindow(0)
        while h and h not in (hb, hc):
            h = user32.GetWindow(h, 2)   # GW_HWNDNEXT
        return h == hb

    def test_greeting_points_at_the_card_avatar_and_survives_the_click(self) -> None:
        self._greet()
        self.assertEqual(len(self.shown), 1)
        req = self.shown[0]
        self.assertEqual((req.origin, req.speaker), ("profile_card", "eunji"))
        x, y, w, h = self.card.avatar_bounds()
        self.assertEqual((req.anchor, req.anchor_size), ((x, y), (w, h)))
        self.assertIsNotNone(self.pet.active_bubble)      # the same click did not close it
        self.assertTrue(self._bubble_above_card())

    def test_page_switch_drag_and_close_take_the_greeting_away(self) -> None:
        for action in ("next", "drag", "close"):
            with self.subTest(action=action):
                self._greet()
                self.assertIsNotNone(self.pet.active_bubble)
                cv = self.card.canvas
                if action == "next":
                    self.card.next_member()
                    self.card.prev_member()               # back to Eunji for the next round
                elif action == "drag":
                    cv.event_generate("<ButtonPress-1>", x=5, y=self.card.h // 2)
                    cv.event_generate("<B1-Motion>", x=2, y=self.card.h // 2)     # under the threshold
                    self.assertIsNotNone(self.pet.active_bubble)
                    cv.event_generate("<B1-Motion>", x=40, y=self.card.h // 2)
                    cv.event_generate("<ButtonRelease-1>", x=40, y=self.card.h // 2)
                else:
                    self.card.close()
                self._pump()
                self.assertIsNone(self.pet.active_bubble)


if __name__ == "__main__":
    unittest.main()
