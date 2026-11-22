"""Integration & regression tests for Q1 (5 holiday previews + first-encounter welcome),
Q2 (compact corner standby clock, H-key pure wallpaper mode, appearance setting, 7 wallpapers + multi-DPI),
and Q3 (thread-safe LRU caches, bounded bytes, background warmup manager & cancellation).

Run:  python -B -m unittest tests.test_holiday_previews_and_standby_modes -v
"""
from __future__ import annotations

import datetime as dt
import gc
import json
import os
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.asset_images import AssetImageCache  # noqa: E402
from app.daily_actions import (  # noqa: E402
    LANTERN,
    LUNAR_NY,
    MID_AUTUMN_FESTIVAL,
    NEW_YEAR,
    festival_occurrence_key,
)
from app.engine.assets import AssetRegistry  # noqa: E402
from app.engine.calendar import OffsetClock  # noqa: E402
from app.engine.contracts import ActorState, EventRequest, GlobalMode, Priority, SystemClock  # noqa: E402
from app.main import PandaPet, SETTINGS_DEFAULTS  # noqa: E402
from app.pink_context_menu import PinkContextMenu  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402
from app.settings_panel import SettingsPanel  # noqa: E402
from app.sprites import SpriteLibrary  # noqa: E402
from app.standby import (  # noqa: E402
    PREPARED_IMAGES,
    PandaStandbyOverlay,
    STAGE_SCENES,
    StandbyWarmupManager,
    _FITTED_WALLPAPER_LOCK,
    _FITTED_WALLPAPERS,
    _fitted_wallpaper,
    clear_standby_caches,
    load_wallpapers,
)
from app.storage.settings import DEFAULT_SETTINGS, PersistenceService  # noqa: E402


class _FakeKey:
    def __init__(self, keysym: str, keycode: int = 0) -> None:
        self.keysym = keysym
        self.keycode = keycode
        self.x = self.y = 0


