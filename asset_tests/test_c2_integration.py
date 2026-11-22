"""C2 integration: main.py <-> StateCoordinator / SpeechQueue conflict fixes.

Creates a real PandaPet (Tk window, tray, hotkey) — run on a Windows desktop:
    python tests/test_c2_integration.py
"""
from __future__ import annotations

import sys
import time
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import ActorState, GlobalMode, Priority  # noqa: E402
import os as _os, tempfile as _tempfile
# Never touch the real work/settings.json from tests.
_os.environ.setdefault("PANDA_DATA_DIR", _tempfile.mkdtemp(prefix="panda_test_"))
from app.main import PandaPet  # noqa: E402


class _Ev:
    def __init__(self, x: int, y: int) -> None:
        self.x_root, self.y_root = x, y


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_c2_conflicts(_os_idle) -> None:
    pet = PandaPet()
    pet.calendar.enable_hourly_chime = False
    try:
        pet.window.update()

        # 1. A system reminder must not overwrite a visible notification bubble.
        assert pet._toast("通知 A", priority=Priority.SYSTEM, kind="notify.relay")
        first = pet.active_bubble
        assert not pet._toast("久坐提醒", priority=Priority.SYSTEM, kind="reminder")
        assert pet.active_bubble is first, "SYSTEM bubble was overwritten"
        assert [r.text for r in pet.speech.pending()] == ["久坐提醒"]
        first.dismiss()  # user clicks it away -> queued one follows
        pet._pump_speech()
        assert pet.speech.current is not None and pet.speech.current.text == "久坐提醒"
        pet._dismiss_toast()

        # 2. Spontaneous chatter is dropped while a bubble is up.
        pet._toast("使用者聊天")
        assert not pet._toast("閒聊", priority=Priority.SPONTANEOUS)
        assert all(r.text != "閒聊" for r in pet.speech.pending())
        pet._dismiss_toast()
        pet.speech.clear()

        # 3. Spontaneous cheer must not wake a sleeping pet; system cheer may.
        pet._set_ambient("sleep")
        assert not pet.trigger_cheer(priority=Priority.SPONTANEOUS, wakes_sleep=False)
        assert pet.state == "sleep"

        # 4. A plain click (press/release without movement) does not cancel a cheer.
        pet._set_ambient("idle")
        pet.trigger_cheer(cycles=3, kind="feed")
        assert pet.state == "cheer"
        pet.drag_begin(_Ev(500, 500))
        pet.drag_move(_Ev(501, 500))      # below threshold
        pet.drag_end(_Ev(501, 500))
        assert pet.state == "cheer", "click must not interrupt the cheer"

        # 5. Real drag preempts, shows DRAGGED (idle sprite), wakes from sleep.
        pet._set_ambient("sleep")
        pet.drag_begin(_Ev(500, 500))
        pet.drag_move(_Ev(540, 500))
        assert pet.coord.actor_state is ActorState.DRAGGED
        assert pet.coord.snapshot().active is None
        pet.drag_end(_Ev(540, 500))
        assert pet.state == "idle"

        # 6. Standby: system events/bubbles are parked, pet never pops up on top.
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock, \
             mock.patch("app.main.is_workstation_locked", return_value=False):
            pet.settings["standby_lock_workstation"] = False
            pet.open_standby_screen()
            # This checks coordinator parking and an explicit programmatic exit,
            # not external desktop input. Ignore real pointer/key events while
            # Tk drains its queue (the motion-to-exit contract is tested elsewhere).
            for window in (pet.standby_overlay.win, *(c["win"] for c in pet.standby_overlay.covers)):
                for event in ("<Motion>", "<ButtonPress>", "<Key>"):
                    window.unbind(event)
            pet.window.update()
            assert pet.coord.mode is GlobalMode.STANDBY
            assert not pet._toast("通知 B", priority=Priority.SYSTEM, kind="notify.relay")
            pet.trigger_cheer(priority=Priority.SYSTEM, kind="notify.relay")
            pet.coord.tick()
            pet._pump_speech()
            pet.window.update()
            assert pet.active_bubble is None
            assert not pet.window.winfo_viewable(), "pet floated above standby"
            assert pet.coord.snapshot().active is None

            pet.standby_overlay.handle_exit(None)
            deadline = time.monotonic() + 5
            while pet.coord.mode is not GlobalMode.NORMAL and time.monotonic() < deadline:
                pet.root.update()
                time.sleep(0.01)
            assert not lock.called
        assert pet.coord.mode is GlobalMode.NORMAL
        # welcome-back (USER) shows first, the parked notification waits behind it
        assert pet.speech.current is not None
        assert any(r.text == "通知 B" for r in pet.speech.pending())

        print("[PASS] C2 conflict fixes verified: bubble queue, sleep guard, click vs drag, standby parking.")
    finally:
        pet.close()


if __name__ == "__main__":
    test_c2_conflicts()
