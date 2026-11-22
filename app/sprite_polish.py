"""sprite_polish.py — display-time clean-up of member sprites (no asset is modified).

The generated sheets were cut from a white background, so the outermost body
pixels are often a pale halo instead of the dark outline, and the large pet size
(240 px) makes that fringe visible on dark desktops. ``polish_frame`` runs on the
final-size frame, after the binary alpha was applied:

1. light unsharp mask on the colours (the "foggy" look),
2. near-white face/belly pixels -> pure white,
3. soft or pale pixels on the outer edge -> the nearest outline colour, so every
   member keeps a crisp, closed dark outline (also where the source outline is thin
   or broken). The 2nd edge pixel (large size only) is changed only if it is pale.

Alpha and the frame size are never changed, so feet anchors and hit areas stay put.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import statistics
import threading

from PIL import Image, ImageChops, ImageFilter

_ULW_SOURCE_CACHE_LOCK = threading.Lock()
_ULW_SOURCE_CACHE: OrderedDict[tuple[tuple[int, int], bytes], Image.Image] = OrderedDict()
_ULW_SOURCE_CACHE_MAX = 128
# 2026-11-22: count-only, 128 full-size cleaned sources held ~76 MB for the whole session
# (warmup fills it at start-up) while PREPARED_IMAGES already keeps the scaled results.
_ULW_SOURCE_CACHE_MAX_BYTES = 16 * 1024 * 1024


def _ulw_cache_bytes(im: Image.Image) -> int:
    return im.width * im.height * 4

SHARPEN = ImageFilter.UnsharpMask(radius=0.8, percent=55, threshold=3)
_AA_BLUR = ImageFilter.GaussianBlur(radius=5.0)
_ALPHA_GROW_CAP = ImageFilter.MaxFilter(3)
_RING3_DILATE = ImageFilter.MaxFilter(7)
WHITE_MIN = 244      # every channel >= this -> pure white
DARK_LUM = 110       # luminance of outline pixels
LIGHT_LUM = 130      # an edge pixel brighter than this is fringe, not outline
RIM_LUM = 70         # edge pixels darker than this are already outline
SOFT_MARGIN = 20     # an edge pixel this much lighter than the outline nearby is a soft rim
SEARCH_RADIUS = 2    # look this far inward for the local outline colour
LARGE_PX = 220       # from this display size on, a 2 px fringe is cleaned


# Reused C-level lookup tables; no per-frame Python callbacks or 16-bit LUTs.
NONZERO_LUT = tuple(255 if v else 0 for v in range(256))
_SOLID_200_LUT = tuple(255 if v >= 200 else 0 for v in range(256))
_SOLID_180_LUT = tuple(255 if v >= 180 else 0 for v in range(256))
_AA_THRESH_LUT = tuple(255 if v >= 110 else 0 for v in range(256))
_DUST_ALPHA_LUT = tuple(0 if v <= 8 else v for v in range(256))
WHITE_LUT = tuple(255 if v >= WHITE_MIN else 0 for v in range(256))
GAP_LUT = tuple(255 if v >= SOFT_MARGIN - 1 else 0 for v in range(256))
NEAR_DARK_LUT = tuple(255 if v <= DARK_LUM else 0 for v in range(256))
PALE_LUT = tuple(255 if v >= LIGHT_LUM else 0 for v in range(256))
RIM_LUT = tuple(255 if v >= RIM_LUM else 0 for v in range(256))


def _lum(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


_SOFT_BINARIZE_LUT = tuple(255 if v >= 128 else 0 for v in range(256))


def alpha_bleed(im: Image.Image, radius: int = 2, *, alpha_threshold: int = 1) -> Image.Image:
    """Extrapolate darker edge colours into transparent pixels before LANCZOS resize.

    Many cut-out sprites and bubble frames retain pale/grey/magenta RGB values in
    their alpha=0 (or faint semi-alpha) pixels; resampling without bleeding pulls
    those hidden colours into the outermost visible edge ring.
    """
    im = im.convert("RGBA")
    r, g, b, a = im.split()
    if alpha_threshold <= 1:
        solid = a.point(NONZERO_LUT)
    elif alpha_threshold == 200:
        solid = a.point(_SOLID_200_LUT)
    elif alpha_threshold == 180:
        solid = a.point(_SOLID_180_LUT)
    else:
        solid = a.point(tuple(255 if v >= alpha_threshold else 0 for v in range(256)))
    white = Image.new("L", im.size, 255)
    flt = ImageFilter.MinFilter(2 * radius + 1)
    r = Image.composite(r, Image.composite(r, white, solid).filter(flt), solid)
    g = Image.composite(g, Image.composite(g, white, solid).filter(flt), solid)
    b = Image.composite(b, Image.composite(b, white, solid).filter(flt), solid)
    return Image.merge("RGBA", (r, g, b, a))


SOFT_BINARIZE_ALPHA = 128


def prepare_ulw_source(im: Image.Image, *, soft_binarize: bool = False) -> Image.Image:
    """Clean 1-bit pale cutout fringe and smooth contour at 8x supersampling for ULW display.

    Sources with semi-transparent alpha are left to ``alpha_bleed`` unless ``soft_binarize``:
    then alpha is first cut at ``SOFT_BINARIZE_ALPHA`` so the soft (often pale) rim joins the
    same 1-bit fringe clean-up. The runtime sprite pipelines pass ``soft_binarize=True``
    (2026-11-22: ~40 % of approved frames are soft and kept a 4-10 % light halo at 240-288 px).
    """
    im = im.convert("RGBA")
    if soft_binarize:
        alpha = im.getchannel("A")
        if sum(alpha.histogram()[1:255]) > 0:
            im = im.copy()
            im.putalpha(alpha.point(_SOFT_BINARIZE_LUT))
    cache_key = (im.size, hashlib.blake2b(im.tobytes(), digest_size=16).digest())
    with _ULW_SOURCE_CACHE_LOCK:
        cached = _ULW_SOURCE_CACHE.get(cache_key)
        if cached is not None:
            _ULW_SOURCE_CACHE.move_to_end(cache_key)
            return cached.copy()
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return im
    margin = SEARCH_RADIUS + 6
    x0, y0, x1, y1 = bbox
    box = (max(0, x0 - margin), max(0, y0 - margin),
           min(im.width, x1 + margin), min(im.height, y1 + margin))
    crop = im.crop(box)
    alpha0 = crop.getchannel("A")
    # Only process 1-bit sources; sources that already carry semi-transparent alpha are skipped.
    if sum(alpha0.histogram()[1:255]) > 0:
        return alpha_bleed(im)

    alpha_clean = alpha0.point(_DUST_ALPHA_LUT)
    ring1 = edge_ring(alpha_clean, 1)
    outline = _outline_colour(crop, ring1)
    if outline is None:
        return alpha_bleed(im)
    outline_lum = _lum(outline)
    dark_thresh = max(DARK_LUM, min(140.0, outline_lum + 35.0))
    pale_thresh = max(outline_lum + 15.0, 75.0)

    # Step (a): Shrink/strip pale outer pixels reached from alpha==0 without crossing dark outline.
    grey = crop.convert("L")
    opaque = alpha_clean.point(NONZERO_LUT)
    dark_mask = ImageChops.multiply(
        opaque,
        grey.point(tuple(255 if v <= dark_thresh else 0 for v in range(256))),
    )
    has_dark_near = dark_mask.filter(_RING3_DILATE)
    pale_in_sprite = ImageChops.multiply(
        opaque,
        grey.point(tuple(255 if v > pale_thresh else 0 for v in range(256))),
    )
    frontier = ImageChops.invert(opaque)
    outer_pale = Image.new("L", crop.size, 0)
    for _ in range(3):
        step = ImageChops.multiply(frontier.filter(_ALPHA_GROW_CAP), pale_in_sprite)
        outer_pale = ImageChops.lighter(outer_pale, step)
        frontier = ImageChops.lighter(frontier, step)
    strip_mask = ImageChops.multiply(outer_pale, has_dark_near)
    alpha_shrunk = ImageChops.subtract(alpha_clean, strip_mask)

    # Step (b): 8x BICUBIC -> GaussianBlur(5) -> threshold(110) -> BOX, clamped by MaxFilter(3).
    cw, ch = crop.size
    hi = alpha_shrunk.resize((cw * 8, ch * 8), Image.Resampling.BICUBIC)
    hi = hi.filter(_AA_BLUR).point(_AA_THRESH_LUT)
    aa = ImageChops.darker(
        hi.resize((cw, ch), Image.Resampling.BOX),
        alpha_clean.filter(_ALPHA_GROW_CAP),
    )

    # Step (c): Outer 3px of aa outside original dark outline -> outline RGB.
    aa_nonzero = aa.point(NONZERO_LUT)
    non_dark_aa = ImageChops.subtract(aa_nonzero, dark_mask)
    ext = ImageChops.invert(aa_nonzero)
    recolor_mask = Image.new("L", crop.size, 0)
    for _ in range(3):
        step = ImageChops.multiply(ext.filter(_ALPHA_GROW_CAP), non_dark_aa)
        recolor_mask = ImageChops.lighter(recolor_mask, step)
        ext = ImageChops.lighter(ext, step)
    recolored = crop.copy()
    recolored.paste(outline + (255,), (0, 0), recolor_mask)
    recolored.putalpha(aa)
    bled = alpha_bleed(recolored, radius=2)
    out = im.copy()
    out.paste(bled, box[:2])
    with _ULW_SOURCE_CACHE_LOCK:
        _ULW_SOURCE_CACHE[cache_key] = out.copy()
        _ULW_SOURCE_CACHE.move_to_end(cache_key)
        total = sum(_ulw_cache_bytes(v) for v in _ULW_SOURCE_CACHE.values())
        while len(_ULW_SOURCE_CACHE) > 1 and (
                len(_ULW_SOURCE_CACHE) > _ULW_SOURCE_CACHE_MAX or total > _ULW_SOURCE_CACHE_MAX_BYTES):
            _k, old = _ULW_SOURCE_CACHE.popitem(last=False)
            total -= _ulw_cache_bytes(old)
    return out


def edge_ring(alpha: Image.Image, width: int = 1) -> Image.Image:
    """Opaque pixels within ``width`` px (8-neighbourhood) of a transparent pixel or canvas border."""
    padded = Image.new("L", (alpha.width + 2 * width, alpha.height + 2 * width), 0)
    padded.paste(alpha, (width, width))
    inner = padded.filter(ImageFilter.MinFilter(2 * width + 1)).crop(
        (width, width, width + alpha.width, width + alpha.height)
    )
    return ImageChops.subtract(alpha, inner)


def _outline_colour(im: Image.Image, ring: Image.Image) -> tuple[int, int, int] | None:
    """Median colour of the dark edge pixels: this frame's outline colour."""
    w = im.width
    raw_im = im.tobytes()
    dark: list[tuple[int, int, int]] = []
    for idx in _mask_positions(ring):
        off = idx * 4
        r, g, b = raw_im[off], raw_im[off + 1], raw_im[off + 2]
        if 0.299 * r + 0.587 * g + 0.114 * b < DARK_LUM:
            dark.append((r, g, b))
    if not dark:
        return None
    return tuple(int(statistics.median(c[i] for c in dark)) for i in range(3))


