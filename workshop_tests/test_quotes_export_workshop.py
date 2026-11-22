"""The 58 verified quotes' markdown export ledger (a workshop file, not shipped).

Exported to workshop_tests/ by tools/export_public_repo.py; the quotes themselves are
checked in tests/test_quotes_and_i18n_v13.py.

Run:  python -m unittest tests.test_quotes_export_workshop -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QuotesExportLedgerTest(unittest.TestCase):
    def test_verified_quotes_58_export_ledger(self) -> None:
        export_md = ROOT / "work" / "quotes_verified_58_export.md"
        self.assertTrue(export_md.exists())
        md_text = export_md.read_text(encoding="utf-8")
        self.assertIn("SOURCE_NAMED_PENDING_URL", md_text)
        self.assertIn("VERIFIED_QUOTE", md_text)


if __name__ == "__main__":
    unittest.main()
