"""Windows notification relay: every toast of a poll is kept, one bubble shows them.

Run:  python -m unittest tests.test_notification_queue -v
"""
from __future__ import annotations

import contextlib
import datetime
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.i18n import t  # noqa: E402
from app.notifications import (  # noqa: E402
    PREVIEW_LINES, RECENT_LIMIT, WindowsNotificationMonitor, drawer_entry, relay_bubble,
)

# Made-up test data only (no real notification text).
ITEMS = [
    {"id": "11", "app": "LINE", "title": "TEST-TITLE-A", "body": "line 1\nline 2"},
    {"id": "12", "app": "Teams", "title": "TEST-TITLE-B", "body": "SECRET-BODY-B"},
    {"id": "13", "app": "Outlook", "title": "TEST-TITLE-C", "body": ""},
]


def _payload(*texts: str) -> bytes:
    inner = "".join(f"<text>{x}</text>" for x in texts)
    return f"<toast><visual><binding template='ToastGeneric'>{inner}</binding></visual></toast>".encode()


class RelayBubbleTest(unittest.TestCase):
    def test_first_item_then_how_many_more(self) -> None:
        header, text = relay_bubble(ITEMS, "zh_TW", False, t)
        self.assertEqual(header, t("windows_notif_header", "zh_TW", app="LINE"))
        self.assertTrue(text.startswith("TEST-TITLE-A\nline 1\nline 2\n"))
        self.assertIn("2", text.splitlines()[-1])
        self.assertNotIn("TEST-TITLE-B", text)

    def test_single_item_has_no_more_line(self) -> None:
        self.assertEqual(relay_bubble(ITEMS[:1], "en", False, t)[1], "TEST-TITLE-A\nline 1\nline 2")

    def test_privacy_names_the_app_only(self) -> None:
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                header, text = relay_bubble(ITEMS, lang, True, t)
                self.assertIn("LINE", text)
                for secret in ("TEST-TITLE", "line 1", "SECRET-BODY"):
                    self.assertNotIn(secret, header + text)

    def test_long_body_is_cut_and_untitled_gets_a_title(self) -> None:
        body = "\n".join(f"row {i}" for i in range(9))
        text = relay_bubble([{"id": "1", "app": "X", "title": "", "body": body}], "en", False, t)[1]
        lines = text.splitlines()
        self.assertEqual(len(lines), 1 + PREVIEW_LINES + 1)
        self.assertEqual(lines[-1], "...")
        self.assertTrue(lines[0])                              # translated "new notification"

    def test_texts_exist_in_all_languages(self) -> None:
        for lang in ("zh_TW", "ko", "en"):
            text = relay_bubble([{"id": "1", "app": "X", "title": "", "body": ""}] * 2, lang, False, t)[1]
            with self.subTest(lang=lang):
                self.assertNotIn("windows_notif", text)        # never a raw key

    def test_drawer_entry(self) -> None:
        row = drawer_entry(ITEMS[0], datetime.datetime(2026, 11, 8, 9, 5, 7))
        self.assertEqual(row, {"id": "11", "time": "09:05:07", "app": "LINE",
                               "title": "TEST-TITLE-A", "body": "line 1\nline 2"})


