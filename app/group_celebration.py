"""group_celebration.py — The other four members join the pet for a birthday / anniversary.

Each guest gets a small transparent topmost window standing on the pet's feet line,
two on each side when there is room (otherwise all on the side that has room). A
guest plays her approved ``special_birthday`` animation, or her base cheer. The
windows are view-only and close themselves after ``duration_ms``.

A large pet on a narrow or high-DPI screen leaves too little room for four wide
festival canvases; ``roster_layout`` then rebalances the sides, tightens the gap
and finally shrinks every guest evenly, so all five members stay on stage.
"""
from __future__ import annotations

import logging
import os
import sys
import time
import tkinter as tk
from collections import OrderedDict
from typing import Callable, Optional, Sequence

from PIL import Image, ImageTk

from app.action_frames import load_exact_action
from app.platform.layered_surface import LayeredSpriteSurface
from app.sprite_polish import alpha_bleed, polish_frame
from app.sprites import ALPHA_THRESHOLD, SpriteLibrary

log = logging.getLogger(__name__)

BG = "#ff00fe"
CHEER_MS = 135
CHEER_SEQ = (0, 1, 2, 3, 2, 1)
SPACING = 0.85          # guests stand this many pet widths apart
TICK_MS = 45            # redraw period; each guest picks her frame from elapsed time
FALLBACK_GAPS = (12, 8, 4, 0)
MIN_GUEST_SCALE = 0.4   # below this a guest would be unrecognisable; omit her instead
SYNC_BUDGET_S = 0.06    # guests not ready within this load one per Tk turn
PHOTO_CACHE_ENTRIES = 24
# 2026-11-22: count-only, four entries were already ~18 MB (Tk photo + its PIL frame each).
PHOTO_CACHE_BYTES = 12 * 1024 * 1024


def _photo_cache_bytes(entry) -> int:
    photos = entry[0]
    total = 0
    for photo in photos:
        im = getattr(photo, "_pil_image", None)
        if im is not None:
            total += im.width * im.height * 4 * 2     # PIL frame + the Tk photo's own copy
    return total


def guest_slots(pet_x: int, width: int, area_left: int, area_right: int, count: int) -> list[int]:
    """Left x of each guest: nearest free slots alternating left/right, inside the area."""
    step = max(1, round(width * SPACING))
    slots: list[int] = []
    for n in range(1, 4 * count + 1):
        for x in (pet_x - n * step, pet_x + n * step):
            if area_left <= x and x + width <= area_right and len(slots) < count:
                slots.append(x)
        if len(slots) == count:
            break
    return sorted(slots)


def guest_frame_slots(host_bounds: tuple[int, int], area: tuple[int, int],
                      extents: Sequence[tuple[int, int]], gap: int = 12) -> list[int | None]:
    """Base origins for variable canvases; reserve the host's expanded rectangle.

    Never crop or squeeze art to create room. A guest that cannot fit is omitted.
    """
    left, right = host_bounds
    slots: list[int | None] = []
    for dx, fw in extents:
        candidates = ((left - gap - fw, "left"), (right + gap, "right"))
        candidates = sorted(candidates, key=lambda v: abs(v[0] + fw / 2 - sum(host_bounds) / 2))
        placed = None
        for x, side in candidates:
            if area[0] <= x and x + fw <= area[1]:
                placed = x - dx
                if side == "left":
                    left = x
                else:
                    right = x + fw
                break
        slots.append(placed)
    return slots


def _side_layout(host_bounds: tuple[int, int], area: tuple[int, int],
                 widths: Sequence[int], gap: int) -> list[int] | None:
    """Canvas lefts with each guest left or right of the host, or None if no split fits.

    Every left/right split is tried (four guests: 16) and the most even one wins, so the
    group stays centred on the host instead of leaving the greedy pass's fragments.
    """
    left, right = host_bounds
    room_left, room_right = max(0, left - area[0]), max(0, area[1] - right)
    n, best = len(widths), None
    for mask in range(1 << n):
        need_left = sum(widths[i] + gap for i in range(n) if mask >> i & 1)
        need_right = sum(widths[i] + gap for i in range(n) if not mask >> i & 1)
        if need_left <= room_left and need_right <= room_right:
            score = abs(need_left - need_right)
            if best is None or score < best[0]:
                best = (score, mask)
    if best is None:
        return None
    lefts: list[int] = []
    edge_left, edge_right = left, right
    for i, w in enumerate(widths):
        if best[1] >> i & 1:
            edge_left -= gap + w
            lefts.append(edge_left)
        else:
            lefts.append(edge_right + gap)
            edge_right += gap + w
    return lefts


