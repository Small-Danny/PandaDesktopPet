"""Settings panel back end: only valid values are applied; defaults; preview; custom reminder text.

Run:  python -m unittest tests.test_settings_apply -v
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import Priority  # noqa: E402
from app.main import SETTINGS_DEFAULTS, PandaPet, clean_reminder_text  # noqa: E402


def _pet(**settings):
    pet = types.SimpleNamespace(settings=dict(settings), lang="zh_TW", sedentary_active_sec=123)
    calls = []
    for name in ("set_bubble_theme", "set_pet_size", "set_text_size", "toggle_hourly_chime",
                 "set_sedentary_interval", "test_sedentary_alert", "set_hourly_range"):
        setattr(pet, name, lambda *a, _n=name: calls.append((_n,) + a))
    pet.save_settings = lambda: calls.append(("save",)) or True
    for name in ("apply_setting", "reset_settings", "preview_reminder", "settings_state"):
        setattr(pet, name, getattr(PandaPet, name).__get__(pet))
    return pet, calls


class ApplySettingTest(unittest.TestCase):
    def test_valid_values_go_to_the_existing_setters(self) -> None:
        pet, calls = _pet()
        for key, value, expected in (("bubble_theme", "classic", ("set_bubble_theme", "classic")),
                                     ("pet_size", "large", ("set_pet_size", "large")),
                                     ("text_size", "small", ("set_text_size", "small")),
                                     ("hourly_chime", False, ("toggle_hourly_chime",)),
                                     ("sedentary_interval_min", 90, ("set_sedentary_interval", 90)),
                                     ("sedentary_interval_min", 0, ("set_sedentary_interval", 0))):
            calls.clear()
            with self.subTest(key=key, value=value):
                self.assertTrue(pet.apply_setting(key, value))
                self.assertEqual(calls, [expected])

    def test_invalid_values_change_nothing(self) -> None:
        pet, calls = _pet()
        for key, value in (("bubble_theme", "no_such_theme"), ("pet_size", "huge"), ("text_size", 3),
                           ("bubble_theme", []), ("pet_size", {}), ("text_size", ["small"]),
                           ("hourly_chime", "yes"), ("hourly_chime", 1),
                           ("sedentary_interval_min", 4), ("sedentary_interval_min", 241),
                           ("sedentary_interval_min", 30.0), ("sedentary_interval_min", True),
                           ("sedentary_message", "x" * 61), ("sedentary_message", None),
                           ("hourly_start", -1), ("hourly_end", 24), ("hourly_start", 8.0), ("hourly_end", True),
                           ("lang", "en"), ("standby_lock_workstation", False)):
            with self.subTest(key=key, value=value):
                self.assertFalse(pet.apply_setting(key, value))
        self.assertEqual(calls, [])
        self.assertEqual(pet.settings, {})

    def test_unchanged_values_do_not_toggle(self) -> None:
        pet, calls = _pet(hourly_chime=True, sedentary_interval_min=60, bubble_theme="auto")
        self.assertTrue(pet.apply_setting("hourly_chime", True))
        self.assertTrue(pet.apply_setting("sedentary_interval_min", 60))
        self.assertTrue(pet.apply_setting("bubble_theme", "auto"))
        self.assertEqual(calls, [])

    def test_custom_message_is_cleaned_and_saved(self) -> None:
        pet, calls = _pet()
        self.assertTrue(pet.apply_setting("sedentary_message", "  起來​動一動\n囉 "))
        self.assertEqual(pet.settings["sedentary_message"], "起來動一動囉")
        self.assertEqual(calls, [("save",)])
        self.assertTrue(pet.apply_setting("sedentary_message", ""))           # back to the member line
        self.assertEqual(pet.settings["sedentary_message"], "")

    def test_clean_reminder_text(self) -> None:
        self.assertEqual(clean_reminder_text("\t喝水\x07 "), "喝水")
        self.assertEqual(clean_reminder_text("a" * 60), "a" * 60)
        self.assertIsNone(clean_reminder_text("a" * 61))
        self.assertIsNone(clean_reminder_text(42))


class HourlyRangeTest(unittest.TestCase):
    def test_each_end_moves_and_drags_the_other_along(self) -> None:
        pet, calls = _pet()
        self.assertTrue(pet.apply_setting("hourly_start", 8))
        self.assertTrue(pet.apply_setting("hourly_end", 23))
        self.assertEqual(calls, [("set_hourly_range", 8, 22), ("set_hourly_range", 9, 23)])  # fake keeps 9-22
        pet, calls = _pet(hourly_start=10, hourly_end=12)
        pet.apply_setting("hourly_start", 15)
        pet.apply_setting("hourly_end", 7)
        self.assertEqual(calls, [("set_hourly_range", 15, 15), ("set_hourly_range", 7, 7)])

    def test_unchanged_or_broken_saved_range(self) -> None:
        from app.main import hourly_range
        pet, calls = _pet(hourly_start=9, hourly_end=22)
        self.assertTrue(pet.apply_setting("hourly_end", 22))
        self.assertEqual(calls, [])
        self.assertEqual(hourly_range({"hourly_start": 20, "hourly_end": 8}), (9, 22))
        self.assertEqual(hourly_range({"hourly_start": 0, "hourly_end": 23}), (0, 23))

    def test_real_pet_chimes_in_the_new_hours(self) -> None:
        import os, tempfile
        os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp())
        pet = types.SimpleNamespace(settings={}, calendar=types.SimpleNamespace(hourly_chime_range=(9, 22)),
                                    save_settings=lambda: True)
        PandaPet.set_hourly_range(pet, 7, 23)
        self.assertEqual((pet.calendar.hourly_chime_range, pet.settings), ((7, 23), {"hourly_start": 7, "hourly_end": 23}))


class ResetAndPreviewTest(unittest.TestCase):
    def test_reset_reminders_restores_the_defaults(self) -> None:
        pet, calls = _pet(hourly_chime=False, sedentary_interval_min=30, sedentary_message="喝水")
        self.assertTrue(pet.reset_settings("reminders"))
        self.assertIn(("toggle_hourly_chime",), calls)
        self.assertIn(("set_sedentary_interval", 60), calls)
        self.assertEqual(pet.settings["sedentary_message"], "")

    def test_reset_appearance(self) -> None:
        pet, calls = _pet(bubble_theme="classic", pet_size="large", text_size="small")
        self.assertTrue(pet.reset_settings("appearance"))
        self.assertEqual(calls, [("set_bubble_theme", "auto"), ("set_pet_size", "medium"),
                                 ("set_text_size", "medium")])
        self.assertFalse(pet.reset_settings("everything"))

    def test_state_has_every_panel_key(self) -> None:
        pet, _ = _pet(pet_size="small")
        state = pet.settings_state()
        expected = {k for section in SETTINGS_DEFAULTS.values() for k in section} | {"notify_privacy_mode"}
        self.assertEqual(set(state), expected)
        self.assertEqual(state["pet_size"], "small")
        self.assertEqual(state["sedentary_message"], "")

    def test_preview_does_not_touch_the_countdown(self) -> None:
        pet, calls = _pet()
        self.assertTrue(pet.preview_reminder("sedentary"))
        self.assertEqual(calls, [("test_sedentary_alert",)])
        self.assertEqual(pet.sedentary_active_sec, 123)
        self.assertFalse(pet.preview_reminder("hourly"))


class SedentaryTextTest(unittest.TestCase):
    def _alert(self, message):
        shown = []
        pet = types.SimpleNamespace(
            settings={"sedentary_message": message} if message is not None else {}, lang="zh_TW",
            trigger_cheer=lambda **kw: None, get_active_name=lambda: "初瓏",
            _toast=lambda msg, **kw: shown.append(msg),
        )
        PandaPet.sedentary_alert(pet, priority=Priority.USER)
        return shown[0]

    def test_custom_text_or_member_default(self) -> None:
        from app.i18n import t
        self.assertEqual(self._alert("該喝水囉"), "該喝水囉")
        self.assertEqual(self._alert(""), t("sedentary_hint", "zh_TW"))
        self.assertEqual(self._alert(None), t("sedentary_hint", "zh_TW"))


if __name__ == "__main__":
    unittest.main()
