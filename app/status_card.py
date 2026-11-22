"""status_card.py — Dedicated High-Texture Glassmorphism Apink Status Card (狀態面板).

Upgraded with:
- Glassmorphism layered card aesthetics with member-specific palette themes
- Living avatar animation: smoothly cycles idle frames right inside the profile frame
- Gamified friendship & cheer passion level progression
- Enhanced time formatting (hours + minutes) with persistent accumulation
- Favorite food indicators & fullness state
- Smooth window dragging and edge-clamped positioning
- 100% full tri-lingual i18n support (zh_TW, ko, en)
"""
from __future__ import annotations

import re
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Callable, Optional
from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.paths import resource_dir
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, scale_canvas, ui_scale
from app.resource_store import open_resource_image, resource_exists, resource_store

BG_TRANSPARENT = "#ff00fe"
ROOT = resource_dir()

# ── Member-Specific Palette & Personality Themes ──────────────────────────────
MEMBER_THEMES = {
    "chorong": {
        "primary": "#d81b60",
        "soft_bg": "#fff9fb",
        "header_fill": "#fce4ec",
        "border": "#f8bbd0",
        "glow": "#f48fb1",
        "accent": "#ad1457",
        "pill_fill": "#fdeef3",
        "icon": "🌸",
        "badge_border": "#f48fb1",
        "bar_fill": "#ec407a",
        "fav_food": {
            "zh_TW": "濃郁抹茶 🍵 / 招牌雞爪 🐾 / 現烤麵包 🍞",
            "ko": "진한 말차 🍵 / 쫄깃 닭발 🐾 / 갓 구운 빵 🍞",
            "en": "Rich Matcha 🍵 / Chicken Feet 🐾 / Fresh Bread 🍞",
        },
    },
    "bomi": {
        "primary": "#b83b00",
        "soft_bg": "#fffaf5",
        "header_fill": "#ffeede",
        "border": "#ffd2b8",
        "glow": "#ffa060",
        "accent": "#8c2800",
        "pill_fill": "#fff3e0",
        "icon": "🍊",
        "badge_border": "#ffb74d",
        "bar_fill": "#c43e00",
        "fav_food": {
            "zh_TW": "韓式部隊鍋 🍲 / 辣炒年糕 🍢 / 韓式炸醬麵 🍜",
            "ko": "한식 부대찌개 🍲 / 매콤 떡볶이 🍢 / 감칠맛 짜장면 🍜",
            "en": "Korean Army Stew 🍲 / Spicy Tteokbokki 🍢 / Jajangmyeon 🍜",
        },
    },
    "eunji": {
        "primary": "#0277bd",
        "soft_bg": "#f4faff",
        "header_fill": "#e6f3fc",
        "border": "#c0e0f8",
        "glow": "#5cb4e6",
        "accent": "#01579b",
        "pill_fill": "#e1f5fe",
        "icon": "🌊",
        "badge_border": "#81d4fa",
        "bar_fill": "#039be5",
        "fav_food": {
            "zh_TW": "營養烤雞蛋 🥚 / 烤五花肉 🥩 / 香辣雞爪 🐾",
            "ko": "구운 달걀 🥚 / 노릇 삼겹살 🥩 / 매운 닭발 🐾",
            "en": "Sauna Baked Egg 🥚 / Pork Belly 🥩 / Spicy Chicken Feet 🐾",
        },
    },
    "namjoo": {
        "primary": "#6a1b9a",
        "soft_bg": "#faf6ff",
        "header_fill": "#f3e5f5",
        "border": "#dfc0f8",
        "glow": "#b388ff",
        "accent": "#4a148c",
        "pill_fill": "#ede1f6",
        "icon": "🍇",
        "badge_border": "#ce93d8",
        "bar_fill": "#8e24aa",
        "fav_food": {
            "zh_TW": "香辣雞爪 🐾 / 辣炒年糕 🍢 / 泡菜豬肉 🥩",
            "ko": "매운 닭발 🐾 / 쫄깃 떡볶이 🍢 / 김치제육 🥩",
            "en": "Spicy Chicken Feet 🐾 / Tteokbokki 🍢 / Kimchi Pork 🥩",
        },
    },
    "hayoung": {
        "primary": "#9a5200",
        "soft_bg": "#fffdf5",
        "header_fill": "#fff7d6",
        "border": "#ffe48a",
        "glow": "#f5b432",
        "accent": "#78350f",
        "pill_fill": "#fff9c4",
        "icon": "🍯",
        "badge_border": "#fdd835",
        "bar_fill": "#a15800",
        "fav_food": {
            "zh_TW": "現烤地瓜 🍠 / 現烤麵包 🍞 / 辣炒年糕 🍢",
            "ko": "달콤 군고구마 🍠 / 갓 구운 빵 🍞 / 매콤달콤 떡볶이 🍢",
            "en": "Roasted Sweet Potato 🍠 / Fresh Bread 🍞 / Spicy Tteokbokki 🍢",
        },
    },
}


