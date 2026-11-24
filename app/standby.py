"""standby.py — Fullscreen Panda Standby / Screensaver Overlay with switchable scenes.

Features:
- Four ambient backdrops drawn with plain Tk Canvas primitives (no image assets):
  "starfield" (deep night sky), "campfire" (night camping), "christmas" (cozy
  living room with fireplace, blinking tree and falling snow) and "practice_room"
  (dance practice room with mirrors, wooden floor and speakers).
- Approved image wallpapers (``work/standby_backgrounds.json``, hash-checked)
  are added after the drawn scenes; without that file nothing changes.
- Scene is picked automatically (December -> christmas, otherwise a per-day
  rotation) unless ``scene=`` is given; Left/Right arrow keys cycle scenes
  without leaving standby.
- Glass clock card (HH:MM:SS), date and team badge stay on top of every scene.
- All 5 Apink pandas parade along the bottom, occasionally stopping to cheer, or
  to play one of their registry actions tagged "standby" (exact action only, never
  a fallback; "context:<name>" tags limit an action to a scene / date context).
- Safe auto-dismiss on mouse movement (>25px), click, or any other key.
- Strict anti-lock safety protection.

Performance: every animation reuses its canvas items (coords/itemconfigure),
runs at <= 10 fps, particle counts are capped, and all ``after`` callbacks are
cancelled before the window is destroyed. The standby actions load in small
``after`` steps once the parade is on screen, and their polished frames (and the
fitted wallpapers) are kept for the next standby window.
"""
from __future__ import annotations

from collections import OrderedDict
import ctypes
import dataclasses
import datetime
import hashlib
import io
import zlib
import json
import logging
import math
from pathlib import Path
import random
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Iterable, Mapping, Sequence
from PIL import Image, ImageDraw, ImageOps, ImageTk

from app.dome_stage import (
    DOME_BASEBALL_ACTION,
    DOME_BASEBALL_SCENE,
    DOME_EUNJI_SCENE,
    DOME_FLANK_CHEER_ACTION,
    DOME_SCENES,
    EUNJI_DOME_CONCERT_OUTFITS,
    EUNJI_FLANK_MEMBERS,
    available_dome_bubble_space,
    compute_dome_bubble_rect,
    dome_baseball_standby_slots,
    dome_baseball_step,
    dome_concert_step,
    eunji_dome_standby_slots,
    map_cover_point,
    render_dome_bubble_pil,
    resolved_eunji_dome_outfits,
)
from app.fortune_room import (
    FORTUNE_READER_ACTION,
    FORTUNE_ROOM_SCENE,
    FORTUNE_STUDENT_ACTION,
    compute_fortune_standby_slots,
)
from app.paths import resource_dir
from app.platform.win32 import is_workstation_locked
from app.resource_store import (
    FolderResourceStore,
    normalize_resource_key,
    open_resource_image,
    resource_stat_signature,
    resource_store,
)
from app.engine.contracts import BASE_ACTIONS
from app.action_cache import LazyPhotoList
from app.sprites import DIRECTIONAL_WALK_LEFT, MemberSprites, SpriteLibrary
from app.storage.settings import VALID_STANDBY_CLOCK_POSITIONS
from app.i18n import format_long_date, get_member_short_name, t

log = logging.getLogger(__name__)


def _characters_dir() -> Path:
    """Bundled sprite folder (works in dev and in a PyInstaller EXE)."""
    return resource_dir() / "work" / "characters"


# Kept for backwards compatibility with code importing these names.
ROOT = resource_dir()
CHARACTERS_DIR = _characters_dir()

LOCK_WATCH_MS = 1000
SCENES = ("starfield", "campfire", "christmas", "practice_room")
_MODIFIER_KEYSYMS = frozenset({
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Caps_Lock", "Num_Lock", "Scroll_Lock",
    "Super_L", "Super_R", "Win_L", "Win_R", "Mode_switch", "ISO_Level3_Shift", "Multi_key",
})
_MODIFIER_VK_CODES = frozenset({16, 17, 18, 20, 91, 92, 93, 144, 145})
_IME_H_CHARS = frozenset({"h", "H", "ㄘ", "竹", "ㅗ", "く"})
_VK_PROCESSKEY = 229


def _detach_ime_from_widgets(widgets: Iterable[tk.Misc | None]) -> None:
    """Disable Win32 IME composition on screensaver windows so hotkeys like H never stall in IME."""
    if sys.platform != "win32":
        return
    try:
        imm32 = getattr(ctypes.windll, "imm32", None)
        if imm32 is None:
            return
        assoc = imm32.ImmAssociateContext
        assoc.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        assoc.restype = ctypes.c_void_p
    except Exception:
        return
    seen: set[int] = set()
    for widget in widgets:
        if widget is None:
            continue
        candidates: list[int] = []
        try:
            candidates.append(int(widget.winfo_id()))
        except Exception:
            pass
        try:
            frame = widget.wm_frame() if hasattr(widget, "wm_frame") else ""
            if frame:
                candidates.append(int(frame, 16) if frame.startswith("0x") else int(frame))
        except Exception:
            pass
        for hwnd in candidates:
            if hwnd and hwnd not in seen:
                seen.add(hwnd)
                try:
                    assoc(hwnd, None)
                except Exception:
                    pass


def _resolve_ime_virtual_key(event: tk.Event, fallback_hwnd: int = 0) -> int | None:
    """Resolve the underlying Win32 virtual key when IME masks a key event as VK_PROCESSKEY (229)."""
    if sys.platform != "win32":
        return None
    try:
        imm32 = getattr(ctypes.windll, "imm32", None)
        if imm32 is None:
            return None
        get_vk = imm32.ImmGetVirtualKey
        get_vk.argtypes = [ctypes.c_void_p]
        get_vk.restype = ctypes.c_uint
        widget = getattr(event, "widget", None)
        hwnd = int(widget.winfo_id()) if widget is not None and hasattr(widget, "winfo_id") else int(fallback_hwnd or 0)
        if hwnd:
            vk = int(get_vk(hwnd) or 0)
            if vk and vk != _VK_PROCESSKEY:
                return vk
    except Exception:
        pass
    return None
SCENE_LABELS = {
    "starfield": "星空夜晚",
    "campfire": "營火露營",
    "christmas": "聖誕暖爐",
    "practice_room": "舞蹈練習室",
}

# (key, display name, member colour). No emoji: Tk on Windows renders colour
# emoji as tofu boxes.
MEMBER_ROSTER = [
    ("chorong", "初瓏", "#ff80ab"),   # pink
    ("bomi", "普美", "#ff8a65"),      # coral-orange
    ("eunji", "恩地", "#4fc3f7"),     # sky-blue
    ("namjoo", "南珠", "#b39ddb"),    # lavender-purple
    ("hayoung", "夏榮", "#fff176"),   # lemon-yellow
]

STANDBY_CLOCK_THEMES = {
    "chorong": {
        "family": "Georgia",
        "clock_color": "#FFF5F7",
        "date_color": "#F48FB1",
        "badge_color": "#FFB6C1",
        "card_bg": "#2A1520",
        "card_border": "#F8BBD0",
        "bezel": "#FFB6C1",
        "flow1": "#FF77A9",
        "flow2": "#F48FB1",
        "shadow_bg": "#140810",
        "shadow_border": "#3A1B2C",
    },
    "bomi": {
        "family": "Trebuchet MS",
        "clock_color": "#FFF8E1",
        "date_color": "#FFB74D",
        "badge_color": "#FFA000",
        "card_bg": "#241208",
        "card_border": "#FFA000",
        "bezel": "#FF6F00",
        "flow1": "#FF8F00",
        "flow2": "#FFB74D",
        "shadow_bg": "#130903",
        "shadow_border": "#3D1C0B",
    },
    "eunji": {
        "family": "Segoe UI",
        "clock_color": "#E0F7FA",
        "date_color": "#81D4FA",
        "badge_color": "#40C4FF",
        "card_bg": "#0A1C2C",
        "card_border": "#40C4FF",
        "bezel": "#00B0FF",
        "flow1": "#00B0FF",
        "flow2": "#81D4FA",
        "shadow_bg": "#050E17",
        "shadow_border": "#0F324E",
    },
    "namjoo": {
        "family": "Palatino Linotype",
        "clock_color": "#F3E5F5",
        "date_color": "#E1BEE7",
        "badge_color": "#CE93D8",
        "card_bg": "#190B28",
        "card_border": "#CE93D8",
        "bezel": "#AA00FF",
        "flow1": "#BA68C8",
        "flow2": "#E1BEE7",
        "shadow_bg": "#0D0515",
        "shadow_border": "#2E1548",
    },
    "hayoung": {
        "family": "Consolas",
        "clock_color": "#FFFDE7",
        "date_color": "#A7FFEB",
        "badge_color": "#FFEE58",
        "card_bg": "#1F1C05",
        "card_border": "#FFEE58",
        "bezel": "#FFD600",
        "flow1": "#FFD600",
        "flow2": "#00E676",
        "shadow_bg": "#100E02",
        "shadow_border": "#363108",
    },
}


def get_standby_clock_theme(scene: str, char_key: str = "chorong") -> dict:
    scene_to_char = {
        "christmas": "chorong",
        "campfire": "bomi",
        "practice_room": "eunji",
        "starfield": "namjoo",
        FORTUNE_ROOM_SCENE: "eunji",
    }
    member = scene_to_char.get(scene, char_key if char_key in STANDBY_CLOCK_THEMES else "chorong")
    return STANDBY_CLOCK_THEMES.get(member, STANDBY_CLOCK_THEMES["chorong"])

SCENE_TICK_MS = 100      # 10 fps for flicker / snow / embers
WALLPAPER_SRC = (2752, 1536)
# A costume stage: at every stop all five are in costume, the dancers dance and the rest hold the pose.
COSTUME_SCENES = {"bg_standby_musical_theater": "musical_pose"}
# Christmas (the cabin, or any scene in December) works the same way with the Christmas outfit.
CHRISTMAS_COSTUME = "festival_christmas"
# ...or, all five together, unwrapping presents or with scarves and hot cocoa (drawn 2026-11-10).
CHRISTMAS_SETS = (CHRISTMAS_COSTUME, "christmas_gift", "winter_cocoa")
# key -> (kind, picture region x0, y0, x1, y1 as fractions, count, colours)
WALLPAPER_FX = {
    "bg_standby_autumn_cafe": ("fall", (0.0, 0.0, 1.0, 0.62), 16, ("#e8833a", "#f2b84b", "#c8562e")),
    "bg_standby_spring_picnic": ("fall", (0.0, 0.0, 1.0, 0.66), 22, ("#ffd1e0", "#ffb7cf", "#fff0f5")),
    "concert_stage_audience": ("twinkle", (0.12, 0.42, 0.88, 0.62), 34, ("#ff8fc8", "#ffc4e4", "#ff5fae")),
    "bg_standby_christmas": ("snow", (0.30, 0.14, 0.67, 0.39), 26, ("#ffffff", "#e8f1ff")),
    "bg_standby_musical_theater": ("twinkle", (0.18, 0.04, 0.82, 0.50), 30, ("#ffe6a8", "#fff6dc", "#ffc8e6")),
    "bg_standby_eunji_fortune_room": ("twinkle", (0.14, 0.08, 0.86, 0.42), 20, ("#e9d5ff", "#fde68a", "#c4b5fd")),
}
STAGE_SCENES: frozenset[str] = DOME_SCENES | {FORTUNE_ROOM_SCENE}
PANDA_TICK_MS = 130
MAX_SNOW = 60
MAX_EMBERS = 14
SPRITE_PX = 192          # parade sprite size at 100% scaling (96 dpi)


BACKGROUNDS_MANIFEST = "work/standby_backgrounds.json"
from app.daily_actions import SCENE_ACTIONS, SIGNATURE_POOL, festival_on  # noqa: E402

STANDBY_ACTION_TAG = "standby"
CONTEXT_TAG_PREFIX = "context:"
SCENE_ACTION_SHARE = 0.6
MAX_PAUSE_PERFORMERS = 2
PAUSE_TICKS = 18                 # minimum length of a parade stop (x PANDA_TICK_MS)
# How an action fills a parade stop that outlasts one pass (frames reviewed 2026-11-19). A stop
# is open-ended, so every other multi-frame action cycles; single-frame stills simply hold.
PAUSE_HOLD_END = frozenset({      # ends on a finishing pose: stay on it
    "musical_bow", "special_soccer_kick", "special_sing_highnote", "scene_beach",
})
PAUSE_ONCE_THEN_CHEER = frozenset({   # ends mid-air / mid-reveal: cheer for the rest of the stop
    "christmas_gift",
})
ACTION_LOAD_DELAY_MS = 60        # the parade is on screen before the standby actions load
ACTION_LOAD_STEP_MS = 15         # one action per step keeps the parade moving meanwhile
PREPARED_CACHE_BYTES = 64 * 1024 * 1024


class _PreparedImageCache:
    """PIL images prepared for a standby window, kept for the next one.

    Scaling and polishing the sprites is most of the cost of opening standby. The result
    depends only on the source frames (sha256 and calibration, see _source_signature), the
    display size and the polish switch, which are all part of every key. Images are stored
    as deflated RGBA bytes (no PNG filtering or codec) under a byte budget, least
    recently used first out. PhotoImages are never shared: each window builds its own for its master.
    """

    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = limit_bytes
        self._lock = threading.RLock()
        self._items: OrderedDict[tuple, tuple[dict[str, list[tuple]], object, int]] = OrderedDict()
        self._bytes = 0
        self.hits = self.misses = 0

    def get(
        self,
        key: tuple,
        actions: Iterable[str] | None = None,
    ) -> tuple[dict[str, list[Image.Image]], object] | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            encoded, meta, _size = item
        wanted = set(actions) if actions is not None else None
        images = {}
        for name, blobs in encoded.items():
            if wanted is not None and name not in wanted:
                continue
            images[name] = []
            for size, blob in blobs:
                images[name].append(Image.frombytes("RGBA", size, zlib.decompress(blob)))
        return images, meta

    def put(self, key: tuple, images: Mapping[str, Sequence[Image.Image]], meta: object = None) -> None:
        encoded: dict[str, list[tuple]] = {}
        for name, ims in images.items():
            encoded[name] = []
            for im in ims:
                rgba = im.convert("RGBA")
                # In-memory pixels need no PNG filters, chunks or decoder.
                # Deflate retains compact immutable storage and the same LRU
                # budget while making desktop seeding cheap on the Tk thread.
                encoded[name].append((rgba.size, zlib.compress(rgba.tobytes(), level=1)))
        size = sum(len(blob) + 16 for blobs in encoded.values() for _dimensions, blob in blobs)
        with self._lock:
            if size > self.limit_bytes:
                return
            old = self._items.pop(key, None)
            if old is not None:
                self._bytes -= old[2]
            while self._items and self._bytes + size > self.limit_bytes:
                self._bytes -= self._items.popitem(last=False)[1][2]
            self._items[key] = (encoded, meta, size)
            self._bytes += size

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0
            self.hits = self.misses = 0

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._bytes


PREPARED_IMAGES = _PreparedImageCache(PREPARED_CACHE_BYTES)
# Full-screen Tk photos kept per overlay/cover: the shown scene plus the one before it, so
# flipping back is instant. Each is 4 bytes/pixel (8 MB at 1920x1080, 25 MB at 3200x2000);
# keeping every visited scene was ~150 MB while standby stayed open (2026-11-22).
WALLPAPER_PHOTOS_KEPT = 2
# 2026-11-22: standby members used the library defaults (binary alpha, no edge refine),
# so every frame on the dark dome / wallpaper scenes showed the jagged white-gray matte
# ring the desktop ULW pet never shows. The standby canvas is opaque and Tk photo images
# blend 8-bit alpha onto it (the dome bubble already relies on that), so standby uses the
# same soft-alpha + edge-refine pipeline as the desktop pet.
STANDBY_BINARY_ALPHA = False
STANDBY_EDGE_REFINE = True


def _trim_photo_cache(cache: dict) -> None:
    """Drop the oldest entries (insertion order = recency) beyond WALLPAPER_PHOTOS_KEPT."""
    while len(cache) > WALLPAPER_PHOTOS_KEPT:
        cache.pop(next(iter(cache)))
# Separate key namespaces share one bounded memory budget across member/action art.
PREPARED_ACTIONS = PREPARED_IMAGES


def _source_signature(registry, spec) -> tuple | None:
    """What decides the decoded pixels of ``spec``; None when a frame is unknown.

    Per frame the registry sha256 plus the fields ``AssetImageCache._decode`` normalises
    with (mode, scale, bboxes, sizes, anchor), so re-calibrating unchanged PNG bytes is a
    new key; then the spec's own asset id, canvas and anchor.
    """
    try:
        frames = []
        for path in spec.frames:
            record = registry._record(path)
            frames.append((record["sha256"], record.get("normalization_mode", "bbox"),
                           record.get("normalization_scale"), tuple(record.get("alpha_bbox") or ()),
                           tuple(record.get("source_size") or ()), tuple(record.get("normalized_size") or ()),
                           tuple(record.get("anchor") or ())))
        own = (getattr(spec, "asset_id", None), tuple(getattr(spec, "canvas", ()) or ()),
               tuple(getattr(spec, "anchor", ()) or ()))
        signature = (tuple(frames), own)
        hash(signature)
        return signature
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


@dataclasses.dataclass(frozen=True)
class WallpaperSpec:
    """One approved image backdrop. ``path`` is absolute; labels are per language."""

    key: str
    path: Path
    labels: Mapping[str, str] = dataclasses.field(default_factory=dict)

    def label(self, lang: str) -> str:
        return self.labels.get(lang) or self.labels.get("zh_TW") or self.key


_WALLPAPER_MANIFEST_LOCK = threading.RLock()
_WALLPAPER_MANIFEST_CACHE: OrderedDict[tuple, tuple[WallpaperSpec, ...]] = OrderedDict()
_WALLPAPER_MANIFEST_MAX = 8


def _entry_stat_signature(store, root: Path, rel: object) -> tuple | None:
    if not isinstance(rel, str):
        return None
    try:
        path = (root / rel).resolve()
        path.relative_to(root / "work")
        norm = normalize_resource_key(path, root=root)
        return (norm, store.stat_signature(norm))
    except (KeyError, OSError, ValueError, FileNotFoundError):
        return None


