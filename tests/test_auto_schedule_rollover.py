"""Auto mode hands over to the new day's member at midnight (no Tk, no assets)."""
from __future__ import annotations

import datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.engine.contracts import GlobalMode   # noqa: E402
from app.main import MEMBER_KEYS, PandaPet   # noqa: E402

MONDAY = datetime.datetime(2026, 11, 23, 23, 59, 59)   # chorong
TUESDAY = datetime.datetime(2026, 11, 24, 0, 0, 1)     # bomi
SATURDAY = datetime.datetime(2026, 11, 28, 0, 0, 1)
SUNDAY = datetime.datetime(2026, 11, 29, 0, 0, 1)


class _Clock:
    def __init__(self, now: datetime.datetime) -> None:
        self.value = now

    def now(self) -> datetime.datetime:
        return self.value


class _Coord:
    def __init__(self) -> None:
        self.mode = GlobalMode.NORMAL


class _FakePet:
    """Just the state the rollover reads; the real switch side effects are recorded."""

    _auto_schedule_today = PandaPet._auto_schedule_today
    get_auto_character = PandaPet.get_auto_character
    _check_auto_schedule_rollover = PandaPet._check_auto_schedule_rollover
    switch_to_auto_schedule = PandaPet.switch_to_auto_schedule

    def __init__(self, now: datetime.datetime, mode: str = "auto") -> None:
        self.clock = _Clock(now)
        self.coord = _Coord()
        self.mode = mode
        self.settings = {"mode": mode}
        self.standby_overlay = None
        self._standby_resume_pending = False
        self._desktop_was_locked = False
        self.dragging = False
        self.cameo_window = None
        self.group_celebration = None
        self._festival_preview_active = False
        self.char_key = self.get_auto_character() if mode == "auto" else "eunji"
        self._last_auto_date = self._auto_schedule_today()
        self.switch_calls: list[tuple[str, str]] = []
        self.menu_builds = 0

    def switch_character(self, char_key: str, mode: str = "manual") -> None:
        self.switch_calls.append((char_key, mode))
        self.mode = mode
        if mode == "auto":
            self._last_auto_date = self._auto_schedule_today()
        self.char_key = char_key

    def save_settings(self) -> None:
        pass

    def build_menu(self) -> None:
        self.menu_builds += 1


class AutoScheduleRolloverTests(unittest.TestCase):
    def test_monday_to_tuesday_switches_chorong_to_bomi(self) -> None:
        pet = _FakePet(MONDAY)
        self.assertEqual(pet.char_key, "chorong")
        self.assertFalse(pet._check_auto_schedule_rollover())   # same day: nothing
        pet.clock.value = TUESDAY
        self.assertTrue(pet._check_auto_schedule_rollover())
        self.assertEqual(pet.switch_calls, [("bomi", "auto")])
        self.assertEqual(pet.char_key, "bomi")
        self.assertEqual(pet._last_auto_date, TUESDAY.date())
        pet._check_auto_schedule_rollover()                      # later ticks don't repeat
        self.assertEqual(len(pet.switch_calls), 1)

    def test_manual_mode_is_never_overridden(self) -> None:
        pet = _FakePet(MONDAY, mode="manual")
        pet.clock.value = TUESDAY
        self.assertFalse(pet._check_auto_schedule_rollover())
        self.assertEqual(pet.switch_calls, [])
        self.assertEqual(pet.char_key, "eunji")

    def test_busy_states_defer_until_back_to_normal(self) -> None:
        blockers = {
            "standby": lambda p, on: setattr(p, "standby_overlay", object() if on else None),
            "standby_resume": lambda p, on: setattr(p, "_standby_resume_pending", on),
            "locked": lambda p, on: setattr(p, "_desktop_was_locked", on),
            "dragging": lambda p, on: setattr(p, "dragging", on),
            "cameo_mode": lambda p, on: setattr(p.coord, "mode", GlobalMode.CAMEO if on else GlobalMode.NORMAL),
            "standby_mode": lambda p, on: setattr(p.coord, "mode", GlobalMode.STANDBY if on else GlobalMode.NORMAL),
            "cameo_window": lambda p, on: setattr(p, "cameo_window", object() if on else None),
            "group_celebration": lambda p, on: setattr(p, "group_celebration", object() if on else None),
        }
        for name, toggle in blockers.items():
            with self.subTest(blocker=name):
                pet = _FakePet(MONDAY)
                pet.clock.value = TUESDAY
                toggle(pet, True)
                for _ in range(3):
                    self.assertFalse(pet._check_auto_schedule_rollover())
                self.assertEqual(pet.switch_calls, [])
                self.assertEqual(pet._last_auto_date, MONDAY.date())   # not marked while deferred
                toggle(pet, False)
                self.assertTrue(pet._check_auto_schedule_rollover())
                self.assertEqual(pet.switch_calls, [("bomi", "auto")])

    def test_same_member_next_day_only_marks_the_date(self) -> None:
        pet = _FakePet(SATURDAY)
        pet.clock.value = SUNDAY
        sunday_member = pet.get_auto_character()
        pet.char_key = sunday_member   # weekend draw happens to repeat
        self.assertFalse(pet._check_auto_schedule_rollover())
        self.assertEqual(pet.switch_calls, [])
        self.assertEqual(pet._last_auto_date, SUNDAY.date())
        self.assertEqual(pet.menu_builds, 1)   # weekday label refreshed once
        pet._check_auto_schedule_rollover()
        self.assertEqual(pet.menu_builds, 1)

    def test_weekend_draw_is_stable_and_triggers_once(self) -> None:
        pet = _FakePet(datetime.datetime(2026, 11, 27, 23, 59))   # Friday = namjoo
        self.assertEqual(pet.char_key, MEMBER_KEYS[4])
        pet.clock.value = SATURDAY
        expected = pet.get_auto_character()
        self.assertEqual(expected, pet.get_auto_character())       # seeded by the date
        for _ in range(5):
            pet._check_auto_schedule_rollover()
        switches = len(pet.switch_calls)
        self.assertLessEqual(switches, 1)
        self.assertEqual(pet.char_key, expected)
        self.assertEqual(pet._last_auto_date, SATURDAY.date())

    def test_uses_shifted_clock_not_wall_date(self) -> None:
        pet = _FakePet(TUESDAY)
        self.assertEqual(pet.get_auto_character(), "bomi")
        del pet.clock
        pet.calendar = type("Cal", (), {"clock": _Clock(MONDAY)})()
        self.assertEqual(pet.get_auto_character(), "chorong")

    def test_switch_to_auto_schedule_marks_today(self) -> None:
        pet = _FakePet(MONDAY, mode="manual")
        pet.clock.value = TUESDAY
        pet.switch_to_auto_schedule()
        self.assertEqual(pet.switch_calls, [("bomi", "auto")])
        self.assertEqual(pet._last_auto_date, TUESDAY.date())
        self.assertFalse(pet._check_auto_schedule_rollover())
        self.assertEqual(len(pet.switch_calls), 1)


if __name__ == "__main__":
    unittest.main()
