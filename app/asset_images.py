"""Pillow decoder and bounded LRU for the UI; no Tk root or display required."""
from __future__ import annotations

import hashlib
import io
import logging
import threading
from collections import OrderedDict

from PIL import Image

from app.engine.asset_policy import BASIC_ACTIONS, CANVAS_ANCHORS, MEMBERS
from app.engine.assets import AssetRegistry, AssetUnavailable
from app.engine.contracts import AnimationSpec
from app.resource_store import ResourceStore

log = logging.getLogger(__name__)


class AssetImageCache:
    """32 MiB decoded-pixel budget. UI-owned PhotoImages are additional memory.

    Returned images are borrowed, read-only by convention. Cache eviction only
    drops references and does not close images still held by the UI.
    """

    def __init__(self, registry: AssetRegistry, cache_bytes: int = 32 * 1024 * 1024):
        if cache_bytes < 0:
            raise ValueError("cache_bytes must be nonnegative")
        self.registry = registry
        self.cache_limit_bytes = cache_bytes
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, Image.Image] = OrderedDict()
        self._cache_bytes = 0

    @property
    def cache_size_bytes(self) -> int:
        with self._lock:
            return self._cache_bytes

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def _decode(self, source: str) -> Image.Image:
        with self._lock:
            if source in self._cache:
                self._cache.move_to_end(source)
                return self._cache[source]
        record = self.registry._record(source)
        store = getattr(self.registry, "store", None)
        if isinstance(store, ResourceStore):
            payload, digest = store.read_verified(source)
        else:
            payload = store.read_bytes(source) if store is not None else (self.registry.resource_root / source).read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
        if digest != record["sha256"]:
            raise ValueError("asset changed during load")
        with Image.open(io.BytesIO(payload)) as raw:
            image = raw.convert("RGBA")
            bbox = image.getchannel("A").getbbox()
            if bbox is None or list(bbox) != record["alpha_bbox"] or list(image.size) != record["source_size"]:
                raise ValueError("asset geometry differs from registry")
            mode = record.get("normalization_mode", "bbox")
            if mode == "preserve_canvas":
                anchor = CANVAS_ANCHORS.get(image.size)
                if (anchor is None or bbox[3] > (image.height if image.size != (256, 256) else anchor[1])
                        or record.get("anchor") != list(anchor)):
                    raise ValueError("preserved canvas must use a canonical safe anchor")
                normalized = image.copy()
            elif mode == "bbox":
                scale = record["normalization_scale"]
                width = max(1, round((bbox[2] - bbox[0]) * scale))
                height = max(1, round((bbox[3] - bbox[1]) * scale))
                if width > 256 or height > 244:
                    raise ValueError("normalized asset would clip")
                scaled = image.crop(bbox).resize((width, height), Image.Resampling.LANCZOS)
                normalized = Image.new("RGBA", (256, 256))
                # Masked paste would multiply antialiased edge alpha a second time.
                normalized.paste(scaled, ((256 - width) // 2, 244 - height))
            else:
                raise ValueError("unknown normalization mode")
        size = normalized.width * normalized.height * 4
        with self._lock:
            if source in self._cache:
                self._cache.move_to_end(source)
                return self._cache[source]
            if size <= self.cache_limit_bytes:
                while self._cache and self._cache_bytes + size > self.cache_limit_bytes:
                    _, evicted = self._cache.popitem(last=False)
                    self._cache_bytes -= evicted.width * evicted.height * 4
                self._cache[source] = normalized
                self._cache_bytes += size
        return normalized

    def load_animation(self, spec: AnimationSpec) -> tuple[AnimationSpec, tuple[Image.Image, ...]]:
        """Return the actual spec with its frames, including after fallback."""
        candidates = [spec.asset_id]
        if spec.member in MEMBERS:
            candidates += [f"{spec.member}.{action}" for action in BASIC_ACTIONS]
        seen = set()
        for key in candidates:
            if key in seen:
                continue
            seen.add(key)
            candidate = self.registry._spec(key)
            if candidate is None:
                continue
            try:
                frames = tuple(self._decode(path) for path in candidate.frames)
                return candidate, frames
            except (OSError, ValueError, KeyError, TypeError):
                log.warning("Cannot decode %s; trying safe baseline", key, exc_info=True)
        raise AssetUnavailable(f"No decodable approved animation for {spec.asset_id}")

    def load_frames(self, spec: AnimationSpec) -> tuple[Image.Image, ...]:
        """Convenience for static previews. Animation UI should use load_animation."""
        return self.load_animation(spec)[1]
