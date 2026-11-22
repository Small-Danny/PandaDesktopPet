"""tools/clean_edge_fringe.py — Fast 4px boundary-seeded connected-component edge fringe cleanup.

Eliminates stray adjacent-cell crop fragments (such as sofa corners at the top of Bomi walk,
table legs at the top of Hayoung sleep, or wing tips on the side of Namjoo sunglasses)
while preserving intentional floating elements (like 'Zzz' sleep letters, music notes, or hearts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHAR_DIR = ROOT / "work" / "characters"
POLICY_PATH = ROOT / "work" / "asset_review_policy.json"


def find_edge_fringe_components(
    im: Image.Image,
    edge_margin: int = 4,
    max_thickness: int = 20,
    max_area: int = 450,
) -> tuple[list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, int]]]], tuple[int, int, int, int] | None]:
    """Finds small disconnected components seeded from the 4px boundary of the alpha bbox
    that have a flat crop-cut edge or thin sliver profile along the cell border.
    """
    rgba = im.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return [], None

    bx0, by0, bx1, by1 = bbox
    px = rgba.load()
    visited: set[tuple[int, int]] = set()
    fringe_comps = []

    # Collect seed pixels strictly within the 4px outer ring of the alpha bbox
    seeds: list[tuple[int, int]] = []
    for y in range(by0, min(by1, by0 + edge_margin)):
        for x in range(bx0, bx1):
            if px[x, y][3] > 0:
                seeds.append((x, y))
    for y in range(max(by0, by1 - edge_margin), by1):
        for x in range(bx0, bx1):
            if px[x, y][3] > 0:
                seeds.append((x, y))
    for y in range(by0, by1):
        for x in range(bx0, min(bx1, bx0 + edge_margin)):
            if px[x, y][3] > 0:
                seeds.append((x, y))
        for x in range(max(bx0, bx1 - edge_margin), bx1):
            if px[x, y][3] > 0:
                seeds.append((x, y))

    for sx, sy in seeds:
        if (sx, sy) in visited:
            continue
        q = deque([(sx, sy)])
        visited.add((sx, sy))
        pts = []
        minx = maxx = sx
        miny = maxy = sy
        aborted = False

        while q:
            cx, cy = q.popleft()
            pts.append((cx, cy))
            if cx < minx:
                minx = cx
            if cx > maxx:
                maxx = cx
            if cy < miny:
                miny = cy
            if cy > maxy:
                maxy = cy

            if len(pts) > max_area:
                aborted = True
                # Continue marking connected pixels within the thin strip so we don't re-seed
                while q:
                    qx, qy = q.popleft()
                    for nx in (qx - 1, qx, qx + 1):
                        for ny in (qy - 1, qy, qy + 1):
                            if (
                                0 <= nx < w
                                and 0 <= ny < h
                                and (nx, ny) not in visited
                                and px[nx, ny][3] > 0
                                and (
                                    ny < by0 + max_thickness
                                    or ny >= by1 - max_thickness
                                    or nx < bx0 + max_thickness
                                    or nx >= bx1 - max_thickness
                                )
                            ):
                                visited.add((nx, ny))
                                q.append((nx, ny))
                break

            for nx in (cx - 1, cx, cx + 1):
                for ny in (cy - 1, cy, cy + 1):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and px[nx, ny][3] > 0:
                        visited.add((nx, ny))
                        q.append((nx, ny))

        if aborted:
            continue

        cbbox = (minx, miny, maxx + 1, maxy + 1)
        cw = maxx + 1 - minx
        ch = maxy + 1 - miny

        # Determine which border this small component hugs
        side = None
        if miny <= by0 + 2 and (maxy + 1 - by0) <= max_thickness and maxy + 1 <= int(h * 0.14):
            # Top border slice artifact: check flat cut along top edge or tiny stray speck
            top_edge_px = sum(1 for x, y in pts if y <= miny + 1)
            if top_edge_px >= 4 or len(pts) <= 65:
                side = "top"
        elif maxy + 1 >= by1 - 2 and (by1 - miny) <= max_thickness and miny >= int(h * 0.90):
            bot_edge_px = sum(1 for x, y in pts if y >= maxy - 1)
            if bot_edge_px >= 4 or len(pts) <= 65:
                side = "bottom"
        elif minx <= bx0 + 2 and (maxx + 1 - bx0) <= max_thickness and maxx + 1 <= int(w * 0.13):
            # Left border slice artifact (e.g. Namjoo sunglasses wing tip): must have flat cut along left edge
            left_edge_px = sum(1 for x, y in pts if x <= minx + 1)
            if (cw <= 12 and left_edge_px >= 10 and ch >= cw * 2.2) or len(pts) <= 45:
                side = "left"
        elif maxx + 1 >= bx1 - 2 and (bx1 - minx) <= max_thickness and minx >= int(w * 0.88):
            right_edge_px = sum(1 for x, y in pts if x >= maxx - 1)
            if (cw <= 12 and right_edge_px >= 10 and ch >= cw * 2.2) or len(pts) <= 45:
                side = "right"

        if side is not None:
            fringe_comps.append((len(pts), side, cbbox, pts))

    return fringe_comps, bbox


def clean_sprite_file(path: Path, dry_run: bool = False) -> list[tuple[int, str, tuple[int, int, int, int]]]:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        fringe, _ = find_edge_fringe_components(rgba)
        if not fringe:
            return []
        if not dry_run:
            px = rgba.load()
            for _sz, _side, _cbbox, pts in fringe:
                for x, y in pts:
                    px[x, y] = (0, 0, 0, 0)
            rgba.save(path, "PNG")
        return [(sz, side, cbbox) for sz, side, cbbox, _ in fringe]


def regenerate_preview_sheets() -> None:
    """Regenerates work/all1_situational_master_preview.png and work/special_v3_master_preview.png
    so the master preview sheets reflect the cleaned sprites.
    """
    # 1. Regenerate all1_situational_master_preview.png
    all1_dir = CHAR_DIR / "all_situational"
    if all1_dir.is_dir():
        poses = sorted(all1_dir.glob("pose_*.png"))
        if len(poses) == 16:
            cols, rows, cell_size = 4, 4, 200
            preview = Image.new("RGB", (cols * cell_size, rows * cell_size), (248, 249, 250))
            for i, p_path in enumerate(poses):
                r, c = i // cols, i % cols
                with Image.open(p_path) as p_img:
                    box_bg = Image.new("RGBA", (cell_size - 10, cell_size - 10), (255, 255, 255, 255))
                    preview.paste(box_bg, (c * cell_size + 5, r * cell_size + 5))
                    preview.paste(
                        p_img,
                        (c * cell_size + (cell_size - p_img.width) // 2, r * cell_size + (cell_size - p_img.height) // 2),
                        p_img,
                    )
            preview.save(ROOT / "work" / "all1_situational_master_preview.png")

    # 2. Regenerate member special_v3/preview_sheet.png and work/special_v3_master_preview.png
    members = ["chorong", "bomi", "eunji", "namjoo", "hayoung"]
    for m in members:
        v3_dir = CHAR_DIR / m / "special_v3"
        if v3_dir.is_dir():
            poses = [v3_dir / f"pose_{i:02d}.png" for i in range(1, 10) if (v3_dir / f"pose_{i:02d}.png").exists()]
            if len(poses) == 9:
                preview = Image.new("RGBA", (3 * 192, 3 * 192), (255, 255, 255, 255))
                for i, p_path in enumerate(poses):
                    pr, pc = i // 3, i % 3
                    with Image.open(p_path) as sp:
                        preview.paste(sp, (pc * 192, pr * 192), sp)
                preview.save(v3_dir / "preview_sheet.png")


def update_policy_and_registry(modified_rels: list[str]) -> None:
    if not POLICY_PATH.exists():
        return
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))
    approved = policy.get("approved", {})
    changed = False
    for rel in modified_rels:
        if rel in approved:
            full = CHAR_DIR / rel
            approved[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
            changed = True
    if changed:
        POLICY_PATH.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report fringe components without modifying files")
    args = parser.parse_args()

    modified_rels = []
    for p in sorted(CHAR_DIR.rglob("*.png")):
        if p.name == "preview_sheet.png":
            continue
        res = clean_sprite_file(p, dry_run=args.dry_run)
        if res:
            rel = p.relative_to(CHAR_DIR).as_posix()
            modified_rels.append(rel)
            print(f"[{'DRY' if args.dry_run else 'CLEANED'}] {rel}: {res}")

    if not args.dry_run and modified_rels:
        regenerate_preview_sheets()
        update_policy_and_registry(modified_rels)

    print(f"Total files {'detected' if args.dry_run else 'cleaned'}: {len(modified_rels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