def load_wallpapers(resource_root: Path | None = None,
                    manifest: str = BACKGROUNDS_MANIFEST) -> tuple[WallpaperSpec, ...]:
    """Approved wallpapers from the background manifest; a bad entry is skipped, a missing file = none.

    Entry (Codex contract): {"key", "path" (relative to the resources, must be under work/),
    "sha256", "width", "height", "status": "approved", "labels"}. "ground_y" is not used yet.
    """
    root = Path(resource_root or resource_dir()).resolve()
    store = resource_store(root)
    try:
        manifest_raw = store.read_bytes(manifest)
        data = json.loads(manifest_raw.decode("utf-8-sig"))
    except FileNotFoundError:
        return ()
    except (OSError, ValueError):
        log.exception("standby background manifest unreadable")
        return ()
    entries = data.get("backgrounds") if isinstance(data, dict) and data.get("schema_version") == 1 else None
    if not isinstance(entries, list):
        log.warning("standby background manifest: unsupported schema")
        return ()
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    asset_sigs = tuple(
        _entry_stat_signature(store, root, item.get("path")) if isinstance(item, dict) else None
        for item in entries
    )
    cache_key = (str(root), manifest, manifest_sha, asset_sigs)
    with _WALLPAPER_MANIFEST_LOCK:
        cached = _WALLPAPER_MANIFEST_CACHE.get(cache_key)
        if cached is not None:
            _WALLPAPER_MANIFEST_CACHE.move_to_end(cache_key)
            return cached

    out: list[WallpaperSpec] = []
    seen = set(SCENES)
    with store.session():
        for item in entries:
            try:
                key, rel, sha = item["key"], item["path"], item["sha256"]
                if not (isinstance(key, str) and key and key not in seen and isinstance(rel, str)
                        and isinstance(sha, str) and item.get("status") == "approved"):
                    continue
                path = (root / rel).resolve()
                path.relative_to(root / "work")
                norm = normalize_resource_key(path, root=root)
                payload = store.read_bytes(norm)
                if hashlib.sha256(payload).hexdigest() != sha.lower():
                    log.warning("standby background %s: hash differs from approved bytes", key)
                    continue
                with Image.open(io.BytesIO(payload)) as im:
                    if [im.width, im.height] != [item.get("width"), item.get("height")]:
                        log.warning("standby background %s: size differs from the manifest", key)
                        continue
                labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}
                labels = {k: v for k, v in labels.items() if isinstance(k, str) and isinstance(v, str)}
            except (KeyError, TypeError, ValueError, OSError):
                continue
            seen.add(key)
            out.append(WallpaperSpec(key, path, labels))
    result = tuple(out)
    with _WALLPAPER_MANIFEST_LOCK:
        _WALLPAPER_MANIFEST_CACHE[cache_key] = result
        _WALLPAPER_MANIFEST_CACHE.move_to_end(cache_key)
        while len(_WALLPAPER_MANIFEST_CACHE) > _WALLPAPER_MANIFEST_MAX:
            _WALLPAPER_MANIFEST_CACHE.popitem(last=False)
    return result


def cover_image(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale to fill width x height (aspect kept), cropping the overflow around the centre."""
    return ImageOps.fit(image.convert("RGB"), (max(1, width), max(1, height)), Image.Resampling.LANCZOS)


_FITTED_WALLPAPER_LOCK = threading.RLock()
_FITTED_WALLPAPERS: OrderedDict[tuple, Image.Image] = OrderedDict()
FITTED_WALLPAPER_KEEP = 2        # legacy alias retained for compatibility
FITTED_WALLPAPER_MAX_BYTES = 48 * 1024 * 1024


def _image_byte_size(im: Image.Image) -> int:
    # Pillow keeps RGB as 4 bytes/pixel (RGBX); counting 3 under-reported the cache by 33%.
    bands = len(im.getbands())
    return max(1, im.width * im.height * (4 if bands >= 3 else max(1, bands)))


def _fitted_wallpaper(path: Path, width: int, height: int, *, base_root: Path | None = None) -> Image.Image:
    """``cover_image`` of the file, thread-safe bounded-byte LRU keyed by source sig and dimensions."""
    p = Path(path)
    root = Path(base_root).resolve() if base_root is not None else resource_dir()
    sig = resource_stat_signature(p, root=root)
    w, h = max(1, int(width)), max(1, int(height))
    key = (str(p), sig, w, h, "LANCZOS")
    with _FITTED_WALLPAPER_LOCK:
        image = _FITTED_WALLPAPERS.get(key)
        if image is not None:
            _FITTED_WALLPAPERS.move_to_end(key)
            return image
    with open_resource_image(p, root=root) as im:
        image = cover_image(im, w, h)
    with _FITTED_WALLPAPER_LOCK:
        existing = _FITTED_WALLPAPERS.get(key)
        if existing is not None:
            _FITTED_WALLPAPERS.move_to_end(key)
            return existing
        _FITTED_WALLPAPERS[key] = image
        _FITTED_WALLPAPERS.move_to_end(key)
        total_bytes = sum(_image_byte_size(val) for val in _FITTED_WALLPAPERS.values())
        while len(_FITTED_WALLPAPERS) > 1 and total_bytes > FITTED_WALLPAPER_MAX_BYTES:
            _, evicted = _FITTED_WALLPAPERS.popitem(last=False)
            total_bytes -= _image_byte_size(evicted)
    return image


def trim_fitted_wallpapers(keep: int = 1) -> int:
    """Drop all but the ``keep`` most recent fitted wallpapers; returns bytes released.

    2026-11-22: after standby closed, the cache kept every scene visited (9 full-screen
    RGB images, ~48 MB at 1920x1080) for the rest of the session. Standby re-fits a
    wallpaper in ~0.1 s and the warmup prepares the next one, so idle keeps only the last.
    """
    freed = 0
    with _FITTED_WALLPAPER_LOCK:
        while len(_FITTED_WALLPAPERS) > max(0, int(keep)):
            _, evicted = _FITTED_WALLPAPERS.popitem(last=False)
            freed += _image_byte_size(evicted)
    return freed


def clear_standby_caches() -> None:
    """Clear in-memory standby wallpaper and prepared sprite caches (used by tests)."""
    PREPARED_IMAGES.clear()
    with _FITTED_WALLPAPER_LOCK:
        _FITTED_WALLPAPERS.clear()
    with _WALLPAPER_MANIFEST_LOCK:
        _WALLPAPER_MANIFEST_CACHE.clear()


def standby_contexts(scene: str, today: datetime.date) -> frozenset[str]:
    """Context names that "context:<name>" action tags may require."""
    ctx = {scene}
    if today.month == 12 or scene == "bg_standby_christmas":     # the cabin is Christmas all year
        ctx.add("christmas")
    if (today.month, today.day) == (4, 19):
        ctx.add("anniversary_0419")
    festival = festival_on(today)
    if festival is not None and festival.action != CHRISTMAS_COSTUME:
        ctx.add(festival.action)
    return frozenset(ctx)


def action_allowed(tags: Iterable[str], contexts: Iterable[str]) -> bool:
    """No context tag = always; otherwise one of its contexts must be active."""
    needed = {tag[len(CONTEXT_TAG_PREFIX):] for tag in tags if tag.startswith(CONTEXT_TAG_PREFIX)}
    return not needed or bool(needed & set(contexts))


def secret_visitor_allowed(policy: Mapping | None, scene: str, today: datetime.date) -> bool:
    """Easter-egg visitor: only in the policy's contexts, never as a random cameo."""
    if not isinstance(policy, Mapping) or policy.get("mode") != "easter_egg_only":
        return False
    allowed = policy.get("allowed_contexts")
    if not isinstance(allowed, (list, tuple)):
        return False
    return bool(set(allowed) & standby_contexts(scene, today))


def walk_feet_point(display_px: int) -> tuple[int, int]:
    """Feet anchor of a parade (walk) frame in display px, as laid out by sprites.scale_to_display."""
    from app.sprites import CANVAS_SRC, SOURCE_ANCHOR, SOURCE_PX
    k = display_px / SOURCE_PX
    return round(CANVAS_SRC[0] * k / 2), round(display_px - (SOURCE_PX - SOURCE_ANCHOR[1]) * k)


def display_action_frame(image: Image.Image, anchor: tuple[int, int], member_scale: float,
                         display_px: int, *, binary_alpha: bool = True,
                         edge_refine: bool = False) -> tuple[Image.Image, tuple[int, int]]:
    """Whole source canvas at the walk frames' source->display factor; returns (frame, feet point).

    A 384 canvas is not squeezed into the walk height: hats and props may stand taller.
    """
    from app.sprite_polish import alpha_bleed, prepare_ulw_source
    from app.sprites import ALPHA_THRESHOLD, SOURCE_PX
    s = member_scale * display_px / SOURCE_PX
    im = prepare_ulw_source(image, soft_binarize=True) if (not binary_alpha and edge_refine) else alpha_bleed(image)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.Resampling.LANCZOS)
    if binary_alpha:
        im.putalpha(im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0))
    return im, (round(anchor[0] * s), round(anchor[1] * s))


def _union_alpha_bbox(info: dict | None) -> tuple[int, int, int, int] | None:
    """Union of an action's per-frame alpha boxes, cached until a re-fit replaces them."""
    bboxes = (info or {}).get("alpha_bboxes")
    if not bboxes:
        return None
    cached = info.get("_union_bbox")
    if cached is not None and cached[0] is bboxes:
        return cached[1]
    boxes = [b for b in bboxes if b is not None]
    union = (min(b[0] for b in boxes), min(b[1] for b in boxes),
             max(b[2] for b in boxes), max(b[3] for b in boxes)) if boxes else None
    info["_union_bbox"] = (bboxes, union)
    return union


def scene_fits(action: str, tags: Iterable[str], member: str, scene: str) -> bool:
    """Signature moves go everywhere; a scene's own actions only in that scene; other
    standby actions everywhere unless some scene claims them (hot tea is not for the beach)."""
    if action in SIGNATURE_POOL.get(member, ()) or action in SCENE_ACTIONS.get(scene, {}).get(member, ()):
        return True
    claimed = any(action in pool.get(member, ()) for pool in SCENE_ACTIONS.values())
    return STANDBY_ACTION_TAG in tags and not claimed


def pick_pause_actions(options: Mapping[str, Sequence[str]], rng: random.Random) -> dict[str, str | None]:
    """Per member: one of its allowed standby actions, or None (= cheer) about half the time."""
    plan: dict[str, str | None] = {}
    for member, actions in options.items():
        plan[member] = rng.choice(list(actions)) if actions and rng.random() < 0.65 else None
    return plan


def _load_sprite(path: Path, size: int = SPRITE_PX) -> Image.Image:
    with open_resource_image(path) as raw:
        im = raw.convert("RGBA")
    if im.size != (size, size):
        im = im.resize((size, size), Image.Resampling.LANCZOS)
    return im


def pick_default_scene(today: datetime.date | None = None, rng: random.Random | None = None) -> str:
    """December -> christmas; otherwise a deterministic per-day pick among SCENES."""
    today = today or datetime.date.today()
    if today.month == 12:
        return "christmas"
    rng = rng or random.Random(today.toordinal())
    return rng.choice(SCENES)


def _strip_emoji(text: str) -> str:
    """Drop astral-plane characters / variation selectors Tk cannot draw on Windows."""
    return "".join(ch for ch in str(text) if ord(ch) <= 0xFFFF and ch != "️").strip()


def _hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(c1: str, c2: str, t: float) -> str:
    """Linear blend of two #rrggbb colours (t=0 -> c1, t=1 -> c2)."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#%02x%02x%02x" % (
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def _flame_pts(x: float, base: float, w: float, h: float, rng: random.Random, j: float) -> list[float]:
    """Smooth-polygon control points for a flickering flame tongue."""
    h *= rng.uniform(0.85, 1.08)
    jt = lambda a: rng.uniform(-a, a)  # noqa: E731
    return [
        x - w / 2, base,
        x - w * 0.48 + jt(j), base - h * 0.32,
        x - w * 0.2 + jt(j), base - h * 0.68,
        x + jt(j * 1.6), base - h,
        x + w * 0.22 + jt(j), base - h * 0.6,
        x + w * 0.48 + jt(j), base - h * 0.28,
        x + w / 2, base,
    ]


def _round_rect_pts(x1: float, y1: float, x2: float, y2: float, r: float = 6) -> tuple[float, ...]:
    """Generates 20 control points (40 floats) for a smooth rounded rectangle."""
    return (
        x1 + r, y1,
        x1 + r, y1,
        x2 - r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1 + r,
        x1, y1,
    )


def _draw_round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r: float = 18,
    **kwargs,
) -> int:
    """Draws a smooth rounded rectangle on a Tkinter Canvas using bezier curves."""
    points = _round_rect_pts(x1, y1, x2, y2, r)
    return canvas.create_polygon(points, **kwargs, smooth=True)


def _member_prepared_key(library: SpriteLibrary, member: str) -> tuple | None:
    registry = getattr(library, "registry", None)
    if registry is None:
        return None
    try:
        from app.visual_calibration import CALIBRATION_REVISION
        specs = [registry.resolve(member, action) for action in BASE_ACTIONS]
        signatures = [_source_signature(registry, spec) if spec is not None else None for spec in specs]
        directional = None
        if member in DIRECTIONAL_WALK_LEFT:
            left = registry.resolve(member, "walk_left")
            if left is not None and left.action == "walk_left":
                directional = (_source_signature(registry, left), left.fps, left.anchor)
        if all(signatures):
            binary_alpha = bool(getattr(library, "binary_alpha", True))
            edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
            return ("member", member, library.display_px, library.equalize, library.polish,
                    binary_alpha, edge_refine, tuple(signatures), directional, CALIBRATION_REVISION)
    except Exception:
        log.exception("standby: cannot sign %s's base sprites", member)
    return None


def _measure_member_scale(library: SpriteLibrary, member: str) -> float:
    registry, cache = library.registry, library.cache
    base = []
    for basic in ("idle",):
        spec = registry.resolve(member, basic)
        if spec is not None:
            base += list(cache.load_animation(spec)[1])
    return SpriteLibrary._equal_scale(member, {"idle": base})


def _prepare_member_pil(
    library: SpriteLibrary,
    member: str,
    yield_fn: Callable[[], None] | None = None,
) -> tuple[dict[str, list[Image.Image]], str] | None:
    """Thread-safe pure-PIL load of one member's 4 base actions via ``PREPARED_IMAGES``."""
    key = _member_prepared_key(library, member)
    hit = PREPARED_IMAGES.get(key) if key is not None else None
    if hit is not None:
        metadata = hit[1] if isinstance(hit[1], dict) else {}
        if metadata.get("directional") is not None:
            library._directional_placement[member] = metadata["directional"]
        return hit[0], "registry"
    prepared, source = library.load_member_pil(member, yield_fn=yield_fn)
    if key is not None and source == "registry":
        PREPARED_IMAGES.put(key, prepared, {"directional": library._directional_placement.get(member)})
    return prepared, source


def seed_prepared_member_pil(library: SpriteLibrary, member: str,
                             prepared: Mapping[str, Sequence[Image.Image]] | None) -> bool:
    """Seed ``PREPARED_IMAGES`` with already-decoded desktop PIL frames when cache key matches."""
    if not prepared:
        return False
    key = _member_prepared_key(library, member)
    if key is None:
        return False
    if PREPARED_IMAGES.get(key) is not None:
        return True
    PREPARED_IMAGES.put(key, prepared, {"directional": library._directional_placement.get(member)})
    return True


def _wanted_actions_for(library: SpriteLibrary, member: str, scene: str | None,
                        today: datetime.date) -> list[str]:
    registry = getattr(library, "registry", None)
    if registry is None:
        return []
    extras = list(SCENE_ACTIONS.get(scene, {}).get(member, ()))
    if scene in STAGE_SCENES:
        return extras  # stage playback never needs all the unrelated parade pauses
    names = list(extras)
    for extra in registry.actions(member, tag=STANDBY_ACTION_TAG):
        if extra not in names:
            names.append(extra)
    fest = festival_on(today)
    if fest is not None and fest.action not in names:
        names.append(fest.action)
    return names


def _prepare_action_pil(
    library: SpriteLibrary,
    spec,
    scale: float,
    yield_fn: Callable[[], None] | None = None,
) -> tuple[list[Image.Image], tuple[int, int]] | None:
    """Thread-safe pure-PIL preparation of one standby action (cached across windows)."""
    steps = _iter_prepare_action_pil(library, spec, scale, yield_fn)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def _iter_prepare_action_pil(library, spec, scale, yield_fn=None):
    """Prepare at most one frame per step; Tk callers advance this via after()."""
    from app.visual_calibration import action_scale_factor, calibrated_frame, CALIBRATION_REVISION, FACE_WIDTHS
    if f"{getattr(spec, 'member', None)}.{getattr(spec, 'action', None)}" in FACE_WIDTHS:
        scale *= action_scale_factor(spec.member, spec.action, _measure_member_scale(library, spec.member))
    polish = bool(getattr(library, "polish", False))
    binary_alpha = bool(getattr(library, "binary_alpha", True))
    edge_refine = bool(getattr(library, "edge_refine", False)) and not binary_alpha
    signature = _source_signature(library.registry, spec)
    key = (None if signature is None else
           ("action", spec.asset_id, signature, tuple(spec.anchor), library.display_px, round(scale, 9), polish,
            binary_alpha, edge_refine, CALIBRATION_REVISION))
    hit = PREPARED_ACTIONS.get(key) if key is not None else None
    if hit is not None:
        return hit[0]["frames"], hit[1]
    actual, images = library.cache.load_animation(spec)
    if actual.asset_id != spec.asset_id or len(images) < (1 if "static" in spec.tags else 2):
        return None
    images = [calibrated_frame(im, actual.member, actual.action, i,
              library.registry._record(actual.frames[i])["sha256"]) for i, im in enumerate(images)]
    frames = []
    feet = None
    from app.sprite_polish import polish_frame
    for image in images:
        im, frame_feet = display_action_frame(image, actual.anchor, scale, library.display_px,
                                              binary_alpha=binary_alpha, edge_refine=edge_refine)
        if feet is None:
            feet = frame_feet
        frames.append(
            polish_frame(im, library.display_px, binary_alpha=binary_alpha, edge_refine=edge_refine)
            if polish else im
        )
        if yield_fn is not None:
            yield_fn()
        yield
    if key is not None:
        PREPARED_ACTIONS.put(key, {"frames": frames}, feet)
    return frames, feet


def _lower_current_thread_priority() -> None:
    """Best-effort BELOW_NORMAL priority for Windows background warmup worker."""
    try:
        if sys.platform == "win32":
            k32 = ctypes.windll.kernel32
            k32.SetThreadPriority(k32.GetCurrentThread(), -1)  # THREAD_PRIORITY_BELOW_NORMAL
    except Exception:
        pass


