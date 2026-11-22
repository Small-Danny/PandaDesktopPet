"""End-user build: celebration previews / debug entries are developer-only, and the
standby overlay does not lock Windows a second time after a real lock + unlock.

Run:  python -m unittest tests.test_enduser_build -v
"""
from __future__ import annotations

import os
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.i18n import t  # noqa: E402
from app.paths import is_developer_mode  # noqa: E402
from app.pink_context_menu import build_pet_context_menu_items  # noqa: E402
from app.standby import PandaStandbyOverlay  # noqa: E402
from tests.test_pink_context_menu import _DummyPet  # noqa: E402

RELEASE_FESTIVAL_PREVIEW_KEYS = (
    "preview_event_new_year",
    "preview_event_lunar_ny",
    "preview_event_lantern",
    "preview_event_mid_autumn",
    "preview_event_christmas",
)
DEV_ONLY_PREVIEW_KEYS = (
    "special_move_birthday_all",
    "preview_event_user_birthday",
    "preview_event_419",
    "preview_event_newyearseve",
    "preview_event_musical",
    "preview_event_dome_baseball",
    "preview_event_dome_eunji",
    "debug_panel",
    "dev_tools_menu",
)


def _labels(items, seen=None) -> set[str]:
    seen = set() if seen is None else seen
    found: set[str] = set()
    for item in items:
        if id(item) in seen:
            continue
        seen.add(id(item))
        found.add(item.label)
        if item.submenu:
            found |= _labels(item.submenu, seen)
    return found


