"""Hash-bound asset resolver; standard library and shared contracts only.

AnimationSpec paths name source files. app.asset_images.AssetImageCache owns
normalization and decoding; source files are never modified.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from app.engine.asset_policy import BASIC_ACTIONS, CANVAS_ANCHORS, KNOWN_BLOCKED, MEMBERS, file_sha256
from app.engine.contracts import AnimationSpec
from app.resource_store import FolderResourceStore, ResourceStore, normalize_resource_key, resource_store

log = logging.getLogger(__name__)


class AssetUnavailable(RuntimeError):
    """No approved baseline animation remains available."""


class AssetRegistry:
    def __init__(self, registry_path: Path, resource_root: Path | None = None,
                 store: ResourceStore | None = None) -> None:
        self.registry_path = Path(registry_path)
        self.resource_root = (Path(resource_root) if resource_root is not None
                              else self.registry_path.resolve().parent.parent).resolve()
        self.store = store if store is not None else resource_store(self.resource_root)
        if self.registry_path.is_file():
            raw_text = self.registry_path.read_text(encoding="utf-8-sig")
        else:
            try:
                rel = self.registry_path.resolve().relative_to(self.resource_root).as_posix()
            except ValueError:
                rel = "work/asset_registry.json"
            raw_text = self.store.read_text(rel, encoding="utf-8-sig")
        self.data = json.loads(raw_text)
        if self.data.get("schema_version") != 1 or not isinstance(self.data.get("assets"), dict) or not isinstance(self.data.get("files"), dict):
            raise ValueError("unsupported asset registry schema")
        self._verified_records: dict[str, tuple[tuple, str]] = {}
        self._characters_root = (self.resource_root / "work/characters").resolve()

    def _record(self, source: str) -> dict:
        norm = normalize_resource_key(source)
        prefix = "work/characters/"
        if not norm.startswith(prefix):
            raise ValueError("asset source must be under work/characters")
        relative = norm[len(prefix):]
        record = self.data["files"].get(relative.removesuffix(".png"))
        if not isinstance(record, dict) or record.get("path") != relative:
            raise ValueError("missing file metadata")
        if (relative in KNOWN_BLOCKED or Path(relative).name == "preview_sheet.png"
                or record.get("runtime_ok") is not True
                or record.get("ExcludeFromRuntime") is not False
                or record.get("review_status") != "approved"):
            raise ValueError("file is not approved for runtime")
        if isinstance(self.store, FolderResourceStore) and self.store.base_root != self.resource_root:
            path = (self.resource_root / norm).resolve()
            path.relative_to(self._characters_root)
        signature = self.store.stat_signature(norm)
        expected_hash = record.get("sha256")
        if self._verified_records.get(norm) != (signature, expected_hash):
            if self.store.sha256(norm) != expected_hash:
                raise ValueError("asset hash differs from approved bytes")
            # Keep only the latest verified version of each source.
            self._verified_records[norm] = (signature, expected_hash)
        return record

    def _spec(self, key: str) -> AnimationSpec | None:
        item = self.data["assets"].get(key)
        if not isinstance(item, dict) or item.get("runtime_ok") is not True:
            return None
        frames = item.get("frames")
        fps = item.get("fps")
        tags = item.get("tags", [])
        canvas, anchor = item.get("canvas"), item.get("anchor")
        if (not isinstance(canvas, list) or any(type(v) is not int for v in canvas)
                or tuple(canvas) not in CANVAS_ANCHORS
                or not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)):
            return None
        large = canvas != [256, 256]
        if (not isinstance(frames, list) or not frames or not all(isinstance(p, str) for p in frames)
                or not isinstance(fps, (int, float)) or isinstance(fps, bool)
                or not math.isfinite(fps) or fps <= 0
                or anchor != list(CANVAS_ANCHORS[tuple(canvas)])
                or (large and (item.get("action") in BASIC_ACTIONS
                               or not {"standby", "desktop_action"}.intersection(tags)))):
            return None
        try:
            for source in frames:
                record = self._record(source)
                if large or record.get("normalization_mode") == "preserve_canvas":
                    if (record.get("normalization_mode") != "preserve_canvas"
                            or record.get("normalized_size") != canvas or record.get("anchor") != anchor):
                        return None
        except (OSError, ValueError, TypeError):
            return None
        return AnimationSpec(
            asset_id=key, member=item.get("member"), action=item["action"],
            frames=tuple(frames), fps=float(fps), loop=bool(item.get("loop", True)),
            anchor=tuple(anchor), canvas=tuple(canvas), fallback=item.get("fallback"),
            interruptible=bool(item.get("interruptible", True)),
            tags=tuple(item.get("tags", [])), runtime_ok=True,
        )

    def resolve(self, member: str | None, action: str) -> AnimationSpec | None:
        prefix = member if member is not None else "shared"
        # Accept both action names and full asset ids without changing member.
        key = action if action.startswith(prefix + ".") else f"{prefix}.{action}"
        visited = set()
        while key not in visited:
            visited.add(key)
            spec = self._spec(key)
            if spec is not None:
                return spec
            item = self.data["assets"].get(key, {})
            fallback = item.get("fallback") if isinstance(item, dict) else None
            if not isinstance(fallback, str) or not fallback.startswith(prefix + "."):
                break
            key = fallback
        if member in MEMBERS:
            for basic in BASIC_ACTIONS:
                spec = self._spec(f"{member}.{basic}")
                if spec is not None:
                    return spec
        log.warning("No approved animation available for %s.%s", prefix, action)
        return None

    def actions(self, member: str | None, tag: str | None = None) -> tuple[str, ...]:
        return tuple(sorted(
            item["action"] for key, item in self.data["assets"].items()
            if item.get("member") == member and (tag is None or tag in item.get("tags", []))
            and self._spec(key) is not None
        ))
