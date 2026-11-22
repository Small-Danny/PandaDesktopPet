"""tests/test_quotes_and_i18n_v13.py — Verification of Module L & Q (DEF-L01 / DEF-Q01).

Run:  python -m unittest tests.test_quotes_and_i18n_v13 -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.i18n import LOCALES  # noqa: E402
from app.personalities import (  # noqa: E402
    get_companion_line_badge,
    get_member_badge,
    get_random_chat_quote,
    get_random_verified_quote,
    get_random_warm_quote,
)

MEMBER_KEYS = ("chorong", "bomi", "eunji", "namjoo", "hayoung")
# 50 original lines each, plus the retired attributed quotes rewritten as companion lines (plus user additions).
EXPECTED_COUNTS = {"chorong": 62, "bomi": 61, "eunji": 64, "namjoo": 61, "hayoung": 61}


class QuotesAndI18nV13Test(unittest.TestCase):
    def test_english_new_year_preview_menu_label(self) -> None:
        self.assertEqual(LOCALES["en"]["preview_event_newyearseve"],
                         "🎆 New Year Countdown & Group Cheer")

    def test_quotes_json_is_309_companion_lines_without_duplicates(self) -> None:
        data = json.loads((ROOT / "work" / "quotes.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data), set(MEMBER_KEYS))
        for member in MEMBER_KEYS:
            self.assertEqual(len(data[member]), EXPECTED_COUNTS[member], member)
        entries = [item for member in MEMBER_KEYS for item in data[member]]
        self.assertEqual(len(entries), 309)
        self.assertTrue(any("truly magical and deeply moving" in item["en"] for item in entries))
        self.assertFalse(any("trulymagical" in item["en"] for item in entries))
        self.assertTrue(any("希望自己成為被需要的人" in item["zh"] and "不會讓你後悔喜歡上我" in item["zh"] for item in data["eunji"]))
        for item in entries:
            self.assertEqual(set(item), {"zh", "ko", "en", "quote_category"})
            self.assertEqual(item["quote_category"], "COMPANION_LINE")
            for lang in ("zh", "ko", "en"):
                self.assertTrue(item[lang].strip())
        for lang in ("zh", "ko", "en"):
            texts = [item[lang] for item in entries]
            self.assertEqual(len(texts), len(set(texts)), f"duplicate {lang} line")

    def test_chat_quotes_only_use_companion_or_hobby_badges(self) -> None:
        for member in MEMBER_KEYS:
            for lang in ("zh_TW", "ko", "en"):
                self.assertIsNone(get_random_verified_quote(member, lang))
                self.assertTrue(get_random_warm_quote(member, lang))
                allowed = {get_companion_line_badge(lang), get_member_badge(member, lang)}
                for _ in range(30):
                    badge, quote = get_random_chat_quote(member, lang)
                    self.assertIn(badge, allowed)
                    self.assertTrue(quote)
                    self.assertNotIn("🎙", badge)

    def test_i18n_locales_have_identical_keys(self) -> None:
        zh_keys = set(LOCALES["zh_TW"].keys())
        ko_keys = set(LOCALES["ko"].keys())
        en_keys = set(LOCALES["en"].keys())
        self.assertEqual(zh_keys, ko_keys)
        self.assertEqual(zh_keys, en_keys)


if __name__ == "__main__":
    unittest.main()
