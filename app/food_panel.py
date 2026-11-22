"""app/food_panel.py — Visual Apink Panda Food Café Panel (粉熊美食小食堂).

Upgrades the legacy 27-row plain-text cascade menu into an interactive, spoiler-free
visual food discovery panel:
- Consistent rounded glassmorphism card styling aligned with StatusCard & MemberProfileCard.
- Category tabs driven strictly by `app.foods.get_food_kind` ("all", "meal", "dessert", "drink")
  while preserving `FOOD_ITEMS` canonical order.
- Displays 64x64 full-color food icons from `work/foods/{id}_64.png` (with emoji/name fallback).
- Progressive Food Discovery (美食圖鑑蓋章機制):
  - Driven strictly by `outcomes: Mapping[str, str]` (`{food_id: 'favourite'|'normal'|'disliked'}`)
    from `app.food_log.outcomes(runtime, char_key)`.
  - Never infers or guesses favorites/disliked from `FOOD_ITEMS` metadata.
  - Locked foods (`food_id not in outcomes`) show ONLY the icon and food name (zero desc spoilers).
  - Unlocked foods (`food_id in outcomes`) map outcomes via:
    `{"favourite": "favorite", "disliked": "disliked", "normal": "tasted"}`.
- Pure UI module: does not import `app.main`, does not write files, does not self-redraw stamps
  inside `trigger_feed` (waits for `main` to call `refresh(outcomes=...)` after persistence succeeds).
"""
from __future__ import annotations

from collections.abc import Mapping
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from typing import Any, Callable, Optional
from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.food_log import ALLOWED_OUTCOMES
from app.foods import (
    DRINK_KINDS,
    FOOD_ITEMS,
    SATIETY_FULL_THRESHOLD,
    get_food_kind,
    get_food_name,
)
from app.i18n import get_member_display_name
from app.paths import resource_dir
from app.platform.win32 import WindowsDesktopAdapter, WorkArea
from app.resource_store import open_resource_image, resource_exists
from app.status_card import MEMBER_THEMES

BG_TRANSPARENT = "#ff00fe"
ROOT = resource_dir()
FOODS_DIR = ROOT / "work" / "foods"
_VALID_FOOD_IDS = frozenset(item["id"] for item in FOOD_ITEMS)
_SHORT_TILE_NAMES = {
    "en": {
        "tw_beef_noodle": "Beef Noodle Soup",
        "tw_xiaolongbao": "Xiaolongbao",
        "tw_mala_dual_hotpot": "Dual Mala Hot Pot",
        "tw_intestine_vermicelli": "Intestine Noodles",
        "tw_scallion_pancake": "Scallion Pancake",
        "kr_kotdoritang": "Crab & Chicken Stew",
        "tw_potstickers": "Potstickers",
        "tw_century_egg_tofu": "Century Egg Tofu",
        "tw_pineapple_cake": "Pineapple Cake",
        "tw_sweet_potato_balls": "Sweet Potato Balls",
        "tw_brown_sugar_boba": "Brown Sugar Boba",
        "tw_strawberry_boba": "Strawberry Boba",
        "tw_wintermelon_tea": "Winter Melon Tea",
    },
    "ko": {"tw_pineapple_cake": "파인애플 케이크"},
}
_BADGE_MAP: dict[str, str] = {
    "favourite": "favorite",
    "disliked": "disliked",
    "normal": "tasted",
}
_FOOD_ICON_PIL_CACHE: dict[tuple[str, int], Image.Image] = {}
_FOOD_ICON_SRC_CACHE: dict[str, Optional[Path]] = {}
_FITTED_LAYOUT_CACHE: dict[tuple[int, int, int, int, float], tuple[float, float, int, int]] = {}

