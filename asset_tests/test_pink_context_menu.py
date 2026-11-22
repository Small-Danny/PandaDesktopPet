"""tests/test_pink_context_menu.py — Unit tests for PinkContextMenu & NotificationDrawerWindow.

Run:  python -m unittest tests.test_pink_context_menu -v
"""
from __future__ import annotations

import contextlib
import sys
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pink_context_menu import (  # noqa: E402
    MenuItemSpec,
    NotificationDrawerWindow,
    PinkContextMenu,
    build_pet_context_menu_items,
)
from app.i18n import t  # noqa: E402
from app.platform.win32 import WorkArea  # noqa: E402


class _DummyPet:
    def __init__(self, lang: str = "zh_TW", char_key: str = "chorong") -> None:
        self.lang = lang
        self.char_key = char_key
        self.state = "idle"
        self.mode = "manual"
        self.hotkey_str = "Ctrl+Shift+S"
        self.settings = {
            "cameo_enabled": True,
            "standby_lock_workstation": True,
            "notify_privacy_mode": False,
            "notify_relay": True,
        }
        self.recent_notifications = [
            {"app_name": "LINE", "title": "Apink Official", "body": "2026 Concert Ticket Open!"},
            {"app_name": "Discord", "title": "Panda Club", "body": "Remember to stream the MV~"},
        ]
        self.triggered_specials: list[tuple[str, str]] = []
        self.drawer_opened = False

    def get_auto_character(self) -> str:
        return "chorong"

    def is_autostart_enabled(self) -> bool:
        return False

    def available_special_actions(self, member: str) -> tuple[str, ...]:
        return ("special_gorilla",) if member == "bomi" else ()

    def trigger_special_action(self, action_key: str, member: str) -> bool:
        self.triggered_specials.append((action_key, member))
        return True

    def open_notification_drawer(self) -> None:
        self.drawer_opened = True


class PinkContextMenuTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def _use_stub_cursor_without_assets(self) -> None:
        """Code-only exports ship no work/ui_icons/*.cur; stand in a fake handle so the hooks still install."""
        from app import cursor_manager as cm

        if cm.get_cursor_path("paw_smooth"):
            return
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(cm, "load_cursor", side_effect=lambda _k: 1001))
        stack.enter_context(mock.patch.object(
            cm, "get_tkinter_cursor_spec", side_effect=lambda k: "" if k == "system" else "hand2"))

    def test_menu_renders_all_three_languages_and_clamps_to_work_area(self) -> None:
        for lang in ("zh_TW", "ko", "en"):
            pet = _DummyPet(lang=lang, char_key="bomi")
            items = build_pet_context_menu_items(pet)
            menu = PinkContextMenu(
                self.root,
                lang=lang,
                char_key="bomi",
                items=items,
                anchor_x=1850,
                anchor_y=980,
                work_area=(0, 0, 1920, 1040),
            )
            self.addCleanup(menu.close)
            mx, my = menu.last_clamped_pos
            self.assertLessEqual(mx + menu.w, 1920)
            self.assertLessEqual(my + menu.h, 1040)

            # Open Special Moves, drill into Bomi (the only member with moves here), play Gorilla
            self.assertTrue(menu.activate_item(3))
            self.assertIsNotNone(menu._sub_window)
            sx, sy = menu.last_sub_clamped_pos
            self.assertGreaterEqual(sx, 0)
            self.assertTrue(menu.activate_submenu_item(0))
            self.assertTrue(menu.activate_submenu_item(1))
            self.assertEqual(pet.triggered_specials, [("special_gorilla", "bomi")])

    def test_stay_in_place_toggle_in_action_sub(self) -> None:
        """Verify stay_in_place toggle is present in action_sub and correctly bound."""
        for lang in ("zh_TW", "ko", "en"):
            pet = _DummyPet(lang=lang, char_key="bomi")
            pet.settings["stay_in_place"] = True
            items = build_pet_context_menu_items(pet)
            action_sub = items[0].submenu
            self.assertIsNotNone(action_sub)
            stay_spec = next((item for item in action_sub if "📌" in item.label), None)
            self.assertIsNotNone(stay_spec, f"stay_in_place item missing in {lang}")
            self.assertTrue(stay_spec.checked)

            # Test unchecking
            pet.settings["stay_in_place"] = False
            items_off = build_pet_context_menu_items(pet)
            stay_off = next((item for item in items_off[0].submenu if "📌" in item.label), None)
            self.assertIsNotNone(stay_off)
            self.assertFalse(stay_off.checked)

    def test_notification_drawer_privacy_mask_and_ram_clear(self) -> None:
        pet = _DummyPet(lang="zh_TW", char_key="eunji")
        cleared = []
        drawer = NotificationDrawerWindow(
            self.root,
            lang="zh_TW",
            char_key="eunji",
            items=pet.recent_notifications,
            privacy_mode=False,
            on_clear=lambda: cleared.append(True),
        )
        self.addCleanup(drawer.close)

        texts_unmasked = "\n".join(
            drawer.canvas.itemcget(i, "text")
            for i in drawer.canvas.find_all()
            if drawer.canvas.type(i) == "text"
        )
        self.assertIn("2026 Concert Ticket Open!", texts_unmasked)

        # Toggle privacy mask ON -> sensitive body text must be hidden
        drawer.toggle_privacy()
        texts_masked = "\n".join(
            drawer.canvas.itemcget(i, "text")
            for i in drawer.canvas.find_all()
            if drawer.canvas.type(i) == "text"
        )
        self.assertNotIn("2026 Concert Ticket Open!", texts_masked)
        self.assertIn("LINE", texts_masked)

        # Clear RAM drawer
        drawer.clear_drawer()
        self.assertEqual(len(drawer.items), 0)
        self.assertEqual(cleared, [True])

    def test_drawer_cards_stay_two_single_lines(self) -> None:
        """A mail preview with line breaks used to grow up over the app line; the title ran under the X."""
        import tkinter.font as tkfont
        long_body = "FW: [Platform] test report and to-do list\nDear team,\nHello, since someone is on leave these days, " * 3
        items = [{"app": "Outlook", "title": "Sender Name " * 6, "body": long_body},
                 {"app": "Telegram", "title": "Work", "body": "short"}]
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                drawer = NotificationDrawerWindow(self.root, lang=lang, char_key="chorong", items=items)
                self.addCleanup(drawer.close)
                c = drawer.canvas
                for i in c.find_all():
                    if c.type(i) != "text":
                        continue
                    text = c.itemcget(i, "text")
                    self.assertNotIn("\n", text)
                    x1, _y1, x2, _y2 = c.bbox(i)
                    self.assertLessEqual(x2, drawer.w - 20, text)     # inside the card / header

    def test_notification_details_restore_arrow_and_rebind_on_reopen(self) -> None:
        from app import cursor_manager as cm
        from app.main import PandaPet

        self._use_stub_cursor_without_assets()
        items = [{"title": f"Older {i}"} for i in range(8)]
        items.append({"title": "Long notification", "body": "Line of detail\n" * 80})
        owner = types.SimpleNamespace(settings={"mouse_cursor": "paw_smooth"})
        drawer = NotificationDrawerWindow(self.root, items=items)
        self.addCleanup(drawer.close)
        self.root.update()
        PandaPet._apply_cursor_to_panel(owner, drawer)

        def click_visible_card():
            canvas = drawer.canvas
            tag = f"notif_card_{drawer.top}"
            left, top, right, bottom = canvas.bbox(tag)
            point = {"x": (left + right) // 2, "y": (top + bottom) // 2}
            canvas.event_generate("<ButtonPress-1>", **point)
            canvas.event_generate("<ButtonRelease-1>", **point)
            self.root.update()

        click_visible_card()
        message, scrollbar = drawer._details.winfo_children()
        original_handles = [w.winfo_id() for w in (message, scrollbar)]
        for widget, hwnd in zip((message, scrollbar), original_handles):
            self.assertEqual(widget.cget("cursor"), cm.get_tkinter_cursor_spec("paw_smooth"))
            self.assertEqual(cm._HWND_HOOKS[hwnd][2], "paw_smooth")
        drawer_callback = cm._HWND_HOOKS[drawer.canvas.winfo_id()][1]
        message.event_generate("<MouseWheel>", delta=-120)
        self.assertGreater(message.yview()[0], 0)

        click_visible_card()
        self.assertIsNone(drawer._details)
        self.assertTrue(all(hwnd not in cm._HWND_HOOKS for hwnd in original_handles))
        self.assertIs(cm._HWND_HOOKS[drawer.canvas.winfo_id()][1], drawer_callback)
        click_visible_card()
        message, scrollbar = drawer._details.winfo_children()
        owner.settings["mouse_cursor"] = "system"
        PandaPet._apply_cursor_to_panel(owner, drawer)
        self.assertEqual(message.cget("cursor"), "arrow")
        for widget in (message, scrollbar):
            self.assertNotIn(widget.winfo_id(), cm._HWND_HOOKS)
        drawer.lang = "ko"
        drawer._render()
        self.root.update()
        self.assertEqual(drawer._details.winfo_children()[0].cget("cursor"), "arrow")

    def test_notification_details_scrollbar_hooks_released_on_collapse_and_close(self) -> None:
        """Tk's Scrollbar restores its own WndProc before WM_NCDESTROY; the drawer must unhook it first."""
        from app import cursor_manager as cm
        from app.main import PandaPet

        self._use_stub_cursor_without_assets()
        items = [{"title": "Long notification", "body": "Line of detail\n" * 80}]
        owner = types.SimpleNamespace(settings={"mouse_cursor": "paw_smooth"})
        for closing in (False, True):
            with self.subTest(closing=closing):
                drawer = NotificationDrawerWindow(self.root, items=items)
                self.addCleanup(drawer.close)
                self.root.update()
                PandaPet._apply_cursor_to_panel(owner, drawer)
                left, top, right, bottom = drawer.canvas.bbox(f"notif_card_{drawer.top}")
                point = {"x": (left + right) // 2, "y": (top + bottom) // 2}
                drawer.canvas.event_generate("<ButtonPress-1>", **point)
                drawer.canvas.event_generate("<ButtonRelease-1>", **point)
                self.root.update()
                handles = [w.winfo_id() for w in drawer._details.winfo_children()]
                self.assertTrue(all(h in cm._HWND_HOOKS for h in handles))
                if closing:
                    drawer.close()
                else:
                    drawer._destroy_details()    # no re-apply afterwards: must be clean on its own
                self.assertIsNone(drawer._details)
                self.assertFalse([h for h in handles if h in cm._HWND_HOOKS])
                self.assertFalse([h for h in cm._HWND_HOOKS if not cm._is_win32_window(h)])

    def test_notification_card_expands_full_wrapped_text_and_preserves_privacy(self) -> None:
        from types import SimpleNamespace

        app_name = "Example sender application"
        title = "Long multiline notification title"
        body = ("First line\n" + "wrapped detail " * 50 + "\nLast line\n") * 4
        when = "15:27:19"
        items = [{"title": f"Older {i}"} for i in range(8)]
        items.append(dict(app_name=app_name, title=title, body=body, time=when))
        drawer = NotificationDrawerWindow(self.root, lang="en", items=items)
        self.addCleanup(drawer.close)
        self.root.update()

        def click():
            c = drawer.canvas
            left, top, right, bottom = c.bbox("notif_card_0")
            xy = {"x": (left + right) // 2, "y": (top + bottom) // 2}
            c.event_generate("<ButtonPress-1>", **xy)
            c.event_generate("<ButtonRelease-1>", **xy)
            self.root.update()

        click()
        details = next(w for w in drawer._details.winfo_children() if isinstance(w, tk.Text))
        self.assertEqual(details.get("1.0", "end-1c"), "\n\n".join((app_name, title, when, body)))
        self.assertEqual(details.cget("wrap"), "word")
        details.event_generate("<MouseWheel>", delta=-120)
        self.assertGreater(details.yview()[0], 0)
        self.assertIs(drawer._expanded_entry, items[-1])
        drawer.toggle_privacy()
        masked = next(w for w in drawer._details.winfo_children() if isinstance(w, tk.Text))
        self.assertNotIn(title, masked.get("1.0", "end-1c"))
        self.assertNotIn("Last line", masked.get("1.0", "end-1c"))
        click()
        self.assertIsNone(drawer._details)
        click()
        drawer._on_wheel(SimpleNamespace(delta=-120))
        self.assertIsNone(drawer._details)
        self.assertEqual(drawer.visible_entries()[0]["title"], "Older 7")

    def test_notification_refresh_tracks_open_entry_until_evicted(self) -> None:
        from collections import deque
        from app.main import PandaPet

        pet = _DummyPet(lang="en")
        original = {"title": "Selected", "body": "Original full text"}
        pet.recent_notifications = deque([original], maxlen=20)
        drawer = NotificationDrawerWindow(self.root, lang=pet.lang, items=pet.recent_notifications)
        pet.notification_drawer = drawer
        self.addCleanup(drawer.close)
        self.root.update()
        left, top, right, bottom = drawer.canvas.bbox("notif_card_0")
        xy = {"x": (left + right) // 2, "y": (top + bottom) // 2}
        drawer.canvas.event_generate("<ButtonPress-1>", **xy)
        drawer.canvas.event_generate("<ButtonRelease-1>", **xy)

        for title in ("New A", "New B"):
            pet.recent_notifications.append({"title": title, "body": "A different notification"})
            PandaPet._refresh_notification_drawer(pet)
            self.assertIs(drawer._expanded_entry, original)
            details = next(w for w in drawer._details.winfo_children() if isinstance(w, tk.Text))
            self.assertIn(original["body"], details.get("1.0", "end-1c"))
            self.assertNotIn("A different notification", details.get("1.0", "end-1c"))

        pet.recent_notifications.extend({"title": str(i)} for i in range(17))
        pet.recent_notifications.append(dict(original))
        PandaPet._refresh_notification_drawer(pet)
        self.assertIsNot(drawer.items[-1], original)
        self.assertIn(original, drawer.items)  # Equal contents are a distinct notification.
        self.assertIsNone(drawer._expanded_entry)
        self.assertIsNone(drawer._details)


    def test_full_drawer_shows_the_newest_first_and_scrolls(self) -> None:
        """With 20 kept only the 6 oldest used to show, and there was no way to reach the rest."""
        import types
        items = [{"app": "LINE", "title": f"msg {i:02d}", "body": "x", "time": f"10:{i:02d}:00"} for i in range(20)]
        drawer = NotificationDrawerWindow(self.root, lang="zh_TW", char_key="bomi", items=items)
        self.addCleanup(drawer.close)

        def shown() -> list[str]:
            return [e["title"] for e in drawer.visible_entries()]

        self.assertEqual(shown()[0], "msg 19")                     # newest on top
        texts = [drawer.canvas.itemcget(i, "text") for i in drawer.canvas.find_all() if drawer.canvas.type(i) == "text"]
        self.assertIn("10:19:00", texts)
        self.assertTrue(any("20" in x and "1" in x and "6" in x for x in texts if "滾輪" in x))
        for _ in range(30):                                        # wheel down past the end
            drawer._on_wheel(types.SimpleNamespace(delta=-120))
        self.assertEqual(shown(), [f"msg {i:02d}" for i in range(5, -1, -1)])   # the oldest six
        for _ in range(30):                                        # and back up past the top
            drawer._on_wheel(types.SimpleNamespace(delta=120))
        self.assertEqual(shown()[0], "msg 19")
        self.assertEqual(drawer.top, 0)

    def test_notification_drawer_clear_menu_item_and_command(self) -> None:
        """The notification drawer submenu must have a dedicated Clear Drawer button."""
        cleared = []
        pet = types.SimpleNamespace(
            lang="zh_TW",
            char_key="bomi",
            settings={"mouse_cursor": "paw_smooth"},
            recent_notifications=[{"app": "Slack", "title": "Hi", "body": "World"}],
            open_notification_drawer=lambda: None,
            clear_recent_notifications=lambda: cleared.append(True),
            toggle_notify_privacy=lambda: None,
            toggle_notify_relay=lambda: None,
            set_mouse_cursor=lambda k: None,
        )
        for lang, expected_label in (
            ("zh_TW", "🧹 清空最近通知紀錄"),
            ("ko", "🧹 최근 알림 기록 지우기"),
            ("en", "🧹 Clear Recent Notifications"),
        ):
            pet.lang = lang
            items = build_pet_context_menu_items(pet)
            notif_row = next(r for r in items if r.tag_id == "row_notif")
            self.assertIsNotNone(notif_row.submenu)
            clear_item = next((sub for sub in notif_row.submenu if sub.label == expected_label), None)
            self.assertIsNotNone(clear_item, f"Missing clear item in {lang}")
            if lang == "zh_TW":
                clear_item.command()
                self.assertEqual(cleared, [True])

    def test_mouse_cursor_submenu_and_selection(self) -> None:
        """The context menu must include custom cursor style selector."""
        selected_cursors = []
        pet = types.SimpleNamespace(
            lang="zh_TW",
            char_key="chorong",
            settings={"mouse_cursor": "paw_smooth"},
            recent_notifications=[],
            set_mouse_cursor=lambda k: selected_cursors.append(k),
        )
        items = build_pet_context_menu_items(pet)
        cursor_row = next(r for r in items if r.tag_id == "row_cursor")
        self.assertIsNotNone(cursor_row.submenu)
        self.assertEqual(len(cursor_row.submenu), 5)
        # Check checked state
        self.assertTrue(cursor_row.submenu[0].checked)  # paw_smooth
        self.assertFalse(cursor_row.submenu[1].checked)  # mitten_smooth
        # Trigger item command
        cursor_row.submenu[1].command()
        self.assertEqual(selected_cursors, ["mitten_smooth"])

    def test_notification_drawer_draggable(self) -> None:
        """The notification drawer window must be draggable by clicking and moving the canvas."""
        drawer = NotificationDrawerWindow(self.root, lang="zh_TW", char_key="bomi", items=[])
        self.addCleanup(drawer.close)

        # Initial drag begin in header area
        event_press = types.SimpleNamespace(x=100, y=30, x_root=500, y_root=300)
        drawer._on_drag_begin(event_press)
        self.assertIsNotNone(drawer.drag_offset_x)
        self.assertIsNotNone(drawer.drag_offset_y)

        # Move mouse
        event_move = types.SimpleNamespace(x_root=560, y_root=340)
        drawer._on_drag_move(event_move)
        expected_x = 560 - drawer.drag_offset_x
        expected_y = 340 - drawer.drag_offset_y
        self.assertEqual(drawer.last_clamped_pos, (expected_x, expected_y))

        # Release drag
        drawer._on_drag_end(types.SimpleNamespace())
        self.assertIsNone(drawer.drag_offset_x)
        self.assertIsNone(drawer.drag_offset_y)


    def test_menu_ignores_an_unpaired_release_over_food_cafe(self) -> None:
        opened = []
        menu = PinkContextMenu(self.root, items=[MenuItemSpec("Food Café", lambda: opened.append(True))])
        self.addCleanup(menu.close)
        self.root.update()
        _, top, bottom = menu._row_bounds[0]
        xy = {"x": menu.w // 2, "y": (top + bottom) // 2}
        menu.canvas.event_generate("<ButtonRelease-1>", **xy)
        self.assertFalse(opened)
        menu.canvas.event_generate("<ButtonPress-1>", **xy)
        menu.canvas.event_generate("<ButtonRelease-1>", **xy)
        self.assertEqual(opened, [True])

    def test_flyouts_require_press_and_release_on_the_same_row(self) -> None:
        for surface in ("sub", "peek"):
            with self.subTest(surface=surface):
                activated = []
                leaves = [
                    MenuItemSpec("First", lambda: activated.append("first")),
                    MenuItemSpec("Second", lambda: activated.append("second")),
                ]
                rows = leaves if surface == "sub" else [MenuItemSpec("Nested", submenu=leaves)]
                menu = PinkContextMenu(self.root, items=[MenuItemSpec("Open", submenu=rows)])
                self.addCleanup(menu.close)
                menu.activate_item(0)
                self.root.update()
                if surface == "peek":
                    submenu = menu._sub_canvas
                    _, y0, y1 = menu._sub_row_bounds[0]
                    submenu.event_generate("<Motion>", x=30, y=(y0 + y1) // 2)
                    self.root.update()
                canvas = getattr(menu, f"_{surface}_canvas")
                bounds = menu._sub_row_bounds if surface == "sub" else menu._peek_bounds
                (_, first_top, first_bottom), (_, second_top, second_bottom) = bounds
                first_y = (first_top + first_bottom) // 2
                second_y = (second_top + second_bottom) // 2
                canvas.event_generate("<ButtonRelease-1>", x=30, y=first_y)
                canvas.event_generate("<ButtonPress-1>", x=30, y=first_y)
                canvas.event_generate("<ButtonRelease-1>", x=30, y=second_y)
                self.assertEqual(activated, [])
                canvas.event_generate("<ButtonPress-1>", x=30, y=second_y)
                canvas.event_generate("<ButtonRelease-1>", x=30, y=second_y)
                self.assertEqual(activated, ["second"])

    def test_eunji_special_submenu_groups_general_and_fortune_with_separator(self) -> None:
        from app.i18n import t

        all_actions = {
            "chorong": (
                "special_cartwheel", "special_hapkido_kick", "special_blow_kiss",
                "daily_cat_cuddle", "special_cheer_lightstick",
            ),
            "bomi": (
                "special_gorilla", "special_taekwondo", "interaction_eat",
                "special_cheer_lightstick",
            ),
            "eunji": (
                "special_sing_highnote", "special_boxing", "special_guitar",
                "standby_stretch", "special_eunji_dome_dream",
                "fortune_tarot_reader", "fortune_student", "fortune_love_reading",
                "special_cheer_lightstick",
            ),
            "namjoo": ("special_boxing", "scene_flamingo", "special_cheer_lightstick"),
            "hayoung": ("special_soccer_kick", "special_gaming", "special_cheer_lightstick"),
        }
        expected_prefixes = {"zh_TW": "恩地：", "ko": "은지: ", "en": "Eunji: "}
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                triggered: list[tuple[str, str]] = []
                rooms: list[bool] = []
                bubbles: list[bool] = []
                pet = types.SimpleNamespace(
                    lang=lang,
                    char_key="eunji",
                    settings={},
                    developer_mode=False,
                    available_special_actions=lambda m: all_actions.get(m, ()),
                    trigger_special_action=lambda a, m: triggered.append((a, m)),
                    open_fortune_room=lambda: rooms.append(True),
                    show_daily_fortune_bubble=lambda: bubbles.append(True),
                )
                items = build_pet_context_menu_items(pet)
                special_sub = next(i for i in items if i.tag_id == "row_special").submenu
                member_rows = [i for i in special_sub if i.submenu]
                self.assertEqual(len(member_rows), 5)

                # Other 4 members have no separators and end with lightstick cheer.
                for idx in (0, 1, 3, 4):
                    sub = member_rows[idx].submenu
                    self.assertFalse(any(r.is_separator for r in sub))
                    self.assertEqual(sub[-1].label, t("special_move_lightstick_all", lang))

                eunji_sub = member_rows[2].submenu
                self.assertEqual(len(eunji_sub), 13)
                expected_keys = [
                    "special_move_back",
                    "special_move_highnote",
                    "special_move_boxing_eunji",
                    "special_move_guitar",
                    "special_move_stretch",
                    "special_move_eunji_dome_dream",
                    "special_move_lightstick_all",
                    None,
                    "special_move_eunji_fortune_room",
                    "fortune_daily_bubble",
                    "special_move_eunji_fortune_tarot",
                    "special_move_eunji_fortune_student",
                    "special_move_eunji_fortune_love",
                ]
                for row_idx, key in enumerate(expected_keys):
                    if key is None:
                        self.assertTrue(eunji_sub[row_idx].is_separator)
                    else:
                        self.assertFalse(eunji_sub[row_idx].is_separator)
                        self.assertEqual(eunji_sub[row_idx].label, t(key, lang))

                # Prefix consistency on Eunji's special move labels.
                for key in ("special_move_eunji_dome_dream", "special_move_eunji_fortune_love", "fortune_daily_bubble"):
                    self.assertIn(expected_prefixes[lang], t(key, lang))

                # Also verify the shortcut in action_sub triggers show_daily_fortune_bubble even when another member is active.
                action_sub = next(i for i in items if i.tag_id == "row_actions").submenu
                action_fortune = next((r for r in action_sub if r.label == t("fortune_daily_bubble", lang)), None)
                self.assertIsNotNone(action_fortune)
                action_fortune.command()
                self.assertEqual(bubbles, [True])
                bubbles.clear()

                # Callbacks map to the exact items before & after the separator.
                eunji_sub[6].command()
                eunji_sub[8].command()
                eunji_sub[9].command()
                eunji_sub[12].command()
                self.assertEqual(
                    triggered,
                    [("special_cheer_lightstick", "eunji"), ("fortune_love_reading", "eunji")],
                )
                self.assertEqual(rooms, [True])
                self.assertEqual(bubbles, [True])

        # Edge cases: no dangling separator when either group is absent.
        only_general_pet = types.SimpleNamespace(
            lang="zh_TW",
            char_key="eunji",
            settings={},
            developer_mode=False,
            available_special_actions=lambda m: (
                ("special_sing_highnote", "special_cheer_lightstick") if m == "eunji" else ()
            ),
            trigger_special_action=lambda a, m: None,
        )
        gen_sub = next(i for i in build_pet_context_menu_items(only_general_pet) if i.tag_id == "row_special").submenu[0].submenu
        self.assertFalse(any(r.is_separator for r in gen_sub))
        self.assertEqual(
            [r.label for r in gen_sub],
            [
                t("special_move_back", "zh_TW"),
                t("special_move_highnote", "zh_TW"),
                t("special_move_lightstick_all", "zh_TW"),
            ],
        )

        only_fortune_pet = types.SimpleNamespace(
            lang="zh_TW",
            char_key="eunji",
            settings={},
            developer_mode=False,
            available_special_actions=lambda m: ("fortune_tarot_reader",) if m == "eunji" else (),
            trigger_special_action=lambda a, m: None,
            open_fortune_room=lambda: None,
        )
        fort_sub = next(i for i in build_pet_context_menu_items(only_fortune_pet) if i.tag_id == "row_special").submenu[0].submenu
        self.assertFalse(any(r.is_separator for r in fort_sub))
        self.assertEqual(
            [r.label for r in fort_sub],
            [
                t("special_move_back", "zh_TW"),
                t("special_move_eunji_fortune_room", "zh_TW"),
                t("special_move_eunji_fortune_tarot", "zh_TW"),
            ],
        )

    def test_flyout_submenu_and_peek_handle_separators_height_hover_and_click(self) -> None:
        for surface in ("sub", "peek"):
            with self.subTest(surface=surface):
                activated: list[str] = []
                leaves = [
                    MenuItemSpec("First", lambda: activated.append("first")),
                    MenuItemSpec("Second", lambda: activated.append("second")),
                    MenuItemSpec("", is_separator=True),
                    MenuItemSpec("Third", lambda: activated.append("third")),
                    MenuItemSpec("Fourth", lambda: activated.append("fourth")),
                ]
                no_sep_leaves = [item for item in leaves if not item.is_separator]
                rows = leaves if surface == "sub" else [MenuItemSpec("Nested", submenu=leaves)]
                menu = PinkContextMenu(self.root, items=[MenuItemSpec("Open", submenu=rows)])
                self.addCleanup(menu.close)

                expected_h = 38 + 4 * menu._row_h + menu._sep_h
                self.assertEqual(menu._compute_height(leaves, include_header=False), expected_h)
                self.assertEqual(
                    expected_h - menu._compute_height(no_sep_leaves, include_header=False),
                    menu._sep_h,
                )

                menu.activate_item(0)
                self.root.update()
                if surface == "peek":
                    sub_c = menu._sub_canvas
                    _, y0, y1 = menu._sub_row_bounds[0]
                    sub_c.event_generate("<Motion>", x=30, y=(y0 + y1) // 2)
                    self.root.update()

                canvas = getattr(menu, f"_{surface}_canvas")
                bounds = menu._sub_row_bounds if surface == "sub" else menu._peek_bounds
                design_w, design_h = menu._sub_design_size if surface == "sub" else menu._peek_design_size
                self.assertEqual(design_h, expected_h)
                self.assertEqual(int(canvas.cget("height")), round(expected_h * menu.ui_scale))

                # Original list indices skip the separator at index 2.
                self.assertEqual([idx for idx, _, _ in bounds], [0, 1, 3, 4])

                # Separator line rendered and all texts stay within canvas bounds.
                canvas_w = round(design_w * menu.ui_scale)
                canvas_h = round(design_h * menu.ui_scale)
                lines = [i for i in canvas.find_all() if canvas.type(i) == "line"]
                self.assertEqual(len(lines), 1)
                (_, _s1_top, second_bottom), (_, third_top, _t_bot), (_, fourth_top, fourth_bottom) = (
                    bounds[1], bounds[2], bounds[3],
                )
                _, ly1, _, ly2 = canvas.bbox(lines[0])
                sep_mid_y = (ly1 + ly2) // 2
                self.assertGreater(sep_mid_y, second_bottom)
                self.assertLess(sep_mid_y, third_top)

                for item_id in canvas.find_all():
                    if canvas.type(item_id) == "text":
                        x1, y1, x2, y2 = canvas.bbox(item_id)
                        self.assertGreaterEqual(x1, 0)
                        self.assertGreaterEqual(y1, 0)
                        self.assertLessEqual(x2, canvas_w)
                        self.assertLessEqual(y2, canvas_h)

                # Programmatic activation of separator is a no-op and keeps menu open.
                activate_fn = menu.activate_submenu_item if surface == "sub" else menu.activate_peek_item
                self.assertFalse(activate_fn(2))
                self.assertFalse(menu._closed)
                self.assertEqual(activated, [])

                # Hovering and clicking on the separator clears hover and triggers nothing.
                sep_gap_y = (second_bottom + third_top) // 2
                canvas.event_generate("<Motion>", x=30, y=sep_gap_y)
                canvas.event_generate("<ButtonPress-1>", x=30, y=sep_gap_y)
                canvas.event_generate("<ButtonRelease-1>", x=30, y=sep_gap_y)
                self.root.update()
                hover_attr = "_sub_hover_idx" if surface == "sub" else "_peek_hover"
                self.assertIsNone(getattr(menu, hover_attr))
                self.assertEqual(activated, [])

                # Hovering Third yields original index 3; clicking Fourth triggers "fourth".
                third_y = (third_top + bounds[2][2]) // 2
                canvas.event_generate("<Motion>", x=30, y=third_y)
                self.root.update()
                self.assertEqual(getattr(menu, hover_attr), 3)

                fourth_y = (fourth_top + fourth_bottom) // 2
                canvas.event_generate("<ButtonPress-1>", x=30, y=fourth_y)
                canvas.event_generate("<ButtonRelease-1>", x=30, y=fourth_y)
                self.root.update()
                self.assertEqual(activated, ["fourth"])
                self.assertTrue(menu._closed)

    def test_drawer_secondary_text_contrast(self) -> None:
        from app.pink_context_menu import DRAWER_MUTED
        from app.status_card import MEMBER_THEMES

        def luminance(color: str) -> float:
            rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

        fg = luminance(DRAWER_MUTED)
        for key, theme in MEMBER_THEMES.items():
            for bg in (theme["header_fill"], theme["soft_bg"], "#ffffff"):
                with self.subTest(member=key, bg=bg):
                    self.assertGreaterEqual((luminance(bg) + 0.05) / (fg + 0.05), 6.5)

    def test_hover_uses_member_header_fill_and_subtitle_is_localized(self) -> None:
        from app.status_card import MEMBER_THEMES
        for lang in ("zh_TW", "ko", "en"):
            with self.subTest(lang=lang):
                menu = PinkContextMenu(self.root, lang=lang, char_key="eunji",
                                       items=[MenuItemSpec("Open", submenu=[MenuItemSpec("Leaf", lambda: None)])])
                self.addCleanup(menu.close)
                texts = [menu.canvas.itemcget(i, "text") for i in menu.canvas.find_all()
                         if menu.canvas.type(i) == "text"]
                self.assertIn(t("pink_menu_subtitle", lang), texts)
                menu.activate_item(0)
                self.root.update()
                fills = {menu.canvas.itemcget(i, "fill") for i in menu.canvas.find_all()
                         if menu.canvas.type(i) == "polygon"}
                self.assertIn(MEMBER_THEMES["eunji"]["header_fill"], fills)
                self.assertNotIn("#ffe3ef", fills)
                menu.close()

    def test_long_flyout_labels_widen_then_elide_inside_the_card(self) -> None:
        long_label = "🖼️ " + "非常非常長的待機背景名稱 Very Long Wallpaper Name " * 3
        menu = PinkContextMenu(self.root, items=[MenuItemSpec("Open", submenu=[
            MenuItemSpec("Short", lambda: None), MenuItemSpec(long_label, lambda: None)])])
        self.addCleanup(menu.close)
        menu.activate_item(0)
        self.root.update()
        design_w, _ = menu._sub_design_size
        self.assertGreater(design_w, 324)
        self.assertLessEqual(design_w, 460)
        canvas = menu._sub_canvas
        width = int(canvas.cget("width"))
        texts = [i for i in canvas.find_all() if canvas.type(i) == "text"]
        self.assertTrue(any(canvas.itemcget(i, "text").endswith("…") for i in texts))
        for item_id in texts:
            x1, _y1, x2, _y2 = canvas.bbox(item_id)
            self.assertGreaterEqual(x1, 0)
            self.assertLessEqual(x2, width)

    def test_tall_standby_flyout_rows_shrink_to_fit_at_200_percent(self) -> None:
        """1080p at 200 %: the real standby list (16 rows) would run ~200 px off-screen."""
        self.root.tk.call("tk", "scaling", 192 / 72)
        self.addCleanup(self.root.tk.call, "tk", "scaling", 96 / 72)
        items = build_pet_context_menu_items(_DummyPet())
        rows = next(item for item in items if item.tag_id == "row_standby").submenu
        area = WorkArea(0, 0, 1920, 1040)
        menu = PinkContextMenu(self.root, items=[MenuItemSpec("Open", submenu=rows)], work_area=area)
        self.addCleanup(menu.close)
        self.assertEqual(menu.ui_scale, 2.0)
        self.assertGreater(menu._compute_height(rows, include_header=False) * menu.ui_scale, area.height)
        menu.activate_item(0)
        self.root.update()
        self.assertLess(menu._sub_row_h, menu._row_h)
        self.assertLessEqual(int(menu._sub_canvas.cget("height")), area.height)
        self.assertEqual(len(menu._sub_row_bounds), sum(1 for r in rows if not r.is_separator))
        x, y = menu.last_sub_clamped_pos
        self.assertGreaterEqual(y, area.top)
        self.assertLessEqual(y + int(menu._sub_canvas.cget("height")), area.bottom)

    def test_context_menu_canvas_renders_bmp_safe_text_and_caches_pil_icons(self) -> None:
        from app.pink_context_menu import _ICON_PIL_CACHE, warm_context_menu_assets
        warm_context_menu_assets(scales=(1.0,))
        self.assertGreaterEqual(len(_ICON_PIL_CACHE), 8)
        items = build_pet_context_menu_items(_DummyPet())
        menu = PinkContextMenu(self.root, items=items)
        self.addCleanup(menu.close)
        for item_id in menu.canvas.find_all():
            if menu.canvas.type(item_id) == "text":
                txt = menu.canvas.itemcget(item_id, "text")
                self.assertTrue(all(ord(ch) <= 0xFFFF for ch in txt), txt)


if __name__ == "__main__":
    unittest.main()