def _mask_positions(mask: Image.Image):
    """Find sparse mask pixels in C instead of iterating the entire RGBA canvas."""
    raw = mask.point(NONZERO_LUT).tobytes()
    index = raw.find(b"\xff")
    while index >= 0:
        yield index
        index = raw.find(b"\xff", index + 1)


def lock_fringe(im: Image.Image, width: int = 1,
                outline: tuple[int, int, int] | None = None,
                first_ring: Image.Image | None = None) -> Image.Image:
    """Replace pale edge pixels with the darkest outline pixel nearby (or the frame's outline colour)."""
    out = im.copy()
    alpha = out.getchannel("A")
    ring1 = first_ring if first_ring is not None else edge_ring(alpha, 1)
    fallback = outline if outline is not None else _outline_colour(out, ring1)
    if fallback is None:
        return out
    ring = edge_ring(alpha, width) if width != 1 else ring1
    w, h = im.size
    raw_im = im.tobytes()
    raw_alpha = alpha.tobytes()
    raw_r1 = ring1.tobytes()
    # Pillow rounds RGB luminance to 8 bits. The thresholds below are
    # deliberately wider than the exact RGB tests (by >= one unit), so the
    # prefilter never removes a pixel that the precise neighbourhood test
    # would replace. Transparent neighbours cannot supply an outline colour.
    grey = im.convert("L")
    opaque = alpha.point(NONZERO_LUT)
    neighbours = Image.composite(grey, Image.new("L", im.size, 255), opaque)
    local = neighbours.filter(ImageFilter.MinFilter(2 * SEARCH_RADIUS + 1))
    gap = ImageChops.subtract(grey, local).point(GAP_LUT)
    near_dark = local.point(NEAR_DARK_LUT)
    soft = ImageChops.multiply(gap, near_dark)
    # With no dark neighbour the original fallback still closes a pale edge.
    pale = grey.point(PALE_LUT)
    candidates = ImageChops.multiply(ring, ImageChops.lighter(soft, pale))
    candidates = ImageChops.multiply(candidates, grey.point(RIM_LUT))
    dst = out.load()
    for idx in _mask_positions(candidates):
        x = idx % w
        y = idx // w
        off = idx * 4
        r, g, b, a_val = raw_im[off], raw_im[off + 1], raw_im[off + 2], raw_im[off + 3]
        own = 0.299 * r + 0.587 * g + 0.114 * b
        if own <= RIM_LUM:
            continue
        best, best_lum = None, DARK_LUM
        local_min, local_min_lum = (r, g, b), own
        y0 = 0 if y < SEARCH_RADIUS else y - SEARCH_RADIUS
        y1 = h if y + SEARCH_RADIUS + 1 > h else y + SEARCH_RADIUS + 1
        x0 = 0 if x < SEARCH_RADIUS else x - SEARCH_RADIUS
        x1 = w if x + SEARCH_RADIUS + 1 > w else x + SEARCH_RADIUS + 1
        for yy in range(y0, y1):
            row = yy * w
            for xx in range(x0, x1):
                pidx = row + xx
                if raw_alpha[pidx]:
                    poff = pidx * 4
                    pr, pg, pb = raw_im[poff], raw_im[poff + 1], raw_im[poff + 2]
                    lum = 0.299 * pr + 0.587 * pg + 0.114 * pb
                    if lum < local_min_lum:
                        local_min, local_min_lum = (pr, pg, pb), lum
                    if lum < best_lum:
                        best, best_lum = (pr, pg, pb), lum
        if best is not None and own - best_lum > SOFT_MARGIN:
            dst[x, y] = best + (a_val,)       # soft / pale rim -> local outline colour
        elif best is None and (own > LIGHT_LUM or (raw_r1[idx] and own - local_min_lum > SOFT_MARGIN)):
            colour = local_min if own - local_min_lum > SOFT_MARGIN else fallback
            dst[x, y] = colour + (a_val,)
    out.putalpha(alpha)
    return out


