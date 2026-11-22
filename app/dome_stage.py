"""app/dome_stage.py — Shared Taipei Dome domain logic, timelines, layouts & trilingual banner.

Single shared module consumed by both Standby (`app/standby.py`) and Desktop (`app/main.py`)
for the two Dome scenes and Eunji's future Taipei Dome solo concert personal effect:
- Scene 1 (`bg_standby_dome_baseball`): synchronized 5-member `dome_baseball_cheer`
  timeline with extended F3 reading frame and programmatically rendered trilingual
  cheering banner (`zh_TW`, `ko`, `en`, no baked text in sprites).
- Scene 2 (`bg_standby_eunji_dome_dream`) & Personal Effect (`special_eunji_dome_dream`):
  shared approved-only `EUNJI_DOME_CONCERT_OUTFITS` sequential playback (`dome_concert_step`)
  with Eunji centered under the spotlight and the other 4 members flanking the audience.
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from app.action_frames import available_actions
from app.platform.layered_surface import LayeredSpriteSurface
from app.platform.win32 import ui_scale
from app.sprite_polish import alpha_bleed, polish_frame
from app.sprites import ALPHA_THRESHOLD

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical Scene & Action Identifiers (shared with sprite registry & UI)
# ---------------------------------------------------------------------------

DOME_BASEBALL_SCENE = "bg_standby_dome_baseball"
DOME_EUNJI_SCENE = "bg_standby_eunji_dome_dream"
DOME_SCENES: frozenset[str] = frozenset({DOME_BASEBALL_SCENE, DOME_EUNJI_SCENE})

DOME_BASEBALL_ACTION = "dome_baseball_cheer"
DOME_FLANK_CHEER_ACTION = "special_cheer_lightstick"
EUNJI_DOME_PERSONAL_ACTION = "special_eunji_dome_dream"

EUNJI_DOME_CONCERT_OUTFITS: tuple[str, ...] = (
    "dome_concert_opening",
    "dome_concert_white_dress",
    "dome_concert_blue_varsity",
    "dome_concert_red_leather",
    "dome_concert_star_jacket",
    "dome_concert_pinstripe",
    "dome_concert_rock_vest",
    "dome_concert_white_tee",
)

DOME_STAGE_MEMBERS: tuple[str, ...] = ("chorong", "bomi", "eunji", "namjoo", "hayoung")
EUNJI_LEFT_FLANK_MEMBERS: tuple[str, ...] = ("chorong", "bomi")
EUNJI_RIGHT_FLANK_MEMBERS: tuple[str, ...] = ("namjoo", "hayoung")
EUNJI_FLANK_MEMBERS: tuple[str, ...] = EUNJI_LEFT_FLANK_MEMBERS + EUNJI_RIGHT_FLANK_MEMBERS

DOME_CONCERT_FRAME_MS = 260
DOME_CONCERT_FRAMES_PER_OUTFIT = 4

# Reference backdrop resolution (16:9).
WALLPAPER_SRC_SIZE: tuple[int, int] = (2752, 1536)


# ---------------------------------------------------------------------------
# Synchronized Dome Baseball Timeline & Trilingual Cheering Copy
# ---------------------------------------------------------------------------

# (frame_idx, duration_ms, bubble_scale)
# F3 ("一人帶30人！！") is intentionally extended (~2.3x F1/F2) for reading comfort
# and synced to Chorong's fiery-eye F3 climax frame.
DOME_BASEBALL_TIMELINE: tuple[tuple[int, int, float], ...] = (
    (0, 650, 0.94),
    (1, 650, 1.00),
    (2, 1500, 1.18),
    (3, 950, 1.00),
)
DOME_BASEBALL_CYCLE_MS: int = sum(dur for _, dur, _ in DOME_BASEBALL_TIMELINE)

DOME_BASEBALL_COPY: dict[str, tuple[str, str, str, str]] = {
    "zh_TW": (
        "準備好了嗎？",
        "大家一起！",
        "一人帶30人！！",
        "APINK ♥ PANDA",
    ),
    "ko": (
        "준비됐나요?",
        "다 같이!",
        "한 명당 30명씩!!",
        "에이핑크 ♥ 판다",
    ),
    "en": (
        "Are you ready?",
        "All together!",
        "Bring 30 people each!!",
        "APINK ♥ PANDA",
    ),
}

_DOME_BUBBLE_BADGES: dict[str, tuple[str, str, str, str]] = {
    "zh_TW": ("TAIPEI DOME", "PANDA CHEER", "CLIMAX ★", "FOREVER ♥"),
    "ko": ("TAIPEI DOME", "PANDA CHEER", "CLIMAX ★", "FOREVER ♥"),
    "en": ("TAIPEI DOME", "PANDA CHEER", "CLIMAX ★", "FOREVER ♥"),
}


def dome_baseball_step(elapsed_ms: float) -> tuple[int, int, float]:
    """Return synchronized `(frame_idx, duration_ms, bubble_scale)` at `elapsed_ms`."""
    pos = max(0.0, float(elapsed_ms)) % float(DOME_BASEBALL_CYCLE_MS)
    acc = 0.0
    for frame_idx, duration_ms, bubble_scale in DOME_BASEBALL_TIMELINE:
        acc += duration_ms
        if pos < acc:
            return frame_idx, duration_ms, bubble_scale
    return DOME_BASEBALL_TIMELINE[-1]


def dome_baseball_text(frame_idx: int, lang: str) -> str:
    """Return the cheering line for `frame_idx` (0..3) and `lang`."""
    lines = DOME_BASEBALL_COPY.get(lang, DOME_BASEBALL_COPY["zh_TW"])
    return lines[int(frame_idx) % len(lines)]


# ---------------------------------------------------------------------------
# Shared Eunji Dream Concert Sequencer (Approved Outfits Only)
# ---------------------------------------------------------------------------

def resolved_eunji_dome_outfits(
    source,
    *,
    available_fn: Callable = available_actions,
) -> tuple[str, ...]:
    """Return approved Eunji concert outfit keys in canonical order.

    `source` may be a `SpriteLibrary` (Desktop / Standby library lookup via
    `available_fn`) or a preloaded `{action: frames}` mapping (Standby cache).
    Never invents or returns unapproved outfit keys.
    """
    if source is None:
        return ()
    if isinstance(source, Mapping):
        return tuple(
            outfit for outfit in EUNJI_DOME_CONCERT_OUTFITS
            if source.get(outfit)
        )
    found = tuple(available_fn(source, "eunji", EUNJI_DOME_CONCERT_OUTFITS))
    found_set = set(found)
    return tuple(outfit for outfit in EUNJI_DOME_CONCERT_OUTFITS if outfit in found_set)


def dome_concert_step(
    elapsed_ms: float,
    outfits: Sequence[str],
    *,
    frame_ms: int = DOME_CONCERT_FRAME_MS,
    frames_per_outfit: int = DOME_CONCERT_FRAMES_PER_OUTFIT,
) -> tuple[str, int]:
    """Return `(outfit_action, local_frame_idx)` cycling approved outfits sequentially."""
    if not outfits:
        raise ValueError("dome_concert_step requires at least one approved outfit")
    fpo = max(1, int(frames_per_outfit))
    step_ms = max(1, int(frame_ms))
    tick = int(max(0.0, float(elapsed_ms)) // step_ms)
    total_ticks = len(outfits) * fpo
    pos = tick % total_ticks
    return outfits[pos // fpo], pos % fpo


def dome_concert_cycle_ms(
    outfits: Sequence[str],
    *,
    frame_ms: int = DOME_CONCERT_FRAME_MS,
    frames_per_outfit: int = DOME_CONCERT_FRAMES_PER_OUTFIT,
) -> int:
    """Total duration in milliseconds of one full pass across all approved outfits."""
    count = max(1, len(outfits))
    return count * max(1, int(frames_per_outfit)) * max(1, int(frame_ms))


# ---------------------------------------------------------------------------
# Font Resolution & Crisp Anti-Tofu Glyph Rendering
# ---------------------------------------------------------------------------

_FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "zh_TW": ("msjhbd.ttc", "msjh.ttc", "NotoSansTC-VF.ttf", "NotoSansHK-VF.ttf", "mingliu.ttc"),
    "ko": ("malgunbd.ttf", "malgun.ttf", "msjhbd.ttc"),
    "en": ("segoeuib.ttf", "msjhbd.ttc", "segoeui.ttf", "malgunbd.ttf", "arialbd.ttf"),
    "symbol": ("seguisym.ttf", "malgunbd.ttf", "msjhbd.ttc", "NotoSansTC-VF.ttf"),
}

_LOADED_FONT_PATHS: dict[str, str | None] = {}
_FONT_OBJ_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_GLYPH_SUPPORT_CACHE: dict[tuple[str, str], bool] = {}


def _font_search_dirs() -> tuple[Path, ...]:
    dirs: list[Path] = []
    windir = os.environ.get("WINDIR")
    if windir:
        dirs.append(Path(windir) / "Fonts")
    dirs.extend((
        Path(r"C:\Windows\Fonts"),
        Path("/usr/share/fonts"),
        Path("/System/Library/Fonts"),
    ))
    return tuple(dirs)


def resolve_font_path(lang: str) -> str | None:
    """Return an existing TTF/TTC font path best suited for `lang`."""
    key = lang if lang in _FONT_CANDIDATES else "zh_TW"
    if key in _LOADED_FONT_PATHS:
        return _LOADED_FONT_PATHS[key]
    candidates = _FONT_CANDIDATES[key] + _FONT_CANDIDATES["zh_TW"] + _FONT_CANDIDATES["ko"]
    dirs = _font_search_dirs()
    for name in candidates:
        for base in dirs:
            path = base / name
            if path.is_file():
                _LOADED_FONT_PATHS[key] = str(path)
                return str(path)
    _LOADED_FONT_PATHS[key] = None
    return None


def _get_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    sz = max(10, int(size))
    if path:
        cache_key = (path, sz)
        cached = _FONT_OBJ_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            font = ImageFont.truetype(path, sz)
            _FONT_OBJ_CACHE[cache_key] = font
            return font
        except Exception:
            pass
    return ImageFont.load_default()


def _font_supports_char(font_path: str | None, ch: str) -> bool:
    """Return True if `font_path` has a non-.notdef glyph for `ch`."""
    if not font_path:
        return False
    if ord(ch) < 128 and ch.isprintable():
        return True
    cache_key = (font_path, ch)
    if cache_key in _GLYPH_SUPPORT_CACHE:
        return _GLYPH_SUPPORT_CACHE[cache_key]
    try:
        font = _get_font(font_path, 24)
        mask = font.getmask(ch)
        notdef = font.getmask("\uffff")
        notdef2 = font.getmask("\ufffe")
        m_bytes = bytes(mask)
        n_bytes = bytes(notdef)
        n2_bytes = bytes(notdef2)
        supported = (
            mask.size[0] > 0
            and mask.size[1] > 0
            and any(b > 0 for b in m_bytes)
            and m_bytes != n_bytes
            and m_bytes != n2_bytes
        )
    except Exception:
        supported = False
    _GLYPH_SUPPORT_CACHE[cache_key] = supported
    return supported


def _pick_font_for_char(primary_path: str | None, symbol_path: str | None, ch: str, size: int):
    if _font_supports_char(primary_path, ch):
        return _get_font(primary_path, size), primary_path
    if _font_supports_char(symbol_path, ch):
        return _get_font(symbol_path, size), symbol_path
    for group in ("ko", "zh_TW", "en", "symbol"):
        cand = resolve_font_path(group)
        if _font_supports_char(cand, ch):
            return _get_font(cand, size), cand
    return _get_font(primary_path or symbol_path, size), None


def _draw_vector_heart(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int],
) -> None:
    """Draw a crisp anti-aliased heart centered around `(cx, cy)` when no glyph exists."""
    r = max(3.0, size * 0.27)
    lx = cx - r * 0.92
    rx = cx + r * 0.92
    top_y = cy - r * 0.35
    draw.ellipse((lx - r, top_y - r, lx + r, top_y + r), fill=fill)
    draw.ellipse((rx - r, top_y - r, rx + r, top_y + r), fill=fill)
    draw.polygon(
        [
            (lx - r * 0.95, top_y + r * 0.25),
            (rx + r * 0.95, top_y + r * 0.25),
            (cx, cy + r * 2.15),
        ],
        fill=fill,
    )


def _draw_vector_star(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    fill: tuple[int, int, int, int],
) -> None:
    """Draw a crisp 5-pointed star centered around `(cx, cy)` without font glyph dependency."""
    outer_r = max(3.0, size * 0.44)
    inner_r = outer_r * 0.42
    pts: list[tuple[float, float]] = []
    for k in range(10):
        ang = -math.pi / 2.0 + k * (math.pi / 5.0)
        r = outer_r if k % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _measure_run_segments(
    text: str,
    primary_path: str | None,
    symbol_path: str | None,
    size: int,
) -> tuple[list[tuple[str, object, str | None, int, int]], int, int]:
    """Split `text` into per-glyph/run items supporting mixed CJK/Hangul/ASCII/♥/★."""
    items: list[tuple[str, object, str | None, int, int]] = []
    total_w = 0
    max_h = max(12, int(round(size * 1.18)))
    for ch in text:
        if ch == "♥":
            heart_w = max(12, int(round(size * 0.95)))
            items.append((ch, None, "heart", heart_w, max_h))
            total_w += heart_w
            continue
        if ch == "★":
            star_w = max(9, int(round(size * 0.92)))
            items.append((ch, None, "star", star_w, max_h))
            total_w += star_w
            continue
        fnt, resolved = _pick_font_for_char(primary_path, symbol_path, ch, size)
        if ch == " ":
            adv = max(4, int(round(size * 0.32)))
            items.append((ch, fnt, None, adv, max_h))
            total_w += adv
            continue
        try:
            bbox = fnt.getbbox(ch)
            adv = max(int(round(fnt.getlength(ch))), (bbox[2] - bbox[0]) if bbox else size)
            h = (bbox[3] - bbox[1]) if bbox else max_h
        except Exception:
            adv = max(8, size // 2)
            h = max_h
        if resolved is None and ord(ch) > 127:
            adv = max(10, int(round(size * 0.65)))
        items.append((ch, fnt, None, adv, h))
        total_w += adv
        max_h = max(max_h, h)
    return items, max(1, total_w), max_h


def _wrap_text_to_width(
    text: str,
    primary_path: str | None,
    symbol_path: str | None,
    size: int,
    max_text_w: int,
) -> list[str]:
    """Wrap `text` cleanly into lines not exceeding `max_text_w`."""
    _, full_w, _ = _measure_run_segments(text, primary_path, symbol_path, size)
    if full_w <= max_text_w:
        return [text]

    # Prefer word wrapping for space-delimited strings, char wrapping for CJK/Hangul.
    tokens = text.split(" ") if " " in text else list(text)
    joiner = " " if " " in text else ""
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        cand = f"{cur}{joiner}{tok}" if cur else tok
        _, cand_w, _ = _measure_run_segments(cand, primary_path, symbol_path, size)
        if cand_w <= max_text_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)

    # Guard against single long unspaced word overflow.
    final_lines: list[str] = []
    for line in lines:
        _, lw, _ = _measure_run_segments(line, primary_path, symbol_path, size)
        if lw <= max_text_w or len(line) <= 1:
            final_lines.append(line)
            continue
        sub = ""
        for ch in line:
            cand = sub + ch
            _, cw, _ = _measure_run_segments(cand, primary_path, symbol_path, size)
            if cw <= max_text_w or not sub:
                sub = cand
            else:
                final_lines.append(sub)
                sub = ch
        if sub:
            final_lines.append(sub)
    return final_lines or [text]


# Frame visual styles: (card_fill, border_outer, border_inner, text_fill, heart_fill, badge_fill, badge_fg)
_BUBBLE_PALETTES: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("#fff8fb", "#ff84b8", "#ffd4e6", "#5b193c", "#ff2b7a", "#ff84b8", "#ffffff"),
    ("#fff5fa", "#ff62a5", "#ffc6de", "#531336", "#ff2572", "#ff5c9f", "#ffffff"),
    ("#fff1f7", "#ff297b", "#ffd700", "#7c0a3e", "#ff1468", "#ff297b", "#fff9d6"),
    ("#fff6fa", "#ff5fa2", "#ffc7e1", "#5b163d", "#ff1f75", "#ff5fa2", "#ffffff"),
)


def _hex_rgba(hx: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hx.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), max(0, min(255, alpha))


def render_dome_bubble_pil(
    frame_idx: int,
    lang: str,
    *,
    dpi_scale: float = 1.0,
    anim_scale: float = 1.0,
    max_width: int = 560,
    max_height: int | None = None,
    binary_alpha: bool = False,
    text_override: str | None = None,
) -> Image.Image:
    """Render the synchronized Dome cheering banner as a crisp Pillow RGBA image.

    - Supports `zh_TW`, `ko`, `en` and `♥` cleanly without tofu fallback.
    - `binary_alpha=False` yields smooth RGBA anti-aliased drop-shadow for Standby Canvas.
    - `binary_alpha=True` yields crisp binary alpha (`0` or `255`) with opaque solid fill
      so Windows `-transparentcolor #ff00fe` desktop overlays never show pink fringe.
    """
    idx = int(frame_idx) % 4
    eff_lang = lang if lang in DOME_BASEBALL_COPY else "zh_TW"
    text = text_override if text_override is not None else dome_baseball_text(idx, eff_lang)
    badge = _DOME_BUBBLE_BADGES.get(eff_lang, _DOME_BUBBLE_BADGES["zh_TW"])[idx]

    primary_path = resolve_font_path(eff_lang)
    symbol_path = resolve_font_path("symbol")
    ui_path = resolve_font_path("en") or primary_path

    scale = max(0.65, float(dpi_scale)) * max(0.75, float(anim_scale))
    lim_w = max(140, int(max_width))
    lim_h = max(24, int(max_height)) if max_height is not None else 9999

    pal = _BUBBLE_PALETTES[idx]
    card_fill = _hex_rgba(pal[0], 255)
    border_outer = _hex_rgba(pal[1], 255)
    border_inner = _hex_rgba(pal[2], 255)
    text_fill = _hex_rgba(pal[3], 255)
    heart_fill = _hex_rgba(pal[4], 255)
    badge_fill = _hex_rgba(pal[5], 255)
    badge_fg = _hex_rgba(pal[6], 255)

    # Iteratively fit font size & padding within max_width / max_height bounds.
    base_font_px = max(16, int(round((24 if idx == 2 else 21) * scale)))
    chosen = None
    for shrink in (1.0, 0.88, 0.76, 0.66, 0.56):
        font_px = max(13, int(round(base_font_px * shrink)))
        badge_px = max(9, int(round(10.5 * scale * shrink)))
        pad_x = max(14, int(round(22 * scale * shrink)))
        pad_y = max(10, int(round(13 * scale * shrink)))
        tail_h = max(8, int(round(12 * scale * shrink)))
        shadow_pad = 0 if binary_alpha else max(4, int(round(6 * scale * shrink)))
        line_gap = max(4, int(round(5 * scale * shrink)))
        badge_gap = max(4, int(round(6 * scale * shrink)))

        avail_text_w = max(80, lim_w - 2 * pad_x - 2 * shadow_pad)
        lines = _wrap_text_to_width(text, primary_path, symbol_path, font_px, avail_text_w)
        measured_lines = [_measure_run_segments(ln, primary_path, symbol_path, font_px) for ln in lines]
        text_w = max((lw for _, lw, _ in measured_lines), default=40)
        line_hs = [lh for _, _, lh in measured_lines]
        text_h = sum(line_hs) + line_gap * max(0, len(lines) - 1)

        badge_items, badge_text_w, badge_text_h = _measure_run_segments(
            badge, ui_path, symbol_path, badge_px
        )
        badge_pad_x = max(8, int(round(10 * scale * shrink)))
        badge_pad_y = max(3, int(round(4 * scale * shrink)))
        badge_box_w = badge_text_w + 2 * badge_pad_x
        badge_box_h = badge_text_h + 2 * badge_pad_y

        card_w = min(lim_w - 2 * shadow_pad, max(badge_box_w + 2 * pad_x, text_w + 2 * pad_x))
        card_h = pad_y + badge_box_h + badge_gap + text_h + pad_y
        total_w = card_w + 2 * shadow_pad
        total_h = card_h + tail_h + 2 * shadow_pad
        chosen = (
            font_px, badge_px, pad_x, pad_y, tail_h, shadow_pad, line_gap, badge_gap,
            lines, measured_lines, line_hs, badge_items, badge_text_w, badge_text_h,
            badge_box_w, badge_box_h, card_w, card_h, total_w, total_h,
        )
        if total_w <= lim_w and total_h <= lim_h:
            break

    (
        font_px, badge_px, pad_x, pad_y, tail_h, shadow_pad, line_gap, badge_gap,
        lines, measured_lines, line_hs, badge_items, badge_text_w, badge_text_h,
        badge_box_w, badge_box_h, card_w, card_h, total_w, total_h,
    ) = chosen

    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx0, cy0 = shadow_pad, shadow_pad
    cx1, cy1 = cx0 + card_w, cy0 + card_h
    radius = max(12, min(card_h // 2 - 2, int(round(20 * scale))))
    center_x = total_w / 2.0

    # Soft outer stadium glow / drop shadow (Standby RGBA mode only).
    if not binary_alpha:
        glow_alpha = 72 if idx == 2 else 46
        glow_col = _hex_rgba(pal[1], glow_alpha)
        for expand in (4, 2):
            draw.rounded_rectangle(
                (cx0 - expand, cy0 - expand + 2, cx1 + expand, cy1 + expand + 2),
                radius=radius + expand,
                fill=(glow_col[0], glow_col[1], glow_col[2], glow_alpha // expand),
            )

    # Downward center tail pointing toward the 5 pandas without touching them.
    tail_half_w = max(8, int(round(11 * scale)))
    tail_tip_y = cy1 + tail_h - 1
    draw.polygon(
        [
            (center_x - tail_half_w - 2, cy1 - 3),
            (center_x + tail_half_w + 2, cy1 - 3),
            (center_x, tail_tip_y),
        ],
        fill=border_outer,
    )

    # Outer accent border + card body + subtle inner rim.
    border_w = max(2, int(round((3.4 if idx == 2 else 2.6) * scale)))
    draw.rounded_rectangle(
        (cx0, cy0, cx1, cy1),
        radius=radius,
        fill=card_fill,
        outline=border_outer,
        width=border_w,
    )
    inner_inset = max(3, border_w + 1)
    if card_w > 2 * inner_inset + 8 and card_h > 2 * inner_inset + 8:
        draw.rounded_rectangle(
            (cx0 + inner_inset, cy0 + inner_inset, cx1 - inner_inset, cy1 - inner_inset),
            radius=max(6, radius - inner_inset),
            outline=border_inner,
            width=1,
        )

    # Re-fill interior tail triangle so border splits seamlessly into the bubble body.
    draw.polygon(
        [
            (center_x - tail_half_w + 2, cy1 - border_w - 1),
            (center_x + tail_half_w - 2, cy1 - border_w - 1),
            (center_x, max(cy1 + 1, tail_tip_y - border_w - 1)),
        ],
        fill=card_fill,
    )

    # Top stadium pill badge ("CLIMAX ★", "TAIPEI DOME", etc.), rendered via per-glyph fallback.
    bx0 = round(center_x - badge_box_w / 2.0)
    by0 = cy0 + pad_y
    draw.rounded_rectangle(
        (bx0, by0, bx0 + badge_box_w, by0 + badge_box_h),
        radius=max(6, badge_box_h // 2),
        fill=badge_fill,
    )
    b_cur_x = round(center_x - badge_text_w / 2.0)
    b_mid_y = by0 + badge_box_h / 2.0
    for ch, fnt, vec_kind, adv, _ in badge_items:
        if vec_kind == "star":
            _draw_vector_star(draw, b_cur_x + adv / 2.0, b_mid_y, badge_px * 0.95, badge_fg)
        elif vec_kind == "heart":
            _draw_vector_heart(draw, b_cur_x + adv / 2.0, b_mid_y, badge_px * 0.92, badge_fg)
        else:
            try:
                gb = fnt.getbbox(ch)
                gh = gb[3] - gb[1]
                gy = round(b_mid_y - gh / 2.0 - gb[1])
            except Exception:
                gy = round(by0 + 2)
            draw.text((b_cur_x, gy), ch, font=fnt, fill=badge_fg)
        b_cur_x += adv

    # Render cheering line(s) centered horizontally, glyph-by-glyph to prevent tofu boxes.
    cur_y = by0 + badge_box_h + badge_gap
    for (items, line_w, line_h) in measured_lines:
        cur_x = round(center_x - line_w / 2.0)
        line_mid_y = cur_y + line_h / 2.0
        for ch, fnt, vec_kind, adv, _ in items:
            if vec_kind == "heart":
                _draw_vector_heart(
                    draw,
                    cur_x + adv / 2.0,
                    line_mid_y,
                    font_px * 0.92,
                    heart_fill,
                )
            elif vec_kind == "star":
                _draw_vector_star(
                    draw,
                    cur_x + adv / 2.0,
                    line_mid_y,
                    font_px * 0.92,
                    text_fill,
                )
            else:
                try:
                    gb = fnt.getbbox(ch)
                    gh = gb[3] - gb[1]
                    gy = round(line_mid_y - gh / 2.0 - gb[1])
                except Exception:
                    gy = round(cur_y)
                draw.text((cur_x, gy), ch, font=fnt, fill=text_fill)
            cur_x += adv
        cur_y += line_h + line_gap

    if total_h > lim_h:
        ratio = max(0.20, lim_h / float(total_h))
        nw = max(48, int(round(total_w * ratio)))
        nh = max(20, min(lim_h, int(round(total_h * ratio))))
        resample = Image.NEAREST if binary_alpha else Image.LANCZOS
        img = img.resize((nw, nh), resample)

    if binary_alpha:
        img = _binary_alpha(img)

    return img


def _binary_alpha(img: Image.Image) -> Image.Image:
    mask = img.getchannel("A").point((0,) * 128 + (255,) * 128)
    opaque = img.copy()
    opaque.putalpha(255)
    return Image.composite(opaque, Image.new("RGBA", img.size), mask)


# ---------------------------------------------------------------------------
# Clearance, Safe Positioning & Stage Geometry Helpers
# ---------------------------------------------------------------------------

def available_dome_bubble_space(
    member_boxes: Sequence[tuple[int, int, int, int]],
    bounds: tuple[int, int, int, int],
    *,
    gap: int = 16,
    top_safe_y: int | None = None,
    side_margin: int = 16,
) -> tuple[int, int]:
    """Return `(max_width, max_height)` safe above members & below top UI chrome."""
    bx0, by0, bx1, by1 = bounds
    max_w = max(140, (bx1 - bx0) - 2 * side_margin)
    eff_top = max(by0 + side_margin, int(top_safe_y)) if top_safe_y is not None else (by0 + side_margin)
    if member_boxes:
        min_top = min(box[1] for box in member_boxes)
    else:
        min_top = by0 + int((by1 - by0) * 0.65)
    max_h = max(24, min_top - gap - eff_top)
    return max_w, max_h


def compute_dome_bubble_rect(
    member_boxes: Sequence[tuple[int, int, int, int]],
    bubble_size: tuple[int, int],
    bounds: tuple[int, int, int, int],
    *,
    gap: int = 16,
    top_safe_y: int | None = None,
    side_margin: int = 16,
) -> tuple[int, int, int, int]:
    """Place the bubble centered cleanly above all active member sprites.

    Guarantees:
    - Horizontal bounds inside `[bounds[0] + side_margin, bounds[2] - side_margin]`.
    - Vertical bottom edge strictly `<= min_member_top_y - gap` whenever overhead space permits
      (never covers pandas' eyes, caps, moles, sweet potatoes, or lightsticks).
    - Vertical top edge strictly `>= top_safe_y` (below Standby UI hints / clock cards).
    """
    bx0, by0, bx1, by1 = bounds
    bw = max(40, int(bubble_size[0]))
    bh = max(24, int(bubble_size[1]))
    eff_top = max(by0 + side_margin, int(top_safe_y)) if top_safe_y is not None else (by0 + side_margin)

    if member_boxes:
        min_x = min(box[0] for box in member_boxes)
        max_x = max(box[2] for box in member_boxes)
        center_x = (min_x + max_x) / 2.0
        min_top_y = min(box[1] for box in member_boxes)
    else:
        center_x = (bx0 + bx1) / 2.0
        min_top_y = by0 + int((by1 - by0) * 0.65)

    max_allowed_bottom = min_top_y - gap
    avail_h = max_allowed_bottom - eff_top
    if avail_h >= 28 and bh > avail_h:
        ratio = avail_h / float(bh)
        bw = max(60, int(round(bw * ratio)))
        bh = max(28, avail_h)

    avail_w = max(80, (bx1 - bx0) - 2 * side_margin)
    if bw > avail_w:
        ratio = avail_w / float(bw)
        bw = avail_w
        bh = max(24, int(round(bh * ratio)))

    x = int(round(center_x - bw / 2.0))
    min_bx = bx0 + side_margin
    max_bx = max(min_bx, bx1 - side_margin - bw)
    x = max(min_bx, min(max_bx, x))

    y = max_allowed_bottom - bh
    if y < eff_top:
        y = eff_top
        if avail_h >= 24 and y + bh > max_allowed_bottom:
            bh = max(24, max_allowed_bottom - y)

    return x, y, bw, bh


def map_cover_point(
    nx: float,
    ny: float,
    canvas_w: int,
    canvas_h: int,
    src_size: tuple[int, int] = WALLPAPER_SRC_SIZE,
) -> tuple[float, float]:
    """Map normalized `[0..1]` backdrop coordinates through Standby cover-crop transform."""
    src_w, src_h = max(1, src_size[0]), max(1, src_size[1])
    scale = max(canvas_w / float(src_w), canvas_h / float(src_h))
    disp_w = src_w * scale
    disp_h = src_h * scale
    ox = (canvas_w - disp_w) / 2.0
    oy = (canvas_h - disp_h) / 2.0
    return ox + nx * disp_w, oy + ny * disp_h


def _spread_centers_non_overlapping(
    desired: list[float],
    widths: list[int],
    min_x: float,
    max_x: float,
    min_gap: float,
) -> list[int]:
    """Adjust horizontal centers in sorted order to avoid bounding-box overlap."""
    n = len(desired)
    if n == 0:
        return []
    if n == 1:
        half0 = widths[0] / 2.0
        return [int(round(max(min_x + half0, min(max_x - half0, desired[0]))))]

    usable = max(1.0, max_x - min_x)
    total_w = sum(widths)
    free = usable - total_w
    if free < 0.0:
        start = min_x + widths[0] / 2.0
        end = max(start, max_x - widths[-1] / 2.0)
        step = (end - start) / max(1, n - 1)
        return [int(round(start + i * step)) for i in range(n)]

    eff_gap = min(min_gap, free / max(1, n - 1))
    centers = list(desired)
    for i in range(n):
        half_i = widths[i] / 2.0
        centers[i] = max(min_x + half_i, min(max_x - half_i, centers[i]))
    # Left-to-right push to enforce minimum pairwise spacing
    for i in range(1, n):
        req = centers[i - 1] + (widths[i - 1] + widths[i]) / 2.0 + eff_gap
        if centers[i] < req:
            centers[i] = req
    # Preserve group midpoint when widening spacing (avoids right-shift bias)
    orig_mid = (desired[0] + desired[-1]) / 2.0
    spread_mid = (centers[0] + centers[-1]) / 2.0
    if abs(spread_mid - orig_mid) > 0.5:
        shift = spread_mid - orig_mid
        centers = [c - shift for c in centers]
    # Right boundary clamp and cascade left
    last_half = widths[-1] / 2.0
    if centers[-1] > max_x - last_half:
        centers[-1] = max_x - last_half
        for i in range(n - 2, -1, -1):
            req = centers[i + 1] - (widths[i] + widths[i + 1]) / 2.0 - eff_gap
            if centers[i] > req:
                centers[i] = req
    # Left boundary clamp and cascade right (guaranteed within max_x since eff_gap fits)
    first_half = widths[0] / 2.0
    if centers[0] < min_x + first_half:
        centers[0] = min_x + first_half
        for i in range(1, n):
            req = centers[i - 1] + (widths[i - 1] + widths[i]) / 2.0 + eff_gap
            if centers[i] < req:
                centers[i] = req
    return [int(round(c)) for c in centers]


def dome_baseball_standby_slots(
    canvas_w: int,
    canvas_h: int,
    member_sizes: Mapping[str, tuple[int, int]],
    *,
    members: Sequence[str] = DOME_STAGE_MEMBERS,
    ui_scale_factor: float = 1.0,
) -> dict[str, tuple[int, int]]:
    """Compute non-overlapping `(center_x, feet_y)` slots across the stadium floor."""
    k = max(0.8, float(ui_scale_factor))
    margin = max(16.0, 24.0 * k)
    bottom_pad = max(24.0, 32.0 * k)

    # Pitcher's plate / first-to-third baseline in the approved backdrop.
    norm_xs = (0.24, 0.37, 0.50, 0.63, 0.76)
    norm_ys = (0.7708,) * 5

    widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in members]
    desired_x: list[float] = []
    feet_y: list[int] = []
    for idx, _m in enumerate(members):
        nx = norm_xs[idx % len(norm_xs)]
        ny = norm_ys[idx % len(norm_ys)]
        cx, fy = map_cover_point(nx, ny, canvas_w, canvas_h)
        desired_x.append(cx)
        # Reserve headroom without adding the sprite height to a floor fraction:
        # that used to push tall sprites down to the foreground again.
        mh = max(48, member_sizes.get(_m, (150, 150))[1])
        min_fy = int(round(max(canvas_h * 0.56, mh + 40 * k)))
        max_fy = max(min_fy, int(round(canvas_h - bottom_pad)))
        feet_y.append(max(min_fy, min(max_fy, int(round(fy)))))

    min_gap = max(12.0, 18.0 * k)
    centers_x = _spread_centers_non_overlapping(
        desired_x, widths, margin, max(margin + 100.0, canvas_w - margin), min_gap
    )
    return {m: (centers_x[i], feet_y[i]) for i, m in enumerate(members)}


def eunji_dome_standby_slots(
    canvas_w: int,
    canvas_h: int,
    member_sizes: Mapping[str, tuple[int, int]],
    *,
    ui_scale_factor: float = 1.0,
) -> dict[str, tuple[int, int]]:
    """Compute Spotlight stage slot for Eunji + lower audience flank slots for 4 members.

    Enforces:
    - Eunji centered in the circular front spotlight platform (`nx=0.50, ny=0.73`).
    - Chorong & Bomi in front-left audience flank; Namjoo & Hayoung in front-right audience flank.
    - Flanks strictly lower than Eunji (`flank_feet_y > eunji_feet_y`) and outside center stage.
    - Zero bounding-box overlap among any pair of members.
    """
    k = max(0.8, float(ui_scale_factor))
    margin = max(16.0, 24.0 * k)
    bottom_pad = max(18.0, 26.0 * k)

    ew, eh = member_sizes.get("eunji", (160, 160))
    ec_raw, ef_raw = map_cover_point(0.50, 0.73, canvas_w, canvas_h)
    eunji_cx = int(round(max(margin + ew / 2.0, min(canvas_w - margin - ew / 2.0, ec_raw))))
    min_eunji_fy = int(round(max(eh + 40 * k, canvas_h * 0.56)))
    max_eunji_fy = int(round(min(canvas_h - bottom_pad - max(36.0, 44.0 * k), canvas_h * 0.80)))
    eunji_fy = int(round(max(min_eunji_fy, min(max(min_eunji_fy, max_eunji_fy), ef_raw))))

    stage_corridor_half = max(ew * 0.56 + 14.0 * k, min(canvas_w * 0.11, ew * 0.72 + 12.0 * k))
    corridor_gap = max(10.0, 14.0 * k)
    left_limit_max = min(
        eunji_cx - ew / 2.0 - corridor_gap,
        max(margin + 48.0, eunji_cx - stage_corridor_half),
    )
    right_limit_min = max(
        eunji_cx + ew / 2.0 + corridor_gap,
        min(canvas_w - margin - 48.0, eunji_cx + stage_corridor_half),
    )

    flank_gap = max(12.0, 16.0 * k)
    left_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in EUNJI_LEFT_FLANK_MEMBERS]
    left_desired = [
        min(left_limit_max - left_widths[1] - flank_gap - left_widths[0] / 2.0,
            map_cover_point(0.18, 0.90, canvas_w, canvas_h)[0]),
        min(left_limit_max - left_widths[1] / 2.0,
            map_cover_point(0.32, 0.87, canvas_w, canvas_h)[0]),
    ]
    left_xs = _spread_centers_non_overlapping(left_desired, left_widths, margin, max(margin + 48.0, left_limit_max), flank_gap)

    right_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in EUNJI_RIGHT_FLANK_MEMBERS]
    right_desired = [
        max(right_limit_min + right_widths[0] / 2.0,
            map_cover_point(0.68, 0.87, canvas_w, canvas_h)[0]),
        max(right_limit_min + right_widths[0] + flank_gap + right_widths[1] / 2.0,
            map_cover_point(0.82, 0.90, canvas_w, canvas_h)[0]),
    ]
    right_xs = _spread_centers_non_overlapping(
        right_desired, right_widths, min(canvas_w - margin - 48.0, right_limit_min), canvas_w - margin, flank_gap
    )

    flank_min_fy = eunji_fy + max(28, int(round(36 * k)))
    flank_max_fy = max(flank_min_fy, int(round(canvas_h - bottom_pad)))

    def _flank_y(ny: float) -> int:
        raw_y = map_cover_point(0.5, ny, canvas_w, canvas_h)[1]
        return int(round(max(flank_min_fy, min(flank_max_fy, raw_y))))

    slots: dict[str, tuple[int, int]] = {"eunji": (eunji_cx, eunji_fy)}
    for idx, member in enumerate(EUNJI_LEFT_FLANK_MEMBERS):
        slots[member] = (left_xs[idx], _flank_y(0.915 if idx == 0 else 0.885))
    for idx, member in enumerate(EUNJI_RIGHT_FLANK_MEMBERS):
        slots[member] = (right_xs[idx], _flank_y(0.885 if idx == 0 else 0.915))
    return slots


def compute_desktop_baseball_slots(
    area_left: int,
    area_top: int,
    area_right: int,
    area_bottom: int,
    member_sizes: Mapping[str, tuple[int, int]],
    *,
    anchor_cx: int | None = None,
    ui_scale_factor: float = 1.0,
) -> dict[str, tuple[int, int]]:
    """Compute non-overlapping `(top_left_x, top_left_y)` slots along work area bottom."""
    k = max(0.8, float(ui_scale_factor))
    margin = max(12.0, 16.0 * k)
    min_gap = max(12.0, 18.0 * k)
    widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in DOME_STAGE_MEMBERS]
    heights = [max(48, member_sizes.get(m, (150, 150))[1]) for m in DOME_STAGE_MEMBERS]

    mid_x = float(anchor_cx) if anchor_cx is not None else (area_left + area_right) / 2.0
    step = max(widths) + min_gap
    desired = [mid_x + (idx - 2) * step for idx in range(len(DOME_STAGE_MEMBERS))]
    centers_x = _spread_centers_non_overlapping(
        desired, widths, area_left + margin, area_right - margin, min_gap
    )
    out: dict[str, tuple[int, int]] = {}
    for idx, member in enumerate(DOME_STAGE_MEMBERS):
        w, h = widths[idx], heights[idx]
        x = int(round(centers_x[idx] - w / 2.0))
        y = max(area_top + 120, area_bottom - h)
        out[member] = (x, y)
    return out


def compute_desktop_eunji_slots(
    area_left: int,
    area_top: int,
    area_right: int,
    area_bottom: int,
    member_sizes: Mapping[str, tuple[int, int]],
    *,
    ui_scale_factor: float = 1.0,
) -> dict[str, tuple[int, int]]:
    """Compute non-overlapping `(top_left_x, top_left_y)` for Desktop Eunji Dome Dream."""
    k = max(0.8, float(ui_scale_factor))
    margin = max(12.0, 16.0 * k)
    ew, eh = member_sizes.get("eunji", (160, 160))
    area_mid = (area_left + area_right) / 2.0
    eunji_cx = max(area_left + margin + ew / 2.0, min(area_right - margin - ew / 2.0, area_mid))
    stage_lift = max(24, int(round(30 * k)))
    eunji_y = max(area_top + 48, area_bottom - eh - stage_lift)

    corridor_gap = max(10.0, 14.0 * k)
    corridor_half = max(ew * 0.5 + corridor_gap, ew * 0.55 + max(18.0, 24.0 * k))
    flank_gap = max(12.0, 16.0 * k)
    left_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in EUNJI_LEFT_FLANK_MEMBERS]
    right_widths = [max(48, member_sizes.get(m, (150, 150))[0]) for m in EUNJI_RIGHT_FLANK_MEMBERS]

    # Never push flanks across Eunji's center stage corridor (`eunji_cx -/+ corridor_half`).
    left_max_x = max(
        area_left + margin + 48.0,
        min(eunji_cx - ew / 2.0 - corridor_gap, eunji_cx - corridor_half),
    )
    left_desired = [
        left_max_x - left_widths[1] - flank_gap - left_widths[0] / 2.0,
        left_max_x - left_widths[1] / 2.0,
    ]
    left_xs = _spread_centers_non_overlapping(
        left_desired, left_widths, area_left + margin, left_max_x, flank_gap
    )

    right_min_x = min(
        area_right - margin - 48.0,
        max(eunji_cx + ew / 2.0 + corridor_gap, eunji_cx + corridor_half),
    )
    right_desired = [
        right_min_x + right_widths[0] / 2.0,
        right_min_x + right_widths[0] + flank_gap + right_widths[1] / 2.0,
    ]
    right_xs = _spread_centers_non_overlapping(
        right_desired, right_widths, right_min_x, area_right - margin, flank_gap
    )

    out: dict[str, tuple[int, int]] = {"eunji": (int(round(eunji_cx - ew / 2.0)), int(eunji_y))}
    for idx, member in enumerate(EUNJI_LEFT_FLANK_MEMBERS):
        w, h = member_sizes.get(member, (150, 150))
        out[member] = (int(round(left_xs[idx] - w / 2.0)), max(area_top + 48, area_bottom - h))
    for idx, member in enumerate(EUNJI_RIGHT_FLANK_MEMBERS):
        w, h = member_sizes.get(member, (150, 150))
        out[member] = (int(round(right_xs[idx] - w / 2.0)), max(area_top + 48, area_bottom - h))
    return out


# ---------------------------------------------------------------------------
# Visible Bounding Box & Transparent `Toplevel` Helpers
# ---------------------------------------------------------------------------

def visible_alpha_bbox_in_screen(
    pil_img: Image.Image | None,
    center_x: int,
    feet_y: int,
    anchor: tuple[int, int],
    *,
    width: int | None = None,
    height: int | None = None,
) -> tuple[int, int, int, int]:
    """Return screen `(x0, y0, x1, y1)` around non-transparent pixels of a sprite frame."""
    if pil_img is not None and getattr(pil_img, "mode", None) == "RGBA":
        top_left_x = int(round(center_x - anchor[0]))
        top_left_y = int(round(feet_y - anchor[1]))
        bbox = pil_img.getchannel("A").getbbox()
        if bbox is not None:
            return (
                top_left_x + bbox[0],
                top_left_y + bbox[1],
                top_left_x + bbox[2],
                top_left_y + bbox[3],
            )
        return (top_left_x, top_left_y, top_left_x + pil_img.width, top_left_y + pil_img.height)
    w = width or 150
    h = height or 150
    top_left_x = int(round(center_x - anchor[0]))
    top_left_y = int(round(feet_y - anchor[1]))
    return (top_left_x, top_left_y, top_left_x + w, top_left_y + h)


def cancel_after_safely(widget: tk.Misc | None, timer_id: str | None) -> None:
    """Cancel a Tk `after` timer without raising on already-destroyed widgets."""
    if widget is None or not timer_id:
        return
    try:
        widget.after_cancel(timer_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Desktop Multi-Member Dome Preview Controller (419 / Musical style)
# ---------------------------------------------------------------------------

BG_TRANSPARENT = "#ff00fe"


class DomeDesktopPreview:
    """Synchronized Desktop preview for Taipei Dome Baseball & Eunji Concert Dream.

    Shares `dome_baseball_step`, `resolved_eunji_dome_outfits`, `dome_concert_step`,
    `render_dome_bubble_pil`, and `compute_dome_bubble_rect` directly with Standby
    while loading actions strictly via `action_frames.load_exact_action` / `available_actions`.
    """

    def __init__(
        self,
        pet,
        mode: str,
        *,
        load_action_fn: Callable,
        available_fn: Callable = available_actions,
        duration_ms: int = 15000,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        if mode not in ("baseball", "eunji_dream"):
            raise ValueError(f"unsupported DomeDesktopPreview mode: {mode!r}")
        self.pet = pet
        self.mode = mode
        self._load_action_fn = load_action_fn
        self._available_fn = available_fn
        self._duration_ms = max(1000, int(duration_ms))
        self._on_done = on_done
        self.closed = False
        self._t0 = time.monotonic()
        self._after_ids: dict[str, str] = {}
        self.actor_windows: dict[str, tk.Toplevel] = {}
        self.actor_surfaces: dict[str, LayeredSpriteSurface] = {}
        self._actor_canvases: dict[str, tuple[tk.Canvas, int]] = {}
        self.bubble_window: tk.Toplevel | None = None
        self.bubble_surface: LayeredSpriteSurface | None = None
        self._bubble_canvas: tk.Canvas | None = None
        self._bubble_img_id: int | None = None
        self._bubble_photo: ImageTk.PhotoImage | None = None
        self._bubble_size: tuple[int, int] = (240, 96)
        self._bubble_cache_key: tuple | None = None
        self._actor_presented: dict[str, tuple[int, int, int]] = {}
        self._bubble_presented: tuple[int, int, int] | None = None
        self._member_actions: dict[str, dict[str, dict]] = {m: {} for m in DOME_STAGE_MEMBERS}
        self._eunji_outfits: tuple[str, ...] = ()

        self.area = pet.desktop.work_area_for_point(
            pet.x + pet.width // 2, pet.y + pet.height // 2
        )
        try:
            self.k = float(ui_scale(pet.root))
        except Exception:
            self.k = 1.0
        raw_ulw = getattr(pet, "_use_ulw", None)
        if raw_ulw is None:
            raw_env = os.environ.get("PANDA_DISABLE_ULW", "").strip().lower()
            self._use_ulw = (sys.platform == "win32") and (raw_env not in ("1", "true", "yes", "on"))
        else:
            self._use_ulw = bool(raw_ulw) and (sys.platform == "win32")
        target_binary = not self._use_ulw
        base_sprites = getattr(pet, "guest_sprites", None) or pet.sprites
        self._sprites = (
            base_sprites.with_binary_alpha(target_binary)
            if getattr(base_sprites, "binary_alpha", True) != target_binary and hasattr(base_sprites, "with_binary_alpha")
            else base_sprites
        )

        self._prepare_member_assets()
        self._fit_member_assets_to_work_area()
        self.slots = self._compute_slots()
        try:
            self._spawn_windows()
            self._render_step(schedule_next=True)
        except Exception:
            self.close(restore_pet=False)
            raise
        try:
            self._after_ids["done"] = pet.root.after(self._duration_ms, self.close)
        except tk.TclError:
            self._after_ids.pop("done", None)

    def _load_member_action(self, member: str, action: str) -> dict | None:
        cached = self._member_actions[member].get(action)
        if cached is not None:
            return cached
        loaded = self._load_action_fn(self._sprites, member, action)
        if loaded is None or not getattr(loaded, "frames", None):
            return None
        pil_frames = list(loaded.frames)
        tk_frames = [ImageTk.PhotoImage(im, master=self.pet.root) for im in pil_frames]
        w = pil_frames[0].width
        h = pil_frames[0].height
        bboxes = tuple(
            im.getchannel("A").getbbox() if getattr(im, "mode", None) == "RGBA" else None
            for im in pil_frames
        )
        entry = {
            "pil": pil_frames,
            "tk": tk_frames,
            "w": w,
            "h": h,
            "anchor": (w // 2, h - max(8, round(12 * self.k))),
            "offset": tuple(getattr(loaded, "offset", (0, 0))),
            "alpha_bboxes": bboxes,
        }
        self._member_actions[member][action] = entry
        return entry

    def _load_fallback_cheer(self, member: str) -> dict:
        existing = self._member_actions[member].get("__fallback__")
        if existing is not None:
            return existing
        alt = self._load_member_action(member, DOME_FLANK_CHEER_ACTION)
        if alt is not None:
            self._member_actions[member]["__fallback__"] = alt
            return alt
        pil_img = Image.new("RGBA", (self.pet.width, self.pet.height), (0, 0, 0, 0))
        tk_frames: list = []
        pil_frames: list[Image.Image] = []
        try:
            loaded_base = self._sprites.load_member(member, self.pet.root)
            cheer = loaded_base.get("cheer") or loaded_base.get("idle") or []
            tk_frames = list(cheer)
            if callable(getattr(loaded_base, "get_pil", None)):
                pil_frames = list(loaded_base.get_pil("cheer", 1) or loaded_base.get_pil("idle", 1) or [])
        except Exception:
            tk_frames = []
            pil_frames = []
        if not tk_frames:
            tk_frames = [ImageTk.PhotoImage(pil_img, master=self.pet.root)]
        if not pil_frames:
            try:
                pil_frames = [ImageTk.getimage(p) for p in tk_frames]
            except Exception:
                pil_frames = [pil_img] * len(tk_frames)
        fw = tk_frames[0].width() if hasattr(tk_frames[0], "width") else self.pet.width
        fh = tk_frames[0].height() if hasattr(tk_frames[0], "height") else self.pet.height
        entry = {
            "pil": pil_frames,
            "tk": tk_frames,
            "w": fw,
            "h": fh,
            "anchor": (fw // 2, fh),
            "offset": (0, 0),
            "alpha_bboxes": tuple(
                im.getchannel("A").getbbox() if getattr(im, "mode", None) == "RGBA" else None
                for im in pil_frames
            ),
        }
        self._member_actions[member]["__fallback__"] = entry
        return entry

    def _prepare_member_assets(self) -> None:
        if self.mode == "baseball":
            for m in DOME_STAGE_MEMBERS:
                if self._load_member_action(m, DOME_BASEBALL_ACTION) is None:
                    self._load_fallback_cheer(m)
            return
        self._eunji_outfits = resolved_eunji_dome_outfits(
            self._sprites, available_fn=self._available_fn
        )
        for outfit in self._eunji_outfits:
            self._load_member_action("eunji", outfit)
        if not any(o in self._member_actions["eunji"] for o in self._eunji_outfits):
            self._load_fallback_cheer("eunji")
        for m in EUNJI_FLANK_MEMBERS:
            if self._load_member_action(m, DOME_FLANK_CHEER_ACTION) is None:
                self._load_fallback_cheer(m)

    def _primary_entry(self, member: str) -> dict:
        if self.mode == "baseball":
            act = self._member_actions[member].get(DOME_BASEBALL_ACTION)
            return act or self._load_fallback_cheer(member)
        if member == "eunji":
            for outfit in self._eunji_outfits:
                act = self._member_actions["eunji"].get(outfit)
                if act is not None:
                    return act
            return self._load_fallback_cheer("eunji")
        return (
            self._member_actions[member].get(DOME_FLANK_CHEER_ACTION)
            or self._load_fallback_cheer(member)
        )

    def _active_entries_for(self, member: str) -> list[dict]:
        actions = self._member_actions.get(member, {})
        if self.mode == "baseball":
            act = actions.get(DOME_BASEBALL_ACTION)
            return [act] if act is not None else [self._primary_entry(member)]
        if member == "eunji":
            out = [actions[o] for o in self._eunji_outfits if o in actions]
            return out if out else [self._primary_entry(member)]
        act = actions.get(DOME_FLANK_CHEER_ACTION)
        return [act] if act is not None else [self._primary_entry(member)]

    def _union_opaque_bbox(self, member: str) -> tuple[int, int, int, int]:
        x0s: list[int] = []
        y0s: list[int] = []
        x1s: list[int] = []
        y1s: list[int] = []
        primary = self._primary_entry(member)
        for entry in self._active_entries_for(member):
            for bb in entry.get("alpha_bboxes") or ():
                if bb is not None:
                    x0s.append(int(bb[0]))
                    y0s.append(int(bb[1]))
                    x1s.append(int(bb[2]))
                    y1s.append(int(bb[3]))
        if not x0s:
            return (0, 0, int(primary["w"]), int(primary["h"]))
        return (min(x0s), min(y0s), max(x1s), max(y1s))

    def _fit_member_assets_to_work_area(self) -> None:
        """Downscale desktop preview frames proportionally on narrow work areas so opaque sprites never overlap."""
        area_w = max(200.0, float(self.area.right - self.area.left))
        margin = max(12.0, 16.0 * self.k)
        if self.mode == "baseball":
            min_gap = max(12.0, 18.0 * self.k)
            avail = max(160.0, area_w - 2.0 * margin - 4.0 * min_gap)
        else:
            corridor_gap = max(10.0, 14.0 * self.k)
            flank_gap = max(12.0, 16.0 * self.k)
            avail = max(160.0, area_w - 2.0 * margin - 2.0 * flank_gap - 2.0 * corridor_gap)

        vis_widths: list[int] = []
        for m in DOME_STAGE_MEMBERS:
            ux0, _uy0, ux1, _uy1 = self._union_opaque_bbox(m)
            vis_widths.append(max(48, ux1 - ux0))
        total_w = float(sum(vis_widths))
        fit = min(1.0, (avail / total_w) * 0.94) if total_w > avail else 1.0
        if self.mode != "baseball":
            # Total width alone is insufficient: the two flanks can have
            # different widths, while Eunji must keep the central corridor.
            # Satisfy each half separately, including both corridor bounds.
            ew = vis_widths[DOME_STAGE_MEMBERS.index("eunji")]
            by_member = dict(zip(DOME_STAGE_MEMBERS, vis_widths))
            for flank in (EUNJI_LEFT_FLANK_MEMBERS, EUNJI_RIGHT_FLANK_MEMBERS):
                flank_width = sum(by_member[m] for m in flank)
                for coefficient, clearance in ((.5, corridor_gap), (.55, max(18.0, 24.0 * self.k))):
                    fit = min(fit, (area_w / 2 - margin - flank_gap - clearance) /
                              (flank_width + coefficient * ew))
        fit = max(.1, fit)
        if fit >= 1.0:
            return
        for m in DOME_STAGE_MEMBERS:
            seen_ids: set[int] = set()
            for entry in list(self._member_actions.get(m, {}).values()):
                if id(entry) in seen_ids:
                    continue
                seen_ids.add(id(entry))
                pil_frames = entry.get("pil")
                if not pil_frames:
                    continue
                polish = bool(getattr(getattr(self.pet, "sprites", None), "polish", True))
                binary_alpha = not getattr(self, "_use_ulw", False)
                scaled_pil = []
                for im in pil_frames:
                    nw_i = max(48, round(im.width * fit))
                    nh_i = max(48, round(im.height * fit))
                    resized = alpha_bleed(im).resize((nw_i, nh_i), Image.LANCZOS)
                    if binary_alpha:
                        resized.putalpha(resized.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0))
                        if polish:
                            resized = polish_frame(resized, nh_i, binary_alpha=True)
                    scaled_pil.append(resized)
                nw, nh = scaled_pil[0].width, scaled_pil[0].height
                entry["pil"] = scaled_pil
                entry["tk"] = [ImageTk.PhotoImage(im, master=self.pet.root) for im in scaled_pil]
                entry["w"] = nw
                entry["h"] = nh
                entry["anchor"] = (nw // 2, nh - max(6, round(12 * self.k * fit)))
                entry["alpha_bboxes"] = tuple(
                    im.getchannel("A").getbbox() if getattr(im, "mode", None) == "RGBA" else None
                    for im in scaled_pil
                )

    def _compute_slots(self) -> dict[str, tuple[int, int]]:
        unions = {m: self._union_opaque_bbox(m) for m in DOME_STAGE_MEMBERS}
        sizes = {
            m: (max(48, ux1 - ux0), max(48, uy1 - uy0))
            for m, (ux0, uy0, ux1, uy1) in unions.items()
        }
        a = self.area
        if self.mode == "baseball":
            vis_slots = compute_desktop_baseball_slots(
                a.left, a.top, a.right, a.bottom, sizes, ui_scale_factor=self.k
            )
        else:
            vis_slots = compute_desktop_eunji_slots(
                a.left, a.top, a.right, a.bottom, sizes, ui_scale_factor=self.k
            )
        return {
            m: (vis_slots[m][0] - unions[m][0], vis_slots[m][1] - unions[m][1])
            for m in DOME_STAGE_MEMBERS
        }

    def _make_transparent_window(
        self,
        w: int,
        h: int,
        x: int,
        y: int,
        *,
        initial_pil: Image.Image | None = None,
    ) -> tuple[tk.Toplevel, tk.Canvas, LayeredSpriteSurface | None]:
        win = tk.Toplevel(self.pet.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        surf: LayeredSpriteSurface | None = None
        if getattr(self, "_use_ulw", False) and isinstance(tk.Toplevel, type) and isinstance(win, tk.Toplevel):
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
                log.exception("DomeDesktopPreview ULW init failed; falling back to ColorKey")
                surf = None
        if surf is None:
            try:
                win.wm_attributes("-transparentcolor", BG_TRANSPARENT)
            except tk.TclError:
                pass
        win.configure(bg=BG_TRANSPARENT)
        canvas = tk.Canvas(win, width=w, height=h, bg=BG_TRANSPARENT, highlightthickness=0)
        canvas.pack()
        win.geometry(f"{w}x{h}+{x}+{y}")
        if surf is not None:
            first_im = initial_pil if initial_pil is not None else Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
            try:
                surf.present(first_im, x=x, y=y, opacity=1.0)
                win.deiconify()
                surf.set_visibility(True, reorder=False)
            except Exception:
                log.exception("DomeDesktopPreview ULW present failed; falling back to ColorKey")
                try:
                    surf.close(clear_exstyle=True)
                except Exception:
                    pass
                surf = None
                try:
                    win.wm_attributes("-transparentcolor", BG_TRANSPARENT)
                except tk.TclError:
                    pass
                win.deiconify()
        else:
            win.deiconify()
        try:
            self.pet.desktop.set_noactivate(int(win.winfo_id()))
        except Exception:
            pass
        return win, canvas, surf

    def _spawn_windows(self) -> None:
        try:
            if hasattr(self.pet, "_set_pet_visibility"):
                self.pet._set_pet_visibility(False)
            else:
                self.pet.window.withdraw()
        except tk.TclError:
            pass
        for m in DOME_STAGE_MEMBERS:
            entry = self._primary_entry(m)
            x, y = self.slots[m]
            w, h = entry["w"], entry["h"]
            first_pil = (entry.get("pil") or [None])[0]
            win, canvas, surf = self._make_transparent_window(w, h, x, y, initial_pil=first_pil)
            img_id = canvas.create_image(w // 2, h // 2, image=entry["tk"][0], anchor="center")
            self.actor_windows[m] = win
            self._actor_canvases[m] = (canvas, img_id)
            if surf is not None:
                self.actor_surfaces[m] = surf
        if self.mode == "baseball":
            b_win, b_canvas, b_surf = self._make_transparent_window(
                240, 96, self.area.left, self.area.top + 40,
            )
            b_id = b_canvas.create_image(0, 0, anchor="nw")
            self.bubble_window = b_win
            self.bubble_surface = b_surf
            self._bubble_canvas = b_canvas
            self._bubble_img_id = b_id

    def _render_step(self, *, schedule_next: bool = True) -> None:
        if self.closed:
            return
        elapsed_ms = max(0.0, (time.monotonic() - self._t0) * 1000.0)

        if self.mode == "baseball":
            frame_idx, _dur_ms, bubble_scale = dome_baseball_step(elapsed_ms)
            vis_boxes: list[tuple[int, int, int, int]] = []
            for m in DOME_STAGE_MEMBERS:
                entry = self._primary_entry(m)
                tk_frames = entry["tk"]
                idx = frame_idx % len(tk_frames)
                canvas, img_id = self._actor_canvases[m]
                try:
                    canvas.itemconfigure(img_id, image=tk_frames[idx])
                except tk.TclError:
                    pass
                sx, sy = self.slots[m]
                surf = self.actor_surfaces.get(m)
                if surf is not None and not surf.closed:
                    pil_frames = entry.get("pil")
                    if pil_frames:
                        pil_im = pil_frames[idx % len(pil_frames)]
                        pres_key = (id(pil_im), sx, sy)
                        if self._actor_presented.get(m) != pres_key:
                            try:
                                surf.present(pil_im, x=sx, y=sy)
                                self._actor_presented[m] = pres_key
                            except OSError:
                                pass
                bb = entry["alpha_bboxes"][idx] if idx < len(entry["alpha_bboxes"]) else None
                if bb is not None:
                    vis_boxes.append((sx + bb[0], sy + bb[1], sx + bb[2], sy + bb[3]))
                else:
                    vis_boxes.append((sx, sy, sx + entry["w"], sy + entry["h"]))

            a = self.area
            gap = max(14, round(18 * self.k))
            margin = max(12, round(16 * self.k))
            top_safe = a.top + margin
            max_bw, max_bh = available_dome_bubble_space(
                vis_boxes, (a.left, a.top, a.right, a.bottom),
                gap=gap, top_safe_y=top_safe, side_margin=margin,
            )
            binary_alpha = not getattr(self, "_use_ulw", False)
            cache_key = (frame_idx, self.pet.lang, round(self.k, 2), max_bw, max_bh, binary_alpha)
            if self._bubble_cache_key != cache_key or self._bubble_photo is None:
                pil_bub = render_dome_bubble_pil(
                    frame_idx,
                    self.pet.lang,
                    dpi_scale=self.k,
                    anim_scale=bubble_scale,
                    max_width=min(round(560 * self.k), max_bw),
                    max_height=max_bh,
                    binary_alpha=binary_alpha,
                )
                self._bubble_pil = pil_bub
                self._bubble_size = (pil_bub.width, pil_bub.height)
                self._bubble_photo = ImageTk.PhotoImage(pil_bub, master=self.pet.root)
                self._bubble_cache_key = cache_key

            bx, by, bw_rect, bh_rect = compute_dome_bubble_rect(
                vis_boxes,
                self._bubble_size,
                (a.left, a.top, a.right, a.bottom),
                gap=gap,
                top_safe_y=top_safe,
                side_margin=margin,
            )
            if (bw_rect, bh_rect) != self._bubble_size and getattr(self, "_bubble_pil", None) is not None:
                resample = Image.NEAREST if binary_alpha else Image.LANCZOS
                resized = self._bubble_pil.resize((bw_rect, bh_rect), resample)
                self._bubble_pil = resized
                self._bubble_size = (bw_rect, bh_rect)
                self._bubble_photo = ImageTk.PhotoImage(resized, master=self.pet.root)
            bw_px, bh_px = self._bubble_size
            if self.bubble_window is not None and self._bubble_canvas is not None:
                try:
                    self._bubble_canvas.configure(width=bw_px, height=bh_px)
                    self._bubble_canvas.itemconfigure(self._bubble_img_id, image=self._bubble_photo)
                    self.bubble_window.geometry(f"{bw_px}x{bh_px}+{bx}+{by}")
                    if self.bubble_surface is not None and not self.bubble_surface.closed and getattr(self, "_bubble_pil", None) is not None:
                        b_key = (id(self._bubble_pil), bx, by)
                        if self._bubble_presented != b_key:
                            self.bubble_surface.present(self._bubble_pil, x=bx, y=by)
                            self._bubble_presented = b_key
                except (tk.TclError, OSError):
                    pass
            if schedule_next:
                self._reschedule_step(75)
            return

        # mode == "eunji_dream"
        eunji_outfits = tuple(
            o for o in self._eunji_outfits if o in self._member_actions["eunji"]
        )
        if eunji_outfits:
            outfit, e_idx = dome_concert_step(elapsed_ms, eunji_outfits)
            e_entry = self._member_actions["eunji"][outfit]
        else:
            e_entry = self._load_fallback_cheer("eunji")
            e_idx = int(elapsed_ms // 150.0)
        e_frames = e_entry["tk"]
        e_canvas, e_img_id = self._actor_canvases["eunji"]
        e_win = self.actor_windows["eunji"]
        ew, eh = e_entry["w"], e_entry["h"]
        ex, ey = self.slots["eunji"]
        try:
            e_canvas.configure(width=ew, height=eh)
            e_canvas.coords(e_img_id, ew // 2, eh // 2)
            e_canvas.itemconfigure(e_img_id, image=e_frames[e_idx % len(e_frames)])
            e_win.geometry(f"{ew}x{eh}+{ex}+{ey}")
            e_surf = self.actor_surfaces.get("eunji")
            e_pil = e_entry.get("pil")
            if e_surf is not None and not e_surf.closed and e_pil:
                e_surf.present(e_pil[e_idx % len(e_pil)], x=ex, y=ey)
        except (tk.TclError, OSError):
            pass

        flank_step = int(elapsed_ms // 150.0)
        for idx, member in enumerate(EUNJI_FLANK_MEMBERS):
            f_entry = self._primary_entry(member)
            f_frames = f_entry["tk"]
            f_canvas, f_img_id = self._actor_canvases[member]
            f_idx = (flank_step + idx) % len(f_frames)
            try:
                f_canvas.itemconfigure(
                    f_img_id, image=f_frames[f_idx]
                )
                f_surf = self.actor_surfaces.get(member)
                f_pil = f_entry.get("pil")
                if f_surf is not None and not f_surf.closed and f_pil:
                    fx, fy = self.slots[member]
                    f_surf.present(f_pil[f_idx % len(f_pil)], x=fx, y=fy)
            except (tk.TclError, OSError):
                pass
        if schedule_next:
            self._reschedule_step(130)

    def _reschedule_step(self, delay_ms: int) -> None:
        if self.closed:
            return
        prev = self._after_ids.pop("step", None)
        cancel_after_safely(self.pet.root, prev)
        try:
            self._after_ids["step"] = self.pet.root.after(delay_ms, self._tick)
        except tk.TclError:
            pass

    def _tick(self) -> None:
        self._after_ids.pop("step", None)
        if not self.closed:
            self._render_step(schedule_next=True)

    def close(self, *, restore_pet: bool = True) -> None:
        """Tear down all windows and scheduled timers deterministically."""
        if self.closed:
            return
        self.closed = True
        for key in list(self._after_ids):
            cancel_after_safely(self.pet.root, self._after_ids.pop(key, None))

        b_surf, self.bubble_surface = getattr(self, "bubble_surface", None), None
        if b_surf is not None:
            try:
                b_surf.close()
            except Exception:
                pass
        if self.bubble_window is not None:
            try:
                self.bubble_window.destroy()
            except Exception:
                pass
            self.bubble_window = None
        for m in list(getattr(self, "actor_surfaces", ())):
            a_surf = self.actor_surfaces.pop(m, None)
            if a_surf is not None:
                try:
                    a_surf.close()
                except Exception:
                    pass
        for m in list(self.actor_windows):
            win = self.actor_windows.pop(m, None)
            if win is not None:
                try:
                    win.destroy()
                except Exception:
                    pass
        self._bubble_photo = None

        if restore_pet and not getattr(self.pet, "_closing", False):
            try:
                if self.pet.window.winfo_exists():
                    if hasattr(self.pet, "_set_pet_visibility"):
                        self.pet._set_pet_visibility(True)
                    else:
                        self.pet.window.deiconify()
                    self.pet.ensure_topmost()
            except tk.TclError:
                pass
        if self._on_done is not None:
            cb, self._on_done = self._on_done, None
            try:
                cb()
            except Exception:
                pass
