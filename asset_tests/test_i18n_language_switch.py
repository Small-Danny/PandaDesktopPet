"""B7: every visible string follows the chosen language (zh_TW / ko / en).

Checks the entry points the user saw in the wrong language: the manual sleep
line, storage error bubbles, hourly chime, standby screen texts, and that all
locale tables carry the same keys and placeholders.
"""
from __future__ import annotations

import datetime as dt
import re
import string
import time
import tkinter as tk
import types
import unittest
import unittest.mock as mock

from app.engine.calendar import SEDENTARY_LINES, CalendarScheduler
from app.engine.contracts import Clock
from app.i18n import LOCALES, MEMBER_SHORT_NAME_MAP, format_long_date, get_member_short_name, t
from app.main import PandaPet
from app.paths import resource_dir
from app.sprites import SpriteLibrary
from app.standby import PandaStandbyOverlay

LANGS = ("zh_TW", "ko", "en")
HAN = re.compile(r"[一-鿿]")          # Chinese characters
HANGUL = re.compile(r"[가-힯]")


def _placeholders(pattern: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(pattern) if field}


class _Clock(Clock):
    def __init__(self, now: dt.datetime) -> None:
        self._now = now

    def now(self) -> dt.datetime:
        return self._now

    def monotonic(self) -> float:
        return 0.0


class LocaleTableTest(unittest.TestCase):
    def test_every_key_in_every_language_with_same_placeholders(self) -> None:
        keys = set().union(*(set(table) for table in LOCALES.values()))
        for lang in LANGS:
            self.assertEqual(keys - set(LOCALES[lang]), set(), f"{lang} lacks keys")
        for key in sorted(keys):
            with self.subTest(key=key):
                expected = _placeholders(LOCALES["zh_TW"][key])
                for lang in LANGS:
                    self.assertTrue(LOCALES[lang][key].strip(), f"{lang}.{key} is empty")
                    self.assertEqual(_placeholders(LOCALES[lang][key]), expected, f"{lang}.{key}")

    def test_ko_and_en_texts_are_not_chinese(self) -> None:
        # Korean text may legitimately contain no Hangul (emoji, names), but never Chinese.
        for lang in ("en", "ko"):
            for key, text in LOCALES[lang].items():
                if key == "lang_switch":  # "🌐 Language / 語言 / 언어" lists every language on purpose
                    continue
                self.assertFalse(HAN.search(text), f"{lang}.{key}: {text}")

    def test_member_short_names_and_dates(self) -> None:
        for key in MEMBER_SHORT_NAME_MAP:
            self.assertTrue(HAN.search(get_member_short_name(key, "zh_TW")))
            self.assertTrue(HANGUL.search(get_member_short_name(key, "ko")))
            self.assertRegex(get_member_short_name(key, "en"), r"^[A-Z][a-z]+$")
        self.assertEqual(format_long_date(2026, 12, 30, 2, "zh_TW"), "2026 年 12 月 30 日 週三")
        self.assertEqual(format_long_date(2026, 12, 30, 2, "ko"), "2026년 12월 30일 수요일")
        self.assertEqual(format_long_date(2026, 12, 30, 2, "en"), "Wednesday, December 30, 2026")


class CalendarLanguageTest(unittest.TestCase):
    def test_hourly_chime_follows_language(self) -> None:
        expected = {"zh_TW": "下午 2 點", "ko": "오후 2시", "en": "2 PM"}
        for lang, fragment in expected.items():
            with self.subTest(lang=lang):
                sched = CalendarScheduler(clock=_Clock(dt.datetime(2026, 6, 1, 14, 0)),
                                          sedentary_interval_min=0, user_birthday=None)
                events = sched.poll_all_due_events("chorong", lang=lang)
                chimes = [e for e in events if e.kind == "calendar.chime.14"]
                self.assertEqual(len(chimes), 1)
                self.assertIn(fragment, chimes[0].payload["text"])

    def test_sedentary_lines_exist_per_language(self) -> None:
        self.assertEqual({len(v) for v in SEDENTARY_LINES.values()}, {4})
        for line in SEDENTARY_LINES["en"] + SEDENTARY_LINES["ko"]:
            self.assertFalse(HAN.search(line), line)


class PetEntryPointTest(unittest.TestCase):
    """Methods run on a stand-in ``self`` so no pet window is created."""

    def test_storage_errors_are_translated_when_shown(self) -> None:
        for lang, header in (("ko", "⚠ 설정 파일"), ("en", "⚠ Settings file")):
            with self.subTest(lang=lang):
                shown = []
                fake = types.SimpleNamespace(
                    lang=lang,
                    _persist_errors=[("persist_save_failed", "disk full")],
                    _toast=lambda msg, **kw: shown.append((msg, kw)),
                )
                PandaPet._report_persist_errors(fake)
                self.assertEqual(len(shown), 1)
                msg, kw = shown[0]
                self.assertEqual(msg, t("persist_save_failed", lang, error="disk full"))
                self.assertEqual(kw["header"], header)
                self.assertFalse(HAN.search(msg + kw["header"]))
                self.assertEqual(fake._persist_errors, [])

    def test_manual_sleep_line_uses_language(self) -> None:
        for lang in ("ko", "en"):
            with self.subTest(lang=lang):
                shown = []
                fake = types.SimpleNamespace(
                    lang=lang, char_key="bomi",
                    record_activity=lambda: None,
                    coord=types.SimpleNamespace(snapshot=lambda: types.SimpleNamespace(active=None)),
                    _set_ambient=lambda state: None,
                    _toast=lambda msg, **kw: shown.append(msg),
                )
                PandaPet.set_state(fake, "sleep", manual=True)
                self.assertEqual(len(shown), 1)
                self.assertFalse(HAN.search(shown[0]), shown[0])

    def test_short_names_follow_language(self) -> None:
        for lang in LANGS:
            fake = types.SimpleNamespace(lang=lang)
            names = PandaPet._member_short_names(fake)
            self.assertEqual(names, {k: get_member_short_name(k, lang) for k in MEMBER_SHORT_NAME_MAP})


class StandbyLanguageTest(unittest.TestCase):
    def test_standby_texts_follow_language(self) -> None:
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        sprites = SpriteLibrary(resource_dir()).load_member("bomi", root)
        names = {"ko": "보미", "en": "Bomi"}
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock:
            for lang in ("ko", "en"):
                with self.subTest(lang=lang):
                    ov = PandaStandbyOverlay(
                        parent=root, char_key="bomi", char_name=names[lang],
                        frames=sprites.frames, flipped_walk_frames=sprites.flipped("walk"),
                        passion_points=3480, companion_minutes=60, on_close=None,
                        lock_on_exit=True, show_panda_tags=True, scene="campfire", lang=lang,
                    )
                    # Human input must not dismiss the overlay while text is inspected.
                    ov.win.unbind("<Motion>")
                    ov.win.unbind("<ButtonPress>")
                    ov.win.unbind("<Key>")
                    end = time.time() + 0.6
                    while time.time() < end:
                        root.update()
                        time.sleep(0.01)
                    texts = [ov.canvas.itemcget(i, "text") for i in ov.canvas.find_all()
                             if ov.canvas.type(i) == "text"]
                    joined = "\n".join(texts)
                    self.assertFalse(HAN.search(joined), joined)
                    self.assertIn(t("standby_exit_hint", lang), joined)
                    self.assertIn(t("scene_campfire", lang), joined)
                    self.assertIn(names[lang], joined)
                    ov.lock_on_exit = False  # never lock the real workstation from a test
                    ov.handle_exit(None)
        lock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
