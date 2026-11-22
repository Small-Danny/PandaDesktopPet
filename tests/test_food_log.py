"""Food discovery log kept in runtime: tolerant reads, first discovery kept, safe storage.

Run:  python -m unittest tests.test_food_log -v
"""
from __future__ import annotations

import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.food_log import normalize, outcomes, record  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class RecordTest(unittest.TestCase):
    def test_first_feed_is_new_and_first_discovery_is_kept(self) -> None:
        runtime = dict(DEFAULT_RUNTIME)
        self.assertTrue(record(runtime, "eunji", "egg", "favourite", 1000))
        self.assertFalse(record(runtime, "eunji", "egg", "normal", 2000))
        self.assertEqual(runtime["food_log"]["eunji"]["egg"], {"outcome": "favourite", "first_fed": 1000})
        self.assertEqual(outcomes(runtime, "eunji"), {"egg": "favourite"})

    def test_members_are_separate(self) -> None:
        runtime = {}
        record(runtime, "eunji", "egg", "favourite", 1)
        self.assertEqual(outcomes(runtime, "hayoung"), {})
        self.assertTrue(record(runtime, "hayoung", "egg", "normal", 2))

    def test_invalid_input_changes_nothing(self) -> None:
        for args in (("nobody", "egg", "normal", 1), ("eunji", "pizza_x", "normal", 1),
                     ("eunji", "egg", "refused_full", 1), ("eunji", "egg", "drink_full", 1),
                     ("eunji", "egg", "normal", -1),
                     ("eunji", "egg", "normal", math.nan), ("eunji", "egg", "normal", True)):
            runtime = {"feed_count": 1}
            with self.subTest(args=args):
                self.assertFalse(record(runtime, *args))
                self.assertEqual(runtime, {"feed_count": 1})

    def test_outcomes_returns_a_detached_copy(self) -> None:
        runtime = {}
        record(runtime, "eunji", "egg", "favourite", 1)
        before = copy.deepcopy(runtime)
        outcomes(runtime, "eunji")["egg"] = "disliked"
        self.assertEqual(runtime, before)


class TolerantReadTest(unittest.TestCase):
    def _dirty(self) -> dict:
        return {"feed_count": 4, "food_log": {
            "eunji": {
                "egg": {"outcome": "favourite", "first_fed": 10},
                "ramyeon": {"outcome": "loved", "first_fed": 10},       # unknown outcome
                "cola": {"outcome": "normal", "first_fed": -1},         # bad timestamp
                "beer": {"outcome": "normal"},                           # missing field
                "gone_food": {"outcome": "normal", "first_fed": 10},    # food removed
                "soju": "normal",                                        # not an entry
            },
            "ghost": {"egg": {"outcome": "normal", "first_fed": 1}},
            "bomi": [],
        }}

    def test_bad_entries_are_dropped_one_by_one(self) -> None:
        runtime = self._dirty()
        self.assertEqual(outcomes(runtime, "eunji"), {"egg": "favourite"})
        self.assertEqual(outcomes(runtime, "ghost"), {})
        self.assertEqual(outcomes(runtime, "bomi"), {})
        self.assertEqual(runtime, self._dirty())             # reading never mutates

    def test_normalize_keeps_valid_peers_and_other_keys(self) -> None:
        runtime = self._dirty()
        self.assertTrue(normalize(runtime))
        self.assertEqual(runtime, {"feed_count": 4, "food_log": {"eunji": {"egg": {"outcome": "favourite", "first_fed": 10}}}})
        self.assertFalse(normalize(runtime))

    def test_broken_log_value_is_replaced(self) -> None:
        for broken in ([], "x", None, 3):
            runtime = {"food_log": broken}
            with self.subTest(broken=broken):
                self.assertEqual(outcomes(runtime, "eunji"), {})
                self.assertTrue(record(runtime, "eunji", "egg", "favourite", 5))
                self.assertEqual(outcomes(runtime, "eunji"), {"egg": "favourite"})

    def test_broken_entry_is_rewritten_as_new(self) -> None:
        runtime = {"food_log": {"eunji": {"egg": {"outcome": "x"}}}}
        self.assertTrue(record(runtime, "eunji", "egg", "favourite", 7))
        self.assertEqual(runtime["food_log"]["eunji"]["egg"], {"outcome": "favourite", "first_fed": 7})


class StorageRoundTripTest(unittest.TestCase):
    def test_log_survives_save_and_load_and_bad_entries_do_not_lose_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PersistenceService(Path(tmp))
            runtime = dict(DEFAULT_RUNTIME, feed_count=3)
            record(runtime, "eunji", "egg", "favourite", 100)
            runtime["food_log"]["eunji"]["bad"] = {"outcome": "x"}
            store.save(dict(DEFAULT_SETTINGS), runtime)
            _, loaded = store.load()
            self.assertEqual(store.recovery_events, [])
            self.assertEqual(loaded["feed_count"], 3)
            self.assertEqual(outcomes(loaded, "eunji"), {"egg": "favourite"})


if __name__ == "__main__":
    unittest.main()
