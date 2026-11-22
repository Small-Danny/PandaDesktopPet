"""Measured speech cards, wrapped chips, and font-independent color icons.

Emoji use local vector icons rather than unsupported Windows font glyphs. Long
messages remain readable in a scrollable inner card. No source text is changed.

Decorated themes (frame art in work/bubbles) lay everything out inside the
frame's measured safe area (``bubble_art``), so text never sits on an
ornament; the frame is scaled uniformly to the card width and only an
ornament-free band of rows is stretched for taller content. If the art is
missing or broken the plain vector card is used.
"""
from __future__ import annotations

from collections import OrderedDict
import logging
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Callable
from PIL import Image, ImageDraw, ImageTk
from app.bubble_art import FrameLayout
from app.bubble_layout import is_emoji, iter_clusters, layout_lines
from app.bubble_themes import BubbleTheme, get_theme
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, ui_scale
from app.resource_store import open_resource_image
from app.sprite_polish import alpha_bleed, defringe_light_frame

log = logging.getLogger(__name__)

BG_TRANSPARENT = "#ff00fe"
LONG_TEXT_CHARS = 80          # longer messages stay up 8..10 s
LONG_TEXT_MIN_MS = 8000
LONG_TEXT_MAX_MS = 10000
RESUME_MIN_MS = 1500          # after the pointer leaves, never vanish instantly
FRAMED_WIDTHS = (320, 370, 440, 480)  # short messages get a smaller decorated card
TILE_MAX_ROWS = 16            # stretch bands at least this tall are resized, thinner ones tiled
_BINARIZE_LUT = tuple(255 if a >= 128 else 0 for a in range(256))
_FRAME_CACHE_MAX = 24
_FRAME_CACHE: OrderedDict[tuple, Image.Image] = OrderedDict()
_AVATAR_THUMB_MAX = 16
_AVATAR_THUMB_CACHE: OrderedDict[tuple[str, int, tuple | None], Image.Image] = OrderedDict()


def _path_version(path: Path) -> tuple | None:
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None

TEXT_SIZE_FONTS = {
    "small":  {"title": 9,  "message": 9,  "small": 8},
    "medium": {"title": 10, "message": 10, "small": 8},
    "large":  {"title": 12, "message": 12, "small": 10},
}
TEXT_SIZE_WIDTHS = {
    "small":  (300, 350, 420),
    "medium": (320, 370, 440, 480),
    "large":  (360, 420, 500),
}


def effective_duration_ms(message: str, duration_ms: int) -> int:
    """Long messages (> 80 characters) stay 8..10 s, never shorter than asked."""
    chars = sum(1 for c in iter_clusters(message) if not c.isspace())
    if chars <= LONG_TEXT_CHARS:
        return duration_ms
    extra = min(LONG_TEXT_MAX_MS, LONG_TEXT_MIN_MS + (chars - LONG_TEXT_CHARS) * 25)
    return max(duration_ms, extra)


def _render_9slice(src_path: Path | Image.Image, target_w: int, target_h: int,
                   insets: tuple[int, int, int, int]) -> Image.Image:
    """Dynamic 9-slice image scaling for speech bubbles (zero insets allowed)."""
    def paste(box, size, at):
        if box[2] > box[0] and box[3] > box[1] and size[0] > 0 and size[1] > 0:
            piece = card.crop(box)
            if piece.size != size:
                piece = piece.resize(size, Image.Resampling.BILINEAR)
            dest.paste(piece, at)

    opened = None if isinstance(src_path, Image.Image) else open_resource_image(src_path)
    try:
        card = src_path if opened is None else opened
        cw, ch = card.size
        top, right, bottom, left = insets
        tw, th = target_w, target_h
        dest = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        card = card.convert("RGBA") if card.mode != "RGBA" else card
        paste((0, 0, left, top), (left, top), (0, 0))
        paste((cw - right, 0, cw, top), (right, top), (tw - right, 0))
        paste((0, ch - bottom, left, ch), (left, bottom), (0, th - bottom))
        paste((cw - right, ch - bottom, cw, ch), (right, bottom), (tw - right, th - bottom))
        edge_w = tw - left - right
        edge_h = th - top - bottom
        paste((left, 0, cw - right, top), (edge_w, top), (left, 0))
        paste((left, ch - bottom, cw - right, ch), (edge_w, bottom), (left, th - bottom))
        paste((0, top, left, ch - bottom), (left, edge_h), (0, top))
        paste((cw - right, top, cw, ch - bottom), (right, edge_h), (tw - right, top))
        paste((left, top, cw - right, ch - bottom), (edge_w, edge_h), (left, top))
        return dest
    finally:
        if opened is not None:
            opened.close()


