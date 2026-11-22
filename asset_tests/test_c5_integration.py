"""C5 integration: user-birthday dialog -> settings -> calendar celebration,
and the host panda turning to face a cameo guest.

Run on a Windows desktop:  python tests/test_c5_integration.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Never touch the real work/settings.json from tests.
os.environ.setdefault("PANDA_DATA_DIR", tempfile.mkdtemp(prefix="panda_test_"))

from app.birthday_dialog import BirthdayDialog  # noqa: E402
from app.cameo_view import CameoActorWindow  # noqa: E402
from app.engine.contracts import CameoPhase  # noqa: E402
from app.main import PandaPet  # noqa: E402


def pump(pet: PandaPet, seconds: float, until=None) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pet.root.update()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until else True


def test_user_birthday_flow() -> None:
    data = Path(tempfile.mkdtemp(prefix="panda_bday_"))
    pet = PandaPet(data_dir=data)
    try:
        pet.window.update()
        pet.calendar.enable_hourly_chime = False

        # Dialog: invalid date shows an error and keeps the dialog open.
        saved = []
        dlg = BirthdayDialog(pet.root, None, "", on_save=lambda *a: saved.append(a))
        dlg.month.delete(0, "end"); dlg.month.insert(0, "2")
        dlg.day.delete(0, "end"); dlg.day.insert(0, "30")
        dlg.save()
        assert saved == [] and dlg.error.cget("text"), "invalid date must be rejected"
        dlg.day.delete(0, "end"); dlg.day.insert(0, "14")
        dlg.nickname.delete(0, "end"); dlg.nickname.insert(0, "小熊貓")
        dlg.save()
        assert saved == [(2, 14, "小熊貓")]

        # Saving goes to settings + calendar and survives a restart.
        pet.set_user_birthday(2, 14, "小熊貓")
        assert pet.settings["user_birthday"] == "02-14"
        assert pet.calendar.user_birthday == (2, 14)
        pet.close()
        pet = PandaPet(data_dir=data)
        pet.window.update()
        pet.calendar.enable_hourly_chime = False
        assert pet.calendar.user_birthday == (2, 14) and pet.calendar.user_nickname == "小熊貓"

        # On the day: L3 celebration with the nickname, header without doubled emoji.
        pet.clock.set_target_date(2027, 2, 14, hour=10)
        pet.poll_calendar()
        pet.coord.on_frame_boundary()
        active = pet.coord.snapshot().active
        assert active is not None and active.request.kind == "calendar.birthday.user"
        cur = pet.speech.current
        assert cur is not None and "小熊貓" in cur.text, cur
        assert not cur.header.startswith("🎉 🎉"), cur.header

        # Clearing removes it.
        pet.set_user_birthday(None, None, "小熊貓")
        assert pet.settings["user_birthday"] == "" and pet.calendar.user_birthday is None
        print("[PASS] user birthday: dialog validation, persisted, celebrated with nickname, clearable.")
    finally:
        pet.close()


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_host_faces_guest(_mock_idle) -> None:
    pet = PandaPet(data_dir=Path(tempfile.mkdtemp(prefix="panda_face_")))
    try:
        pet.window.update()
        pet.cameo._perform_s = 2.0
        sw = pet.window.winfo_screenwidth()
        # Host at the right edge -> guest must stand on the LEFT -> host faces left.
        pet.x = sw - pet.width
        pet.window.geometry(f"+{pet.x}+{pet.y}")
        assert pet.start_cameo(manual=True, guest="eunji")
        script = pet.cameo.run.script
        assert pump(pet, script.enter_s + 2, lambda: pet._cameo_phase is CameoPhase.PERFORM)
        assert pet.face_override == -1
        # rendered frame is the mirrored one
        mirrored = pet.sprites.load_member(pet.char_key, pet.root).get(pet.state, -1)
        assert pet.current_frame() in mirrored
        assert pump(pet, script.perform_s + script.exit_s + 2, lambda: pet.cameo_window is None)
        assert pet.face_override is None, "facing must reset after the visit"
        print("[PASS] host turns to face the guest during the visit and resets afterwards.")
    finally:
        pet.close()


@mock.patch("app.main.get_system_idle_seconds", return_value=0.0)
def test_cameo_on_secondary_monitor(_mock_idle) -> None:
    """Guest walks in on the host's monitor, also one at negative coordinates."""
    from app.platform.win32 import WorkArea

    pet = PandaPet(data_dir=Path(tempfile.mkdtemp(prefix="panda_mon_")))
    try:
        pet.window.update()
        pet.cameo._perform_s = 1.0
        left_monitor = WorkArea(-1920, 0, 0, 1040)
        pet.desktop.work_area_for_point = lambda x, y: left_monitor
        pet.x, pet.y = -900, 500  # place the host inside the simulated left work area
        xs: list[float] = []
        alphas: list[float] = []
        widths: list[int] = []
        real_render = CameoActorWindow.render
        def capture(window, frame, now_ms, area):
            assert area == left_monitor
            xs.append(frame.x)
            alphas.append(frame.alpha)
            real_render(window, frame, now_ms, area)
            window.win.update_idletasks()
            if window.win.winfo_ismapped():
                x, y = window.win.winfo_rootx(), window.win.winfo_rooty()
                w, h = window.win.winfo_width(), window.win.winfo_height()
                assert area.left <= x < x + w <= area.right, (x, w, area)
                assert area.top <= y < y + h <= area.bottom, (y, h, area)
                widths.append(w)
        # Capture the synchronous first render too, with genuinely cold Bomi
        # sprites. Prewarming would conceal an ENTER timing regression.
        with mock.patch.object(CameoActorWindow, "render", new=capture):
            assert pet.start_cameo(manual=True, guest="bomi")
            script = pet.cameo.run.script
            assert pump(pet, script.enter_s + script.perform_s + script.exit_s + 2,
                        lambda: pet.cameo_window is None)
        assert xs, "cameo never rendered"
        assert alphas[0] < 1 and 1 in alphas, alphas
        assert widths and min(widths) < max(widths), widths
        lo, hi = left_monitor.left - pet.width, left_monitor.right
        assert all(lo <= x <= hi for x in xs), (min(xs), max(xs))
        edge_gap = min(abs(xs[0] - lo), abs(xs[0] - hi))
        assert edge_gap < 200, f"guest must enter from an edge of the host's monitor: {xs[0]}"
        print("[PASS] cameo guest stays on the host's (negative-coordinate) monitor.")
    finally:
        pet.close()


if __name__ == "__main__":
    test_user_birthday_flow()
    test_host_faces_guest()
    test_cameo_on_secondary_monitor()