def get_passion_tier(passion: int, lang: str = "zh_TW") -> tuple[int, str]:
    """Calculate cheer passion friendship tier and title."""
    if passion < 100:
        tiers = {
            "zh_TW": "Lv.1 萌新粉熊 🐾",
            "ko": "Lv.1 새싹 판다 🐾",
            "en": "Lv.1 Baby Panda 🐾",
        }
        return 1, tiers.get(lang, tiers["zh_TW"])
    elif passion < 300:
        tiers = {
            "zh_TW": "Lv.2 狂熱應援 💖",
            "ko": "Lv.2 열정 응원 💖",
            "en": "Lv.2 Passionate Panda 💖",
        }
        return 2, tiers.get(lang, tiers["zh_TW"])
    elif passion < 600:
        tiers = {
            "zh_TW": "Lv.3 靈魂摯友 🔥",
            "ko": "Lv.3 소울메이트 🔥",
            "en": "Lv.3 Soulmate Panda 🔥",
        }
        return 3, tiers.get(lang, tiers["zh_TW"])
    elif passion < 1000:
        tiers = {
            "zh_TW": "Lv.4 傳奇粉熊 👑",
            "ko": "Lv.4 전설의 판다 👑",
            "en": "Lv.4 Legend Panda 👑",
        }
        return 4, tiers.get(lang, tiers["zh_TW"])
    tiers = {
        "zh_TW": "Lv.5 本命守護神 🌟",
        "ko": "Lv.5 최애 수호신 🌟",
        "en": "Lv.5 Ultimate Guardian 🌟",
    }
    return 5, tiers.get(lang, tiers["zh_TW"])


BADGE_TIERS = ((8, 12, 6), (7, 8, 4))      # (pt, pill padding, gap) tried in order
BADGE_ROW_STEP = 28                         # design px between wrapped badge rows
_STATUS_AVATAR_PIL_CACHE: dict[tuple[str, int], tuple[Image.Image, ...]] = {}


def clean_badge_text(text: str) -> str:
    """Drop variation selectors / ZWJ that leave huge GDI gaps; single space after the icon."""
    text = text.replace("️", "").replace("‍♀", "").replace("‍", "").strip()
    return re.sub(r"^(\S+)\s+", r"\1 ", text)


