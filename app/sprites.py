"""sprites.py — Tk sprite loading for desktop actors (host pet + cameo guests).

Source of truth is the asset registry (``engine.assets.AssetRegistry``) with
Pillow decoding via ``asset_images.AssetImageCache``: only approved,
hash-verified frames are used, normalized to 256x256 with the feet anchor at
(128, 244). Frames are then scaled to the on-screen size and their alpha is
made binary, because the windows use a colour key (``-transparentcolor``) and
semi-transparent edge pixels would otherwise show a magenta halo.

If the registry is missing or unusable (e.g. an old portable build), the
legacy per-member ``manifest.json`` sprites are used instead.
"""
from __future__ import annotations

import json
import logging
import statistics
import tkinter as tk
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageTk

from app.engine.contracts import BASE_ACTIONS
from app.resource_store import resource_store
from app.action_cache import LazyPhotoList
from app.sprite_polish import alpha_bleed, polish_frame, prepare_ulw_source
from app.visual_calibration import action_scale

log = logging.getLogger(__name__)

DISPLAY_PX = 192          # on-screen sprite size (legacy sprites were 192x192)
ALPHA_THRESHOLD = 128
# Members with asymmetric identity marks (Bomi: mole under the LEFT eye, cross-body
# bag; Eunji: mole above her RIGHT eye, "A" cap lettering). Never mirror their art:
# a member with drawn left-walk art walks with it; everyone else (and every static
# pose) keeps the authored orientation.
MIRROR_UNSAFE = frozenset({"bomi", "eunji"})
# Members that have an approved walk_left sequence (bomi: hand-fixed; eunji: mirrored profile, mole
# removed because walking left shows her left side, which has no mole — 2026-11-22).
DIRECTIONAL_WALK_LEFT = frozenset({"bomi", "eunji"})


def directional_action(member: str, action: str, facing: int = 1) -> str:
    """Resolve asymmetric walking art before any consumer considers mirroring."""
    if member in DIRECTIONAL_WALK_LEFT and facing < 0 and action in ("walk", "walk_left"):
        return "walk_left"
    return action

# Registry frames are 256x256 with the feet at (128, 244), but the members were
# drawn at different scales (visible body height 179..221 px), so Eunji/Namjoo
# looked much smaller than Chorong/Bomi side by side. Every member is rescaled
# about the feet to the same visible height on a slightly wider shared canvas
# (wide cheer poses must not be clipped).
SOURCE_PX = 256
SOURCE_ANCHOR = (128, 244)
BODY_PX = 220                     # target visible height in source px (Chorong's)
CANVAS_SRC = (296, SOURCE_PX)     # shared canvas in source px (w, h)


@dataclass
class MemberSprites:
    member: str
    frames: dict[str, list[tk.PhotoImage]]               # facing right
    source: str                                           # "registry" | "manifest"
    _pil: dict[str, list[Image.Image]] = field(default_factory=dict, repr=False)
    _flipped: dict[str, list[tk.PhotoImage]] = field(default_factory=dict, repr=False)
    _flipped_pil: dict[str, list[Image.Image]] = field(default_factory=dict, repr=False)
    offsets: dict[str, tuple[int, int]] = field(default_factory=dict, repr=False)
    durations: dict[str, float] = field(default_factory=dict, repr=False)

    def flipped(self, action: str) -> list[tk.PhotoImage]:
        """Left-facing frames, created lazily."""
        if self.member in MIRROR_UNSAFE:
            return self.frames.get(directional_action(self.member, action, -1),
                                   self.frames.get(action, self.frames["idle"]))
        if action not in self._flipped:
            # Tk images are built only for frames actually drawn (none on a ULW pet).
            self._flipped[action] = LazyPhotoList(
                self.flipped_pil(action), factory=ImageTk.PhotoImage)
        return self._flipped[action]

    def flipped_pil(self, action: str) -> list[Image.Image]:
        """Left-facing PIL frames, created lazily."""
        if self.member in MIRROR_UNSAFE:
            directed = directional_action(self.member, action, -1)
            return self._pil.get(directed, self._pil.get(action, self._pil.get("idle", [])))
        if action not in self._flipped_pil:
            self._flipped_pil[action] = [
                im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                for im in self._pil.get(action, [])
            ]
        return self._flipped_pil[action]

    def get(self, action: str, facing: int = 1) -> list[tk.PhotoImage]:
        directed = directional_action(self.member, action, facing)
        if directed != action and directed in self.frames:
            return self.frames[directed]
        action = action if action in self.frames else "idle"
        if facing < 0:
            return self.flipped(action)
        return self.frames[action]

    def get_pil(self, action: str, facing: int = 1) -> list[Image.Image]:
        """Return right- or left-facing PIL RGBA frames for ``action``."""
        directed = directional_action(self.member, action, facing)
        if directed != action and directed in self._pil:
            return self._pil[directed]
        action = action if action in self._pil else "idle"
        if facing < 0:
            return self.flipped_pil(action)
        return self._pil.get(action, [])

    def offset(self, action: str, facing: int = 1) -> tuple[int, int]:
        return self.offsets.get(directional_action(self.member, action, facing), (0, 0))

    def frame_ms(self, action: str, facing: int, default: float) -> float:
        return self.durations.get(directional_action(self.member, action, facing), default)


