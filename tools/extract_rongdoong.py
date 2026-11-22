"""Extract RONGDOONG sprite sheet into clean, aligned RGBA frames.

Improvements in v2:
- Supports high-resolution member sprite sheets (default: 初瓏.jpg, 2400x1792)
- Dynamic per-row and per-column cluster detection (replaces rigid shared grid)
- Resolves sleep_01 / sleep_02 clipping and ear overlapping completely
- Preserves uniform character scale across all 16 frames
- Flood-fills exterior background with calibrated threshold (default 220)
- Preserves enclosed white panda face/belly
- Smart defringe eliminates JPG white/gray edge halo
- Standardized ground baseline alignment across all frames
- Writes to work/rongdoong_processed_v2 by default (preserving legacy output)
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reference" / "rongdong_sprites" / "初瓏.jpg"
DEFAULT_OUT = ROOT / "work" / "rongdoong_processed_v2"

ACTIONS = ("idle", "walk", "cheer", "sleep")


def detect_grid_cells(im: Image.Image, threshold: int = 240) -> list[list[tuple[int, int, int, int]]]:
    """Dynamically detect 4 rows and 4 columns of character bounding boxes."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    pix = rgb.load()

    row_counts = [0] * h
    for y in range(h):
        c = 0
        for x in range(w):
            r, g, b = pix[x, y]
            if r < threshold or g < threshold or b < threshold:
                c += 1
        row_counts[y] = c

    min_row_pixels = 50
    active_rows = [y for y, c in enumerate(row_counts) if c > min_row_pixels]
    if not active_rows:
        raise ValueError("No character content detected in sprite sheet")

    bands = []
    start = active_rows[0]
    for i in range(1, len(active_rows)):
        if active_rows[i] > active_rows[i - 1] + 25:
            bands.append((start, active_rows[i - 1]))
            start = active_rows[i]
    bands.append((start, active_rows[-1]))

    if len(bands) != 4:
        raise ValueError(f"Expected 4 action rows, found {len(bands)} bands")

    grid = []
    for r_idx, (y0, y1) in enumerate(bands):
        band_col_counts = [0] * w
        for y in range(y0, y1 + 1):
            for x in range(w):
                r, g, b = pix[x, y]
                if r < threshold or g < threshold or b < threshold:
                    band_col_counts[x] += 1

        active_cols = [x for x, c in enumerate(band_col_counts) if c > 15]
        col_segments = []
        if active_cols:
            c_start = active_cols[0]
            for c_i in range(1, len(active_cols)):
                if active_cols[c_i] > active_cols[c_i - 1] + 25:
                    col_segments.append((c_start, active_cols[c_i - 1]))
                    c_start = active_cols[c_i]
            col_segments.append((c_start, active_cols[-1]))

        if len(col_segments) != 4:
            raise ValueError(f"Row {r_idx + 1} expected 4 columns, found {len(col_segments)}")

        # Add safe margin around each character cell (clamped to image bounds)
        pad_x = 18
        pad_y = 15
        row_cells = []
        for x0, x1 in col_segments:
            cx0 = max(0, x0 - pad_x)
            cx1 = min(w, x1 + pad_x + 1)
            cy0 = max(0, y0 - pad_y)
            cy1 = min(h, y1 + pad_y + 1)
            row_cells.append((cx0, cy0, cx1, cy1))
        grid.append(row_cells)

    return grid