def defringe_light_frame(im: Image.Image) -> Image.Image:
    """Pull outermost 1-2 px pale anti-aliased fringe on decorated frames to the local border colour.

    Unlike character sprites (which fall back to a dark outline), pastel speech-bubble
    frames only replace an edge pixel when a darker opaque border pixel exists within 2 px.
    """
    out = im.copy()
    alpha = out.getchannel("A")
    ring1 = edge_ring(alpha, 1)
    ring2 = edge_ring(alpha, 2)
    w, h = out.size
    raw_im = out.tobytes()
    raw_alpha = alpha.tobytes()
    raw_r1 = ring1.tobytes()
    dst = out.load()
    for idx in _mask_positions(ring2):
        x = idx % w
        y = idx // w
        off = idx * 4
        r, g, b, a_val = raw_im[off], raw_im[off + 1], raw_im[off + 2], raw_im[off + 3]
        own_lum = 0.299 * r + 0.587 * g + 0.114 * b
        best_rgb = (r, g, b)
        best_lum = own_lum
        y0 = 0 if y < 2 else y - 2
        y1 = h if y + 3 > h else y + 3
        x0 = 0 if x < 2 else x - 2
        x1 = w if x + 3 > w else x + 3
        for yy in range(y0, y1):
            row = yy * w
            for xx in range(x0, x1):
                pidx = row + xx
                if raw_alpha[pidx]:
                    poff = pidx * 4
                    pr, pg, pb = raw_im[poff], raw_im[poff + 1], raw_im[poff + 2]
                    lum = 0.299 * pr + 0.587 * pg + 0.114 * pb
                    if lum < best_lum:
                        best_rgb, best_lum = (pr, pg, pb), lum
        margin = 1.5 if raw_r1[idx] else 10.0
        if own_lum - best_lum > margin:
            dst[x, y] = best_rgb + (a_val,)
    out.putalpha(alpha)
    return out


