"""Stage explicit reviewed source cells; never approve or deploy runtime assets.

Example: python tools/stage_googleflow_assets.py --action festival_christmas
Outputs are confined to work/staging/. Source hashes and grid dimensions are
checked before processing; one uniform scale and common row baseline preserve
the original proportions and inter-frame jump offsets. No hole filling, face
replacement, or automatic selection of excluded/pending cells is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from extract_rongdoong import exterior_mask, defringe
from app.engine.asset_policy import CANVAS_ANCHORS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(parent.resolve()) or resolved == parent.resolve():
        raise ValueError(f"path outside allowed directory: {path}")
    return resolved


def checked_source(row: dict) -> Path:
    path = contained(ROOT / row["path"], ROOT / "reference")
    if digest(path) != row["sha256"]:
        raise ValueError(f"source changed: {row['path']}")
    with Image.open(path) as im:
        if list(im.size) != [row["width"], row["height"]]:
            raise ValueError(f"source size changed: {row['path']}")
    override = row.get("reviewed_source_override")
    if override is not None:
        if override.get("original_sha256") != row["sha256"]:
            raise ValueError("derived source is not bound to the original")
        derived = contained(ROOT / override["path"], ROOT / "work/staging")
        if digest(derived) != override["sha256"]:
            raise ValueError("derived source bytes changed")
        with Image.open(derived) as im:
            if list(im.size) != [row["width"], row["height"]]:
                raise ValueError("derived source must preserve sheet dimensions")
        return derived
    return path


def column_bounds(sheet: Image.Image, row: int, row_count: int, cols: int) -> list[int]:
    """Find blank separators near ideal grid lines; never cut through a prop.

    Grids define frame count, not necessarily exact equal-width source padding.
    Require a genuinely blank run of >=4px within 15% of one cell width.
    """
    band = sheet.crop((0, round(row * sheet.height / row_count), sheet.width,
                       round((row + 1) * sheet.height / row_count)))
    red, green, blue = band.split()
    foreground = ImageChops.darker(ImageChops.darker(red, green), blue).point(
        lambda v: 255 if v < 220 else 0)
    bounds = [0]
    for col in range(1, cols):
        ideal = sheet.width * col / cols
        radius = sheet.width / cols * .15
        left, right = max(bounds[-1] + 1, round(ideal - radius)), min(sheet.width - 1, round(ideal + radius))
        runs, start = [], None
        for x in range(left, right + 1):
            blank = foreground.crop((x, 0, x + 1, band.height)).getbbox() is None
            if blank and start is None:
                start = x
            elif not blank and start is not None:
                if x - start >= 4:
                    runs.append((start, x))
                start = None
        if start is not None and right + 1 - start >= 4:
            runs.append((start, right + 1))
        if not runs:
            raise ValueError(f"no blank separator at row {row}, column {col}; explicit crop review required")
        run = min(runs, key=lambda span: abs((span[0] + span[1]) / 2 - ideal))
        bounds.append((run[0] + run[1]) // 2)
    return bounds + [sheet.width]


def stage(row: dict, output: Path, calibration: dict | None = None) -> tuple[dict, list[Image.Image]]:
    if row.get("slice_enabled") is not True or row.get("status") != "candidate":
        raise ValueError("only explicitly enabled candidate rows may be staged")
    if row.get("category") not in ("daily_action", "festival_variant"):
        raise ValueError("UI icons, secret visitors and wallpapers use separate workflows")
    for key in ("member", "action"):
        if not isinstance(row.get(key), str) or not re.fullmatch(r"[a-z0-9_]+", row[key]):
            raise ValueError(f"invalid {key}")
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", row["grid"])
    if match is None:
        raise ValueError("explicit grid required")
    rows, cols = map(int, match.groups())
    cells = row["selected_cells"]
    excluded = {tuple(c) for c in row["excluded_cells"]}
    if not cells or len(set(map(tuple, cells))) != len(cells):
        raise ValueError("selection must be nonempty and unique")
    for r, c in cells:
        if type(r) is not int or type(c) is not int or not (0 <= r < rows and 0 <= c < cols) or (r, c) in excluded:
            raise ValueError("invalid or excluded cell")
    if len({c[0] for c in cells}) != 1:
        raise ValueError("select one source row per staged action; cross-row baseline requires review")
    order = row["play_order"]
    if not order or any(type(i) is not int or not 0 <= i < len(cells) for i in order):
        raise ValueError("invalid play_order")
    source = checked_source(row)
    with Image.open(source) as im:
        sheet = im.convert("RGB")
    masked, boxes, crops, normalized_boxes = [], [], [], []
    reviewed = row.get("reviewed_cell_masks")
    masks = {}
    if reviewed is not None:
        if reviewed.get("original_sha256") != row["sha256"]:
            raise ValueError("cell masks do not bind the original source")
        masks = {tuple(item["cell"]): item for item in reviewed["cells"]}
        if len(masks) != len(reviewed["cells"]) or set(masks) != {tuple(c) for c in cells}:
            raise ValueError("cell masks must match the entire selection")
    dividers = None if masks else column_bounds(sheet, cells[0][0], rows, cols)
    for r, c in cells:
        item = masks.get((r, c))
        crop = tuple(item["crop"]) if item else (dividers[c], round(r * sheet.height / rows),
                                               dividers[c + 1], round((r + 1) * sheet.height / rows))
        if (len(crop) != 4 or any(type(v) is not int for v in crop)
                or not 0 <= crop[0] < crop[2] <= sheet.width
                or not 0 <= crop[1] < crop[3] <= sheet.height):
            raise ValueError("invalid reviewed cell crop")
        cell = sheet.crop(crop)
        rgba = cell.convert("RGBA")
        if item:
            mask_path = contained(ROOT / item["alpha_mask"], ROOT / "work/staging")
            if digest(mask_path) != item["sha256"]:
                raise ValueError("reviewed cell mask changed")
            with Image.open(mask_path) as image:
                alpha = image.convert("L")
            if alpha.size != cell.size or not set(alpha.tobytes()) <= {0, 255}:
                raise ValueError("cell mask must be binary and match its crop")
            rgba.putalpha(alpha)
        else:
            rgba.putalpha(exterior_mask(cell, threshold=220))
        box = rgba.getchannel("A").getbbox()
        if box is None:
            raise ValueError("empty foreground")
        # Content on a split line can belong to a neighbour or be clipped.
        if box[0] <= 1 or box[1] <= 1 or box[2] >= cell.width - 1 or box[3] >= cell.height - 1:
            raise ValueError(f"foreground touches cell boundary {r,c}; needs explicit reviewed crop")
        masked.append(rgba)
        boxes.append(box)
        crops.append(crop)
        offset_x = crop[0] - c * sheet.width / cols
        offset_y = crop[1] - r * sheet.height / rows
        normalized_boxes.append((box[0] + offset_x, box[1] + offset_y,
                                 box[2] + offset_x, box[3] + offset_y))
    common = (min(b[0] for b in normalized_boxes), min(b[1] for b in normalized_boxes),
              max(b[2] for b in normalized_boxes), max(b[3] for b in normalized_boxes))
    scale = min(220 / (common[3] - common[1]), 240 / (common[2] - common[0]))
    canvas, anchor = (256, 256), (128, 244)
    if calibration is not None:
        if (calibration.get("source_sha256") != row["sha256"]
                or calibration.get("selected_cells") != cells
                or calibration.get("play_order") != order
                or calibration.get("member") != row["member"]
                or calibration.get("action") != row["action"]):
            raise ValueError("calibration does not match exact source and selection")
        base = contained(ROOT / calibration["base_source"], ROOT / "work/characters")
        if digest(base) != calibration["base_source_sha256"]:
            raise ValueError("calibration base bytes changed")
        scale = calibration.get("source_uniform_scale")
        if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
            raise ValueError("invalid reviewed uniform scale")
        supplied_canvas = calibration.get("canvas", [384, 384])
        if (not isinstance(supplied_canvas, list) or any(type(v) is not int for v in supplied_canvas)
                or tuple(supplied_canvas) not in CANVAS_ANCHORS):
            raise ValueError("calibration canvas is not canonical")
        canvas = tuple(supplied_canvas)
        anchor = CANVAS_ANCHORS[canvas]
    feet = calibration.get("source_feet_y") if calibration else None
    if feet is not None and (not isinstance(feet, list) or len(feet) != len(cells)
                            or any(type(v) not in (int, float) or not math.isfinite(v)
                                   or not 0 < v <= sheet.height for v in feet)):
        raise ValueError("invalid per-frame foot landmarks")
    center_x = (common[0] + common[2]) / 2
    centers = calibration.get("source_centers_x") if calibration else None
    if centers is not None and (not isinstance(centers, list) or len(centers) != len(cells)
                               or any(type(v) not in (int, float) or not math.isfinite(v)
                                      or not 0 < v < sheet.width for v in centers)):
        raise ValueError("invalid per-frame horizontal landmarks")
    frames, frame_records, pending_writes = [], [], []
    dest = output / row["member"] / row["action"]
    dest.mkdir(parents=True, exist_ok=True)
    for idx, (rgba, box, crop, normalized) in enumerate(zip(masked, boxes, crops, normalized_boxes)):
        clean = defringe(rgba.crop(box))
        size = (max(1, round(clean.width * scale)), max(1, round(clean.height * scale)))
        scaled = clean.resize(size, Image.Resampling.LANCZOS)
        # Optional reviewed landmarks are absolute source coordinates, unlike
        # the default common grid center. This handles uneven mother-sheet spacing.
        relative_x = crop[0] + box[0] - centers[idx] if centers is not None else normalized[0] - center_x
        x = round(anchor[0] + relative_x * scale)
        y = round(anchor[1] + (normalized[1] - (feet[idx] if feet is not None else common[3])) * scale)
        if x < 0 or y < 0 or x + size[0] > canvas[0] or y + size[1] > canvas[1]:
            raise ValueError("scaled content would clip")
        frame = Image.new("RGBA", canvas)
        frame.paste(scaled, (x, y))  # no alpha mask: avoid applying alpha twice
        frame.putalpha(frame.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
        path = dest / f"frame_{idx + 1:02d}.png"
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        data = buffer.getvalue()
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"different staging bytes already exist: {path}; choose another output")
        pending_writes.append((path, data))
        frame_records.append({"cell": cells[idx], "source_crop": crop, "source_bbox": box,
                              "path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
                              "alpha_bbox": frame.getchannel("A").getbbox()})
        frames.append(frame)
    # Calculate and validate the whole action before writing its first PNG.
    for path, data in pending_writes:
        path.write_bytes(data)
    # A GIF is a review artifact, not an approved AnimationSpec or runtime fps.
    review_frames = []
    for i in order:
        bg = Image.new("RGBA", canvas, "#173a2a")
        bg.alpha_composite(frames[i])
        review_frames.append(bg.convert("RGB"))
    review_frames[0].save(dest / "review.gif", save_all=True, append_images=review_frames[1:],
                          duration=180, loop=0, disposal=2)
    return {"member": row["member"], "action": row["action"], "source": row["path"],
            "source_sha256": row["sha256"], "selected_cells": cells, "play_order": order,
            "reviewed_source_override": row.get("reviewed_source_override"),
            "reviewed_cell_masks": reviewed,
            "trigger_policy": row.get("trigger_policy"),
            "original_declaration": row.get("original_declaration"),
            "common_bbox": common, "scale": scale, "canvas": list(canvas), "anchor": list(anchor),
            "source_feet_y": feet,
            "review_duration_ms": 180, "status": "review_pending", "frames": frame_records}, frames


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "work/googleflow_1108_manifest.json")
    parser.add_argument("--section", default="files_1108_new_folder",
                        choices=("root_files", "files_1108", "files_1108_new_folder"))
    parser.add_argument("--action", action="append")
    parser.add_argument("--asset-id", action="append", help="Select one exact member.action instead of all members sharing an action")
    parser.add_argument("--calibration", type=Path, help="Exact-source reviewed landmark scales; still stages review-pending assets")
    parser.add_argument("--source-overrides", type=Path, help="Explicit SHA-bound derived sheets under work/staging; originals unchanged")
    parser.add_argument("--cell-masks", type=Path, help="Explicit SHA-bound actor masks/crops; staging only")
    parser.add_argument("--out", type=Path, default=ROOT / "work/staging/googleflow_20261108/christmas_v1")
    args = parser.parse_args()
    output = contained(args.out, ROOT / "work/staging")
    raw = args.manifest.read_bytes()
    doc = json.loads(raw.decode("utf-8-sig"))
    calibration_raw = args.calibration.read_bytes() if args.calibration else None
    calibration = json.loads(calibration_raw) if calibration_raw else None
    if calibration is not None and calibration.get("status") != "landmarks_reviewed":
        parser.error("calibration must have landmarks_reviewed status")
    if not args.action and not args.asset_id:
        parser.error("at least one action or asset-id is required")
    candidates = [r for r in doc[args.section] if r.get("action") in (args.action or [])
                  or f"{r.get('member')}.{r.get('action')}" in (args.asset_id or [])]
    override_raw = args.source_overrides.read_bytes() if args.source_overrides else None
    overrides = json.loads(override_raw) if override_raw else {}
    candidates = [dict(r, reviewed_source_override=overrides[f"{r['member']}.{r['action']}"])
                  if f"{r['member']}.{r['action']}" in overrides else r for r in candidates]
    masks_raw = args.cell_masks.read_bytes() if args.cell_masks else None
    mask_groups = json.loads(masks_raw) if masks_raw else {}
    candidates = [dict(r, reviewed_cell_masks=mask_groups[f"{r['member']}.{r['action']}"])
                  if f"{r['member']}.{r['action']}" in mask_groups else r for r in candidates]
    if not candidates:
        parser.error("no matching source records")
    ids = [(r.get("member"), r.get("action")) for r in candidates]
    if len(set(ids)) != len(ids):
        parser.error("duplicate member/action; select a narrower source batch")
    scales = {(r["member"], r["action"]): r for r in calibration["records"]} if calibration else {}
    if calibration is not None and (len(scales) != len(calibration["records"]) or set(scales) != set(ids)):
        parser.error("calibration must match the complete selected batch")
    wallpapers = [r for group in doc.values() if isinstance(group, list) for r in group
                  if isinstance(r, dict) and r.get("category") == "standby_wallpaper"]
    # Validate every chosen source and wallpaper before producing the batch.
    for row in candidates + wallpapers:
        checked_source(row)
    output.mkdir(parents=True, exist_ok=True)
    report = {"manifest_sha256": hashlib.sha256(raw).hexdigest(), "tool_sha256": digest(Path(__file__)),
              "runtime_adopted": False, "records": [], "errors": []}
    report["calibration_sha256"] = hashlib.sha256(calibration_raw).hexdigest() if calibration_raw else None
    report["source_overrides_sha256"] = hashlib.sha256(override_raw).hexdigest() if override_raw else None
    report["cell_masks_sha256"] = hashlib.sha256(masks_raw).hexdigest() if masks_raw else None
    tile = max(max(r.get("canvas", [384, 384])) for r in scales.values()) if calibration else 256
    montage = Image.new("RGB", (tile * 4, len(candidates) * (tile + 24)), "#173a2a")
    draw = ImageDraw.Draw(montage)
    for index, row in enumerate(candidates):
        try:
            record, frames = stage(row, output, scales.get((row["member"], row["action"])))
            report["records"].append(record)
            for col, frame in enumerate(frames):
                montage.paste(frame, (col * tile, index * (tile + 24) + 24), frame)
            draw.text((4, index * (tile + 24) + 4), f"{row['member']} / {row['action']} REVIEW_PENDING", fill="white")
            print(f"[STAGED] {row['member']}.{row['action']}: {len(frames)} frames", flush=True)
        except (ValueError, OSError) as error:
            report["errors"].append({"source": row["path"], "error": str(error)})
            print(f"[REVIEW] {row['filename']}: {error}", flush=True)
    (output / "wallpaper_sources.json").write_text(json.dumps(
        {"status": "review_pending", "records": wallpapers}, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.manifest.read_bytes() != raw:
        raise ValueError("manifest changed during batch; output cannot be accepted")
    if args.calibration and args.calibration.read_bytes() != calibration_raw:
        raise ValueError("calibration changed during batch; output cannot be accepted")
    if args.source_overrides and args.source_overrides.read_bytes() != override_raw:
        raise ValueError("source overrides changed during batch; output cannot be accepted")
    if args.cell_masks and args.cell_masks.read_bytes() != masks_raw:
        raise ValueError("cell masks changed during batch; output cannot be accepted")
    for row in candidates + wallpapers:
        checked_source(row)
    montage.save(output / "contact_sheet.png")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
