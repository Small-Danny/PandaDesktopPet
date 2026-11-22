"""Satiety survives closing and reopening the app (it only decays while the app runs).

Run:  python -m unittest tests.test_satiety_persistence -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.main import SATIETY_KEY, PandaPet, member_satiety, migrate_shared_satiety  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class SatietyPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _store(self, satiety: float, updated_ago: float) -> None:
        runtime = dict(DEFAULT_RUNTIME, satiety=satiety, last_satiety_update=time.time() - updated_ago)
        PersistenceService(self.dir).save(dict(DEFAULT_SETTINGS), runtime)

    def _saved(self) -> dict:
        return PersistenceService(self.dir).load()[1]

    def test_no_decay_while_closed(self) -> None:
        self._store(satiety=60.0, updated_ago=10 * 3600)   # closed overnight
        pet = PandaPet(data_dir=self.dir)
        try:
            self.assertAlmostEqual(pet.satiety, 60.0)
            self.assertLess(time.time() - pet.last_satiety_update, 5)
        finally:
            pet.close()

    def test_close_saves_the_current_value(self) -> None:
        self._store(satiety=60.0, updated_ago=0)
        pet = PandaPet(data_dir=self.dir)
        member = pet.char_key
        pet.satiety = 73.0
        pet.last_satiety_update = time.time() - 720       # one unsaved percent of decay
        pet.close()
        self.assertAlmostEqual(self._saved()[SATIETY_KEY][member], 72.0, delta=0.15)
        reopened = PandaPet(data_dir=self.dir)
        try:
            self.assertAlmostEqual(reopened.satiety, 72.0, delta=0.15)
        finally:
            reopened.close()

    def test_bad_stored_value_is_clamped(self) -> None:
        self._store(satiety=250.0, updated_ago=0)
        pet = PandaPet(data_dir=self.dir)
        try:
            self.assertEqual(pet.satiety, 100.0)
        finally:
            pet.close()


class PerMemberSatietyTest(unittest.TestCase):
    """Feeding Chorong full must not fill the other members."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _pet(self, runtime_extra: dict | None = None, member: str = "chorong") -> PandaPet:
        settings = dict(DEFAULT_SETTINGS, mode="manual", manual_character=member)
        PersistenceService(self.dir).save(settings, dict(DEFAULT_RUNTIME, **(runtime_extra or {})))
        pet = PandaPet(data_dir=self.dir)
        self.assertEqual(pet.char_key, member)
        return pet

    def test_switching_keeps_each_members_own_value(self) -> None:
        pet = self._pet({SATIETY_KEY: {"chorong": 40.0, "eunji": 70.0}})
        try:
            pet.feed("matcha_cake")                          # Chorong's favourite: +35
            self.assertAlmostEqual(pet.satiety, 75.0, delta=0.1)
            pet.switch_character("eunji")
            self.assertAlmostEqual(pet.satiety, 70.0)        # not Chorong's 75
            pet.switch_character("hayoung")
            self.assertAlmostEqual(pet.satiety, 100.0, delta=0.1)   # never fed: full
            pet.switch_character("chorong")
            self.assertAlmostEqual(pet.satiety, 75.0, delta=0.1)
        finally:
            pet.close()
        saved = PersistenceService(self.dir).load()[1][SATIETY_KEY]
        self.assertAlmostEqual(saved["chorong"], 75.0, delta=0.1)
        self.assertAlmostEqual(saved["eunji"], 70.0, delta=0.1)
        self.assertAlmostEqual(saved["hayoung"], 100.0, delta=0.1)

    def test_off_stage_members_get_hungry_too(self) -> None:
        pet = self._pet({SATIETY_KEY: {"chorong": 50.0, "eunji": 80.0}})
        try:
            pet.last_satiety_update = time.time() - 7200     # 2 h, unsaved
            pet.switch_character("eunji")
            self.assertAlmostEqual(pet.runtime[SATIETY_KEY]["chorong"], 40.0, delta=0.1)
            self.assertAlmostEqual(pet.satiety, 70.0, delta=0.1)          # off stage, still 10 % down
            self.assertAlmostEqual(pet.runtime[SATIETY_KEY]["hayoung"], 90.0, delta=0.1)   # never fed: from full
        finally:
            pet.close()

    def test_the_minute_tick_decays_everyone(self) -> None:
        pet = self._pet({SATIETY_KEY: {"chorong": 50.0, "bomi": 30.0}})
        try:
            pet.last_satiety_update = time.time() - 720       # one percent
            pet._last_companion_save = 0
            pet._tick_1s_body() if hasattr(pet, "_tick_1s_body") else pet._decay_everyone(time.time())
            table = pet.runtime[SATIETY_KEY]
            self.assertAlmostEqual(table["chorong"], 49.0, delta=0.1)
            self.assertAlmostEqual(table["bomi"], 29.0, delta=0.1)
            self.assertAlmostEqual(table["namjoo"], 99.0, delta=0.1)
        finally:
            pet.close()

    def test_old_shared_value_goes_to_the_member_on_stage_once(self) -> None:
        pet = self._pet({"satiety": 30.0}, member="bomi")
        try:
            self.assertAlmostEqual(pet.satiety, 30.0)
            self.assertNotIn("satiety", pet.runtime)
            pet.switch_character("namjoo")
            self.assertAlmostEqual(pet.satiety, 100.0, delta=0.1)
        finally:
            pet.close()
        runtime = PersistenceService(self.dir).load()[1]
        self.assertNotIn("satiety", runtime)
        self.assertAlmostEqual(runtime[SATIETY_KEY]["bomi"], 30.0, delta=0.1)

    def test_table_wins_over_a_leftover_shared_value(self) -> None:
        pet = self._pet({"satiety": 5.0, SATIETY_KEY: {"chorong": 60.0}})
        try:
            self.assertAlmostEqual(pet.satiety, 60.0)
        finally:
            pet.close()

    def test_broken_values_count_as_full(self) -> None:
        for broken in (None, "x", True, {"chorong": None}, {"chorong": "60"}, {"chorong": False}):
            runtime = {SATIETY_KEY: broken}
            with self.subTest(broken=broken):
                self.assertEqual(member_satiety(runtime, "chorong"), 100.0)
        legacy = {"satiety": None}
        migrate_shared_satiety(legacy, "chorong")              # used to crash float(None)
        self.assertEqual(member_satiety(legacy, "chorong"), 100.0)


@unittest.skipUnless(sys.platform == "win32", "named mutex is Windows only")
class SingleInstanceTest(unittest.TestCase):
    """Two pets on one data folder overwrote each other's satiety every minute."""

    def test_second_pet_on_the_same_folder_is_refused(self) -> None:
        import ctypes
        from app.main import acquire_single_instance
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = acquire_single_instance(Path(a))
            self.assertTrue(first)
            try:
                self.assertIsNone(acquire_single_instance(Path(a)))
                self.assertIsNone(acquire_single_instance(Path(a.upper())))   # same folder, other case
                other = acquire_single_instance(Path(b))                    # other folder: allowed
                self.assertTrue(other)
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(other))
            finally:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(first))
            again = acquire_single_instance(Path(a))                       # first pet closed
            self.assertTrue(again)
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(again))


if __name__ == "__main__":
    unittest.main()