def layout_badge_pills(
    texts: list[str],
    measure: Callable[[str, int], int],
    x0: int,
    x_max: int,
    tiers: tuple[tuple[int, int, int], ...],
    min_w: int,
) -> tuple[int, list[tuple[int, int, int, str]]]:
    """Fit every pill on one row, shrinking font and padding first; wrap rather than drop.

    ``measure(text, pt)`` returns design px. Returns ``(pt, [(x, row, width, text), ...])``.
    """
    avail = x_max - x0
    for pt, pad, gap in tiers:
        widths = [max(min_w, measure(t, pt) + pad) for t in texts]
        if sum(widths) + gap * (len(widths) - 1) <= avail:
            break
    pills: list[tuple[int, int, int, str]] = []
    x, row = x0, 0
    for text, tw in zip(texts, widths):
        if x > x0 and x + tw > x_max:
            x, row = x0, row + 1
        if tw > avail:   # one pill wider than a whole row: shorten its text
            while len(text) > 1 and measure(text + "…", pt) + pad > avail:
                text = text[:-1]
            text, tw = text.rstrip() + "…", avail
        pills.append((x, row, tw, text))
        x += tw + gap
    return pt, pills


def format_companion_duration(total_minutes: int, lang: str = "zh_TW") -> str:
    """Format minutes into days/hours/minutes."""
    if total_minutes < 60:
        if lang == "ko":
            return f"{total_minutes} 분"
        elif lang == "en":
            return f"{total_minutes} mins"
        return f"{total_minutes} 分鐘"

    hours = total_minutes // 60
    rem_min = total_minutes % 60
    if hours < 24:
        if lang == "ko":
            return f"{hours}시간 {rem_min}분"
        elif lang == "en":
            return f"{hours}h {rem_min}m"
        return f"{hours} 小時 {rem_min} 分"

    days = hours // 24
    rem_hours = hours % 24
    if lang == "ko":
        return f"{days}일 {rem_hours}시간"
    elif lang == "en":
        return f"{days}d {rem_hours}h"
    return f"{days} 天 {rem_hours} 小時"


class PandaStatusCard:
    """High-texture glassmorphism Apink Status Card with living animated avatar."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        char_key: str = "chorong",
        char_name: str = "初瓏 (Chorong)",
        badge_desc: str = "🌸 溫暖隊長 ｜ 🥋 合氣道三段 ｜ 🐱 貓咪控",
        passion_points: int = 0,
        companion_start_time: float = 0.0,
        feed_count: int = 0,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        lang: str = "zh_TW",
        total_companion_seconds: int | None = None,
        satiety: float = 100.0,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.char_key = char_key
        self.char_name = char_name
        self.badge_desc = badge_desc
        self.passion_points = passion_points
        self.companion_start_time = companion_start_time
        self.total_companion_seconds = total_companion_seconds
        self.feed_count = feed_count
        self.satiety = max(0.0, min(100.0, float(satiety)))
        self.lang = lang
        self.on_close = on_close

        # Geometry
        self._design_w, self._design_h = 470, 400
        self.drag_offset_x: int | None = None
        self.drag_offset_y: int | None = None

        # Animated avatar state
        self.avatar_frames: list[ImageTk.PhotoImage] = []
        self.avatar_step = 0
        self.avatar_item: int | None = None
        self._avatar_timer: str | None = None
        self._fonts: dict[tuple[int, str], tkfont.Font] = {}
        self._desktop = WindowsDesktopAdapter(fallback_bounds=lambda: WorkArea(
            0, 0, max(1, self.window.winfo_screenwidth()), max(1, self.window.winfo_screenheight())))

        # Build window
        self.window = tk.Toplevel(parent)
        try:
            if parent and hasattr(parent, "state") and parent.state() != "withdrawn":
                self.window.transient(parent)
        except Exception:
            pass
        self.window.title(f"Apink Panda Status - {char_name}")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.resizable(False, False)
        self.window.configure(bg=BG_TRANSPARENT)
        try:
            self.window.attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.ui_scale = ui_scale(self.window)
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)

        self.canvas = tk.Canvas(
            self.window,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Smooth drag event handling
        self.canvas.bind("<ButtonPress-1>", self.on_drag_begin)
        self.canvas.bind("<B1-Motion>", self.on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        # Smart placement next to the pet
        self._position_window(anchor_x, anchor_y)

        # Pre-load avatar frames
        self._load_avatar_sequence(char_key)
        self.avatar_thumb = self.avatar_frames[0] if self.avatar_frames else None

        # Render complete aesthetic card
        self._render_card()

        # Start living avatar loop
        self._tick_avatar()

        try:
            self.window.deiconify()
            self.window.lift()
        except Exception:
            pass

    def _position_window(self, anchor_x: int | None, anchor_y: int | None) -> None:
        if anchor_x is not None and anchor_y is not None:
            work = self._desktop.work_area_for_point(anchor_x, anchor_y)
            gap = round(13 * self.ui_scale)
            target_x = anchor_x + round(205 * self.ui_scale)
            if target_x + self.w > work.right - gap:
                target_x = anchor_x - self.w - gap
            target_y = anchor_y - round(30 * self.ui_scale)
            cx, cy = work.clamp(target_x, target_y, self.w, self.h)
            self.window.geometry(f"{self.w}x{self.h}+{max(0, cx)}+{max(0, cy)}")
            try:
                self.window.update_idletasks()
                frame = self.window.wm_frame()
                hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.window.winfo_id())
                self._desktop.position_without_activation(hwnd, cx, cy)
            except Exception:
                pass
        else:
            try:
                px = self.window.master.winfo_rootx() + max(1, self.window.master.winfo_width()) // 2
                py = self.window.master.winfo_rooty() + max(1, self.window.master.winfo_height()) // 2
            except Exception:
                px, py = 600, 300
            work = self._desktop.work_area_for_point(px, py)
            cx, cy = work.clamp(
                (work.left + work.right - self.w) // 2,
                (work.top + work.bottom - self.h) // 2,
                self.w,
                self.h,
            )
            self.window.geometry(f"{self.w}x{self.h}+{max(0, cx)}+{max(0, cy)}")
            try:
                self.window.update_idletasks()
                frame = self.window.wm_frame()
                hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.window.winfo_id())
                self._desktop.position_without_activation(hwnd, cx, cy)
            except Exception:
                pass

    def _fit_window_height(self, design_h: int) -> None:
        """Grow or shrink the window in place when the content height changes."""
        new_h = round(design_h * self.ui_scale)
        if new_h == self.h:
            return
        self.h = new_h
        self.canvas.config(height=new_h)
        self.window.geometry(f"{self.w}x{new_h}")

    def _font(self, pt: int, weight: str = "bold") -> tkfont.Font:
        key = (pt, weight)
        f = self._fonts.get(key)
        if f is None:
            f = tkfont.Font(root=self.window, family="Microsoft JhengHei", size=pt, weight=weight)
            self._fonts[key] = f
        return f

    def _load_avatar_sequence(self, char_key: str) -> None:
        """Loads and crops the 4-frame idle sequence into cleanly resized avatar thumbnails."""
        self.avatar_frames = []
        px = max(16, round(76 * self.ui_scale))
        cache_key = (char_key, px)
        cached_pils = _STATUS_AVATAR_PIL_CACHE.get(cache_key)
        if cached_pils is None:
            char_dir = ROOT / "work" / "characters" / char_key
            fallback_dir = ROOT / "work" / "characters" / "chorong"
            pils: list[Image.Image] = []
            with resource_store().session():
                for idx in range(1, 5):
                    img_path = char_dir / f"idle_0{idx}.png"
                    if not resource_exists(img_path):
                        img_path = fallback_dir / f"idle_0{idx}.png"
                    if not resource_exists(img_path):
                        img_path = char_dir / "idle_01.png"

                    try:
                        with open_resource_image(img_path) as raw:
                            im = raw.convert("RGBA")
                        bbox = im.getbbox()
                        if bbox:
                            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                            if bh > 80:
                                cx = (bbox[0] + bbox[2]) // 2
                                top = max(0, bbox[1] - 4)
                                side = max(bw + 6, int(bh * 0.72))
                                left = max(0, cx - side // 2)
                                right = min(im.width, left + side)
                                bottom = min(im.height, top + side)
                                im = im.crop((left, top, right, bottom))
                        pils.append(im.resize((px, px), Image.Resampling.LANCZOS))
                    except Exception:
                        pils.append(Image.new("RGBA", (px, px), (255, 255, 255, 0)))
            if not pils:
                pils.append(Image.new("RGBA", (px, px), (255, 255, 255, 0)))
            cached_pils = tuple(pils)
            _STATUS_AVATAR_PIL_CACHE[cache_key] = cached_pils

        for pil_im in cached_pils:
            try:
                self.avatar_frames.append(ImageTk.PhotoImage(pil_im, master=self.window))
            except Exception:
                pass
        if not self.avatar_frames:
            blank = Image.new("RGBA", (px, px), (255, 255, 255, 0))
            self.avatar_frames.append(ImageTk.PhotoImage(blank, master=self.window))

    def _tick_avatar(self) -> None:
        """Living avatar animation: gently cycles frames every 280ms."""
        if not self.window.winfo_exists():
            return
        if self.avatar_frames and self.avatar_item is not None:
            self.avatar_step = (self.avatar_step + 1) % len(self.avatar_frames)
            try:
                self.canvas.itemconfigure(self.avatar_item, image=self.avatar_frames[self.avatar_step])
            except Exception:
                pass
        self._avatar_timer = self.window.after(280, self._tick_avatar)

    def refresh(
        self,
        char_key: str,
        char_name: str,
        badge_desc: str,
        passion_points: int,
        companion_start_time: float,
        feed_count: int,
        lang: str = "zh_TW",
        total_companion_seconds: int | None = None,
        satiety: float | None = None,
    ) -> None:
        """Dynamically re-renders the card contents without changing its window position."""
        old_char = self.char_key
        self.char_key = char_key
        self.char_name = char_name
        self.badge_desc = badge_desc
        self.passion_points = passion_points
        self.companion_start_time = companion_start_time
        if total_companion_seconds is not None:
            self.total_companion_seconds = total_companion_seconds
        if satiety is not None:
            self.satiety = max(0.0, min(100.0, float(satiety)))
        self.feed_count = feed_count
        self.lang = lang

        if old_char != char_key:
            self._load_avatar_sequence(char_key)

        self._render_card()

    def _render_card(self) -> None:
        self.canvas.delete("all")
        w = self._design_w
        k = self.ui_scale
        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])

        # Member traits are laid out first: a wrapped second row pushes everything below it down.
        traits = [t.strip() for t in self.badge_desc.replace("｜", "|").split("|") if t.strip()]

        def measure_badge(text: str, pt: int) -> int:
            return round(self._font(pt, "bold").measure(text) / k)

        badge_pt, pills = layout_badge_pills(
            [clean_badge_text(t) for t in traits], measure_badge, 116, w - 16, BADGE_TIERS, 48)
        dy = BADGE_ROW_STEP * max((row for _x, row, _w, _t in pills), default=0)
        h = self._design_h + dy
        self._fit_window_height(h)

        # Font definitions with reliable cross-platform metrics
        f_header = self._font(11, "bold")
        f_name = self._font(14, "bold")
        f_tier = self._font(9, "bold")
        f_label = self._font(8, "bold")

        # 1. Outer Glow Glass Border (Simulated soft shadow)
        _draw_round_rect(
            self.canvas,
            4, 4, w - 4, h - 4,
            r=24,
            fill="#ffffff",
            outline=theme["glow"],
            width=2,
        )

        # 2. Main Frosted Glass Card Body
        _draw_round_rect(
            self.canvas,
            8, 8, w - 8, h - 8,
            r=20,
            fill=theme["soft_bg"],
            outline=theme["border"],
            width=1,
        )

        # 3. Header Glossy Banner
        _draw_round_rect(
            self.canvas,
            10, 10, w - 10, 50,
            r=18,
            fill=theme["header_fill"],
            outline=theme["border"],
            width=1,
        )

        header_title = {
            "zh_TW": f"{theme['icon']} Apink 熊貓狀態面板",
            "ko": f"{theme['icon']} 에이핑크 판다 상태 패널",
            "en": f"{theme['icon']} Apink Panda Status Card",
        }.get(self.lang, f"{theme['icon']} Apink 熊貓狀態面板")

        self.canvas.create_text(
            26, 30,
            anchor="w",
            text=header_title,
            fill=theme["primary"],
            font=f_header,
        )

        # Close button with soft circular pill
        close_btn = self.canvas.create_text(
            w - 26, 30,
            text="✕",
            fill=theme["primary"],
            font=("Segoe UI", 12, "bold"),
            tags=("close_btn",),
        )
        self.canvas.tag_bind(close_btn, "<Button-1>", lambda _: self.close())

        # 4. Avatar Profile Section
        # Glowing double-ring frame (88x88)
        _draw_round_rect(
            self.canvas,
            18, 62, 106, 150,
            r=16,
            fill="#ffffff",
            outline=theme["glow"],
            width=2,
        )

        # 76x76 animated living avatar thumbnail centered at (62, 106)
        first_frame = self.avatar_frames[0] if self.avatar_frames else None
        if first_frame:
            self.avatar_item = self.canvas.create_image(62, 106, image=first_frame)

        # Member Name + Icon
        self.canvas.create_text(
            116, 75,
            anchor="w",
            text=self.char_name,
            fill="#2c1d27",
            font=f_name,
        )

        # Member Traits: dynamic rounded pills, never silently dropped
        for px, row, tw, clean_trait in pills:
            py = 94 + row * BADGE_ROW_STEP
            _draw_round_rect(
                self.canvas,
                px, py, px + tw, py + 22,
                r=6,
                fill=theme["pill_fill"],
                outline=theme["badge_border"],
                width=1,
                tags=("badge_pill",),
            )
            self.canvas.create_text(
                px + tw // 2, py + 11,
                text=clean_trait,
                fill=theme["accent"],
                font=("Microsoft JhengHei", badge_pt, "bold"),
                tags=("badge_text",),
            )

        # Tier Pill with dynamic font-measured width matching text exactly
        lvl, tier_title = get_passion_tier(self.passion_points, lang=self.lang)
        tier_label = {
            "zh_TW": f"應援等級: {tier_title}",
            "ko": f"응원 등급: {tier_title}",
            "en": f"Cheer Tier: {tier_title}",
        }.get(self.lang, f"應援等級: {tier_title}")

        font_tier = self._font(9, "bold")
        tier_w = max(160, round(font_tier.measure(tier_label) / k) + 20)
        _draw_round_rect(
            self.canvas,
            116, 124 + dy, 116 + tier_w, 148 + dy,
            r=8,
            fill="#ffffff",
            outline=theme["border"],
            width=1.5,
        )
        self.canvas.create_text(
            116 + tier_w // 2, 136 + dy,
            text=tier_label,
            fill=theme["primary"],
            font=f_tier,
        )

        # 5. Status Satiety & Energy Bar (Split Layout: Title Left, State Right)
        energy_title = {
            "zh_TW": "🥣 飽腹元氣與親密度",
            "ko": "🥣 포만도 & 기분 활력",
            "en": "🥣 Fullness & Mood Energy",
        }.get(self.lang, "🥣 飽腹元氣與親密度")

        # Dynamic Satiety calculation
        fullness_pct = max(0, min(100, int(round(self.satiety))))
        if fullness_pct >= 80:
            energy_state = {
                "zh_TW": f"{fullness_pct}% 滿足元氣 🌟",
                "ko": f"{fullness_pct}% 활력 만점 🌟",
                "en": f"{fullness_pct}% Full Energy 🌟",
            }.get(self.lang, f"{fullness_pct}% 滿足元氣 🌟")
            bar_color = theme["bar_fill"]
        elif fullness_pct >= 30:
            energy_state = {
                "zh_TW": f"{fullness_pct}% 肚子還不餓 😊",
                "ko": f"{fullness_pct}% 아직 배 안 고파요 😊",
                "en": f"{fullness_pct}% Not hungry yet 😊",
            }.get(self.lang, f"{fullness_pct}% 肚子還不餓 😊")
            bar_color = theme["bar_fill"]
        elif fullness_pct >= 10:
            energy_state = {
                "zh_TW": f"{fullness_pct}% 肚子咕嚕嚕 🥺",
                "ko": f"{fullness_pct}% 배에서 꼬르륵 🥺",
                "en": f"{fullness_pct}% Hungry Aegyo 🥺",
            }.get(self.lang, f"{fullness_pct}% 肚子咕嚕嚕 🥺")
            bar_color = "#b45309"
        else:
            energy_state = {
                "zh_TW": f"{fullness_pct}% 沒力氣討食中 🥀",
                "ko": f"{fullness_pct}% 배고파서 기절 🥀",
                "en": f"{fullness_pct}% Starving Aegyo 🥀",
            }.get(self.lang, f"{fullness_pct}% 沒力氣討食中 🥀")
            bar_color = "#c62828"

        self.canvas.create_text(
            22, 166 + dy,
            anchor="w",
            text=energy_title,
            fill="#372733",
            font=("Microsoft JhengHei", 9, "bold"),
        )
        self.canvas.create_text(
            w - 22, 166 + dy,
            anchor="e",
            text=energy_state,
            fill=bar_color if fullness_pct < 30 else theme["primary"],
            font=("Microsoft JhengHei", 9, "bold"),
        )

        # Progress Bar track
        _draw_round_rect(self.canvas, 20, 180 + dy, w - 20, 194 + dy, r=6, fill="#f0edf5", outline="#e2dceb", width=1)
        # Progress Bar fill (clamped to at least 6px if > 0 so rounded corners look aesthetic)
        if fullness_pct > 0:
            bar_w = max(6, int((w - 40) * (fullness_pct / 100.0)))
            _draw_round_rect(self.canvas, 20, 180 + dy, 20 + bar_w, 194 + dy, r=6, fill=bar_color, outline=theme["glow"], width=1)

        # 6. Visual 2x2 Glass Pods (Spacious, Polish, High-Contrast)
        if self.total_companion_seconds is not None:
            minutes = max(1, self.total_companion_seconds // 60)
        else:
            minutes = max(1, int((time.time() - self.companion_start_time) / 60))

        formatted_time = format_companion_duration(minutes, lang=self.lang)
        fav_food_name = theme["fav_food"].get(self.lang, theme["fav_food"]["zh_TW"])

        if self.lang == "ko":
            s1_title, s1_val = "응원 열기", f"{self.passion_points:,} P"
            s2_title, s2_val = "간식 횟수", f"{self.feed_count} 회"
            s3_title, s3_val = "함께한 시간", formatted_time
            s4_title, s4_val = "최애 간식", fav_food_name
        elif self.lang == "en":
            s1_title, s1_val = "Cheer Heat", f"{self.passion_points:,} pts"
            s2_title, s2_val = "Feed Count", f"{self.feed_count} times"
            s3_title, s3_val = "Companion Time", formatted_time
            s4_title, s4_val = "Favorite Snack", fav_food_name
        else:
            s1_title, s1_val = "應援熱度", f"{self.passion_points:,} 熱度值"
            s2_title, s2_val = "餵食總計", f"{self.feed_count} 次"
            s3_title, s3_val = "累計陪伴", formatted_time
            s4_title, s4_val = "本命最愛", fav_food_name

        stat_cards = [
            (0, 0, "🔥", s1_title, s1_val, theme["primary"]),
            (1, 0, "🍱", s2_title, s2_val, "#6a1b9a"),
            (0, 1, "⏰", s3_title, s3_val, "#00796b"),
            (1, 1, "⭐", s4_title, s4_val, theme["accent"]),
        ]

        card_w = (w - 40 - 14) // 2  # 208px
        card_h = 80
        x_offsets = [20, 20 + card_w + 14]
        y_offsets = [210 + dy, 298 + dy]

        pending_values: list[tuple[int, int, int, int, int, str, str]] = []
        for col, row, icon, title, val, text_color in stat_cards:
            x1 = x_offsets[col]
            y1 = y_offsets[row]
            x2 = x1 + card_w
            y2 = y1 + card_h

            # Soft white card with delicate member border
            _draw_round_rect(
                self.canvas,
                x1, y1, x2, y2,
                r=12,
                fill="#ffffff",
                outline=theme["border"],
                width=1.5,
            )

            # Icon + Title
            title_item = self.canvas.create_text(
                x1 + 14, y1 + 19,
                anchor="w",
                text=f"{icon} {title}",
                fill="#616161",
                font=f_label,
            )
            pending_values.append((x1, y1, x2, y2, title_item, val, text_color))

        scale_canvas(self.canvas, k)

        val_font_check = self._font(10, "bold")
        for x1, y1, x2, y2, _title_item, val, text_color in pending_values:
            sx1, sy1 = x1 * k, y1 * k

            # Prominent Value with fast cached font-metric fitting
            clean_val = val.replace("\ufe0f", "").strip()
            max_val_w = round((card_w - 24) * k)
            display_val = clean_val
            if " / " in clean_val and val_font_check.measure(clean_val) > max_val_w:
                parts = [p.strip() for p in clean_val.split(" / ") if p.strip()]
                if len(parts) == 3:
                    line1 = f"{parts[0]} / {parts[1]}"
                    if val_font_check.measure(line1) <= max_val_w:
                        display_val = f"{line1}\n{parts[2]}"
                    else:
                        display_val = f"{parts[0]}\n{parts[1]} / {parts[2]}"

            lines = display_val.splitlines() or [display_val]
            chosen_font = self._font(8, "bold")
            for sz in (10, 9, 8):
                f_cand = self._font(sz, "bold")
                if all(f_cand.measure(ln) <= max_val_w for ln in lines):
                    chosen_font = f_cand
                    break
            self.canvas.create_text(
                sx1 + 14 * k, sy1 + 52 * k,
                anchor="w",
                text=display_val,
                fill=text_color,
                font=chosen_font,
                width=max_val_w,
            )

    def on_drag_begin(self, event: tk.Event) -> None:
        try:
            self.window.lift()
        except Exception:
            pass
        current_tags = self.canvas.gettags("current")
        if "close_btn" in current_tags:
            return
        self.drag_offset_x = event.x_root - self.window.winfo_x()
        self.drag_offset_y = event.y_root - self.window.winfo_y()

    def on_drag_move(self, event: tk.Event) -> None:
        if self.drag_offset_x is not None and self.drag_offset_y is not None:
            x = event.x_root - self.drag_offset_x
            y = event.y_root - self.drag_offset_y
            work = self._desktop.work_area_for_point(event.x_root, event.y_root)
            cx, cy = work.clamp(x, y, self.w, self.h)
            self.window.geometry(f"+{cx}+{cy}")

    def on_drag_end(self, event: tk.Event) -> None:
        self.drag_offset_x = None
        self.drag_offset_y = None

    def close(self) -> None:
        if self._avatar_timer is not None:
            try:
                self.window.after_cancel(self._avatar_timer)
            except Exception:
                pass
            self._avatar_timer = None
        try:
            self.window.destroy()
        except Exception:
            pass
        self.avatar_frames.clear()
        self.avatar_thumb = None
        if hasattr(self, "on_close") and self.on_close and callable(self.on_close):
            try:
                self.on_close()
            except Exception:
                pass
