"""C2b integration: CalendarScheduler (L3) + PersistenceService wired into main.py.

Creates real PandaPet windows — run on a Windows desktop:
    python tests/test_c2b_integration.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import tempfile
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

import app.main as main_mod  # noqa: E402
from app.engine.contracts import GlobalMode  # noqa: E402
from app.main import PandaPet  # noqa: E402


def _fresh_pet(data_dir: Path) -> PandaPet:
    return PandaPet(data_dir=data_dir)


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_storage_split_and_legacy_migration(_os_idle) -> None:
    data = Path(tempfile.mkdtemp(prefix="panda_legacy_"))
    (data / "settings.json").write_text(json.dumps({
        "mode": "manual", "manual_character": "bomi", "cheer_passion": 100,
        "feed_count": 7, "sedentary_interval_min": 45, "notify_relay": True,
        "standby_lock_workstation": False, "lang": "zh_TW",
    }), encoding="utf-8")
    pet = _fresh_pet(data)
    try:
        assert pet.char_key == "bomi"
        assert pet.runtime["feed_count"] == 7 and pet.runtime["cheer_passion"] == 100
        assert "cheer_passion" not in pet.settings
        # New profiles start full; migration persistence is tested with a
        # genuinely accepted feed, not a full-pet solid-food refusal.
        pet.satiety = 20.0
        pet.feed(main_mod.FOOD_ITEMS[0]["id"])
        runtime = json.loads((data / "runtime.json").read_text(encoding="utf-8"))
        settings = json.loads((data / "settings.json").read_text(encoding="utf-8"))
        assert runtime["schema_version"] == 1 and runtime["data"]["feed_count"] == 8
        assert "feed_count" not in settings["data"]
        assert pet._persist_errors == [], "plain migration must not raise a warning bubble"
    finally:
        pet.close()
    print("[PASS] legacy settings migrated; settings/runtime saved separately.")


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_calendar_birthday_and_standby(_os_idle) -> None:
    pet = _fresh_pet(Path(tempfile.mkdtemp(prefix="panda_cal_")))
    try:
        pet.window.update()
        pet.calendar.enable_hourly_chime = False

        # Birthday: L3 soft preempt -> starts on frame boundary -> bubble in sync.
        pet.clock.set_target_date(2027, 3, 3, hour=12)
        pet.poll_calendar()
        assert pet.coord.snapshot().pending_id is not None
        assert pet.active_bubble is None, "bubble must wait for the event to start"
        pet.coord.on_frame_boundary()
        active = pet.coord.snapshot().active
        assert active is not None and active.request.kind == "calendar.birthday.chorong"
        assert pet.speech.current is not None and "初瓏" in pet.speech.current.text
        pet.poll_calendar()  # same day: nothing new
        assert pet.coord.snapshot().queue == ()
        pet.coord.cancel(active.event_id)
        pet._dismiss_toast()

        # 419 during standby: parked (long TTL), plays once after standby ends.
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True), \
             mock.patch("app.main.is_workstation_locked", return_value=False):
            pet.settings["standby_lock_workstation"] = False
            pet.open_standby_screen()
            pet.clock.set_target_date(2027, 4, 19, hour=12)
            pet.poll_calendar()
            pet.coord.tick()
            assert pet.coord.mode is GlobalMode.STANDBY
            assert pet.coord.snapshot().active is None
            assert len(pet.coord.snapshot().queue) == 1
            pet.standby_overlay.handle_exit(None)
            deadline = time.monotonic() + 5
            while pet.coord.mode is not GlobalMode.NORMAL and time.monotonic() < deadline:
                pet.root.update()
                time.sleep(0.01)
            assert pet.coord.mode is GlobalMode.NORMAL
        # welcome-back USER cheer preempts; the anniversary is requeued, then runs
        kinds = [pet.coord.snapshot().active.request.kind]
        pet.clock.base = _Shifted(pet.clock.base, 10)  # let the welcome cheer expire
        pet.coord.tick()
        kinds.append(pet.coord.snapshot().active.request.kind)
        assert kinds[-1] == "calendar.anniversary.apink419", kinds
        texts = [pet.speech.current.text] + [r.text for r in pet.speech.pending()]
        assert sum("419" in t for t in texts) == 1, texts
    finally:
        pet.close()
    print("[PASS] calendar birthday synced with bubble; 419 parked through standby, spoken once.")


class _Shifted:
    """Base clock advanced by a fixed number of seconds (monotonic + wall)."""

    def __init__(self, base, seconds: float) -> None:
        self._base, self._s = base, seconds

    def now(self):
        import datetime as dt
        return self._base.now() + dt.timedelta(seconds=self._s)

    def monotonic(self) -> float:
        return self._base.monotonic() + self._s


if __name__ == "__main__":
    test_storage_split_and_legacy_migration()
    test_calendar_birthday_and_standby()
