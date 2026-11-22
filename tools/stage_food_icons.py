"""Stage the reviewed eight-food sheet using explicit cells and edge flood-fill.

Only work/staging outputs are permitted. No global white-to-transparent filter
is used: enclosed white plates, cream and highlights keep their original RGB.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.extract_rongdoong import exterior_mask

SOURCE_SHA = "28a6a9c3df0237bde438bd03b4a359e5fbcce487cb7c1fd9a090175cddb8f799"
IDS = {"buldak", "chicken_breast", "coriander", "matcha_cake", "mint_choco", "soju", "stinky_tofu", "whiskey"}


def extract_icon(cell: Image.Image, size: int) -> Image.Image:
    rgba = cell.convert("RGBA")
    rgba.putalpha(exterior_mask(cell, threshold=220))
    box = rgba.getchannel("A").getbbox()
    if box is None or box[0] <= 0 or box[1] <= 0 or box[2] >= cell.width or box[3] >= cell.height:
        raise ValueError("empty or boundary-touching foreground; crop needs review")
    art = rgba.crop(box)
    padding = round(size * 10 / 128)
    scale = min((size - 2 * padding) / art.width, (size - 2 * padding) / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.Resampling.LANCZOS)
    art.putalpha(art.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
    result = Image.new("RGBA", (size, size))
    result.paste(art, ((size - art.width) // 2, (size - art.height) // 2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "work/googleflow_1108_manifest.json")
    parser.add_argument("--out", type=Path, default=ROOT / "work/staging/googleflow_20261108/food_icons_v1")
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT / "work/staging") or output == ROOT / "work/staging":
        raise ValueError("output must be a subdirectory of work/staging")
    raw = args.manifest.read_bytes()
    doc = json.loads(raw.decode("utf-8-sig"))
    rows = [r for group in doc.values() if isinstance(group, list) for r in group
            if isinstance(r, dict) and r.get("category") == "food_icon_sheet" and r.get("sha256") == SOURCE_SHA]
    if len(rows) != 1:
        raise ValueError("expected the exact independently reviewed food sheet")
    row = rows[0]
    source = (ROOT / row["path"]).resolve()
    source.relative_to(ROOT / "reference")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError("source bytes changed")
    mappings = row["food_cell_mapping"]
    if (len(mappings) != 8 or {m["food_id"] for m in mappings} != IDS
            or {tuple(m["cell"]) for m in mappings} != {(r, c) for r in range(2) for c in range(4)}):
        raise ValueError("food ID mapping must be complete and unique")
    xs, ys = row["x_splits"], row["y_splits"]
    if xs != [0, 634, 1212, 1825, 2400] or ys != [0, 845, 1792]:
        raise ValueError("split coordinates differ from reviewed crop")
    with Image.open(io.BytesIO(data)) as image:
        sheet = image.convert("RGB")
    if sheet.size != (2400, 1792):
        raise ValueError("source dimensions changed")
    report = {"status": "review_pending", "runtime_adopted": False, "source_sha256": SOURCE_SHA,
              "manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "records": []}
    pending = []
    preview = Image.new("RGB", (8 * 160, 2 * 210), "#1e1e24")
    draw = ImageDraw.Draw(preview)
    draw.rectangle((0, 210, preview.width, preview.height), fill="#fff5f8")
    for index, mapping in enumerate(mappings):
        r, c = mapping["cell"]
        crop = (xs[c], ys[r], xs[c + 1], ys[r + 1])
        cell = sheet.crop(crop)
        for size in (128, 64):
            icon = extract_icon(cell, size)
            suffix = "" if size == 128 else "_64"
            name = f"{mapping['food_id']}{suffix}.png"
            buffer = io.BytesIO()
            icon.save(buffer, "PNG")
            payload = buffer.getvalue()
            path = output / name
            if path.exists() and path.read_bytes() != payload:
                raise ValueError("different staged bytes exist; choose a new output")
            pending.append((path, payload))
            report["records"].append(dict(food_id=mapping["food_id"], size=size, cell=[r, c],
                crop=crop, filename=name, sha256=hashlib.sha256(payload).hexdigest(), alpha_bbox=icon.getchannel("A").getbbox()))
            for y in (0, 210):
                preview.paste(icon, (index * 160 + (160 - size) // 2, y + (24 if size == 128 else 150)), icon)
        for y in (0, 210):
            draw.text((index * 160 + 4, y + 4), mapping["food_id"], fill="white" if y == 0 else "#3b1e1e")
    if source.read_bytes() != data or args.manifest.read_bytes() != raw:
        raise ValueError("source/manifest changed during staging")
    output.mkdir(parents=True, exist_ok=True)
    for path, payload in pending:
        path.write_bytes(payload)
    preview.save(output / "dark_light_preview.png")
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Staged {len(pending)} icons; production food directory unchanged")


if __name__ == "__main__":
    main()
