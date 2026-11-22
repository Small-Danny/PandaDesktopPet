"""Prepare speech-bubble frame art in work/bubbles/ for the colour-key bubble window.

The generated PNGs came as opaque RGB on a white page, and two files were
sheets with two stacked cards. This tool (idempotent, originals kept):

  1. backs up every original to work/bubbles/source/ (only the first time);
  2. splits stacked sheets and picks the card each theme needs;
  3. makes the page around the frame transparent (flood fill from the border,
     plus a light anti-alias fringe pass) and binarizes alpha, because the
     bubble window uses -transparentcolor and cannot show partial alpha;
  4. trims to the card and writes work/bubbles/<file>.png (500 px wide).

Run:  python tools/prepare_bubble_art.py
"""
from __future__ import annotations

import shutil
import sys
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BUBBLES = ROOT / "work" / "bubbles"
SOURCE = BUBBLES / "source"
WIDTH = 500
BACKGROUND8 = ROOT / "reference" / "需求" / "背景8.png"
BACKGROUND6 = ROOT / "reference" / "需求" / "背景6.png"
# Padded single-card bounds measured on the 1672x941 original (reference/需求/背景8.png).
# 背景8.png contains 4 Apink member-exclusive cloud frame cards (2x2 grid):
#   - Top-Left:     Chorong (Pink, Cats & Ribbon)
#   - Top-Right:    Bomi (Coral, Campfire & Bag)
#   - Bottom-Left:  Eunji (Sky Blue, A-Cap & Headphones)
#   - Bottom-Right: Namjoo (Lilac Purple, Flamingo & Shaker)
ORIGINAL_CARDS = {
    "bubble_chorong_pink.png": (14, 5, 822, 446),
    "bubble_bomi_coral.png": (842, 2, 1661, 449),
    "bubble_eunji_comic.png": (14, 470, 822, 914),
    "bubble_namjoo_purple.png": (844, 463, 1666, 916),
    # Independent decorative frames from background6, not member-frame aliases.
    # Keep ruby_velvet's stable filename for existing settings; its UI name is
    # Strawberry Macaron, matching the artwork rather than the legacy identifier.
    "bubble_ruby_velvet.png": (840, 5, 1665, 455),
    "bubble_lilac_mauve.png": (5, 450, 830, 935),
}
BACKGROUND6_NAMES = frozenset({"bubble_ruby_velvet.png", "bubble_lilac_mauve.png"})
PAGE_TOL = 18     # colour distance from the page colour that still counts as page
FRINGE_TOL = 70   # light anti-alias pixels touching the page are removed too

# Original six single-card inputs are read only from the preserved backups.
# The two former stacked sheets now use ORIGINAL_CARDS, never a derivative.


def _dist(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def split_cards(im: Image.Image) -> list[Image.Image]:
    """Cards stacked vertically, separated by rows of plain page colour."""
    rgb = im.convert("RGB")
    page = rgb.getpixel((0, 0))
    px = rgb.load()
    w, h = rgb.size
    blank = [all(_dist(px[x, y], page) <= PAGE_TOL for x in range(0, w, 2)) for y in range(h)]
    cards, start = [], None
    for y, b in enumerate(blank + [True]):
        if not b and start is None:
            start = y
        elif b and start is not None:
            if y - start > 40:
                cards.append(im.crop((0, start, w, y)))
            start = None
    return cards or [im]


def make_transparent(im: Image.Image) -> Image.Image:
    rgba = im.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    page = px[0, 0]
    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        q.extend(((0, y), (w - 1, y)))
    outside = []
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i] or _dist(px[x, y], page) > PAGE_TOL:
            continue
        seen[i] = 1
        outside.append((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                q.append((nx, ny))
    for x, y in outside:
        px[x, y] = (0, 0, 0, 0)
    # Anti-aliased light pixels on the frame's outer edge would show as a pale halo.
    for _ in range(2):
        fringe = []
        for x, y in outside:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    p = px[nx, ny]
                    if p[3] and _dist(p, page) <= FRINGE_TOL:
                        fringe.append((nx, ny))
        for x, y in fringe:
            px[x, y] = (0, 0, 0, 0)
        outside = fringe
    alpha = rgba.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    rgba.putalpha(alpha)
    return rgba.crop(alpha.getbbox())


def prepare(name: str) -> Image.Image:
    if name in ORIGINAL_CARDS:
        source = BACKGROUND6 if name in BACKGROUND6_NAMES else BACKGROUND8
        with Image.open(source) as src:
            if src.size != (1672, 941):
                raise ValueError(f"{source.name} source dimensions changed; review crop bounds")
            card = src.convert("RGB").crop(ORIGINAL_CARDS[name])
    else:
        with Image.open(SOURCE / name) as src:
            im = src.convert("RGB")
        card = split_cards(im)[0]
    out = make_transparent(card)
    if out.width != WIDTH:
        out = out.resize((WIDTH, round(out.height * WIDTH / out.width)), Image.Resampling.LANCZOS)
        out.putalpha(out.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
    return out


def main() -> int:
    SOURCE.mkdir(parents=True, exist_ok=True)
    for path in sorted(BUBBLES.glob("bubble_*.png")):
        backup = SOURCE / path.name
        if not backup.exists():
            shutil.copy2(path, backup)
    for path in sorted(SOURCE.glob("bubble_*.png")):
        out = prepare(path.name)
        out.save(BUBBLES / path.name)
        print(f"{path.name}: {out.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
