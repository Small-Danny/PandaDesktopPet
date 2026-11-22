"""test_disappearing_panda_fix.py — Verifies anti-disappearing, topmost, and bubble-roam lock guards.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os as _os, tempfile as _tempfile
# Never touch the real work/settings.json from tests.
_os.environ.setdefault("PANDA_DATA_DIR", _tempfile.mkdtemp(prefix="panda_test_"))
from app.main import PandaPet


def test_guards() -> None:
    pet = PandaPet()

    # 1. Test ensure_topmost executes safely
    pet.ensure_topmost()
    assert pet.window.winfo_exists()

    # 2. Test Roam AI Lock when bubble is active
    pet.set_state("idle")
    # Simulate an active bubble
    class DummyBubble:
        pass
    pet.active_bubble = DummyBubble()  # type: ignore

    # check_roam_ai should immediately return and NOT change state to walk
    pet.next_roam_time = 0
    pet.check_roam_ai()
    assert pet.state == "idle", "Pet should NOT roam while bubble is active!"

    # 3. Test step_walk pauses if bubble is active
    pet.state = "walk"
    pet.step_walk()
    assert pet.state == "idle", "step_walk must immediately pause to idle if bubble is active!"
    assert pet.target_roam_x is None

    # Clear dummy bubble
    pet.active_bubble = None

    # 4. Test Toast auto-restores if pet was hidden in tray
    pet.hide_to_tray()
    assert not pet.window.winfo_viewable(), "Window should be withdrawn"

    # Trigger a toast -> must auto deiconify pet so bubble is never orphaned
    pet._toast("測試訊息", duration_ms=1000)
    assert pet.state == "idle", "Pet must be idle immediately when speaking"
    pet.window.update()
    assert pet.window.winfo_viewable(), "Window must be deiconified when toast arrives!"

    # 5. Clean close
    pet.close()
    print("[PASS] All anti-disappearing guards, topmost locks, and bubble-roam sync verified successfully!")


if __name__ == "__main__":
    test_guards()