def _pump(root: tk.Misc, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


class _IsolatedPetMixin:
    def _spawn_pet(
        self,
        *,
        developer_mode: bool = False,
        settings_override: dict | None = None,
        now_dt: dt.datetime | None = None,
    ) -> tuple[PandaPet, Path]:
        td = tempfile.TemporaryDirectory(prefix="panda_q123_")
        self.addCleanup(td.cleanup)
        data_dir = Path(td.name)
        service = PersistenceService(data_dir)
        base_settings = dict(DEFAULT_SETTINGS)
        base_settings["mode"] = "manual"
        base_settings["manual_character"] = "chorong"
        base_settings["onboarding_prompted"] = True
        if settings_override:
            base_settings.update(settings_override)
        service.save(base_settings, {"cheer_passion": 500})

        stack = self._stack  # set by TestCase
        stack.enter_context(mock.patch.dict(os.environ, {"PANDA_DATA_DIR": str(data_dir)}))
        stack.enter_context(mock.patch("app.main.is_developer_mode", return_value=developer_mode))
        stack.enter_context(mock.patch("app.main.PandaSystemTray", return_value=mock.MagicMock()))
        stack.enter_context(mock.patch("app.main.GlobalHotkeyManager", return_value=mock.MagicMock()))
        stack.enter_context(mock.patch("app.main.WindowsNotificationMonitor", return_value=mock.MagicMock()))
        stack.enter_context(mock.patch("app.main.is_workstation_locked", return_value=False))
        stack.enter_context(mock.patch("app.main.get_system_idle_seconds", return_value=0.0))
        stack.enter_context(mock.patch("ctypes.windll.user32.LockWorkStation", create=True))

        pet = PandaPet(data_dir=data_dir)
        self.addCleanup(self._safe_close_pet, pet)
        if now_dt is not None:
            pet.clock.set_target_date(now_dt.year, now_dt.month, now_dt.day, hour=now_dt.hour)
            pet.clock.offset_seconds += now_dt.minute * 60 + now_dt.second
            pet.set_state("idle", manual=True)
            pet._refresh_visual_appearance()
        pet.window.update()
        return pet, data_dir

    @staticmethod
    def _safe_close_pet(pet: PandaPet) -> None:
        try:
            pet.close()
        except Exception:
            pass


class Q1FestivalPreviewAndWelcomeTests(unittest.TestCase, _IsolatedPetMixin):
    def setUp(self) -> None:
        from contextlib import ExitStack

        self.addCleanup(gc.collect)   # runs last: free this pet's Tk objects on the main thread
        self._stack = ExitStack()
        self.addCleanup(self._stack.close)

    def _unseen_lantern_pet(self):
        pet, _ = self._spawn_pet(now_dt=dt.datetime(2026, 3, 3, 12))
        pet._close_group_celebration()
        for token in list(pet._loop_after.values()):
            pet.window.after_cancel(token)
        pet._loop_after.clear()
        pet.runtime['festival_welcome_seen'] = {}
        active = pet.coord.snapshot().active
        if active is not None:
            pet.coord.cancel(active.event_id)
        return pet

    def test_missed_standby_welcome_is_scheduled_on_resume_and_seen_once(self):
        pet = self._unseen_lantern_pet()
        pet.coord.set_mode(GlobalMode.STANDBY)
        self.assertFalse(pet._maybe_festival_welcome())
        self.assertNotIn('festival_welcome', pet._loop_after)
        pet._standby_resume_pending = True
        with mock.patch.object(pet, '_restore_pet_window', return_value=True), \
                mock.patch.object(pet, '_mark_festival_welcome_seen', wraps=pet._mark_festival_welcome_seen) as mark:
            pet._resume_after_standby()
            self.assertIn('festival_welcome', pet._loop_after)
            _pump(pet.window, .6)
            self.assertEqual(mark.call_count, 1)
            self.assertEqual(list(pet.runtime['festival_welcome_seen'].values()), [True])
            self.assertNotIn('festival_welcome', pet._loop_after)
            pet._close_group_celebration()
            _pump(pet.window, .5)
            self.assertEqual(mark.call_count, 1)

    def test_missed_preview_welcome_is_scheduled_after_natural_end(self):
        pet = self._unseen_lantern_pet()
        pet.preview_festival_event(MID_AUTUMN_FESTIVAL.action, 'preview')
        self.assertFalse(pet._maybe_festival_welcome())
        self.assertEqual(pet.runtime['festival_welcome_seen'], {})
        self.assertIn('festival_welcome', pet._loop_after)
        with mock.patch.object(pet, '_mark_festival_welcome_seen', wraps=pet._mark_festival_welcome_seen) as mark:
            pet.group_celebration.close()  # real on_done callback, no manual welcome call
            _pump(pet.window, .6)
            self.assertEqual(mark.call_count, 1)
            self.assertFalse(pet.is_festival_preview_active())
            pet._close_group_celebration()
            _pump(pet.window, .5)
            self.assertEqual(mark.call_count, 1)

    def test_cancel_preview_does_not_close_a_real_celebration(self):
        pet = self._unseen_lantern_pet()
        pet.celebrate_together(host_action=LANTERN.action, guest_action=LANTERN.action,
                              is_preview=False)
        party = pet.group_celebration
        active = pet.coord.snapshot().active
        self.assertIsNotNone(party)
        self.assertFalse(pet.cancel_festival_preview())
        self.assertIs(pet.group_celebration, party)
        self.assertEqual(pet.coord.snapshot().active.event_id, active.event_id)

    def test_cancelled_preview_delivers_the_unseen_real_welcome(self):
        pet = self._unseen_lantern_pet()
        pet.preview_festival_event(MID_AUTUMN_FESTIVAL.action, 'preview')
        self.assertFalse(pet._maybe_festival_welcome())
        self.assertTrue(pet.cancel_festival_preview())
        with mock.patch.object(pet, '_mark_festival_welcome_seen', wraps=pet._mark_festival_welcome_seen) as mark:
            _pump(pet.window, .6)
            self.assertEqual(mark.call_count, 1)
            pet._close_group_celebration()
            _pump(pet.window, .5)
            self.assertEqual(mark.call_count, 1)

    def test_busy_retry_requires_enabled_unseen_festival(self):
        pet = self._unseen_lantern_pet()
        pet.dragging = True
        with mock.patch.object(pet, '_schedule_festival_welcome') as schedule:
            pet.settings['festival_auto_enabled'] = False
            self.assertFalse(pet._maybe_festival_welcome())
            pet.settings['festival_auto_enabled'] = True
            key = festival_occurrence_key(pet.calendar.clock.now().date())[1]
            pet.runtime['festival_welcome_seen'][key] = True
            self.assertFalse(pet._maybe_festival_welcome())
            pet.runtime['festival_welcome_seen'] = {}
            pet.clock.set_target_date(2026, 6, 15)
            self.assertFalse(pet._maybe_festival_welcome())
            schedule.assert_not_called()
        pet.dragging = False

    def test_drag_welcome_retry_and_explicit_seen_cancel_pending_timer(self):
        pet = self._unseen_lantern_pet()
        pet.dragging = True
        with mock.patch.object(pet, '_schedule_festival_welcome', wraps=pet._schedule_festival_welcome) as schedule:
            self.assertFalse(pet._maybe_festival_welcome())
            schedule.assert_called_once_with(delay_ms=1500)
        self.assertEqual(pet.runtime['festival_welcome_seen'], {})
        key = festival_occurrence_key(pet.calendar.clock.now().date())[1]
        pending = pet._loop_after['festival_welcome']
        pet._mark_festival_welcome_seen(key)
        self.assertNotIn('festival_welcome', pet._loop_after)
        self.assertNotIn(pending, pet.window.tk.call('after', 'info'))
        pet.dragging = False
        self.assertFalse(pet._maybe_festival_welcome())

    def test_closed_pet_never_schedules_welcome(self):
        pet = self._unseen_lantern_pet()
        pet.close()
        with mock.patch.object(pet.window, 'after') as after:
            pet._close_group_celebration()
            pet._schedule_festival_welcome()
            after.assert_not_called()

    def test_cameo_retries_unseen_welcome_then_fires_once_when_normal(self):
        pet = self._unseen_lantern_pet()
        request = EventRequest(kind='cameo.welcome_test', priority=Priority.CAMEO,
                               state=ActorState.IDLE, duration_s=20)
        self.assertTrue(pet.coord.submit(request).accepted)
        self.assertEqual(pet.coord.mode, GlobalMode.CAMEO)
        with mock.patch.object(pet, '_schedule_festival_welcome', wraps=pet._schedule_festival_welcome) as schedule:
            self.assertFalse(pet._maybe_festival_welcome())
            schedule.assert_called_once_with(delay_ms=1500)
        self.assertEqual(pet.runtime['festival_welcome_seen'], {})
        pet.coord.cancel(pet.coord.snapshot().active.event_id)
        self.assertEqual(pet.coord.mode, GlobalMode.NORMAL)
        with mock.patch.object(pet, '_mark_festival_welcome_seen', wraps=pet._mark_festival_welcome_seen) as mark:
            _pump(pet.window, 1.7)
            self.assertEqual(mark.call_count, 1)
            pet._close_group_celebration()
            _pump(pet.window, .5)
            self.assertEqual(mark.call_count, 1)

    def test_mark_seen_tolerates_missing_or_destroyed_window(self):
        from types import SimpleNamespace
        for window in (None, mock.Mock()):
            owner = SimpleNamespace(_loop_after={'festival_welcome': 'stale'},
                                    runtime={}, save_settings=mock.Mock())
            if window is not None:
                window.after_cancel.side_effect = tk.TclError('destroyed window')
                owner.window = window
            PandaPet._mark_festival_welcome_seen(owner, 'lantern:test')
            self.assertEqual(owner.runtime['festival_welcome_seen'], {'lantern:test': True})
            self.assertEqual(owner._loop_after, {})
            owner.save_settings.assert_called_once_with()

    def test_release_menu_exposes_five_holidays_and_hides_dev_tools(self) -> None:
        from app.pink_context_menu import build_pet_context_menu_items

        pet, _ = self._spawn_pet(developer_mode=False, now_dt=dt.datetime(2026, 6, 15, 12, 0, 0))
        self.assertFalse(pet.developer_mode)
        all_labels: list[str] = []
        seen: set[int] = set()

        def _walk_items(items) -> None:
            for item in items:
                if id(item) in seen:
                    continue
                seen.add(id(item))
                lbl = getattr(item, "label", None)
                if lbl:
                    all_labels.append(str(lbl))
                sub = getattr(item, "submenu", None)
                if sub:
                    _walk_items(sub)

        _walk_items(build_pet_context_menu_items(pet))
        joined = "\n".join(all_labels)
        from app.i18n import t

        for key in (
            "preview_event_new_year",
            "preview_event_lunar_ny",
            "preview_event_lantern",
            "preview_event_mid_autumn",
            "preview_event_christmas",
        ):
            self.assertIn(t(key, pet.lang), joined)
        for dev_key in (
            "special_move_birthday_all",
            "preview_event_user_birthday",
            "preview_event_419",
            "preview_event_newyearseve",
            "preview_event_musical",
            "preview_event_dome_baseball",
            "preview_event_dome_eunji",
            "debug_panel",
        ):
            self.assertNotIn(t(dev_key, pet.lang), joined)

    def test_five_previews_are_strictly_transient_and_restore_normal_state(self) -> None:
        pet, data_dir = self._spawn_pet(developer_mode=False, now_dt=dt.datetime(2026, 6, 15, 14, 30, 0))
        settings_before = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
        runtime_before = json.loads((data_dir / "runtime.json").read_text(encoding="utf-8"))

        previews = (
            ("new_year", lambda: pet.preview_new_year_event()),
            ("lunar_ny", lambda: pet.preview_festival_event(LUNAR_NY.action, "農曆新年")),
            ("lantern", lambda: pet.preview_festival_event(LANTERN.action, "元宵節")),
            ("mid_autumn", lambda: pet.preview_festival_event(MID_AUTUMN_FESTIVAL.action, "中秋節")),
            ("christmas", lambda: pet.preview_christmas_event()),
        )
        for name, trigger in previews:
            with self.subTest(preview=name):
                trigger()
                self.assertTrue(pet.is_festival_preview_active())
                self.assertIsNotNone(pet.group_celebration)
                self.assertEqual(pet.char_key, "chorong")
                self.assertEqual(pet.mode, "manual")
                self.assertFalse(pet.runtime.get("festival_welcome_seen"))
                self.assertTrue(pet.cancel_festival_preview())
                self.assertFalse(pet.is_festival_preview_active())
                self.assertIsNone(pet.group_celebration)
                self.assertEqual(pet.state, "idle")

        # set_state("sleep") and switch_character also cleanly cancel an active preview.
        pet.preview_festival_event(LANTERN.action, "元宵節")
        self.assertTrue(pet.is_festival_preview_active())
        pet.set_state("sleep", manual=True)
        self.assertFalse(pet.is_festival_preview_active())
        self.assertIsNone(pet.group_celebration)
        pet.set_state("idle", manual=True)

        settings_after = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
        runtime_after = json.loads((data_dir / "runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(settings_after["data"]["mode"], settings_before["data"]["mode"])
        self.assertEqual(settings_after["data"]["manual_character"], settings_before["data"]["manual_character"])
        self.assertEqual(runtime_after["data"].get("festival_welcome_seen", {}), {})
        self.assertEqual(
            runtime_before["data"].get("festival_welcome_seen", {}),
            runtime_after["data"].get("festival_welcome_seen", {}),
        )

    def test_real_festival_welcome_fires_once_and_preview_does_not_consume_it(self) -> None:
        # 2026-03-03 is Lantern Festival
        lantern_day = dt.datetime(2026, 3, 3, 12, 0, 0)
        pet, _ = self._spawn_pet(developer_mode=False, now_dt=lantern_day)
        old_cb = pet._loop_after.pop("festival_welcome", None)
        if old_cb is not None:
            pet.window.after_cancel(old_cb)
        pet.runtime["festival_welcome_seen"] = {}

        # Manual preview of another holiday on a real festival day must NOT mark welcome seen and restores genuine Lantern costume.
        pet.preview_festival_event(MID_AUTUMN_FESTIVAL.action, "中秋節")
        self.assertTrue(pet.is_festival_preview_active())
        self.assertEqual(pet.runtime.get("festival_welcome_seen"), {})
        pet.cancel_festival_preview()
        self.assertEqual(pet._shown_action, LANTERN.action)

        # Genuine first-encounter welcome triggers once for this occurrence and marks runtime.
        pair = festival_occurrence_key(lantern_day.date())
        self.assertIsNotNone(pair)
        _fest, occ_key = pair
        self.assertTrue(pet._maybe_festival_welcome())
        self.assertTrue(pet.runtime.get("festival_welcome_seen", {}).get(occ_key))
        self.assertFalse(pet.is_festival_preview_active())
        pet._close_group_celebration()
        # Same occurrence never fires twice.
        self.assertFalse(pet._maybe_festival_welcome())


class Q2StandbyClockAndPureViewTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_standby_caches()
        self.addCleanup(gc.collect)   # runs after root.destroy, still on the main thread
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.addCleanup(clear_standby_caches)
        lib = SpriteLibrary(ROOT, display_px=192)
        spr = lib.load_member("chorong", self.root)
        self.frames = spr.frames
        self.flipped = spr.flipped("walk")

    def _make_overlay(self, scene: str, *, clock_position: str = "top_right",
                      bounds: WorkArea | None = None, on_close=None) -> PandaStandbyOverlay:
        ov = PandaStandbyOverlay(
            parent=self.root,
            char_key="chorong",
            char_name="初瓏 (Chorong)",
            lang="zh_TW",
            frames=self.frames,
            flipped_walk_frames=self.flipped,
            passion_points=2590,
            companion_minutes=42,
            on_close=on_close or (lambda: None),
            lock_on_exit=False,
            lock_probe=lambda: False,
            scene=scene,
            bounds=bounds or WorkArea(0, 0, 1920, 1080),
            clock_position=clock_position,
        )
        # A second monitor has independent cover windows with the same exit
        # bindings. Real pointer/keyboard events must not dismiss test overlays.
        for surface in [ov.win, *(cover['win'] for cover in ov.covers)]:
            for event in ('<Motion>', '<ButtonPress>', '<Key>'):
                surface.unbind(event)
        self.addCleanup(lambda: ov.win.winfo_exists() and ov.handle_exit(None))
        return ov

    def test_clock_positions_all_wallpapers_and_cross_dpi_no_overlap(self) -> None:
        wps = load_wallpapers(ROOT)
        self.assertEqual(len(wps), 10)  # 7 originals + 2 Dome + 1 Fortune Studio (2026-11-16)
        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            # All 10 wallpapers at default top_right
            for w in wps:
                with self.subTest(wallpaper=w.key):
                    ov = self._make_overlay(w.key, clock_position="top_right")
                    _pump(self.root, 0.25)
                    cb = ov.canvas.bbox("clock_card")
                    hb = ov.canvas.bbox("standby_hint_ui")
                    self.assertIsNotNone(cb)
                    self.assertIsNotNone(hb)
                    self.assertGreaterEqual(cb[0], ov.sw // 2)
                    self.assertLessEqual(cb[2], ov.sw)
                    overlaps = not (cb[2] <= hb[0] or cb[0] >= hb[2] or cb[3] <= hb[1] or cb[1] >= hb[3])
                    self.assertFalse(overlaps)
                    # A stage room stays hidden until its costumes load (bbox None); measure
                    # the room as it appears once they have.
                    panda_tops = [b[1] for b in (ov.canvas.bbox(p["img_item"]) for p in ov.pandas) if b]
                    if not panda_tops and ov.scene in STAGE_SCENES:
                        ov.finish_action_loading()
                        ov._animate_dome_scene(reschedule=False)
                        panda_tops = [b[1] for b in (ov.canvas.bbox(p["img_item"]) for p in ov.pandas) if b]
                    self.assertLessEqual(cb[3], min(panda_tops) + 4)
                    ov.handle_exit(None)

            # top_left placement & hidden clock placement
            ov_left = self._make_overlay("bg_standby_spring_picnic", clock_position="top_left")
            _pump(self.root, 0.25)
            cb_left = ov_left.canvas.bbox("clock_card")
            self.assertIsNotNone(cb_left)
            self.assertLessEqual(cb_left[2], ov_left.sw // 2)
            ov_left.handle_exit(None)

            ov_hidden = self._make_overlay("bg_standby_autumn_cafe", clock_position="hidden")
            _pump(self.root, 0.25)
            for item in ov_hidden.canvas.find_withtag("clock_card"):
                self.assertEqual(ov_hidden.canvas.itemcget(item, "state"), "hidden")
            for item in ov_hidden.canvas.find_withtag("standby_hint_ui"):
                self.assertEqual(ov_hidden.canvas.itemcget(item, "state"), "normal")
            ov_hidden.handle_exit(None)

            # 192 DPI (200% scaling via tk scaling) stays within bounds and above pandas
            old_scaling = float(self.root.tk.call("tk", "scaling"))
            self.addCleanup(lambda: self.root.tk.call("tk", "scaling", old_scaling))
            self.root.tk.call("tk", "scaling", 2.0 * 96.0 / 72.0)
            ov_192 = self._make_overlay("bg_standby_moonlight_terrace", clock_position="top_right")
            _pump(self.root, 0.25)
            cb_192 = ov_192.canvas.bbox("clock_card")
            hb_192 = ov_192.canvas.bbox("standby_hint_ui")
            self.assertGreaterEqual(cb_192[0], 0)
            self.assertLessEqual(cb_192[2], ov_192.sw)
            overlaps_192 = not (
                cb_192[2] <= hb_192[0] or cb_192[0] >= hb_192[2]
                or cb_192[3] <= hb_192[1] or cb_192[1] >= hb_192[3]
            )
            self.assertFalse(overlaps_192)
            panda_tops_192 = [ov_192.canvas.bbox(p["img_item"])[1] for p in ov_192.pandas]
            self.assertLessEqual(cb_192[3], min(panda_tops_192) + 4)
            ov_192.handle_exit(None)

    def test_h_key_and_ime_keycode_toggle_pure_view_and_survive_scene_switch(self) -> None:
        closed = 0

        def on_close() -> None:
            nonlocal closed
            closed += 1

        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            ov = self._make_overlay("bg_standby_autumn_cafe", clock_position="top_right", on_close=on_close)
            _pump(self.root, 0.25)
            self.assertFalse(ov.pure_view)

            # Uppercase/lowercase H AND IME Process key with hardware keycode 72 ('H')
            for ev in (_FakeKey("h", 72), _FakeKey("Process", 72), _FakeKey("H", 72)):
                res = ov.handle_key(ev)
                self.assertEqual(res, "break")
                self.assertTrue(ov.running)
                self.assertEqual(closed, 0)

            self.assertTrue(ov.pure_view)
            for tag in ("clock_card", "standby_hint_ui"):
                for item in ov.canvas.find_withtag(tag):
                    self.assertEqual(ov.canvas.itemcget(item, "state"), "hidden")

            # Scene cycling via Left/Right keeps pure_view active on the new scene
            ov.handle_key(_FakeKey("Right", 39))
            self.assertTrue(ov.running)
            self.assertTrue(ov.pure_view)
            for tag in ("clock_card", "standby_hint_ui"):
                for item in ov.canvas.find_withtag(tag):
                    self.assertEqual(ov.canvas.itemcget(item, "state"), "hidden")

            # Restoring with H brings both clock_card and standby_hint_ui back
            ov.handle_key(_FakeKey("h", 72))
            self.assertFalse(ov.pure_view)
            for tag in ("clock_card", "standby_hint_ui"):
                for item in ov.canvas.find_withtag(tag):
                    self.assertEqual(ov.canvas.itemcget(item, "state"), "normal")

            # Normal non-shortcut key still wakes/exits once
            ov.handle_key(_FakeKey("a", 65))
            self.assertFalse(ov.running)
            self.assertEqual(closed, 1)

    def test_standby_detaches_ime_ignores_modifiers_and_handles_bopomofo_h(self) -> None:
        import ctypes
        from types import SimpleNamespace

        closed = 0

        def on_close() -> None:
            nonlocal closed
            closed += 1

        with mock.patch("ctypes.windll.user32.LockWorkStation", create=True):
            ov = self._make_overlay("bg_standby_autumn_cafe", clock_position="top_right", on_close=on_close)
            _pump(self.root, 0.2)

            if sys.platform == "win32":
                imm32 = ctypes.windll.imm32
                imm32.ImmGetContext.argtypes = [ctypes.c_void_p]
                imm32.ImmGetContext.restype = ctypes.c_void_p
                self.assertIsNone(imm32.ImmGetContext(int(ov.win.winfo_id())))
                self.assertIsNone(imm32.ImmGetContext(int(ov.canvas.winfo_id())))

            # Standalone modifiers (e.g. Shift before capital H or switching IME) never exit standby
            for ev in (
                SimpleNamespace(keysym="Shift_L", char="", keycode=16),
                SimpleNamespace(keysym="Control_L", char="", keycode=17),
                SimpleNamespace(keysym="Alt_L", char="", keycode=18),
                SimpleNamespace(keysym="Caps_Lock", char="", keycode=20),
            ):
                self.assertEqual(ov.handle_key(ev), "break")
                self.assertTrue(ov.running)
                self.assertFalse(ov.pure_view)
                self.assertEqual(closed, 0)

            # IME VK_PROCESSKEY (229) resolved via ImmGetVirtualKey == 72 toggles pure view instead of exiting
            with mock.patch("app.standby._resolve_ime_virtual_key", return_value=72):
                self.assertEqual(
                    ov.handle_key(SimpleNamespace(keysym="Process", char="", keycode=229)),
                    "break",
                )
            self.assertTrue(ov.running)
            self.assertTrue(ov.pure_view)
            self.assertEqual(closed, 0)

            # Taiwan Bopomofo 'ㄘ' on H key toggles back cleanly
            self.assertEqual(
                ov.handle_key(SimpleNamespace(keysym="??", char="ㄘ", keycode=0)),
                "break",
            )
            self.assertTrue(ov.running)
            self.assertFalse(ov.pure_view)

            # Unknown keysym with Windows virtual keycode 72 (VK_H) still toggles pure view
            self.assertEqual(
                ov.handle_key(SimpleNamespace(keysym="??", char="", keycode=72)),
                "break",
            )
            self.assertTrue(ov.running)
            self.assertTrue(ov.pure_view)

            # IME VK_PROCESSKEY resolving to non-shortcut 'A' (65) still exits cleanly
            with mock.patch("app.standby._resolve_ime_virtual_key", return_value=65):
                ov.handle_key(SimpleNamespace(keysym="Process", char="", keycode=229))
            self.assertFalse(ov.running)
            self.assertEqual(closed, 1)

    def test_settings_panel_clock_position_and_persistence_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="panda_cfg_") as td:
            svc = PersistenceService(Path(td))
            s, r = svc.load()
            self.assertEqual(s["standby_clock_position"], "top_right")
            s["standby_clock_position"] = "top_left"
            svc.save(s, r)
            s2, _ = svc.load()
            self.assertEqual(s2["standby_clock_position"], "top_left")

            # Invalid value falls back safely on load
            raw_path = Path(td) / "settings.json"
            doc = json.loads(raw_path.read_text(encoding="utf-8"))
            doc["data"]["standby_clock_position"] = "center_huge"
            raw_path.write_text(json.dumps(doc), encoding="utf-8")
            s3, _ = svc.load()
            self.assertEqual(s3["standby_clock_position"], "top_right")

        applied: list[tuple[str, object]] = []
        state = dict(SETTINGS_DEFAULTS["appearance"], **SETTINGS_DEFAULTS["reminders"])
        panel_ref: list[SettingsPanel] = []

        def on_change(k: str, v: object) -> bool:
            applied.append((k, v))
            state[k] = v
            panel_ref[0].refresh(state=state)
            return True

        panel = SettingsPanel(self.root, lang="zh_TW", state=state, on_change=on_change)
        panel_ref.append(panel)
        self.addCleanup(panel.close)
        for pos in ("top_left", "hidden", "top_right"):
            self.assertTrue(panel.canvas.find_withtag(f"standby_clock_{pos}"))
            self.assertTrue(panel.apply_change("standby_clock_position", pos))
        self.assertEqual(
            applied,
            [
                ("standby_clock_position", "top_left"),
                ("standby_clock_position", "hidden"),
                ("standby_clock_position", "top_right"),
            ],
        )


class Q3CachesAndWarmupTests(unittest.TestCase):
    def setUp(self) -> None:
        # Tk objects left by earlier tests must not be collected on a worker thread below
        # (Tcl_AsyncDelete: "async handler deleted by the wrong thread").
        gc.collect()
        clear_standby_caches()
        self.addCleanup(clear_standby_caches)

    def test_asset_image_cache_thread_safety_and_byte_budget(self) -> None:
        reg = AssetRegistry(ROOT / "work" / "asset_registry.json", ROOT)
        cache = AssetImageCache(reg, cache_bytes=1024 * 1024)  # 1 MiB forces LRU eviction under multi-member load
        errors: list[BaseException] = []

        def worker(member: str) -> None:
            try:
                for act in ("idle", "walk", "sleep", "cheer"):
                    spec = reg.resolve(member, act)
                    if spec is not None:
                        _actual, imgs = cache.load_animation(spec)
                        self.assertGreaterEqual(len(imgs), 1)
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(m,)) for m in ("chorong", "bomi", "eunji", "namjoo", "hayoung") * 2]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=10)
        self.assertFalse(errors, errors)
        self.assertLessEqual(cache.cache_size_bytes, 1024 * 1024)

    def test_fitted_wallpaper_bounded_lru_no_disk_cache(self) -> None:
        wps = load_wallpapers(ROOT)
        before_files = set((ROOT / "work").rglob("*"))
        for w in wps:
            im = _fitted_wallpaper(w.path, 1920, 1080, base_root=ROOT)
            self.assertEqual(im.size, (1920, 1080))
        with _FITTED_WALLPAPER_LOCK:
            total_bytes = sum(im.width * im.height * len(im.getbands()) for im in _FITTED_WALLPAPERS.values())
            self.assertGreaterEqual(len(_FITTED_WALLPAPERS), 1)
            self.assertLessEqual(total_bytes, 48 * 1024 * 1024 + (1920 * 1080 * 3))
        after_files = set((ROOT / "work").rglob("*"))
        self.assertEqual(before_files, after_files)  # strictly RAM-only cache

    def test_warmup_manager_populates_caches_and_cancels_cleanly(self) -> None:
        wm = StandbyWarmupManager()
        self.addCleanup(lambda: wm.shutdown(timeout=1.5))

        # busy_check pausing & generation cancel
        wm.schedule(
            ROOT, sprite_px=192, screen_w=1920, screen_h=1080,
            active_scene="bg_standby_autumn_cafe", today=dt.date(2026, 11, 15),
            busy_check=lambda: True,
        )
        time.sleep(0.08)
        wm.cancel()
        self.assertTrue(wm.wait(timeout=1.5))

        # Full warmup populates active wallpaper + 5 base members + scene actions in RAM
        clear_standby_caches()
        wm.completed_items = 0
        wm.schedule(
            ROOT, sprite_px=192, screen_w=1920, screen_h=1080,
            active_scene="bg_standby_autumn_cafe", today=dt.date(2026, 11, 15),
            busy_check=lambda: False,
        )
        self.assertTrue(wm.wait(timeout=30.0))
        self.assertGreaterEqual(wm.completed_items, 6)
        self.assertEqual(len(_FITTED_WALLPAPERS), 1)  # only expected wallpaper warmed, others stay on-demand
        self.assertGreater(PREPARED_IMAGES.size_bytes, 0)


if __name__ == "__main__":
    unittest.main()