class MonitorTest(unittest.TestCase):
    """A fake wpndatabase.db with the columns the monitor reads."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "wpndatabase.db"
        with self._db() as con:
            con.execute("CREATE TABLE NotificationHandler (RecordId INTEGER, PrimaryId TEXT)")
            con.execute("CREATE TABLE Notification (Id INTEGER, Type TEXT, HandlerId INTEGER, Payload BLOB)")
            con.execute("INSERT INTO NotificationHandler VALUES (1, 'Microsoft.Teams_8wekyb3d8bbwe!App')")
            for nid in (1, 2):
                con.execute("INSERT INTO Notification VALUES (?, 'toast', 1, ?)", (nid, _payload(f"OLD-{nid}")))

    @contextlib.contextmanager
    def _db(self):
        con = sqlite3.connect(self.db)
        try:
            with con:                                  # commit
                yield con
        finally:
            con.close()                                # Windows keeps the file locked otherwise

    def _monitor(self) -> WindowsNotificationMonitor:
        mon = WindowsNotificationMonitor()
        mon.db_path = str(self.db)
        mon.last_seen_id = None
        mon._init_last_id()
        return mon

    def _add(self, *ids: int) -> None:
        with self._db() as con:
            for nid in ids:
                con.execute("INSERT INTO Notification VALUES (?, 'toast', 1, ?)",
                            (nid, _payload(f"TITLE-{nid}", f"BODY-{nid}")))

    def test_old_toasts_are_not_replayed_at_start(self) -> None:
        self.assertEqual(self._monitor().check_new_notifications(), [])

    def test_a_burst_is_read_in_order_and_nothing_is_dropped(self) -> None:
        mon = self._monitor()
        self._add(*range(3, 10))                                   # 7 new toasts
        first, second, third = (mon.check_new_notifications() for _ in range(3))
        self.assertEqual([n["id"] for n in first + second], [str(i) for i in range(3, 10)])
        self.assertEqual((len(first), third), (5, []))
        self.assertEqual((first[0]["app"], first[0]["title"], first[0]["body"]), ("Teams", "TITLE-3", "BODY-3"))

    def test_untitled_toast_has_an_empty_title(self) -> None:
        mon = self._monitor()
        with self._db() as con:
            con.execute("INSERT INTO Notification VALUES (3, 'toast', 1, ?)", (b"<toast/>",))
        self.assertEqual(mon.check_new_notifications()[0]["title"], "")

    def test_the_database_is_only_read(self) -> None:
        before = self.db.read_bytes()
        mon = self._monitor()
        self._add(3)
        snapshot = self.db.read_bytes()
        mon.check_new_notifications()
        self.assertEqual(self.db.read_bytes(), snapshot)
        self.assertNotEqual(before, snapshot)


class PetRelayTest(unittest.TestCase):
    def setUp(self) -> None:
        from app.main import PandaPet
        from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = PersistenceService(self.dir)
        self.store.save(dict(DEFAULT_SETTINGS, mode="manual", manual_character="chorong"), dict(DEFAULT_RUNTIME))
        self.pet = PandaPet(data_dir=self.dir)
        self.addCleanup(self.pet.close)
        self.shown: list = []
        patcher = mock.patch.object(self.pet, "_render_bubble", side_effect=self.shown.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_bubble_per_poll_and_every_item_in_the_drawer(self) -> None:
        with mock.patch.object(self.pet, "trigger_cheer") as cheer:
            self.pet.relay_notifications(ITEMS)
        self.assertEqual([r.kind for r in self.shown], ["notify.relay"])
        self.assertIn("TEST-TITLE-A", self.shown[0].text)
        self.assertEqual([r["id"] for r in self.pet.recent_notifications], ["11", "12", "13"])
        self.assertEqual(cheer.call_count, 1)                      # one reaction, not one per toast
        self.assertEqual(cheer.call_args.kwargs["kind"], "notify.relay")

    def test_drawer_keeps_the_latest_twenty_in_ram(self) -> None:
        for i in range(RECENT_LIMIT + 5):
            self.pet.relay_notifications([{"id": str(i), "app": "A", "title": f"T{i}", "body": ""}])
        ids = [r["id"] for r in self.pet.recent_notifications]
        self.assertEqual(ids, [str(i) for i in range(5, RECENT_LIMIT + 5)])
        self.assertNotIn("recent_notifications", self.store.load()[0])        # never saved
        self.pet.clear_recent_notifications()
        self.assertEqual(len(self.pet.recent_notifications), 0)

    def test_privacy_mode_hides_title_and_body_and_is_saved(self) -> None:
        self.pet.toggle_notify_privacy()
        self.assertIs(self.store.load()[0]["notify_privacy_mode"], True)
        self.shown.clear()
        self.pet.speech.clear()                       # the "privacy on" toast is gone
        self.pet.relay_notifications(ITEMS[1:2])
        bubble = self.shown[-1]
        self.assertNotIn("TEST-TITLE-B", bubble.text + bubble.header)
        self.assertNotIn("SECRET-BODY-B", bubble.text + bubble.header)
        self.assertIn("Teams", bubble.text)
        self.assertEqual(self.pet.recent_notifications[-1]["title"], "TEST-TITLE-B")   # RAM drawer keeps it
        self.pet.toggle_notify_privacy()
        self.assertIs(self.store.load()[0]["notify_privacy_mode"], False)

    def test_relay_off_does_not_poll(self) -> None:
        self.pet.settings["notify_relay"] = False
        with mock.patch.object(self.pet.notif_monitor, "check_new_notifications") as check:
            self.pet.tick_3s()
        check.assert_not_called()

    def test_relay_on_shows_what_the_poll_returned(self) -> None:
        with mock.patch.object(self.pet.notif_monitor, "check_new_notifications", return_value=ITEMS[:2]):
            self.pet.tick_3s()
        self.assertEqual(len(self.pet.recent_notifications), 2)
        self.assertEqual(len(self.shown), 1)


if __name__ == "__main__":
    unittest.main()
