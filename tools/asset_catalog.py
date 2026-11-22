"""Build a deterministic, hash-bound inventory without changing source artwork.

Names are declarations, not proof of pose semantics. New files remain pending
until their exact bytes are approved in the separate review policy.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image
from app.engine.asset_policy import MEMBERS, BASIC_ACTIONS, CANVAS_ANCHORS, KNOWN_BLOCKED, file_sha256

TARGET_SIZE = 256


def load_baselines(root: Path) -> dict[str, list[str]]:
    """Only explicit manifest sequences form the inherited baseline."""
    result = {}
    for member in MEMBERS:
        manifest = root / member / "manifest.json"
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        for action in BASIC_ACTIONS:
            paths = []
            for name in data.get("frames", {}).get(action, []):
                path = (root / member / name).resolve()
                relative = path.relative_to(root.resolve()).as_posix()
                paths.append(relative)
            if paths:
                result[f"{member}.{action}"] = paths
    return result


def baseline_policy(root: Path) -> dict:
    """Explicit bootstrap; this is inherited compatibility, not a visual audit."""
    baseline = {path for frames in load_baselines(root).values() for path in frames}
    return {
        "schema_version": 1,
        "approval_basis": "existing_manifest_baseline; not a new independent visual audit",
        "approved": {path: file_sha256(root / path) for path in sorted(baseline)
                     if (root / path).is_file() and path not in KNOWN_BLOCKED},
        "blocked": dict(KNOWN_BLOCKED),
    }


def inspect_asset(path: Path, root: Path, policy: dict) -> dict:
    relative = path.relative_to(root).as_posix()
    digest = file_sha256(path)
    reasons = []
    excluded = path.name == "preview_sheet.png"
    if excluded:
        reasons.append("preview_sheet is not an animation frame")
    blocked = {**policy.get("blocked", {}), **KNOWN_BLOCKED}
    if relative in blocked:
        reasons.append(blocked[relative])
    record = {
        "id": relative.removesuffix(".png"), "path": relative,
        "member": relative.split("/")[0], "declared_action": path.stem,
        "sha256": digest, "source_size": None, "alpha_bbox": None,
        "source_anchor": None, "normalized_size": [TARGET_SIZE, TARGET_SIZE],
        "anchor": [TARGET_SIZE / 2, TARGET_SIZE - 12],
        "anchor_basis": "alpha_bbox_bottom_center; airborne/prop poses need manual foot review",
        "ExcludeFromRuntime": excluded,
    }
    try:
        with Image.open(path) as image:
            record["source_size"] = list(image.size)
            record["source_mode"] = image.mode
            if image.mode != "RGBA":
                reasons.append("source is not RGBA")
            alpha = image.convert("RGBA").getchannel("A")
            bbox = alpha.getbbox()
            record["alpha_bbox"] = list(bbox) if bbox else None
            if bbox:
                record["source_anchor"] = [(bbox[0] + bbox[2]) / 2, bbox[3]]
                record["normalization_scale"] = (
                    TARGET_SIZE / image.width if image.size in ((192, 192), (256, 256))
                    else min((TARGET_SIZE - 24) / (bbox[2] - bbox[0]),
                             (TARGET_SIZE - 24) / (bbox[3] - bbox[1]))
                )
                scale = record["normalization_scale"]
                if (bbox[2] - bbox[0]) * scale > TARGET_SIZE or (bbox[3] - bbox[1]) * scale > TARGET_SIZE - 12:
                    reasons.append("normalization would clip content; manual scale required")
            else:
                reasons.append("empty alpha channel")
    except (OSError, ValueError) as error:
        reasons.append(f"cannot decode image: {error}")
    approved_hash = policy.get("approved", {}).get(relative)
    approved = approved_hash == digest
    if approved_hash is not None and not approved:
        reasons.append("approved bytes changed; review hash mismatch")
    preserved = policy.get("preserve_canvas", {})
    if relative in preserved:
        canvas = tuple(record["source_size"] or [])
        anchor = CANVAS_ANCHORS.get(canvas)
        if preserved[relative] != digest:
            reasons.append("preserved canvas bytes changed; review hash mismatch")
        elif (anchor is None or not record["alpha_bbox"]
              or record["alpha_bbox"][3] > (canvas[1] if canvas != (256, 256) else anchor[1])):
            reasons.append("preserved canvas requires canonical canvas and safe anchor")
        else:
            record.update(normalization_mode="preserve_canvas", normalization_scale=1.0,
                          normalized_size=list(canvas), anchor=list(anchor),
                          source_anchor=list(anchor), anchor_basis="reviewed_common_action_canvas")
    status = "excluded" if excluded else "blocked" if reasons else "approved" if approved else "pending_review"
    record.update(review_status=status, review_reasons=reasons,
                  runtime_ok=status == "approved")
    return record


def build_catalog(root: Path, policy: dict) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"asset root does not exist: {root}")
    if not isinstance(policy.get("preserve_canvas", {}), dict) or not isinstance(policy.get("animations", {}), dict):
        raise ValueError("preserve_canvas and animations must be objects")
    assets = {}
    for path in sorted(root.rglob("*.png"), key=lambda p: p.relative_to(root).as_posix()):
        # A symlink must not escape the selected asset tree.
        path.resolve().relative_to(root)
        item = inspect_asset(path, root, policy)
        assets[item["id"]] = item
    animations = {}
    for key, paths in load_baselines(root).items():
        member, action = key.split(".", 1)
        animations[key] = {
            "member": member, "action": action,
            "frames": [f"work/characters/{path}" for path in paths],
            "fps": {"idle": 3.125, "walk": 1000 / 140, "cheer": 1000 / 130, "sleep": 2.5}[action],
            "loop": True, "fallback": f"{member}.idle", "interruptible": True,
            "canvas": [256, 256], "anchor": [128, 244], "tags": ["base"],
        }
    baseline_ids = {path.removeprefix("work/characters/").removesuffix(".png")
                    for item in animations.values() for path in item["frames"]}
    for asset_id, item in assets.items():
        if asset_id not in baseline_ids:
            # Large canvases require an explicit standby animation declaration;
            # never manufacture a 256px static alias for a 384px frame.
            if item["normalized_size"] != [256, 256]:
                continue
            action = asset_id.split('/', 1)[-1]
            key = f"{item['member']}.{action}"
            animations[key] = {
                "member": item["member"] if item["member"] in MEMBERS else None, "action": action,
                "frames": [f"work/characters/{item['path']}"], "fps": 1, "loop": False,
                "fallback": f"{item['member']}.idle" if item["member"] in MEMBERS else None,
                "interruptible": True, "canvas": [256, 256], "anchor": [128, 244],
                "tags": ["static", "shared"] if item["member"] not in MEMBERS else ["static"],
            }
    # Optional, explicit multi-frame groups. Legacy baseline/static output is
    # byte-for-byte structurally unchanged when these policy fields are absent.
    for key, group in sorted(policy.get("animations", {}).items()):
        if not isinstance(key, str) or not isinstance(group, dict):
            raise ValueError("invalid animation declaration")
        member, action = group.get("member"), group.get("action")
        paths, fps = group.get("frames"), group.get("fps")
        tags = group.get("tags", [])
        secret = member == "shared" and action == "secret_clover_visitor"
        canvas = group.get("canvas", [256, 256])
        if (not isinstance(canvas, list) or any(type(v) is not int for v in canvas)
                or tuple(canvas) not in CANVAS_ANCHORS):
            raise ValueError(f"noncanonical animation canvas: {key}")
        anchor = list(CANVAS_ANCHORS[tuple(canvas)])
        if (member not in MEMBERS and not secret or not isinstance(action, str) or not action
                or key != f"{member}.{action}" or key in animations
                or not isinstance(paths, list) or not paths
                or type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0
                or not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)
                or type(group.get("loop", True)) is not bool
                or type(group.get("interruptible", True)) is not bool):
            raise ValueError(f"invalid animation declaration: {key}")
        if secret:
            trigger = group.get("trigger_policy")
            if (not isinstance(trigger, dict) or trigger.get("mode") != "easter_egg_only"
                    or trigger.get("allowed_contexts") != ["concert_stage_audience", "anniversary_0419"]
                    or trigger.get("allow_random_cameo") is not False
                    or trigger.get("expose_name_in_ui") is not False
                    or "secret" not in tags or "standby" in tags):
                raise ValueError("secret visitor requires the explicit hidden-only trigger policy")
        if canvas != [256, 256] and not {"standby", "desktop_action"}.intersection(tags):
            raise ValueError("large animations must be explicitly tagged standby or desktop_action")
        for relative in paths:
            if not isinstance(relative, str) or not relative.startswith(member + "/"):
                raise ValueError(f"invalid animation frame: {key}")
            resolved = (root / relative).resolve()
            resolved.relative_to(root / member)
            if relative.removesuffix(".png") not in assets:
                raise ValueError(f"animation frame missing from inventory: {relative}")
        modes = {assets[p.removesuffix(".png")].get("normalization_mode", "bbox")
                 for p in paths if assets[p.removesuffix(".png")]["runtime_ok"]}
        if len(modes) > 1:
            raise ValueError(f"animation mixes reviewed normalization modes: {key}")
        if any(assets[p.removesuffix(".png")]["normalized_size"] != canvas
               or assets[p.removesuffix(".png")]["anchor"] != anchor
               for p in paths if assets[p.removesuffix(".png")]["runtime_ok"]):
            raise ValueError(f"animation geometry differs from its reviewed files: {key}")
        animations[key] = {
            "member": None if secret else member, "action": action, "frames": [f"work/characters/{p}" for p in paths],
            "fps": fps, "loop": group.get("loop", True), "fallback": None if secret else f"{member}.idle",
            "interruptible": group.get("interruptible", True),
            "canvas": canvas, "anchor": anchor, "tags": tags,
        }
        if secret:
            animations[key]["trigger_policy"] = dict(group["trigger_policy"])
    for item in animations.values():
        item["runtime_ok"] = bool(item["frames"]) and all(
            assets.get(path.removeprefix("work/characters/").removesuffix(".png"), {}).get("runtime_ok", False)
            for path in item["frames"])
    return {
        "schema_version": 1, "asset_root": "work/characters", "normalized_size": [256, 256],
        "summary": {"png_count": len(assets),
                    "review_status_counts": dict(sorted(Counter(a["review_status"] for a in assets.values()).items())),
                    "baseline_frame_references": sum(len(paths) for paths in load_baselines(root).values())},
        "files": assets, "assets": animations,
    }