def roster_layout(host_bounds: tuple[int, int], area: tuple[int, int],
                  extents: Sequence[tuple[int, int]]) -> tuple[list[int | None], float]:
    """(base origins, guest scale) that keep every guest on stage whenever possible.

    The usual 12 px greedy slots are kept when they hold everyone. Otherwise the sides
    are rebalanced and the gap tightened; if the art still cannot fit, every guest is
    shrunk by one common factor (never cropped). A scaled guest's canvas left is
    ``origin + dx`` with her unscaled ``dx``.
    """
    slots = guest_frame_slots(host_bounds, area, extents)
    if None not in slots:
        return slots, 1.0
    widths = [fw for _dx, fw in extents]
    for gap in FALLBACK_GAPS:
        lefts = _side_layout(host_bounds, area, widths, gap)
        if lefts is not None:
            return [x - dx for x, (dx, _fw) in zip(lefts, extents)], 1.0
    lo, hi, found = MIN_GUEST_SCALE, 1.0, None
    for _ in range(14):
        mid = (lo + hi) / 2
        lefts = _side_layout(host_bounds, area, [max(1, round(w * mid)) for w in widths], 4)
        if lefts is None:
            hi = mid
        else:
            lo, found = mid, (lefts, mid)
    if found is not None:
        lefts, scale = found
        return [x - dx for x, (dx, _fw) in zip(lefts, extents)], scale
    return slots, 1.0


def scale_sprite_frame(src_im: Image.Image, scale: float, library, *, default_binary: bool = True) -> Image.Image:
    """One display frame shrunk by ``scale`` with the library's alpha/polish rules.

    Shared by the guests and (2026-11-22) the host: when a narrow screen shrinks the
    guests, the host is shrunk by the same factor so all five stand the same size.
    """
    polish = bool(getattr(library, "polish", True))
    raw_bin = getattr(library, "binary_alpha", default_binary)
    binary_alpha = raw_bin if isinstance(raw_bin, bool) else default_binary
    edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
    raw_px = getattr(library, "display_px", 192)
    base_px = raw_px if isinstance(raw_px, (int, float)) and not isinstance(raw_px, bool) else 192
    target_px = max(48, round(base_px * scale))
    im = alpha_bleed(src_im, alpha_threshold=200 if edge_refine else 1)
    size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    im = im.resize(size, Image.LANCZOS)
    if binary_alpha:
        im.putalpha(im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0))
        if polish:
            im = polish_frame(im, target_px, binary_alpha=True)
    return im


def _should_use_ulw(use_layered: bool | None) -> bool:
    if use_layered is not None:
        return bool(use_layered) and sys.platform == "win32"
    if sys.platform != "win32":
        return False
    raw = os.environ.get("PANDA_DISABLE_ULW", "").strip().lower()
    return raw not in ("1", "true", "yes", "on")