class StandbyWarmupManager:
    """Low-priority single-worker PIL background warmup (never touches Tk off main thread).

    The worker must be gone before its owner destroys Tk: a worker that outlives the
    root may run Python's cyclic GC and finalize Tk objects (or the interpreter
    itself) off the Tk thread -> ``Tcl_AsyncDelete: async handler deleted by the
    wrong thread`` (0x80000003). ``shutdown`` therefore joins for real.
    """

    THREAD_NAME = "StandbyWarmup"
    SHUTDOWN_TIMEOUT_S = 10.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._done_event = threading.Event()
        self._done_event.set()
        self._generation = 0
        self._shutdown = False
        self._plan: dict | None = None
        self._worker: threading.Thread | None = None
        self.completed_items = 0

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def is_running(self) -> bool:
        return not self._done_event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._done_event.wait(timeout=timeout)

    def cancel(self) -> None:
        with self._lock:
            self._generation += 1
            self._plan = None
            self._done_event.set()
            self._wakeup.set()

    def request_shutdown(self) -> None:
        """Non-blocking: every step of the running plan sees ``_stale`` and returns."""
        with self._lock:
            self._shutdown = True
            self._generation += 1
            self._plan = None
            self._done_event.set()
            self._wakeup.set()

    def join(self, timeout: float | None = None) -> bool:
        """Wait for the worker thread to exit; True when no worker is left alive."""
        with self._lock:
            worker = self._worker
        if worker is None or worker is threading.current_thread():
            return True
        worker.join(timeout=self.SHUTDOWN_TIMEOUT_S if timeout is None else timeout)
        if worker.is_alive():
            log.warning("%s worker still alive after shutdown join", self.THREAD_NAME)
            return False
        return True

    def is_worker_alive(self) -> bool:
        with self._lock:
            worker = self._worker
        return worker is not None and worker.is_alive()

    def shutdown(self, timeout: float | None = None) -> bool:
        self.request_shutdown()
        return self.join(timeout)

    def schedule(
        self,
        resource_root: Path,
        sprite_px: int,
        screen_w: int,
        screen_h: int,
        active_scene: str | None = None,
        today: datetime.date | None = None,
        busy_check: Callable[[], bool] | None = None,
        active_member: str | None = None,
        *,
        binary_alpha: bool = True,
        edge_refine: bool = False,
        registry=None,
    ) -> int:
        with self._lock:
            if self._shutdown:
                return self._generation
            self._generation += 1
            gen = self._generation
            self._plan = {
                "gen": gen,
                "resource_root": Path(resource_root),
                "sprite_px": max(48, int(sprite_px)),
                "screen_w": max(1, int(screen_w)),
                "screen_h": max(1, int(screen_h)),
                "active_scene": active_scene,
                "today": today or datetime.date.today(),
                "busy_check": busy_check,
                "active_member": active_member,
                "binary_alpha": bool(binary_alpha),
                "edge_refine": bool(edge_refine),
                "registry": registry,   # the pet's parsed AssetRegistry (read-only) or None
            }
            self._done_event.clear()
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run_loop, name=self.THREAD_NAME, daemon=True)
                self._worker.start()
            self._wakeup.set()
            return gen

    def _stale(self, gen: int) -> bool:
        with self._lock:
            return self._shutdown or gen != self._generation

    def _yield_step(self, gen: int, busy_check: Callable[[], bool] | None, pause_s: float = 0.015) -> bool:
        if self._stale(gen):
            return True
        if busy_check is not None:
            while not self._stale(gen):
                try:
                    if not busy_check():
                        break
                except Exception:
                    break
                time.sleep(0.04)
        if self._stale(gen):
            return True
        time.sleep(pause_s)
        return self._stale(gen)

    def _run_loop(self) -> None:
        _lower_current_thread_priority()
        while True:
            self._wakeup.wait()
            with self._lock:
                self._wakeup.clear()
                if self._shutdown:
                    self._done_event.set()
                    return
                plan = self._plan
                self._plan = None
            if plan is not None:
                try:
                    self._execute_plan(plan)
                except Exception:
                    log.debug("standby warmup interrupted", exc_info=True)
                with self._lock:
                    if self._plan is None and (self._shutdown or self._generation == plan["gen"]):
                        self._done_event.set()

    def _execute_plan(self, plan: dict) -> None:
        gen = plan["gen"]
        root = plan["resource_root"]
        sprite_px = plan["sprite_px"]
        sw, sh = plan["screen_w"], plan["screen_h"]
        active_scene = plan["active_scene"]
        today = plan["today"]
        busy_check = plan["busy_check"]

        class _WarmupAbort(Exception):
            pass

        def _frame_yield() -> None:
            if self._yield_step(gen, busy_check, pause_s=0.002):
                raise _WarmupAbort()

        # 1. Active / expected standby wallpaper only (other wallpapers stay on-demand).
        if self._stale(gen):
            return
        wallpapers = load_wallpapers(root)
        if self._stale(gen):
            return
        target_wp = None
        if active_scene:
            target_wp = next((w for w in wallpapers if w.key == active_scene), None)
        if target_wp is None and wallpapers:
            if today.month == 12:
                target_wp = next((w for w in wallpapers if "christmas" in w.key), None)
            if target_wp is None:
                target_wp = wallpapers[0]
        if target_wp is not None and not self._yield_step(gen, busy_check):
            try:
                _fitted_wallpaper(target_wp.path, sw, sh, base_root=root)
                self.completed_items += 1
            except Exception:
                pass

        if self._stale(gen):
            return

        # 2. Five members' base parade sprites (PIL only into PREPARED_IMAGES).
        library = SpriteLibrary(root, display_px=sprite_px, binary_alpha=STANDBY_BINARY_ALPHA,
                                edge_refine=STANDBY_EDGE_REFINE, registry=plan.get("registry"))
        if self._stale(gen):
            return
        scales: dict[str, float] = {}
        first = plan.get("active_member") or ("eunji" if active_scene in (DOME_EUNJI_SCENE, FORTUNE_ROOM_SCENE) else None)
        roster = sorted(MEMBER_ROSTER, key=lambda item: item[0] != first)
        for key, _name, _col in roster:
            if self._yield_step(gen, busy_check):
                return
            try:
                res = _prepare_member_pil(library, key, yield_fn=_frame_yield)
                if res is not None:
                    self.completed_items += 1
                    if library.registry is not None:
                        scales[key] = _measure_member_scale(library, key)
            except _WarmupAbort:
                return
            except Exception:
                pass

        # 3. Active scene & festival actions (pure PIL).
        target_scene = active_scene or (target_wp.key if target_wp is not None else pick_default_scene(today))
        registry = getattr(library, "registry", None)
        if registry is None:
            return
        for key, _name, _col in roster:
            scale = scales.get(key)
            if scale is None:
                try:
                    scale = _measure_member_scale(library, key)
                except Exception:
                    continue
            for action in _wanted_actions_for(library, key, target_scene, today):
                if self._yield_step(gen, busy_check):
                    return
                spec = registry.resolve(key, action)
                if spec is None or spec.action != action:
                    continue
                try:
                    if _prepare_action_pil(library, spec, scale, yield_fn=_frame_yield) is not None:
                        self.completed_items += 1
                except _WarmupAbort:
                    return
                except Exception:
                    pass


