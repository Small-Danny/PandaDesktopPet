"""anniversary_scene.py — The 419 group photo: five pandas around the cake, a visitor drops by.

0-2 s the photo loops; at 2 s the visitor slides in from the right; 2.2-3.2 s everyone
turns to greet her; afterwards the photo loops on and she keeps waving beside it.
"""
from __future__ import annotations

import logging
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageOps, ImageTk

from app.action_frames import load_exact_action
from app.platform.layered_surface import LayeredSpriteSurface
from app.resource_store import open_resource_image
from app.sprite_polish import alpha_bleed, defringe_light_frame, purify_white
from app.sprites import SpriteLibrary

log = logging.getLogger(__name__)

BG = "#ff00fe"
HEIGHT_FACTOR = 1.7        # photo height, in pet heights
FRAME_MS = 240
TICK_MS = 40
VISITOR_AT = 2.0
SLIDE_S = 0.5
SURPRISE = (2.2, 3.2)
LOOP_FILES = ("loop_1.png", "loop_2.png", "loop_3.png", "loop_4.png")
SURPRISE_FILE = "surprise.png"
VISITOR_ACTION = "secret_clover_visitor"
VISITOR_SCALE = 0.72       # about the size of the pandas in the photo


def photo_index(elapsed_s: float) -> int:
    """Index into loop + surprise frames (the surprise frame is the last one)."""
    if SURPRISE[0] <= elapsed_s < SURPRISE[1]:
        return len(LOOP_FILES)
    return int(elapsed_s * 1000 // FRAME_MS) % len(LOOP_FILES)


def _should_use_ulw(use_layered: bool | None) -> bool:
    if use_layered is not None:
        return bool(use_layered) and sys.platform == "win32"
    if sys.platform != "win32":
        return False
    raw = os.environ.get("PANDA_DISABLE_ULW", "").strip().lower()
    return raw not in ("1", "true", "yes", "on")


class AnniversaryScene:
    def __init__(self, parent: tk.Misc, library: SpriteLibrary, scene_dir: Path,
                 pet_box: tuple[int, int, int, int], area: tuple[int, int, int, int],
                 duration_ms: int = 9000, on_done: Optional[Callable[[], None]] = None,
                 *, use_layered: bool | None = None) -> None:
        self.parent, self.on_done = parent, on_done
        self._use_ulw = _should_use_ulw(use_layered)
        target_binary = not self._use_ulw
        if isinstance(library, SpriteLibrary) and bool(getattr(library, "binary_alpha", True)) != target_binary:
            library = library.with_binary_alpha(target_binary)
        self._after: Optional[str] = None
        self._end: Optional[str] = None
        self.surface: LayeredSpriteSurface | None = None
        self.vis_surface: LayeredSpriteSurface | None = None
        self._shown_idx: int | None = None
        self._vis_shown_idx: int | None = None
        pet_x, pet_y, pet_w, pet_h = pet_box
        left, top, right, bottom = area
        height = round(pet_h * HEIGHT_FACTOR)
        self.pil_frames = [self._load_pil(scene_dir / name, height, binary_alpha=target_binary)
                           for name in (*LOOP_FILES, SURPRISE_FILE)]
        self.frames = []
        for im in self.pil_frames:
            photo = ImageTk.PhotoImage(im, master=parent)
            photo._pil_image = im  # type: ignore[attr-defined]
            self.frames.append(photo)
        w, h = self.frames[0].width(), self.frames[0].height()
        loaded = load_exact_action(library, None, VISITOR_ACTION, scale_member="chorong")
        self.visitor_pil = (
            [self._visitor_frame(im, binary_alpha=target_binary) for im in loaded.frames]
            if loaded else []
        )
        self.visitor = []
        for im in self.visitor_pil:
            photo = ImageTk.PhotoImage(im, master=parent)
            photo._pil_image = im  # type: ignore[attr-defined]
            self.visitor.append(photo)
        vw = self.visitor[0].width() if self.visitor else 0
        vh = self.visitor[0].height() if self.visitor else 0
        self.x = max(left, min(pet_x + (pet_w - w) // 2, right - w - vw))
        self.y = max(top, min(pet_y + pet_h - h, bottom - h))
        self.win, self.canvas, self.surface = self._make_window(
            w, h, self.x, self.y, initial_pil=self.pil_frames[0], visible=True,
        )
        self.item = self.canvas.create_image(0, 0, anchor="nw", image=self.frames[0])
        self._shown_idx = 0
        self.vis_win = self.vis_canvas = self.vis_item = None
        if self.visitor:
            self.vis_rest = self.x + w - vw // 5
            self.vis_y = self.y + h - vh
            self.vis_start = min(right, self.vis_rest + vw)
            self.vis_win, self.vis_canvas, self.vis_surface = self._make_window(
                vw, vh, self.vis_start, self.vis_y, initial_pil=self.visitor_pil[0], visible=False,
            )
            self.vis_item = self.vis_canvas.create_image(0, 0, anchor="nw", image=self.visitor[0])
            self._vis_shown_idx = 0
        self._t0 = time.monotonic()
        self._tick()
        self._end = parent.after(duration_ms, self.close)

    @staticmethod
    def _visitor_frame(image: Image.Image, *, binary_alpha: bool = False) -> Image.Image:
        """Smaller, and mirrored so she looks at the group on her left."""
        target_w, target_h = round(image.width * VISITOR_SCALE), round(image.height * VISITOR_SCALE)
        small = alpha_bleed(image).resize((target_w, target_h), Image.Resampling.LANCZOS)
        if binary_alpha:
            small.putalpha(small.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
            small = purify_white(defringe_light_frame(small))
        return ImageOps.mirror(small)

    @staticmethod
    def _load_pil(path: Path, height: int, *, binary_alpha: bool = False) -> Image.Image:
        with open_resource_image(path) as src:
            im = alpha_bleed(src.convert("RGBA"))
        im = im.resize((round(im.width * height / im.height), height), Image.Resampling.LANCZOS)
        if binary_alpha:
            im.putalpha(im.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
            im = purify_white(defringe_light_frame(im))
        return im

    def _load(self, path: Path, height: int) -> tk.PhotoImage:
        im = self._load_pil(path, height, binary_alpha=not getattr(self, "_use_ulw", False))
        photo = ImageTk.PhotoImage(im, master=self.parent)
        photo._pil_image = im  # type: ignore[attr-defined]
        return photo

    def _make_window(
        self,
        w: int,
        h: int,
        x: int,
        y: int,
        *,
        initial_pil: Image.Image | None = None,
        visible: bool = True,
    ) -> tuple[tk.Toplevel, tk.Canvas, LayeredSpriteSurface | None]:
        win = tk.Toplevel(self.parent)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)
        surf: LayeredSpriteSurface | None = None
        if self._use_ulw and isinstance(tk.Toplevel, type) and isinstance(win, tk.Toplevel):
            try:
                surf = LayeredSpriteSurface(
                    win,
                    x=x,
                    y=y,
                    opacity=1.0,
                    input_policy="interactive",
                    noactivate=True,
                    topmost=True,
                )
            except Exception:
                log.exception("AnniversaryScene ULW init failed; falling back to ColorKey")
                surf = None
        if surf is None:
            try:
                win.attributes("-transparentcolor", BG)
            except tk.TclError:
                pass
        canvas = tk.Canvas(win, width=w, height=h, bg=BG, highlightthickness=0)
        canvas.pack()
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.update_idletasks()
        if surf is not None and initial_pil is not None:
            surf.present(initial_pil, x=x, y=y, opacity=1.0)
        if visible:
            win.deiconify()
            if surf is not None:
                surf.set_visibility(True, reorder=False)
        return win, canvas, surf

    def _window(self, w: int, h: int, x: int, y: int) -> tuple[tk.Toplevel, tk.Canvas]:
        win, canvas, _surf = self._make_window(w, h, x, y, visible=True)
        return win, canvas

    def _tick(self) -> None:
        t = time.monotonic() - self._t0
        idx = photo_index(t)
        if idx != self._shown_idx:
            self._shown_idx = idx
            self.canvas.itemconfigure(self.item, image=self.frames[idx])
            if self.surface is not None and not self.surface.closed:
                self.surface.present(self.pil_frames[idx], x=self.x, y=self.y)
        if self.vis_win is not None and t >= VISITOR_AT:
            p = min(1.0, (t - VISITOR_AT) / SLIDE_S)
            x = round(self.vis_start + (self.vis_rest - self.vis_start) * p)
            shown = 0 if p < 1.0 else (2 + int(t * 1000 // 400) % 2) % len(self.visitor)   # clover, wave
            self.vis_win.geometry(f"+{x}+{self.vis_y}")
            self.vis_canvas.itemconfigure(self.vis_item, image=self.visitor[shown])
            if self.vis_surface is not None and not self.vis_surface.closed:
                if shown != self._vis_shown_idx:
                    self._vis_shown_idx = shown
                    self.vis_surface.present(self.visitor_pil[shown], x=x, y=self.vis_y)
                else:
                    self.vis_surface.move(x, self.vis_y)
            if self.vis_win.state() == "withdrawn":
                self.vis_win.deiconify()
                if self.vis_surface is not None and not self.vis_surface.closed:
                    self.vis_surface.set_visibility(True, reorder=False)
        self._after = self.parent.after(TICK_MS, self._tick)

    @property
    def visitor_shown(self) -> bool:
        return self.vis_win is not None and self.vis_win.state() != "withdrawn"

    def close(self) -> None:
        for after_id in (self._after, self._end):
            if after_id is not None:
                try:
                    self.parent.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._after = self._end = None
        for surf_attr in ("vis_surface", "surface"):
            surf = getattr(self, surf_attr, None)
            setattr(self, surf_attr, None)
            if surf is not None:
                try:
                    surf.close()
                except Exception:
                    pass
        windows = [w for w in (self.vis_win, self.win) if w is not None]
        self.vis_win = None
        for win in windows:
            try:
                win.destroy()
            except tk.TclError:
                pass
        done, self.on_done = self.on_done, None
        if done is not None:
            done()