def purify_white(im: Image.Image) -> Image.Image:
    r, g, b, a = im.split()
    mask = ImageChops.darker(ImageChops.darker(r, g), b).point(WHITE_LUT)
    out = im.copy()
    out.paste((255, 255, 255, 255), mask=ImageChops.multiply(mask, a))
    out.putalpha(a)
    return out


def sharpen(im: Image.Image, outline: tuple[int, int, int] | None = None) -> Image.Image:
    """Unsharp mask on the colours only; transparent pixels take the outline colour first
    so the filter does not brighten the edge against black."""
    alpha = im.getchannel("A")
    fill = outline if outline is not None else (_outline_colour(im, edge_ring(alpha, 1)) or (0, 0, 0))
    base = Image.new("RGB", im.size, fill)
    base.paste(im.convert("RGB"), mask=alpha)
    out = base.filter(SHARPEN).convert("RGBA")
    out.putalpha(alpha)
    return out


def polish_frame(im: Image.Image, display_px: int, *, binary_alpha: bool = True,
                 edge_refine: bool = False) -> Image.Image:
    """Sharpen, purify white, then lock the edge fringe (2 px at large sizes).

    When ``binary_alpha=False`` (8-bit smooth alpha for Win32 UpdateLayeredWindow):
    - with ``edge_refine=False`` (small size), light unsharp masking and near-white
      purification are applied without 1-bit lock_fringe;
    - with ``edge_refine=True`` (medium/large), sharpen is omitted to avoid bright
      unsharp-mask overshoot along the dark outline and near-white purification stays
      interior-only.
    """
    im = im.convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return im
    width = 2 if display_px >= LARGE_PX else 1
    margin = SEARCH_RADIUS + 3  # preserve the unsharp neighbourhood at the alpha edge
    x0, y0, x1, y1 = bbox
    box = (max(0, x0 - margin), max(0, y0 - margin),
           min(im.width, x1 + margin), min(im.height, y1 + margin))
    crop = im.crop(box)
    crop_a = crop.getchannel("A")
    if binary_alpha or not edge_refine:
        ring = edge_ring(crop_a, 1)
        outline = _outline_colour(crop, ring) or (0, 0, 0)
        polished = purify_white(sharpen(crop, outline))
        if binary_alpha:
            polished = lock_fringe(polished, width, outline, ring)
    else:
        solid_out = crop_a.point(_SOLID_200_LUT)
        interior_mask = ImageChops.subtract(solid_out, edge_ring(solid_out, 2))
        pure = purify_white(crop)
        polished = crop.copy()
        polished.paste(pure, (0, 0), interior_mask)
        polished.putalpha(crop_a)
        polished = alpha_bleed(polished, radius=2, alpha_threshold=200)
    out = im.copy()
    out.paste(polished, box[:2])
    return out


def fringe_ratio(im: Image.Image, width: int = 1, threshold: float = RIM_LUM) -> float:
    """Share (0..1) of edge pixels lighter than ``threshold``: soft rim / pale fringe, not outline."""
    ring = edge_ring(im.getchannel("A"), width)
    px, rp = im.load(), ring.load()
    edge = [px[x, y] for y in range(im.height) for x in range(im.width) if rp[x, y]]
    if not edge:
        return 0.0
    return sum(1 for p in edge if _lum(p) > threshold) / len(edge)