def body_height(images: list[Image.Image]) -> int:
    """Median visible (alpha >= threshold) height of ``images``; robust to a raised-arm frame."""
    heights = []
    for im in images:
        box = im.convert("RGBA").getchannel("A").point(
            lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()
        if box:
            heights.append(box[3] - box[1])
    return int(statistics.median(heights)) if heights else 0


def rescale_about_feet(image: Image.Image, scale: float, canvas: tuple[int, int] = CANVAS_SRC) -> Image.Image:
    """Scale a 256x256 registry frame about its feet anchor onto ``canvas``.

    The anchor lands bottom-centre with the same bottom margin as the source.
    """
    im = image.convert("RGBA")
    if scale != 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    ax, ay = SOURCE_ANCHOR
    cw, ch = canvas
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.paste(im, (round(cw / 2 - ax * scale), round(ch - (SOURCE_PX - ay) - ay * scale)), im)
    return out


def prepare_frame(image: Image.Image, size: int = DISPLAY_PX, *, binary_alpha: bool = True,
                  edge_refine: bool = False) -> Image.Image:
    """Scale to display height ``size`` (keeping aspect) and optionally binarize alpha for colour-key windows."""
    im = prepare_ulw_source(image, soft_binarize=True) if (not binary_alpha and edge_refine) else alpha_bleed(image)
    if im.height != size:
        im = im.resize((round(im.width * size / im.height), size), Image.Resampling.LANCZOS)
    if binary_alpha:
        alpha = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0)
        im.putalpha(alpha)
    return im


def scale_to_display(image: Image.Image, scale: float, size: int = DISPLAY_PX, *,
                     binary_alpha: bool = True, edge_refine: bool = False) -> Image.Image:
    """``prepare_frame(rescale_about_feet(image, scale), size)`` with a single resize.

    Two LANCZOS passes soften the art; this lands the 256x256 registry frame
    directly on the display canvas with the same feet anchor. When ``binary_alpha=False``,
    full 8-bit antialiased alpha is preserved for Win32 UpdateLayeredWindow.
    """
    k = size / SOURCE_PX
    s = scale * k
    im = prepare_ulw_source(image, soft_binarize=True) if (not binary_alpha and edge_refine) else alpha_bleed(image)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.Resampling.LANCZOS)
    ax, ay = SOURCE_ANCHOR
    out = Image.new("RGBA", (round(CANVAS_SRC[0] * k), size), (0, 0, 0, 0))
    out.paste(im, (round(CANVAS_SRC[0] * k / 2 - ax * s), round(size - (SOURCE_PX - ay) * k - ay * s)), im)
    if binary_alpha:
        alpha = out.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0)
        out.putalpha(alpha)
    return out


def unclipped_base_scale(images, scale: float) -> float:
    """Keep all base poses inside the shared canvas while retaining the feet anchor."""
    for im in images:
        box = im.getchannel("A").getbbox()
        if box is None:
            continue
        if box[1] < SOURCE_ANCHOR[1]:
            scale = min(scale, (SOURCE_ANCHOR[1] - 1) / (SOURCE_ANCHOR[1] - box[1]))
        reach = max(SOURCE_ANCHOR[0] - box[0], box[2] - SOURCE_ANCHOR[0])
        if reach > 0:
            scale = min(scale, (CANVAS_SRC[0] / 2 - 1) / reach)
    return scale