CAFE_I18N = {
    "title": {
        "zh_TW": "🍱 粉熊美食小食堂",
        "ko": "🍱 판다 미식 식당",
        "en": "🍱 Panda Food Café",
    },
    "satiety_label": {
        "zh_TW": "飽腹度",
        "ko": "포만감",
        "en": "Satiety",
    },
    "satiety_full_hint": {
        "zh_TW": "吃飽飽囉（可喝飲品）",
        "ko": "배불러요 (음료 가능)",
        "en": "Full (Drinks OK)",
    },
    "pokedex_label": {
        "zh_TW": "美食圖鑑 {done}/{total}",
        "ko": "미식 도감 {done}/{total}",
        "en": "Food Log {done}/{total}",
    },
    "tab_all": {
        "zh_TW": "🍽️ 全部",
        "ko": "🍽️ 전체",
        "en": "🍽️ All",
    },
    "tab_meal": {
        "zh_TW": "🍲 美味主食",
        "ko": "🍲 든든한 주식",
        "en": "🍲 Main Dishes",
    },
    "tab_dessert": {
        "zh_TW": "🍰 甜點烘焙",
        "ko": "🍰 디저트·빵",
        "en": "🍰 Desserts",
    },
    "tab_drink": {
        "zh_TW": "🥤 飲品小酌",
        "ko": "🥤 음료·주류",
        "en": "🥤 Drinks",
    },
    "legend": {
        "zh_TW": "💖 本命最愛：開心享用   ⚡ 避雷：搖頭拒吃   （餵過才揭曉）",
        "ko": "💖 최애: 행복하게 먹기   ⚡ 기피: 고개 저으며 거절   (먹여 봐야 공개)",
        "en": "💖 Favourite: savoured   ⚡ Disliked: refused   (revealed once fed)",
    },
    "stamp_fav": {
        "zh_TW": "💖 本命",
        "ko": "💖 최애",
        "en": "💖 Fav",
    },
    "stamp_disliked": {
        "zh_TW": "⚡ 避雷",
        "ko": "⚡ 기피",
        "en": "⚡ Nope",
    },
}


def filter_foods_by_tab(tab_key: str) -> list[dict]:
    """Filter FOOD_ITEMS strictly via `app.foods.get_food_kind`, preserving FOOD_ITEMS order."""
    if tab_key == "all":
        return list(FOOD_ITEMS)
    if tab_key == "meal":
        return [f for f in FOOD_ITEMS if get_food_kind(f) == "meal"]
    if tab_key == "dessert":
        return [f for f in FOOD_ITEMS if get_food_kind(f) == "dessert"]
    if tab_key == "drink":
        return [f for f in FOOD_ITEMS if get_food_kind(f) in DRINK_KINDS]
    return [f for f in FOOD_ITEMS if get_food_kind(f) == tab_key]


def _sanitize_outcomes(raw: object) -> dict[str, str]:
    """Copy valid food_id -> outcome entries where outcome is in ALLOWED_OUTCOMES."""
    if not isinstance(raw, Mapping):
        return {}
    cleaned: dict[str, str] = {}
    for fid, outcome in raw.items():
        if isinstance(fid, str) and fid in _VALID_FOOD_IDS and isinstance(outcome, str):
            if outcome in ALLOWED_OUTCOMES:
                cleaned[fid] = outcome
    return cleaned


def _coerce_work_area(
    work_area: tuple[int, int, int, int] | WorkArea | None,
) -> Optional[WorkArea]:
    if isinstance(work_area, WorkArea):
        return work_area
    if isinstance(work_area, (tuple, list)) and len(work_area) == 4:
        try:
            left, top, right, bottom = (int(v) for v in work_area)
            if right > left and bottom > top:
                return WorkArea(left, top, right, bottom)
        except (TypeError, ValueError):
            return None
    return None


