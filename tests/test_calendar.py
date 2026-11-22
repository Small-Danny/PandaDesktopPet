"""tests/test_calendar.py — Unit tests for CalendarScheduler & Special Events."""
import datetime as dt
import unittest
from typing import Optional

from app.engine.calendar import (
    APINK_SPECIAL_DATES,
    CalendarScheduler,
    OffsetClock,
    SpecialDate,
)
from app.engine.contracts import ActorState, Priority


class FakeClock:
    def __init__(self, current_dt: dt.datetime, initial_mono: float = 1000.0) -> None:
        self._dt = current_dt
        self._mono = initial_mono

    def now(self) -> dt.datetime:
        return self._dt

    def monotonic(self) -> float:
        return self._mono

    def advance(self, seconds: float = 0.0, days: int = 0) -> None:
        self._dt += dt.timedelta(seconds=seconds, days=days)
        self._mono += seconds + (days * 86400.0)

    def set_datetime(self, new_dt: dt.datetime) -> None:
        self._dt = new_dt


class TestCalendarScheduler(unittest.TestCase):
    def test_chorong_birthday_triggers(self) -> None:
        clock = FakeClock(dt.datetime(2026, 3, 3, 10, 30))
        sched = CalendarScheduler(clock=clock)
        events = sched.check_special_dates(active_member="chorong")

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.kind, "calendar.birthday.chorong")
        self.assertEqual(ev.priority, Priority.SYSTEM)
        self.assertEqual(ev.state, ActorState.CHEER)
        self.assertEqual(ev.action, "birthday_cake")
        self.assertTrue(ev.payload["is_birthday"])
        self.assertIn("初瓏", ev.payload["text"])

    def test_all_five_members_birthdays(self) -> None:
        expected = [
            (3, 3, "chorong"),
            (4, 15, "namjoo"),
            (7, 19, "hayoung"),
            (8, 13, "bomi"),
            (8, 18, "eunji"),
        ]
        for m, d, member in expected:
            clock = FakeClock(dt.datetime(2026, m, d, 14, 0))
            sched = CalendarScheduler(clock=clock)
            events = sched.check_special_dates(active_member="chorong")
            self.assertEqual(len(events), 1, f"Failed for {member} on {m}/{d}")
            self.assertIn(member, events[0].kind)

    def test_apink_419_anniversary(self) -> None:
        clock = FakeClock(dt.datetime(2026, 4, 19, 12, 0))
        sched = CalendarScheduler(clock=clock)
        events = sched.check_special_dates(active_member="eunji")

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.kind, "calendar.anniversary.apink419")
        self.assertTrue(ev.payload["is_anniversary"])
        self.assertIn("419", ev.payload["text"])

    def test_regular_day_no_special_dates(self) -> None:
        clock = FakeClock(dt.datetime(2026, 5, 20, 10, 0))
        sched = CalendarScheduler(clock=clock)
        events = sched.check_special_dates(active_member="bomi")
        self.assertEqual(len(events), 0)

    def test_no_double_trigger_same_day(self) -> None:
        clock = FakeClock(dt.datetime(2026, 3, 3, 10, 0))
        sched = CalendarScheduler(clock=clock)

        events1 = sched.check_special_dates(active_member="chorong")
        self.assertEqual(len(events1), 1)

        # Same day 1 hour later
        clock.advance(seconds=3600)
        events2 = sched.check_special_dates(active_member="chorong")
        self.assertEqual(len(events2), 0)

    def test_reset_next_day(self) -> None:
        clock = FakeClock(dt.datetime(2026, 3, 3, 23, 0))
        sched = CalendarScheduler(clock=clock)
        self.assertEqual(len(sched.check_special_dates("chorong")), 1)

        # Next day
        clock.advance(days=1)
        self.assertEqual(len(sched.check_special_dates("chorong")), 0)

    def test_hourly_chime_daytime_on_the_hour(self) -> None:
        clock = FakeClock(dt.datetime(2026, 6, 1, 14, 0))  # 14:00
        sched = CalendarScheduler(clock=clock, enable_hourly_chime=True)
        chime = sched.check_hourly_chime()
        self.assertIsNotNone(chime)
        assert chime is not None
        self.assertEqual(chime.kind, "calendar.chime.14")
        self.assertEqual(chime.priority, Priority.SYSTEM)
        self.assertFalse(chime.wakes_sleep)
        self.assertIn("14", chime.kind)

        # Subsequent check at 14:00 doesn't double trigger
        self.assertIsNone(sched.check_hourly_chime())

    def test_hourly_chime_not_on_the_hour(self) -> None:
        clock = FakeClock(dt.datetime(2026, 6, 1, 14, 15))  # 14:15
        sched = CalendarScheduler(clock=clock, enable_hourly_chime=True)
        self.assertIsNone(sched.check_hourly_chime())

    def test_hourly_chime_night_silent(self) -> None:
        clock = FakeClock(dt.datetime(2026, 6, 1, 2, 0))  # 02:00
        sched = CalendarScheduler(clock=clock, hourly_chime_range=(9, 22))
        self.assertIsNone(sched.check_hourly_chime())

    def test_sedentary_reminder_trigger_and_interval(self) -> None:
        clock = FakeClock(dt.datetime(2026, 6, 1, 10, 0), initial_mono=100.0)
        sched = CalendarScheduler(clock=clock, sedentary_interval_min=30)

        # Not yet due (20 min passed)
        clock.advance(seconds=20 * 60)
        self.assertIsNone(sched.check_sedentary_reminder())

        # Due (31 min passed total)
        clock.advance(seconds=11 * 60)
        reminder = sched.check_sedentary_reminder()
        self.assertIsNotNone(reminder)
        assert reminder is not None
        self.assertEqual(reminder.kind, "reminder.sedentary")
        self.assertEqual(reminder.priority, Priority.SYSTEM)

    def test_user_personal_birthday_celebration(self) -> None:
        # User birthday on November 5th
        clock = FakeClock(dt.datetime(2026, 11, 5, 10, 0))
        sched = CalendarScheduler(clock=clock, user_birthday=(11, 5), user_nickname="小粉熊")

        events = sched.poll_all_due_events(active_member="eunji")
        user_events = [e for e in events if e.kind == "calendar.birthday.user"]
        self.assertEqual(len(user_events), 1)

        ev = user_events[0]
        self.assertEqual(ev.priority, Priority.SYSTEM)
        self.assertEqual(ev.state, ActorState.CHEER)
        self.assertEqual(ev.action, "birthday_cake")
        self.assertIn("小粉熊", ev.payload["text"])
        self.assertIn("恩地", ev.payload["text"])
        self.assertTrue(ev.payload["is_user_birthday"])

        # Same day won't trigger again
        clock.advance(seconds=3600)
        events2 = sched.poll_all_due_events(active_member="eunji")
        user_events2 = [e for e in events2 if e.kind == "calendar.birthday.user"]
        self.assertEqual(len(user_events2), 0)

    def test_offset_clock_shifting(self) -> None:
        base = FakeClock(dt.datetime(2026, 1, 1, 12, 0))
        offset_clock = OffsetClock(base=base)
        self.assertEqual(offset_clock.now().month, 1)

        # Shift to Chorong birthday
        offset_clock.set_target_date(2026, 3, 3, 12)
        self.assertEqual(offset_clock.now().month, 3)
        self.assertEqual(offset_clock.now().day, 3)

        sched = CalendarScheduler(clock=offset_clock)
        events = sched.check_special_dates("chorong")
        self.assertEqual(len(events), 1)
        self.assertIn("chorong", events[0].kind)

    def test_solo_and_unit_anniversaries(self) -> None:
        milestones = [
            (1, 5, "chorong", "anniversary.first_win", "一位"),
            (2, 18, "chorong", "anniversary.fandom.pinkpanda", "粉熊"),
            (4, 18, "eunji", "anniversary.solo.eunji", "Hopefully Sky"),
            (6, 27, "bomi", "anniversary.unit.bnn", "BnN"),
            (7, 12, "chorong", "anniversary.unit.chobom", "CHOBOM"),
            (8, 21, "hayoung", "anniversary.solo.hayoung", "Don't Make Me Laugh"),
            (9, 7, "namjoo", "anniversary.solo.namjoo", "Bird"),
            (12, 31, "chorong", "holiday.newyearseve", "跨年夜"),
        ]
        for m, d, member, expected_kind, expected_keyword in milestones:
            clock = FakeClock(dt.datetime(2026, m, d, 15, 0))
            sched = CalendarScheduler(clock=clock)
            events = sched.check_special_dates(active_member=member)
            matching = [e for e in events if expected_kind in e.kind]
            self.assertEqual(len(matching), 1, f"Failed for {expected_kind}")
            self.assertIn(expected_keyword, matching[0].payload["text"])

    def test_holiday_and_solo_actions_are_valid_and_nye_has_no_false_30min_warning(self) -> None:
        by_kind = {sd.kind_suffix: sd for sd in APINK_SPECIAL_DATES}
        self.assertEqual(by_kind["holiday.christmas"].action, "festival_christmas")
        self.assertEqual(by_kind["anniversary.solo.eunji"].action, "special_sing_highnote")
        self.assertEqual(by_kind["anniversary.solo.hayoung"].action, "special_gaming")
        self.assertEqual(by_kind["holiday.newyearseve"].action, "festival_new_year")
        self.assertEqual(by_kind["holiday.newyear"].action, "festival_new_year")
        nye = by_kind["holiday.newyearseve"]
        all_nye_text = " ".join([nye.default_speech, *nye.speech_i18n.values()])
        for bad_phrase in ("還有 30 分鐘跨年", "이제 30분 남았어요", "Just 30 minutes left"):
            self.assertNotIn(bad_phrase, all_nye_text)



if __name__ == "__main__":
    unittest.main()
