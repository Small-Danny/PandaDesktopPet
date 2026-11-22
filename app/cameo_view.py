"""cameo_view.py — Transparent Tk window for one cameo guest.

Pure view: ``CameoDirector`` (engine/cameo.py) decides phase / position /
action / opacity; this window only draws that state. One window per actor so
guests can move independently of the host pet.
"""
from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from app.engine.cameo import CameoFrame
from app.platform.layered_surface import LayeredSpriteSurface
from app.platform.win32 import WindowsDesktopAdapter, WorkArea
from app.sprites import MemberSprites

log = logging.getLogger(__name__)

BG = "#ff00fe"
FRAME_MS = {"idle": 180, "walk": 100, "cheer": 135, "sleep": 220}
CHEER_SEQ = (0, 1, 2, 3, 2, 1)


def _should_use_ulw(use_layered: bool | None, win: object, sprites: object) -> bool:
    if use_layered is False:
        return False
    if not isinstance(tk.Toplevel, type) or not isinstance(win, tk.Toplevel):
        return False
    if not callable(getattr(sprites, "get_pil", None)):
        return False
    if use_layered is True:
        return sys.platform == "win32"
    if sys.platform != "win32":
        return False
    raw = os.environ.get("PANDA_DISABLE_ULW", "").strip().lower()
    return raw not in ("1", "true", "yes", "on")


