"""Hanbok Lunar New Year / Lantern / Mid-Autumn greetings (2026-11-22 user report: only New
Year's Day had one; these three toasted their menu title instead)."""
from __future__ import annotations

import re
import types
import unittest

from app.daily_actions import CHRISTMAS, LANTERN, LUNAR_NY, MID_AUTUMN_FESTIVAL, NEW_YEAR
from app.engine.contracts import MEMBER_KEYS
from app.festival_greetings import FESTIVAL_GREETINGS, PREVIEW_ACTION_FESTIVAL, festival_greeting
from app.main import PandaPet

HANGUL = re.compile(r"[가-힣]")
CJK = re.compile(r"[一-鿿]")


class FestivalGreetingTest(unittest.TestCase):
    def test_every_member_has_three_languages_for_each_festival(self) -> None:
        for fest in (LUNAR_NY, LANTERN, MID_AUTUMN_FESTIVAL):
            self.assertEqual(PREVIEW_ACTION_FESTIVAL[fest.action], fest.key)
            by_member = FESTIVAL_GREETINGS[fest.key]
            self.assertEqual(set(by_member), set(MEMBER_KEYS))
            for member in MEMBER_KEYS:
                lines = by_member[member]
                self.assertTrue(CJK.search(lines["zh_TW"]), (fest.key, member))
                self.assertTrue(HANGUL.search(lines["ko"]), (fest.key, member))
                self.assertFalse(CJK.search(lines["en"]) or HANGUL.search(lines["en"]), (fest.key, member))
            # Each member speaks in her own words.
            for lang in ("zh_TW", "ko", "en"):
                self.assertEqual(len({by_member[m][lang] for m in MEMBER_KEYS}), len(MEMBER_KEYS))

    def test_festivals_with_their_own_speech_are_untouched(self) -> None:
        self.assertIsNone(festival_greeting(NEW_YEAR.key, "chorong", "zh_TW"))
        self.assertIsNone(festival_greeting(CHRISTMAS.key, "chorong", "zh_TW"))
        self.assertEqual(festival_greeting(LANTERN.key, "nobody", "xx"),
                         FESTIVAL_GREETINGS[LANTERN.key]["chorong"]["zh_TW"])

    def test_preview_toasts_the_member_greeting_not_the_title(self) -> None:
        for fest in (LUNAR_NY, LANTERN, MID_AUTUMN_FESTIVAL):
            for member in MEMBER_KEYS:
                toasts = []
                fake = types.SimpleNamespace(
                    char_key=member, lang="ko", record_activity=lambda: None,
                    celebrate_together=lambda **kw: None,
                    _toast=lambda msg, **kw: toasts.append((msg, kw.get("header"))))
                PandaPet.preview_festival_event(fake, fest.action, "TITLE")
                self.assertEqual(toasts, [(FESTIVAL_GREETINGS[fest.key][member]["ko"], "TITLE")])


if __name__ == "__main__":
    unittest.main()