def _render_frame(nine_path: Path, frame: FrameLayout, geo) -> Image.Image:
    """Decorated card: frame scaled uniformly to the card width; the clean band
    (with straight side borders) is repeated, never resized, to add height."""
    cache_key = (
        str(nine_path), _path_version(nine_path),
        geo.width, geo.height, geo.cap_top, geo.cap_bottom,
        round(geo.scale, 4), frame.band, frame.right_cut, frame.fill_row,
    )
    cached = _FRAME_CACHE.get(cache_key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(cache_key)
        return cached.copy()
    with open_resource_image(nine_path) as src:
        source = alpha_bleed(src.convert("RGBA"))
    w = geo.width
    scaled = source.resize((w,round(frame.size[1]*geo.scale)),Image.Resampling.LANCZOS)
    band_h = geo.height-geo.cap_top-geo.cap_bottom
    strip = frame.band_strip(source)
    strip = strip.resize((w,max(1,round(strip.height*geo.scale))),Image.Resampling.LANCZOS)
    if strip.height >= TILE_MAX_ROWS:
        tiled = strip   # tall gradient band: resize smoothly (repeating would show seams)
    else:               # thin band (paper texture): repeat it (resizing would streak)
        tiled = Image.new("RGBA",(w,band_h),(0,0,0,0))
        for y in range(0,band_h,strip.height):
            tiled.paste(strip,(0,y))
    out = Image.new("RGBA",(w,geo.height),(0,0,0,0))
    scaled_clean = defringe_light_frame(_binarize(scaled))
    out.paste(scaled_clean.crop((0,0,w,geo.cap_top)),(0,0))
    out.paste(defringe_light_frame(_binarize(_render_9slice(tiled,w,band_h,(0,0,0,0)))),(0,geo.cap_top))
    out.paste(scaled_clean.crop((0,scaled.height-geo.cap_bottom,w,scaled.height)),(0,geo.height-geo.cap_bottom))
    if frame.right_cut is not None:     # left and right halves may split at different rows to keep ornaments intact
        mid, shift = w//2, round((frame.right_cut-frame.band[0])*geo.scale)
        top, bottom = geo.cap_top+shift, geo.height-geo.cap_bottom+shift
        out.paste(scaled_clean.crop((mid,0,w,top)),(mid,0))
        if bottom > top:
            right_band = defringe_light_frame(_binarize(_render_9slice(tiled,w,bottom-top,(0,0,0,0))))
            out.paste(right_band.crop((mid,0,w,bottom-top)),(mid,top))
        out.paste(scaled_clean.crop((mid,scaled.height-geo.cap_bottom+shift,w,scaled.height)),(mid,bottom))
    result = _binarize(out)
    _FRAME_CACHE[cache_key] = result.copy()
    while len(_FRAME_CACHE) > _FRAME_CACHE_MAX:
        _FRAME_CACHE.popitem(last=False)
    return result


def _binarize(image: Image.Image) -> Image.Image:
    """Colour-key windows cannot show partial alpha (it would blend with magenta)."""
    image.putalpha(image.getchannel("A").point(_BINARIZE_LUT))
    return image


def _draw_round_rect(canvas, x1, y1, x2, y2, r=16, **kwargs):
    r = min(r, max(0, (x2-x1)/2), max(0, (y2-y1)/2))
    points = (x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r,
              x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1)
    return canvas.create_polygon(points, smooth=True, **kwargs)


def emoji_icon(cluster: str, size: int) -> Image.Image:
    """Semantic icon families; unknown emoji use a neutral sparkle."""
    image = Image.new("RGBA", (72, 72))
    d = ImageDraw.Draw(image)
    pink, dark = "#ef719e", "#71394e"
    if any(ch in cluster for ch in "❤♥💕💖💗💞💓💝💟🩷💛🥰"):
        d.ellipse((8,12,37,42), fill=pink)
        d.ellipse((35,12,64,42), fill=pink)
        d.polygon(((9,29),(63,29),(36,64)), fill=pink)
    elif any(ch in cluster for ch in "🐼🐾🐶🐱🐰"):
        d.ellipse((8,8,29,30), fill=dark)
        d.ellipse((43,8,64,30), fill=dark)
        d.ellipse((10,15,62,65), fill="#fff5fa", outline=dark, width=3)
        for x in (19,41):
            d.ellipse((x,31,x+12,45), fill=pink)
            d.ellipse((x+4,34,x+8,39), fill=dark)
        d.ellipse((32,45,40,51), fill=dark)
    elif any(ch in cluster for ch in "☕🍵🥤🍺🥃🍶💧🚰🍻🥛🧊"):
        d.rounded_rectangle((13,20,51,59), radius=8, fill="#e3a6be", outline=dark, width=3)
        d.arc((41,25,65,51),270,90,fill=dark,width=4)
        for x in (24,39):
            d.line((x,15,x-4,9,x+1,3),fill=pink,width=3)
    elif any(ch in cluster for ch in "⏰🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚🕛"):
        d.ellipse((8,8,64,64),fill="#fff6de",outline=dark,width=4)
        d.line((36,18,36,36,49,42),fill=pink,width=4)
        d.arc((2,1,30,25),190,350,fill=pink,width=4)
        d.arc((42,1,70,25),190,350,fill=pink,width=4)
    elif any(ch in cluster for ch in "⚠🚨"):
        d.polygon(((36,5),(69,65),(3,65)),fill="#f6d06a",outline=dark,width=3)
        d.rounded_rectangle((33,24,39,46),radius=2,fill=dark)
        d.ellipse((33,52,39,58),fill=dark)
    elif any(ch in cluster for ch in "🍞🍠🍗🍢🍔🍖🥩🍲🍱🍜🥗🥣🥓🥚"):
        d.ellipse((8,25,64,43),fill="#fff4d9",outline=dark,width=3)
        d.pieslice((8,12,64,68),0,180,fill="#eb9abb",outline=dark,width=3)
        d.line((19,16,61,5),fill=dark,width=3)
        d.line((19,21,65,12),fill=dark,width=3)
    elif any(ch in cluster for ch in "🎂🍰🧁🍮🍩🍪🍓🍨"):
        d.rounded_rectangle((10,30,62,62),radius=7,fill="#f9c8d8",outline=dark,width=2)
        d.rectangle((11,31,61,41),fill="#fff6de")
        d.line((36,13,36,30),fill=pink,width=5)
        d.ellipse((32,4,40,15),fill="#efb348")
    elif any(ch in cluster for ch in "🎤🎵🎶🎸🎧"):
        d.line((28,51,28,18,57,11,57,44),fill=dark,width=5)
        d.ellipse((12,44,29,59),fill=pink)
        d.ellipse((41,38,58,53),fill=pink)
    elif any(ch in cluster for ch in "💤🌙🛌😴"):
        d.ellipse((9,6,63,63),fill="#e8bc65")
        d.ellipse((29,0,70,46),fill=(0,0,0,0))
    elif any(ch in cluster for ch in "🔔📣📢💌💬📨📧📬📌"):
        d.rounded_rectangle((7,13,65,53),radius=10,fill="#f4c1d5",outline=dark,width=3)
        d.polygon(((17,49),(17,65),(34,51)),fill="#f4c1d5")
        for x in (22,36,50):
            d.ellipse((x-3,30,x+3,36),fill=dark)
    elif any(ch in cluster for ch in "🌸🌿🌱🎍"):
        d.line((36, 66, 36, 28), fill="#468157", width=5)
        d.ellipse((13, 45, 37, 58), fill="#77ae71", outline="#468157", width=2)
        d.ellipse((36, 38, 59, 52), fill="#77ae71", outline="#468157", width=2)
        for x, y in ((36, 12), (49, 22), (44, 36), (28, 36), (23, 22)):
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=pink)
        d.ellipse((28, 17, 44, 33), fill="#ffe198", outline=dark, width=2)
    elif any(ch in cluster for ch in "☀⚡"):
        d.polygon(((36, 2), (45, 15), (62, 10), (58, 27), (70, 36), (58, 45),
                   (62, 62), (45, 57), (36, 70), (27, 57), (10, 62), (14, 45),
                   (2, 36), (14, 27), (10, 10), (27, 15)), fill="#ffe295")
        d.ellipse((17, 17, 55, 55), fill="#fbc653", outline="#bd733a", width=3)
        d.polygon(((37, 22), (26, 38), (35, 38), (32, 50), (46, 32), (37, 32)),
                  fill="#fff8db", outline="#bd733a")
    elif "🎮" in cluster:
        d.rounded_rectangle((5, 19, 67, 56), radius=17, fill="#cdb7ed", outline=dark, width=3)
        d.line((23, 28, 23, 47), fill=dark, width=5)
        d.line((14, 37, 32, 37), fill=dark, width=5)
        d.ellipse((46, 28, 55, 37), fill=pink, outline=dark)
        d.ellipse((54, 38, 63, 47), fill="#fff1bd", outline=dark)
    elif any(ch in cluster for ch in "🔥🌶"):
        d.polygon(((36, 3), (44, 22), (52, 16), (56, 29), (63, 41), (61, 54),
                   (51, 65), (34, 69), (19, 63), (10, 51), (13, 39), (24, 25),
                   (27, 34)), fill="#f57763", outline="#a44347", width=2)
        d.polygon(((37, 31), (43, 46), (50, 49), (47, 60), (37, 65), (27, 59),
                   (24, 52)), fill="#ffd36b")
    elif any(ch in cluster for ch in "🎉🎆🎁🏆👑🎄"):
        d.polygon(((12, 66), (24, 29), (49, 50)), fill=pink, outline=dark, width=3)
        d.line((19, 46, 35, 56), fill="#fff5fa", width=4)
        d.line((33, 27, 36, 12), fill="#a78bdc", width=4)
        d.line((46, 34, 62, 24), fill="#6cae93", width=4)
        d.ellipse((48, 7, 57, 16), fill="#fbc653")
        d.ellipse((57, 42, 66, 51), fill="#a78bdc")
        d.ellipse((19, 14, 26, 21), fill="#6cae93")
    elif any(ch in cluster for ch in "★☆⭐🌟"):    # rating stars: ☆ is the unlit one
        star = ((36,4),(45,26),(69,27),(50,42),(57,66),(36,52),(15,66),(22,42),(3,27),(27,26))
        if "☆" in cluster:
            d.polygon(star,fill="#f3e8f0",outline="#c9a2b8",width=3)
        else:
            d.polygon(star,fill="#f5bf45",outline="#bd733a",width=3)
    elif any(ch in cluster for ch in "😋😆🥺😫💪🥋🥊⚽"):
        d.ellipse((6, 6, 66, 66), fill="#ffdf8d", outline=dark, width=3)
        for x in (18, 42):
            d.arc((x, 23, x + 12, 38), 195, 345, fill=dark, width=3)
            d.ellipse((x - 4, 39, x + 8, 45), fill=pink)
        d.pieslice((23, 32, 49, 57), 0, 180, fill=dark)
        d.ellipse((32, 48, 43, 55), fill=pink)
    else:
        d.polygon(((36,3),(45,26),(68,35),(45,44),(36,68),(27,44),(4,35),(27,26)),fill="#efb65f")
        d.ellipse((51,6,62,17),fill=pink)
    return image.resize((size,size),Image.Resampling.LANCZOS)


