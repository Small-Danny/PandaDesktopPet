"""test_verified_quotes.py — attributed quotes are retired from the runtime and the package."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.personalities import (  # noqa: E402
    VERIFIED_QUOTES,
    WARM_QUOTES,
    get_random_chat_quote,
    get_random_verified_quote,
)
from tools.runtime_manifest import RUNTIME_FILES, runtime_files  # noqa: E402

MEMBERS = ["chorong", "bomi", "eunji", "namjoo", "hayoung"]


class TestVerifiedQuotesRetired(unittest.TestCase):
    def test_no_attributed_quotes_are_loaded(self):
        self.assertEqual(VERIFIED_QUOTES, {})
        for m in MEMBERS:
            for lang in ["zh_TW", "ko", "en"]:
                self.assertIsNone(get_random_verified_quote(m, lang=lang))

    def test_runtime_lines_are_companion_lines_only(self):
        for m in MEMBERS:
            self.assertTrue(WARM_QUOTES[m])
            for q in WARM_QUOTES[m]:
                self.assertEqual(q.get("quote_category"), "COMPANION_LINE")
                self.assertNotIn("verification_status", q)
                self.assertNotIn("source", q)

    def test_package_does_not_carry_the_unverified_quote_file(self):
        self.assertNotIn("work/quotes_verified.json", RUNTIME_FILES)
        files = runtime_files(ROOT)
        self.assertIn("work/quotes.json", files)
        self.assertFalse([f for f in files if "quotes_verified" in f])
        shipped = (ROOT / "work" / "quotes.json").read_text(encoding="utf-8")
        for marker in ("SOURCE_NAMED_PENDING_URL", "VERIFIED_QUOTE"):
            self.assertNotIn(marker, shipped)

    def test_chat_quote_integration(self):
        for m in MEMBERS:
            for lang in ["zh_TW", "ko", "en"]:
                badge, quote = get_random_chat_quote(m, lang=lang)
                self.assertTrue(len(badge) > 0)
                self.assertTrue(len(quote) > 0)


if __name__ == "__main__":
    unittest.main()
