"""app/fortune_room.py — Eunji's Mystic Fortune Studio stage layout & interactive Tarot dialog.

Shared domain + view module used by Standby (`app/standby.py`) and Desktop (`app/main.py`):
- Standby scene `bg_standby_eunji_fortune_room`: places Tarot Reader Eunji on the left
  side of the center crystal-ball table, Student querent (when approved) on the right side,
  and the other four members cheering warmly on the carpet flanks with zero overlap.
- Desktop interactive `FortuneRoomDialog`: plays the crystal-ball Tarot card draw
  sequence (`work/scenes/fortune_room/frame_01..24.png`) and reveals an original
  trilingual Fortune Tarot reading (`zh_TW`, `ko`, `en`).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from datetime import datetime
import logging
import random
import tkinter as tk
import time
from typing import Optional
from collections import OrderedDict
import threading

from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.dome_stage import (
    WALLPAPER_SRC_SIZE,
    _spread_centers_non_overlapping,
    map_cover_point,
)
from app.fortune_cards import (
    CHORONG_EGG_CARD, CHORONG_EGG_LINES, CHORONG_EGG_TAG, CHORONG_EGG_UNLOCK,
    EGG_EMBLEM_CLICKS, EGG_EMBLEM_WINDOW_MS, EGG_GOLD, GUARDIAN_LINES_FINAL,
    GUARDIAN_TAGS_FINAL, TAROT_CARDS, TarotCard,
)
from app.fortune_reading import FOODS, Reading, daily_fortune, egg_chance, make_reading
from app.foods import get_food_name
from app.i18n import get_member_display_name, t
from app.paths import resource_dir
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, ui_scale
from app.resource_store import open_resource_image, resource_exists, resource_store

BG_TRANSPARENT = "#ff00fe"
log = logging.getLogger(__name__)
_THEATER_PIL = OrderedDict()
_THEATER_LOCK = threading.RLock()
_THEATER_LIMIT = 32 * 1024 * 1024


def _scaled_theater_frames(root: Path, width: int, height: int) -> tuple[Image.Image, ...]:
    # Resolve the store once and pass relative keys: the cache key is computed on
    # the Tk thread every time the dialog opens, so per-frame resource_exists /
    # resource_stat_signature (each re-resolving the store and path) made a hit cost
    # as much as a small decode.
    store = resource_store(root)
    keys = []
    signatures = []
    for idx in range(1, FORTUNE_THEATER_FRAME_COUNT + 1):
        rel = f"work/scenes/fortune_room/frame_{idx:02d}.png"
        if not store.exists(rel):
            break
        keys.append(rel)
        signatures.append(store.stat_signature(rel))
    key = (str(store.base_root), width, height, tuple(signatures))
    with _THEATER_LOCK:
        if key in _THEATER_PIL:
            _THEATER_PIL.move_to_end(key)
            return _THEATER_PIL[key]
    pictures = []
    for rel in keys:
        try:
            with open_resource_image(rel, root=root) as source:
                rgb = source.convert("RGB")
                if rgb.size != (width, height):
                    rgb = rgb.resize((width, height), Image.Resampling.LANCZOS)
                pictures.append(rgb)
        except (OSError, ValueError):
            log.warning("Fortune theater frame could not be decoded: %s", rel, exc_info=True)
            return tuple(pictures)
    frames = tuple(pictures)
    size = width * height * 4 * len(frames)   # Pillow RGB is 4 bytes/pixel
    if frames and size <= _THEATER_LIMIT:
        with _THEATER_LOCK:
            _THEATER_PIL[key] = frames
            while sum(k[1] * k[2] * 4 * len(v) for k, v in _THEATER_PIL.items()) > _THEATER_LIMIT:
                _THEATER_PIL.popitem(last=False)
    return frames

FORTUNE_ROOM_SCENE = "bg_standby_eunji_fortune_room"
FORTUNE_READER_ACTION = "fortune_tarot_reader"
FORTUNE_STUDENT_ACTION = "fortune_student"
FORTUNE_LOVE_DESKTOP_ACTION = "fortune_love_reading"

FORTUNE_LEFT_MEMBERS: tuple[str, ...] = ("chorong", "bomi", "eunji")
FORTUNE_RIGHT_FLANK_MEMBERS: tuple[str, ...] = ("namjoo", "hayoung")
FORTUNE_THEATER_FRAME_MS = 95
FORTUNE_THEATER_FRAME_COUNT = 24


_CARD_UI_TEXT = {
    "zh_TW": {
        "title": "恩地神祕占卜室 · 今日塔羅指引",
        "drawing": "水晶球感應星塵中… 恩地正在為你翻開塔羅牌",
        "draw_again": "再抽一張",
        "daily": "今日專屬一籤",
        "random": "隨手抽",
        "skip": "略過動畫",
        "motion_on": "恢復動態",
        "motion_off": "減少動態",
        "summon_desktop": "桌面占卜小劇場",
        "close": "關閉",
        "fallback_hint": "（點下方按鈕隨時抽取恩地為你準備的專屬幸運牌）",
    },
    "ko": {
        "title": "은지의 신비로운 점집 · 오늘의 타로",
        "drawing": "수정구슬이 별빛을 모으는 중… 은지가 타로 카드를 펼치고 있어요",
        "draw_again": "다시 뽑기",
        "daily": "오늘의 타로",
        "random": "랜덤 타로",
        "skip": "애니메이션 건너뛰기",
        "motion_on": "움직임 복원",
        "motion_off": "움직임 줄이기",
        "summon_desktop": "바탕화면 타로 극장",
        "close": "닫기",
        "fallback_hint": "(아래 버튼을 눌러 은지의 타로 행운 카드를 뽑아 보세요)",
    },
    "en": {
        "title": "Eunji's Fortune Studio · Tarot Reading",
        "drawing": "Crystal ball shimmering… Eunji is revealing today's card",
        "draw_again": "Draw Again",
        "daily": "Today's Reading",
        "random": "Random Reading",
        "skip": "Skip Animation",
        "motion_on": "Restore Motion",
        "motion_off": "Reduce Motion",
        "summon_desktop": "Desktop Duo Show",
        "close": "Close",
        "fallback_hint": "(Click below to draw today's lucky Tarot reading)",
    },
}


def pick_tarot_card(rng: random.Random | None = None, last_key: str | None = None) -> TarotCard:
    """Return a Tarot card avoiding back-to-back repeats when possible."""
    picker = rng or random
    pool = [c for c in TAROT_CARDS if c.key != last_key] or list(TAROT_CARDS)
    return picker.choice(pool)


def fortune_table_corridor(
    canvas_w: int,
    canvas_h: int,
    *,
    ui_scale_factor: float = 1.0,
) -> tuple[float, float]:
    """Return `(left_limit_x, right_limit_x)` framing the center crystal-ball table in `場景.jpg`."""
    k = max(0.8, float(ui_scale_factor))
    gap = max(10.0, 14.0 * k)
    tbl_left = map_cover_point(0.385, 0.85, canvas_w, canvas_h, WALLPAPER_SRC_SIZE)[0]
    tbl_right = map_cover_point(0.605, 0.85, canvas_w, canvas_h, WALLPAPER_SRC_SIZE)[0]
    cx = canvas_w / 2.0
    min_half = max(72.0, min(canvas_w * 0.14, 150.0 * k))
    left_lim = min(tbl_left - gap, cx - min_half)
    right_lim = max(tbl_right + gap, cx + min_half)
    return left_lim, right_lim


def compute_fortune_standby_slots(
    canvas_w: int,
    canvas_h: int,
    member_sizes: Mapping[str, tuple[int, int]],
    *,
    include_student: bool = True,
    ui_scale_factor: float = 1.0,
) -> dict[str, tuple[int, int]]:
    """Non-overlapping `(center_x, feet_y)` slots around the center fortune tarot table.

    - Leaves the center table & crystal ball (`nx ≈ 0.385..0.605`) uncovered on landscape screens,
      and smoothly redistributes the flank intervals on portrait/narrow screens so all actors
      never stack or overlap.
    - Places `chorong`, `bomi`, `eunji` (`fortune_tarot_reader`) on the left rug.
    - Places `student` (when available), `namjoo`, `hayoung` on the right rug.
    """
    k = max(0.8, float(ui_scale_factor))
    margin = max(14.0, 22.0 * k)
    bottom_pad = max(20.0, 28.0 * k)
    pair_gap = max(6.0, 12.0 * k) if canvas_w < canvas_h else max(8.0, 14.0 * k)

    left_lim, right_lim = fortune_table_corridor(canvas_w, canvas_h, ui_scale_factor=k)
    left_members = list(FORTUNE_LEFT_MEMBERS)
    right_members = (["student"] if include_student else []) + list(FORTUNE_RIGHT_FLANK_MEMBERS)

    left_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in left_members]
    right_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in right_members]

    left_span = float(sum(left_widths) + pair_gap * max(0, len(left_widths) - 1))
    right_span = float(sum(right_widths) + pair_gap * max(0, len(right_widths) - 1))

    left_avail = left_lim - margin
    right_avail = (canvas_w - margin) - right_lim
    if left_avail >= left_span and right_avail >= right_span:
        left_hi = left_lim
        right_lo = right_lim
    else:
        # Narrow / portrait aspect: cover-cropped table widens horizontally, so keep as much
        # central corridor as fits alongside non-overlapping left/right intervals.
        avail_total = max(60.0, canvas_w - 2.0 * margin)
        extra = max(0.0, avail_total - left_span - right_span)
        corridor_gap = min(max(pair_gap * 2.0, right_lim - left_lim), extra * 0.72) if extra > 0 else 0.0
        side_slack = max(0.0, (extra - corridor_gap) * 0.5)
        if left_span + right_span <= avail_total:
            left_hi = margin + left_span + side_slack
            right_lo = (canvas_w - margin) - right_span - side_slack
        else:
            share = left_span / max(1.0, left_span + right_span)
            left_hi = margin + avail_total * share
            right_lo = left_hi + pair_gap

    left_norm_x = (0.125, 0.225, 0.335)
    left_desired = [map_cover_point(nx, 0.89, canvas_w, canvas_h, WALLPAPER_SRC_SIZE)[0] for nx in left_norm_x]
    left_xs = _spread_centers_non_overlapping(
        left_desired, left_widths, margin, max(margin + left_span, left_hi), pair_gap
    )

    right_norm_x = (0.665, 0.775, 0.875) if include_student else (0.72, 0.85)
    right_desired = [map_cover_point(nx, 0.89, canvas_w, canvas_h, WALLPAPER_SRC_SIZE)[0] for nx in right_norm_x]
    right_xs = _spread_centers_non_overlapping(
        right_desired, right_widths, min((canvas_w - margin) - right_span, right_lo), canvas_w - margin, pair_gap
    )

    ny_feet = 0.945 if canvas_w < canvas_h else 0.895
    raw_fy = map_cover_point(0.5, ny_feet, canvas_w, canvas_h, WALLPAPER_SRC_SIZE)[1]
    slots: dict[str, tuple[int, int]] = {}
    for group_names, group_xs in ((left_members, left_xs), (right_members, right_xs)):
        for m, cx in zip(group_names, group_xs):
            mh = max(48, member_sizes.get(m, (150, 150))[1])
            min_fy = int(round(max(canvas_h * 0.56, mh + 36 * k)))
            max_fy = max(min_fy, int(round(canvas_h - bottom_pad)))
            fy = max(min_fy, min(max_fy, int(round(raw_fy))))
            slots[m] = (cx, fy)
    return slots


def _font_family(lang: str) -> str:
    if lang == "ko":
        return "Malgun Gothic"
    if lang == "en":
        return "Segoe UI"
    return "Microsoft JhengHei"


class FortuneRoomDialog:
    """Animated mystic Tarot Fortune Room popup with interactive card draw."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        lang: str = "zh_TW",
        res_root: Path | None = None,
        on_summon_desktop: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        reduced_motion: bool = False,
        on_motion_change: Callable[[bool], None] | None = None,
        rng: random.Random | None = None,
        daily_provider: Callable[[], Reading] | None = None,
        clock: Callable[[], datetime] = datetime.now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.parent = parent
        self.lang = lang if lang in _CARD_UI_TEXT else "zh_TW"
        self.res_root = Path(res_root) if res_root is not None else resource_dir()
        self.on_summon_desktop = on_summon_desktop
        self.on_close = on_close
        self.on_motion_change = on_motion_change
        self.rng = rng or random.Random()
        self.tx = _CARD_UI_TEXT[self.lang]
        self._design_w, self._design_h = 540, 650
        self._after_id: Optional[str] = None
        self._closed = False
        self._drag_offset: tuple[int, int] | None = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._frame_idx = 0
        self._revealed = False
        self._clock = clock
        self._monotonic = monotonic
        self._daily_provider = daily_provider or (lambda: daily_fortune(self._clock().date(), "", None)[0])
        self.reading = self._daily_provider()
        self.current_card = self.reading.card
        self._daily = True
        self._egg_shown = self._egg_forced = self._egg_pending = self._egg_unlock = False
        self._emblem_clicks = []
        self._emblem_press = None
        self._reduced_motion = reduced_motion
        self._upload_id = None
        self._load_generation = 0
        self._loading = True
        self._frame_source = ()
        self._focus_slot = 0
        self._pressed_control: int | None = None

        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        try:
            if parent and hasattr(parent, "state") and parent.state() != "withdrawn":
                self.win.transient(parent)
        except Exception:
            pass
        self.win.title(self.tx["title"])
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.configure(bg=BG_TRANSPARENT)
        try:
            self.win.attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass

        self.k = ui_scale(self.win)
        self._draw_scale = self.k
        self._win_pos = (12, 12)
        self._desktop = WindowsDesktopAdapter(
            fallback_bounds=lambda: WorkArea(
                0, 0, max(640, int(self.win.winfo_screenwidth())), max(480, int(self.win.winfo_screenheight()))
            )
        )
        self._compute_fitted_layout()

        self.canvas = tk.Canvas(
            self.win,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.bind("<Tab>", lambda _e: self._move_focus(1))
        self.win.bind("<Shift-Tab>", lambda _e: self._move_focus(-1))
        self.win.bind("<Return>", self._activate_focus)
        self.win.bind("<space>", self._activate_focus)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._render()
        x, y = self._win_pos
        self.win.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.win.deiconify()
        self.win.lift()
        self.canvas.focus_set()
        self._upload_id = self.win.after(1, self._load_frames, self._load_generation)

    def _s(self, v: float) -> int:
        return max(1, round(v * self._draw_scale))

    def _font_px(self, pt: float) -> int:
        # Negative Tkinter font sizes specify exact pixel height so text scales
        # uniformly with WorkArea fit even at 192 DPI on compact displays.
        return -max(8, round(pt * (96.0 / 72.0) * self._draw_scale))

    def _compute_fitted_layout(self) -> None:
        self.win.update_idletasks()
        try:
            area = self._area_for_parent()
        except Exception:
            area = WorkArea(0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight())
        avail_w = max(240, (area.right - area.left) - 24)
        avail_h = max(260, (area.bottom - area.top) - 24)
        raw_w = self._design_w * self.k
        raw_h = self._design_h * self.k
        fit = 1.0
        if raw_w > avail_w or raw_h > avail_h:
            fit = min(avail_w / max(1.0, raw_w), avail_h / max(1.0, raw_h))
        self._draw_scale = max(0.35, self.k * fit)
        self.w = max(240, min(avail_w, round(self._design_w * self._draw_scale)))
        self.h = max(260, min(avail_h, round(self._design_h * self._draw_scale)))
        self._media_w = max(120, round(480 * self._draw_scale))
        self._media_h = max(68, round(270 * self._draw_scale))
        x = max(area.left + 12, min(area.right - self.w - 12, (area.left + area.right - self.w) // 2))
        y = max(area.top + 12, min(area.bottom - self.h - 12, (area.top + area.bottom - self.h) // 2))
        self._win_pos = (x, y)

    def _area_for_parent(self) -> WorkArea:
        x = self.parent.winfo_rootx() + self.parent.winfo_width() // 2
        y = self.parent.winfo_rooty() + self.parent.winfo_height() // 2
        return self._desktop.work_area_for_point(x, y)

    def set_language(self, lang: str) -> None:
        """Refresh UI strings and current Tarot reading card after app language changes."""
        target = lang if lang in _CARD_UI_TEXT else "zh_TW"
        if target == self.lang or self._closed:
            return
        self.lang = target
        self.tx = _CARD_UI_TEXT[target]
        try:
            if not self.win.winfo_exists():
                return
            self.win.title(self.tx["title"])
        except tk.TclError:
            return
        self._render()
        if getattr(self, "_media_item", None) is not None and self._photos:
            shown_idx = min(self._frame_idx, len(self._photos) - 1)
            try:
                self.canvas.itemconfigure(self._media_item, image=self._photos[shown_idx])
            except tk.TclError:
                pass

    def _draw_crystal_emblem(self, cx: int, cy: int, r: int) -> None:
        self.canvas.create_polygon(
            cx - r * 0.72, cy + r * 0.98,
            cx - r * 0.45, cy + r * 0.62,
            cx + r * 0.45, cy + r * 0.62,
            cx + r * 0.72, cy + r * 0.98,
            fill="#eab308", outline="#fde047", width=1,
        )
        self.canvas.create_oval(
            cx - r * 0.85, cy - r * 0.92, cx + r * 0.85, cy + r * 0.78,
            fill="#7c3aed", outline="#ddd6fe", width=max(1, self._s(1.2)),
        )
        self.canvas.create_oval(
            cx - r * 0.48, cy - r * 0.62, cx - r * 0.05, cy - r * 0.19,
            fill="#e0f2fe", outline="",
        )

    def _draw_star_polygon(self, cx: float, cy: float, outer_r: float, *, fill: str, outline: str) -> None:
        import math
        inner_r = outer_r * 0.44
        pts: list[float] = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            rad = outer_r if i % 2 == 0 else inner_r
            pts.extend((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        self.canvas.create_polygon(*pts, fill=fill, outline=outline, width=1, tags=(self._reveal_group_tag,))

    def _load_frames(self, generation: int) -> None:
        self._upload_id = None
        if self._closed or generation != self._load_generation:
            return
        try:
            self._frame_source = _scaled_theater_frames(self.res_root, self._media_w, self._media_h)
        except (OSError, ValueError):
            log.warning("Fortune theater is unavailable", exc_info=True)
        if not self._frame_source:
            bg_rel = self.res_root / "work/standby_backgrounds/bg_standby_eunji_fortune_room.jpg"
            try:
                if resource_exists(bg_rel, root=self.res_root):
                    with open_resource_image(bg_rel, root=self.res_root) as im:
                        self._frame_source = (im.convert("RGB").resize(
                            (self._media_w, self._media_h), Image.Resampling.LANCZOS),)
            except (OSError, ValueError):
                log.warning("Fortune theater fallback is unavailable", exc_info=True)
        self._upload_frames(generation)

    def _upload_frames(self, generation: int) -> None:
        self._upload_id = None
        if self._closed or generation != self._load_generation:
            return
        start = len(self._photos)
        stop = start + (1 if start == 0 else 3)
        try:
            for rgb in self._frame_source[start:stop]:
                self._photos.append(ImageTk.PhotoImage(rgb, master=self.win))
            if start == 0 and self._photos:
                self.canvas.itemconfigure(self._media_item, image=self._photos[0])
                self.canvas.delete("media_placeholder")
        except (tk.TclError, OSError, ValueError):
            log.warning("Fortune theater upload stopped", exc_info=True)
            self._frame_source = ()
        if len(self._photos) < len(self._frame_source):
            self._upload_id = self.win.after(1, self._upload_frames, generation)
        else:
            self._frame_source = ()
            self._loading = False
            if not self._revealed:
                self._start_playback()

    def _render(self) -> None:
        self.canvas.delete("all")
        w, h = self.w, self.h
        fam = _font_family(self.lang)
        f_title = (fam, self._font_px(11), "bold")
        f_badge = (fam, self._font_px(9), "bold")
        f_card = (fam, self._font_px(12), "bold")
        f_body = (fam, self._font_px(10))
        f_sub = (fam, self._font_px(9), "bold")
        f_btn = (fam, self._font_px(9), "bold")

        # Outer mystic deep violet card + sky-blue rim
        _draw_round_rect(
            self.canvas, self._s(4), self._s(4), w - self._s(4), h - self._s(4),
            r=self._s(20), fill="#17112b", outline="#7dd3fc", width=self._s(2),
        )
        # Header bar
        _draw_round_rect(
            self.canvas, self._s(7), self._s(7), w - self._s(7), self._s(48),
            r=self._s(16), fill="#261947", outline="#a78bfa", width=1,
        )
        self._emblem_bounds = (self._s(12), self._s(14), self._s(38), self._s(42))
        emblem_outline = "#fbbf24" if self._focus_slot == 0 else ""
        self.canvas.create_rectangle(*self._emblem_bounds, outline=emblem_outline)
        self._draw_crystal_emblem(self._s(25), self._s(28), self._s(8))
        self.canvas.create_text(
            self._s(41), self._s(28), anchor="w", text=self.tx["title"],
            fill="#e0f2fe", font=f_title, width=w - self._s(89), tags=("dialog_title",),
        )
        close_cx, close_cy, close_r = w - self._s(28), self._s(27), self._s(12)
        self.canvas.create_oval(
            close_cx - close_r, close_cy - close_r, close_cx + close_r, close_cy + close_r,
            fill="#3b2668", outline="#a78bfa", width=1, tags=("close_btn",),
        )
        arm = max(3, round(close_r * 0.42))
        self.canvas.create_line(
            close_cx - arm, close_cy - arm, close_cx + arm, close_cy + arm,
            fill="#e0f2fe", width=max(1.5, self._draw_scale * 1.8), capstyle="round", tags=("close_btn",),
        )
        self.canvas.create_line(
            close_cx - arm, close_cy + arm, close_cx + arm, close_cy - arm,
            fill="#e0f2fe", width=max(1.5, self._draw_scale * 1.8), capstyle="round", tags=("close_btn",),
        )

        # Animated Tarot Theater frame container
        mx0 = (w - self._media_w) // 2
        my0 = self._s(58)
        _draw_round_rect(
            self.canvas, mx0 - self._s(3), my0 - self._s(3),
            mx0 + self._media_w + self._s(3), my0 + self._media_h + self._s(3),
            r=self._s(12), fill="#0d081c", outline="#8b5cf6", width=2,
        )
        self._media_item = self.canvas.create_image(
            w // 2, my0 + self._media_h // 2, anchor="center",
            image=self._photos[min(self._frame_idx, len(self._photos) - 1)] if self._photos else "",
        )
        if not self._photos:
            cx, cy = w // 2, my0 + self._media_h // 2
            r = self._s(38)
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#5b21b6", outline="#c4b5fd",
                                    tags=("media_placeholder",))

        # Fortune Reveal Panel
        py0 = my0 + self._media_h + self._s(12)
        py1 = h - self._s(77)
        self._reveal_outline = _draw_round_rect(
            self.canvas, self._s(20), py0, w - self._s(20), py1,
            r=self._s(14), fill="#21163e", outline="#6d28d9", width=1.5,
        )
        self._reveal_group_tag = "reveal_panel"
        self._f_fonts = (f_badge, f_card, f_body, f_sub)
        self._reveal_bounds = (self._s(20), py0, w - self._s(20), py1)
        self._draw_reveal_contents()

        # Bottom action buttons
        buttons: list[tuple[str, str, str, Callable[[], None]]] = [
            (self.tx["draw_again"], "#6d28d9", "#ede9fe", self.draw_again),
            (self.tx["daily"], "#3b2668", "#ede9fe", self.show_daily),
            (self.tx["skip"], "#3b2668", "#ede9fe", self.skip_animation),
            (self.tx["motion_on" if self._reduced_motion else "motion_off"],
             "#3b2668", "#ede9fe", self.toggle_motion),
        ]
        if callable(self.on_summon_desktop):
            buttons.append((self.tx["summon_desktop"], "#0284c7", "#e0f2fe", self._summon_desktop))
        buttons.append((self.tx["close"], "#332557", "#cbd5e1", self.close))

        self._focus_handlers = [self._record_emblem_click] + [item[3] for item in buttons]
        gap = self._s(10)
        btn_w = (w - self._s(40) - 2 * gap) // 3
        for idx, (label, fill_hex, fg_hex, _) in enumerate(buttons):
            bx = self._s(20) + (idx % 3) * (btn_w + gap)
            by0 = h - self._s(68) + (idx // 3) * self._s(29)
            by1 = by0 + self._s(25)
            tag = f"btn_{idx}"
            _draw_round_rect(
                self.canvas, bx, by0, bx + btn_w, by1,
                r=self._s(8), fill=fill_hex,
                outline="#fbbf24" if self._focus_slot == idx + 1 else "#c4b5fd",
                width=1, tags=("action_buttons", tag),
            )
            self.canvas.create_text(
                bx + btn_w // 2, (by0 + by1) // 2, text=label, fill=fg_hex,
                font=f_btn, width=btn_w - self._s(8), tags=("action_buttons", tag, f"{tag}_label"),
            )

    def _draw_reveal_contents(self) -> None:
        self.canvas.delete(self._reveal_group_tag)
        egg = self._revealed and self.current_card.key == CHORONG_EGG_CARD.key
        self.canvas.itemconfigure(self._reveal_outline, outline=EGG_GOLD if egg else "#6d28d9")
        x0, y0, x1, y1 = self._reveal_bounds
        cx = (x0 + x1) // 2
        pad_w = (x1 - x0) - self._s(32)
        f_badge, f_card, f_body, f_sub = self._f_fonts
        if not self._revealed:
            self.canvas.create_text(
                cx, (y0 + y1) // 2, text=self.tx["drawing"], fill="#ddd6fe",
                font=f_body, width=pad_w, justify="center", tags=(self._reveal_group_tag,),
            )
            return
        card = self.current_card
        cursor_y = y0 + self._s(7)

        def row(text, font, fill, tag, gap=3):
            nonlocal cursor_y
            item = self.canvas.create_text(cx, cursor_y, text=text, font=font, fill=fill,
                                           anchor="n", width=pad_w, justify="center",
                                           tags=(self._reveal_group_tag, tag))
            cursor_y = self.canvas.bbox(item)[3] + self._s(gap)

        row(self.tx["daily" if self._daily else "random"], f_sub, "#c4b5fd", "mode_chip")
        badge_item = self.canvas.create_text(
            cx, cursor_y, anchor="n", text=card.badge[self.lang], fill=card.accent,
            font=f_badge, tags=(self._reveal_group_tag, "card_badge"),
        )
        badge_box = self.canvas.bbox(badge_item)
        star_y = (badge_box[1] + badge_box[3]) / 2
        star_r = max(3.5, self._draw_scale * 5.0)
        star_step = max(9.0, self._draw_scale * 12.0)
        n_stars = len(card.stars)
        stars_span = star_r * 2.0 + max(0, n_stars - 1) * star_step
        badge_w = (badge_box[2] - badge_box[0]) if badge_box else 0
        gap_s = self._s(10)
        group_w = badge_w + gap_s + stars_span
        group_x0 = cx - group_w / 2.0
        self.canvas.move(badge_item, (group_x0 + badge_w / 2.0) - cx, 0)
        filled = card.stars.count("★")
        star_start_x = group_x0 + badge_w + gap_s + star_r
        for s_idx in range(n_stars):
            is_lit = s_idx < filled
            self._draw_star_polygon(
                star_start_x + s_idx * star_step,
                star_y,
                star_r,
                fill=card.accent if is_lit else "#3b2c63",
                outline=card.accent if is_lit else "#6d28d9",
            )
        cursor_y = badge_box[3] + self._s(3)
        row(card.title[self.lang], f_card, "#f8fafc", "card_title")
        row(card.message[self.lang], f_body, "#e2e8f0", "card_message")
        row(card.lucky[self.lang], f_sub, "#93c5fd", "card_lucky")
        guardian = self.reading.guardian_id
        persona_egg = guardian == "chorong" and self._egg_shown and not self._daily
        label = CHORONG_EGG_TAG if persona_egg else GUARDIAN_TAGS_FINAL[guardian]
        lines = CHORONG_EGG_LINES if persona_egg else GUARDIAN_LINES_FINAL[guardian]
        row(f"{get_member_display_name(guardian, self.lang)} · {label[self.lang]}",
            f_sub, "#fde68a" if persona_egg else "#ddd6fe", "guardian_row")
        guardian_line = (
            CHORONG_EGG_UNLOCK if egg and self._egg_unlock else lines[self.reading.line_id % len(lines)]
        )
        row(guardian_line[self.lang], f_sub, "#e2e8f0", "guardian_row")
        food = FOODS.get(self.reading.food_id)
        if food:
            row(t("fortune_lucky_food", self.lang, food=get_food_name(food, self.lang)),
                f_sub, "#a7f3d0", "food_row")

    def _start_playback(self) -> None:
        self._cancel_playback()
        self._frame_idx = 0
        self._revealed = False
        if self._reduced_motion or (not self._loading and len(self._photos) <= 1):
            self.skip_animation()
            return
        self._draw_reveal_contents()
        if len(self._photos) > 1 and not self._loading and not self._closed:
            self._playback_start = self._monotonic()
            self._after_id = self.win.after(FORTUNE_THEATER_FRAME_MS, self._tick_playback)

    def _cancel_playback(self) -> None:
        if self._after_id is not None:
            try:
                self.win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick_playback(self) -> None:
        self._after_id = None
        if self._closed or self._loading or self._revealed:
            return
        elapsed_ms = max(0.0, (self._monotonic() - self._playback_start) * 1000)
        frame = int(elapsed_ms // FORTUNE_THEATER_FRAME_MS)
        if frame >= len(self._photos) - 1:
            self.skip_animation()
            return
        if frame != self._frame_idx:
            self._frame_idx = frame
            self.canvas.itemconfigure(self._media_item, image=self._photos[frame])
        remaining = (frame + 1) * FORTUNE_THEATER_FRAME_MS - elapsed_ms
        self._after_id = self.win.after(max(1, round(remaining)), self._tick_playback)

    def draw_again(self) -> None:
        """Pick a new Tarot card and replay the crystal ball reveal."""
        if self._closed or not self._revealed:
            return
        egg = not self._egg_shown and (self._egg_forced or self.rng.random() < egg_chance(self._clock().hour))
        reading = make_reading(self.rng, self.current_card.key, egg=egg)
        self._select_reading(reading, daily=False, egg=egg)

    def show_daily(self) -> None:
        if not self._closed:
            self._select_reading(self._daily_provider(), daily=True)

    def _select_reading(self, reading: Reading, *, daily: bool, egg=False) -> None:
        self.reading = reading
        self.current_card = reading.card
        self._daily = daily
        self._egg_pending = egg
        self._egg_unlock = False
        if self._photos:
            self.canvas.itemconfigure(self._media_item, image=self._photos[0])
        self._start_playback()

    def skip_animation(self) -> None:
        if self._closed or self._revealed:
            return
        self._cancel_playback()
        if self._photos:
            self._frame_idx = len(self._photos) - 1
            self.canvas.itemconfigure(self._media_item, image=self._photos[self._frame_idx])
        self._revealed = True
        if self._egg_pending:
            self._egg_shown = self._egg_unlock = True
            self._egg_pending = self._egg_forced = False
        self._draw_reveal_contents()

    def toggle_motion(self) -> None:
        if self._closed:
            return
        self._reduced_motion = not self._reduced_motion
        if self._reduced_motion:
            self.skip_animation()
        self._render()
        if self.on_motion_change is not None:
            self.on_motion_change(self._reduced_motion)

    def _move_focus(self, direction: int) -> str:
        self._focus_slot = (self._focus_slot + direction) % len(self._focus_handlers)
        self._render()
        return "break"

    def _activate_focus(self, _event: tk.Event) -> str:
        if not self._closed:
            self._focus_handlers[self._focus_slot]()
        return "break"

    def _click_control(self, index: int) -> None:
        if not self._closed:
            self._focus_slot = index
            self.canvas.focus_set()
            self._focus_handlers[index]()

    def _in_emblem(self, event: tk.Event) -> bool:
        x0, y0, x1, y1 = self._emblem_bounds
        return x0 <= event.x <= x1 and y0 <= event.y <= y1

    def _record_emblem_click(self) -> None:
        if self._closed or self._egg_shown:
            return
        now = self._monotonic()
        interval = EGG_EMBLEM_WINDOW_MS / 1000
        self._emblem_clicks = [stamp for stamp in self._emblem_clicks if now - stamp <= interval]
        self._emblem_clicks.append(now)
        if len(self._emblem_clicks) >= EGG_EMBLEM_CLICKS:
            self._egg_forced = True
            self._emblem_clicks.clear()

    def _summon_desktop(self) -> None:
        if callable(self.on_summon_desktop):
            self.on_summon_desktop()

    def _control_at(self, event: tk.Event) -> int | None:
        # Use the click coordinates, even if a redraw replaced the item under a
        # stationary pointer since Tk last updated the canvas "current" tag.
        for item in reversed(self.canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            tags = self.canvas.gettags(item)
            if "close_btn" in tags:
                return 0  # Header close button, outside the footer's focus order.
            if "action_buttons" in tags:
                for index in range(1, len(self._focus_handlers)):
                    if f"btn_{index - 1}" in tags:
                        return index
        return None

    def _on_canvas_press(self, event: tk.Event) -> str | None:
        self._pressed_control = self._control_at(event)
        if self._pressed_control is not None:
            return "break"
        self._on_drag_begin(event)
        return None

    def _on_canvas_release(self, event: tk.Event) -> str | None:
        pressed, self._pressed_control = self._pressed_control, None
        self._on_drag_end(event)
        if pressed is None:
            return None
        if pressed == self._control_at(event):
            if pressed == 0:
                self.close()
            else:
                self._click_control(pressed)
        return "break"

    def _on_drag_begin(self, event: tk.Event) -> None:
        if not self._closed and self._in_emblem(event):
            self._emblem_press = (event.x_root, event.y_root)
            self._drag_offset = None
            return
        if self._closed or event.y > self._s(48) or event.x >= self.w - self._s(44):
            return
        self._drag_offset = (event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y())

    def _on_drag_move(self, event: tk.Event) -> None:
        if self._emblem_press is not None:
            x, y = self._emblem_press
            if max(abs(event.x_root - x), abs(event.y_root - y)) > self._s(5):
                self._emblem_press = None
                self._emblem_clicks.clear()
            return
        if self._closed or self._drag_offset is None:
            return
        nx = event.x_root - self._drag_offset[0]
        ny = event.y_root - self._drag_offset[1]
        work = self._desktop.work_area_for_point(event.x_root, event.y_root)
        cx, cy = work.clamp(nx, ny, self.w, self.h)
        self._win_pos = (cx, cy)
        self.win.geometry(f"{self.w}x{self.h}+{max(0, cx)}+{max(0, cy)}")
        try:
            self.win.update_idletasks()
            frame = self.win.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.win.winfo_id())
            if not self._desktop.position_without_activation(hwnd, cx, cy) and cx >= 0 and cy >= 0:
                self.win.geometry(f"+{cx}+{cy}")
        except Exception:
            pass

    def _on_drag_end(self, event: tk.Event) -> None:
        self._drag_offset = None
        press, self._emblem_press = self._emblem_press, None
        if press is not None and self._in_emblem(event):
            dx, dy = event.x_root - press[0], event.y_root - press[1]
            if max(abs(dx), abs(dy)) <= self._s(5):
                self._record_emblem_click()
                return
        self._emblem_clicks.clear()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._cancel_playback()
        self._load_generation += 1
        if self._upload_id is not None:
            try:
                self.win.after_cancel(self._upload_id)
            except tk.TclError:
                pass
            self._upload_id = None
        self._frame_source = ()
        self._photos.clear()
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        cb, self.on_close = self.on_close, None
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