class KawaiiSpeechBubble:
    def __init__(self, parent: tk.Tk | tk.Toplevel, target_x: int, target_y: int,
                 sprite_w: int, header: str, message: str, sub_badge: str = "",
                 badge_text: str = "", icon_path: Path | None = None,
                 duration_ms: int = 5000, on_close: Callable[[], None] | None = None,
                 *, sprite_h: int = 192, desktop: WindowsDesktopAdapter | None = None,
                 theme: BubbleTheme | None = None,
                 text_size: str = "medium"):
        self.parent, self.on_close = parent, on_close
        self.header, self.message = header, message
        self.theme = theme or get_theme("classic")
        self.text_size = text_size if text_size in TEXT_SIZE_FONTS else "medium"
        fonts = TEXT_SIZE_FONTS[self.text_size]
        self._closed, self.timer, self.icon_thumb = False, None, None
        self._image_refs, self._emoji_images = [], {}
        self.duration_ms = effective_duration_ms(message, duration_ms)
        self._deadline = 0.0
        self._remaining_ms = 0.0
        self._pressed_canvas = None
        self.chip_boxes = []
        self.frame: FrameLayout | None = None
        self.card_image: Image.Image | None = None   # decorated frame actually drawn
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost",True)
        self.window.configure(bg=BG_TRANSPARENT)
        try:
            self.window.attributes("-transparentcolor",BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.ui_scale = ui_scale(self.window)
        self.framed_widths = tuple(self._s(w) for w in TEXT_SIZE_WIDTHS[self.text_size])
        self.card_origin = (self._s(6), self._s(6))
        self.f_title = tkfont.Font(root=self.window,family="Microsoft JhengHei",size=fonts["title"],weight="bold")
        self.f_message = tkfont.Font(root=self.window,family="Microsoft JhengHei",size=fonts["message"])
        self.f_small = tkfont.Font(root=self.window,family="Microsoft JhengHei",size=fonts["small"])
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.desktop = desktop or WindowsDesktopAdapter(fallback_bounds=WorkArea(0,0,sw,sh))
        self.work_area = area = self.desktop.work_area_for_point(target_x+sprite_w//2,target_y+sprite_h//2)
        self.title_lh = self.f_title.metrics("linespace")+self._s(5)
        self.small_lh = self.f_small.metrics("linespace")+self._s(4)
        self.msg_lh = self.f_message.metrics("linespace")+self._s(6)
        self.emoji_size = max(self._s(12),self.f_message.metrics("linespace")-self._s(2))
        has_icon = False
        if icon_path is not None:
            try:
                icon_px = self._s(42)
                akey = (str(icon_path), icon_px, _path_version(icon_path))
                image = _AVATAR_THUMB_CACHE.get(akey)
                if image is not None:
                    _AVATAR_THUMB_CACHE.move_to_end(akey)
                else:
                    with open_resource_image(icon_path) as source:
                        image = source.convert("RGBA")
                        bbox = image.getbbox()
                        if bbox:
                            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                            if bh > 100:
                                cx = (bbox[0] + bbox[2]) // 2
                                top = max(0, bbox[1] - 4)
                                side = max(bw + 8, int(bh * 0.70))
                                left = max(0, cx - side // 2)
                                right = min(image.width, left + side)
                                bottom = min(image.height, top + side)
                                image = image.crop((left, top, right, bottom))
                        image = image.resize((icon_px, icon_px), Image.Resampling.LANCZOS)
                    _AVATAR_THUMB_CACHE[akey] = image
                    while len(_AVATAR_THUMB_CACHE) > _AVATAR_THUMB_MAX:
                        _AVATAR_THUMB_CACHE.popitem(last=False)
                self.icon_thumb = ImageTk.PhotoImage(image,master=self.window)
                self._image_refs.append(self.icon_thumb)
                has_icon = True
            except (OSError,ValueError):
                pass
        args = (area,target_x,target_y,sprite_w,sprite_h,header,message,sub_badge,badge_text,has_icon)
        placed = None
        nine_path = self.theme.get_nine_slice_path()
        if nine_path is not None:
            try:
                self.frame = self.theme.frame_layout()
                placed = self._build_framed(nine_path,*args)
            except Exception:
                log.warning("bubble frame %s unusable; using vector card", nine_path, exc_info=True)
                self._reset_canvas()
        if placed is None:
            placed = self._build_vector(*args)
        bx,by = placed
        w = self.width
        self.window.geometry(f"{w}x{self.height}+{bx}+{by}")
        self.window.update_idletasks()
        frame = self.window.wm_frame()
        hwnd = int(frame,16) if frame.startswith("0x") else int(frame)
        self.desktop.set_noactivate(hwnd)
        self.window.deiconify()
        self.window.update_idletasks()
        # Native absolute placement avoids negative-geometry right-edge semantics.
        self.desktop.position_without_activation(hwnd,int(bx),int(by))
        # Hovering pauses the countdown so a long notice can be read in peace.
        self.window.bind("<Enter>",self._pause_timer,add="+")
        self.window.bind("<Leave>",self._resume_timer,add="+")
        self._start_timer(self.duration_ms)

    # ------------------------------------------------------------ countdown
    def _start_timer(self, ms: float) -> None:
        self._deadline = time.monotonic()+ms/1000
        self.timer = self.window.after(max(1,int(ms)),self.dismiss)

    def _pause_timer(self, _event=None) -> None:
        if self._closed or self.timer is None:
            return
        try:
            self.window.after_cancel(self.timer)
        except tk.TclError:
            pass
        self.timer = None
        self._remaining_ms = max(0.0,(self._deadline-time.monotonic())*1000)

    def _resume_timer(self, _event=None) -> None:
        if self._closed or self.timer is not None or self._pressed_canvas is not None:
            return
        try:  # <Leave> also fires when moving onto a child widget: still inside?
            px,py = self.window.winfo_pointerxy()
            x,y = self.window.winfo_rootx(),self.window.winfo_rooty()
            if x <= px < x+self.window.winfo_width() and y <= py < y+self.window.winfo_height():
                return
        except tk.TclError:
            return
        self._start_timer(max(RESUME_MIN_MS,self._remaining_ms))

    @property
    def paused(self) -> bool:
        return not self._closed and self.timer is None

    # ------------------------------------------------------------ layouts
    def _reset_canvas(self) -> None:
        canvas = getattr(self,"canvas",None)
        if canvas is not None:
            canvas.destroy()
            del self.canvas
        if hasattr(self,"_bg_photo"):
            del self._bg_photo
        self.card_image = None
        self.chip_boxes = []

    def _s(self, px: float) -> int:
        return round(px * self.ui_scale)

    def _layout_chips(self, sub_badge, x0, x1, y):
        """Wrap context chips into rows between x0..x1 from y; returns (boxes, bottom)."""
        boxes,inner_w = [],x1-x0
        chips = [p.strip() for p in sub_badge.replace("【","").replace("】","").split("｜") if p.strip()]
        if not chips:
            return boxes, y
        measured = []
        min_w = self._s(20)
        for chip in chips:
            lines = layout_lines(chip,max(min_w,inner_w-min_w),self.f_small.measure,self.emoji_size)
            text_w = max((self._line_width(line,self.f_small) for line in lines),default=0)
            measured.append((chip,lines,text_w))
        n = len(measured)
        sum_text_w = sum(m[2] for m in measured)
        pad_x, gap_x = self._s(10), self._s(8)
        if n > 1:
            std_need = sum_text_w + n * self._s(20) + (n - 1) * gap_x
            if std_need > inner_w:
                for g in (self._s(6), self._s(5), self._s(4)):
                    avail = inner_w - sum_text_w - (n - 1) * g
                    cand_pad = avail // (n * 2)
                    if cand_pad >= self._s(3):
                        pad_x = min(self._s(10), cand_pad)
                        gap_x = g
                        break
        x,row_h = x0,0
        chip_vpad, row_gap = self._s(10), self._s(7)
        for chip,lines,text_w in measured:
            chip_w = min(inner_w,text_w+pad_x*2)
            chip_h = len(lines)*self.small_lh+chip_vpad
            if x>x0 and x+chip_w>x1:
                x,y,row_h = x0,y+row_h+row_gap,0
            boxes.append((x,y,chip_w,chip_h,lines))
            x += chip_w+gap_x
            row_h = max(row_h,chip_h)
        return boxes,(y+row_h if chips else y)

    def _place(self, area, w, target_x, target_y, sprite_w, sprite_h):
        """Window position next to the sprite, kept inside the monitor work area."""
        center_x = target_x+sprite_w//2
        bx = min(max(area.left+10,center_x-w//2),max(area.left+10,area.right-w-10))
        above = target_y-self.height-8>=area.top+10
        by = target_y-self.height-8 if above else target_y+sprite_h+8
        by = min(max(area.top+10,by),max(area.top+10,area.bottom-self.height-10))
        self.target_position = (bx,by)
        tail_x = min(max(30,center_x-bx),w-30)
        return bx,by,above,tail_x

    def _build_framed(self, nine_path, area, target_x, target_y, sprite_w, sprite_h,
                      header, message, sub_badge, badge_text, has_icon):
        """Decorated card: every element inside the frame's measured safe area."""
        frame = self.frame
        sw,sh = area.width,area.height
        candidate_widths = getattr(self, "framed_widths", FRAMED_WIDTHS)
        max_w = min(candidate_widths[-1], max(self._s(160), sw - 20))
        widths = [w for w in candidate_widths if w <= max_w] or [max_w]
        icon_box,close_d,gap = self._s(44),self._s(24),self._s(8)
        min_w, card_pad = self._s(20), self._s(6)
        for w in widths:
            card_w = w-self._s(12)
            geo = frame.geometry(card_w,0)
            sx0,sy0,sx1,sy1 = geo.safe
            inner_w = sx1-sx0
            title_x = sx0+(icon_box+self._s(10) if has_icon else 0)
            title_w = max(min_w,sx1-close_d-gap-title_x)
            title_lines = layout_lines(header,title_w,self.f_title.measure,self.emoji_size) if header else ()
            msg_lines = layout_lines(message,max(min_w,inner_w-self._s(20)),self.f_message.measure,self.emoji_size)
            chip_boxes,_ = self._layout_chips(sub_badge,sx0,sx1,0)
            chip_rows = len({b[1] for b in chip_boxes})
            if w == widths[-1] or (len(title_lines) <= 1 and len(msg_lines) <= 2 and chip_rows <= 1):
                break
        # Stack top -> bottom in safe-area coordinates (y = 0 at the safe top).
        head_h = max(icon_box if has_icon else 0,len(title_lines)*self.title_lh,close_d)
        chip_boxes,chips_bottom = self._layout_chips(sub_badge,sx0,sx1,head_h+gap)
        msg_top = (chips_bottom if chip_boxes else head_h)+gap
        badge_lines = layout_lines(badge_text,max(min_w,inner_w-self._s(8)),self.f_small.measure,self.emoji_size) if badge_text else ()
        footer_h = len(badge_lines)*self.small_lh+gap if badge_text else 0
        desired = max(self._s(44),len(msg_lines)*self.msg_lh+self._s(20))
        # Height budget: the window must fit the monitor; the message scrolls beyond that.
        decor_h = geo.height-(sy1-sy0)
        max_content = max(self._s(60),sh-20-self._s(24)-decor_h)
        viewport_limit = max(self._s(36),min(self._s(360),max_content-msg_top-footer_h))
        self.scrollable = desired>viewport_limit
        if self.scrollable:
            msg_lines = layout_lines(message,max(min_w,inner_w-self._s(38)),self.f_message.measure,self.emoji_size)
            desired = max(self._s(44),len(msg_lines)*self.msg_lh+self._s(20))
        message_h = min(desired,viewport_limit)
        content_h = msg_top+message_h+footer_h
        geo = frame.geometry(card_w,content_h)
        sx0,sy0,sx1,sy1 = geo.safe
        dy = sy0+((sy1-sy0)-content_h)//2   # centre the content in the safe area

        art = _render_frame(nine_path,frame,geo)
        body_h = card_pad+geo.height
        h = body_h+self._s(24)
        self.width,self.height,self.content_height = w,min(h,max(self._s(80),sh-20)),h
        self.canvas = tk.Canvas(self.window,width=w,height=self.height,bg=BG_TRANSPARENT,highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.configure(scrollregion=(0,0,w,h))
        bx,by,above,tail_x = self._place(area,w,target_x,target_y,sprite_w,sprite_h)
        offset = 0 if above else self._s(12)
        ox,oy = card_pad,card_pad+offset
        self._bg_photo = ImageTk.PhotoImage(art,master=self.window)
        self._image_refs.append(self._bg_photo)
        self.card_image,self.card_origin = art,(ox,oy)
        self.canvas.create_image(ox,oy,anchor="nw",image=self._bg_photo)

        X0,X1,Y0 = ox+sx0,ox+sx1,oy+dy
        if has_icon:
            _draw_round_rect(self.canvas,X0,Y0,X0+icon_box,Y0+icon_box,self._s(12),fill="white",outline=self.theme.chip_outline)
            self.canvas.create_image(X0+icon_box//2,Y0+icon_box//2,image=self.icon_thumb)
        title_y = Y0+max(0,(head_h-len(title_lines)*self.title_lh)//2)
        self._draw_lines(self.canvas,title_lines,ox+title_x,title_y,self.f_title,self.theme.header_color,self.title_lh)
        cy0 = Y0+(head_h-close_d)//2
        self.canvas.create_oval(X1-close_d,cy0,X1,cy0+close_d,fill=self.theme.close_btn_bg,outline="",tags="close_btn")
        self.canvas.create_line(X1-self._s(16),cy0+self._s(8),X1-self._s(8),cy0+self._s(16),
                                fill=self.theme.close_btn_cross,width=1.5*self.ui_scale,tags="close_btn")
        self.canvas.create_line(X1-self._s(8),cy0+self._s(8),X1-self._s(16),cy0+self._s(16),
                                fill=self.theme.close_btn_cross,width=1.5*self.ui_scale,tags="close_btn")
        self.chip_boxes = [(x+ox,y+Y0,cw,ch,lines) for x,y,cw,ch,lines in chip_boxes]
        for x,y,cw,ch,lines in self.chip_boxes:
            _draw_round_rect(self.canvas,x,y,x+cw,y+ch,self._s(7),fill=self.theme.chip_fill,outline=self.theme.chip_outline)
            text_w = max((self._line_width(line,self.f_small) for line in lines),default=0)
            pad_left = max(self._s(4),(cw-text_w)//2)
            self._draw_lines(self.canvas,lines,x+pad_left,y+self._s(5),self.f_small,self.theme.chip_text,self.small_lh)
        my = Y0+msg_top
        _draw_round_rect(self.canvas,X0,my,X1,my+message_h,self._s(10),fill=self.theme.inner_card_fill,outline=self.theme.inner_card_outline)
        msg_w = inner_w-self._s(8)-(self._s(18) if self.scrollable else 0)
        msg_inset = self._s(4)
        self.message_canvas = tk.Canvas(self.canvas,width=msg_w,height=message_h-self._s(8),bg=self.theme.inner_card_fill,highlightthickness=0)
        self.canvas.create_window(X0+msg_inset,my+msg_inset,anchor="nw",window=self.message_canvas,width=msg_w,height=message_h-self._s(8))
        self._draw_lines(self.message_canvas,msg_lines,self._s(6),self._s(6),self.f_message,self.theme.text_color,self.msg_lh)
        self.message_canvas.configure(scrollregion=(0,0,msg_w,desired-self._s(8)))
        if self.scrollable:
            scrollbar = tk.Scrollbar(self.canvas,orient="vertical",command=self.message_canvas.yview)
            self.message_canvas.configure(yscrollcommand=scrollbar.set)
            self.canvas.create_window(X1-self._s(18),my+self._s(6),anchor="nw",window=scrollbar,width=self._s(14),height=message_h-self._s(12))
            self.message_canvas.bind("<MouseWheel>",lambda e:self.message_canvas.yview_scroll(-1 if e.delta>0 else 1,"units"))
        self._draw_lines(self.canvas,badge_lines,X0+msg_inset,my+message_h+gap,self.f_small,self.theme.badge_color,self.small_lh)
        if h>self.height:
            self.canvas.bind("<MouseWheel>",lambda e:self.canvas.yview_scroll(-1 if e.delta>0 else 1,"units"))
        self._bind_dismiss_clicks()
        return bx,by

    def _build_vector(self, area, target_x, target_y, sprite_w, sprite_h,
                      header, message, sub_badge, badge_text, has_icon):
        """Plain vector card (classic theme, or when the frame art is unusable)."""
        sw,sh = area.width,area.height
        title_lh,small_lh,msg_lh = self.title_lh,self.small_lh,self.msg_lh
        candidate_widths = getattr(self, "framed_widths", FRAMED_WIDTHS)
        w = min(candidate_widths[-1], max(self._s(120), sw - 20))
        margin_x = self._s(32)
        inner_w = w - margin_x * 2
        title_x = self._s(84) if has_icon else margin_x
        min_w = self._s(20)
        title_lines = layout_lines(header,max(min_w,w-title_x-self._s(52)),self.f_title.measure,self.emoji_size)
        title_h = len(title_lines)*title_lh if header else 0
        y = max(self._s(66) if has_icon else self._s(26)+title_h,self._s(48),self._s(26)+title_h)
        self.chip_boxes, chips_bottom = self._layout_chips(sub_badge,margin_x,w-margin_x,y)
        y = chips_bottom+self._s(14) if self.chip_boxes else y+self._s(8)
        card_top = y
        badge_lines = layout_lines(badge_text,max(min_w,inner_w-self._s(20)),self.f_small.measure,self.emoji_size) if badge_text else ()
        footer_h = len(badge_lines)*small_lh+self._s(22) if badge_text else self._s(16)
        viewport_limit = min(self._s(360),max(self._s(36),sh-self._s(40)-card_top-footer_h-self._s(24)))
        msg_lines = layout_lines(message,max(min_w,inner_w-self._s(20)),self.f_message.measure,self.emoji_size)
        desired = max(self._s(44),len(msg_lines)*msg_lh+self._s(20))
        self.scrollable = desired>viewport_limit
        if self.scrollable:
            msg_lines = layout_lines(message,max(min_w,inner_w-self._s(38)),self.f_message.measure,self.emoji_size)
            desired = max(self._s(44),len(msg_lines)*msg_lh+self._s(20))
        message_h = min(desired,viewport_limit)
        body_h = card_top+message_h+footer_h
        h = body_h+self._s(24)
        self.width,self.height,self.content_height = w,min(h,max(self._s(80),sh-20)),h
        self.canvas = tk.Canvas(self.window,width=w,height=self.height,bg=BG_TRANSPARENT,highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.configure(scrollregion=(0,0,w,h))
        if h>self.height:
            self.canvas.bind("<MouseWheel>",lambda e:self.canvas.yview_scroll(-1 if e.delta>0 else 1,"units"))
        bx,by,above,_tail_x = self._place(area,w,target_x,target_y,sprite_w,sprite_h)
        offset = 0 if above else self._s(12)
        card_pad = self._s(6)
        _draw_round_rect(self.canvas,card_pad,card_pad+offset,w-card_pad,body_h+offset,self._s(18),
                         fill=self.theme.bg_fill,outline=self.theme.outline_color,width=1.5*self.ui_scale)

        if has_icon:
            _draw_round_rect(self.canvas,self._s(18),self._s(14)+offset,self._s(66),self._s(62)+offset,
                             self._s(12),fill="white",outline=self.theme.chip_outline)
            self.canvas.create_image(self._s(42),self._s(38)+offset,image=self.icon_thumb)
        self._draw_lines(self.canvas,title_lines if header else (),title_x,self._s(22)+offset,self.f_title,self.theme.header_color,title_lh)
        self.canvas.create_oval(w-self._s(46),self._s(14)+offset,w-self._s(20),self._s(40)+offset,fill=self.theme.close_btn_bg,outline="",tags="close_btn")
        self.canvas.create_line(w-self._s(37),self._s(23)+offset,w-self._s(29),self._s(31)+offset,
                                fill=self.theme.close_btn_cross,width=1.5*self.ui_scale,tags="close_btn")
        self.canvas.create_line(w-self._s(29),self._s(23)+offset,w-self._s(37),self._s(31)+offset,
                                fill=self.theme.close_btn_cross,width=1.5*self.ui_scale,tags="close_btn")
        for cx,cy,cw,ch,lines in self.chip_boxes:
            _draw_round_rect(self.canvas,cx,cy+offset,cx+cw,cy+ch+offset,self._s(7),fill=self.theme.chip_fill,outline=self.theme.chip_outline)
            text_w = max((self._line_width(line,self.f_small) for line in lines),default=0)
            pad_left = max(self._s(4),(cw-text_w)//2)
            self._draw_lines(self.canvas,lines,cx+pad_left,cy+self._s(5)+offset,self.f_small,self.theme.chip_text,small_lh)
        card_x = self._s(24)
        _draw_round_rect(self.canvas,card_x,card_top+offset,w-card_x,card_top+message_h+offset,
                         self._s(10),fill=self.theme.inner_card_fill,outline=self.theme.inner_card_outline)
        msg_w = inner_w-(self._s(18) if self.scrollable else 0)
        self.message_canvas = tk.Canvas(self.canvas,width=msg_w,height=message_h-self._s(8),bg=self.theme.inner_card_fill,highlightthickness=0)
        self.canvas.create_window(self._s(32),card_top+self._s(4)+offset,anchor="nw",window=self.message_canvas,width=msg_w,height=message_h-self._s(8))
        self._draw_lines(self.message_canvas,msg_lines,self._s(10),self._s(8),self.f_message,self.theme.text_color,msg_lh)
        self.message_canvas.configure(scrollregion=(0,0,msg_w,desired-self._s(8)))
        if self.scrollable:
            scrollbar = tk.Scrollbar(self.canvas,orient="vertical",command=self.message_canvas.yview)
            self.message_canvas.configure(yscrollcommand=scrollbar.set)
            self.canvas.create_window(w-self._s(42),card_top+self._s(8)+offset,anchor="nw",window=scrollbar,width=self._s(14),height=message_h-self._s(16))
            self.message_canvas.bind("<MouseWheel>",lambda e:self.message_canvas.yview_scroll(-1 if e.delta>0 else 1,"units"))
        self._draw_lines(self.canvas,badge_lines,self._s(32),card_top+message_h+self._s(8)+offset,self.f_small,self.theme.badge_color,small_lh)
        self._bind_dismiss_clicks()
        return bx,by

    def _line_width(self,line,font):
        width,run = 0,""
        for cluster in line:
            if is_emoji(cluster):
                width += font.measure(run)+self.emoji_size
                run = ""
            else:
                run += cluster
        return width+font.measure(run)

    def _draw_lines(self,canvas,lines,x,y,font,color,line_height):
        for row,line in enumerate(lines):
            cx,run = x,""
            def flush():
                nonlocal cx,run
                if run:
                    canvas.create_text(cx,y+row*line_height,text=run,anchor="nw",font=font,fill=color)
                    cx += font.measure(run)
                    run = ""
            for cluster in line:
                if is_emoji(cluster):
                    flush()
                    key = cluster,self.emoji_size
                    if key not in self._emoji_images:
                        photo = ImageTk.PhotoImage(emoji_icon(cluster,self.emoji_size),master=self.window)
                        self._emoji_images[key] = photo
                        self._image_refs.append(photo)
                    canvas.create_image(cx,y+row*line_height+1,anchor="nw",image=self._emoji_images[key])
                    cx += self.emoji_size
                else:
                    run += cluster
            flush()

    def _bind_dismiss_clicks(self):
        for canvas in (self.canvas, self.message_canvas):
            if canvas is self.message_canvas and self.scrollable:
                continue
            canvas.bind("<ButtonPress-1>", self._on_dismiss_press)
            canvas.bind("<ButtonRelease-1>", self.on_bubble_click)

    def _on_dismiss_press(self, event):
        self._pressed_canvas = event.widget
        self._pause_timer()
        return "break"

    def on_bubble_click(self, event):
        pressed, self._pressed_canvas = self._pressed_canvas, None
        if pressed is event.widget and (
            0 <= event.x < pressed.winfo_width() and 0 <= event.y < pressed.winfo_height()
        ):
            self.dismiss()
        else:
            self._resume_timer()
        return "break"

    def dismiss(self):
        if self._closed:
            return
        self._closed = True
        if self.timer:
            try:
                self.window.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        try:
            self.window.withdraw()
        except tk.TclError:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        # Release the art/emoji photos now; the closed bubble may wait for a full gc pass.
        self._image_refs.clear()
        self._emoji_images.clear()
        self.icon_thumb = None
        self._bg_photo = None
        callback,self.on_close = self.on_close,None
        if callback:
            callback()
