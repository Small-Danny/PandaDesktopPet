"""birthday_dialog.py — "Set my birthday" dialog so the pandas can celebrate the user.

Stored in settings as ``user_birthday`` ("MM-DD", "" = unset) and
``user_nickname``; main.py passes them to ``CalendarScheduler.set_user_birthday``.
Styled as a borderless rounded pink card consistent with ``status_card.py``.
"""
from __future__ import annotations

import calendar
import tkinter as tk
from typing import Callable, Optional

from app.bubble import _draw_round_rect
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, scale_canvas, ui_scale
from app.status_card import MEMBER_THEMES

NICKNAME_MAX = 12
DEFAULT_NICKNAME = "粉熊"
BG_TRANSPARENT = "#ff00fe"

TEXT = {
    "zh_TW": {
        "title": "設定我的生日", "intro": "告訴熊貓們你的生日，當天大家會一起幫你慶生！",
        "month": "月", "day": "日", "nickname": "專屬暱稱", "save": "儲存設定",
        "clear": "清除生日", "cancel": "取消", "invalid": "日期不正確，請重新確認月份與日期。",
    },
    "ko": {
        "title": "내 생일 설정", "intro": "생일을 알려주면 판다들이 함께 축하해 줄 거예요!",
        "month": "월", "day": "일", "nickname": "닉네임", "save": "저장",
        "clear": "생일 삭제", "cancel": "취소", "invalid": "날짜가 올바르지 않아요. 월과 일을 확인해 주세요.",
    },
    "en": {
        "title": "Set My Birthday", "intro": "Tell the pandas your birthday and they'll celebrate with you!",
        "month": "Month", "day": "Day", "nickname": "Nickname", "save": "Save",
        "clear": "Clear", "cancel": "Cancel", "invalid": "That date isn't valid. Please check month and day.",
    },
}


def _font_family(lang: str) -> str:
    if lang == "ko":
        return "Malgun Gothic"
    if lang == "en":
        return "Segoe UI"
    return "Microsoft JhengHei"


def parse_birthday(month: str, day: str) -> tuple[int, int]:
    """Validate a month/day pair; Feb 29 is allowed (leap-year birthdays)."""
    m, d = int(str(month).strip()), int(str(day).strip())
    if not 1 <= m <= 12:
        raise ValueError("month out of range")
    if not 1 <= d <= calendar.monthrange(2024, m)[1]:  # 2024 is a leap year
        raise ValueError("day out of range")
    return m, d


def format_birthday(month: Optional[int], day: Optional[int]) -> str:
    return f"{month:02d}-{day:02d}" if month and day else ""


def read_birthday(value: object) -> Optional[tuple[int, int]]:
    """Settings value "MM-DD" -> (month, day); anything else -> None."""
    if not isinstance(value, str) or "-" not in value:
        return None
    try:
        return parse_birthday(*value.split("-", 1))
    except ValueError:
        return None


def clean_nickname(value: str) -> str:
    return (value or "").strip()[:NICKNAME_MAX] or DEFAULT_NICKNAME


class BirthdayDialog:
    """Borderless rounded pink card dialog; ``on_save(month, day, nickname)`` with None/None = cleared."""

    def __init__(
        self,
        parent: tk.Misc,
        current: Optional[tuple[int, int]],
        nickname: str,
        on_save: Callable[[Optional[int], Optional[int], str], None],
        lang: str = "zh_TW",
        member_key: str = "chorong",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.on_close = on_close
        self.current = current
        self.nickname_val = nickname
        self.on_save = on_save
        self.lang = lang
        self.member_key = member_key
        self.theme = MEMBER_THEMES.get(member_key, MEMBER_THEMES["chorong"])
        self.tx = TEXT.get(lang, TEXT["zh_TW"])
        self._design_w, self._design_h = 420, 290
        self.drag_offset_x: Optional[int] = None
        self.drag_offset_y: Optional[int] = None
        self._pressed_tag: Optional[str] = None
        self._button_actions: dict[str, Callable[[], None]] = {}

        self.win = tk.Toplevel(parent)
        self._desktop = WindowsDesktopAdapter(
            fallback_bounds=lambda: WorkArea(
                0, 0, max(640, int(self.win.winfo_screenwidth())), max(480, int(self.win.winfo_screenheight()))
            )
        )
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
        self.ui_scale = ui_scale(self.win)
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)

        self.canvas = tk.Canvas(
            self.win,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_drag_begin)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        self.win.bind("<Return>", lambda _e: self.save())
        self.win.bind("<Escape>", lambda _e: self.close())
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._render_dialog(current=current, nickname=nickname)

        self.win.update_idletasks()
        try:
            px = int(self.parent.winfo_rootx()) + max(1, int(self.parent.winfo_width())) // 2
            py = int(self.parent.winfo_rooty()) + max(1, int(self.parent.winfo_height())) // 2
        except Exception:
            px, py = 600, 300
        work = self._desktop.work_area_for_point(px, py)
        cx, cy = work.clamp(
            work.left + (work.width - self.w) // 2,
            work.top + (work.height - self.h) // 3,
            self.w,
            self.h,
        )
        self._move_window(cx, cy)
        self.win.deiconify()
        self.win.lift()
        if hasattr(self, "month") and self.month:
            self.month.focus_set()

    def _move_window(self, x: int, y: int) -> None:
        self.last_clamped_pos = (int(x), int(y))
        self.win.geometry(f"{self.w}x{self.h}+{max(0, int(x))}+{max(0, int(y))}")
        try:
            self.win.update_idletasks()
            frame = self.win.wm_frame()
            hwnd = (int(frame, 16) if frame.startswith("0x") else int(frame)) if frame else int(self.win.winfo_id())
            if not self._desktop.position_without_activation(hwnd, int(x), int(y)) and x >= 0 and y >= 0:
                self.win.geometry(f"{self.w}x{self.h}+{int(x)}+{int(y)}")
        except Exception:
            pass

    def _render_dialog(
        self, current: Optional[tuple[int, int]], nickname: str, err_text: str = ""
    ) -> None:
        """Render or re-render dialog content according to self.theme and self.tx."""
        # 1. Clean up old widgets if re-rendering
        for attr in ("month", "day", "nickname", "error"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
        self.canvas.delete("all")
        self._button_actions = {"close_btn": self.close}

        theme = self.theme
        tx = self.tx
        w, h = self._design_w, self._design_h
        fam = _font_family(self.lang)
        f_header = (fam, 11, "bold")
        f_intro = (fam, 9, "bold")
        f_label = (fam, 9, "bold")
        f_input = (fam, 10, "bold")
        f_btn = (fam, 9, "bold")
        f_err = (fam, 9)

        # 1. Outer Rounded Card matching member theme in status_card.py
        _draw_round_rect(
            self.canvas, 6, 6, w - 6, h - 6,
            r=22, fill=theme["soft_bg"], outline=theme["border"], width=2,
        )

        # 2. Header Banner
        _draw_round_rect(
            self.canvas, 8, 8, w - 8, 48,
            r=18, fill=theme["header_fill"], outline=theme["glow"], width=1,
        )

        # Vector Birthday Cake Icon (avoids Windows Tk emoji tofu boxes)
        self.canvas.create_rectangle(22, 27, 40, 38, fill=theme["border"], outline=theme["accent"], width=1.5)
        self.canvas.create_rectangle(23, 27, 39, 31, fill="#fff6de", outline="")
        self.canvas.create_line(31, 19, 31, 27, fill=theme["primary"], width=2)
        self.canvas.create_oval(29, 14, 33, 19, fill="#ffb300", outline="")

        self.canvas.create_text(
            48, 28, anchor="w", text=tx["title"], fill=theme["accent"], font=f_header,
        )

        self.canvas.create_oval(
            w - 40, 16, w - 16, 40, fill=theme["border"], outline="", tags=("close_btn",),
        )
        self.canvas.create_text(
            w - 28, 28, text="✕", fill=theme["accent"], font=("Segoe UI", 10, "bold"), tags=("close_btn",),
        )

        # 3. Intro Subtitle
        self.canvas.create_text(
            26, 68, anchor="w", text=tx["intro"], fill=theme["accent"], font=f_intro, width=w - 52,
        )

        # 4. Date Row inside Soft Inner Panel
        _draw_round_rect(
            self.canvas, 22, 92, w - 22, 198,
            r=14, fill=theme["pill_fill"], outline=theme["border"], width=1,
        )

        m0, d0 = current if current else (1, 1)

        # Month pill + Spinbox
        _draw_round_rect(
            self.canvas, 36, 104, 128, 138,
            r=10, fill="#ffffff", outline=theme["glow"], width=1.5,
        )
        self.month = tk.Spinbox(
            self.win, from_=1, to=12, width=4, font=f_input, justify="center",
            relief="flat", bd=0, highlightthickness=0, bg="#ffffff", fg="#4a2538",
            buttonbackground=theme["header_fill"],
        )
        self.month.delete(0, "end")
        self.month.insert(0, str(m0))
        self.canvas.create_window(82, 121, window=self.month, width=72, height=24)
        self.canvas.create_text(136, 121, anchor="w", text=tx["month"], fill=theme["accent"], font=f_label)

        # Day pill + Spinbox
        _draw_round_rect(
            self.canvas, 192, 104, 284, 138,
            r=10, fill="#ffffff", outline=theme["glow"], width=1.5,
        )
        self.day = tk.Spinbox(
            self.win, from_=1, to=31, width=4, font=f_input, justify="center",
            relief="flat", bd=0, highlightthickness=0, bg="#ffffff", fg="#4a2538",
            buttonbackground=theme["header_fill"],
        )
        self.day.delete(0, "end")
        self.day.insert(0, str(d0))
        self.canvas.create_window(238, 121, window=self.day, width=72, height=24)
        self.canvas.create_text(292, 121, anchor="w", text=tx["day"], fill=theme["accent"], font=f_label)

        # 5. Nickname Row
        self.canvas.create_text(38, 168, anchor="w", text=tx["nickname"], fill=theme["accent"], font=f_label)
        _draw_round_rect(
            self.canvas, 118, 151, w - 36, 185,
            r=10, fill="#ffffff", outline=theme["glow"], width=1.5,
        )
        self.nickname = tk.Entry(
            self.win, width=18, font=f_input, relief="flat", bd=0,
            highlightthickness=0, bg="#ffffff", fg="#4a2538", insertbackground=theme["accent"],
        )
        self.nickname.insert(0, nickname or DEFAULT_NICKNAME)
        self.canvas.create_window(
            128, 168, anchor="w", window=self.nickname, width=w - 176, height=24,
        )

        # 6. Error Label
        self.error = tk.Label(
            self.win, text=err_text, bg=theme["soft_bg"], fg="#d81b60", font=f_err, anchor="w",
        )
        self.canvas.create_window(26, 214, anchor="w", window=self.error, width=w - 52, height=22)

        # 7. Rounded Pill Action Buttons
        btn_y1, btn_y2 = 238, 272
        # Save button (rightmost)
        self._make_pill_button(
            w - 116, btn_y1, w - 22, btn_y2,
            text=tx["save"], fill=theme["bar_fill"], outline=theme["primary"], fg="#ffffff",
            font=f_btn, command=self.save, tag="btn_save",
        )
        # Cancel button
        self._make_pill_button(
            w - 206, btn_y1, w - 124, btn_y2,
            text=tx["cancel"], fill=theme["header_fill"], outline=theme["border"], fg=theme["accent"],
            font=f_btn, command=self.close, tag="btn_cancel",
        )
        # Clear button (if birthday was set or configured)
        if self.current or current:
            self._make_pill_button(
                22, btn_y1, 116, btn_y2,
                text=tx["clear"], fill=theme["pill_fill"], outline=theme["glow"], fg=theme["accent"],
                font=f_btn, command=self.clear, tag="btn_clear",
            )
        scale_canvas(self.canvas, self.ui_scale)

    def refresh_theme(self, member_key: str, lang: Optional[str] = None) -> None:
        """Dynamically re-renders the dialog theme preserving user-entered inputs."""
        cur_m = self.month.get() if hasattr(self, "month") and self.month else "1"
        cur_d = self.day.get() if hasattr(self, "day") and self.day else "1"
        cur_nick = self.nickname.get() if hasattr(self, "nickname") and self.nickname else DEFAULT_NICKNAME
        cur_err = self.error.cget("text") if hasattr(self, "error") and self.error else ""

        self.member_key = member_key
        self.theme = MEMBER_THEMES.get(member_key, MEMBER_THEMES["chorong"])
        if lang is not None:
            self.lang = lang
        self.tx = TEXT.get(self.lang, TEXT["zh_TW"])
        self.win.title(self.tx["title"])

        try:
            m_val = int(str(cur_m).strip())
            d_val = int(str(cur_d).strip())
            cur_tuple = (m_val, d_val)
        except ValueError:
            cur_tuple = self.current

        self._render_dialog(current=cur_tuple, nickname=cur_nick, err_text=cur_err)
        try:
            self.win.lift()
        except Exception:
            pass

    def _make_pill_button(
        self,
        x1: int, y1: int, x2: int, y2: int,
        text: str, fill: str, outline: str, fg: str,
        font: tuple, command: Callable[[], None], tag: str,
    ) -> None:
        _draw_round_rect(
            self.canvas, x1, y1, x2, y2,
            r=12, fill=fill, outline=outline, width=1.5, tags=(tag,),
        )
        self.canvas.create_text(
            (x1 + x2) // 2, (y1 + y2) // 2,
            text=text, fill=fg, font=font, tags=(tag,),
        )
        self._button_actions[tag] = command

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
                if t in self._button_actions:
                    return t
        for t in self.canvas.gettags("current"):
            if t in self._button_actions:
                return t
        return None

    def _on_drag_begin(self, event: tk.Event) -> None:
        try:
            self.win.lift()
        except Exception:
            pass
        hit = self._interactive_tag_at(event)
        if hit is not None:
            self._pressed_tag = hit
            self.drag_offset_x = None
            self.drag_offset_y = None
            return
        self._pressed_tag = None
        x_root = getattr(event, "x_root", getattr(event, "x", 0) + self.win.winfo_x())
        y_root = getattr(event, "y_root", getattr(event, "y", 0) + self.win.winfo_y())
        self.drag_offset_x = x_root - self.win.winfo_x()
        self.drag_offset_y = y_root - self.win.winfo_y()

    def _on_drag_move(self, event: tk.Event) -> None:
        if self.drag_offset_x is not None and self.drag_offset_y is not None:
            x_root = getattr(event, "x_root", getattr(event, "x", 0) + self.win.winfo_x())
            y_root = getattr(event, "y_root", getattr(event, "y", 0) + self.win.winfo_y())
            nx = x_root - self.drag_offset_x
            ny = y_root - self.drag_offset_y
            work = self._desktop.work_area_for_point(x_root, y_root)
            cx, cy = work.clamp(nx, ny, self.w, self.h)
            self._move_window(cx, cy)

    def _on_drag_end(self, event: tk.Event) -> None:
        self.drag_offset_x = None
        self.drag_offset_y = None
        pressed, self._pressed_tag = self._pressed_tag, None
        if pressed is not None and pressed == self._interactive_tag_at(event):
            action = self._button_actions.get(pressed)
            if action is not None:
                action()

    def save(self) -> None:
        try:
            m, d = parse_birthday(self.month.get(), self.day.get())
        except ValueError:
            self.error.configure(text=self.tx["invalid"])
            return
        nickname = clean_nickname(self.nickname.get())
        self.close()
        self.on_save(m, d, nickname)

    def clear(self) -> None:
        nickname = clean_nickname(self.nickname.get())
        self.close()
        self.on_save(None, None, nickname)

    def close(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self._button_actions.clear()
        callback, self.on_close = self.on_close, None       # at most once, however it was closed
        if callback:
            callback()
