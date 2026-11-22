"""C4 integration: cameo guest window lifecycle in a real Tk session.

Run on a Windows desktop (takes ~15 s, drives the real event loop):
    python tests/test_c4_integration.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.engine.contracts import CameoPhase, GlobalMode  # noqa: E402
from app.main import PandaPet  # noqa: E402


def pump(pet: PandaPet, seconds: float, until=None) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pet.root.update()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until else True


class _Ev:
    def __init__(self, x: int, y: int) -> None:
        self.x_root, self.y_root = x, y


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_cameo_lifecycle(_os_idle) -> None:
    pet = PandaPet()
    pet.calendar.enable_hourly_chime = False
    try:
        pet.window.update()
        pet.cameo._perform_s = 3.0   # keep the test short
        pet.x = 200
        pet.window.geometry(f"+{pet.x}+{pet.y}")

        # Uses only approved registry sprites.
        assert pet.sprites.load_member(pet.char_key, pet.root).source == "registry"

        # 1. Manual invite: guest window + stage reserved, host stands still.
        assert pet.start_cameo(manual=True)
        guest = pet.cameo.run.guest
        assert guest != pet.char_key
        assert pet.coord.mode is GlobalMode.CAMEO
        win = pet.cameo_window
        script = pet.cameo.run.script
        assert pump(pet, script.enter_s + 2, lambda: pet._cameo_phase is CameoPhase.PERFORM)
        assert win.win.winfo_viewable()
        assert abs(win.win.winfo_x() - (pet.x + pet.width + 8)) <= 2, "guest stands next to host"
        # guest line is shown above the guest, not the host
        assert pet.speech.current is not None and pet.speech.current.kind == "cameo.guest"
        assert pet.speech.current.anchor[0] == int(pet.cameo.run.stand_x)

        # 2. Normal flow: host reply, wave, trot off-screen, window destroyed.
        assert pump(pet, script.perform_s + script.exit_s + 2, lambda: pet.cameo_window is None)
        assert pet.coord.snapshot().active is None
        assert pet.coord.mode is GlobalMode.NORMAL

        # 3. Drag interrupt: graceful 0.8 s exit, not instant.
        assert pet.start_cameo(manual=True)
        assert pump(pet, pet.cameo.run.script.enter_s + 2, lambda: pet._cameo_phase is CameoPhase.PERFORM)
        pet.drag_begin(_Ev(pet.x + 50, pet.y + 50))
        pet.drag_move(_Ev(pet.x + 90, pet.y + 50))
        t0 = time.monotonic()
        pump(pet, 0.15)
        assert pet.cameo_window is not None, "guest must not vanish instantly"
        assert pet.speech.current is None or not pet.speech.current.kind.startswith("cameo")
        assert pump(pet, 3, lambda: pet.cameo_window is None)
        took = time.monotonic() - t0
        assert 0.6 <= took <= 1.5, f"interrupted exit took {took:.2f}s"
        pet.drag_end(_Ev(pet.x + 90, pet.y + 50))

        # 4. Standby covers the screen: cameo dropped at once, no stray window.
        assert pet.start_cameo(manual=True)
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True), \
             mock.patch("app.main.is_workstation_locked", return_value=False):
            pet.settings["standby_lock_workstation"] = False
            pet.open_standby_screen()
            assert pet.cameo_window is None and pet.cameo.run is None
            assert not pet.start_cameo(manual=True), "no cameo during standby"
            pet.standby_overlay.handle_exit(None)
            assert pump(pet, 5, lambda: pet.coord.mode is GlobalMode.NORMAL)

        # 5. Automatic visits respect settings and user presence.
        pet._stop_cameo()
        pet.next_cameo_at = 0
        pet.settings["cameo_enabled"] = False
        pet.maybe_auto_cameo(os_idle=0)
        assert pet.cameo_window is None
        pet.settings["cameo_enabled"] = True
        pet.maybe_auto_cameo(os_idle=600)            # user away -> postponed
        assert pet.cameo_window is None and pet.next_cameo_at > time.time()

        print("[PASS] C4 cameo: enter/perform/exit, anchored speech, drag interrupt 0.8 s, standby drop, auto gating.")
    finally:
        pet.close()


if __name__ == "__main__":
    test_cameo_lifecycle()