class DeveloperModeTest(unittest.TestCase):
    def test_source_is_developer_mode_and_packaged_exe_is_not(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PANDA_DEV", None)
            self.assertTrue(is_developer_mode({}))
            with mock.patch.object(sys, "frozen", True, create=True):
                self.assertFalse(is_developer_mode({}))
                self.assertTrue(is_developer_mode({"developer_mode": True}))
                with mock.patch.dict(os.environ, {"PANDA_DEV": "1"}):
                    self.assertTrue(is_developer_mode({}))
            self.assertFalse(is_developer_mode({"developer_mode": False}))
            with mock.patch.dict(os.environ, {"PANDA_DEV": "0"}):
                self.assertFalse(is_developer_mode({"developer_mode": True}))

    def test_end_user_menu_shows_holiday_previews_and_hides_dev_tools(self) -> None:
        pet = _DummyPet(char_key="bomi")
        pet.developer_mode = True
        dev = _labels(build_pet_context_menu_items(pet))
        pet.developer_mode = False
        user = _labels(build_pet_context_menu_items(pet))
        for key in RELEASE_FESTIVAL_PREVIEW_KEYS:
            self.assertIn(t(key, "zh_TW"), dev, key)
            self.assertIn(t(key, "zh_TW"), user, key)
        for key in DEV_ONLY_PREVIEW_KEYS:
            self.assertIn(t(key, "zh_TW"), dev, key)
            self.assertNotIn(t(key, "zh_TW"), user, key)
        # Everything else, including standby backdrops & 5 major festival previews, is unchanged.
        self.assertEqual(dev - user, {t(key, "zh_TW") for key in DEV_ONLY_PREVIEW_KEYS})
        for key in ("preview_standby_christmas", "preview_standby_campfire", "special_move_gorilla"):
            self.assertIn(t(key, "zh_TW"), user, key)

    def test_dev_tools_live_in_their_own_submenu(self) -> None:
        pet = _DummyPet(char_key="bomi")
        pet.developer_mode = True
        items = build_pet_context_menu_items(pet)
        dev_row = next(item for item in items if item.tag_id == "row_dev")
        dev_labels = [item.label for item in dev_row.submenu if not item.is_separator]
        self.assertEqual(dev_labels[0], t("debug_panel", "zh_TW"))
        self.assertEqual(set(dev_labels), {t(key, "zh_TW") for key in DEV_ONLY_PREVIEW_KEYS if key != "dev_tools_menu"})
        others = [item for item in items if item.tag_id != "row_dev"]
        self.assertFalse(_labels(others) & set(dev_labels))       # signature moves / language stay lean
        self.assertEqual(items[-1].tag_id, "row_exit")

    def test_panda_dev_0_hides_dev_tools_even_when_settings_ask(self) -> None:
        pet = _DummyPet(char_key="bomi")
        pet.developer_mode = None
        pet.settings = {"developer_mode": True}
        with mock.patch.dict(os.environ, {"PANDA_DEV": "0"}):
            items = build_pet_context_menu_items(pet)
        self.assertNotIn("row_dev", {item.tag_id for item in items})
        labels = _labels(items)
        for key in DEV_ONLY_PREVIEW_KEYS:
            self.assertNotIn(t(key, "zh_TW"), labels, key)


class LauncherBatchTest(unittest.TestCase):
    """The .bat launchers are pure 7-bit ASCII CRLF (windows-automation-harness) and fail closed cleanly."""

    def test_launchers_are_ascii_crlf(self) -> None:
        for name in ("debug_run.bat", "LaunchPandaPet.bat", "build_exe.bat"):
            data = (ROOT / name).read_bytes()
            with self.subTest(name=name):
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"))     # a BOM breaks "@echo off"
                self.assertTrue(all(b <= 127 for b in data), f"{name} must be pure 7-bit ASCII")
                self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
                self.assertGreater(data.count(b"\r\n"), 3)
                text = data.decode("ascii")
                self.assertIn('cd /d "%~dp0"', text)
                self.assertNotIn('BASE=%~dp0', text)

    def test_debug_runner_explains_a_duplicate_pet_and_pauses(self) -> None:
        text = (ROOT / "debug_run.bat").read_bytes().decode("ascii")
        self.assertIn("PANDA_DUPLICATE_EXIT_CODE=3", text)
        self.assertIn("PandaDesktopPet.exe", text)
        self.assertIn("ASSETS_REQUIRED.md", text)
        self.assertIn("exit /b %PANDA_EXIT%", text)
        self.assertGreaterEqual(text.count("pause"), 2)

    @unittest.skipUnless(sys.platform == "win32", "cmd.exe batch runner")
    def test_debug_runner_reports_the_duplicate_exit_code(self) -> None:
        import shutil
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            shutil.copy(ROOT / "debug_run.bat", td)
            (Path(td) / "app").mkdir()
            (Path(td) / "work").mkdir()
            (Path(td) / "work" / "asset_registry.json").write_text("{}", encoding="utf-8")
            (Path(td) / "app" / "main.py").write_text(
                "import os, sys\nsys.exit(int(os.environ['PANDA_DUPLICATE_EXIT_CODE']))\n", encoding="utf-8")
            env = dict(os.environ, CI="1", PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
            result = subprocess.run(["cmd.exe", "/c", str(Path(td) / "debug_run.bat")], input=b"\r\n",
                                    capture_output=True, timeout=30, env=env)
        self.assertEqual(result.returncode, 3)
        self.assertIn("already be running", result.stdout.decode("ascii", "replace"))

    @unittest.skipUnless(sys.platform == "win32", "cmd.exe batch runner")
    def test_all_launchers_fail_closed_with_exit_code_2_when_assets_missing(self) -> None:
        import shutil
        import subprocess
        import tempfile
        for name in ("debug_run.bat", "LaunchPandaPet.bat", "build_exe.bat"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                shutil.copy(ROOT / name, td)
                (Path(td) / "app").mkdir()
                (Path(td) / "app" / "main.py").write_text("raise AssertionError('should not run')\n", encoding="utf-8")
                env = dict(os.environ, CI="1")
                result = subprocess.run(["cmd.exe", "/c", str(Path(td) / name)], input=b"\r\n",
                                        capture_output=True, timeout=30, env=env)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("ASSETS_REQUIRED.md", result.stdout.decode("ascii", "replace"))

    def test_main_duplicate_exit_code_is_opt_in(self) -> None:
        source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("PANDA_DUPLICATE_EXIT_CODE", "0")', source)


class StandbyRealLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.closed = 0
        self.locked: bool | None = False

    def _overlay(self) -> PandaStandbyOverlay:
        def closed() -> None:
            self.closed += 1

        overlay = PandaStandbyOverlay(
            parent=self.root, char_key="chorong", char_name="Chorong", frames={}, flipped_walk_frames=[],
            on_close=closed, lock_on_exit=True, scene="starfield", wallpapers=(),
            lock_probe=lambda: self.locked,
        )
        overlay.win.unbind("<Motion>")
        overlay.win.unbind("<ButtonPress>")
        return overlay

    def _pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)

    def test_real_lock_then_unlock_closes_without_locking_again(self) -> None:
        with mock.patch("app.standby.LOCK_WATCH_MS", 30), \
                mock.patch("ctypes.windll.user32.LockWorkStation", create=True) as lock, \
                mock.patch.object(sys, "argv", ["panda"]):
            had_flag = hasattr(sys, "_running_tests")
            saved = getattr(sys, "_running_tests", None)
            if had_flag:
                del sys._running_tests
            try:
                overlay = self._overlay()
                self._pump(0.2)
                self.assertTrue(overlay.running)            # unlocked all along: nothing happens
                self.locked = None
                self._pump(0.2)
                self.assertTrue(overlay.running)            # unknown is not "locked"
                self.locked = True
                self._pump(0.2)
                self.assertTrue(overlay.running)            # stays up behind the lock screen
                self.locked = False
                self._pump(0.3)
                self.assertFalse(overlay.running)
                self.assertEqual(self.closed, 1)
                lock.assert_not_called()

                # Without a real lock, leaving standby still locks as before.
                overlay = self._overlay()
                self._pump(0.2)
                overlay.handle_exit(None)
                lock.assert_called_once()
                self.assertEqual(self.closed, 2)
            finally:
                if had_flag:
                    sys._running_tests = saved


if __name__ == "__main__":
    unittest.main()