class SpriteLibrary:
    def __init__(self, resource_root: Path, display_px: int = DISPLAY_PX, equalize: bool = True,
                 polish: bool = True, binary_alpha: bool = True, edge_refine: bool = False) -> None:
        self.resource_root = Path(resource_root)
        self.display_px = display_px
        self.equalize = equalize
        self.polish = polish
        self.binary_alpha = binary_alpha
        self.edge_refine = bool(edge_refine)
        self._members: dict[str, MemberSprites] = {}
        self._directional_placement: dict[str, tuple[tuple[int, int], float]] = {}
        self._peer_library: Optional["SpriteLibrary"] = None
        self.registry = None
        self.cache = None
        registry_path = self.resource_root / "work" / "asset_registry.json"
        try:
            from app.asset_images import AssetImageCache
            from app.engine.assets import AssetRegistry

            self.registry = AssetRegistry(registry_path, self.resource_root)
            self.cache = AssetImageCache(self.registry)
        except Exception:
            log.exception("asset registry unavailable (%s); using legacy manifests", registry_path)

    def with_binary_alpha(self, binary_alpha: bool = True) -> "SpriteLibrary":
        """Return a SpriteLibrary view sharing registry/cache with the requested binary_alpha mode."""
        target = bool(binary_alpha)
        if bool(self.binary_alpha) == target:
            return self
        peer = getattr(self, "_peer_library", None)
        if peer is not None and bool(peer.binary_alpha) == target:
            if peer.display_px != self.display_px or bool(getattr(peer, "edge_refine", False)) != bool(self.edge_refine):
                peer.edge_refine = bool(self.edge_refine)
                peer.display_px = self.display_px
                peer._members.clear()
                peer._directional_placement.clear()
            return peer
        peer = object.__new__(SpriteLibrary)
        peer.resource_root = self.resource_root
        peer.display_px = self.display_px
        peer.equalize = self.equalize
        peer.polish = self.polish
        peer.binary_alpha = target
        peer.edge_refine = bool(self.edge_refine)
        peer._members = {}
        peer._directional_placement = {}
        peer._peer_library = self
        peer.registry = self.registry
        peer.cache = self.cache
        self._peer_library = peer
        return peer

    def set_edge_refine(self, edge_refine: bool) -> None:
        """Toggle 8-bit medium/large contour refinement and keep peer library synchronized."""
        target = bool(edge_refine)
        if bool(getattr(self, "edge_refine", False)) != target:
            self.edge_refine = target
            self._members.clear()
            self._directional_placement.clear()
        peer = getattr(self, "_peer_library", None)
        if peer is not None and bool(getattr(peer, "edge_refine", False)) != target:
            peer.edge_refine = target
            peer._members.clear()
            peer._directional_placement.clear()

    def resize(self, display_px: int, edge_refine: Optional[bool] = None) -> None:
        """Switch display height while retaining the verified registry and decoded source cache."""
        refine_changed = (
            edge_refine is not None
            and bool(edge_refine) != bool(getattr(self, "edge_refine", False))
        )
        if refine_changed:
            self.edge_refine = bool(edge_refine)
        if self.display_px == display_px and not refine_changed:
            return
        self.display_px = display_px
        self._members.clear()
        self._directional_placement.clear()
        peer = getattr(self, "_peer_library", None)
        if peer is not None:
            if refine_changed:
                peer.edge_refine = self.edge_refine
            if peer.display_px != display_px or refine_changed:
                peer.display_px = display_px
                peer._members.clear()
                peer._directional_placement.clear()

    def load_member_pil(
        self,
        member: str,
        yield_fn: Optional[Callable[[], None]] = None,
    ) -> tuple[dict[str, list[Image.Image]], str]:
        """Thread-safe pure-PIL load/scale/polish of the 4 base actions (no Tk PhotoImage)."""
        pil, source = self._load_registry(member), "registry"
        if pil is None:
            pil, source = self._load_manifest(member), "manifest"
        scale = self._equal_scale(member, pil) if (self.equalize and source == "registry") else None
        prepared: dict[str, list[Image.Image]] = {}
        for action, ims in pil.items():
            frames: list[Image.Image] = []
            own_scale = (unclipped_base_scale(ims, action_scale(member, action, scale))
                         if scale is not None else None)
            for im in ims:
                if own_scale is not None:
                    out = scale_to_display(
                        im, own_scale, self.display_px,
                        binary_alpha=self.binary_alpha, edge_refine=self.edge_refine,
                    )
                else:
                    out = prepare_frame(
                        im, self.display_px,
                        binary_alpha=self.binary_alpha, edge_refine=self.edge_refine,
                    )
                if self.polish:
                    out = polish_frame(
                        out, self.display_px,
                        binary_alpha=self.binary_alpha, edge_refine=self.edge_refine,
                    )
                frames.append(out)
                if yield_fn is not None:
                    yield_fn()
            prepared[action] = frames
        if member in DIRECTIONAL_WALK_LEFT and source == "registry":
            # Exact large-canvas art retains its own dimensions and feet offset.
            from app.action_frames import load_exact_action
            left = load_exact_action(self, member, "walk_left")
            if left is not None:
                prepared["walk_left"] = list(left.frames)
                self._directional_placement[member] = (left.offset, left.frame_ms)
        return prepared, source

    def load_member(self, member: str, master: tk.Misc) -> MemberSprites:
        """Load (or return cached) right-facing PhotoImages for the 4 base actions."""
        if member in self._members:
            return self._members[member]
        from app.standby import _prepare_member_pil
        prepared, source = _prepare_member_pil(self, member)
        frames = {a: LazyPhotoList(ims, master, factory=ImageTk.PhotoImage) for a, ims in prepared.items()}
        sprites = MemberSprites(member, frames, source, _pil=prepared)
        if member in self._directional_placement:
            offset, duration = self._directional_placement[member]
            sprites.offsets["walk_left"] = offset
            sprites.durations["walk_left"] = duration
        self._members[member] = sprites
        return sprites

    @staticmethod
    def _equal_scale(member: str, pil: dict[str, list[Image.Image]]) -> float:
        """Standing face reference, without counting caps or a crouched walking pose."""
        h = body_height(pil.get("idle", []))
        scale = action_scale(member, "idle", BODY_PX / h if h else 1.0)
        scale = unclipped_base_scale(pil.get("idle", []), scale)
        log.debug("%s body height %d px -> scale %.3f", member, h, scale)
        return scale

    @classmethod
    def _equalize(cls, member: str, pil: dict[str, list[Image.Image]]) -> dict[str, list[Image.Image]]:
        """Equalized frames still in source px (used by tests and tools)."""
        scale = cls._equal_scale(member, pil)
        return {a: [rescale_about_feet(im, unclipped_base_scale(ims, action_scale(member, a, scale)))
                    for im in ims] for a, ims in pil.items()}

    def _load_registry(self, member: str) -> Optional[dict[str, list[Image.Image]]]:
        if self.registry is None or self.cache is None:
            return None
        out: dict[str, list[Image.Image]] = {}
        store = getattr(self.registry, "store", None)
        ctx = store.session() if store is not None else nullcontext()
        try:
            with ctx:
                for action in BASE_ACTIONS:
                    spec = self.registry.resolve(member, action)
                    if spec is None:
                        return None
                    actual, images = self.cache.load_animation(spec)
                    if actual.action != action:
                        log.warning("%s.%s fell back to %s", member, action, actual.asset_id)
                    out[action] = list(images)
        except Exception:
            log.exception("registry load failed for %s; using legacy manifest", member)
            return None
        return out

    def _load_manifest(self, member: str) -> dict[str, list[Image.Image]]:
        store = resource_store(self.resource_root)
        char_rel = f"work/characters/{member}"
        if not store.exists(f"{char_rel}/manifest.json"):
            char_rel = "work/rongdoong_processed_v2"
        manifest_rel = f"{char_rel}/manifest.json"
        if not store.exists(manifest_rel):
            raise RuntimeError(
                f"Missing sprites in {self.resource_root / char_rel}. "
                "Restore approved work/ assets (see ASSETS_REQUIRED.md) or run a packaged release."
            )
        manifest = store.read_json(manifest_rel, encoding="utf-8")
        with store.session():
            out = {
                action: [store.open_image(f"{char_rel}/{f}").convert("RGBA")
                         for f in manifest["frames"][action]]
                for action in BASE_ACTIONS
            }
        return out
