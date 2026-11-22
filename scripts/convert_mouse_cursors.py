"""scripts/convert_mouse_cursors.py — Converts JPG cursor source designs to transparent PNG and multi-resolution Windows .CUR files.

Processes:
1. Mitten_mouse_cursor_design_84215600.jpg -> cursor_mitten_smooth (.png & .cur)
2. White_mitten_mouse_cursor_design_7f16607e.jpg -> cursor_mitten_pixel (.png & .cur)
3. Pink_panda_mouse_cursor_design_2674c4ce.jpg -> cursor_paw_pixel (.png & .cur)
4. Pink_panda_paw_cursor_design_47965c8e.jpg -> cursor_paw_smooth (.png & .cur)
"""
from __future__ import annotations

import ctypes
import os
import struct
from collections import deque
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UI_ICONS_DIR = ROOT / "work" / "ui_icons"


def remove_bg(img: Image.Image, tolerance: int = 30, keep_main_comp: bool = False) -> Image.Image:
    rgba = img.convert("RGBA")
    w, h = rgba.size
    bg = rgba.getpixel((0, 0))[:3]
    q = deque()
    visited = set()
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
        visited.add((x, 0))
        visited.add((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))
        visited.add((0, y))
        visited.add((w - 1, y))
    pixels = rgba.load()
    while q:
        x, y = q.popleft()
        r, g, b, a = pixels[x, y]
        if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) <= tolerance:
            pixels[x, y] = (0, 0, 0, 0)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny))

    if keep_main_comp:
        visited_c = set()
        components = []
        for x in range(w):
            for y in range(h):
                if pixels[x, y][3] > 0 and (x, y) not in visited_c:
                    cq = deque([(x, y)])
                    visited_c.add((x, y))
                    pts = []
                    while cq:
                        cx, cy = cq.popleft()
                        pts.append((cx, cy))
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited_c and pixels[nx, ny][3] > 0:
                                visited_c.add((nx, ny))
                                cq.append((nx, ny))
                    components.append(pts)
        if len(components) > 1:
            components.sort(key=len, reverse=True)
            main_comp = set(components[0])
            for x in range(w):
                for y in range(h):
                    if (x, y) not in main_comp and pixels[x, y][3] > 0:
                        pixels[x, y] = (0, 0, 0, 0)
    return rgba


def process_cursor(src_path: Path, dst_base: Path, hotspot_fn, keep_main_comp: bool = False, tolerance: int = 30) -> None:
    if not src_path.exists():
        print(f"Skipping {src_path.name}: not found")
        return

    im = Image.open(src_path)
    rgba = remove_bg(im, tolerance=tolerance, keep_main_comp=keep_main_comp)
    bbox = rgba.getbbox()
    cropped = rgba.crop(bbox)
    cw, ch = cropped.size
    sq_size = max(cw, ch)
    square_img = Image.new("RGBA", (sq_size, sq_size), (0, 0, 0, 0))
    offset_x = (sq_size - cw) // 2
    offset_y = (sq_size - ch) // 2
    square_img.paste(cropped, (offset_x, offset_y))

    # Calculate hotspot relative to square canvas
    tip_x, tip_y = hotspot_fn(bbox, offset_x, offset_y, sq_size)
    hx_ratio = tip_x / sq_size
    hy_ratio = tip_y / sq_size

    # Save high-res master PNG
    png_path = dst_base.with_suffix(".png")
    square_img.save(png_path)

    # Multi-size CUR (32, 48)
    sizes = (32, 48)
    images = [(s, square_img.resize((s, s), Image.Resampling.LANCZOS).convert("RGBA")) for s in sizes]

    header = struct.pack("<HHH", 0, 2, len(images))
    entries = []
    dibs = []
    offset = 6 + len(images) * 16
    for s, img in images:
        w_s, h_s = img.size
        hx = max(0, min(w_s - 1, int(round(w_s * hx_ratio))))
        hy = max(0, min(h_s - 1, int(round(h_s * hy_ratio))))
        bih = struct.pack("<IIIHHIIIIII", 40, w_s, h_s * 2, 1, 32, 0, w_s * h_s * 4, 0, 0, 0, 0)
        xor_data = bytearray()
        for y_i in reversed(range(h_s)):
            for x_i in range(w_s):
                r, g, b, a = img.getpixel((x_i, y_i))
                xor_data.extend([b, g, r, a])
        and_row_bytes = (w_s + 31) // 32 * 4
        and_data = bytearray()
        for y_i in reversed(range(h_s)):
            row = bytearray(and_row_bytes)
            for x_i in range(w_s):
                _, _, _, a = img.getpixel((x_i, y_i))
                if a < 128:
                    row[x_i // 8] |= (1 << (7 - (x_i % 8)))
            and_data.extend(row)
        dib = bih + bytes(xor_data) + bytes(and_data)
        dibs.append(dib)
        w_b = 0 if s == 256 else s
        h_b = 0 if s == 256 else s
        entry = struct.pack("<BBBBHHII", w_b, h_b, 0, 0, hx, hy, len(dib), offset)
        entries.append(entry)
        offset += len(dib)

    cur_path = dst_base.with_suffix(".cur")
    with open(cur_path, "wb") as f:
        f.write(header + b"".join(entries) + b"".join(dibs))

    hcur = ctypes.windll.user32.LoadCursorFromFileW(str(cur_path.resolve()))
    print(f"Generated {cur_path.name}: hCursor={hcur}, 32x32 hotspot=({int(round(32 * hx_ratio))}, {int(round(32 * hy_ratio))})")


def main() -> None:
    targets = [
        (
            UI_ICONS_DIR / "Mitten_mouse_cursor_design_84215600.jpg",
            UI_ICONS_DIR / "cursor_mitten_smooth",
            lambda bbox, ox, oy, sz: (345 - bbox[0] + ox, 213 - bbox[1] + oy),
            False,
        ),
        (
            UI_ICONS_DIR / "White_mitten_mouse_cursor_design_7f16607e.jpg",
            UI_ICONS_DIR / "cursor_mitten_pixel",
            lambda bbox, ox, oy, sz: (256 - bbox[0] + ox, 153 - bbox[1] + oy),
            False,
        ),
        (
            UI_ICONS_DIR / "Pink_panda_mouse_cursor_design_2674c4ce.jpg",
            UI_ICONS_DIR / "cursor_paw_pixel",
            lambda bbox, ox, oy, sz: (280 - bbox[0] + ox, 200 - bbox[1] + oy),
            True,
        ),
        (
            UI_ICONS_DIR / "Pink_panda_paw_cursor_design_47965c8e.jpg",
            UI_ICONS_DIR / "cursor_paw_smooth",
            lambda bbox, ox, oy, sz: (240 - bbox[0] + ox, 210 - bbox[1] + oy),
            False,
        ),
    ]

    for src, dst, fn, keep_main in targets:
        process_cursor(src, dst, fn, keep_main_comp=keep_main)


if __name__ == "__main__":
    main()
