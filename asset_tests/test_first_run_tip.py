"""First run: after the welcome card closes, the pet says once how to play."""
from __future__ import annotations

import gc
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp())

from app.birthday_dialog import BirthdayDialog  # noqa: E402
from app.i18n import LOCALES, t  # noqa: E402
from app.main import PandaPet  # noqa: E402
from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class DialogCloseCallbackTest(unittest.TestCase):
    def test_on_close_fires_once_for_save_and_plain_close(self) -> None:
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(gc.collect)
        self.addCleanup(root.destroy)
        calls: list[str] = []
        dlg = BirthdayDialog(root, (4, 19), "Panda", lambda *a: calls.append("save"),
                             on_close=lambda: calls.append("close"))
        dlg.save()
        dlg.close()
        self.assertEqual(calls, ["close", "save"])
        dlg2 = BirthdayDialog(root, None, "Panda", lambda *a: None, on_close=lambda: calls.append("close2"))
        dlg2.close()
        self.assertEqual(calls[-1], "close2")
        BirthdayDialog(root, None, "Panda", lambda *a: None).close()        # still optional


class FirstRunTipTest(unittest.TestCase):
    def _pet(self, **settings) -> PandaPet:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        PersistenceService(Path(tmp.name)).save(
            dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong", **settings), dict(DEFAULT_RUNTIME))
        pet = PandaPet(data_dir=Path(tmp.name))
        self.addCleanup(gc.collect)
        self.addCleanup(pet.close)
        return pet

    def test_tip_is_queued_when_the_welcome_card_closes(self) -> None:
        pet = self._pet()
        pet._check_first_run_onboarding()
        self.assertTrue(pet.settings["onboarding_prompted"])
        self.assertNotIn("first_run_tip", pet._loop_after)
        pet.birthday_dialog.close()
        self.assertIn("first_run_tip", pet._loop_after)
        with mock.patch.object(pet, "_toast") as toast:
            pet._show_first_run_tip()
        self.assertEqual(toast.call_args.args[0], t("first_run_tip", pet.lang))

    def test_reopening_the_birthday_card_later_does_not_repeat_the_tip(self) -> None:
        pet = self._pet(onboarding_prompted=True)
        pet.open_birthday_dialog()
        pet.birthday_dialog.close()
        self.assertNotIn("first_run_tip", pet._loop_after)

    def test_every_language_has_the_tip(self) -> None:
        for lang, table in LOCALES.items():
            self.assertIn("first_run_tip", table, lang)


if __name__ == "__main__":
    unittest.main()