class CameoActorWindow:
    def __init__(
        self,
        parent: tk.Misc,
        sprites: MemberSprites,
        on_click: Optional[Callable[[], None]] = None,
        on_double_click: Optional[Callable[[], None]] = None,
        *,
        desktop: WindowsDesktopAdapter | None = None,
        use_layered: bool | None = None,
    ) -> None:
        self.sprites = sprites
        self.on_click = on_click
        self.on_double_click = on_double_click
        self.desktop = desktop
        self.last_x, self.last_y = 0.0, 0.0
        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)
        self._use_ulw = _should_use_ulw(use_layered, self.win, sprites)
        self.surface: LayeredSpriteSurface | None = None
        if self._use_ulw:
            try:
                self.surface = LayeredSpriteSurface(
                    self.win,
                    x=0,
                    y=0,
                    opacity=1.0,
                    input_policy="interactive",
                    noactivate=True,
                    topmost=True,
                )
            except Exception:
                log.exception("CameoActorWindow ULW init failed; falling back to ColorKey")
                self._use_ulw = False
                self.surface = None
        if not self._use_ulw:
            try:
                self.win.attributes("-transparentcolor", BG)
            except tk.TclError:
                pass
        # Under ULW, read dimensions from PIL so LazyPhotoList never allocates unused Tk PhotoImages.
        pil_idle = (
            sprites.get_pil("idle", 1)
            if self._use_ulw and callable(getattr(sprites, "get_pil", None))
            else []
        )
        if pil_idle:
            self.w, self.h = pil_idle[0].size
        else:
            first = sprites.frames["idle"][0]
            self.w, self.h = first.width(), first.height()
        self.canvas = tk.Canvas(self.win, width=self.w, height=self.h, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.image = self.canvas.create_image(0, 0, anchor="nw")
        bind_target = self.win if self._use_ulw else self.canvas
        bind_target.bind("<Button-1>", self._handle_click)
        bind_target.bind("<Double-Button-1>", self._handle_double_click)
        self._shown = False
        self._alpha = 1.0
        self._photo = None
        self._geometry = None
        self._image_xy = (0, 0)
        self._walk_pose = None
        self._ulw_content_key: tuple[int, tuple[int, int, int, int]] | None = None
        self._ulw_pos: tuple[int, int] | None = None

    def _handle_click(self, event: tk.Event) -> None:
        if self.on_click:
            self.on_click()

    def _handle_double_click(self, event: tk.Event) -> None:
        if self.on_double_click:
            self.on_double_click()

    def render(self, frame: CameoFrame, now_ms: float, work_area: WorkArea | None = None) -> None:
        surf = getattr(self, "surface", None)
        use_ulw = surf is not None and not surf.closed
        pil_frames = (
            self.sprites.get_pil(frame.action, frame.facing)
            if use_ulw and callable(getattr(self.sprites, "get_pil", None))
            else []
        )
        if frame.action == "walk":
            cadence = FRAME_MS["walk"]
        else:
            cadence = self.sprites.frame_ms(frame.action, frame.facing, FRAME_MS.get(frame.action, 150))
        step = int(now_ms // cadence)
        dx, dy = self.sprites.offset(frame.action, frame.facing)
        photo = None
        pil_im = None
        if use_ulw and pil_frames:
            if frame.action == "cheer":
                idx = CHEER_SEQ[step % len(CHEER_SEQ)] % len(pil_frames)
            else:
                idx = step % len(pil_frames)
            pil_im = pil_frames[idx]
            frame_id = id(pil_im)
            fw, fh = pil_im.size
        else:
            frames = self.sprites.get(frame.action, frame.facing)
            if frame.action == "cheer":
                idx = CHEER_SEQ[step % len(CHEER_SEQ)] % len(frames)
            else:
                idx = step % len(frames)
            photo = frames[idx]
            frame_id = id(photo)
            fw, fh = photo.width(), photo.height()
        walk_pose = (getattr(frame, "phase", None), frame.facing, frame_id) if frame.action == "walk" else None
        if walk_pose is None or walk_pose != getattr(self, "_walk_pose", None):
            # Keep the displayed position with the foot pose, including while
            # clipped out. Phase changes still land exactly at their endpoints.
            self.last_x, self.last_y = frame.x, frame.y
        self._walk_pose = walk_pose
        x, y = int(self.last_x + dx), int(self.last_y + dy)
        left, top, right, bottom = x, y, x + fw, y + fh
        if work_area is not None:
            left, top = max(left, work_area.left), max(top, work_area.top)
            right, bottom = min(right, work_area.right), min(bottom, work_area.bottom)
        if right <= left or bottom <= top:
            if self._shown:
                if surf is not None and not surf.closed:
                    surf.set_visibility(False)
                self.win.withdraw()
                self._shown = False
            return
        old_w, old_h = getattr(self, "w", 0), getattr(self, "h", 0)
        self.w, self.h = right - left, bottom - top
        grew = (not use_ulw) and self._shown and (self.w > old_w or self.h > old_h)
        if grew:
            try:
                self.win.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
        image_xy = (x - left, y - top)
        if image_xy != getattr(self, "_image_xy", None):
            self.canvas.coords(self.image, *image_xy)
            self._image_xy = image_xy
        if not use_ulw and photo is not self._photo:
            self.canvas.itemconfigure(self.image, image=photo)
            self._photo = photo
        geometry = f"{self.w}x{self.h}+{left}+{top}"
        geometry_changed = geometry != self._geometry
        if geometry_changed:
            self.win.geometry(geometry)
            self._geometry = geometry
        alpha = round(max(0.0, min(1.0, frame.alpha)), 2)
        alpha_changed = alpha != self._alpha
        if use_ulw:
            if pil_im is None:
                pil_im = ImageTk.getimage(photo)
            crop_box = (left - x, top - y, right - x, bottom - y)
            content_key = (id(pil_im), crop_box)
            content_changed = content_key != getattr(self, "_ulw_content_key", None)
            pos_changed = (left, top) != getattr(self, "_ulw_pos", None)
            if not self._shown or content_changed:
                cropped_im = pil_im if crop_box == (0, 0, fw, fh) else pil_im.crop(crop_box)
                surf.present(cropped_im, x=left, y=top, opacity=alpha)
                self._ulw_content_key = content_key
                self._ulw_pos = (left, top)
                self._alpha = alpha
            else:
                if pos_changed:
                    surf.move(left, top)
                    self._ulw_pos = (left, top)
                if alpha_changed:
                    surf.set_opacity(alpha)
                    self._alpha = alpha
            if not self._shown:
                self._shown = True
                self.win.update_idletasks()
                self.win.deiconify()
                surf.set_visibility(True, reorder=False)
                if self.desktop is not None:
                    try:
                        self.desktop.set_noactivate(surf.hwnd)
                    except (tk.TclError, ValueError, OSError):
                        pass
            elif geometry_changed:
                self.win.update_idletasks()
            return
        if not self._shown:
            self._shown = True
            self._alpha = alpha
            try:
                self.win.attributes("-alpha", 0.0)
            except tk.TclError:
                pass
            self.win.update_idletasks()
            self.win.deiconify()
            if self.desktop is not None:
                try:
                    frame_id = self.win.wm_frame()
                    hwnd = int(frame_id, 0) if frame_id else self.win.winfo_id()
                    self.desktop.set_noactivate(hwnd)
                except (tk.TclError, ValueError):
                    pass
            self.win.attributes("-topmost", True)
            self.win.update_idletasks()
            try:
                self.win.attributes("-alpha", alpha)
            except tk.TclError:
                pass
        else:
            if grew or geometry_changed:
                self.win.update_idletasks()
            if alpha_changed or grew:
                self._alpha = alpha
                try:
                    self.win.attributes("-alpha", alpha)
                except tk.TclError:
                    pass

    def destroy(self) -> None:
        surf = getattr(self, "surface", None)
        self.surface = None
        if surf is not None:
            try:
                surf.close()
            except Exception:
                pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
