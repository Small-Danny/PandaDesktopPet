"""User data lives in %APPDATA%\\PandaDesktopPet, adopted once from the legacy work folder."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import paths


class UserDataDirTests(unittest.TestCase):
    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"PANDA_DATA_DIR": r"X:\somewhere", "APPDATA": r"X:\roaming"}):
            self.assertEqual(paths.user_data_dir(), Path(r"X:\somewhere"))

    def test_default_is_under_appdata_not_the_checkout(self):
        env = {k: v for k, v in os.environ.items() if k != "PANDA_DATA_DIR"}
        env["APPDATA"] = r"X:\roaming"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(paths.user_data_dir(), Path(r"X:\roaming") / "PandaDesktopPet")

    def test_without_appdata_falls_back_to_work(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PANDA_DATA_DIR", "APPDATA")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(paths.user_data_dir(), paths.app_dir() / "work")


class AdoptLegacyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.legacy = Path(tmp.name) / "work"
        self.target = Path(tmp.name) / "roaming" / "PandaDesktopPet"
        self.legacy.mkdir()

    def test_copies_both_files_once_and_keeps_the_originals(self):
        (self.legacy / "settings.json").write_text('{"a": 1}', encoding="utf-8")
        (self.legacy / "runtime.json").write_text('{"b": 2}', encoding="utf-8")
        self.assertEqual(paths.adopt_legacy_user_data(self.target, self.legacy),
                         ["settings.json", "runtime.json"])
        self.assertEqual((self.target / "settings.json").read_text(encoding="utf-8"), '{"a": 1}')
        self.assertEqual((self.target / "runtime.json").read_text(encoding="utf-8"), '{"b": 2}')
        self.assertTrue((self.legacy / "settings.json").is_file())

    def test_never_overwrites_existing_new_data(self):
        (self.legacy / "settings.json").write_text('{"old": 1}', encoding="utf-8")
        self.target.mkdir(parents=True)
        (self.target / "settings.json").write_text('{"new": 1}', encoding="utf-8")
        self.assertEqual(paths.adopt_legacy_user_data(self.target, self.legacy), [])
        self.assertEqual((self.target / "settings.json").read_text(encoding="utf-8"), '{"new": 1}')

    def test_nothing_to_adopt(self):
        self.assertEqual(paths.adopt_legacy_user_data(self.target, self.legacy), [])
        self.assertFalse(self.target.exists())

    def test_same_folder_is_a_no_op(self):
        (self.legacy / "settings.json").write_text("{}", encoding="utf-8")
        self.assertEqual(paths.adopt_legacy_user_data(self.legacy, self.legacy), [])


if __name__ == "__main__":
    unittest.main()
