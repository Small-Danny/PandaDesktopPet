"""action_frames.py — Exact approved registry actions for the desktop pet window.

Two kinds of canvas are played on the desktop:

- 256 canvases: scaled and placed like the base frames (``sprites.scale_to_display``
  at the member's equal scale), so they fit the pet window exactly (offset 0, 0).
- larger canvases (384, 384x416 ...) tagged ``desktop_action``: the whole canvas at the
  same source->display factor, placed by the spec's own anchor so the feet land on the
  base feet point. ``offset`` is the frame's top-left relative to the base frame's; the
  window grows around the pet while such an action plays. Untagged large canvases are
  standby-only and never play here.

``resolve`` falls back to basic actions; an action is used only when the registry
returns exactly that action, so a missing animation never shows up as idle frames.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

from app.sprites import SOURCE_PX, SpriteLibrary, scale_to_display
from app.visual_calibration import action_scale_factor, calibrated_frame

log = logging.getLogger(__name__)

PET_CANVAS = (SOURCE_PX, SOURCE_PX)
DESKTOP_TAG = "desktop_action"
XMAS_POSE_PREFIX = "xmas_special_v6/"     # shared single-image poses, one set per member

# Manually measured horizontal face spans in the original PNGs (exclude ears,
# hats, bedding and props). Match the ~160px standing idle face, not the whole
# pose's height. The normalized bbox transform must be undone for wide tableaux.
XMAS_HEAD_WIDTHS = {
    "bomi_xmas_pulling_gift_sled": 145,
    "bomi_xmas_reindeer_gingerbread_cookie": 141,
    "chorong_xmas_santa_hat_gift_box": 152,
    "chorong_xmas_snowflake_scarf_cocoa": 142,
    "eunji_xmas_carol_candycane_mic": 144,
    "eunji_xmas_fireplace_stocking_sleep": 148,
    "namjoo_xmas_giant_candycane_march": 150,
    "namjoo_xmas_goldstar_decorating_tree": 126,
    "hayoung_xmas_rockinghorse_snowglobe": 118,
}
XMAS_REFERENCE_HEAD_WIDTH = 152

# Effective F1 face spans in source pixels, reviewed against the face contour
# and torso (not a white-pixel band: that can include a fur hat, collar or muffs).
# New Year includes a small whole-body balance allowance for the different hats.
# One uniform factor per action retains authored motion and all hats/props.
FESTIVAL_FACE_WIDTHS = {
    "festival_lunar_ny": dict(zip(("chorong", "bomi", "eunji", "namjoo", "hayoung"), (159, 166, 155, 169, 164))),
    "festival_mid_autumn": dict(zip(("chorong", "bomi", "eunji", "namjoo", "hayoung"), (161, 159, 155, 166, 155))),
    "festival_christmas": dict(zip(("chorong", "bomi", "eunji", "namjoo", "hayoung"), (161, 166, 156, 170, 162))),
    "festival_lantern": dict(zip(("chorong", "bomi", "eunji", "namjoo", "hayoung"), (149, 154, 166, 160, 155))),
    "festival_new_year": dict(zip(("chorong", "bomi", "eunji", "namjoo", "hayoung"), (160, 160, 166, 168, 163))),
}


def festival_scale_factor(member: str, action: str, reference_scale: float) -> float:
    """Cancel idle-height bias for reviewed holiday poses, retaining caller fit/DPI."""
    return action_scale_factor(member, action, reference_scale)


def xmas_head_factor(registry, spec, reference_scale: float = 1.0) -> float:
    name = spec.action.removeprefix(XMAS_POSE_PREFIX)
    head = XMAS_HEAD_WIDTHS.get(name)
    if not head:
        return 1.0
    record = registry._record(spec.frames[0])
    return XMAS_REFERENCE_HEAD_WIDTH / (head * record.get("normalization_scale", 1.0) * reference_scale)


@dataclass(frozen=True)
class ActionFrames:
    action: str
    frames: tuple[Image.Image, ...]      # display-size RGBA, all the same size
    frame_ms: float
    loop: bool
    offset: tuple[int, int] = (0, 0)     # top-left relative to the base frame's top-left


def _playable(spec, action: str) -> bool:
    if spec is None or spec.action != action:
        return False
    if len(spec.frames) < (1 if action.startswith(XMAS_POSE_PREFIX) or "static" in spec.tags else 2):
        return False
    return tuple(spec.canvas) == PET_CANVAS or DESKTOP_TAG in spec.tags


def load_exact_action(library: SpriteLibrary, member: str | None, action: str,
                      scale_member: str | None = None, yield_fn=None) -> ActionFrames | None:
    """Share bounded, signed PIL results between idle workers and Tk consumers."""
    from app.standby import PREPARED_ACTIONS, _source_signature
    from app.visual_calibration import CALIBRATION_REVISION
    registry = getattr(library, "registry", None)
    key = None
    if registry is not None:
        shared = action.startswith(XMAS_POSE_PREFIX)
        spec = registry.resolve(None if shared else member, action)
        ref = registry.resolve(scale_member or member, "idle")
        if _playable(spec, action) and ref is not None:
            signature = _source_signature(registry, spec)
            reference = _source_signature(registry, ref)
            if signature is not None and reference is not None:
                binary_alpha = bool(getattr(library, "binary_alpha", True))
                edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
                key = ("desktop_action", member, action, scale_member, signature, reference,
                       library.display_px, getattr(library, "polish", False), binary_alpha, edge_refine,
                       spec.fps, spec.loop, CALIBRATION_REVISION)
    hit = PREPARED_ACTIONS.get(key) if key is not None else None
    if hit is not None:
        ms, loop, offset = hit[1]
        return ActionFrames(action, tuple(hit[0]["frames"]), ms, loop, offset)
    loaded = _load_exact_action(library, member, action, scale_member, yield_fn)
    if loaded is not None and key is not None:
        PREPARED_ACTIONS.put(key, {"frames": loaded.frames}, (loaded.frame_ms, loaded.loop, loaded.offset))
    return loaded


def _load_exact_action(library: SpriteLibrary, member: str | None, action: str,
                       scale_member: str | None = None, yield_fn=None) -> ActionFrames | None:
    """The approved animation ``member.action`` at pet size, or None if it is not playable here.

    ``member=None`` is a shared asset; it is drawn at ``scale_member``'s size.
    """
    registry, cache = getattr(library, "registry", None), getattr(library, "cache", None)
    if registry is None or cache is None:
        return None
    try:
        if action.startswith(XMAS_POSE_PREFIX):
            member, scale_member = None, member
        spec = registry.resolve(member, action)
        if not _playable(spec, action):
            return None
        if tuple(spec.canvas) != PET_CANVAS and not action.startswith(XMAS_POSE_PREFIX):
            # Share already-warmed expanded frames with standby, including the
            # calibration revision and exact source hashes in its bounded key.
            from app.standby import _measure_member_scale, _prepare_action_pil, walk_feet_point
            prepared = _prepare_action_pil(library, spec, _measure_member_scale(library, member), yield_fn)
            if prepared is None:
                return None
            frames, feet = prepared
            base_feet = walk_feet_point(library.display_px)
            offset = tuple(base_feet[i] - feet[i] for i in (0, 1))
            return ActionFrames(action, tuple(frames), 1000.0 / spec.fps, bool(spec.loop), offset)
        actual, images = cache.load_animation(spec)
        if actual.asset_id != spec.asset_id or len(images) < len(spec.frames):
            return None
        images = tuple(calibrated_frame(im, scale_member or member, action, i,
                       registry._record(actual.frames[i])["sha256"]) for i, im in enumerate(images))
        base = []
        for basic in ("idle",):
            basic_spec = registry.resolve(scale_member or member, basic)
            if basic_spec is not None:
                base += list(cache.load_animation(basic_spec)[1])
        scale = SpriteLibrary._equal_scale(scale_member or member, {"idle": base})
        px = library.display_px
        binary_alpha = bool(getattr(library, "binary_alpha", True))
        edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
        if not action.startswith(XMAS_POSE_PREFIX):
            scale *= action_scale_factor(scale_member or member, action, scale)
        if action.startswith(XMAS_POSE_PREFIX):
            from app.standby import display_action_frame, walk_feet_point
            factor = xmas_head_factor(registry, actual, scale)
            # Keep all pixels on an expanded canvas. Feet still share the base
            # anchor, so seated/sleeping heads grow without pulling the floor up.
            placed = [
                display_action_frame(
                    im, actual.anchor, scale * factor, px,
                    binary_alpha=binary_alpha, edge_refine=edge_refine,
                )
                for im in images
            ]
            frames = [im for im, _ in placed]
            (fx, fy), (wfx, wfy) = placed[0][1], walk_feet_point(px)
            offset = (wfx - fx, wfy - fy)
        elif tuple(actual.canvas) == PET_CANVAS:
            from app.sprites import unclipped_base_scale
            if unclipped_base_scale(images, scale) + 1e-9 >= scale:
                frames = [
                    scale_to_display(im, scale, px, binary_alpha=binary_alpha, edge_refine=edge_refine)
                    for im in images
                ]
                offset = (0, 0)
            else:
                from app.standby import display_action_frame, walk_feet_point
                placed = [
                    display_action_frame(
                        im, actual.anchor, scale, px,
                        binary_alpha=binary_alpha, edge_refine=edge_refine,
                    )
                    for im in images
                ]
                frames = [im for im, _ in placed]
                (fx, fy), (wfx, wfy) = placed[0][1], walk_feet_point(px)
                offset = (wfx - fx, wfy - fy)
        else:
            from app.standby import display_action_frame, walk_feet_point
            placed = [
                display_action_frame(
                    im, actual.anchor, scale, px,
                    binary_alpha=binary_alpha, edge_refine=edge_refine,
                )
                for im in images
            ]
            frames = [im for im, _ in placed]
            (fx, fy), (wfx, wfy) = placed[0][1], walk_feet_point(px)
            offset = (wfx - fx, wfy - fy)
        if getattr(library, "polish", False):
            from app.sprite_polish import polish_frame
            polished = []
            for im in frames:
                polished.append(
                    polish_frame(im, px, binary_alpha=binary_alpha, edge_refine=edge_refine)
                )
                if yield_fn is not None:
                    yield_fn()
            frames = polished
        return ActionFrames(action, tuple(frames), 1000.0 / spec.fps, bool(spec.loop), offset)
    except Exception:
        log.exception("cannot load %s.%s", member, action)
        return None


def xmas_poses(library: SpriteLibrary, member: str) -> tuple[str, ...]:
    """This member's approved single-image Christmas poses."""
    registry = getattr(library, "registry", None)
    if registry is None:
        return ()
    prefix = f"shared.{XMAS_POSE_PREFIX}{member}_"
    names = [key[len("shared."):] for key in registry.data["assets"] if key.startswith(prefix)]
    return tuple(name for name in names if _playable(registry.resolve(None, name), name))


def available_actions(library: SpriteLibrary, member: str, candidates) -> tuple[str, ...]:
    """The candidates that ``load_exact_action`` would play for this member."""
    registry = getattr(library, "registry", None)
    if registry is None:
        return ()
    return tuple(action for action in candidates if _playable(
        registry.resolve(None if action.startswith(XMAS_POSE_PREFIX) else member, action), action))