def exterior_mask(im: Image.Image, threshold: int = 220) -> Image.Image:
    """Keep only non-background pixels by flood-filling near-white from image edges."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    pix = rgb.load()
    visited = bytearray(w * h)
    q = deque()

    def candidate(x: int, y: int) -> bool:
        r, g, b = pix[x, y]
        return min(r, g, b) >= threshold

    def add(x: int, y: int) -> None:
        i = y * w + x
        if not visited[i] and candidate(x, y):
            visited[i] = 1
            q.append((x, y))

    for x in range(w):
        add(x, 0)
        add(x, h - 1)
    for y in range(h):
        add(0, y)
        add(w - 1, y)

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                add(nx, ny)

    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    for y in range(h):
        for x in range(w):
            if visited[y * w + x]:
                ap[x, y] = 0
    return alpha


def defringe(rgba: Image.Image, bright_threshold: int = 190, dark_threshold: int = 140) -> Image.Image:
    """Reduce JPG halo: edge pixels that touch transparency and are lighter than stroke

    borrow color from dark stroke neighbors.
    """
    rgba = rgba.copy()
    px = rgba.load()
    w, h = rgba.size

    def neighbors(x: int, y: int):
        for ny in range(max(0, y - 1), min(h, y + 2)):
            for nx in range(max(0, x - 1), min(w, x + 2)):
                if nx == x and ny == y:
                    continue
                yield nx, ny

    updates = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue

            # Check if this pixel touches transparency
            has_transparent_neighbor = any(px[nx, ny][3] == 0 for nx, ny in neighbors(x, y))
            if not has_transparent_neighbor:
                continue

            # If it's a bright transition pixel touching dark stroke
            if max(r, g, b) >= bright_threshold:
                dark_samples = []
                for nx, ny in neighbors(x, y):
                    nr, ng, nb, na = px[nx, ny]
                    if na > 0 and max(nr, ng, nb) <= dark_threshold:
                        dark_samples.append((nr, ng, nb))

                if dark_samples:
                    rr = round(sum(s[0] for s in dark_samples) / len(dark_samples))
                    gg = round(sum(s[1] for s in dark_samples) / len(dark_samples))
                    bb = round(sum(s[2] for s in dark_samples) / len(dark_samples))
                    updates.append((x, y, rr, gg, bb, 255))

    for x, y, r, g, b, a in updates:
        px[x, y] = (r, g, b, a)

    return rgba


def binarize_alpha(im: Image.Image) -> Image.Image:
    a = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    im.putalpha(a)
    return im


def run(
    source: Path,
    out: Path,
    size: int = 192,
    threshold: int = 220,
    baseline_pad: int = 8,
) -> dict:
    with Image.open(source) as inp:
        sheet = inp.convert("RGB")

    w, h = sheet.size
    grid = detect_grid_cells(sheet)

    out.mkdir(parents=True, exist_ok=True)

    raw_characters = []
    diagnostics = []

    for row_idx, action in enumerate(ACTIONS):
        for col_idx in range(4):
            x0, y0, x1, y1 = grid[row_idx][col_idx]
            tile = sheet.crop((x0, y0, x1, y1))
            alpha = exterior_mask(tile, threshold)
            tile = tile.convert("RGBA")
            tile.putalpha(alpha)

            bb = tile.getbbox()
            if not bb:
                raise ValueError(f"Empty character in {action}_{col_idx + 1}")

            char = tile.crop(bb)
            char = defringe(char)

            raw_characters.append((action, col_idx + 1, char))
            diagnostics.append(
                {
                    "action": action,
                    "col": col_idx + 1,
                    "raw_w": char.width,
                    "raw_h": char.height,
                    "cell_box": [x0, y0, x1, y1],
                    "content_margin_left": bb[0],
                    "content_margin_top": bb[1],
                    "content_margin_right": tile.width - bb[2],
                    "content_margin_bottom": tile.height - bb[3],
                }
            )

    # Calculate uniform scale across all 16 frames
    max_raw_w = max(char.width for _, _, char in raw_characters)
    max_raw_h = max(char.height for _, _, char in raw_characters)

    target_max_w = size - 16
    target_max_h = size - 16
    scale = min(target_max_w / max_raw_w, target_max_h / max_raw_h, 1.0)

    manifest = {
        "source": str(source),
        "sheet_size": [w, h],
        "canvas": [size, size],
        "threshold": threshold,
        "uniform_scale": scale,
        "baseline_pad": baseline_pad,
        "max_raw_size": [max_raw_w, max_raw_h],
        "frames": {},
        "diagnostics": diagnostics,
    }

    baseline_y = size - baseline_pad

    for action, col_num, char in raw_characters:
        new_w = max(1, round(char.width * scale))
        new_h = max(1, round(char.height * scale))
        char_scaled = char.resize((new_w, new_h), Image.Resampling.LANCZOS)
        char_scaled = binarize_alpha(char_scaled)

        frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        pos_x = (size - new_w) // 2
        pos_y = baseline_y - new_h
        if pos_y < 0:
            pos_y = 0

        frame.alpha_composite(char_scaled, (pos_x, pos_y))

        name = f"{action}_{col_num:02d}.png"
        frame.save(out / name)

        if action not in manifest["frames"]:
            manifest["frames"][action] = []
        manifest["frames"][action].append(name)

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--size", type=int, default=192)
    parser.add_argument("--threshold", type=int, default=220)
    parser.add_argument("--baseline-pad", type=int, default=8)
    args = parser.parse_args()

    res = run(args.input, args.output, args.size, args.threshold, args.baseline_pad)
    total = sum(len(v) for v in res["frames"].values())
    print(f"OK: {total} frames -> {args.output} (scale={res['uniform_scale']:.4f})")