class GroupCelebration:
    def __init__(
        self,
        parent: tk.Misc,
        library: SpriteLibrary,
        guests: Sequence[str | None],
        pet_box: tuple[int, int, int, int],
        area: tuple[int, int],
        action: str | Callable[[str], str] = "special_birthday",
        duration_ms: int = 8000,
        on_done: Optional[Callable[[], None]] = None,
        visitor_action: Optional[str] = None,
        host_bounds: tuple[int, int] | None = None,
        photo_cache: Optional[OrderedDict] = None,
        on_placed: Optional[Callable[["GroupCelebration"], None]] = None,
        stagger: bool = False,
        *,
        use_layered: bool | None = None,
    ) -> None:
        self.parent = parent
        self._use_ulw = _should_use_ulw(use_layered)
        target_binary = not self._use_ulw
        self.library = (
            library.with_binary_alpha(target_binary)
            if isinstance(library, SpriteLibrary) and bool(getattr(library, "binary_alpha", True)) != target_binary
            else library
        )
        self.visitor_action = visitor_action     # a None guest is this shared easter-egg visitor
        self.scale_member = next((g for g in guests if g), None)
        self.on_done = on_done
        self.on_placed = on_placed
        self.photo_cache = photo_cache           # shared between parties: a repeat skips decoding
        self.windows: list[tuple[tk.Toplevel, tk.Canvas, int, list[tk.PhotoImage], float, bool]] = []
        self.surfaces: dict[tk.Toplevel, LayeredSpriteSurface] = {}
        self._canvas_surfaces: dict[tk.Canvas, LayeredSpriteSurface] = {}
        self.omitted: list[str | None] = []
        self.guest_scale = 1.0
        self._after: Optional[str] = None
        self._end: Optional[str] = None
        self._load: Optional[str] = None
        self._closed = False
        self._t0 = time.monotonic()
        self._shown_photos = {}
        self._pet_box = pet_box
        self._area = area
        self._host_bounds = host_bounds or (pet_box[0], pet_box[0] + pet_box[2])
        self._pending = [(member, action(member) if callable(action) and member else action)
                         for member in guests]
        self._prepared: list[tuple] = []
        self._end = parent.after(duration_ms, self.close)
        # Cached guests appear at once. A cold guest costs ~100 ms of decoding at 240 px,
        # so with stagger, past the budget the rest load one per Tk turn while the host plays.
        deadline = time.monotonic() + SYNC_BUDGET_S
        while self._pending and (not stagger or time.monotonic() < deadline):
            self._prepare_next()
        if self._pending:
            self._load = parent.after(1, self._load_step)
        else:
            self._place()

    def _prepare_next(self) -> None:
        member, own = self._pending.pop(0)
        frames, frame_ms, ping_pong, (dx, dy) = self._frames(self.library, member, own)
        if frames:
            self._prepared.append((member, frames, frame_ms, ping_pong, dx, dy))

    def _load_step(self) -> None:
        self._load = None
        if self._closed:
            return
        if self._pending:
            self._prepare_next()
        if self._pending:
            self._load = self.parent.after(1, self._load_step)
        else:
            self._place()

    def _place(self) -> None:
        """Lay out every prepared guest at once (layout needs all widths) and open her window."""
        _pet_x, pet_y, _w, h = self._pet_box
        prepared, self._prepared = self._prepared, []
        slots, scale = roster_layout(self._host_bounds, self._area,
                                     [(e[4], e[1][0].width()) for e in prepared])
        self.guest_scale = scale
        for (member, frames, frame_ms, ping_pong, dx, dy), x in zip(prepared, slots):
            if x is None:
                self.omitted.append(member)
                log.warning("group celebration: no uncropped slot for %s", member or "visitor")
                continue
            if scale < 1.0:
                frames = self._scaled(frames, scale)
            # A large canvas is offset so her feet land on the slot's feet point; a shrunk
            # one keeps the base box's bottom (her feet) on the pet's feet line.
            fw, fh = frames[0].width(), frames[0].height()
            top = pet_y + dy if scale >= 1.0 else pet_y + h - round((h - dy) * scale)
            wx = x + dx
            win = tk.Toplevel(self.parent)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=BG)
            surf: LayeredSpriteSurface | None = None
            if self._use_ulw and isinstance(tk.Toplevel, type) and isinstance(win, tk.Toplevel):
                try:
                    # Keep input_policy='interactive' so PandaPet._apply_cursor_to_panel shows the
                    # custom Apink paw cursor on opaque guest pixels while ULW alpha==0 passes through.
                    surf = LayeredSpriteSurface(
                        win,
                        x=wx,
                        y=top,
                        opacity=1.0,
                        input_policy="interactive",
                        noactivate=True,
                        topmost=True,
                    )
                except Exception:
                    log.exception("group celebration ULW init failed; falling back to ColorKey")
                    surf = None
            if surf is None:
                try:
                    win.attributes("-transparentcolor", BG)
                except tk.TclError:
                    pass
            canvas = tk.Canvas(win, width=fw, height=fh, bg=BG, highlightthickness=0)
            canvas.pack()
            item = canvas.create_image(0, 0, anchor="nw", image=frames[0])
            win.geometry(f"{fw}x{fh}+{wx}+{top}")
            win.update_idletasks()
            if surf is not None:
                first_pil = getattr(frames[0], "_pil_image", None) or ImageTk.getimage(frames[0])
                surf.present(first_pil, x=wx, y=top, opacity=1.0)
                win.deiconify()
                surf.set_visibility(True, reorder=False)
                self.surfaces[win] = surf
                self._canvas_surfaces[canvas] = surf
            else:
                win.deiconify()
            self.windows.append((win, canvas, item, frames, frame_ms, ping_pong))
        self._tick()
        if self.on_placed is not None:
            try:
                self.on_placed(self)
            except Exception:
                log.exception("group celebration: on_placed failed")

    def _scaled(self, frames, scale: float) -> list[tk.PhotoImage]:
        out = []
        for photo in frames:
            src_im = getattr(photo, "_pil_image", None) or ImageTk.getimage(photo)
            im = scale_sprite_frame(src_im, scale, self.library, default_binary=not getattr(self, "_use_ulw", False))
            scaled_photo = ImageTk.PhotoImage(im, master=self.parent)
            scaled_photo._pil_image = im  # type: ignore[attr-defined]
            out.append(scaled_photo)
        return out

    @staticmethod
    def _make_photo(im: Image.Image, master: tk.Misc) -> tk.PhotoImage:
        photo = ImageTk.PhotoImage(im, master=master)
        photo._pil_image = im  # type: ignore[attr-defined]
        return photo

    def _frames(self, library: SpriteLibrary, member: str, action: str):
        """(frames, frame_ms, ping_pong, offset): her approved action, else her base cheer."""
        try:
            raw_bin = getattr(library, "binary_alpha", not getattr(self, "_use_ulw", False))
            binary_alpha = raw_bin if isinstance(raw_bin, bool) else (not getattr(self, "_use_ulw", False))
            edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
            if member is None:
                loaded = load_exact_action(library, None, self.visitor_action, scale_member=self.scale_member)
                if loaded is None:
                    return [], CHEER_MS, False, (0, 0)
            else:
                cache = self.photo_cache
                key = (member, action, getattr(library, "display_px", None), binary_alpha, edge_refine)
                if cache is not None and key in cache:
                    cache.move_to_end(key)
                    photos, frame_ms, offset = cache[key]
                    return list(photos), frame_ms, False, offset
                loaded = load_exact_action(library, member, action)
                if loaded is not None and cache is not None:
                    photos = [self._make_photo(im, self.parent) for im in loaded.frames]
                    cache[key] = (photos, loaded.frame_ms, loaded.offset)
                    total = sum(_photo_cache_bytes(v) for v in cache.values())
                    while len(cache) > 1 and (len(cache) > PHOTO_CACHE_ENTRIES or total > PHOTO_CACHE_BYTES):
                        _k, old = cache.popitem(last=False)
                        total -= _photo_cache_bytes(old)
                    return list(photos), loaded.frame_ms, False, loaded.offset
            if loaded is not None:
                return ([self._make_photo(im, self.parent) for im in loaded.frames],
                        loaded.frame_ms, False, loaded.offset)
            member_sprites = library.load_member(member, self.parent)
            photos = list(member_sprites.get("cheer"))
            if callable(getattr(member_sprites, "get_pil", None)):
                pil_list = member_sprites.get_pil("cheer", 1)
                for p, im in zip(photos, pil_list):
                    p._pil_image = im  # type: ignore[attr-defined]
            return photos, CHEER_MS, True, (0, 0)
        except Exception:
            log.exception("group celebration: no frames for %s", member)
            return [], CHEER_MS, False, (0, 0)

    @property
    def members_shown(self) -> int:
        return len(self.windows)

    @property
    def loading(self) -> bool:
        """True while cold guests are still being decoded (their windows are not open yet)."""
        return self._load is not None

    def frame_index(self, n_frames: int, frame_ms: float, ping_pong: bool, elapsed_ms: float) -> int:
        step = int(elapsed_ms // frame_ms)
        if ping_pong:
            return CHEER_SEQ[step % len(CHEER_SEQ)] % n_frames
        return step % n_frames

    def _tick(self) -> None:
        elapsed_ms = (time.monotonic() - self._t0) * 1000
        canvas_surfaces = getattr(self, "_canvas_surfaces", None) or {}
        for win, canvas, item, frames, frame_ms, ping_pong in self.windows:
            try:
                photo = frames[self.frame_index(len(frames), frame_ms, ping_pong, elapsed_ms)]
                if self._shown_photos.get(canvas) is not photo:
                    canvas.itemconfigure(item, image=photo)
                    self._shown_photos[canvas] = photo
                    surf = canvas_surfaces.get(canvas)
                    if surf is not None and not surf.closed:
                        pil_im = getattr(photo, "_pil_image", None) or ImageTk.getimage(photo)
                        surf.present(pil_im)
            except (tk.TclError, OSError):
                pass
        if self.windows:
            self._after = self.parent.after(TICK_MS, self._tick)

    def close(self) -> None:
        was_active = bool(self.windows or self._prepared or self._pending or self._load is not None)
        self._closed = True
        self._pending = []
        self._prepared = []
        for after_id in (self._after, self._end, self._load):
            if after_id is not None:
                try:
                    self.parent.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._after = self._end = self._load = None
        windows, self.windows = self.windows, []
        self._shown_photos.clear()
        surfaces = getattr(self, "surfaces", None)
        if isinstance(surfaces, dict):
            all_surfs = list(surfaces.values())
            surfaces.clear()
        else:
            all_surfs = []
        canvas_surfaces = getattr(self, "_canvas_surfaces", None)
        if isinstance(canvas_surfaces, dict):
            canvas_surfaces.clear()
        for surf in all_surfs:
            try:
                surf.close()
            except Exception:
                pass
        for win, *_ in windows:
            try:
                win.destroy()
            except tk.TclError:
                pass
        if was_active and self.on_done is not None:
            on_done, self.on_done = self.on_done, None
            on_done()