class PandaStandbyOverlay:
    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        char_key: str,
        char_name: str,
        frames: dict[str, list[tk.PhotoImage]],
        flipped_walk_frames: list[tk.PhotoImage],
        passion_points: int = 0,
        companion_minutes: int = 0,
        on_close: Callable[[], None] | None = None,
        lock_on_exit: bool = False,
        show_panda_tags: bool = False,
        scene: str | None = None,
        bounds=None,
        lang: str = "zh_TW",
        wallpapers: Sequence[WallpaperSpec] | None = None,
        today: datetime.date | None = None,
        other_bounds: Sequence = (),
        lock_probe: Callable[[], bool | None] | None = None,
        clock_position: str = "top_right",
        display_px: int | None = None,
    ) -> None:
        self.parent = parent
        self.lang = lang
        self.char_key = char_key
        self.char_name = char_name
        self.frames = frames
        self.flipped_walk_frames = flipped_walk_frames
        self.passion_points = passion_points
        self.companion_minutes = companion_minutes
        self.on_close = on_close
        self.lock_on_exit = lock_on_exit
        self.lock_probe = lock_probe or is_workstation_locked
        self._saw_real_lock = False
        self.show_panda_tags = show_panda_tags
        self.clock_position = clock_position if clock_position in VALID_STANDBY_CLOCK_POSITIONS else "top_right"
        self.pure_view = False
        self._gen = 1

        self.rng = random.Random()
        self.max_performers = MAX_PAUSE_PERFORMERS
        self.running = True
        self._created_at = time.monotonic()
        self._grace_period_s = 0.8
        self.mouse_origin: tuple[int, int] | None = None
        self._after_ids: dict[str, str] = {}
        self._action_jobs: dict[tuple[str, str], tuple] = {}
        self._scene_tick_fn: Callable[[], None] | None = None
        self._scene_state: dict = {}
        self._fortune_student_item: int | None = None
        self._tick_n = 0
        self._today_fixed = today is not None
        self.today = today or datetime.date.today()
        if wallpapers is None:
            wallpapers = load_wallpapers()
        self.wallpapers = {w.key: w for w in wallpapers if w.key not in SCENES}
        self.scenes = SCENES + tuple(self.wallpapers)
        self._wallpaper_cache: dict[str, ImageTk.PhotoImage] = {}
        if scene in self.scenes:
            self.scene = scene
        else:       # a different backdrop every time; December keeps to the Christmas ones
            festive = [s for s in self.scenes if "christmas" in s]
            self.scene = self.rng.choice(festive if self.today.month == 12 and festive else list(self.scenes))

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        # ``bounds`` (left/top/right/bottom, e.g. a WorkArea) = the pet's monitor;
        # default is the primary screen. Canvas coordinates stay local (0..sw).
        if bounds is not None:
            left, top = bounds.left, bounds.top
            self.sw, self.sh = bounds.right - bounds.left, bounds.bottom - bounds.top
        else:
            left, top = 0, 0
            self.sw = self.win.winfo_screenwidth()
            self.sh = self.win.winfo_screenheight()
        self.win.geometry(f"{self.sw}x{self.sh}+{left}+{top}")
        self.win.configure(bg="#0a0c16")

        self.canvas = tk.Canvas(
            self.win,
            width=self.sw,
            height=self.sh,
            bg="#0a0c16",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Shared layout. k = display scaling (1.0 at 96 dpi, 2.0 at 200 % when the
        # process is DPI aware); every fixed pixel size is multiplied by it.
        try:
            self.k = max(1.0, min(4.0, self.win.winfo_fpixels("1i") / 96.0))
        except Exception:
            self.k = 1.0
        k = self.k
        self.sprite_px = (max(48, min(int(display_px), round(self.sh * .60))) if display_px is not None else
                          max(96, min(round(SPRITE_PX * k), int(self.sh * 0.22))))
        self.cx = self.sw // 2
        self.floor_y = self.sh - round(170 * k)
        # Side prop regions stay balanced on the outer thirds even after moving the clock to the corner.
        side_span = max(round(160 * k), min(round(460 * k), self.sw // 3))
        self.side_l = (0, side_span)
        self.side_r = (self.sw - side_span, self.sw)
        self._layout_card()

        # 1. Compact corner clock card + top hints + initial backdrop paint
        self.covers: list[dict] = []
        self._build_card()
        self._draw_scene()
        try:
            self.win.update_idletasks()
        except tk.TclError:
            pass

        # 2. All 5 Pandas Parade System ("bg" already below "ui")
        self.member_sprites: list[dict] = []
        self._load_all_pandas()
        # Required stage poses are prepared one frame per after() step once
        # the backdrop and five base actors are visible, not synchronously here.
        self.canvas.tag_lower("bg")

        # Bindings: arrows cycle scenes, H toggles pure view, anything else exits
        self.win.bind("<Key>", self.handle_key)
        self.win.bind("<ButtonPress>", self.handle_click)
        self.win.bind("<Motion>", self.handle_motion)
        _detach_ime_from_widgets((self.win, self.canvas))

        # 3. Every other monitor gets a cover: the same backdrop and synced clock.
        self.covers = [self._make_cover(b) for b in other_bounds]
        self._paint_covers()
        self._sync_overlay_chrome_visibility()
        _detach_ime_from_widgets((self.win, self.canvas))
        try:
            self.win.focus_force()
        except Exception:
            pass

        self.update_clock()
        self.animate_pandas()
        self._scene_tick()
        self._restart_hint_fade()
        self._later("lock_watch", LOCK_WATCH_MS, self._watch_real_lock)
        self._queue_action_loading()

    # ------------------------------------------------------------------ other monitors
    def _make_cover(self, bounds) -> dict:
        w, h = bounds.right - bounds.left, bounds.bottom - bounds.top
        win = tk.Toplevel(self.win)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{bounds.left}+{bounds.top}")
        canvas = tk.Canvas(win, width=w, height=h, bg="#0a0c16", highlightthickness=0, cursor="none")
        canvas.pack(fill="both", expand=True)
        # 2026-11-22: a cover shows the backdrop only. The old centred white HH:MM:SS/date
        # was unreadable on photo wallpapers; the real clock card lives on the pet's screen.
        win.bind("<Key>", self.handle_key)
        win.bind("<ButtonPress>", self.handle_click)
        win.bind("<Motion>", self.handle_motion)
        _detach_ime_from_widgets((win, canvas))
        return {"win": win, "canvas": canvas, "w": w, "h": h, "clock": None, "date": None, "photos": {}}

    def _paint_covers(self) -> None:
        """The current scene on every cover: photo wallpaper or static drawn scene (no clock/pandas)."""
        bg = self.canvas.cget("bg")
        wallpaper = self.wallpapers.get(self.scene)
        drawn_builders = {
            "starfield": self._draw_starfield,
            "campfire": self._draw_campfire,
            "christmas": self._draw_christmas,
            "practice_room": self._draw_practice_room,
        }
        builder = drawn_builders.get(self.scene) if wallpaper is None else None
        for cover in self.covers:
            canvas = cover["canvas"]
            canvas.delete("bg")
            canvas.configure(bg=bg)
            if wallpaper is not None:
                photo = cover["photos"].pop(wallpaper.key, None)
                if photo is not None:
                    cover["photos"][wallpaper.key] = photo      # most recent last
                else:
                    try:
                        photo = ImageTk.PhotoImage(_fitted_wallpaper(wallpaper.path, cover["w"], cover["h"]),
                                                   master=cover["win"])
                    except (OSError, ValueError):
                        photo = None
                    cover["photos"][wallpaper.key] = photo
                    _trim_photo_cache(cover["photos"])
                if photo is not None:
                    canvas.create_image(0, 0, anchor="nw", image=photo, tags=("bg",))
                    canvas.tag_lower("bg")
            elif builder is not None:
                cw, ch = cover["w"], cover["h"]
                saved = (
                    self.canvas,
                    self.sw,
                    self.sh,
                    self.cx,
                    self.floor_y,
                    self.side_l,
                    self.side_r,
                    self._scene_state,
                    self._scene_tick_fn,
                )
                try:
                    k = self.k
                    side_span = max(round(160 * k), min(round(460 * k), cw // 3))
                    self.canvas = canvas
                    self.sw, self.sh = cw, ch
                    self.cx = cw // 2
                    self.floor_y = ch - round(170 * k)
                    self.side_l = (0, side_span)
                    self.side_r = (cw - side_span, cw)
                    self._scene_state = {}
                    self._scene_tick_fn = None
                    cover_bg, _hint = builder()
                    canvas.configure(bg=cover_bg)
                    canvas.tag_lower("bg")
                finally:
                    (
                        self.canvas,
                        self.sw,
                        self.sh,
                        self.cx,
                        self.floor_y,
                        self.side_l,
                        self.side_r,
                        self._scene_state,
                        self._scene_tick_fn,
                    ) = saved

    # ------------------------------------------------------------------ timers
    def _later(self, key: str, ms: int, fn: Callable[[], None]) -> None:
        if not self.running:
            return
        old = self._after_ids.pop(key, None)
        if old is not None:
            try:
                self.win.after_cancel(old)
            except Exception:
                pass
        self._after_ids[key] = self.win.after(ms, fn)

    def _cancel_all_timers(self) -> None:
        for aid in list(self._after_ids.values()):
            try:
                self.win.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

    # ------------------------------------------------------------------ card
    def _layout_card(self) -> None:
        """Size and corner-anchor the compact clock card from real font metrics across DPIs."""
        k = self.k
        theme = get_standby_clock_theme(self.scene, self.char_key)
        self.f_clock = tkfont.Font(root=self.win, family=theme["family"], size=28, weight="bold")
        self.f_date = tkfont.Font(root=self.win, family="Microsoft JhengHei", size=10)
        self.f_badge = tkfont.Font(root=self.win, family="Microsoft JhengHei", size=9, weight="bold")
        self.f_hint = tkfont.Font(root=self.win, family="Microsoft JhengHei", size=11)
        self.f_hint2 = tkfont.Font(root=self.win, family="Microsoft JhengHei", size=10)
        self.f_tag = tkfont.Font(root=self.win, family="Microsoft JhengHei", size=10, weight="bold")
        name = _strip_emoji(self.char_name)
        self.badge_text = t("standby_badge", self.lang, name=name, passion=self.passion_points)

        lc = self.f_clock.metrics("linespace")
        ld = self.f_date.metrics("linespace")
        lb = self.f_badge.metrics("linespace")
        pad_y = max(round(10 * k), round(ld * 0.72))
        gap1 = max(round(2 * k), round(ld * 0.16))
        gap2 = max(round(5 * k), round(ld * 0.36))
        pad_x = max(round(14 * k), round(ld * 1.15))

        clock_w = self.f_clock.measure("00:00:00")
        date_w = self.f_date.measure(format_long_date(2026, 12, 30, 2, self.lang))
        badge_w = self.f_badge.measure(self.badge_text)
        content_w = max(clock_w, date_w, badge_w)
        # Keep the card sleek in the corner (never occupying the center hero backdrop).
        corner_cap = (
            self.sw - round(24 * k)
            if self.sw < round(640 * k)
            else min(self.sw - round(24 * k), max(round(240 * k), int(self.sw * 0.40)))
        )
        max_card_w = max(round(180 * k), min(corner_cap, max(round(410 * k), content_w + 2 * pad_x)))
        min_card_w = min(max_card_w, round(220 * k))
        self.card_w = max(min_card_w, min(max_card_w, content_w + 2 * pad_x))
        inner_w = max(40, self.card_w - 2 * pad_x)
        badge_lines = max(1, math.ceil(badge_w / inner_w)) if badge_w > inner_w else 1
        date_lines = max(1, math.ceil(date_w / inner_w)) if date_w > inner_w else 1
        self._card_inner_w = inner_w
        self.card_h = pad_y + lc + gap1 + ld * date_lines + gap2 + lb * badge_lines + pad_y

        hint_y0 = round(10 * k)
        hint_y1 = hint_y0 + self.f_hint.metrics("linespace") + round(4 * k)
        hint_bottom = hint_y1 + self.f_hint2.metrics("linespace")
        exit_txt = t("standby_exit_hint", self.lang) + (t("standby_lock_suffix", self.lang) if self.lock_on_exit else "")
        scene_labels = [t("standby_scene_hint", self.lang, scene=self.scene_label())]
        if hasattr(self, "wallpapers"):
            scene_labels.extend(t("standby_scene_hint", self.lang, scene=w.label(self.lang)) for w in self.wallpapers.values())
        hint_half = max(self.f_hint.measure(exit_txt), max(self.f_hint2.measure(s) for s in scene_labels)) // 2 + round(22 * k)

        margin_x = round(20 * k)
        margin_y = round(16 * k)
        if self.clock_position == "top_left":
            card_x0 = margin_x
        else:
            card_x0 = self.sw - margin_x - self.card_w
        card_x0 = max(round(8 * k), min(card_x0, self.sw - self.card_w - round(8 * k)))
        self.card_cx = card_x0 + self.card_w // 2

        hint_x0, hint_x1 = self.cx - hint_half - round(10 * k), self.cx + hint_half + round(10 * k)
        overlaps_hint = not (card_x0 + self.card_w <= hint_x0 or card_x0 >= hint_x1)
        top = (hint_bottom + round(14 * k)) if overlaps_hint else margin_y

        parade_top = self.sh - self.sprite_px - round(40 * k)
        top = max(round(6 * k), min(top, parade_top - self.card_h - round(8 * k)))
        self.cy = top + self.card_h // 2
        self._y_clock = top + pad_y
        self._y_date = self._y_clock + lc + gap1
        self._y_badge = self._y_date + ld * date_lines + gap2

    def _build_card(self) -> None:
        k = self.k
        cx = getattr(self, "card_cx", self.cx)
        cy, card_w, card_h = self.cy, self.card_w, self.card_h
        o_x, o_y = round(6 * k), round(5 * k)
        theme = get_standby_clock_theme(self.scene, self.char_key)
        wrap_w = getattr(self, "_card_inner_w", max(40, card_w - round(24 * k)))

        # 1. Outer Dark Contrast Halo (keeps corner card readable even over sakura blossoms/sky)
        _draw_round_rect(
            self.canvas,
            cx - card_w // 2 - o_x, cy - card_h // 2 - o_y,
            cx + card_w // 2 + o_x, cy + card_h // 2 + o_y,
            r=20 * k, fill=theme.get("shadow_bg", "#0a0614"), outline=theme.get("shadow_border", "#24133b"),
            width=max(1, round(k)), tags=("ui", "clock_card"),
        )
        # 2. Sleek Compact Dark Frosted Badge Body
        _draw_round_rect(
            self.canvas,
            cx - card_w // 2, cy - card_h // 2,
            cx + card_w // 2, cy + card_h // 2,
            r=16 * k, fill=theme["card_bg"], outline=theme["card_border"],
            width=max(2, round(1.5 * k)), tags=("ui", "clock_card"),
        )
        # 3. Inner Luminous Bezel
        _draw_round_rect(
            self.canvas,
            cx - card_w // 2 + round(3 * k), cy - card_h // 2 + round(3 * k),
            cx + card_w // 2 - round(3 * k), cy + card_h // 2 - round(3 * k),
            r=13 * k, fill="", outline=theme["bezel"], width=1, tags=("ui", "clock_card"),
        )

        # 4. Top Gradient Accent Flow Line
        bar = card_w * 0.34
        self.canvas.create_line(
            cx - bar, cy - card_h // 2 + round(2 * k), cx, cy - card_h // 2 + round(2 * k),
            fill=theme["flow1"], width=max(2, round(2.5 * k)), tags=("ui", "clock_card"),
        )
        self.canvas.create_line(
            cx, cy - card_h // 2 + round(2 * k), cx + bar, cy - card_h // 2 + round(2 * k),
            fill=theme["flow2"], width=max(2, round(2.5 * k)), tags=("ui", "clock_card"),
        )

        # 5. Soft Text Shadows + High-Contrast Foreground Clock / Date / Cheer Badge
        self.canvas.create_text(
            cx + 1, self._y_clock + 1, text="00:00:00", fill="#05060b", anchor="n",
            font=self.f_clock, tags=("ui", "clock_card", "clock_shadow"),
        )
        self.clock_item = self.canvas.create_text(
            cx, self._y_clock, text="00:00:00", fill=theme["clock_color"], anchor="n",
            font=self.f_clock, tags=("ui", "clock_card"),
        )
        self.canvas.create_text(
            cx + 1, self._y_date + 1, text="", fill="#05060b", anchor="n",
            font=self.f_date, width=wrap_w, justify="center", tags=("ui", "clock_card", "date_shadow"),
        )
        self.date_item = self.canvas.create_text(
            cx, self._y_date, text="", fill=theme["date_color"], anchor="n",
            font=self.f_date, width=wrap_w, justify="center", tags=("ui", "clock_card"),
        )
        self.canvas.create_text(
            cx + 1, self._y_badge + 1, text=self.badge_text, fill="#05060b", anchor="n",
            font=self.f_badge, width=wrap_w, justify="center", tags=("ui", "clock_card", "badge_shadow"),
        )
        self.badge_item = self.canvas.create_text(
            cx, self._y_badge, text=self.badge_text, anchor="n",
            fill=theme["badge_color"], font=self.f_badge, width=wrap_w, justify="center",
            tags=("ui", "clock_card"),
        )
        # Top-centre hints stay concise and independent of the corner clock card.
        y0 = round(10 * k)
        y1 = y0 + self.f_hint.metrics("linespace") + round(4 * k)
        self.hint_item = self.canvas.create_text(
            self.cx, y0, anchor="n",
            text=t("standby_exit_hint", self.lang) + (t("standby_lock_suffix", self.lang) if self.lock_on_exit else ""),
            fill="#94a3b8", font=self.f_hint, tags=("ui", "standby_hint_ui"),
        )
        # Scene-switch hint (fades to low contrast)
        self.scene_hint_item = self.canvas.create_text(
            self.cx, y1, text="", fill="#cbd5e1", anchor="n", font=self.f_hint2, tags=("ui", "standby_hint_ui"),
        )
        self.hint_bottom = y1 + self.f_hint2.metrics("linespace")

    def toggle_pure_view(self) -> bool:
        """Toggle H-key pure wallpaper appreciation mode without leaving standby."""
        self.pure_view = not self.pure_view
        self._sync_overlay_chrome_visibility()
        return self.pure_view

    def _sync_overlay_chrome_visibility(self) -> None:
        hide_clock = self.pure_view or self.clock_position == "hidden"
        hide_hints = self.pure_view
        try:
            self.canvas.itemconfigure("clock_card", state="hidden" if hide_clock else "normal")
            self.canvas.itemconfigure("standby_hint_ui", state="hidden" if hide_hints else "normal")
        except tk.TclError:
            pass
        for cover in getattr(self, "covers", ()):
            for key in ("clock", "date"):
                item = cover.get(key)
                if item is not None:
                    try:
                        cover["canvas"].itemconfigure(item, state="hidden" if hide_clock else "normal")
                    except tk.TclError:
                        pass

    # ------------------------------------------------------------------ pandas
    def _load_all_pandas(self) -> None:
        """Loads and initializes sprites and canvas items for all 5 Apink pandas."""
        self.pandas: list[dict] = []
        # Same registry sprites as the desktop pet, height-equalized so all five
        # members look the same size side by side (see sprites.BODY_PX).
        library = SpriteLibrary(resource_dir(), display_px=self.sprite_px,
                                binary_alpha=STANDBY_BINARY_ALPHA, edge_refine=STANDBY_EDGE_REFINE)
        self._library = library
        for key, display_name, tag_col in MEMBER_ROSTER:
            sprites = None
            walk_frames: list[tk.PhotoImage] = []
            flipped_frames: list[tk.PhotoImage] = []
            cheer_frames: list[tk.PhotoImage] = []
            try:
                sprites = self._member_sprites(library, key)
                walk_frames = sprites.get("walk")
                flipped_frames = sprites.get("walk", -1)
                cheer_frames = sprites.get("cheer")
            except Exception:
                log.exception("standby: cannot load sprites for %s", key)

            # Fallback to active pet frames if disk loading failed
            if not walk_frames and "walk" in self.frames and self.frames["walk"]:
                walk_frames = self.frames["walk"]
                flipped_frames = self.flipped_walk_frames
            if not flipped_frames:
                flipped_frames = walk_frames
            if not cheer_frames and key == self.char_key and self.frames.get("cheer"):
                cheer_frames = self.frames["cheer"]
            if cheer_frames and walk_frames and cheer_frames[0].height() != walk_frames[0].height():
                cheer_frames = []  # mismatched sizes would make the parade jump
            if not cheer_frames:
                cheer_frames = walk_frames
            self.pandas.append({
                "key": key,
                "name": get_member_short_name(key, self.lang),
                "color": tag_col,
                "walk": walk_frames,
                "flipped_walk": flipped_frames,
                "left_walk_offset": sprites.offset("walk", -1) if sprites is not None else (0, 0),
                "left_walk_ms": sprites.frame_ms("walk", -1, PANDA_TICK_MS) if sprites is not None else PANDA_TICK_MS,
                "cheer": cheer_frames,
                "actions": {},      # filled by _load_next_action once the parade is on screen
                "pw": walk_frames[0].width() if walk_frames else self.sprite_px,
                "ph": walk_frames[0].height() if walk_frames else self.sprite_px,
            })

        pw = self.pandas[0]["pw"]
        ph = self.pandas[0]["ph"]
        k = self.k
        self.py = self.sh - ph - round(22 * k)
        self.tag_dy = round(14 * k)

        total_members = len(self.pandas)
        self.gap = max(round(16 * k), min(round(60 * k), (self.sw - total_members * pw - round(120 * k)) // max(1, total_members - 1)))
        self.parade_w = total_members * pw + (total_members - 1) * self.gap

        self.px = round(40 * k)
        self.p_dir = 1
        self.p_step = max(1, round(6 * k))
        self.p_frame_idx = 0
        self.p_cheer_ticks = 0
        self.p_pause_tick = 0
        self.pause_plan: dict[str, str | None] = {}

        for i, panda in enumerate(self.pandas):
            cur_x = self.px + i * (pw + self.gap)
            if self.show_panda_tags:
                # Dark shadow under the coloured name keeps it readable on any scene.
                panda["tag_shadow"] = self.canvas.create_text(
                    cur_x + pw // 2 + 1, self.py - self.tag_dy + 1, text=panda["name"], fill="#05060a",
                    font=self.f_tag, tags=("ui",),
                )
                panda["tag_item"] = self.canvas.create_text(
                    cur_x + pw // 2, self.py - self.tag_dy, text=panda["name"], fill=panda["color"],
                    font=self.f_tag, tags=("ui",),
                )
            img = panda["walk"][0] if panda["walk"] else ""
            panda["img_item"] = self.canvas.create_image(
                cur_x, self.py, anchor="nw", image=img, tags=("ui",)
            )

    def _member_sprites(self, library: SpriteLibrary, member: str) -> MemberSprites:
        """Reuse prepared PIL frames through the same loader as desktop sprites."""
        return library.load_member(member, self.win)

    def _member_scale(self, library: SpriteLibrary, member: str) -> float:
        """The member's equal scale (the walk pipeline's), measured once per window."""
        scales = self.__dict__.setdefault("_member_scales", {})
        if member not in scales:
            scales[member] = _measure_member_scale(library, member)
        return scales[member]

    def _wanted_actions(self, library: SpriteLibrary, member: str) -> list[str]:
        """The member's standby actions plus this scene's extras (set_scene loads the next scene's)."""
        return _wanted_actions_for(library, member, getattr(self, "scene", None), self.today)

    def _load_standby_actions(self, library: SpriteLibrary, member: str,
                              walk_frames: list[tk.PhotoImage], only: Sequence[str] | None = None) -> dict[str, dict]:
        """Approved registry actions tagged "standby" for one member.

        {action: {frames, frame_ms, tags, offset}}; offset (dx, dy) moves the frame from the
        walk frame's top-left so both feet anchors coincide. Only the exact action is used
        (the registry would fall back to idle), at the member's equalized scale, on its own
        approved canvas (e.g. 384 for tall hats) without shrinking it to the walk height.
        """
        registry, cache = getattr(library, "registry", None), getattr(library, "cache", None)
        if registry is None or cache is None or not walk_frames:
            return {}
        out: dict[str, dict] = {}
        try:
            names = list(only) if only is not None else self._wanted_actions(library, member)
            if not names:
                return {}
            scale = self._member_scale(library, member)
            walk_fx, walk_fy = walk_feet_point(library.display_px)
            for name in names:
                spec = registry.resolve(member, name)
                if spec is None or spec.action != name:
                    continue
                prepared = self._prepared_action(library, spec, scale)
                if prepared is None:
                    continue
                out[name] = self._action_entry(library, spec, prepared)
        except Exception:
            log.exception("standby: cannot load standby actions for %s", member)
        return out

    def _action_entry(self, library, spec, prepared) -> dict:
        images, (fx, fy) = prepared
        walk_fx, walk_fy = walk_feet_point(library.display_px)
        hold = len(images) == 1 or spec.action in PAUSE_HOLD_END
        # Lazy Tk images (2026-11-22): a stage loads ~5 members x every standby action, but a
        # stop plays only a few. Eager PhotoImages for all of them were ~230 MB of Tk pixels
        # (32-bit per pixel) while standby was open; now only frames actually shown exist.
        return {"frames": LazyPhotoList(images, self.win),
                "frame_ms": 1000.0 / spec.fps, "tags": tuple(spec.tags),
                "loop": not hold and spec.action not in PAUSE_ONCE_THEN_CHEER, "hold": hold,
                "offset": (walk_fx - fx, walk_fy - fy), "anchor": (fx, fy),
                "alpha_bboxes": tuple(im.getchannel("A").getbbox() for im in images)}

    def _prepared_action(self, library: SpriteLibrary, spec, scale: float
                         ) -> tuple[list[Image.Image], tuple[int, int]] | None:
        """(display frames, feet point) of an exact action; cached across windows by source hash."""
        return _prepare_action_pil(library, spec, scale)

    # ------------------------------------------------------------------ deferred action loading
    def _queue_action_loading(self) -> None:
        """Load the standby actions in small steps after the window is up (opening used to wait ~4 s)."""
        first = "eunji" if self.scene in (DOME_EUNJI_SCENE, FORTUNE_ROOM_SCENE) else self.char_key
        self._action_queue = sorted((p["key"] for p in self.pandas), key=lambda key: key != first)
        self._unloadable = {p["key"]: set() for p in self.pandas}
        gen = self._gen
        self._later("load_actions", ACTION_LOAD_DELAY_MS, lambda: self._load_next_action(gen))

    def _load_next_action(self, gen: int | None = None) -> None:
        if not self.running or (gen is not None and gen != self._gen):
            return
        if self._load_one_pending_action():
            cur_gen = self._gen
            self._later("load_actions", ACTION_LOAD_STEP_MS, lambda: self._load_next_action(cur_gen))

    def _load_one_pending_action(self) -> bool:
        """Load one missing action of the first member still loading; True while some remain."""
        queue = getattr(self, "_action_queue", [])
        library = getattr(self, "_library", None)
        while queue and self.running:
            panda = next(p for p in self.pandas if p["key"] == queue[0])
            skip = self._unloadable[panda["key"]]
            missing = [] if library is None else [
                a for a in self._wanted_actions(library, panda["key"]) if a not in panda["actions"] and a not in skip]
            if missing:
                name = missing[0]
                jobs = getattr(self, "_action_jobs", None)
                if jobs is not None:
                    job_key = (panda["key"], name)
                    entry = jobs.get(job_key)
                    if entry is None:
                        spec = library.registry.resolve(panda["key"], name)
                        if spec is None or spec.action != name:
                            skip.add(name)
                            return True
                        scale = self._member_scale(library, panda["key"])
                        jobs[job_key] = (_iter_prepare_action_pil(library, spec, scale), spec)
                        return True
                    steps, spec = entry
                    try:
                        next(steps)
                        return True
                    except StopIteration as done:
                        jobs.pop(job_key, None)
                        prepared = done.value
                        loaded = {name: self._action_entry(library, spec, prepared)} if prepared is not None else {}
                    except Exception:
                        jobs.pop(job_key, None)
                        log.exception("standby: incremental action %s failed", job_key)
                        loaded = {}
                else:
                    loaded = self._load_standby_actions(library, panda["key"], panda["walk"], only=missing[:1])
                panda["actions"].update(loaded)
                if name not in loaded:
                    skip.add(name)
                if not (self.scene == FORTUNE_ROOM_SCENE and panda["key"] == "eunji"):
                    # first pose for every actor before filling one actor's wardrobe; the
                    # fortune reader and her student enter together, so Eunji loads both first.
                    queue.append(queue.pop(0))
                return True
            queue.pop(0)
        return False

    def actions_loading(self) -> bool:
        """True until every member's standby actions for this scene are loaded."""
        return bool(getattr(self, "_action_queue", None))

    def finish_action_loading(self) -> None:
        """Load whatever is still queued right now (a stop needs the actions it may pick)."""
        aid = self._after_ids.pop("load_actions", None)
        if aid is not None:
            try:
                self.win.after_cancel(aid)
            except Exception:
                pass
        while self._load_one_pending_action():
            pass

    def _start_pause(self) -> None:
        """Whole parade stops; each member cheers or plays one allowed standby action."""
        if self.actions_loading():
            self.finish_action_loading()
        contexts = standby_contexts(self.scene, self.today)
        options = {
            p["key"]: [a for a, info in p.get("actions", {}).items() if action_allowed(info["tags"], contexts)
                       and scene_fits(a, info["tags"], p["key"], self.scene)]
            for p in self.pandas
        }
        christmas = "christmas" in contexts
        costume = COSTUME_SCENES.get(self.scene)
        fest = festival_on(self.today)
        fest_action = fest.action if fest is not None else None
        if fest_action and not christmas and not costume:
            self._load_festival_action(fest_action)
        if christmas:   # in its season all five stop in the same Christmas set (cheering is the everyday one)
            shared = [s for s in CHRISTMAS_SETS if all(s in names for names in options.values())]
            costume = self.rng.choice(shared) if shared else CHRISTMAS_COSTUME
            options = {key: [] if costume in names else names for key, names in options.items()}
        elif fest_action and not costume and any(
                fest_action in p.get("actions", {})
                and action_allowed(p["actions"][fest_action]["tags"], contexts)
                for p in self.pandas):
            costume = fest_action
            options = {key: [] if fest_action in next(
                (p.get("actions", {}) for p in self.pandas if p["key"] == key), {}) else names
                for key, names in options.items()}
        elif costume:
            pool = SCENE_ACTIONS.get(self.scene, {})
            options = {key: [a for a in names if a in pool.get(key, ()) and a != costume]
                       for key, names in options.items()}
        else:
            options = self._lean_on_scene(options)
        if costume and not christmas:
            # A costume stage is a show: every member with a dance dances (all five were
            # drawn); the pose is only for a member without one.
            self.pause_plan = {key: self.rng.choice(names) if names else None for key, names in options.items()}
        else:
            self.pause_plan = pick_pause_actions(options, self.rng)
            if not christmas:
                self._limit_performers()
        if costume:
            for p in self.pandas:
                if not self.pause_plan.get(p["key"]) and costume in p.get("actions", {}):
                    self.pause_plan[p["key"]] = costume
        length = PAUSE_TICKS
        for p in self.pandas:
            action = self.pause_plan.get(p["key"])
            if action:
                info = p["actions"][action]
                # At least one full pass at the registry fps (the parade timer stays at PANDA_TICK_MS).
                length = max(length, math.ceil(len(info["frames"]) * info["frame_ms"] / PANDA_TICK_MS))
        self.p_cheer_ticks = length
        self.p_pause_tick = 0

    def _lean_on_scene(self, options: dict[str, list[str]]) -> dict[str, list[str]]:
        """Mostly what fits this place; signature moves keep their share."""
        pool = SCENE_ACTIONS.get(self.scene, {})
        leaned = {}
        for member, names in options.items():
            local = [a for a in names if a in pool.get(member, ())]
            leaned[member] = local if local and self.rng.random() < SCENE_ACTION_SHARE else names
        return leaned

    def _limit_performers(self) -> None:
        """A couple of members show off at each stop; the rest just cheer along."""
        performers = [key for key, action in self.pause_plan.items() if action]
        self._pause_turn = getattr(self, "_pause_turn", -1) + 1
        turn = self._pause_turn % max(1, len(performers))
        keep = set((performers[turn:] + performers[:turn])[:self.max_performers])
        for key in performers:
            if key not in keep:
                self.pause_plan[key] = None

    def _pause_frame(self, panda: dict, i: int) -> tuple[tk.PhotoImage, int, int]:
        """(frame, dx, dy) during a stop; dx/dy place an action's feet on the walk feet point."""
        action = self.pause_plan.get(panda["key"])
        info = panda.get("actions", {}).get(action) if action else None
        if info:
            frames = info["frames"]
            elapsed_ms = self.p_pause_tick * PANDA_TICK_MS        # time since the stop began
            dx, dy = info.get("offset", (0, 0))
            step = int(elapsed_ms // info["frame_ms"])
            if info.get("loop"):
                return frames[step % len(frames)], dx, dy
            if step < len(frames) or info.get("hold", True):
                return frames[min(len(frames) - 1, step)], dx, dy
        seq = panda["cheer"]
        return seq[(self.p_frame_idx // 2 + i) % len(seq)], 0, 0

    def update_clock(self) -> None:
        if not self.running:
            return
        now = datetime.datetime.now()
        if not getattr(self, "_today_fixed", False):
            self.today = now.date()
        time_str = now.strftime("%H:%M:%S")
        date_str = format_long_date(now.year, now.month, now.day, now.weekday(), self.lang)

        self.canvas.itemconfigure(self.clock_item, text=time_str)
        self.canvas.itemconfigure("clock_shadow", text=time_str)
        self.canvas.itemconfigure("date_shadow", text=date_str)
        self.canvas.itemconfigure(self.date_item, text=date_str)
        self._later("clock", 1000, self.update_clock)

    def animate_pandas(self) -> None:
        if not self.running:
            return
        if self.scene in STAGE_SCENES:
            self._animate_dome_scene()
            return

        pw = self.pandas[0]["pw"]
        cheering = self.p_cheer_ticks > 0
        if cheering:
            self.p_cheer_ticks -= 1
        else:
            min_x = round(30 * self.k)
            max_x = self.sw - self.parade_w - min_x
            if self.px >= max_x:
                self.p_dir = -1
            elif self.px <= min_x:
                self.p_dir = 1
            self.px += self.p_dir * self.p_step
            # Every ~20 s on average the whole team stops for a short cheer / action.
            if not self.actions_loading() and self.rng.random() < 0.006:
                self._start_pause()

        for i, panda in enumerate(self.pandas):
            if not panda["walk"]:
                continue
            cur_x = self.px + i * (pw + self.gap)
            dx = dy = 0
            if cheering:
                frame, dx, dy = self._pause_frame(panda, i)
            else:
                seq = panda["walk"] if self.p_dir == 1 else panda["flipped_walk"]
                tick = self.p_frame_idx
                if self.p_dir < 0:
                    dx, dy = panda.get("left_walk_offset", (0, 0))
                    tick = int(tick * PANDA_TICK_MS / panda.get("left_walk_ms", PANDA_TICK_MS))
                frame = seq[(tick + i * 2) % len(seq)]
            self.canvas.coords(panda["img_item"], cur_x + dx, self.py + dy)
            self.canvas.itemconfigure(panda["img_item"], image=frame)

            if "tag_item" in panda:
                self.canvas.coords(panda["tag_shadow"], cur_x + pw // 2 + 1, self.py - self.tag_dy + 1)
                self.canvas.coords(panda["tag_item"], cur_x + pw // 2, self.py - self.tag_dy)

        if cheering:
            self.p_pause_tick += 1          # after drawing: the first stop tick shows frame 0
        self.p_frame_idx += 1
        self._later("pandas", PANDA_TICK_MS, self.animate_pandas)

    # ------------------------------------------------------------------ scenes
    def set_scene(self, name: str) -> None:
        """Switch the backdrop without leaving standby."""
        if name not in self.scenes:
            raise ValueError(f"unknown standby scene: {name!r}")
        prev_scene = self.scene
        self.scene = name
        if not self.running:
            return
        self.pause_plan = {key: None for key in getattr(self, "pause_plan", {})}   # the old scene's acts end
        self._load_scene_actions()
        if self.scene in STAGE_SCENES:
            self._ensure_dome_actions_loaded()
        self._draw_scene()
        if prev_scene in STAGE_SCENES and self.scene not in STAGE_SCENES:
            self._restore_parade_layout()
        self._restart_hint_fade()

    def _load_scene_actions(self) -> None:
        if self.scene in STAGE_SCENES and hasattr(self, "_action_jobs") and getattr(self, "pandas", None):
            self._queue_action_loading()
            return
        library = getattr(self, "_library", None)
        queued = set(getattr(self, "_action_queue", ()))
        for p in self.pandas if library is not None else ():
            if p["key"] in queued:
                continue
            missing = [a for a in SCENE_ACTIONS.get(self.scene, {}).get(p["key"], ()) if a not in p["actions"]]
            if missing:
                p["actions"].update(self._load_standby_actions(library, p["key"], p["walk"], only=missing))

    def _load_festival_action(self, action_name: str) -> None:
        library = getattr(self, "_library", None)
        if library is None or not action_name:
            return
        for p in self.pandas:
            if action_name not in p["actions"] and p["walk"]:
                p["actions"].update(self._load_standby_actions(library, p["key"], p["walk"], only=[action_name]))

    def cycle_scene(self, step: int = 1) -> str:
        idx = self.scenes.index(self.scene) if self.scene in self.scenes else 0
        self.set_scene(self.scenes[(idx + step) % len(self.scenes)])
        return self.scene

    def _draw_scene(self) -> None:
        self._clear_dome_stage()
        self.canvas.delete("bg")
        self._scene_state = {}
        self._scene_tick_fn = None
        wallpaper = self.wallpapers.get(self.scene)
        drawer = {
            "starfield": self._draw_starfield,
            "campfire": self._draw_campfire,
            "christmas": self._draw_christmas,
            "practice_room": self._draw_practice_room,
        }.get(self.scene) or (lambda: self._draw_wallpaper(wallpaper))
        bg, exit_hint_col = drawer()
        self.canvas.configure(bg=bg)
        self.win.configure(bg=bg)
        self.canvas.itemconfigure(self.hint_item, fill=exit_hint_col)
        if self.scene in STAGE_SCENES:
            self._init_dome_stage_state()
        self.canvas.tag_lower("bg")
        self.canvas.itemconfigure(
            self.scene_hint_item,
            text=t("standby_scene_hint", self.lang, scene=self.scene_label()),
        )
        self._apply_clock_theme()
        self._sync_overlay_chrome_visibility()
        if getattr(self, "covers", None):
            self._paint_covers()
        if self.scene in STAGE_SCENES and getattr(self, "pandas", None):
            self._ensure_dome_actions_loaded()
            self._animate_dome_scene(reschedule=False)

    # ------------------------------------------------------------------ Taipei Dome & Fortune stage scenes
    def _clear_dome_stage(self) -> None:
        """Destroy any Dome/Fortune stage canvas items and cached PhotoImages."""
        if hasattr(self, "canvas"):
            for tag in ("dome_stage", "fortune_stage"):
                try:
                    self.canvas.delete(tag)
                except tk.TclError:
                    pass
        self._dome_state: dict | None = None
        self._dome_bubble_item: int | None = None
        self._dome_bubble_photo: ImageTk.PhotoImage | None = None
        self._dome_bubble_cache_key: tuple | None = None
        self._dome_spot_photo: ImageTk.PhotoImage | None = None
        self._fortune_student_item: int | None = None
        self._dome_bubble_placed: tuple | None = None
        for panda in getattr(self, "pandas", None) or ():
            panda.pop("_dome_placed", None)   # the parade moved the items: place them again

    def _restore_parade_layout(self) -> None:
        """Snap all 5 pandas and tags cleanly back onto the bottom parade track."""
        if not getattr(self, "pandas", None):
            return
        pw = self.pandas[0]["pw"]
        for i, panda in enumerate(self.pandas):
            self._set_member_shown(panda, True)
            cur_x = self.px + i * (pw + self.gap)
            seq = panda["walk"] if self.p_dir == 1 else panda["flipped_walk"]
            if seq:
                dx, dy = panda.get("left_walk_offset", (0, 0)) if self.p_dir < 0 else (0, 0)
                tick = int(self.p_frame_idx * PANDA_TICK_MS / panda.get("left_walk_ms", PANDA_TICK_MS)) if self.p_dir < 0 else self.p_frame_idx
                frame = seq[(tick + i * 2) % len(seq)]
                self.canvas.coords(panda["img_item"], cur_x + dx, self.py + dy)
                self.canvas.itemconfigure(panda["img_item"], image=frame)
            if "tag_item" in panda:
                self.canvas.coords(panda["tag_shadow"], cur_x + pw // 2 + 1, self.py - self.tag_dy + 1)
                self.canvas.coords(panda["tag_item"], cur_x + pw // 2, self.py - self.tag_dy)

    def _ensure_dome_actions_loaded(self) -> None:
        """Queue required stage frames; synchronous loading is only for legacy stubs."""
        library = getattr(self, "_library", None)
        if library is None or not getattr(self, "pandas", None):
            return
        if hasattr(self, "_action_jobs"):
            self._queue_action_loading()
            return
        for p in self.pandas:
            if not p.get("walk"):
                continue
            key = p["key"]
            if self.scene == DOME_BASEBALL_SCENE:
                wanted = (DOME_BASEBALL_ACTION,)
            elif self.scene == DOME_EUNJI_SCENE:
                wanted = EUNJI_DOME_CONCERT_OUTFITS if key == "eunji" else (DOME_FLANK_CHEER_ACTION,)
            elif self.scene == FORTUNE_ROOM_SCENE:
                wanted = (FORTUNE_READER_ACTION, FORTUNE_STUDENT_ACTION) if key == "eunji" else (DOME_FLANK_CHEER_ACTION,)
            else:
                wanted = ()
            missing = [a for a in wanted if a not in p["actions"]]
            if missing:
                p["actions"].update(self._load_standby_actions(library, key, p["walk"], only=missing))

    def _init_dome_stage_state(self) -> None:
        """Initialize synchronized monotonic timer and Scene 2 spotlight/note effects."""
        if hasattr(self, "canvas"):
            try:
                self.canvas.delete("dome_eunji_fx")
            except tk.TclError:
                pass
        if "_dome_base_tick" in self._scene_state:
            self._scene_tick_fn = self._scene_state["_dome_base_tick"]
        else:
            self._scene_state["_dome_base_tick"] = self._scene_tick_fn
        self._dome_state = {"t0": time.monotonic()}
        if self.scene == DOME_EUNJI_SCENE:
            self._setup_eunji_dome_fx()

    def _setup_eunji_dome_fx(self) -> None:
        """Soft vertical spotlight cone + gentle floating musical notes (non-strobing)."""
        k = self.k
        top_x, _ = map_cover_point(0.50, 0.0, self.sw, self.sh, WALLPAPER_SRC)
        stage_x, stage_y = map_cover_point(0.50, 0.73, self.sw, self.sh, WALLPAPER_SRC)
        top_x = max(80.0, min(self.sw - 80.0, top_x))
        stage_x = max(120.0, min(self.sw - 120.0, stage_x))
        stage_y = max(self.sh * 0.48, min(self.sh * 0.86, stage_y))

        # Single smooth Pillow RGBA spotlight cone + soft floor stage aura.
        spot_w = max(240, int(round(min(self.sw, 560 * k))))
        spot_h = max(200, int(round(stage_y + 70 * k)))
        left_x = int(round(stage_x - spot_w / 2.0))
        img = Image.new("RGBA", (spot_w, spot_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        beam_top_cx = top_x - left_x
        beam_bot_cx = spot_w / 2.0
        for layer, (half_top, half_bot, col) in enumerate((
            (58 * k, 155 * k, (255, 198, 232, 18)),
            (40 * k, 112 * k, (255, 224, 244, 22)),
            (24 * k, 72 * k, (255, 248, 252, 24)),
        )):
            draw.polygon(
                [
                    (beam_top_cx - half_top, 0),
                    (beam_top_cx + half_top, 0),
                    (beam_bot_cx + half_bot, stage_y),
                    (beam_bot_cx - half_bot, stage_y),
                ],
                fill=col,
            )
            rx = half_bot * 1.05
            ry = (44 - layer * 9) * k
            draw.ellipse(
                (beam_bot_cx - rx, stage_y - ry, beam_bot_cx + rx, stage_y + ry),
                fill=(255, 184, 224, 24 + layer * 8),
            )
        self._dome_spot_photo = ImageTk.PhotoImage(img, master=self.win)
        self.canvas.create_image(
            left_x, 0, anchor="nw", image=self._dome_spot_photo,
            tags=("bg", "dome_stage", "dome_eunji_fx"),
        )

        # Gentle floating musical notes drifting slowly upward around stage edges.
        note_chars = ("♪", "♫", "♩", "✧")
        note_cols = ("#ffd1eb", "#ffe9f7", "#fff4c8", "#ffb3dc")
        notes: list[dict] = []
        note_font = ("Segoe UI Symbol", max(12, round(15 * k)))
        for idx in range(8):
            side = -1 if idx % 2 == 0 else 1
            base_x = stage_x + side * self.rng.uniform(75 * k, min(260 * k, self.sw * 0.34))
            y = self.rng.uniform(stage_y - 220 * k, stage_y + 10 * k)
            col = note_cols[idx % len(note_cols)]
            item = self.canvas.create_text(
                base_x, y, text=note_chars[idx % len(note_chars)],
                fill=col, font=note_font, tags=("bg", "dome_stage", "dome_eunji_fx"),
            )
            notes.append({
                "item": item,
                "base_x": base_x,
                "y": y,
                "vy": self.rng.uniform(0.55, 1.05) * k,
                "ph": self.rng.uniform(0.0, 6.28),
                "min_y": max(self.hint_bottom + 24 * k, stage_y - 260 * k),
                "max_y": min(self.sh - 40 * k, stage_y + 20 * k),
            })

        try:
            self.canvas.tag_raise("standby_hint_ui")
        except tk.TclError:
            pass

        prev_tick = self._scene_tick_fn

        def eunji_tick() -> None:
            if prev_tick is not None:
                prev_tick()
            for n in notes:
                n["y"] -= n["vy"]
                if n["y"] < n["min_y"]:
                    n["y"] = n["max_y"]
                nx = n["base_x"] + math.sin(self._tick_n * 0.08 + n["ph"]) * 9.0 * k
                self.canvas.coords(n["item"], nx, n["y"])

        self._scene_tick_fn = eunji_tick

    def _dome_action_draw_spec(
        self,
        panda: dict,
        action_name: str | None,
        frame_idx: int,
        slot_cx: int,
        slot_fy: int,
    ) -> tuple[object, int, int, tuple[int, int, int, int]]:
        """Resolve `(PhotoImage, draw_x, draw_y, visible_bbox)` anchored cleanly at `(slot_cx, slot_fy)`."""
        walk_fx, walk_fy = walk_feet_point(self.sprite_px)
        act_info = panda.get("actions", {}).get(action_name) if action_name else None
        if act_info and act_info.get("frames"):
            frames = act_info["frames"]
            idx = int(frame_idx) % len(frames)
            photo = frames[idx]
            anchor = act_info.get("anchor")
            if anchor is not None:
                draw_x = int(round(slot_cx - anchor[0]))
                draw_y = int(round(slot_fy - anchor[1]))
            else:
                dx, dy = act_info.get("offset", (0, 0))
                draw_x = int(round(slot_cx - walk_fx + dx))
                draw_y = int(round(slot_fy - walk_fy + dy))
            fw = photo.width() if hasattr(photo, "width") else panda["pw"]
            fh = photo.height() if hasattr(photo, "height") else panda["ph"]
            bboxes = act_info.get("alpha_bboxes")
            bb = bboxes[idx] if bboxes and idx < len(bboxes) else None
            if bb is not None:
                vis_box = (draw_x + bb[0], draw_y + bb[1], draw_x + bb[2], draw_y + bb[3])
            else:
                vis_box = (draw_x, draw_y, draw_x + fw, draw_y + fh)
            return photo, draw_x, draw_y, vis_box

        fallback = panda.get("cheer") or panda.get("walk")
        photo = fallback[int(frame_idx) % len(fallback)]
        draw_x = int(round(slot_cx - walk_fx))
        draw_y = int(round(slot_fy - walk_fy))
        return photo, draw_x, draw_y, (draw_x, draw_y, draw_x + panda["pw"], draw_y + panda["ph"])

    def _dome_top_safe_y(self) -> int:
        """Top vertical boundary below Standby exit hints and any centered clock card."""
        k = self.k
        top_safe = int(round(self.hint_bottom + 14 * k))
        if (
            not getattr(self, "pure_view", False)
            and getattr(self, "clock_position", "top-left") != "hidden"
        ):
            card_cx = getattr(self, "card_cx", self.cx)
            card_cy = getattr(self, "cy", 0)
            card_w = getattr(self, "card_w", 0)
            card_h = getattr(self, "card_h", 0)
            if abs(card_cx - self.cx) < (card_w // 2 + round(280 * k)) and card_cy < self.sh * 0.45:
                top_safe = max(top_safe, int(round(card_cy + card_h / 2.0 + 14 * k)))
        return top_safe

    def _fortune_student_pending(self, eunji: dict) -> bool:
        """True while the braided student (drawn from Eunji's actions) is still loading."""
        if FORTUNE_STUDENT_ACTION in eunji.get("actions", {}):
            return False
        if FORTUNE_STUDENT_ACTION in getattr(self, "_unloadable", {}).get(eunji["key"], ()):
            return False
        return eunji["key"] in getattr(self, "_action_queue", ())

    def _set_member_shown(self, panda: dict, shown: bool) -> None:
        """Show/hide one member's sprite and name tag (a stage hides an actor until her costume loads)."""
        if bool(panda.get("_hidden")) != (not shown):
            panda["_hidden"] = not shown
            state = "normal" if shown else "hidden"
            for key in ("img_item", "tag_item", "tag_shadow"):
                item = panda.get(key)
                if item is not None:
                    try:
                        self.canvas.itemconfigure(item, state=state)
                    except tk.TclError:
                        pass

    def _place_dome_member(
        self,
        panda: dict,
        photo,
        draw_x: int,
        draw_y: int,
        slot_cx: int,
        slot_fy: int,
    ) -> None:
        placed = panda.get("_dome_placed")
        where = (panda["img_item"], draw_x, draw_y, slot_cx, slot_fy)
        if placed is not None and placed[0] is photo and placed[1:] == where:
            return    # same frame at the same spot: skip the canvas round-trips
        panda["_dome_placed"] = (photo, *where)
        self._set_member_shown(panda, True)
        self.canvas.coords(panda["img_item"], draw_x, draw_y)
        self.canvas.itemconfigure(panda["img_item"], image=photo)
        if "tag_item" in panda:
            tag_y = min(self.sh - round(12 * self.k), slot_fy + round(10 * self.k))
            self.canvas.coords(panda["tag_shadow"], slot_cx + 1, tag_y + 1)
            self.canvas.coords(panda["tag_item"], slot_cx, tag_y)

    def _fit_dome_scene_actions_to_width(self) -> None:
        """Downscale active Dome/Fortune stage actions on narrow screens so figures fit without overlap."""
        if self.scene not in STAGE_SCENES:
            return
        library = getattr(self, "_library", None)
        registry = getattr(library, "registry", None) if library is not None else None
        if library is None or registry is None:
            return

        member_action_lists: list[tuple[dict, list[tuple[str, dict]]]] = []
        vis_widths: list[int] = []
        student_extra_w = 0
        for p in self.pandas:
            actions_map = p.get("actions", {})
            if self.scene == DOME_BASEBALL_SCENE:
                act_names = (DOME_BASEBALL_ACTION,)
            elif self.scene == DOME_EUNJI_SCENE:
                act_names = resolved_eunji_dome_outfits(actions_map) if p["key"] == "eunji" else (DOME_FLANK_CHEER_ACTION,)
            elif p["key"] == "eunji":
                act_names = tuple(a for a in (FORTUNE_READER_ACTION, FORTUNE_STUDENT_ACTION) if a in actions_map)
            else:
                act_names = (DOME_FLANK_CHEER_ACTION,)

            loaded: list[tuple[str, dict]] = []
            max_vis_w = 0
            for name in act_names:
                info = actions_map.get(name)
                if not info or not info.get("frames"):
                    continue
                bboxes = [b for b in (info.get("alpha_bboxes") or ()) if b is not None]
                fw = info.setdefault("_natural_width", max((b[2] - b[0] for b in bboxes),
                                                          default=info["frames"][0].width()))
                if self.scene == FORTUNE_ROOM_SCENE and name == FORTUNE_STUDENT_ACTION:
                    student_extra_w = max(48, int(fw))
                else:
                    max_vis_w = max(max_vis_w, int(fw))
                loaded.append((name, info))
            if not loaded:
                return
            member_action_lists.append((p, loaded))
            vis_widths.append(max(48, max_vis_w))

        if len(member_action_lists) < len(self.pandas):
            return
        if student_extra_w > 0:
            vis_widths.append(student_extra_w)

        fit_cache = getattr(self, "_dome_scene_fit_cache", None)
        if fit_cache is None:
            fit_cache = {}
            self._dome_scene_fit_cache = fit_cache
        # Progressive wardrobes can reveal a wider later pose. Fit from natural
        # source widths, never from a previously shrunk PhotoImage, so scene
        # changes and additional outfits cannot compound the scale.
        scene_key = (self.scene, self.sw, tuple(vis_widths))
        if scene_key in fit_cache:
            fit = fit_cache[scene_key]
        else:
            margin = max(16.0, 24.0 * self.k)
            if self.scene == DOME_BASEBALL_SCENE:
                min_gap = max(12.0, 18.0 * self.k)
                avail = max(160.0, self.sw - 2.0 * margin - max(0, len(vis_widths) - 1) * min_gap)
            elif self.scene == FORTUNE_ROOM_SCENE:
                corridor_w = max(140.0 * self.k, self.sw * 0.22)
                pair_gap = max(8.0, 14.0 * self.k)
                avail = max(160.0, self.sw - 2.0 * margin - corridor_w - max(0, len(vis_widths) - 2) * pair_gap)
            else:
                flank_gap = max(12.0, 16.0 * self.k)
                corridor_gap = max(14.0, 20.0 * self.k)
                avail = max(160.0, self.sw - 2.0 * margin - 2.0 * flank_gap - 2.0 * corridor_gap)
            total_w = float(sum(vis_widths))
            fit = 1.0 if total_w <= avail else max(0.35, min(1.0, (avail / total_w) * 0.92))
            fit_cache[scene_key] = fit

        walk_fx, walk_fy = walk_feet_point(library.display_px)
        fit_key = (scene_key, round(fit, 9))
        for p, loaded in member_action_lists:
            base_scale = self._member_scale(library, p["key"])
            for name, info in loaded:
                if info.get("_dome_fit_key") == fit_key:
                    continue
                if fit < 0.999 or info.get("_dome_fit_key") is not None:
                    spec = registry.resolve(p["key"], name)
                    if spec is not None and spec.action == name:
                        prepared = self._prepared_action(library, spec, base_scale * fit)
                        if prepared is not None:
                            images, (fx, fy) = prepared
                            info["frames"] = LazyPhotoList(images, self.win)
                            info["alpha_bboxes"] = tuple(
                                im.getchannel("A").getbbox() if getattr(im, "mode", None) == "RGBA" else None
                                for im in images
                            )
                            info["anchor"] = (fx, fy)
                            info["offset"] = (walk_fx - fx, walk_fy - fy)
                info["_dome_fit_key"] = fit_key

    def _animate_dome_scene(self, *, reschedule: bool = True) -> None:
        if not self.running or not getattr(self, "pandas", None):
            return
        state = getattr(self, "_dome_state", None)
        if state is None:
            state = {"t0": time.monotonic()}
            self._dome_state = state
        elapsed_ms = max(0.0, (time.monotonic() - state["t0"]) * 1000.0)

        self._fit_dome_scene_actions_to_width()

        member_sizes: dict[str, tuple[int, int]] = {}
        eunji_panda = None
        for p in self.pandas:
            target_act = DOME_BASEBALL_ACTION
            if self.scene == DOME_EUNJI_SCENE:
                if p["key"] == "eunji":
                    outfits = resolved_eunji_dome_outfits(p.get("actions", {}))
                    target_act = outfits[0] if outfits else None
                else:
                    target_act = DOME_FLANK_CHEER_ACTION
            elif self.scene == FORTUNE_ROOM_SCENE:
                if p["key"] == "eunji":
                    eunji_panda = p
                    target_act = FORTUNE_READER_ACTION
                else:
                    target_act = DOME_FLANK_CHEER_ACTION
            info = p.get("actions", {}).get(target_act) if target_act else None
            if info and info.get("frames"):
                f0 = info["frames"][0]
                fw, fh = f0.width(), f0.height()
                stage_actors = len(self.pandas) + (1 if self.scene == FORTUNE_ROOM_SCENE else 0)
                if self.scene in STAGE_SCENES and (
                    self.scene == FORTUNE_ROOM_SCENE or fw * stage_actors > self.sw - round(64 * self.k)
                ):
                    bboxes = [b for b in (info.get("alpha_bboxes") or ()) if b is not None]
                    if bboxes:
                        fw = max(48, max(b[2] - b[0] for b in bboxes) + max(4, round(6 * self.k)))
                member_sizes[p["key"]] = (fw, fh)
            else:
                member_sizes[p["key"]] = (p["pw"], p["ph"])

        if self.scene == FORTUNE_ROOM_SCENE:
            student_info = (eunji_panda.get("actions", {}).get(FORTUNE_STUDENT_ACTION) if eunji_panda else None)
            has_student = bool(student_info and student_info.get("frames"))
            if has_student:
                bboxes = [b for b in (student_info.get("alpha_bboxes") or ()) if b is not None]
                sf0 = student_info["frames"][0]
                sfw = max(48, max((b[2] - b[0] for b in bboxes), default=sf0.width()) + max(4, round(6 * self.k)))
                member_sizes["student"] = (sfw, sf0.height())
            slots = compute_fortune_standby_slots(
                self.sw, self.sh, member_sizes, include_student=has_student, ui_scale_factor=self.k
            )
            eunji_item = None
            # 2026-11-22: the reader's costume loads a few ticks after the room opens.
            # Drawing the cheer fallback meant a plain capped Eunji sat at the table
            # first, then turned into the long-haired reader; she now waits unseen —
            # and the other four wait with her so the whole room appears at once.
            reader_info = eunji_panda.get("actions", {}).get(FORTUNE_READER_ACTION) if eunji_panda else None
            ready = eunji_panda is None or (bool(reader_info and reader_info.get("frames"))
                                            and not self._fortune_student_pending(eunji_panda))
            for idx, p in enumerate(self.pandas):
                if not p.get("walk"):
                    continue
                key = p["key"]
                cx, fy = slots.get(key, (self.cx, self.sh - round(32 * self.k)))
                act_key = FORTUNE_READER_ACTION if key == "eunji" else DOME_FLANK_CHEER_ACTION
                act_info = p.get("actions", {}).get(act_key)
                self._set_member_shown(p, ready)
                if not ready:
                    continue
                if key == "eunji" and act_info and act_info.get("frame_ms"):
                    step_ms = max(40.0, float(act_info["frame_ms"]))
                    step = int(elapsed_ms // step_ms)
                else:
                    step = int(elapsed_ms // PANDA_TICK_MS) + idx
                photo, dx, dy, _ = self._dome_action_draw_spec(p, act_key, step, cx, fy)
                self._place_dome_member(p, photo, dx, dy, cx, fy)
                if key == "eunji":
                    eunji_item = p["img_item"]
            if has_student and eunji_panda is not None:
                scx, sfy = slots["student"]
                student_ms = max(40.0, float(student_info.get("frame_ms", PANDA_TICK_MS)))
                sphoto, sdx, sdy, _ = self._dome_action_draw_spec(
                    eunji_panda, FORTUNE_STUDENT_ACTION, int(elapsed_ms // student_ms), scx, sfy
                )
                if getattr(self, "_fortune_student_item", None) is None:
                    self._fortune_student_item = self.canvas.create_image(
                        sdx, sdy, anchor="nw", image=sphoto, tags=("fortune_stage", "panda"),
                    )
                    try:
                        self.canvas.tag_raise("ui")
                    except tk.TclError:
                        pass
                else:
                    self.canvas.coords(self._fortune_student_item, sdx, sdy)
                    self.canvas.itemconfigure(self._fortune_student_item, image=sphoto)
            if eunji_item is not None:
                try:
                    self.canvas.tag_raise(eunji_item)
                except tk.TclError:
                    pass
            if reschedule:
                self._later("pandas", PANDA_TICK_MS, self.animate_pandas)
            return

        if self.scene == DOME_BASEBALL_SCENE:
            frame_idx, _dur_ms, bubble_scale = dome_baseball_step(elapsed_ms)
            slots = dome_baseball_standby_slots(
                self.sw, self.sh, member_sizes, ui_scale_factor=self.k
            )
            vis_boxes: list[tuple[int, int, int, int]] = []
            for p in self.pandas:
                if not p.get("walk"):
                    continue
                cx, fy = slots.get(p["key"], (self.cx, self.sh - round(32 * self.k)))
                photo, dx, dy, v_box = self._dome_action_draw_spec(
                    p, DOME_BASEBALL_ACTION, frame_idx, cx, fy
                )
                self._place_dome_member(p, photo, dx, dy, cx, fy)
                # All four frames' outline: a raised arm must not shove the banner up and down.
                union = _union_alpha_bbox(p.get("actions", {}).get(DOME_BASEBALL_ACTION))
                vis_boxes.append((dx + union[0], dy + union[1], dx + union[2], dy + union[3])
                                 if union is not None else v_box)

            top_safe = self._dome_top_safe_y()
            gap = max(14, round(18 * self.k))
            side_margin = max(14, round(18 * self.k))
            max_bw, max_bh = available_dome_bubble_space(
                vis_boxes, (0, 0, self.sw, self.sh),
                gap=gap, top_safe_y=top_safe, side_margin=side_margin,
            )
            cache_key = (frame_idx, self.lang, round(self.k, 2), max_bw, max_bh)
            if self._dome_bubble_cache_key != cache_key or self._dome_bubble_photo is None:
                pil_bub = render_dome_bubble_pil(
                    frame_idx,
                    self.lang,
                    dpi_scale=self.k,
                    anim_scale=bubble_scale,
                    max_width=min(round(560 * self.k), max_bw),
                    max_height=max_bh,
                    binary_alpha=False,
                )
                self._dome_bubble_pil = pil_bub
                self._dome_bubble_size = (pil_bub.width, pil_bub.height)
                self._dome_bubble_photo = ImageTk.PhotoImage(pil_bub, master=self.win)
                self._dome_bubble_cache_key = cache_key

            bx, by, bw_rect, bh_rect = compute_dome_bubble_rect(
                vis_boxes,
                self._dome_bubble_size,
                (0, 0, self.sw, self.sh),
                gap=gap,
                top_safe_y=top_safe,
                side_margin=side_margin,
            )
            if (bw_rect, bh_rect) != self._dome_bubble_size and getattr(self, "_dome_bubble_pil", None) is not None:
                resized = self._dome_bubble_pil.resize((bw_rect, bh_rect), Image.LANCZOS)
                self._dome_bubble_size = (bw_rect, bh_rect)
                self._dome_bubble_photo = ImageTk.PhotoImage(resized, master=self.win)
            if self._dome_bubble_item is None:
                self._dome_bubble_item = self.canvas.create_image(
                    bx, by, anchor="nw", image=self._dome_bubble_photo,
                    tags=("dome_stage", "dome_bubble"),
                )
                self._dome_bubble_placed = (self._dome_bubble_photo, bx, by)
            else:
                placed = getattr(self, "_dome_bubble_placed", None)
                if placed is None or placed[0] is not self._dome_bubble_photo or placed[1:] != (bx, by):
                    self.canvas.coords(self._dome_bubble_item, bx, by)
                    self.canvas.itemconfigure(self._dome_bubble_item, image=self._dome_bubble_photo)
                    self._dome_bubble_placed = (self._dome_bubble_photo, bx, by)

            if reschedule:
                self._later("pandas", 75, self.animate_pandas)
            return

        if self.scene == DOME_EUNJI_SCENE:
            slots = eunji_dome_standby_slots(
                self.sw, self.sh, member_sizes, ui_scale_factor=self.k
            )
            eunji_item = None
            for idx, p in enumerate(self.pandas):
                if not p.get("walk"):
                    continue
                key = p["key"]
                cx, fy = slots.get(key, (self.cx, self.sh - round(32 * self.k)))
                if key == "eunji":
                    approved = resolved_eunji_dome_outfits(p.get("actions", {}))
                    if approved:
                        outfit, f_idx = dome_concert_step(elapsed_ms, approved)
                    else:
                        outfit, f_idx = None, int(elapsed_ms // PANDA_TICK_MS)
                    photo, dx, dy, _ = self._dome_action_draw_spec(p, outfit, f_idx, cx, fy)
                    self._place_dome_member(p, photo, dx, dy, cx, fy)
                    eunji_item = p["img_item"]
                else:
                    flank_step = int(elapsed_ms // PANDA_TICK_MS) + idx
                    photo, dx, dy, _ = self._dome_action_draw_spec(
                        p, DOME_FLANK_CHEER_ACTION, flank_step, cx, fy
                    )
                    self._place_dome_member(p, photo, dx, dy, cx, fy)
            if eunji_item is not None:
                try:
                    self.canvas.tag_raise(eunji_item)
                except tk.TclError:
                    pass
            if reschedule:
                self._later("pandas", PANDA_TICK_MS, self.animate_pandas)

    def scene_label(self) -> str:
        wallpaper = self.wallpapers.get(self.scene)
        return wallpaper.label(self.lang) if wallpaper else t(f"scene_{self.scene}", self.lang)

    def _draw_wallpaper(self, spec: WallpaperSpec) -> tuple[str, str]:
        """Image backdrop filling the screen; decoded once per overlay and kept for re-use."""
        photo = self._wallpaper_cache.pop(spec.key, None)
        if photo is not None:
            self._wallpaper_cache[spec.key] = photo          # most recent last
        else:
            try:
                photo = ImageTk.PhotoImage(_fitted_wallpaper(spec.path, self.sw, self.sh), master=self.win)
            except (OSError, ValueError):
                log.exception("standby wallpaper %s cannot be shown; drawing the starfield", spec.key)
                return self._draw_starfield()
            self._wallpaper_cache[spec.key] = photo
            _trim_photo_cache(self._wallpaper_cache)
        image_item = self.canvas.create_image(0, 0, anchor="nw", image=photo, tags=("bg",))
        self._wallpaper_fx(spec.key, image_item)
        # Photos can be bright anywhere: the top hints get a dark backing to stay readable.
        k = self.k
        scene_hint = t("standby_scene_hint", self.lang, scene=spec.label(self.lang))
        half = max(self.f_hint.measure(self.canvas.itemcget(self.hint_item, "text")),
                   self.f_hint2.measure(scene_hint)) // 2 + round(18 * k)
        _draw_round_rect(self.canvas, self.cx - half, round(4 * k), self.cx + half,
                         self.hint_bottom + round(6 * k), r=12 * k, fill="#141826", outline="",
                         tags=("bg", "standby_hint_ui"))
        self._scene_state.update(hint_lo="#8a93a8")
        return "#0a0c16", "#e2e8f0"

    def _wallpaper_fx(self, key: str, image_item: int) -> None:
        """Soft particles over a photo backdrop: a few dozen canvas ovals, under the clock and pandas.

        Regions are fractions of the picture (cover-cropped like the photo), so the snow stays in
        the cabin window on any screen shape. The beach and the moon terrace already paint their
        string lights / lanterns, so they get nothing that would double them.
        """
        fx = WALLPAPER_FX.get(key)
        if fx is None:
            return
        kind, (fx0, fy0, fx1, fy1), count, colours = fx
        scale = max(self.sw / WALLPAPER_SRC[0], self.sh / WALLPAPER_SRC[1])
        ox, oy = (WALLPAPER_SRC[0] * scale - self.sw) / 2, (WALLPAPER_SRC[1] * scale - self.sh) / 2
        x0, y0 = fx0 * WALLPAPER_SRC[0] * scale - ox, fy0 * WALLPAPER_SRC[1] * scale - oy
        x1, y1 = fx1 * WALLPAPER_SRC[0] * scale - ox, fy1 * WALLPAPER_SRC[1] * scale - oy
        parts = []
        for _ in range(count):
            if kind == "twinkle":
                r = self.rng.uniform(1.0, 2.1) * self.k
            else:
                r = self.rng.uniform(1.6, 3.6) * self.k * (1.6 if kind == "fall" else 1.0)
            p = {"x": self.rng.uniform(x0, x1), "y": self.rng.uniform(y0, y1), "r": r,
                 "vy": self.rng.uniform(0.6, 1.6) * self.k, "ph": self.rng.uniform(0, 6.28),
                 "col": self.rng.choice(colours)}
            w = r * (1.6 if kind == "fall" else 1.0)
            p["item"] = self.canvas.create_oval(p["x"] - w, p["y"] - r, p["x"] + w, p["y"] + r,
                                                fill=p["col"], outline="", tags=("bg", "wall_fx"))
            parts.append(p)
        self.canvas.tag_lower("wall_fx")
        self.canvas.tag_lower(image_item)

        def tick() -> None:
            if self._tick_n % 2:
                return
            for p in parts:
                if kind == "twinkle":
                    on = math.sin(self._tick_n * 0.12 + p["ph"]) > -0.2
                    self.canvas.itemconfigure(p["item"], state="normal" if on else "hidden")
                    continue
                p["y"] += p["vy"] * 2
                p["x"] += math.sin(self._tick_n * 0.1 + p["ph"]) * 0.8 * self.k
                if p["y"] > y1:
                    p["y"], p["x"] = y0, self.rng.uniform(x0, x1)
                r = p["r"]; w = r * (1.6 if kind == "fall" else 1.0)
                self.canvas.coords(p["item"], p["x"] - w, p["y"] - r, p["x"] + w, p["y"] + r)
        self._scene_tick_fn = tick

    def _apply_clock_theme(self) -> None:
        theme = get_standby_clock_theme(self.scene, self.char_key)
        try:
            self.f_clock.configure(family=theme["family"])
        except Exception:
            pass
        if hasattr(self, "clock_item"):
            self.canvas.itemconfigure(self.clock_item, fill=theme["clock_color"])
        if hasattr(self, "date_item"):
            self.canvas.itemconfigure(self.date_item, fill=theme["date_color"])
        if hasattr(self, "badge_item"):
            self.canvas.itemconfigure(self.badge_item, fill=theme["badge_color"])

    def _scene_tick(self) -> None:
        if not self.running:
            return
        self._tick_n += 1
        if self._scene_tick_fn is not None:
            try:
                self._scene_tick_fn()
            except tk.TclError:
                pass
        self._later("scene", SCENE_TICK_MS, self._scene_tick)

    def _restart_hint_fade(self) -> None:
        hi, lo = "#c3cad8", self._scene_state.get("hint_lo", "#3c4258")
        self.canvas.itemconfigure(self.scene_hint_item, fill=hi)
        steps = [_mix(hi, lo, k / 12) for k in range(1, 13)]

        def step(i: int = 0) -> None:
            if not self.running or i >= len(steps):
                return
            self.canvas.itemconfigure(self.scene_hint_item, fill=steps[i])
            self._later("hint", 120, lambda: step(i + 1))

        self._later("hint", 3500, step)

    # -- helpers ---------------------------------------------------------
    def _rect(self, x1, y1, x2, y2, fill, **kw) -> int:
        return self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=kw.pop("outline", ""), tags=("bg",), **kw)

    def _oval(self, x1, y1, x2, y2, fill, **kw) -> int:
        return self.canvas.create_oval(x1, y1, x2, y2, fill=fill, outline=kw.pop("outline", ""), tags=("bg",), **kw)

    def _poly(self, pts, fill, **kw) -> int:
        return self.canvas.create_polygon(*pts, fill=fill, outline=kw.pop("outline", ""), tags=("bg",), **kw)

    def _line(self, *pts, fill, width=1, **kw) -> int:
        return self.canvas.create_line(*pts, fill=fill, width=width, tags=("bg",), **kw)

    def _gradient(self, x1, y1, x2, y2, top, bottom, bands: int = 12) -> None:
        h = (y2 - y1) / bands
        for b in range(bands):
            self._rect(x1, y1 + b * h, x2, y1 + (b + 1) * h + 1, _mix(top, bottom, b / max(1, bands - 1)))

    def _glow_rings(self, x, y, rx, ry, base, hot, n: int = 4, strength: float = 1.0) -> list[tuple[int, float]]:
        rings = []
        for k in range(n):
            f = 1 - k / n
            t = (0.08 + 0.32 * (k / max(1, n - 1))) * strength
            item = self._oval(x - rx * f, y - ry * f, x + rx * f, y + ry * f, _mix(base, hot, t))
            rings.append((item, t))
        return rings

    def _flicker_rings(self, rings, base, hot) -> None:
        k = self.rng.uniform(0.82, 1.12)
        for item, t in rings:
            self.canvas.itemconfigure(item, fill=_mix(base, hot, t * k))

    def _make_fire(self, x, base, w, h) -> dict:
        logs = [
            self._line(x - w * 0.75, base + 4, x + w * 0.75, base - 8, fill="#4e342e", width=max(6, w // 7), capstyle="round"),
            self._line(x - w * 0.75, base - 8, x + w * 0.75, base + 4, fill="#3e2723", width=max(6, w // 7), capstyle="round"),
        ]
        flames = [
            (self._poly(_flame_pts(x, base, w, h, self.rng, 4), "#ff6d00", smooth=True), 1.0, 1.0),
            (self._poly(_flame_pts(x, base, w * 0.68, h * 0.72, self.rng, 3), "#ffab00", smooth=True), 0.68, 0.72),
            (self._poly(_flame_pts(x, base, w * 0.36, h * 0.42, self.rng, 2), "#fff3b0", smooth=True), 0.36, 0.42),
        ]
        return {"x": x, "base": base, "w": w, "h": h, "flames": flames, "logs": logs}

    def _flicker_fire(self, fire: dict) -> None:
        for item, fw, fh in fire["flames"]:
            self.canvas.coords(
                item, *_flame_pts(fire["x"], fire["base"], fire["w"] * fw, fire["h"] * fh, self.rng, 3 + 2 * fw)
            )

    # -- starfield -------------------------------------------------------
    def _draw_starfield(self) -> tuple[str, str]:
        stars = []
        star_chars = ["✦", "★", "•", "·", "✧"]
        star_colors = ["#f8bbd0", "#ffffff", "#fce4ec", "#e1bee7", "#fff9c4"]
        for _ in range(38):
            sx = self.rng.randint(30, self.sw - 30)
            sy = self.rng.randint(30, self.sh - 120)
            col = self.rng.choice(star_colors)
            item = self.canvas.create_text(
                sx, sy, text=self.rng.choice(star_chars), fill=col,
                font=("Segoe UI Symbol", self.rng.choice([9, 11, 14, 18])), tags=("bg",),
            )
            stars.append((item, col))
        self._scene_state.update(stars=stars, hint_lo="#3a3f55", dim=None)

        def tick() -> None:
            # Gentle twinkle: one star at a time dims for ~0.4 s (2.5 updates/s).
            if self._tick_n % 4:
                return
            st = self._scene_state
            if st["dim"] is not None:
                item, col = st["dim"]
                self.canvas.itemconfigure(item, fill=col)
                st["dim"] = None
            else:
                item, col = self.rng.choice(st["stars"])
                self.canvas.itemconfigure(item, fill=_mix(col, "#0a0c16", 0.7))
                st["dim"] = (item, col)

        self._scene_tick_fn = tick
        return "#0a0c16", "#718096"

    # -- campfire --------------------------------------------------------
    def _draw_campfire(self) -> tuple[str, str]:
        sw, sh = self.sw, self.sh
        horizon = self.floor_y - 52   # scenery sits just above the parade's heads
        sky_top, sky_bot = "#05071a", "#251c3f"
        ground = "#0c0e18"
        self._gradient(0, 0, sw, horizon, sky_top, sky_bot, bands=16)

        # Tiny stars in the upper sky
        twinkles = []
        for _ in range(40):
            x = self.rng.randint(10, sw - 10)
            y = self.rng.randint(10, int(horizon * 0.6))
            r = self.rng.choice((1, 1, 1.5, 2))
            col = self.rng.choice(("#cfd8ff", "#ffffff", "#fff3c4"))
            twinkles.append((self._oval(x - r, y - r, x + r, y + r, col), col))

        # Moon with halo (crescent cut with the local sky colour)
        mx = (self.side_r[0] + self.side_r[1]) / 2
        my = sh * 0.14
        mr = max(26, min(42, sh * 0.04))
        sky_at = _mix(sky_top, sky_bot, my / horizon)
        for k, t in ((2.4, 0.035), (1.8, 0.07), (1.35, 0.12)):
            self._oval(mx - mr * k, my - mr * k, mx + mr * k, my + mr * k, _mix(sky_at, "#fff6d5", t))
        self._oval(mx - mr, my - mr, mx + mr, my + mr, "#fff6d5")
        self._oval(mx - mr * 0.55, my - mr * 1.05, mx + mr * 1.45, my + mr * 0.85, _mix(sky_at, "#fff6d5", 0.12))

        # Far and near hills, pine silhouettes
        far = [0, horizon]
        for i in range(0, 9):
            far += [sw * i / 8, horizon - sh * (0.08 + 0.06 * math.sin(i * 1.7 + 0.5))]
        far += [sw, horizon]
        self._poly(far, "#141633", smooth=True)
        for i in range(26):
            tx = sw * (i + self.rng.random() * 0.6) / 26
            th = sh * self.rng.uniform(0.07, 0.13)
            tw = th * 0.42
            base_y = horizon + 4
            self._poly([tx - tw / 2, base_y, tx, base_y - th, tx + tw / 2, base_y], "#0b0d22")
        self._rect(0, horizon, sw, sh, ground)

        # Firelight glow on the ground
        fx = (self.side_r[0] + self.side_r[1]) / 2
        fy = horizon + 14
        side = self.side_r[1] - self.side_r[0]
        rings = self._glow_rings(fx, fy, side * 0.62, 56, ground, "#ff8f3c")

        # Tent (left), lit from the fire on its right face
        tl0, tl1 = self.side_l
        tent_w = min((tl1 - tl0) * 0.8, 300)
        tent_h = tent_w * 0.7
        tx0 = tl0 + ((tl1 - tl0) - tent_w) / 2
        tb = horizon + 12
        apex = (tx0 + tent_w / 2, tb - tent_h)
        self._oval(tx0 - 20, tb - 10, tx0 + tent_w + 20, tb + 14, "#07080f")
        self._poly([tx0, tb, *apex, apex[0], tb], "#221d3a")
        self._poly([apex[0], tb, *apex, tx0 + tent_w, tb], "#4a3348")
        door = [apex[0] - tent_w * 0.17, tb, apex[0], tb - tent_h * 0.62, apex[0] + tent_w * 0.17, tb]
        self._poly(door, "#120d1c")
        self._poly([apex[0], tb, apex[0], tb - tent_h * 0.62, apex[0] + tent_w * 0.17, tb], "#5c3a2c")
        self._line(apex[0], apex[1], apex[0] - 10, apex[1] - 16, fill="#2a2440", width=3)
        self._line(apex[0], apex[1], apex[0] + 10, apex[1] - 16, fill="#6b4a4a", width=3)
        self._line(tx0, tb, tx0 - 22, tb + 6, fill="#2a2440", width=2)
        self._line(tx0 + tent_w, tb, tx0 + tent_w + 22, tb + 6, fill="#6b4a4a", width=2)

        # Stones + fire
        fw = min(side * 0.27, 96)
        fh = fw * 1.55
        for k in range(7):
            a = math.pi * (0.05 + 0.9 * k / 6)
            sx = fx - math.cos(a) * fw * 0.95
            sy = fy + 6 + math.sin(a) * 6
            self._oval(sx - 10, sy - 7, sx + 10, sy + 7, "#3b3a46")
        fire = self._make_fire(fx, fy, fw, fh)

        embers = []
        for _ in range(MAX_EMBERS):
            item = self._oval(fx, fy, fx, fy, "#ffb74d")
            embers.append({"item": item, "life": 0})

        self._scene_state.update(
            rings=rings, fire=fire, embers=embers, twinkles=twinkles,
            ground=ground, hint_lo="#3f3a58",
        )

        # Tk redraws the bounding box of everything changed between two idle
        # redraws, so far-apart updates (sky twinkle vs. fire) use different ticks.
        def tick() -> None:
            st = self._scene_state
            if self._tick_n % 6 == 0:
                item, col = self.rng.choice(st["twinkles"])
                self.canvas.itemconfigure(item, fill=self.rng.choice((col, "#6f7aa8")))
                return
            self._flicker_fire(st["fire"])
            if self._tick_n % 2:
                self._flicker_rings(st["rings"], st["ground"], "#ff8f3c")
            f = st["fire"]
            for e in st["embers"]:
                if e["life"] <= 0:
                    if self.rng.random() < 0.18:
                        e.update(
                            x=f["x"] + self.rng.uniform(-f["w"] * 0.3, f["w"] * 0.3),
                            y=f["base"] - f["h"] * 0.5,
                            vx=self.rng.uniform(-0.8, 0.8), vy=self.rng.uniform(-4.5, -2.5),
                            life=self.rng.randint(14, 26), max=26,
                        )
                    else:
                        continue
                e["life"] -= 1
                if e["life"] <= 0:  # park once, near the fire (keeps the redraw box local)
                    self.canvas.coords(e["item"], f["x"], f["base"], f["x"], f["base"])
                    continue
                e["x"] += e["vx"] + math.sin((self._tick_n + e["life"]) * 0.4) * 0.6
                e["y"] += e["vy"]
                r = 1.2 + 1.3 * e["life"] / e["max"]
                self.canvas.coords(e["item"], e["x"] - r, e["y"] - r, e["x"] + r, e["y"] + r)
                self.canvas.itemconfigure(e["item"], fill=_mix("#3a2a3a", "#ffcc66", e["life"] / e["max"]))

        self._scene_tick_fn = tick
        return ground, "#8a8fae"

    # -- christmas -------------------------------------------------------
    def _draw_christmas(self) -> tuple[str, str]:
        sw, sh = self.sw, self.sh
        fy = self.floor_y
        wall, stripe = "#2c1b23", "#331f29"
        self._rect(0, 0, sw, fy, wall)
        for x in range(0, sw, 56):
            self._rect(x, 0, x + 18, fy, stripe)
        self._rect(0, fy - 16, sw, fy, "#1e1117")
        self._rect(0, fy - 18, sw, fy - 15, "#4a2d35")
        # Wooden floor
        self._rect(0, fy, sw, sh, "#4a2e1e")
        y, k = fy + 18, 0
        while y < sh:
            self._line(0, y, sw, y, fill="#3a2316", width=2)
            off = (k * 137) % 240
            for x in range(off, sw, 240):
                self._line(x, y - 18 if k else fy, x, y, fill="#3a2316", width=2)
            y += 18 + k * 3
            k += 1
        # Rug
        self._oval(self.cx - sw * 0.28, fy + 40, self.cx + sw * 0.28, sh + 60, "#5c1f2a", outline="#8a3a44", width=4)

        # --- Window with snow (left side, upper)
        l0, l1 = self.side_l
        lw = l1 - l0
        wx0, wx1 = l0 + lw * 0.14, l1 - lw * 0.14
        wy0, wy1 = sh * 0.10, sh * 0.44
        self._rect(wx0 - 14, wy0 - 14, wx1 + 14, wy1 + 14, "#1a0f14")
        self._gradient(wx0, wy0, wx1, wy1, "#0b1330", "#24375e", bands=8)
        # snowy hills outside
        self._poly([wx0, wy1, wx0, wy1 - 34, (wx0 + wx1) / 2, wy1 - 52, wx1, wy1 - 26, wx1, wy1], "#c9d6e6", smooth=True)
        for i in range(3):
            hx = wx0 + (wx1 - wx0) * (0.2 + 0.3 * i)
            hy = wy1 - 40 - (i % 2) * 8
            self._poly([hx - 9, hy, hx, hy - 30, hx + 9, hy], "#163a2a")
        flakes = []
        n_flakes = min(MAX_SNOW, 44)
        for _ in range(n_flakes):
            r = self.rng.choice((1.5, 2, 2.5, 3))
            x = self.rng.uniform(wx0, wx1)
            y = self.rng.uniform(wy0, wy1)
            item = self._oval(x - r, y - r, x + r, y + r, "#f4f8ff")
            flakes.append({"item": item, "x": x, "y": y, "r": r, "vy": 0.8 + r * 0.55, "ph": self.rng.random() * 6})
        # frame + muntins
        self.canvas.create_rectangle(wx0, wy0, wx1, wy1, outline="#e9dcc7", width=7, tags=("bg",))
        self._line((wx0 + wx1) / 2, wy0, (wx0 + wx1) / 2, wy1, fill="#e9dcc7", width=5)
        self._line(wx0, (wy0 + wy1) / 2, wx1, (wy0 + wy1) / 2, fill="#e9dcc7", width=5)
        self._rect(wx0 - 20, wy1 + 4, wx1 + 20, wy1 + 16, "#d8c7ad")
        # curtains
        cw = (wx1 - wx0) * 0.2
        self._poly([wx0 - 26, wy0 - 24, wx0 + cw, wy0 - 24, wx0 + cw * 0.3, (wy0 + wy1) / 2, wx0 + cw * 0.6, wy1 + 2, wx0 - 26, wy1 + 2], "#7a1f2b", smooth=True)
        self._poly([wx1 + 26, wy0 - 24, wx1 - cw, wy0 - 24, wx1 - cw * 0.3, (wy0 + wy1) / 2, wx1 - cw * 0.6, wy1 + 2, wx1 + 26, wy1 + 2], "#7a1f2b", smooth=True)
        self._rect(wx0 - 34, wy0 - 30, wx1 + 34, wy0 - 22, "#c9a66b")

        # --- Christmas tree (left, in front of the wall)
        tx = (l0 + l1) / 2
        tb = fy + 26
        th = max(sh * 0.22, min(sh * 0.40, tb - wy1 - 60))
        tw = min(lw * 0.85, th * 0.66)
        self._rect(tx - tw * 0.14, tb - 34, tx + tw * 0.14, tb, "#8e2b2b", outline="#b8423f", width=2)
        self._rect(tx - 8, tb - 52, tx + 8, tb - 30, "#5d4037")
        top = tb - th
        greens = ("#1b5e20", "#226b28", "#2e7d32")
        tiers = []
        for i, g in enumerate(greens):
            t0 = top + th * (0.0 + 0.24 * i)
            t1 = top + th * (0.42 + 0.2 * i) if i < 2 else tb - 50
            half = tw * (0.30 + 0.2 * i) / 1.0 / 2 * 1.6
            self._poly([tx - half, t1, tx, t0, tx + half, t1], g)
            tiers.append((t0, t1, half))
        # garlands + lights
        light_cols = ("#ff5252", "#ffd740", "#69f0ae", "#40c4ff", "#ff80ab")
        lights = []
        for i, (t0, t1, half) in enumerate(tiers):
            gy0 = t1 - (t1 - t0) * 0.55
            gx = half * 0.55
            self._line(tx - gx, gy0, tx, gy0 + 14, tx + gx * 1.15, gy0 + 4, fill="#e6c35c", width=2, smooth=True)
            n = 4 + i * 2
            for j in range(n):
                fx_ = (j + 0.5) / n
                lx = tx - half * 0.85 + fx_ * half * 1.7
                ly = t1 - 10 - abs(fx_ - 0.5) * 8
                item = self._oval(lx - 4, ly - 4, lx + 4, ly + 4, light_cols[(i + j) % len(light_cols)])
                lights.append((item, (i + j) % len(light_cols)))
        # star
        spts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            r = 18 if k % 2 == 0 else 7.5
            spts += [tx + r * math.cos(a), top - 4 + r * math.sin(a)]
        star = self._poly(spts, "#ffd54f", outline="#fff59d")
        # presents
        for dx, w, h, col, rib in ((-tw * 0.42, 44, 34, "#c62828", "#ffd54f"), (tw * 0.3, 38, 30, "#1565c0", "#ffffff"), (tw * 0.02, 30, 22, "#6a1b9a", "#ffd54f")):
            px0 = tx + dx - w / 2
            self._rect(px0, tb - h + 8, px0 + w, tb + 8, col)
            self._line(px0 + w / 2, tb - h + 8, px0 + w / 2, tb + 8, fill=rib, width=4)
            self._line(px0, tb - h / 2 + 8, px0 + w, tb - h / 2 + 8, fill=rib, width=4)

        # --- Fireplace (right)
        r0, r1 = self.side_r
        rw = r1 - r0
        fw = min(rw * 0.84, 330)
        fh = fw * 0.92
        fcx = (r0 + r1) / 2
        fb = fy + 6
        fx0, fx1, ftop = fcx - fw / 2, fcx + fw / 2, fb - fh
        wall_glow = self._glow_rings(fcx, fb - fh * 0.35, fw * 0.78, fh * 0.75, wall, "#ff9e4a", n=3, strength=0.45)
        floor_glow = self._glow_rings(fcx, fb + 30, fw * 0.9, 60, "#4a2e1e", "#ff9e4a", n=3)
        self._rect(fx0, ftop, fx1, fb, "#7a3f31")
        row_h = 18
        rr = 0
        yb = fb - row_h
        while yb > ftop + 4:
            self._line(fx0, yb, fx1, yb, fill="#5e2e24", width=2)
            off = 0 if rr % 2 else 22
            for x in range(int(fx0 + off), int(fx1), 44):
                self._line(x, yb, x, yb + row_h, fill="#5e2e24", width=2)
            yb -= row_h
            rr += 1
        self._rect(fx0 - 22, ftop - 18, fx1 + 22, ftop + 2, "#3e2723")
        self._rect(fx0 - 26, ftop - 24, fx1 + 26, ftop - 16, "#5d4037")
        ox0, ox1, oy0 = fcx - fw * 0.32, fcx + fw * 0.32, ftop + fh * 0.32
        self._poly(_round_rect_pts(ox0, oy0, ox1, fb + 30, r=fw * 0.22), "#120806", smooth=True)
        self._rect(ox0 - 3, fb - 6, ox1 + 3, fb + 6, "#2b1712")
        fire = self._make_fire(fcx, fb - 12, fw * 0.3, fh * 0.42)
        self._rect(fx0 - 10, fb - 2, fx1 + 10, fb + 10, "#2b1712")
        # stockings
        for i, col in enumerate(("#c62828", "#2e7d32", "#c62828")):
            sx = fx0 + fw * (0.22 + 0.28 * i)
            sy = ftop + 2
            self._line(sx, sy - 4, sx, sy + 8, fill="#e9dcc7", width=2)
            self._poly([sx - 12, sy + 16, sx + 12, sy + 16, sx + 12, sy + 52, sx + 24, sy + 60, sx + 24, sy + 72, sx - 4, sy + 72, sx - 12, sy + 60], col)
            self._rect(sx - 14, sy + 8, sx + 14, sy + 20, "#f5f5f5")
        # wreath above the mantel
        wcx, wcy = fcx, ftop - 24 - max(70, sh * 0.1)
        wr = max(34, min(54, fw * 0.17))
        self.canvas.create_oval(wcx - wr, wcy - wr, wcx + wr, wcy + wr, outline="#2e7d32", width=max(12, wr * 0.38), tags=("bg",))
        self.canvas.create_oval(wcx - wr, wcy - wr, wcx + wr, wcy + wr, outline="#1b5e20", width=3, dash=(6, 6), tags=("bg",))
        for k in range(8):
            a = k * math.pi / 4 + 0.3
            bx, by = wcx + wr * math.cos(a), wcy + wr * math.sin(a)
            self._oval(bx - 4, by - 4, bx + 4, by + 4, "#e53935")
        self._poly([wcx, wcy + wr, wcx - 18, wcy + wr - 12, wcx - 18, wcy + wr + 12], "#d32f2f")
        self._poly([wcx, wcy + wr, wcx + 18, wcy + wr - 12, wcx + 18, wcy + wr + 12], "#d32f2f")
        self._poly([wcx - 3, wcy + wr, wcx - 10, wcy + wr + 30, wcx, wcy + wr + 24, wcx + 10, wcy + wr + 30, wcx + 3, wcy + wr], "#b71c1c")

        self._scene_state.update(
            flakes=flakes, win=(wx0, wy0, wx1, wy1), lights=lights, light_cols=light_cols,
            star=star, fire=fire, wall_glow=wall_glow, floor_glow=floor_glow, wall=wall,
            hint_lo="#5a3f4c",
        )

        # Left side (snow, tree lights) and right side (fireplace) update on
        # alternate ticks so each Tk redraw only covers one side of the screen.
        def tick() -> None:
            st = self._scene_state
            if self._tick_n % 2:
                self._flicker_fire(st["fire"])
                if self._tick_n % 4 == 1:
                    self._flicker_rings(st["wall_glow"], st["wall"], "#ff9e4a")
                    self._flicker_rings(st["floor_glow"], "#4a2e1e", "#ff9e4a")
                return
            x0, y0, x1, y1 = st["win"]
            for fl in st["flakes"]:
                fl["y"] += fl["vy"] * 2
                fl["x"] += math.sin(self._tick_n * 0.15 + fl["ph"]) * 1.0
                if fl["y"] > y1 - 8:
                    fl["y"] = y0 + 2
                    fl["x"] = self.rng.uniform(x0 + 4, x1 - 4)
                fl["x"] = min(max(fl["x"], x0 + 4), x1 - 4)
                r = fl["r"]
                self.canvas.coords(fl["item"], fl["x"] - r, fl["y"] - r, fl["x"] + r, fl["y"] + r)
            if self._tick_n % 6 == 0:
                phase = self._tick_n // 6
                cols = st["light_cols"]
                for idx, (item, ci) in enumerate(st["lights"]):
                    on = (idx + phase) % 3 != 0
                    col = cols[(ci + phase) % len(cols)]
                    self.canvas.itemconfigure(item, fill=col if on else _mix(col, "#1b5e20", 0.7))
                self.canvas.itemconfigure(st["star"], fill="#ffe57f" if phase % 2 else "#ffc107")

        self._scene_tick_fn = tick
        return wall, "#b9a3ac"

    # -- practice room ---------------------------------------------------
    def _draw_practice_room(self) -> tuple[str, str]:
        sw, sh = self.sw, self.sh
        fy = self.floor_y
        wall = "#262b38"
        self._rect(0, 0, sw, fy, wall)
        ceil_h = sh * 0.06
        self._rect(0, 0, sw, ceil_h, "#171a22")
        n_lights = 4
        for i in range(n_lights):
            lx = sw * (i + 0.5) / n_lights
            self._glow_rings(lx, ceil_h, sw * 0.08, sh * 0.05, wall, "#fff1d0", n=3, strength=0.45)
            self._rect(lx - sw * 0.05, ceil_h - 8, lx + sw * 0.05, ceil_h - 2, "#fff6e0")

        # Mirror wall
        mx0, mx1 = sw * 0.025, sw * 0.975
        my0, my1 = ceil_h + sh * 0.04, fy - 8
        self._gradient(mx0, my0, mx1, my1, "#3d4a66", "#2b3449", bands=10)
        refl_y = my1 - sh * 0.11
        self._gradient(mx0, refl_y, mx1, my1, "#3a3440", "#4a3a34", bands=4)  # reflected floor
        shines = []
        shine_col = _mix("#34405a", "#ffffff", 0.12)
        sw_w = sw * 0.05
        for i in range(2):
            x = mx0 + (mx1 - mx0) * (0.2 + 0.45 * i)
            pts = [x, my0, x + sw_w, my0, x + sw_w - (my1 - my0) * 0.35, my1, x - (my1 - my0) * 0.35, my1]
            shines.append(self._poly(pts, shine_col))
        # mask strips keep the diagonal shines inside the mirror
        self._rect(0, ceil_h, mx0, fy, wall)
        self._rect(mx1, ceil_h, sw, fy, wall)
        self._rect(0, ceil_h, sw, my0, wall)
        n_pan = max(4, int(sw // 330))
        for i in range(n_pan + 1):
            x = mx0 + (mx1 - mx0) * i / n_pan
            self._line(x, my0, x, my1, fill="#161a24", width=6)
        self.canvas.create_rectangle(mx0, my0, mx1, my1, outline="#9aa3b5", width=3, tags=("bg",))
        # Barre
        by = fy - sh * 0.2
        for i in range(n_pan + 1):
            bx = mx0 + 30 + (mx1 - mx0 - 60) * i / n_pan
            self._rect(bx - 3, by, bx + 3, by + 22, "#8d939e")
        self._line(mx0 + 10, by, mx1 - 10, by, fill="#b98a4e", width=9, capstyle="round")
        self._line(mx0 + 10, by - 2, mx1 - 10, by - 2, fill="#d9ad6f", width=2)
        # Baseboard
        self._rect(0, fy - 8, sw, fy, "#13161d")

        # Wooden floor with perspective planks
        self._rect(0, fy, sw, sh, "#86593a")
        vx, vy = self.cx, fy - sh * 0.9
        for i in range(-14, 15):
            bx = self.cx + i * sw / 14
            t = (fy - vy) / (sh - vy)
            tx = vx + (bx - vx) * t
            self._line(tx, fy, bx, sh, fill="#6e4628", width=2)
        y, gap = fy + 10, 10
        while y < sh:
            self._line(0, y, sw, y, fill="#7a4f31", width=1)
            gap *= 1.35
            y += gap
        for i in range(n_lights):
            lx = sw * (i + 0.5) / n_lights
            self._oval(lx - sw * 0.1, fy + 22, lx + sw * 0.1, fy + 86, "#93653f")

        # Speakers (both sides) with pulsing woofers
        spk_w = min((self.side_l[1] - self.side_l[0]) * 0.42, 130)
        spk_h = spk_w * 1.7
        woofers = []
        notes = []
        for sx in (sw * 0.04, sw * 0.96 - spk_w):
            sb = fy + 36
            st0 = sb - spk_h
            self._oval(sx - 8, sb - 8, sx + spk_w + 8, sb + 10, "#5a3a25")
            self._rect(sx, st0, sx + spk_w, sb, "#15161b", outline="#30323b", width=2)
            ccx = sx + spk_w / 2
            tr = spk_w * 0.13
            self._oval(ccx - tr, st0 + spk_h * 0.16 - tr, ccx + tr, st0 + spk_h * 0.16 + tr, "#2a2c35", outline="#4b4f5c", width=2)
            wy = st0 + spk_h * 0.6
            wr = spk_w * 0.36
            self._oval(ccx - wr, wy - wr, ccx + wr, wy + wr, "#22242c", outline="#4b4f5c", width=3)
            cone = self._oval(ccx - wr * 0.6, wy - wr * 0.6, ccx + wr * 0.6, wy + wr * 0.6, "#30333e")
            woofers.append((cone, ccx, wy, wr * 0.6))
            for _ in range(2):
                item = self.canvas.create_text(
                    ccx, st0 - 10, text=self.rng.choice(("♪", "♫")), fill="#c8d0e0",
                    font=("Segoe UI Symbol", 20), tags=("bg",), state="hidden",
                )
                notes.append({"item": item, "side": len(woofers) - 1, "x0": ccx, "y0": st0 - 10,
                              "life": 0, "x": 0.0, "y": 0.0})

        self._scene_state.update(woofers=woofers, notes=notes, hint_lo="#4a5266")

        def tick() -> None:
            st = self._scene_state
            # Left speaker on even ticks, right on odd: keeps each redraw local.
            side = self._tick_n % 2
            cone, x, y, r = st["woofers"][side]
            rr = r * (1.08 if (self._tick_n // 2) % 2 else 1.0)
            self.canvas.coords(cone, x - rr, y - rr, x + rr, y + rr)
            for n in st["notes"]:
                if n["side"] != side:
                    continue
                if n["life"] <= 0:
                    if self.rng.random() < 0.06:
                        n.update(life=15, x=n["x0"] + self.rng.uniform(-20, 20), y=n["y0"])
                        self.canvas.itemconfigure(n["item"], state="normal")
                    else:
                        continue
                n["life"] -= 1
                n["y"] -= 4.4
                n["x"] += math.sin(n["life"] * 0.7) * 2.4
                if n["life"] <= 0:
                    self.canvas.itemconfigure(n["item"], state="hidden")
                    continue
                self.canvas.coords(n["item"], n["x"], n["y"])
                self.canvas.itemconfigure(n["item"], fill=_mix(wall, "#e6ecff", min(1.0, n["life"] / 8)))

        self._scene_tick_fn = tick
        return wall, "#9aa3b8"

    # ------------------------------------------------------------------ input
    def handle_key(self, event: tk.Event) -> str | None:
        keysym = getattr(event, "keysym", "") or ""
        char = getattr(event, "char", "") or ""
        keycode = getattr(event, "keycode", None)
        win_hwnd = 0
        try:
            if getattr(self, "win", None) is not None:
                win_hwnd = int(self.win.winfo_id())
        except Exception:
            win_hwnd = 0
        eff_keycode = (
            _resolve_ime_virtual_key(event, win_hwnd) or keycode
            if keycode == _VK_PROCESSKEY
            else keycode
        )
        if keysym in _MODIFIER_KEYSYMS or (sys.platform == "win32" and eff_keycode in _MODIFIER_VK_CODES):
            return "break"
        if keysym in ("Left", "Right") or (sys.platform == "win32" and eff_keycode in (37, 39) and not char):
            if self.running:
                step = -1 if (keysym == "Left" or eff_keycode == 37) else 1
                self.cycle_scene(step)
            return "break"
        if keysym.lower() == "h" or char in _IME_H_CHARS or (
                eff_keycode == 72 and (sys.platform == "win32" or keysym in ("Process", "??", ""))):
            if self.running:
                self.toggle_pure_view()
            return "break"
        self.handle_exit(event)
        return None

    def handle_click(self, event: tk.Event) -> None:
        if time.monotonic() - self._created_at < self._grace_period_s:
            return
        self.handle_exit(event)

    def handle_motion(self, event: tk.Event) -> None:
        # Screen coordinates: the mouse may move over any monitor's cover.
        pos = (getattr(event, "x_root", event.x), getattr(event, "y_root", event.y))
        if time.monotonic() - self._created_at < self._grace_period_s:
            self.mouse_origin = pos
            return
        if self.mouse_origin is None:
            self.mouse_origin = pos
            return
        dx = abs(pos[0] - self.mouse_origin[0])
        dy = abs(pos[1] - self.mouse_origin[1])
        threshold = max(50.0, 50.0 * self.k)
        if dx > threshold or dy > threshold:
            self.handle_exit(event)

    def _watch_real_lock(self) -> None:
        """Windows locked for real behind the overlay: leave once the user has unlocked.

        They have just signed in, so locking again on exit would only make them do it twice.
        """
        if not self.running:
            return
        try:
            locked = self.lock_probe()
        except Exception:
            locked = None
        if locked:
            self._saw_real_lock = True
        elif locked is False and self._saw_real_lock:
            self.lock_on_exit = False
            self.handle_exit(None)
            return
        self._later("lock_watch", LOCK_WATCH_MS, self._watch_real_lock)

    def dismiss(self) -> None:
        """Programmatically dismiss the standby screen."""
        self.handle_exit(None)

    def _release_images(self) -> None:
        """Drop the big pixel holders now (2026-11-22).

        The closed overlay sits in reference cycles (Tk callbacks, lambdas) and is only freed
        by a full gc pass; pixel buffers do not count towards gc thresholds, so a closed
        standby could keep ~250 MB of wallpapers and action frames for a long time.
        """
        getattr(self, "_wallpaper_cache", {}).clear()
        for cover in getattr(self, "covers", ()):
            cover.get("photos", {}).clear()
        for panda in getattr(self, "pandas", None) or ():
            panda["actions"] = {}
            for key in ("walk", "flipped_walk", "cheer"):
                if key in panda:
                    panda[key] = []
        # Its own SpriteLibrary (decoded-source cache + five members' parade frames) would
        # otherwise wait for the next full gc too (Neno's breakdown: ~40 MB).
        self._library = None
        for name in ("_dome_bubble_photo", "_dome_spot_photo", "_dome_bubble_pil"):
            if hasattr(self, name):
                setattr(self, name, None)

    def handle_exit(self, _: tk.Event | None = None) -> None:
        if not self.running:
            return
        self._gen = getattr(self, "_gen", 1) + 1
        self.running = False
        for steps, _spec in getattr(self, "_action_jobs", {}).values():
            steps.close()
        getattr(self, "_action_jobs", {}).clear()
        self._clear_dome_stage()
        self._cancel_all_timers()
        self._scene_tick_fn = None
        for cover in getattr(self, "covers", ()):
            try:
                cover["win"].destroy()
            except Exception:
                pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self._release_images()

        # Strict safety guard: never lock OS if under tests, and only if user explicitly turned it on
        if self.lock_on_exit:
            is_testing = any(k in sys.argv[0].lower() for k in ["test", "pytest"]) or hasattr(sys, "_running_tests")
            if not is_testing:
                try:
                    ctypes.windll.user32.LockWorkStation()
                except Exception:
                    pass

        if self.on_close:
            self.on_close()
