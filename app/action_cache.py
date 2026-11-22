"""Byte-bounded LRU for desktop action frames (PIL first, Tk PhotoImages only on demand).

2026-11-22: ``PandaPet`` used four unbounded dicts (Tk + PIL, right + left facing) keyed by
(member, action, display_px). Every action ever played stayed resident: 771 actions at
480 px (192 DPI, large) reached 13.8 GB private bytes. This module replaces them with one
LRU whose budget follows the pixel area of the pet, and whose Tk images are created lazily
so a ULW (UpdateLayeredWindow) pet never allocates them at all.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Hashable, Iterator, Sequence

from PIL import Image, ImageTk

MB = 1024 * 1024
# 2026-11-22: was 96/48/256 MB. PREPARED_IMAGES keeps a compressed copy of every action
# (re-inflating one is 1-2 ms), so the decoded layer only needs the recent working set.
BASE_BUDGET_BYTES = 64 * MB          # at the 240 px reference height
MIN_BUDGET_BYTES = 32 * MB
MAX_BUDGET_BYTES = 160 * MB
REFERENCE_PX = 240
# The newest entries always survive eviction: the action on screen is touched every
# animation tick, so it can never lose its frames (and a canvas PhotoImage) mid-play.
MIN_KEEP_ENTRIES = 4


def action_cache_budget(display_px: int) -> int:
    """Bytes allowed for decoded desktop actions at ``display_px`` (scales with pixel area)."""
    px = max(1, int(display_px))
    budget = int(BASE_BUDGET_BYTES * (px / REFERENCE_PX) ** 2)
    return max(MIN_BUDGET_BYTES, min(MAX_BUDGET_BYTES, budget))


def image_bytes(im: Image.Image) -> int:
    return int(im.width) * int(im.height) * max(1, len(im.getbands()))


class LazyPhotoList(Sequence):
    """Sequence of ``ImageTk.PhotoImage`` built from PIL frames the first time each is indexed."""

    __slots__ = ("pil", "_master", "_photos", "_factory")

    def __init__(self, pil_frames: Sequence[Image.Image], master=None, factory=None) -> None:
        self.pil = tuple(pil_frames)
        self._master = master
        self._photos: dict[int, ImageTk.PhotoImage] = {}
        self._factory = factory

    def __len__(self) -> int:
        return len(self.pil)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self.pil)))]
        n = len(self.pil)
        i = index + n if index < 0 else index
        if not 0 <= i < n:
            raise IndexError(index)
        photo = self._photos.get(i)
        if photo is None:
            build = self._factory if self._factory is not None else ImageTk.PhotoImage
            photo = build(self.pil[i], master=self._master)
            self._photos[i] = photo
        return photo

    def __iter__(self) -> Iterator[ImageTk.PhotoImage]:
        for i in range(len(self.pil)):
            yield self[i]

    @property
    def created(self) -> int:
        return len(self._photos)

    def photo_bytes(self) -> int:
        # Tk keeps a 32-bit block per pixel for every created photo.
        return sum(self.pil[i].width * self.pil[i].height * 4 for i in self._photos)


class ActionEntry:
    """One cached action at one size and facing."""

    __slots__ = ("pil", "frame_ms", "offset", "photos", "pil_bytes")

    def __init__(self, pil: Sequence[Image.Image], frame_ms: float, offset: tuple[int, int],
                 master=None) -> None:
        self.pil = tuple(pil)
        self.frame_ms = frame_ms
        self.offset = offset
        self.photos = LazyPhotoList(self.pil, master)
        self.pil_bytes = sum(image_bytes(im) for im in self.pil)

    def nbytes(self) -> int:
        return self.pil_bytes + self.photos.photo_bytes()

    def tk_tuple(self):
        return self.photos, self.frame_ms, self.offset

    def pil_tuple(self):
        return self.pil, self.frame_ms, self.offset


MISSING = object()


class ActionFrameCache:
    """LRU of ``ActionEntry`` (or ``None`` for "not approved") bounded by decoded bytes."""

    def __init__(self, budget_bytes: int, *, min_keep: int = MIN_KEEP_ENTRIES) -> None:
        self.budget_bytes = int(budget_bytes)
        self.min_keep = int(min_keep)
        self._items: OrderedDict[Hashable, ActionEntry | None] = OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key: Hashable):
        """The entry (``None`` when known absent), or ``MISSING``; a hit becomes most recent."""
        if key in self._items:
            self._items.move_to_end(key)
            self.hits += 1
            return self._items[key]
        self.misses += 1
        return MISSING

    def peek(self, key: Hashable):
        return self._items.get(key, MISSING)

    def put(self, key: Hashable, entry: ActionEntry | None) -> None:
        self._items[key] = entry
        self._items.move_to_end(key)
        self.trim()

    def trim(self) -> None:
        """Evict least recently used entries until the budget holds (newest few always stay)."""
        total = self.nbytes()
        while total > self.budget_bytes and len(self._items) > self.min_keep:
            _key, old = self._items.popitem(last=False)
            self.evictions += 1
            if old is not None:
                total -= old.nbytes()

    def set_budget(self, budget_bytes: int) -> None:
        self.budget_bytes = int(budget_bytes)
        self.trim()

    def nbytes(self) -> int:
        return sum(e.nbytes() for e in self._items.values() if e is not None)

    def photo_count(self) -> int:
        return sum(e.photos.created for e in self._items.values() if e is not None)

    def drop(self, predicate: Callable[[Hashable], bool]) -> None:
        for key in [k for k in self._items if predicate(k)]:
            del self._items[key]

    def clear(self) -> None:
        self._items.clear()

    def keys(self):
        return list(self._items.keys())

    def __contains__(self, key) -> bool:
        return key in self._items

    def __len__(self) -> int:
        return len(self._items)

    def stats(self) -> dict:
        return {
            "entries": len(self._items),
            "mb": round(self.nbytes() / MB, 1),
            "budget_mb": round(self.budget_bytes / MB, 1),
            "tk_photos": self.photo_count(),
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }
