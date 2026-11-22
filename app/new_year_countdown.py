"""new_year_countdown.py — The big clock that counts down the last seconds of the year."""
from __future__ import annotations

import time
import tkinter as tk
from typing import Callable

from app.bubble import _draw_round_rect
from app.platform.win32 import scale_canvas, ui_scale

BG = "#ff00fe"
WIDTH, HEIGHT = 220, 112
GAP = 10                # px between the clock and the pet's head
TICK_MS = 100
TITLES = {"zh_TW": "✦ 跨年倒數", "ko": "✦ 새해 카운트다운", "en": "✦ New Year Countdown"}


class NewYearCountdown:
    def __init__(self, parent: tk.Misc, seconds: int, pet_box: tuple[int, int, int, int],
                 area: tuple[int, int, int, int], lang: str, on_done: Callable[[], None]) -> None:
        self.parent = parent
        self.seconds = seconds
        self.on_done = on_done
        self._after: str | None = None
        self._t0 = time.monotonic()
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)
        try:
            self.win.attributes("-transparentcolor", BG)
        except tk.TclError:
            pass
        self.ui_scale = ui_scale(self.win)
        k = self.ui_scale
        w, h, gap = round(WIDTH * k), round(HEIGHT * k), round(GAP * k)
        self.width, self.height = w, h
        pet_x, pet_y, pet_w, _pet_h = pet_box
        left, top, right, bottom = area
        x = max(left, min(pet_x + (pet_w - w) // 2, right - w))
        y = max(top, min(pet_y - h - gap, bottom - h))
        canvas = tk.Canvas(self.win, width=w, height=h, bg=BG, highlightthickness=0)
        canvas.pack()
        _draw_round_rect(canvas, 3, 3, WIDTH - 3, HEIGHT - 3, r=22, fill="#fff0f6", outline="#ec407a", width=3)
        canvas.create_text(WIDTH // 2, 24, text=TITLES.get(lang, TITLES["zh_TW"]), fill="#ad1457",
                           font=("Microsoft JhengHei UI", 11, "bold"))
        self.canvas = canvas
        self.digits = canvas.create_text(WIDTH // 2, 70, text=str(seconds), fill="#d81b60",
                                         font=("Segoe UI", 38, "bold"))
        scale_canvas(canvas, k)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self._tick()

    def remaining(self) -> int:
        """Whole seconds still to show (rounded up, so the clock reads N for the first second)."""
        left = self.seconds - (time.monotonic() - self._t0)
        return max(0, int(left) + (left > int(left)))

    def _tick(self) -> None:
        left = self.remaining()
        if left <= 0:
            self._after = None
            self._destroy()
            self.on_done()
            return
        self.canvas.itemconfigure(self.digits, text=str(left))
        self._after = self.parent.after(TICK_MS, self._tick)

    def cancel(self) -> None:
        """Close without celebrating."""
        if self._after is not None:
            try:
                self.parent.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None
        self._destroy()

    def _destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
