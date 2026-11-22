"""bubble_art.py — Where text may go on a decorated speech-bubble frame.

Frame art (work/bubbles/*.png) has ornaments that reach well into the card
(Hayoung's sweet potato, Chorong's hearts, ...), so fixed margins put the
title and footer on top of them. Instead each frame is measured once:

* ``safe``: the largest centred rectangle of plain interior colour (source px,
  already shrunk by a small margin). All bubble content goes in here.
* ``band``: rows inside ``safe`` that look identical to each other. When the
  content is taller than the frame, only this band is stretched, so
  ornaments are never smeared or cut. The width is never sliced: the frame is
  scaled uniformly to the bubble width.

Results are cached per file (frames are a few hundred px; analysis is ~0.1 s).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image

from app.resource_store import open_resource_image, resource_stat_signature

PLAIN_TOL = 40      # max RGB distance from the interior colour that counts as plain
BAND_TOL = 20       # max RGB distance for a row to count as "same as the band's first row"
SAFE_MARGIN = 8     # source px kept free between text and the nearest ornament
MIN_SAFE_H = 48     # source px: smallest acceptable safe height before stretching
STABLE_DY = 6       # a stretch row must equal the rows this far above and below


def _dist(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


@dataclass(frozen=True)
class FrameLayout:
    size: tuple[int, int]                 # source (w, h)
    safe: tuple[int, int, int, int]       # x0, y0, x1, y1 in source px
    band: tuple[int, int]                 # stretchable rows [y0, y1) in source px
    interior: tuple[int, int, int]        # card colour (RGB)
    inner: tuple[int, int] = (0, 0)       # plain inner span (left, right) of a clean row
    border_rows: Optional[tuple[int, int]] = None  # rows whose (left, right) borders replace the band's
    fill_row: Optional[int] = None        # row whose inner span replaces the band's
    right_cut: Optional[int] = None       # art row where the right half is cut (ornaments differ per side)

    def band_strip(self, image: Image.Image) -> Image.Image:
        """The band rows to repeat, with straight side borders.

        When every clean row also crosses a side ornament (e.g. a heart on the
        border), the columns outside ``inner`` come from ``border_rows`` instead,
        so stretching never turns that ornament into a long pill. Likewise the
        inner span comes from ``fill_row`` when the band row crosses an ornament.
        """
        im = image.convert("RGBA")
        b0, b1 = self.band
        strip = im.crop((0, b0, im.width, b1))
        left, right = self.inner
        if self.fill_row is not None:
            piece = im.crop((left, self.fill_row, right + 1, self.fill_row + 1))
            for y in range(strip.height):
                strip.paste(piece, (left, y))
            if self.right_cut is not None:
                mid = (left + right + 1) // 2
                half = im.crop((mid, self.right_cut, right + 1, self.right_cut + 1))
                for y in range(strip.height):
                    strip.paste(half, (mid, y))
        if self.border_rows is not None:
            row_l, row_r = self.border_rows
            piece_l = im.crop((0, row_l, left, row_l + 1))
            piece_r = im.crop((right + 1, row_r, im.width, row_r + 1))
            for y in range(strip.height):
                strip.paste(piece_l, (0, y))
                strip.paste(piece_r, (right + 1, y))
        return strip

    def geometry(self, width: int, content_h: float) -> "CardGeometry":
        """Card of ``width`` px whose safe area is at least ``content_h`` px tall."""
        w, h = self.size
        s = width / w
        x0, y0, x1, y1 = self.safe
        natural = (y1 - y0) * s
        extra = max(0, math.ceil(content_h - natural))
        scaled_h = round(h * s)
        top = round(self.band[0] * s)
        band = max(1, round(self.band[1] * s) - top)   # a 1-row band must not round away
        bottom = scaled_h - top - band
        height = scaled_h + extra
        safe = (round(x0 * s), round(y0 * s), round(x1 * s), round(y1 * s) + extra)
        return CardGeometry(width, height, s, top, bottom, safe)


@dataclass(frozen=True)
class CardGeometry:
    width: int
    height: int
    scale: float
    cap_top: int        # rows above the stretch band (output px)
    cap_bottom: int     # rows below the stretch band (output px)
    safe: tuple[int, int, int, int]  # x0, y0, x1, y1 in output px


def analyze(image: Image.Image) -> FrameLayout:
    im = image.convert("RGBA")
    w, h = im.size
    px = im.load()
    cx, cy = w // 2, h // 2
    patch = sorted(px[x, y][:3] for x in range(cx - 10, cx + 10) for y in range(cy - 10, cy + 10))
    interior = patch[len(patch) // 2]

    def plain(x: int, y: int) -> bool:
        p = px[x, y]
        return p[3] == 255 and _dist(p, interior) <= PLAIN_TOL

    # Plain run through the centre column, per row: (left, right) inclusive, or None.
    spans: list[tuple[int, int] | None] = []
    for y in range(h):
        if not plain(cx, y):
            spans.append(None)
            continue
        left = cx
        while left > 0 and plain(left - 1, y):
            left -= 1
        right = cx
        while right < w - 1 and plain(right + 1, y):
            right += 1
        spans.append((left, right))
    if spans[cy] is None:
        raise ValueError("frame centre is not plain interior")

    # "Clean" rows: plain across the frame's whole inner width (the most common
    # span), i.e. no sparkle / dot / ornament anywhere inside the frame. Only
    # these may be stretched; repeating them never smears an ornament.
    counts: dict[tuple[int, int], int] = {}
    for span in spans:
        if span is not None:
            counts[span] = counts.get(span, 0) + 1
    inner = max(counts, key=counts.get)
    clean = [sp is not None and sp[0] <= inner[0] + 2 and sp[1] >= inner[1] - 2 for sp in spans]
    if not any(clean):
        raise ValueError("frame has no ornament-free row to stretch")

    # Widest centred rectangle that is tall enough and contains a clean row
    # (width is what text needs; height comes from stretching the band).
    l0, r0 = spans[cy]
    best = None
    for pad in range(0, max(1, (r0 - l0) // 3), 2):
        x0, x1 = l0 + pad, r0 - pad
        ys = ye = cy
        while ys > 0 and spans[ys - 1] and spans[ys - 1][0] <= x0 and spans[ys - 1][1] >= x1:
            ys -= 1
        while ye < h - 1 and spans[ye + 1] and spans[ye + 1][0] <= x0 and spans[ye + 1][1] >= x1:
            ye += 1
        if ye - ys + 1 < MIN_SAFE_H + 2 * SAFE_MARGIN or not any(clean[ys:ye + 1]):
            continue
        score = (x1 - x0, ye - ys)
        if best is None or score > best[0]:
            best = (score, (x0, ys, x1 + 1, ye + 1))
    if best is None:
        raise ValueError("frame has no usable text area")
    x0, y0, x1, y1 = best[1]
    m = SAFE_MARGIN
    safe = (x0 + m, y0 + m, x1 - m, y1 - m)

    # Stretch band: longest run of clean rows that also look alike (inside the
    # safe rows); a single clean row is enough (it is simply repeated).
    def same(ya: int, yb: int) -> bool:
        diff = sum(1 for x in range(w) if _dist(px[x, ya], px[x, yb]) > BAND_TOL or px[x, ya][3] != px[x, yb][3])
        return diff <= w * 0.01

    # The side borders must be straight there too: a row crossing a heart on the
    # border would turn it into a long pill. "Stable" = same as rows STABLE_DY away.
    def stable(y: int) -> bool:
        return all(0 <= y + d < h and same(y, y + d) for d in (-STABLE_DY, STABLE_DY))

    candidates = [y for y in range(safe[1], safe[3]) if clean[y]] or [y for y in range(y0, y1) if clean[y]]
    rows = [y for y in candidates if stable(y)]
    if not rows:
        # Glossy borders change shade slowly, so nothing is exactly stable: take
        # the clean row whose surroundings change least (away from border hearts).
        def change(y: int) -> int:
            return max(sum(1 for x in range(w) if 0 <= y + d < h and
                           (_dist(px[x, y], px[x, y + d]) > BAND_TOL or px[x, y][3] != px[x, y + d][3]))
                       for d in (-STABLE_DY, STABLE_DY))
        left, right = inner

        def side_plain(y: int) -> int:
            return sum(1 for x in range(w) if (x < left or x > right) and plain(x, y))
        # Prefer the row between side ornaments (hearts on the border), so the caps
        # keep them whole instead of cutting them in half at the band.
        best_row = max(candidates, key=lambda y: (side_plain(y), -change(y), -abs(y - cy)))

        # Side borders from the row whose border area (between the outer rim and
        # the inner span) is most plain interior colour: no heart / sparkle there.
        # Left and right are chosen separately: side ornaments rarely share a row.
        inside = [y for y in range(h)
                  if spans[y] is not None and spans[y][0] <= left + 2 and spans[y][1] >= right - 2]

        def best_side(cols: list[int]) -> int:
            """Row whose border columns ``cols`` look most like the plain frame."""
            # The rim is the same on every row; hearts, sparkles and props replace
            # interior colour, so the row with the most plain pixels is the plain frame.
            return max(inside, key=lambda y: (sum(1 for x in cols if plain(x, y)), -abs(y - best_row)))

        border_rows = (best_side(list(range(left - 1, -1, -1))), best_side(list(range(right + 1, w))))
        return FrameLayout((w, h), safe, (best_row, best_row + 1), interior, inner, border_rows)
    band = (rows[len(rows) // 2], rows[len(rows) // 2] + 1)
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j] == rows[j - 1] + 1 and same(rows[i], rows[j]):
            j += 1
        if rows[j - 1] + 1 - rows[i] > band[1] - band[0]:
            band = (rows[i], rows[j - 1] + 1)
        i = j
    return FrameLayout((w, h), safe, band, interior, inner)


@lru_cache(maxsize=32)
def _analyze_file(path: str, sig: tuple, root_str: str | None = None) -> FrameLayout:
    root = Path(root_str) if root_str is not None else None
    with open_resource_image(Path(path), root=root) as im:
        return analyze(im)


def frame_layout(path: Path, root: Path | None = None) -> FrameLayout:
    p = Path(path)
    sig = resource_stat_signature(p, root=root)
    return _analyze_file(str(p), sig, str(root) if root is not None else None)
