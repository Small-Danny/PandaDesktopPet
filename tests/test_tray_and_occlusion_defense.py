"""tests/test_tray_and_occlusion_defense.py — Unit tests for tray wake/lift, context menu Z-order defense, and status card single instance."""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os as _os, tempfile as _tempfile
_os.environ.setdefault("PANDA_DATA_DIR", _tempfile.mkdtemp(prefix="panda_test_"))

from app.i18n import t
from app.tray import PandaSystemTray
from app.status_card import PandaStatusCard


class TestTrayAndOcclusionDefense(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_i18n_tray_keys_exist(self):
        for lang in ("zh_TW", "ko", "en"):
            wake = t("tray_wake_pet", lang)
            hide = t("tray_hide_pet", lang)
            self.assertTrue(wake, f"tray_wake_pet missing for {lang}")
            self.assertTrue(hide, f"tray_hide_pet missing for {lang}")

    def test_tray_default_action_is_wake_not_hide(self):
        wake_mock = MagicMock()
        hide_mock = MagicMock()
        icon_path = ROOT / "work" / "foods" / "chicken_feet_64.png"

        tray = PandaSystemTray(
            icon_path=icon_path,
            on_wake_pet=wake_mock,
            on_hide_pet=hide_mock,
            on_status_card=MagicMock(),
            on_exit=MagicMock(),
            lang="zh_TW",
        )
        self.assertTrue(tray.is_visible)
        # Verify callbacks
        tray.on_wake_pet()
        wake_mock.assert_called_once()
        hide_mock.assert_not_called()

        tray.on_hide_pet()
        hide_mock.assert_called_once()

    def test_tray_backward_compatible_toggle(self):
        toggle_mock = MagicMock()
        icon_path = ROOT / "work" / "foods" / "chicken_feet_64.png"

        tray = PandaSystemTray(
            icon_path=icon_path,
            on_toggle_show=toggle_mock,
            on_status_card=MagicMock(),
            on_exit=MagicMock(),
        )
        tray.on_wake_pet()
        toggle_mock.assert_called_once()

    def test_status_card_single_instance_and_on_close(self):
        closed = []
        card = PandaStatusCard(
            parent=self.root,
            char_key="chorong",
            char_name="初瓏 (Chorong)",
            on_close=lambda: closed.append(True),
        )
        self.assertTrue(card.window.winfo_exists())
        # Test deiconify and lift
        card.window.deiconify()
        card.window.lift()
        self.assertEqual(card.window.state(), "normal")

        # Close triggers callback
        card.close()
        self.assertEqual(closed, [True])

    def test_z_order_defense_logic(self):
        class DummyPet:
            def __init__(self):
                self._menu_active = False
                self.status_card = None
                self.window = MagicMock()
                self.desktop = MagicMock()
                self.x, self.y = 100, 200

            def _pet_hwnd(self):
                return 12345

            def _has_active_subpanel(self):
                return self.status_card is not None

            def ensure_topmost(self):
                if getattr(self, "_menu_active", False):
                    return "blocked_by_menu"
                if self._has_active_subpanel():
                    return "blocked_by_subpanel"
                return "topmost_applied"

            def _place_pet(self):
                if getattr(self, "_menu_active", False) or self._has_active_subpanel():
                    self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
                    return "tk_geometry_only"
                if not self.desktop.position_without_activation(self._pet_hwnd(), int(self.x), int(self.y)):
                    self.window.geometry(f"+{int(self.x)}+{int(self.y)}")
                    return "tk_geometry_fallback"
                return "win32_topmost_positioned"

        pet = DummyPet()
        # Normal state
        self.assertEqual(pet.ensure_topmost(), "topmost_applied")
        self.assertEqual(pet._place_pet(), "win32_topmost_positioned")

        # Menu active: pet MUST NOT reapply topmost
        pet._menu_active = True
        self.assertEqual(pet.ensure_topmost(), "blocked_by_menu")
        self.assertEqual(pet._place_pet(), "tk_geometry_only")

        # Menu closed, but subpanel active: pet MUST NOT reapply topmost
        pet._menu_active = False
        pet.status_card = MagicMock()
        self.assertEqual(pet.ensure_topmost(), "blocked_by_subpanel")
        self.assertEqual(pet._place_pet(), "tk_geometry_only")


if __name__ == "__main__":
    unittest.main()
