"""app/pink_context_menu.py — Custom Apink Pink Rounded Context Menu & RAM Notification Drawer.

Replaces the native Windows gray `tk.Menu` with a borderless, rounded kawaii Apink pink card
popup (`PinkContextMenu`) and a companion RAM-only 20-item notification drawer (`NotificationDrawerWindow`):
- Uses hand-drawn icons from `work/ui_icons/icon_*.png` (sliced from `新版右鍵快捷面板核心圖示.jpg` & `2.jpg`).
- Supports `zh_TW`, `ko`, and `en` live localization via `app.i18n.t`.
- Clamps both main menu and flyout submenu to the active monitor work area via `WindowsDesktopAdapter`.
- Auto-closes on outside click, `Escape`, or item execution.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Any, Optional
from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.i18n import get_member_display_name, t
from app.paths import is_developer_mode, resource_dir
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, scale_canvas, ui_scale
from app.resource_store import open_resource_image, resource_exists
from app.status_card import MEMBER_THEMES

_WALLPAPER_LABEL = {"zh_TW": "✦ {name}待機", "ko": "✦ {name} 대기화면", "en": "✦ {name} Screensaver"}
_WALLPAPER_CACHE: list = []
_WALLPAPER_LOCK = threading.RLock()
# Cached PIL images are shared read-only across menus; never mutate in-place.
_ICON_PIL_CACHE: dict[tuple[str, int], Image.Image] = {}
_ICON_PIL_LOCK = threading.RLock()
_CORE_UI_ICONS = (
    "icon_paws", "icon_chat", "icon_food", "icon_trophy",
    "icon_photo", "icon_sleep", "icon_clock", "icon_settings",
)
FLYOUT_MAX_W = 460          # design px; longer labels are elided
FLYOUT_TEXT_PAD = 46        # label x (22) + right padding inside the card
FLYOUT_SCREEN_MARGIN = 10
FLYOUT_MIN_ROW_H = 26       # tall lists shrink rows down to this before scrolling off-screen
DRAWER_MUTED = "#4d4d4d"    # secondary drawer text, >= 6.5:1 on every theme header / card


def _wallpapers() -> tuple:
    """The approved standby wallpapers, hash-checked once per run (not on every right click)."""
    with _WALLPAPER_LOCK:
        if not _WALLPAPER_CACHE:
            try:
                from app.standby import load_wallpapers
                _WALLPAPER_CACHE.append(tuple(load_wallpapers()))
            except Exception:
                _WALLPAPER_CACHE.append(())
        return _WALLPAPER_CACHE[0]


def _load_icon_pil(icon_name: str, size: int = 22, root: Path | None = None) -> Optional[Image.Image]:
    """Thread-safe pure-PIL load and LANCZOS resize of a UI icon, cached across menu opens."""
    clean_name = icon_name if icon_name.endswith(".png") else f"{icon_name}.png"
    icons_dir = (Path(root) / "work" / "ui_icons") if root is not None else UI_ICONS_DIR
    eff_root = Path(root) if root is not None else UI_ICONS_DIR.parent.parent
    key = (str(icons_dir), clean_name, int(size))
    with _ICON_PIL_LOCK:
        cached = _ICON_PIL_CACHE.get(key)
        if cached is not None:
            return cached
    p = icons_dir / clean_name
    if not resource_exists(p, root=eff_root):
        return None
    try:
        with open_resource_image(p, root=eff_root) as raw:
            im = raw.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        with _ICON_PIL_LOCK:
            _ICON_PIL_CACHE[key] = im
        return im
    except Exception:
        return None


def warm_context_menu_assets(root: Path | None = None, scales: Sequence[float] = (1.0, 1.25, 1.5, 1.75, 2.0),
                             yield_fn: Optional[Callable[[], None]] = None) -> None:
    """Thread-safe background pre-decode of the 8 UI icons and standby wallpapers (never touches Tk)."""
    for scale in scales:
        px = max(1, round(22 * scale))
        for name in _CORE_UI_ICONS:
            if yield_fn is not None:
                yield_fn()
            _load_icon_pil(name, px, root=root)
    if yield_fn is not None:
        yield_fn()
    _wallpapers()


def _bmp_safe_text(text: str) -> str:
    """Replace non-BMP astral emoji and slow fallback Dingbats with fast native BMP symbols on Canvas."""
    out: list[str] = []
    for ch in text.replace("\ufe0f", ""):
        code = ord(ch)
        if code > 0xFFFF:
            out.append("♥" if ch in ("🎀", "💖", "🩷", "🌸") else "•")
        elif ch in ("✨", "⚙", "✦"):
            out.append("★" if ch in ("✨", "✦") else "•")
        else:
            out.append(ch)
    return "".join(out)

BG_TRANSPARENT = "#ff00fe"
ROOT = resource_dir()
UI_ICONS_DIR = ROOT / "work" / "ui_icons"


def _font_family(lang: str) -> str:
    if lang == "ko":
        return "Malgun Gothic"
    if lang == "en":
        return "Segoe UI"
    return "Microsoft JhengHei"


class MenuItemSpec:
    """Specification for a row in `PinkContextMenu` or its flyout submenu."""

    def __init__(
        self,
        label: str,
        command: Optional[Callable[[], Any]] = None,
        *,
        icon_name: Optional[str] = None,
        submenu: Optional[Sequence["MenuItemSpec"]] = None,
        checked: bool = False,
        badge: Optional[str] = None,
        is_danger: bool = False,
        is_separator: bool = False,
        tag_id: Optional[str] = None,
    ) -> None:
        self.label = label
        self.command = command
        self.icon_name = icon_name
        self.submenu = list(submenu) if submenu else None
        self.checked = checked
        self.badge = badge
        self.is_danger = is_danger
        self.is_separator = is_separator
        self.tag_id = tag_id or ""


class PinkContextMenu:
    """Custom borderless Apink Pink Rounded Right-Click Context Menu."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        lang: str = "zh_TW",
        char_key: str = "chorong",
        title: str = "",
        subtitle: str = "",
        items: Sequence[MenuItemSpec],
        anchor_x: int = 300,
        anchor_y: int = 300,
        work_area: tuple[int, int, int, int] | WorkArea | None = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.lang = lang if lang in ("zh_TW", "ko", "en") else "zh_TW"
        self.char_key = char_key if char_key in MEMBER_THEMES else "chorong"
        self.title = title or get_member_display_name(self.char_key, self.lang)
        self.subtitle = subtitle
        self.items = list(items)
        self.on_close = on_close
        self._closed = False
        self._hover_idx: Optional[int] = None
        self._active_sub_idx: Optional[int] = None
        self._sub_window: Optional[tk.Toplevel] = None
        self._sub_canvas: Optional[tk.Canvas] = None
        self._sub_hover_idx: Optional[int] = None
        self._peek_window: Optional[tk.Toplevel] = None
        self._peek_canvas: Optional[tk.Canvas] = None
        self._peek_row: Optional[int] = None
        self._peek_items: list[MenuItemSpec] = []
        self._peek_bounds: list = []
        self._peek_hover: Optional[int] = None
        self._sub_items: list[MenuItemSpec] = []
        self._pressed_sub_item: int | None = None
        self._pressed_peek_item: int | None = None
        self._icon_refs: dict[str, ImageTk.PhotoImage] = {}
        self.last_clamped_pos: tuple[int, int] = (0, 0)
        self.last_sub_clamped_pos: tuple[int, int] = (0, 0)

        self._desktop = WindowsDesktopAdapter(fallback_bounds=self._tk_fallback_work_area)
        self._explicit_work_area = self._coerce_work_area(work_area)

        self._design_w = 316
        self._row_h = 36
        self._sep_h = 10
        self._header_h = 52
        self._design_h = self._compute_height(self.items, include_header=True)
        self._sub_design_size: tuple[int, int] = (324, 120)
        self._peek_design_size: tuple[int, int] = (300, 120)
        self._sub_row_h = self._peek_row_h = self._row_h
        self._sub_text_px: int | None = None
        self._peek_text_px: int | None = None

        self.window = tk.Toplevel(parent)
        self.win = self.window
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.window.configure(bg=BG_TRANSPARENT)
        work = self._active_work_area(anchor_x, anchor_y)
        self.ui_scale = min(ui_scale(self.window), work.width / self._design_w, work.height / self._design_h)
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)

        self.canvas = tk.Canvas(
            self.window,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._row_bounds: list[tuple[int, int, int]] = []
        self._sub_row_bounds: list[tuple[int, int, int]] = []

        cx, cy = work.clamp(anchor_x, anchor_y, self.w, self.h)
        self._render_main()
        self._move_window(self.window, cx, cy, self.w, self.h, is_sub=False)

        self._pressed_main_item: int | None = None
        self.canvas.bind("<Motion>", self._on_main_motion)
        self.canvas.bind("<ButtonPress-1>", self._on_main_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_main_click)
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.bind("<FocusOut>", self._on_focus_out)

        self.window.deiconify()
        self.window.lift()
        try:
            self.window.focus_force()
        except Exception:
            pass

    @staticmethod
    def _coerce_work_area(work_area: tuple[int, int, int, int] | WorkArea | None) -> Optional[WorkArea]:
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

    def _tk_fallback_work_area(self) -> WorkArea:
        try:
            sw = max(640, int(self.window.winfo_screenwidth()))
            sh = max(480, int(self.window.winfo_screenheight()))
        except Exception:
            sw, sh = 1920, 1080
        return WorkArea(0, 0, sw, sh)

    def _active_work_area(self, x: int, y: int) -> WorkArea:
        if self._explicit_work_area is not None:
            return self._explicit_work_area
        try:
            return self._desktop.work_area_for_point(x, y)
        except Exception:
            return self._tk_fallback_work_area()

    def _compute_height(self, items: Sequence[MenuItemSpec], *, include_header: bool,
                        row_h: int | None = None) -> int:
        row_h = row_h or self._row_h
        total = 20 + (self._header_h if include_header else 8)
        for item in items:
            total += self._sep_h if item.is_separator else row_h
        return max(88, total + 10)

    def _font(self, size: int, weight: str = "normal") -> tkfont.Font:
        cache = getattr(self, "_font_cache", None)
        if cache is None:
            cache = self._font_cache = {}
        key = (self.lang, size, weight)
        font = cache.get(key)
        if font is None:
            font = tkfont.Font(root=self.window, family=_font_family(self.lang), size=size, weight=weight)
            cache[key] = font
        return font

    def _label_font(self) -> tkfont.Font:
        return self._font(9, "bold")

    def _flyout_layout(self, items: Sequence[MenuItemSpec], base_w: int, work: WorkArea
                       ) -> tuple[int, int, int]:
        """(design width, row height, max label px) so a flyout fits its monitor.

        Long labels widen the flyout up to FLYOUT_MAX_W (and the work area); what is
        still too long is elided. A list taller than the work area (long standby
        lists at high DPI) gets shorter rows instead of running off the screen.
        """
        k = self.ui_scale
        font = self._label_font()
        widest = max((font.measure(_bmp_safe_text(f"✓ {item.label}"))
                      for item in items if not item.is_separator), default=0)
        room_w = max(base_w, int(work.width / k) - 2 * FLYOUT_SCREEN_MARGIN)
        design_w = min(max(base_w, round(widest / k) + FLYOUT_TEXT_PAD), FLYOUT_MAX_W, room_w)
        row_h = self._row_h
        room_h = int(work.height / k) - 2 * FLYOUT_SCREEN_MARGIN
        if self._compute_height(items, include_header=False) > room_h:
            rows = sum(1 for item in items if not item.is_separator)
            seps = len(items) - rows
            fit = (room_h - 38 - seps * self._sep_h) // max(1, rows)
            row_h = max(FLYOUT_MIN_ROW_H, min(self._row_h, fit))
        return design_w, row_h, round((design_w - FLYOUT_TEXT_PAD) * k)

    def _get_icon(self, icon_name: Optional[str], size: int = 22) -> Optional[ImageTk.PhotoImage]:
        if not icon_name:
            return None
        cache_key = f"{icon_name}_{size}"
        if cache_key in self._icon_refs:
            return self._icon_refs[cache_key]
        im = _load_icon_pil(icon_name, size=size)
        if im is None:
            return None
        try:
            photo = ImageTk.PhotoImage(im, master=self.window)
            self._icon_refs[cache_key] = photo
            return photo
        except Exception:
            return None

    def _move_window(self, win: tk.Toplevel, x: int, y: int, w: int, h: int, *, is_sub: bool) -> None:
        if is_sub:
            self.last_sub_clamped_pos = (int(x), int(y))
        else:
            self.last_clamped_pos = (int(x), int(y))
        win.geometry(f"{w}x{h}+{max(0, int(x))}+{max(0, int(y))}")
        try:
            win.update_idletasks()
            frame = win.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(win.winfo_id())
            self._desktop.position_without_activation(hwnd, int(x), int(y))
        except Exception:
            pass

    def _render_main(self) -> None:
        if self._closed or not self.window.winfo_exists():
            return
        c = self.canvas
        c.delete("all")
        self._row_bounds.clear()

        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        w, h = self._design_w, self._design_h
        k = self.ui_scale
        fam = _font_family(self.lang)
        f10b = (fam, 10, "bold")
        f9b = (fam, 9, "bold")
        f9n = (fam, 9, "normal")
        f8n = (fam, 8, "normal")
        f7b = (fam, 7, "bold")

        # Soft outer glow & main pink card
        _draw_round_rect(c, 5, 7, w - 2, h - 2, r=20, fill=theme["glow"], outline="")
        _draw_round_rect(c, 3, 3, w - 5, h - 5, r=20, fill="#fff8fb", outline=theme["border"], width=2.5)
        _draw_round_rect(c, 9, 9, w - 11, h - 11, r=16, fill=theme["soft_bg"], outline="")

        # Header banner
        _draw_round_rect(
            c, 14, 14, w - 16, 14 + self._header_h - 6, r=12,
            fill=theme["header_fill"], outline=theme["badge_border"], width=1.2,
        )
        c.create_text(
            26, 28,
            text=f"♥ {_bmp_safe_text(self.title)}",
            font=f10b,
            fill=theme["primary"],
            anchor="w",
        )
        sub_txt = self.subtitle or t("pink_menu_subtitle", self.lang)
        c.create_text(
            26, 46,
            text=_bmp_safe_text(sub_txt),
            font=f8n,
            fill=theme["accent"],
            anchor="w",
        )

        # Close X pill in header
        _draw_round_rect(
            c, w - 44, 20, w - 22, 42, r=8,
            fill="#ffffff", outline=theme["badge_border"], width=1,
            tags=("btn_close_menu",),
        )
        c.create_text(
            w - 33, 31,
            text="×",
            font=f9b,
            fill=theme["primary"],
            tags=("btn_close_menu",),
        )

        cur_y = 16 + self._header_h
        for idx, item in enumerate(self.items):
            if item.is_separator:
                sep_y = cur_y + self._sep_h // 2
                c.create_line(22, sep_y, w - 22, sep_y, fill=theme["badge_border"], width=1)
                cur_y += self._sep_h
                continue

            ry1, ry2 = cur_y, cur_y + self._row_h - 2
            self._row_bounds.append((idx, round(ry1 * k), round(ry2 * k)))
            is_hover = (idx == self._hover_idx) or (idx == self._active_sub_idx)

            if is_hover:
                fill_col = theme["header_fill"] if not item.is_danger else "#ffebee"
                out_col = theme["primary"] if not item.is_danger else "#e53935"
                _draw_round_rect(
                    c, 14, ry1, w - 16, ry2, r=10,
                    fill=fill_col, outline=out_col, width=1.2,
                )

            text_x = 26
            icon_img = self._get_icon(item.icon_name, size=round(22 * k))
            if icon_img is not None:
                c.create_image(30, (ry1 + ry2) // 2, image=icon_img, anchor="center")
                text_x = 48

            fg_col = "#d32f2f" if item.is_danger else (theme["primary"] if is_hover or item.checked else "#3d2c35")
            prefix = "✓ " if item.checked else ""
            clean_label = _bmp_safe_text(f"{prefix}{item.label}")
            c.create_text(
                text_x, (ry1 + ry2) // 2,
                text=clean_label,
                font=f9b if (is_hover or item.checked) else f9n,
                fill=fg_col,
                anchor="w",
            )

            if item.badge:
                _draw_round_rect(
                    c, w - 68, ry1 + 6, w - 36, ry2 - 6, r=8,
                    fill=theme["pill_fill"], outline=theme["badge_border"], width=1,
                )
                c.create_text(
                    w - 52, (ry1 + ry2) // 2,
                    text=item.badge,
                    font=f7b,
                    fill=theme["primary"],
                )

            if item.submenu:
                c.create_text(
                    w - 24, (ry1 + ry2) // 2,
                    text="▸",
                    font=f10b,
                    fill=theme["primary"],
                )

            cur_y += self._row_h
        scale_canvas(c, k)

    def _on_main_motion(self, event: tk.Event) -> None:
        if self._closed:
            return
        hit_idx: Optional[int] = None
        for idx, ry1, ry2 in self._row_bounds:
            if ry1 <= event.y <= ry2:
                hit_idx = idx
                break
        if hit_idx != self._hover_idx:
            self._hover_idx = hit_idx
            self._render_main()
            if hit_idx is not None:
                item = self.items[hit_idx]
                if item.submenu:
                    self._open_submenu(hit_idx, item.submenu)
                else:
                    self._close_submenu()

    def _main_item_at(self, event: tk.Event) -> int | None:
        if not (0 <= event.x < self.w and 0 <= event.y < self.h):
            return None
        hits = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if any("btn_close_menu" in self.canvas.gettags(item) for item in hits):
            return -1
        for idx, ry1, ry2 in self._row_bounds:
            if ry1 <= event.y <= ry2:
                return idx
        return None

    def _on_main_press(self, event: tk.Event) -> None:
        self._pressed_main_item = self._main_item_at(event)

    def _on_main_click(self, event: tk.Event) -> None:
        pressed, self._pressed_main_item = self._pressed_main_item, None
        if self._closed or pressed is None or pressed != self._main_item_at(event):
            return
        if pressed == -1:
            self.close()
        else:
            self.activate_item(pressed)

    def activate_item(self, idx: int) -> bool:
        """Programmatically or interactively trigger main menu item `idx`."""
        if self._closed or idx < 0 or idx >= len(self.items):
            return False
        item = self.items[idx]
        if item.is_separator:
            return False
        if item.submenu:
            self._open_submenu(idx, item.submenu)
            return True
        cmd = item.command
        self.close()
        if cmd is not None:
            cmd()
        return True

    def activate_submenu_item(self, sub_idx: int) -> bool:
        """Programmatically or interactively trigger active submenu item `sub_idx`."""
        if self._closed or sub_idx < 0 or sub_idx >= len(self._sub_items):
            return False
        item = self._sub_items[sub_idx]
        if item.is_separator:
            return False
        if item.submenu:                       # drill in: the same flyout shows the nested rows
            parent, self._active_sub_idx = self._active_sub_idx, None
            self._open_submenu(parent, item.submenu)
            return True
        cmd = item.command
        self.close()
        if cmd is not None:
            cmd()
        return True

    def _apply_flyout_cursor(self, win: tk.Misc, canvas: tk.Misc) -> None:
        """Apply active custom or inherited Tk cursor to lazy flyout windows."""
        cursor_key = getattr(self, "_cursor_key", None)
        if cursor_key:
            from app.cursor_manager import apply_cursor_to_widgets

            apply_cursor_to_widgets((win, canvas), cursor_key)
            return
        try:
            tk_cursor = self.window.cget("cursor")
            if tk_cursor:
                win.config(cursor=tk_cursor)
                canvas.config(cursor=tk_cursor)
        except Exception:
            pass

    def _open_submenu(self, parent_idx: int, sub_items: Sequence[MenuItemSpec]) -> None:
        if self._closed:
            return
        if self._active_sub_idx == parent_idx and self._sub_window is not None and self._sub_window.winfo_exists():
            return
        self._close_submenu()
        self._active_sub_idx = parent_idx
        self._sub_items = list(sub_items)
        self._sub_hover_idx = None

        k = self.ui_scale
        mx, my = self.last_clamped_pos
        work = self._active_work_area(mx + self.w // 2, my + self.h // 2)
        design_sub_w, self._sub_row_h, self._sub_text_px = self._flyout_layout(self._sub_items, 324, work)
        design_sub_h = self._compute_height(self._sub_items, include_header=False, row_h=self._sub_row_h)
        self._sub_design_size = (design_sub_w, design_sub_h)
        sub_w = round(design_sub_w * k)
        sub_h = round(design_sub_h * k)

        ry1 = round((16 + self._header_h) * k)
        for idx, r_top, _r_bot in self._row_bounds:
            if idx == parent_idx:
                ry1 = r_top
                break

        overlap = round(4 * k)
        cand_x = mx + self.w - overlap
        if cand_x + sub_w > work.right:
            cand_x = mx - sub_w + overlap
        sx, sy = work.clamp(cand_x, my + ry1 - round(8 * k), sub_w, sub_h)

        sub_win = tk.Toplevel(self.window)
        sub_win.overrideredirect(True)
        sub_win.attributes("-topmost", True)
        try:
            sub_win.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        sub_win.configure(bg=BG_TRANSPARENT)

        sub_canvas = tk.Canvas(
            sub_win,
            width=sub_w,
            height=sub_h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        sub_canvas.pack(fill="both", expand=True)

        self._sub_window = sub_win
        self._sub_canvas = sub_canvas
        self._render_submenu(sub_w, sub_h)
        self._move_window(sub_win, sx, sy, sub_w, sub_h, is_sub=True)
        self._apply_flyout_cursor(sub_win, sub_canvas)

        sub_canvas.bind("<Motion>", lambda e, w=sub_w, h=sub_h: self._on_sub_motion(e, w, h))
        sub_canvas.bind("<ButtonPress-1>", self._on_sub_press)
        sub_canvas.bind("<ButtonRelease-1>", self._on_sub_click)
        sub_win.bind("<Escape>", lambda _e: self.close())
        sub_win.deiconify()
        sub_win.lift()
        self._render_main()

    def _render_submenu(self, _sub_w: int = 0, _sub_h: int = 0) -> None:
        if self._sub_canvas is None or self._sub_window is None or not self._sub_window.winfo_exists():
            return
        dw, dh = self._sub_design_size
        self._draw_rows(self._sub_canvas, self._sub_items, self._sub_row_bounds, self._sub_hover_idx, dw, dh,
                        row_h=self._sub_row_h, text_px=self._sub_text_px)

    def _draw_rows(self, c: tk.Canvas, items: Sequence[MenuItemSpec], bounds: list,
                   hover_idx: Optional[int], sub_w: int, sub_h: int, *,
                   row_h: int | None = None, text_px: int | None = None) -> None:
        """A flyout's frame and rows; ``bounds`` receives physical (index, top, bottom) per row."""
        c.delete("all")
        bounds.clear()
        row_h = row_h or self._row_h

        k = self.ui_scale
        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        fam = _font_family(self.lang)
        f9b = (fam, 9, "bold")
        f9n = (fam, 9, "normal")
        measure_font = self._label_font() if text_px else None

        _draw_round_rect(c, 5, 7, sub_w - 2, sub_h - 2, r=18, fill=theme["glow"], outline="")
        _draw_round_rect(c, 3, 3, sub_w - 5, sub_h - 5, r=18, fill="#fff8fb", outline=theme["border"], width=2.2)
        _draw_round_rect(c, 8, 8, sub_w - 10, sub_h - 10, r=14, fill=theme["soft_bg"], outline="")

        cur_y = 14
        for idx, item in enumerate(items):
            if item.is_separator:
                sep_y = cur_y + self._sep_h // 2
                c.create_line(18, sep_y, sub_w - 18, sep_y, fill=theme["badge_border"], width=1)
                cur_y += self._sep_h
                continue

            ry1, ry2 = cur_y, cur_y + row_h - 2
            bounds.append((idx, round(ry1 * k), round(ry2 * k)))
            is_hover = idx == hover_idx

            if is_hover:
                _draw_round_rect(
                    c, 12, ry1, sub_w - 14, ry2, r=9,
                    fill=theme["header_fill"], outline=theme["primary"], width=1.2,
                )

            prefix = "✓ " if item.checked else ""
            clean_label = _bmp_safe_text(f"{prefix}{item.label}")
            if text_px and measure_font is not None:
                clean_label = _elide(clean_label, measure_font, text_px)
            c.create_text(
                22, (ry1 + ry2) // 2,
                text=clean_label,
                font=f9b if (is_hover or item.checked) else f9n,
                fill=theme["primary"] if (is_hover or item.checked) else "#3d2c35",
                anchor="w",
            )
            cur_y += row_h
        scale_canvas(c, k)

    def _on_sub_motion(self, event: tk.Event, sub_w: int, sub_h: int) -> None:
        hit_idx: Optional[int] = None
        for idx, ry1, ry2 in self._sub_row_bounds:
            if ry1 <= event.y <= ry2:
                hit_idx = idx
                break
        if hit_idx != self._sub_hover_idx:
            self._sub_hover_idx = hit_idx
            self._render_submenu(sub_w, sub_h)
            if hit_idx is not None:          # off the rows (on the way to the peek) keeps it open
                item = self._sub_items[hit_idx]
                if item.submenu:
                    self._open_peek(hit_idx, sub_w, item.submenu)
                else:
                    self._close_peek()

    def _open_peek(self, row_idx: int, sub_w: int, items: Sequence[MenuItemSpec]) -> None:
        """Hovering a member shows her moves in a flyout beside the list; no click needed."""
        if self._peek_row == row_idx and self._peek_window is not None and self._peek_window.winfo_exists():
            return
        self._close_peek()
        if self._sub_window is None or not self._sub_window.winfo_exists():
            return
        k = self.ui_scale
        self._peek_row, self._peek_items, self._peek_hover = row_idx, list(items), None
        top = next((r_top for idx, r_top, _ in self._sub_row_bounds if idx == row_idx), round(14 * k))
        sx, sy = self._sub_window.winfo_rootx(), self._sub_window.winfo_rooty()
        work = self._active_work_area(sx + sub_w // 2, sy + top)
        design_peek_w, self._peek_row_h, self._peek_text_px = self._flyout_layout(self._peek_items, 300, work)
        design_peek_h = self._compute_height(self._peek_items, include_header=False, row_h=self._peek_row_h)
        self._peek_design_size = (design_peek_w, design_peek_h)
        peek_w, peek_h = round(design_peek_w * k), round(design_peek_h * k)
        overlap = round(4 * k)
        x = sx + sub_w - overlap
        if x + peek_w > work.right:
            x = sx - peek_w + overlap
        x, y = work.clamp(x, sy + top - round(8 * k), peek_w, peek_h)
        win = tk.Toplevel(self.window)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        win.configure(bg=BG_TRANSPARENT)
        canvas = tk.Canvas(win, width=peek_w, height=peek_h, bg=BG_TRANSPARENT, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        self._peek_window, self._peek_canvas = win, canvas
        self._draw_rows(canvas, self._peek_items, self._peek_bounds, None, design_peek_w, design_peek_h,
                        row_h=self._peek_row_h, text_px=self._peek_text_px)
        self._move_window(win, x, y, peek_w, peek_h, is_sub=True)
        self._apply_flyout_cursor(win, canvas)
        canvas.bind("<Motion>", lambda e, w=peek_w, h=peek_h: self._on_peek_motion(e, w, h))
        canvas.bind("<ButtonPress-1>", self._on_peek_press)
        canvas.bind("<ButtonRelease-1>", self._on_peek_click)
        win.bind("<Escape>", lambda _e: self.close())
        win.deiconify()
        win.lift()

    def _hit(self, bounds: list, y: int) -> Optional[int]:
        return next((idx for idx, ry1, ry2 in bounds if ry1 <= y <= ry2), None)

    def _on_peek_motion(self, event: tk.Event, _peek_w: int, _peek_h: int) -> None:
        hit_idx = self._hit(self._peek_bounds, event.y)
        if hit_idx != self._peek_hover and self._peek_canvas is not None:
            self._peek_hover = hit_idx
            dw, dh = self._peek_design_size
            self._draw_rows(self._peek_canvas, self._peek_items, self._peek_bounds, hit_idx, dw, dh,
                            row_h=self._peek_row_h, text_px=self._peek_text_px)

    def activate_peek_item(self, idx: int) -> bool:
        if self._closed or not 0 <= idx < len(self._peek_items):
            return False
        item = self._peek_items[idx]
        if item.is_separator or item.submenu:
            return False
        cmd = item.command
        self.close()
        if cmd is not None:
            cmd()
        return True

    def _flyout_item_at(self, event: tk.Event, canvas: tk.Canvas | None, bounds: list) -> int | None:
        if canvas is not None and event.widget is canvas and 0 <= event.x < canvas.winfo_width():
            return self._hit(bounds, event.y)
        return None

    def _on_peek_press(self, event: tk.Event) -> None:
        self._pressed_peek_item = self._flyout_item_at(event, self._peek_canvas, self._peek_bounds)

    def _on_peek_click(self, event: tk.Event) -> None:
        pressed, self._pressed_peek_item = self._pressed_peek_item, None
        if pressed is not None and pressed == self._flyout_item_at(event, self._peek_canvas, self._peek_bounds):
            self.activate_peek_item(pressed)

    def _close_peek(self) -> None:
        self._pressed_peek_item = None
        self._peek_row, self._peek_items, self._peek_hover = None, [], None
        self._peek_bounds.clear()
        win, self._peek_window, self._peek_canvas = self._peek_window, None, None
        if win is not None:
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

    def _on_sub_press(self, event: tk.Event) -> None:
        self._pressed_sub_item = self._flyout_item_at(event, self._sub_canvas, self._sub_row_bounds)

    def _on_sub_click(self, event: tk.Event) -> None:
        pressed, self._pressed_sub_item = self._pressed_sub_item, None
        if pressed is not None and pressed == self._flyout_item_at(event, self._sub_canvas, self._sub_row_bounds):
            self.activate_submenu_item(pressed)

    def _close_submenu(self) -> None:
        self._pressed_sub_item = None
        self._close_peek()
        self._active_sub_idx = None
        self._sub_items = []
        self._sub_row_bounds.clear()
        self._sub_hover_idx = None
        if self._sub_window is not None:
            try:
                if self._sub_window.winfo_exists():
                    self._sub_window.destroy()
            except Exception:
                pass
            self._sub_window = None
            self._sub_canvas = None

    def _on_focus_out(self, _event: tk.Event) -> None:
        if self._closed:
            return
        try:
            focused = self.window.focus_displayof()
            if focused is not None:
                top = focused.winfo_toplevel()
                if top in (self.window, self._sub_window, self._peek_window):
                    return
        except Exception:
            pass
        self.window.after(80, self._check_outside_focus)

    def _check_outside_focus(self) -> None:
        if self._closed:
            return
        try:
            focused = self.window.focus_displayof()
            if focused is not None:
                top = focused.winfo_toplevel()
                if top in (self.window, self._sub_window, self._peek_window):
                    return
        except Exception:
            pass
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._close_submenu()
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            pass
        self._icon_refs.clear()
        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass


def _elide(text: str, font: tkfont.Font, max_px: int) -> str:
    """One line no wider than max_px: line breaks become spaces, the tail becomes "…"."""
    line = " ".join(text.split())
    if font.measure(line) <= max_px:
        return line
    while line and font.measure(line + "…") > max_px:
        line = line[:-1]
    return line.rstrip() + "…"


class NotificationDrawerWindow:
    """Kawaii RAM-only Recent Notifications Drawer (Max 20 items, zero disk logging).

    ``items`` arrive oldest first (the pet appends); the drawer lists the newest on top and
    shows VISIBLE cards at a time, the mouse wheel scrolls through the rest.
    """

    VISIBLE = 6

    def __init__(
        self,
        parent: tk.Misc,
        *,
        lang: str = "zh_TW",
        char_key: str = "chorong",
        items: Sequence[Mapping[str, Any] | Any],
        privacy_mode: bool = False,
        on_clear: Optional[Callable[[], None]] = None,
        on_toggle_privacy: Optional[Callable[[], bool]] = None,
        on_close: Optional[Callable[[], None]] = None,
        work_area: tuple[int, int, int, int] | WorkArea | None = None,
        anchor_box: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.parent = parent
        self.anchor_box = anchor_box
        self.lang = lang if lang in ("zh_TW", "ko", "en") else "zh_TW"
        self.char_key = char_key if char_key in MEMBER_THEMES else "chorong"
        self.items = list(items)[:20]
        self.privacy_mode = bool(privacy_mode)
        self.on_clear = on_clear
        self.on_toggle_privacy = on_toggle_privacy
        self.on_close = on_close
        self._closed = False
        self.last_clamped_pos: tuple[int, int] = (0, 0)
        self.top = 0                      # index (in newest-first order) of the first card shown
        self._expanded_entry: Any | None = None
        self._details: tk.Frame | None = None

        self._desktop = WindowsDesktopAdapter(fallback_bounds=self._tk_fallback_work_area)
        self._explicit_work_area = PinkContextMenu._coerce_work_area(work_area)

        self._design_w = 460
        self._design_h = 480

        self.window = tk.Toplevel(parent)
        self.win = self.window
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.window.configure(bg=BG_TRANSPARENT)
        self.ui_scale = ui_scale(self.window)
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)

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
        self._render()

        self.drag_offset_x: Optional[int] = None
        self.drag_offset_y: Optional[int] = None

        self.canvas.bind("<ButtonPress-1>", self._on_drag_begin)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self._pressed_card: Any | None = None

        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.window.deiconify()
        self.window.lift()

    def _on_drag_begin(self, event: tk.Event) -> None:
        try:
            self.window.lift()
        except Exception:
            pass
        current_tags = self.canvas.gettags("current")
        self._pressed_card = self._card_at(event)
        if self._pressed_card is not None:
            return
        button_tags = {"btn_close_drawer", "btn_clear_drawer", "btn_drawer_privacy"}
        if any(tag in button_tags for tag in current_tags):
            return
        self.drag_offset_x = event.x_root - self.window.winfo_x()
        self.drag_offset_y = event.y_root - self.window.winfo_y()

    def _on_drag_move(self, event: tk.Event) -> None:
        if self.drag_offset_x is not None and self.drag_offset_y is not None:
            x = event.x_root - self.drag_offset_x
            y = event.y_root - self.drag_offset_y
            work = self._desktop.work_area_for_point(event.x_root, event.y_root)
            cx, cy = work.clamp(x, y, self.w, self.h)
            self.window.geometry(f"+{cx}+{cy}")
            self.last_clamped_pos = (cx, cy)

    def _on_drag_end(self, event: tk.Event) -> None:
        self.drag_offset_x = None
        self.drag_offset_y = None
        pressed, self._pressed_card = self._pressed_card, None
        if pressed is not None and pressed is self._card_at(event):
            self._expanded_entry = None if pressed is self._expanded_entry else pressed
            self._render()

    def _card_at(self, event: tk.Event) -> Any | None:
        c = self.canvas
        for item in reversed(c.find_overlapping(event.x, event.y, event.x, event.y)):
            for tag in c.gettags(item):
                if tag.startswith("notif_card_"):
                    index = int(tag.removeprefix("notif_card_"))
                    return self.items[-index - 1] if index < len(self.items) else None
        return None

    def _expanded_index(self) -> int | None:
        if self._expanded_entry is not None:
            for index, entry in enumerate(reversed(self.items)):
                if entry is self._expanded_entry:
                    return index
            self._expanded_entry = None
        return None

    def scroll(self, rows: int) -> None:
        """Move the window of shown cards by ``rows`` (positive = towards older ones)."""
        index = self._expanded_index()
        if index is not None:
            self.top = index
            self._expanded_entry = None
        self.top += rows
        self._render()

    def _on_wheel(self, event: Any) -> str:
        self.scroll(-1 if getattr(event, "delta", 0) > 0 else 1)
        return "break"

    def visible_entries(self) -> list:
        newest_first = list(reversed(self.items))
        self.top = max(0, min(self.top, len(newest_first) - self.VISIBLE))
        return newest_first[self.top:self.top + self.VISIBLE]

    def _tk_fallback_work_area(self) -> WorkArea:
        try:
            sw = max(640, int(self.window.winfo_screenwidth()))
            sh = max(480, int(self.window.winfo_screenheight()))
        except Exception:
            sw, sh = 1920, 1080
        return WorkArea(0, 0, sw, sh)

    def _position_near_parent(self) -> None:
        if self.anchor_box is not None and len(self.anchor_box) == 4:
            px, py, pw, ph = (int(self.anchor_box[0]), int(self.anchor_box[1]), max(1, int(self.anchor_box[2])), max(1, int(self.anchor_box[3])))
        else:
            try:
                self.parent.update_idletasks()
                px = int(self.parent.winfo_rootx())
                py = int(self.parent.winfo_rooty())
                pw = max(1, int(self.parent.winfo_width()))
                ph = max(1, int(self.parent.winfo_height()))
            except Exception:
                px, py, pw, ph = 500, 300, 192, 192
        work = self._explicit_work_area or self._desktop.work_area_for_point(px + pw // 2, py + ph // 2)
        gap = round(14 * self.ui_scale)
        cand_x = px - self.w - gap
        if cand_x < work.left:
            cand_x = px + pw + gap
        x, y = work.clamp(cand_x, py - round(60 * self.ui_scale), self.w, self.h)
        self.last_clamped_pos = (int(x), int(y))
        self.window.geometry(f"{self.w}x{self.h}+{max(0, int(x))}+{max(0, int(y))}")
        try:
            self.window.update_idletasks()
            frame = self.window.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.window.winfo_id())
            self._desktop.position_without_activation(hwnd, int(x), int(y))
        except Exception:
            pass

    @staticmethod
    def _extract_fields(entry: Any) -> tuple[str, str, str]:
        if isinstance(entry, dict):
            app_name = str(entry.get("app_name") or entry.get("app") or "")
            title = str(entry.get("title") or "")
            body = str(entry.get("body") or entry.get("message") or "")
            return app_name, title, body
        app_name = str(getattr(entry, "app_name", "") or "")
        title = str(getattr(entry, "title", "") or "")
        body = str(getattr(entry, "body", "") or "")
        return app_name, title, body

    def _render(self) -> None:
        if self._closed or not self.window.winfo_exists():
            return
        c = self.canvas
        expanded_index = self._expanded_index()
        self._destroy_details()
        c.delete("all")
        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        fam = _font_family(self.lang)
        w, h = self._design_w, self._design_h
        k = self.ui_scale

        _draw_round_rect(c, 5, 7, w - 2, h - 2, r=22, fill=theme["glow"], outline="")
        _draw_round_rect(c, 3, 3, w - 5, h - 5, r=22, fill="#fff8fb", outline=theme["border"], width=2.5)
        _draw_round_rect(c, 10, 10, w - 12, h - 12, r=16, fill=theme["soft_bg"], outline="")

        # Header: short title + count, the 20-item / RAM-only rule on a small line below
        # (one long title used to run under the close button).
        _draw_round_rect(
            c, 16, 16, w - 18, 62, r=12,
            fill=theme["header_fill"], outline=theme["badge_border"], width=1.2,
        )
        c.create_text(
            28, 31,
            text=_elide(
                _bmp_safe_text(f"{t('notif_drawer_title', self.lang)} ({len(self.items)}/20)"),
                tkfont.Font(root=self.window, family=fam, size=10, weight="bold"),
                round((w - 92) * k),
            ),
            font=(fam, 10, "bold"),
            fill=theme["primary"],
            anchor="w",
        )
        c.create_text(
            28, 50,
            text=_elide(_bmp_safe_text(t("notif_drawer_hint", self.lang)), tkfont.Font(root=self.window, family=fam, size=7), round((w - 92) * k)),
            font=(fam, 7),
            fill=DRAWER_MUTED,
            anchor="w",
        )
        _draw_round_rect(
            c, w - 48, 24, w - 24, 48, r=8,
            fill="#ffffff", outline=theme["badge_border"], width=1,
            tags=("btn_close_drawer",),
        )
        c.create_text(w - 36, 36, text="×", font=(fam, 9, "bold"), fill=theme["primary"], tags=("btn_close_drawer",))
        c.tag_bind("btn_close_drawer", "<ButtonRelease-1>", lambda _e: self.close())

        # Body list (shows up to 6 recent cards cleanly; full count badge shown)
        if not self.items:
            _draw_round_rect(
                c, 22, 82, w - 24, h - 72, r=14,
                fill="#ffffff", outline=theme["badge_border"], width=1,
            )
            c.create_text(
                w // 2, h // 2 - 10,
                text=_bmp_safe_text(t("notif_drawer_empty", self.lang)),
                font=(fam, 9),
                fill=DRAWER_MUTED,
                width=w - 80,
                justify="center",
            )
        else:
            card_y = 72
            card_h = 54
            # Each card is exactly two lines: a body with line breaks used to grow up over line 1.
            text_px = w - 22 - 32 - 32
            time_px = 56
            bold = tkfont.Font(root=self.window, family=fam, size=8, weight="bold")
            plain = tkfont.Font(root=self.window, family=fam, size=8)
            visible = self.visible_entries()
            entries = (enumerate(visible, self.top) if expanded_index is None else
                       [(expanded_index, self._expanded_entry)])
            for index, entry in entries:
                tag = f"notif_card_{index}"
                when = str(entry.get("time", "")) if isinstance(entry, dict) else str(getattr(entry, "time", "") or "")
                app_name, title, body = self._extract_fields(entry)
                disp_app = app_name or ("" if self.privacy_mode else title) or t("windows_notif_default_title", self.lang)
                if self.privacy_mode:
                    line1 = _bmp_safe_text(t("windows_notif_privacy_msg", self.lang, app=disp_app))
                    line2 = _bmp_safe_text(t("notif_drawer_private", self.lang))
                else:
                    line1 = _bmp_safe_text(f"• [{disp_app}] {title}".strip())
                    line2 = _bmp_safe_text(body or title or disp_app)
                _draw_round_rect(
                    c, 20, card_y, w - 22, card_y + card_h - 4, r=10,
                    fill="#ffffff", outline=theme["badge_border"], width=1, tags=(tag,),
                )
                if when:
                    c.create_text(w - 55, card_y + 16, text=when, font=(fam, 7), fill=DRAWER_MUTED,
                                  anchor="e", tags=(tag,))
                cx, cy = w - 36, card_y + 27
                tip = -4 if expanded_index is not None else 4
                c.create_line(cx - 5, cy - tip, cx, cy + tip, cx + 5, cy - tip,
                              fill=theme["primary"], width=2, tags=(tag,))
                c.create_text(
                    32, card_y + 16,
                    text=_elide(line1, bold, round((text_px - (time_px if when else 0)) * k)),
                    font=(fam, 8, "bold"),
                    fill=theme["primary"],
                    anchor="w",
                    tags=(tag,),
                )
                c.create_text(
                    32, card_y + 34,
                    text=_elide(line2, plain, round(text_px * k)),
                    font=(fam, 8),
                    fill="#555555",
                    anchor="w",
                    tags=(tag,),
                )
                card_y += card_h
            if expanded_index is not None:
                c.create_text(w // 2, h - 66, text=t("notif_drawer_browse", self.lang),
                              font=(fam, 7), fill=DRAWER_MUTED)
            elif len(self.items) > self.VISIBLE:
                c.create_text(
                    w // 2, card_y + 8,
                    text=t("notif_drawer_scroll", self.lang, a=self.top + 1,
                           b=min(self.top + self.VISIBLE, len(self.items)), n=len(self.items)),
                    font=(fam, 7),
                    fill=DRAWER_MUTED,
                )

        # Bottom controls: Clear RAM Drawer & Privacy Mode Toggle
        _draw_round_rect(
            c, 20, h - 56, w // 2 + 12, h - 20, r=10,
            fill=theme["pill_fill"], outline=theme["primary"], width=1.2,
            tags=("btn_clear_drawer",),
        )
        # Korean / English labels are longer than the buttons: wrap to two centred lines.
        c.create_text(
            (20 + w // 2 + 12) // 2, h - 38,
            text=_bmp_safe_text(t("notif_drawer_clear", self.lang)),
            font=(fam, 8, "bold"),
            fill=theme["primary"],
            width=w // 2 - 8 - 12,
            justify="center",
            tags=("btn_clear_drawer",),
        )
        c.tag_bind("btn_clear_drawer", "<ButtonRelease-1>", lambda _e: self.clear_drawer())

        _draw_round_rect(
            c, w // 2 + 22, h - 56, w - 20, h - 20, r=10,
            fill=theme["primary"] if self.privacy_mode else "#ffffff",
            outline=theme["primary"], width=1.2,
            tags=("btn_drawer_privacy",),
        )
        c.create_text(
            (w // 2 + 22 + w - 20) // 2, h - 38,
            text=_bmp_safe_text(t("notify_privacy_toggle", self.lang)),
            font=(fam, 8, "bold"),
            fill="#ffffff" if self.privacy_mode else theme["primary"],
            width=w // 2 - 42 - 12,
            justify="center",
            tags=("btn_drawer_privacy",),
        )
        c.tag_bind("btn_drawer_privacy", "<ButtonRelease-1>", lambda _e: self.toggle_privacy())
        scale_canvas(c, k)
        if expanded_index is not None:
            self._render_details(self._expanded_entry, fam, theme)
        cursor_key = getattr(self, "_cursor_key", None)
        if cursor_key is not None:
            from app.cursor_manager import apply_cursor_to_widgets

            apply_cursor_to_widgets((self.window, self.canvas), cursor_key)

    def _render_details(self, entry: Any, family: str, theme: dict) -> None:
        k = self.ui_scale
        app_name, title, body = self._extract_fields(entry)
        when = str(entry.get("time", "")) if isinstance(entry, dict) else str(getattr(entry, "time", "") or "")
        if self.privacy_mode:
            app_name = t("windows_notif_privacy_msg", self.lang,
                         app=app_name or t("windows_notif_default_title", self.lang))
            title, body = "", t("notif_drawer_private", self.lang)
        fields = (app_name, title, when, body)
        self._details = tk.Frame(self.canvas, bg="#ffffff")
        message = tk.Text(self._details, wrap="word", height=1, width=1, relief="flat",
                          bg="#ffffff", fg="#555555", padx=round(10 * k), pady=round(8 * k),
                          font=(family, 9), highlightthickness=0, cursor="arrow")
        scrollbar = tk.Scrollbar(self._details, orient="vertical", command=message.yview)
        message.configure(yscrollcommand=scrollbar.set)
        message.tag_configure("heading", foreground=theme["primary"], font=(family, 9, "bold"))
        for index, field in enumerate(fields):
            if field:
                if message.index("end-1c") != "1.0":
                    message.insert("end", "\n\n")
                message.insert("end", field, ("heading",) if index < 2 else ())
        message.configure(state="disabled")
        def scroll_message(event: tk.Event) -> str:
            message.yview_scroll(-3 if event.delta > 0 else 3, "units")
            return "break"

        message.bind("<MouseWheel>", scroll_message)
        scrollbar.pack(side="right", fill="y")
        message.pack(side="left", expand=True, fill="both")
        self.canvas.create_window(round(20 * k), round(126 * k), window=self._details, anchor="nw",
                                  width=round((self._design_w - 42) * k),
                                  height=round((self._design_h - 205) * k))

    def _destroy_details(self) -> None:
        """Unhook the details pane before destroying it: Tk's Scrollbar skips our WM_NCDESTROY."""
        if self._details is None:
            return
        from app.cursor_manager import release_cursor_hooks

        try:
            release_cursor_hooks((self._details,))
            self._details.destroy()
        except Exception:
            pass
        self._details = None

    def clear_drawer(self) -> None:
        self.items.clear()
        self._expanded_entry = None
        if self.on_clear is not None:
            self.on_clear()
        self._render()

    def toggle_privacy(self) -> None:
        if self.on_toggle_privacy is not None:
            self.privacy_mode = bool(self.on_toggle_privacy())
        else:
            self.privacy_mode = not self.privacy_mode
        self._render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.window.winfo_exists():
                self._destroy_details()
                self.window.destroy()
        except Exception:
            pass
        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass


def build_pet_context_menu_items(pet: Any) -> list[MenuItemSpec]:
    """Build the complete kawaii context menu item tree for `DesktopPet`."""
    import datetime
    from app.i18n import get_weekday_names

    lang = getattr(pet, "lang", "zh_TW")
    char_key = getattr(pet, "char_key", "chorong")
    settings = getattr(pet, "settings", {}) or {}

    # 1. Actions & Status Card Submenu
    cameo_on = bool(settings.get("cameo_enabled", True))
    stay_in_place_on = bool(settings.get("stay_in_place", False))
    action_sub = [
        MenuItemSpec(t("idle", lang), lambda: pet.set_state("idle", manual=True), checked=(getattr(pet, "state", "") == "idle")),
        MenuItemSpec(t("walk", lang), lambda: pet.set_state("walk", manual=True), checked=(getattr(pet, "state", "") == "walk")),
        MenuItemSpec(t("cheer", lang), lambda: pet.set_state("cheer", manual=True), checked=(getattr(pet, "state", "") == "cheer")),
        MenuItemSpec(t("sleep", lang), lambda: pet.set_state("sleep", manual=True), checked=(getattr(pet, "state", "") == "sleep")),
        MenuItemSpec("", is_separator=True),
        MenuItemSpec(t("stay_in_place_toggle", lang), getattr(pet, "toggle_stay_in_place", None), checked=stay_in_place_on),
        MenuItemSpec(t("status_card", lang), getattr(pet, "show_status_card", None)),
        MenuItemSpec(t("member_profile", lang), getattr(pet, "open_profile_card", None)),
        *(
            [MenuItemSpec(t("fortune_daily_bubble", lang), getattr(pet, "show_daily_fortune_bubble"))]
            if callable(getattr(pet, "show_daily_fortune_bubble", None))
            else []
        ),
        MenuItemSpec(t("invite_cameo", lang), getattr(pet, "invite_cameo", None)),
        MenuItemSpec(t("cameo_toggle", lang), getattr(pet, "toggle_cameo", None), checked=cameo_on),
        MenuItemSpec(t("daily_signature_toggle", lang), getattr(pet, "toggle_daily_signature", None),
                     checked=bool(settings.get("daily_signature_enabled", True))),
        MenuItemSpec(t("festival_auto_toggle", lang), getattr(pet, "toggle_festival_auto", None),
                     checked=bool(settings.get("festival_auto_enabled", True))),
        MenuItemSpec(t("set_birthday", lang), getattr(pet, "open_birthday_dialog", None)),
    ]

    # 2. Signature Moves & Party Previews Submenu
    member_moves = {
        "chorong": (("special_move_cartwheel", "special_cartwheel"), ("special_move_hapkido", "special_hapkido_kick"),
                    ("special_move_blow_kiss", "special_blow_kiss"), ("special_move_cat", "daily_cat_cuddle")),
        "bomi": (("special_move_gorilla", "special_gorilla"), ("special_move_taekwondo", "special_taekwondo"),
                 ("special_move_mukbang", "interaction_eat")),
        "eunji": (("special_move_highnote", "special_sing_highnote"), ("special_move_boxing_eunji", "special_boxing"),
                  ("special_move_guitar", "special_guitar"), ("special_move_stretch", "standby_stretch"),
                  ("special_move_eunji_dome_dream", "special_eunji_dome_dream")),
        "namjoo": (("special_move_boxing_namjoo", "special_boxing"),
                   ("special_move_flamingo", "scene_flamingo")),
        "hayoung": (("special_move_soccer", "special_soccer_kick"), ("special_move_gaming", "special_gaming")),
    }
    eunji_fortune_moves = (
        ("special_move_eunji_fortune_tarot", "fortune_tarot_reader"),
        ("special_move_eunji_fortune_student", "fortune_student"),
        ("special_move_eunji_fortune_love", "fortune_love_reading"),
    )
    special_sub: list[MenuItemSpec] = []
    for member, moves in member_moves.items():
        available = getattr(pet, "available_special_actions", lambda _m: ())(member)
        rows = [
            MenuItemSpec(t(label, lang), (lambda a=action, m=member: pet.trigger_special_action(a, m)))
            for label, action in moves + (("special_move_lightstick_all", "special_cheer_lightstick"),)
            if action in available
        ]
        if member == "eunji":
            fortune_rows: list[MenuItemSpec] = []
            if callable(getattr(pet, "open_fortune_room", None)):
                fortune_rows.append(MenuItemSpec(t("special_move_eunji_fortune_room", lang), pet.open_fortune_room))
            bubble = getattr(pet, "show_daily_fortune_bubble", None)
            if callable(bubble):
                fortune_rows.append(MenuItemSpec(t("fortune_daily_bubble", lang), bubble))
            fortune_rows.extend(
                MenuItemSpec(t(label, lang), (lambda a=action, m=member: pet.trigger_special_action(a, m)))
                for label, action in eunji_fortune_moves
                if action in available
            )
            if rows and fortune_rows:
                rows.append(MenuItemSpec("", is_separator=True))
            rows.extend(fortune_rows)
        if rows:
            special_sub.append(MenuItemSpec(f"{get_member_display_name(member, lang)}  ›", None, submenu=rows))
    festival_rows = [
        MenuItemSpec(t("preview_event_new_year", lang), getattr(pet, "preview_new_year_event", None)),
        MenuItemSpec(t("preview_event_lunar_ny", lang), lambda: pet.preview_festival_event("festival_lunar_ny", t("preview_event_lunar_ny", lang))),
        MenuItemSpec(t("preview_event_lantern", lang), lambda: pet.preview_festival_event("festival_lantern", t("preview_event_lantern", lang))),
        MenuItemSpec(t("preview_event_mid_autumn", lang), lambda: pet.preview_festival_event("festival_mid_autumn", t("preview_event_mid_autumn", lang))),
        MenuItemSpec(t("preview_event_christmas", lang), getattr(pet, "preview_christmas_event", None)),
    ]
    if getattr(pet, "is_festival_preview_active", lambda: False)():
        festival_rows.append(MenuItemSpec(t("preview_festival_cancel", lang), getattr(pet, "cancel_festival_preview", None)))
    special_sub += [MenuItemSpec("", is_separator=True), *festival_rows]

    # Developer-only tools: the debug panel and event & stage simulations (birthdays, 419,
    # NYE countdown, musical, dome) live in their own top-level submenu.
    dev_party_rows = [
        MenuItemSpec(t("special_move_birthday_all", lang), getattr(pet, "preview_birthday_event", None)),
        MenuItemSpec(t("preview_event_user_birthday", lang), getattr(pet, "preview_user_birthday_event", None)),
        MenuItemSpec(t("preview_event_419", lang), getattr(pet, "preview_anniversary_event", None)),
        MenuItemSpec(t("preview_event_newyearseve", lang), getattr(pet, "preview_new_year_countdown", None)),
        MenuItemSpec(t("preview_event_musical", lang), getattr(pet, "preview_musical_event", None)),
        MenuItemSpec(t("preview_event_dome_baseball", lang), getattr(pet, "preview_dome_baseball_event", None)),
        MenuItemSpec(t("preview_event_dome_eunji", lang), getattr(pet, "preview_eunji_dome_event", None)),
    ]
    developer_mode = getattr(pet, "developer_mode", None)
    if developer_mode is None:
        developer_mode = is_developer_mode(settings)
    dev_sub = [
        MenuItemSpec(t("debug_panel", lang), getattr(pet, "open_debug_panel", None)),
        MenuItemSpec("", is_separator=True),
        *dev_party_rows,
    ]
    for row in special_sub:                 # the flyout swaps to a member's moves; this row swaps back
        if row.submenu:
            row.submenu.insert(0, MenuItemSpec(t("special_move_back", lang), None, submenu=special_sub))

    # 3. Character Switching Submenu
    today = datetime.date.today()
    wd_names = get_weekday_names(lang)
    auto_char = pet.get_auto_character() if hasattr(pet, "get_auto_character") else "chorong"
    auto_label = f"{t('auto_schedule', lang)} ({wd_names[today.weekday()]}: {get_member_display_name(auto_char, lang)})"
    char_sub = [
        MenuItemSpec(auto_label, getattr(pet, "switch_to_auto_schedule", None), checked=(getattr(pet, "mode", "") == "auto")),
        MenuItemSpec("", is_separator=True),
    ]
    members_order = [("chorong", 0), ("bomi", 1), ("eunji", 2), ("namjoo", 3), ("hayoung", 4)]
    for mkey, wday in members_order:
        mlbl = f"{wd_names[wday]}｜{get_member_display_name(mkey, lang)}"
        is_chk = getattr(pet, "mode", "") == "manual" and char_key == mkey
        char_sub.append(
            MenuItemSpec(mlbl, lambda k=mkey: pet.switch_character(k, mode="manual"), checked=is_chk)
        )
    char_sub.append(MenuItemSpec("", is_separator=True))
    char_sub.append(MenuItemSpec(t("random_pick", lang), getattr(pet, "random_character", None)))

    # 4. Standby Screen & Scene Previews Submenu
    hk_display = f" ({pet.hotkey_str})" if getattr(pet, "hotkey_str", None) else " (Ctrl+Shift+S)"
    lock_on = bool(settings.get("standby_lock_workstation", True))
    standby_sub = [
        MenuItemSpec(f"{t('standby_open', lang)}{hk_display}", getattr(pet, "open_standby_screen", None)),
        MenuItemSpec(t("standby_lock", lang), getattr(pet, "toggle_standby_lock", None), checked=lock_on),
        MenuItemSpec("", is_separator=True),
        MenuItemSpec(t("preview_standby_christmas", lang), lambda: pet.preview_standby_scene("christmas")),
        MenuItemSpec(t("preview_standby_campfire", lang), lambda: pet.preview_standby_scene("campfire")),
        MenuItemSpec(t("preview_standby_starfield", lang), lambda: pet.preview_standby_scene("starfield")),
        MenuItemSpec(t("preview_standby_practice", lang), lambda: pet.preview_standby_scene("practice_room")),
        *(MenuItemSpec(_WALLPAPER_LABEL.get(lang, _WALLPAPER_LABEL["zh_TW"]).format(name=spec.label(lang)),
                       lambda key=spec.key: pet.preview_standby_scene(key)) for spec in _wallpapers()),
    ]

    # 5. Notification Drawer & Stream Privacy Mask Submenu
    recent_list = getattr(pet, "recent_notifications", [])
    drawer_badge = f"{len(recent_list)}/20"
    privacy_on = bool(settings.get("notify_privacy_mode", False))
    notif_relay_on = bool(settings.get("notify_relay", True))
    privacy_cmd = getattr(pet, "toggle_notify_privacy", None) or getattr(pet, "toggle_notify_privacy_mode", None)
    notify_style = settings.get("notify_bubble_style", "banner")
    notify_styles = [
        MenuItemSpec(t(f"notify_style_{key}", lang), lambda key=key: pet.set_notify_bubble_style(key),
                     checked=(notify_style == key))
        for key in ("banner", "sticky", "standard")
    ]
    notif_sub = [
        MenuItemSpec(f"{t('notif_drawer_menu', lang)} ({drawer_badge})", getattr(pet, "open_notification_drawer", None)),
        MenuItemSpec(t("notif_drawer_clear_menu", lang), getattr(pet, "clear_recent_notifications", None)),
        MenuItemSpec(t("notify_privacy_toggle", lang), privacy_cmd, checked=privacy_on),
        MenuItemSpec(t("notify_relay", lang), getattr(pet, "toggle_notify_relay", None), checked=notif_relay_on),
        MenuItemSpec(t("notify_bubble_style", lang), submenu=notify_styles),
    ]

    # 6. Mouse Cursor Styles Submenu
    cur_cursor = settings.get("mouse_cursor", "paw_smooth")
    cursor_sub = [
        MenuItemSpec(t("cursor_paw_smooth", lang), lambda: pet.set_mouse_cursor("paw_smooth"), checked=(cur_cursor == "paw_smooth")),
        MenuItemSpec(t("cursor_mitten_smooth", lang), lambda: pet.set_mouse_cursor("mitten_smooth"), checked=(cur_cursor == "mitten_smooth")),
        MenuItemSpec(t("cursor_paw_pixel", lang), lambda: pet.set_mouse_cursor("paw_pixel"), checked=(cur_cursor == "paw_pixel")),
        MenuItemSpec(t("cursor_mitten_pixel", lang), lambda: pet.set_mouse_cursor("mitten_pixel"), checked=(cur_cursor == "mitten_pixel")),
        MenuItemSpec(t("cursor_system", lang), lambda: pet.set_mouse_cursor("system"), checked=(cur_cursor == "system")),
    ]

    # 7. Language & System Submenu
    autostart_on = bool(pet.is_autostart_enabled()) if hasattr(pet, "is_autostart_enabled") else False
    lang_sub = [
        MenuItemSpec("繁體中文", lambda: pet.set_language("zh_TW"), checked=(lang == "zh_TW")),
        MenuItemSpec("한국어", lambda: pet.set_language("ko"), checked=(lang == "ko")),
        MenuItemSpec("English", lambda: pet.set_language("en"), checked=(lang == "en")),
        MenuItemSpec("", is_separator=True),
        MenuItemSpec(t("autostart", lang), getattr(pet, "toggle_autostart", None), checked=autostart_on),
        MenuItemSpec(t("hide_to_tray", lang), getattr(pet, "hide_to_tray", None)),
    ]
    items = [
        MenuItemSpec(t("status_card", lang), getattr(pet, "show_status_card", None), icon_name="icon_paws", submenu=action_sub, tag_id="row_actions"),
        MenuItemSpec(t("chat", lang), getattr(pet, "chat_with_pet", None), icon_name="icon_chat", tag_id="row_chat"),
        MenuItemSpec(t("food_cafe", lang), getattr(pet, "open_food_panel", None), icon_name="icon_food", tag_id="row_food"),
        MenuItemSpec(t("special_moves_menu", lang), None, icon_name="icon_trophy", submenu=special_sub, tag_id="row_special"),
        MenuItemSpec(f"{t('switch_character', lang)} ({get_member_display_name(char_key, lang)})", None, icon_name="icon_photo", submenu=char_sub, tag_id="row_char"),
        MenuItemSpec(t("standby", lang), None, icon_name="icon_sleep", submenu=standby_sub, tag_id="row_standby"),
        MenuItemSpec(t("notif_drawer_menu", lang), getattr(pet, "open_notification_drawer", None), icon_name="icon_clock", submenu=notif_sub, badge=drawer_badge, tag_id="row_notif"),
        MenuItemSpec(t("cursor_style_menu", lang), None, icon_name="icon_paws", submenu=cursor_sub, tag_id="row_cursor"),
        MenuItemSpec(t("settings_panel", lang), getattr(pet, "open_settings_panel", None), icon_name="icon_settings", tag_id="row_settings"),
        MenuItemSpec(t("lang_switch", lang), None, icon_name="icon_settings", submenu=lang_sub, tag_id="row_lang"),
    ]
    if developer_mode:
        items.append(MenuItemSpec(t("dev_tools_menu", lang), None, icon_name="icon_settings",
                                  submenu=dev_sub, tag_id="row_dev"))
    items += [
        MenuItemSpec("", is_separator=True),
        MenuItemSpec(t("exit", lang), getattr(pet, "close", None), is_danger=True, tag_id="row_exit"),
    ]
    return items

