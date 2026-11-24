"""Test PandaPet runtime: character switching, schedule, states, autostart, feeding, bubble, and standby."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os as _os, tempfile as _tempfile
# Never touch the real work/settings.json from tests.
_os.environ.setdefault("PANDA_DATA_DIR", _tempfile.mkdtemp(prefix="panda_test_"))
from app.main import PandaPet, MEMBER_KEYS, VBS_PATH
from app.foods import FOOD_ITEMS

def test_pet_lifecycle():
    pet = PandaPet()
    try:
        # Check initial state
        assert pet.state == "idle"
        assert pet.char_key in MEMBER_KEYS
        from app.sprites import DIRECTIONAL_WALK_LEFT   # bomi, and eunji since 2026-11-22
        expected_len = 5 if pet.char_key in DIRECTIONAL_WALK_LEFT else 4
        assert len(pet.frames) == expected_len, (pet.char_key, list(pet.frames))
        assert all(len(pet.frames[s]) == 4 for s in ("idle", "walk", "cheer", "sleep"))

        # Test hot-swapping all 5 characters
        for key in MEMBER_KEYS:
            pet.switch_character(key, mode="manual")
            assert pet.char_key == key
            assert pet.mode == "manual"
            frame = pet.current_frame()
            assert frame is not None

        # Test horizontal flip for walking left
        pet.set_state("walk")
        pet.direction = -1
        flipped_frame = pet.current_frame()
        assert flipped_frame is not None
        assert pet.char_key in pet.flipped_walk_cache
        assert len(pet.flipped_walk_cache[pet.char_key]) == 4

        # Test auto schedule
        pet.switch_to_auto_schedule()
        assert pet.mode == "auto"
        assert pet.char_key in MEMBER_KEYS
        assert pet._last_auto_date == pet.clock.now().date()

        # Midnight rollover through the real switch_character (tests/test_auto_schedule_rollover.py)
        import datetime as _dt
        today_member = pet.char_key
        pet.switch_character(MEMBER_KEYS[(MEMBER_KEYS.index(today_member) + 1) % 5], mode="auto")
        pet._last_auto_date = pet.clock.now().date() - _dt.timedelta(days=1)
        pet._check_auto_schedule_rollover()
        assert pet.char_key == today_member, (pet.char_key, today_member)
        assert pet._last_auto_date == pet.clock.now().date()

        # Test state transitions
        for state in ("walk", "cheer", "sleep", "idle"):
            pet.set_state(state)
            assert pet.state == state
            frame = pet.current_frame()
            assert frame is not None
            if state == "walk":
                pet.step_walk()

        # Test speech bubble toast
        pet._toast("測試氣泡文字！", duration_ms=1000)
        assert pet.active_bubble is not None
        pet._dismiss_toast()
        assert pet.active_bubble is None

        # Test feeding system
        for item in FOOD_ITEMS:
            pet.satiety = 50.0  # a full pet refuses solid food (tests/test_feed_full.py)
            pet.feed(item["id"])
            assert pet.state == "cheer"
        assert pet.runtime.get("cheer_passion", 0) > 0

        # Test sedentary reminder setting
        pet.set_sedentary_interval(45)
        assert pet.settings["sedentary_interval_min"] == 45
        pet.test_sedentary_alert()
        assert pet.active_bubble is not None
        pet._dismiss_toast()

        # Test notification relay toggle
        initial_notif = pet.settings.get("notify_relay", True)
        pet.toggle_notify_relay()
        assert pet.settings.get("notify_relay") != initial_notif
        pet.toggle_notify_relay()
        assert pet.settings.get("notify_relay") == initial_notif

        # Test standby overlay creation & safe close (mock LockWorkStation so tests NEVER lock the OS!)
        import unittest.mock as mock
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as mock_lock:
            pet.settings["standby_lock_workstation"] = False
            pet.open_standby_screen()
            assert pet.standby_overlay is not None
            pet.standby_overlay.handle_exit(None)
            assert pet.standby_overlay is None
            assert not mock_lock.called, "LockWorkStation must NEVER be called during test!"

        # Test autostart toggle
        initial_status = pet.is_autostart_enabled()
        pet.toggle_autostart()
        assert pet.is_autostart_enabled() != initial_status
        pet.toggle_autostart()
        assert pet.is_autostart_enabled() == initial_status

        print("[PASS] Full lifecycle verified: 5 members, walk flips, feeding, bubble toasts, standby, and settings working.")
    finally:
        pet.close()

if __name__ == "__main__":
    test_pet_lifecycle()
