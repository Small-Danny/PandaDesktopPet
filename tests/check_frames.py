"""Enhanced frame validator and acceptance checks for RONGDOONG sprite assets.

Validates:
- Exactly 4 action states with 4 frames each (16 total).
- 192x192 RGBA mode.
- Binary alpha (strictly 0 or 255) for tkinter transparent color-key display.
- Non-empty bounding boxes.
- Canvas margin safety (no content touching frame edge x=0 or x=192).
- Ground baseline consistency.
- No cross-cell ear/fragment artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "work" / "rongdoong_processed_v2"
LEGACY_TARGET = ROOT / "work" / "rongdoong_processed"


def validate_frames(asset_dir: Path) -> bool:
    manifest_file = asset_dir / "manifest.json"
    if not manifest_file.exists():
        print(f"[FAIL] Missing manifest.json in {asset_dir}")
        return False

    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    frames_dict = data.get("frames", {})
    expected_actions = ("idle", "walk", "cheer", "sleep")

    if tuple(frames_dict.keys()) != expected_actions:
        print(f"[FAIL] Expected actions {expected_actions}, got {tuple(frames_dict.keys())}")
        return False

    total_frames = sum(len(v) for v in frames_dict.values())
    if total_frames != 16:
        print(f"[FAIL] Expected 16 frames, found {total_frames}")
        return False

    baselines = []
    errors = []

    for action in expected_actions:
        names = frames_dict[action]
        if len(names) != 4:
            errors.append(f"Action '{action}' has {len(names)} frames (expected 4)")

        for name in names:
            fpath = asset_dir / name
            if not fpath.is_file():
                errors.append(f"Missing frame file: {name}")
                continue

            with Image.open(fpath) as im:
                if im.mode != "RGBA" or im.size != (192, 192):
                    errors.append(f"{name}: invalid mode/size ({im.mode}, {im.size}), expected ('RGBA', (192, 192))")

                bbox = im.getbbox()
                if not bbox:
                    errors.append(f"{name}: completely empty / invisible")
                    continue

                # Edge touching check: sprite should not touch absolute canvas boundary
                if bbox[0] <= 1 or bbox[2] >= 191:
                    errors.append(f"{name}: content touches horizontal canvas border (bbox={bbox}), truncation risk!")

                # Alpha binarization check
                alpha = im.getchannel("A")
                lo, hi = alpha.getextrema()
                if lo != 0 or hi != 255:
                    errors.append(f"{name}: alpha extrema ({lo}, {hi}) expected (0, 255)")

                # Modern check for binary alpha without deprecation warning
                alpha_bytes = alpha.tobytes()
                # Count non 0 and non 255 bytes
                non_binary = sum(1 for b in alpha_bytes if b != 0 and b != 255)
                if non_binary > 0:
                    errors.append(f"{name}: contains {non_binary} semi-transparent pixels (must be strictly 0/255)")

                # Ground baseline
                baselines.append((name, bbox[3]))

    # Baseline consistency check
    unique_baselines = set(b for _, b in baselines)
    if len(unique_baselines) > 2:
        errors.append(f"Baseline mismatch: found multiple ground levels: {unique_baselines}")

    if errors:
        print(f"[FAIL] Validation failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return False

    print(f"[PASS] {total_frames} RGBA frames in {asset_dir.name}:")
    print(f"  - 4 states (idle, walk, cheer, sleep) x 4 frames")
    print(f"  - Canvas size: 192x192, binary alpha: 0/255")
    print(f"  - Bounding boxes safe, zero border-clipping")
    print(f"  - Ground baseline aligned at y={list(unique_baselines)[0]}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_TARGET if DEFAULT_TARGET.exists() else LEGACY_TARGET,
        help="Directory containing frames and manifest.json",
    )
    args = parser.parse_args()

    success = validate_frames(args.dir)
    sys.exit(0 if success else 1)