class FoodCafePanel:
    """Interactive visual Food Café panel with spoiler-free Food Pokedex stamps."""

    TABS = ("meal", "dessert", "drink")
    COLS = 6
    VISIBLE_ROWS = 5
    LAYOUT_W = 612
    LAYOUT_H = 658

    def __init__(
        self,
        parent: tk.Misc,
        lang: str = "zh_TW",
        char_key: str = "chorong",
        satiety_getter: Optional[Callable[[], float]] = None,
        outcomes: Optional[Mapping[str, str]] = None,
        on_feed: Optional[Callable[[str], Any]] = None,
        on_close: Optional[Callable[[], None]] = None,
        work_area: tuple[int, int, int, int] | WorkArea | None = None,
    ) -> None:
        self.parent = parent
        self.lang = lang if lang in ("zh_TW", "ko", "en") else "zh_TW"
        self.char_key = char_key if char_key in MEMBER_THEMES else "chorong"
        self.satiety_getter = satiety_getter or (lambda: 50.0)
        self.outcomes: dict[str, str] = _sanitize_outcomes(outcomes)
        self.on_feed = on_feed
        self.on_close = on_close
        self._explicit_work_area: Optional[WorkArea] = _coerce_work_area(work_area)
        self.last_feed_result: Any = None
        self._scroll_row = 0
        self._max_scroll = 0

        self.active_tab: str = "meal"
        self._closed = False
        self._drag_offset = (0, 0)
        self._dragging = False
        self._pressed_tag: Optional[str] = None
        self._icon_cache: dict[str, ImageTk.PhotoImage] = {}

        self.window = tk.Toplevel(parent)
        self._desktop = WindowsDesktopAdapter(fallback_bounds=self._tk_fallback_work_area)
        # Canvas coordinates and images use pixels; positive font sizes use points.
        # Match both to the same 96-DPI design instead of shrinking system fonts.
        self._raw_ui_scale = max(1.0, min(4.0, self.window.winfo_fpixels("1i") / 96.0))
        self.ui_scale = self._raw_ui_scale
        self._font_scale = 1.0
        self.w = round(self.LAYOUT_W * self.ui_scale)
        self.h = round(self.LAYOUT_H * self.ui_scale)
        self._compute_fitted_layout()
        self._label_font = tkfont.Font(
            self.window,
            family="Microsoft JhengHei UI",
            size=self._fpt(8),
            weight="bold",
        )
        self.win = self.window  # Alias for StatusCard (.window) and ProfileCard (.win) conventions
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.window.configure(bg=BG_TRANSPARENT)

        self.canvas = tk.Canvas(
            self.window,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._position_near_parent()
        self._load_food_icons()
        self._render()

        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_begin)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.window.bind("<Escape>", lambda _e: self.close())

    def _tk_fallback_work_area(self) -> WorkArea:
        try:
            sw = max(640, int(self.window.winfo_screenwidth()))
            sh = max(480, int(self.window.winfo_screenheight()))
        except Exception:
            sw, sh = 1920, 1080
        return WorkArea(0, 0, sw, sh)

    def _active_work_area(self, anchor_x: int, anchor_y: int) -> WorkArea:
        if self._explicit_work_area is not None:
            return self._explicit_work_area
        try:
            return self._desktop.work_area_for_point(anchor_x, anchor_y)
        except Exception:
            return self._tk_fallback_work_area()

    def _compute_fitted_layout(self) -> None:
        try:
            px = int(self.parent.winfo_rootx()) + max(1, int(self.parent.winfo_width())) // 2
            py = int(self.parent.winfo_rooty()) + max(1, int(self.parent.winfo_height())) // 2
        except Exception:
            px, py = 300, 200
        area = self._active_work_area(px, py)
        cache_key = (area.left, area.top, area.right, area.bottom, round(self._raw_ui_scale, 4))
        cached = _FITTED_LAYOUT_CACHE.get(cache_key)
        if cached is not None:
            self._font_scale, self.ui_scale, self.w, self.h = cached
            return
        avail_w = max(320, area.width - 16)
        avail_h = max(360, area.height - 16)
        raw_w = self.LAYOUT_W * self._raw_ui_scale
        raw_h = self.LAYOUT_H * self._raw_ui_scale
        fit = 1.0
        if raw_w > avail_w or raw_h > avail_h:
            fit = min(avail_w / max(1.0, raw_w), avail_h / max(1.0, raw_h))
        self._font_scale = fit
        self.ui_scale = max(0.5, self._raw_ui_scale * fit)
        self.w = max(320, min(avail_w, round(self.LAYOUT_W * self.ui_scale)))
        self.h = max(360, min(avail_h, round(self.LAYOUT_H * self.ui_scale)))
        _FITTED_LAYOUT_CACHE[cache_key] = (self._font_scale, self.ui_scale, self.w, self.h)

    def _fpt(self, pt: int) -> int:
        return max(6, round(pt * self._font_scale)) if self._font_scale < 0.999 else pt

    def _tr(self, key: str) -> str:
        table = CAFE_I18N.get(key, {})
        return table.get(self.lang, table.get("zh_TW", key))

    def _hwnd(self) -> int:
        self.window.update_idletasks()
        frame = self.window.wm_frame()
        if frame:
            return int(frame, 16) if frame.startswith("0x") else int(frame)
        return int(self.window.winfo_id())

    def _move_window(self, x: int, y: int) -> None:
        """Place window at virtual-desktop (x, y) via Win32 SetWindowPos to avoid Tk -x right-edge semantics."""
        self.last_clamped_pos = (int(x), int(y))
        # Set size with non-negative placeholder first so Tk never interprets -x as right-edge offset
        if self.window.winfo_width() != self.w or self.window.winfo_height() != self.h:
            self.window.geometry(f"{self.w}x{self.h}+{max(0, int(x))}+{max(0, int(y))}")
        hwnd = self._hwnd()
        if not self._desktop.position_without_activation(hwnd, int(x), int(y)):
            if x >= 0 and y >= 0:
                self.window.geometry(f"{self.w}x{self.h}+{int(x)}+{int(y)}")

    def _position_near_parent(self) -> None:
        try:
            px = int(self.parent.winfo_rootx())
            py = int(self.parent.winfo_rooty())
            pw = max(1, int(self.parent.winfo_width()))
            ph = max(1, int(self.parent.winfo_height()))
        except Exception:
            px, py, pw, ph = 300, 200, 192, 192

        work = self._active_work_area(px + pw // 2, py + ph // 2)
        cand_x = px - self.w - 16
        if cand_x < work.left:
            cand_x = px + pw + 16
        x, y = work.clamp(cand_x, py - 40, self.w, self.h)
        self._move_window(x, y)

    def _load_food_icons(self) -> None:
        from app.resource_store import resource_store

        size = max(16, round(46 * self.ui_scale))
        missing = [
            item["id"]
            for item in FOOD_ITEMS
            if item["id"] not in self._icon_cache and (item["id"], size) not in _FOOD_ICON_PIL_CACHE
        ]
        if missing:
            with resource_store().session():
                for fid in missing:
                    if fid not in _FOOD_ICON_SRC_CACHE:
                        p64 = FOODS_DIR / f"{fid}_64.png"
                        p128 = FOODS_DIR / f"{fid}.png"
                        _FOOD_ICON_SRC_CACHE[fid] = (
                            p128 if resource_exists(p128)
                            else (p64 if resource_exists(p64) else None)
                        )
                    src_path = _FOOD_ICON_SRC_CACHE.get(fid)
                    if src_path is not None:
                        try:
                            with open_resource_image(src_path) as im:
                                rgba = im.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                                r, g, b, a = rgba.split()
                                a_bin = a.point(lambda v: 255 if v >= 128 else 0)
                                _FOOD_ICON_PIL_CACHE[(fid, size)] = Image.merge("RGBA", (r, g, b, a_bin))
                        except Exception:
                            pass
        for item in FOOD_ITEMS:
            fid = item["id"]
            if fid in self._icon_cache:
                continue
            cached_pil = _FOOD_ICON_PIL_CACHE.get((fid, size))
            if cached_pil is not None:
                try:
                    self._icon_cache[fid] = ImageTk.PhotoImage(cached_pil, master=self.window)
                except Exception:
                    pass

    def _current_satiety(self) -> float:
        try:
            val = float(self.satiety_getter())
        except Exception:
            val = 50.0
        return max(0.0, min(100.0, val))

    def get_visible_foods(self) -> list[dict]:
        """Return the list of food items shown in the current category tab in FOOD_ITEMS order."""
        return filter_foods_by_tab(self.active_tab)

    def get_tile_badge(self, food_id: str) -> Optional[str]:
        """Map `self.outcomes.get(food_id)` to 'favorite' | 'disliked' | 'tasted' | None.

        Never consults `FOOD_ITEMS['favorites']` or `FOOD_ITEMS['disliked']`.
        """
        return _BADGE_MAP.get(self.outcomes.get(food_id, ""))

    def select_tab(self, tab_key: str) -> None:
        """Switch category tab and re-render the food grid."""
        if self._closed:
            return
        self.active_tab = tab_key
        self._scroll_row = 0
        self._render()

    def trigger_feed(self, food_id: str) -> Any:
        """Invoke `on_feed(food_id)` without self-redrawing stamps; main calls `refresh(outcomes=...)`."""
        if self._closed:
            return None
        result = self.on_feed(food_id) if self.on_feed is not None else None
        self.last_feed_result = result
        return result

    def refresh(
        self,
        char_key: Optional[str] = None,
        lang: Optional[str] = None,
        outcomes: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Update member, language, or outcomes in-place and redraw."""
        if self._closed:
            return
        if char_key is not None and char_key in MEMBER_THEMES:
            self.char_key = char_key
        if lang is not None and lang in ("zh_TW", "ko", "en"):
            self.lang = lang
        if outcomes is not None:
            self.outcomes = _sanitize_outcomes(outcomes)
        self._render()

    def update_outcomes(
        self,
        outcomes: Mapping[str, str],
        char_key: Optional[str] = None,
    ) -> None:
        """Convenience helper for refreshing `outcomes` after a persisted feed."""
        self.refresh(char_key=char_key, outcomes=outcomes)

    def set_language(self, lang: str) -> None:
        """Switch UI language dynamically."""
        self.refresh(lang=lang)

    def _tile_label(self, food: dict) -> str:
        short_name = _SHORT_TILE_NAMES.get(self.lang, {}).get(food["id"])
        return self._fit_tile_label(short_name or get_food_name(food, self.lang))

    def _fit_tile_label(self, text: str, max_width: float = 78) -> str:
        """Use at most two measured lines; shorten only the final line."""
        limit = max_width * self.ui_scale
        if self._label_font.measure(text) <= limit:
            return text
        split = 0
        while split < len(text) and self._label_font.measure(text[:split + 1]) <= limit:
            split += 1
        # Prefer a complete word for spaced languages, otherwise break by glyph.
        space = text.rfind(" ", 0, split + 1)
        if space > 0:
            split = space
        first, last = text[:split].rstrip(), text[split:].lstrip()
        if self._label_font.measure(last) > limit:
            while last and self._label_font.measure(last + "…") > limit:
                last = last[:-1]
            last = last.rstrip() + "…"
        return first + "\n" + last

    def _render(self) -> None:
        if self._closed:
            return
        cv = self.canvas
        w, h = self.LAYOUT_W, self.LAYOUT_H
        cv.delete("all")

        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        primary = theme["primary"]
        soft_bg = theme["soft_bg"]
        header_fill = theme["header_fill"]
        border_col = theme["border"]
        pill_fill = theme["pill_fill"]
        bar_fill = theme["bar_fill"]
        member_icon = theme["icon"]

        # 1. Outer drop-glow & main rounded card body
        _draw_round_rect(cv, 6, 6, w - 6, h - 6, r=26, fill=border_col, outline="")
        _draw_round_rect(cv, 10, 10, w - 10, h - 10, r=24, fill=soft_bg, outline=primary, width=2)

        # 2. Header banner (y = 18..106)
        _draw_round_rect(cv, 20, 18, w - 20, 106, r=18, fill=header_fill, outline=border_col, width=1)

        cv.create_text(
            34,
            37,
            text=self._tr("title"),
            anchor="w",
            fill="#3B1E1E",
            font=("Microsoft JhengHei UI", 13, "bold"),
        )
        member_label = get_member_display_name(self.char_key, self.lang)
        cv.create_text(
            235,
            38,
            text=f"{member_icon} {member_label}",
            anchor="w",
            fill=primary,
            font=("Microsoft JhengHei UI", 10, "bold"),
        )

        # Close button (top-right)
        _draw_round_rect(
            cv,
            w - 58,
            24,
            w - 28,
            52,
            r=10,
            fill="#ffffff",
            outline=border_col,
            width=1,
            tags=("btn_close",),
        )
        cv.create_text(
            w - 43,
            38,
            text="✕",
            fill=primary,
            font=("Segoe UI", 10, "bold"),
            tags=("btn_close",),
        )

        # Satiety bar + Food Pokedex counter row inside header
        satiety = self._current_satiety()
        satiety_int = int(round(satiety))
        cv.create_text(
            34,
            70,
            text=f"{self._tr('satiety_label')} {satiety_int}%",
            anchor="w",
            fill="#4A2535",
            font=("Microsoft JhengHei UI", 9, "bold"),
            tags=("satiety_label",),
        )

        bar_x1, bar_y1, bar_x2, bar_y2 = 128, 62, 318, 78
        _draw_round_rect(cv, bar_x1, bar_y1, bar_x2, bar_y2, r=8, fill="#ffffff", outline=border_col, width=1)
        fill_w = int((bar_x2 - bar_x1 - 4) * (satiety / 100.0))
        if fill_w > 6:
            active_bar_color = "#ef5350" if satiety >= SATIETY_FULL_THRESHOLD else bar_fill
            _draw_round_rect(
                cv,
                bar_x1 + 2,
                bar_y1 + 2,
                bar_x1 + 2 + fill_w,
                bar_y2 - 2,
                r=6,
                fill=active_bar_color,
                outline="",
            )

        if satiety >= SATIETY_FULL_THRESHOLD:
            # Placed below the satiety bar (y=92) so it never collides with pokedex_pill (x=428..584)
            cv.create_text(
                bar_x1,
                92,
                text=self._tr("satiety_full_hint"),
                anchor="w",
                fill="#c62828",
                font=("Microsoft JhengHei UI", 8, "bold"),
                tags=("satiety_full_hint",),
            )

        # Pokedex unlocked count pill (dynamic denominator len(FOOD_ITEMS))
        done_count = len(self.outcomes.keys() & _VALID_FOOD_IDS)
        pokedex_txt = self._tr("pokedex_label").format(done=done_count, total=len(FOOD_ITEMS))
        _draw_round_rect(
            cv,
            w - 184,
            60,
            w - 28,
            88,
            r=12,
            fill="#ffffff",
            outline=border_col,
            width=1,
            tags=("pokedex_pill",),
        )
        cv.create_text(
            w - 106,
            74,
            text=pokedex_txt,
            anchor="center",
            fill=primary,
            font=("Microsoft JhengHei UI", 9, "bold"),
            tags=("pokedex_text",),
        )

        # 3. Category Tabs bar (driven by get_food_kind, y = 114..148)
        tab_y1, tab_y2 = 114, 148
        tab_w = (w - 40 - 10 * (len(self.TABS) - 1)) // len(self.TABS)
        for idx, t_key in enumerate(self.TABS):
            tx1 = 20 + idx * (tab_w + 10)
            tx2 = tx1 + tab_w
            is_active = self.active_tab == t_key
            t_fill = primary if is_active else pill_fill
            t_fg = "#ffffff" if is_active else "#4A2535"
            t_border = primary if is_active else border_col
            count = len(filter_foods_by_tab(t_key))
            label = f"{self._tr(f'tab_{t_key}')} ({count})"
            tag = f"tab_{t_key}"

            _draw_round_rect(cv, tx1, tab_y1, tx2, tab_y2, r=14, fill=t_fill, outline=t_border, width=1, tags=(tag,))
            cv.create_text(
                (tx1 + tx2) // 2,
                (tab_y1 + tab_y2) // 2,
                text=label,
                fill=t_fg,
                font=("Microsoft JhengHei UI", 9, "bold"),
                tags=(tag,),
            )

        # 4. Food Grid (6 columns x up to 5 rows, y = 156..608, leaving 8px gap above footer y=616)
        foods = self.get_visible_foods()
        grid_x0 = 22
        grid_y0 = 156
        tile_w = 88
        tile_h = 84
        gap_x = 8
        gap_y = 8

        self._max_scroll = max(0, (len(foods) + self.COLS - 1) // self.COLS - self.VISIBLE_ROWS)
        self._scroll_row = max(0, min(self._scroll_row, self._max_scroll))
        if self._max_scroll:               # thin bar right of the tiles; the wheel scrolls one row
            bar_x = grid_x0 + self.COLS * (tile_w + gap_x) - 2
            track_h = self.VISIBLE_ROWS * (tile_h + gap_y) - gap_y
            rows_total = self._max_scroll + self.VISIBLE_ROWS
            top = grid_y0 + track_h * self._scroll_row // rows_total
            _draw_round_rect(cv, bar_x, grid_y0, bar_x + 5, grid_y0 + track_h, r=2, fill=header_fill, outline="")
            _draw_round_rect(cv, bar_x, top, bar_x + 5, top + track_h * self.VISIBLE_ROWS // rows_total,
                             r=2, fill=primary, outline="")

        for idx, food in enumerate(foods):
            row = idx // self.COLS - self._scroll_row
            if not 0 <= row < self.VISIBLE_ROWS:
                continue
            col = idx % self.COLS
            x1 = grid_x0 + col * (tile_w + gap_x)
            y1 = grid_y0 + row * (tile_h + gap_y)
            x2 = x1 + tile_w
            y2 = y1 + tile_h

            fid = food["id"]
            tag = f"food_{fid}"
            badge = self.get_tile_badge(fid)

            if badge == "favorite":
                tile_fill = "#fff0f5"
                tile_border = "#ec407a"
                border_w = 2
            elif badge == "disliked":
                tile_fill = "#f5f0ff"
                tile_border = "#8e24aa"
                border_w = 2
            else:
                tile_fill = "#ffffff"
                tile_border = "#e6d5dc"
                border_w = 1

            _draw_round_rect(
                cv,
                x1,
                y1,
                x2,
                y2,
                r=14,
                fill=tile_fill,
                outline=tile_border,
                width=border_w,
                tags=(tag,),
            )

            cx = (x1 + x2) // 2
            photo = self._icon_cache.get(fid)
            if photo is not None:
                cv.create_image(cx, y1 + 31, image=photo, tags=(tag,))
            else:
                cv.create_text(
                    cx,
                    y1 + 31,
                    text=food.get("emoji", "🍽️"),
                    font=("Segoe UI Emoji", 20),
                    tags=(tag,),
                )

            # Spoiler-free food name (never renders desc_i18n)
            disp_name = self._tile_label(food)
            cv.create_text(
                cx,
                y2 - 15,
                text=disp_name,
                fill="#3B1E1E",
                font=("Microsoft JhengHei UI", 8, "bold"),
                tags=(tag,),
            )

            # Discovery Stamp (ONLY rendered for favorite / disliked; normal tasted items do not draw a checkmark)
            if badge == "favorite":
                _draw_round_rect(
                    cv,
                    x2 - 44,
                    y1 + 3,
                    x2 - 3,
                    y1 + 20,
                    r=7,
                    fill="#ff4081",
                    outline="",
                    tags=(tag,),
                )
                cv.create_text(
                    x2 - 23,
                    y1 + 11,
                    text=self._tr("stamp_fav"),
                    fill="#ffffff",
                    font=("Microsoft JhengHei UI", 7, "bold"),
                    tags=(tag,),
                )
            elif badge == "disliked":
                _draw_round_rect(
                    cv,
                    x2 - 44,
                    y1 + 3,
                    x2 - 3,
                    y1 + 20,
                    r=7,
                    fill="#7b1fa2",
                    outline="",
                    tags=(tag,),
                )
                cv.create_text(
                    x2 - 23,
                    y1 + 11,
                    text=self._tr("stamp_disliked"),
                    fill="#ffffff",
                    font=("Microsoft JhengHei UI", 7, "bold"),
                    tags=(tag,),
                )

        # 5. Footer discovery legend bar (y = 616..642)
        _draw_round_rect(
            cv,
            20,
            h - 42,
            w - 20,
            h - 16,
            r=10,
            fill=header_fill,
            outline=border_col,
            width=1,
            tags=("footer_bar",),
        )
        cv.create_text(
            w // 2,
            h - 29,
            text=self._tr("legend"),
            fill="#4A2535",
            font=("Microsoft JhengHei UI", 8, "bold"),
            tags=("footer_text",),
        )

        if self._font_scale < 0.999:
            for item in cv.find_all():
                if cv.type(item) == "text":
                    f_raw = cv.itemcget(item, "font")
                    try:
                        actual = tkfont.Font(root=self.window, font=f_raw).actual()
                        sz = abs(int(actual.get("size", 8)))
                        wt = actual.get("weight", "normal")
                        new_sz = self._fpt(sz)
                        cv.itemconfigure(
                            item,
                            font=(actual.get("family", "Microsoft JhengHei UI"), new_sz, "bold")
                            if wt == "bold"
                            else (actual.get("family", "Microsoft JhengHei UI"), new_sz),
                        )
                    except Exception:
                        pass

        # Scale each freshly rendered item exactly once. Canvas.scale preserves
        # text point sizes and image sizes; the latter were loaded at physical DPI.
        cv.scale("all", 0, 0, self.ui_scale, self.ui_scale)
        for item in cv.find_all():
            if cv.type(item) in ("polygon", "line", "rectangle", "oval"):
                cv.itemconfigure(item, width=float(cv.itemcget(item, "width")) * self.ui_scale)

    def _on_wheel(self, event: tk.Event) -> None:
        self.scroll_rows(-1 if event.delta > 0 else 1)

    def scroll_rows(self, rows: int) -> None:
        new = max(0, min(self._scroll_row + rows, self._max_scroll))
        if new != self._scroll_row and not self._closed:
            self._scroll_row = new
            self._render()

    def _interactive_tag_at(self, event: tk.Event) -> Optional[str]:
        x = getattr(event, "x", None)
        y = getattr(event, "y", None)
        items = (
            self.canvas.find_overlapping(x, y, x, y)
            if x is not None and y is not None
            else self.canvas.find_withtag("current")
        )
        for item in reversed(items):
            for t in self.canvas.gettags(item):
                if t.startswith(("food_", "tab_", "btn_")):
                    return t
        for t in self.canvas.gettags("current"):
            if t.startswith(("food_", "tab_", "btn_")):
                return t
        return None

    def _on_drag_begin(self, event: tk.Event) -> None:
        hit = self._interactive_tag_at(event)
        # Do not lift or start drag when clicking interactive tiles/tabs/close so speech bubbles stay above
        if hit is not None:
            self._pressed_tag = hit
            self._dragging = False
            return
        self._pressed_tag = None
        self._dragging = True
        self.window.lift()
        self._drag_offset = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self._dragging or self._closed:
            return
        nx = event.x_root - self._drag_offset[0]
        ny = event.y_root - self._drag_offset[1]
        work = self._active_work_area(event.x_root, event.y_root)
        cx, cy = work.clamp(nx, ny, self.w, self.h)
        self._move_window(cx, cy)

    def _on_drag_end(self, event: tk.Event) -> None:
        self._dragging = False
        pressed, self._pressed_tag = self._pressed_tag, None
        if pressed is None or self._closed:
            return
        released = self._interactive_tag_at(event)
        if released != pressed:
            return
        if pressed == "btn_close":
            self.close()
        elif pressed.startswith("tab_"):
            self.select_tab(pressed[4:])
        elif pressed.startswith("food_"):
            self.trigger_feed(pressed[5:])

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        # The closed panel sits in Tk-callback cycles until a full gc pass; drop its
        # 56 food icons now instead (2026-11-22: +56 Tk images per open in the combo run).
        self._icon_cache.clear()
        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass
