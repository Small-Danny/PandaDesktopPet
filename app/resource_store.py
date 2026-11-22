"""app/resource_store.py — Unified resource abstraction (loose folder or indexed .pak).

Keeps only a compact table of contents (TOC) in memory when reading from an
``assets.pak`` container; payloads are slice-read on demand with per-entry
SHA-256 verification and strict path-traversal rejection.

Binary container layout (``APPPAK01``):
  [0..8)   Magic bytes: ``b"APPPAK01"``
  [8..16)  uint64 LE: ``toc_offset``
  [16..24) uint64 LE: ``toc_length``
  [24..toc_offset) Raw or zlib-compressed asset payloads
  [toc_offset..toc_offset + toc_length) UTF-8 JSON TOC mapping normalized POSIX
      keys -> ``{"offset": int, "size": int, "raw_size": int, "codec": str, "sha256": str}``
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections import OrderedDict
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import struct
import threading
from typing import BinaryIO, Iterator
import zlib

from PIL import Image

from app.paths import resource_dir

PAK_MAGIC = b"APPPAK01"
PAK_HEADER_STRUCT = struct.Struct("<8sQQ")
PAK_FILENAME = "assets.pak"
CODEC_STORE = "store"
CODEC_ZLIB = "zlib"
_ALLOWED_CODECS = frozenset({CODEC_STORE, CODEC_ZLIB})


def normalize_resource_key(target: str | Path, root: Path | None = None) -> str:
    """Normalize a resource reference to a safe POSIX key with no ``..`` escape.

    Accepts relative keys like ``work/characters/chorong/idle_01.png`` or ``Path``
    objects located under ``root`` (if given). Raises ``ValueError`` on
    traversal, drive/root escapes, or NUL bytes.
    """
    if isinstance(target, Path):
        if root is not None:
            resolved_root = Path(os.path.abspath(str(root)))
            cand = target if target.is_absolute() else (resolved_root / target)
            resolved_cand = Path(os.path.abspath(str(cand)))
            try:
                rel = resolved_cand.relative_to(resolved_root)
            except ValueError as exc:
                raise ValueError(f"resource path escapes root: {target}") from exc
            raw = rel.as_posix()
        else:
            raw = target.as_posix()
    else:
        raw = str(target).replace("\\", "/")
        if root is not None and (os.path.isabs(raw) or (len(raw) >= 2 and raw[1] == ":")):
            resolved_root = Path(os.path.abspath(str(root)))
            resolved_cand = Path(os.path.abspath(raw))
            try:
                raw = resolved_cand.relative_to(resolved_root).as_posix()
            except ValueError as exc:
                raise ValueError(f"resource path escapes root: {target}") from exc

    if "\x00" in raw:
        raise ValueError("NUL byte in resource key")
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise ValueError(f"absolute resource key rejected: {target}")

    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"invalid resource key: {target}")
    return str(PurePosixPath(*parts))


class ResourceStore(ABC):
    """Read-only resource accessor backed by a folder tree or a .pak file."""

    def __init__(self, base_root: Path):
        self.base_root = Path(base_root).resolve()
        self._verified_lock = threading.RLock()
        self._verified_payloads: OrderedDict[tuple, tuple[bytes, str]] = OrderedDict()
        self._verified_bytes = 0
        self._verified_limit = 8 * 1024 * 1024   # raw PNG bytes; decoded copies live in the image caches

    def _verified_get(self, key: tuple) -> tuple[bytes, str] | None:
        with self._verified_lock:
            result = self._verified_payloads.get(key)
            if result is not None:
                self._verified_payloads.move_to_end(key)
            return result

    def _verified_put(self, key: tuple, data: bytes, digest: str) -> tuple[bytes, str]:
        with self._verified_lock:
            if len(data) <= self._verified_limit:
                old = self._verified_payloads.pop(key, None)
                if old is not None:
                    self._verified_bytes -= len(old[0])
                while self._verified_payloads and (self._verified_bytes + len(data) > self._verified_limit
                                                   or len(self._verified_payloads) >= 256):
                    self._verified_bytes -= len(self._verified_payloads.popitem(last=False)[1][0])
                self._verified_payloads[key] = (data, digest)
                self._verified_bytes += len(data)
        return data, digest

    def read_verified(self, target: str | Path) -> tuple[bytes, str]:
        """Payload and its verified digest, consumed together by decoders."""
        data = self.read_bytes(target, verify_hash=True)
        return data, hashlib.sha256(data).hexdigest()

    @abstractmethod
    def resolve_key(self, target: str | Path) -> str:
        """Convert ``target`` into a normalized relative POSIX key."""

    @abstractmethod
    def exists(self, target: str | Path) -> bool:
        """Return True if ``target`` exists in this store."""

    @abstractmethod
    def read_bytes(self, target: str | Path, *, verify_hash: bool = True) -> bytes:
        """Read the raw asset bytes for ``target``."""

    def read_text(self, target: str | Path, encoding: str = "utf-8-sig") -> str:
        return self.read_bytes(target).decode(encoding)

    def read_json(self, target: str | Path, encoding: str = "utf-8-sig") -> object:
        return json.loads(self.read_text(target, encoding=encoding))

    @abstractmethod
    def sha256(self, target: str | Path) -> str:
        """Return lowercase hex SHA-256 of the asset bytes."""

    @abstractmethod
    def stat_signature(self, target: str | Path) -> tuple:
        """Return an immutable cache key tuple representing the asset's bytes."""

    def open_image(self, target: str | Path) -> Image.Image:
        """Decode an image asset cleanly in memory with no lingering file handle."""
        payload = self.read_bytes(target)
        with Image.open(io.BytesIO(payload)) as raw:
            raw.load()
            return raw.copy()

    def list_keys(self, prefix: str = "") -> tuple[str, ...]:
        """List available normalized keys matching ``prefix``."""
        return ()

    @contextmanager
    def session(self) -> Iterator["ResourceStore"]:
        """Optional batching context to reuse open handle across multiple reads."""
        yield self


class FolderResourceStore(ResourceStore):
    """Direct filesystem implementation under ``base_root``."""

    def resolve_key(self, target: str | Path) -> str:
        return normalize_resource_key(target, root=self.base_root)

    def _safe_path(self, target: str | Path) -> Path:
        key = self.resolve_key(target)
        path = (self.base_root / key).resolve()
        try:
            path.relative_to(self.base_root)
        except ValueError as exc:
            raise ValueError(f"resource path escapes root: {target}") from exc
        return path

    def exists(self, target: str | Path) -> bool:
        try:
            return self._safe_path(target).is_file()
        except (ValueError, OSError):
            return False

    def read_bytes(self, target: str | Path, *, verify_hash: bool = True) -> bytes:
        return self.read_verified(target)[0]

    def read_verified(self, target: str | Path) -> tuple[bytes, str]:
        path = self._safe_path(target)
        version = _file_version(path)
        key = (str(path), version)
        hit = self._verified_get(key)
        if hit is not None:
            return hit
        data = path.read_bytes()
        if _file_version(path) != version:
            raise OSError(f"resource changed while reading: {path}")
        return self._verified_put(key, data, hashlib.sha256(data).hexdigest())

    def sha256(self, target: str | Path) -> str:
        return self.read_verified(target)[1]

    def stat_signature(self, target: str | Path) -> tuple:
        return ("fs", *_file_version(self._safe_path(target)))


def _file_version(path: Path) -> tuple:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


class PakResourceStore(ResourceStore):
    """Indexed container reader keeping only the compact TOC in memory."""

    def __init__(self, pak_path: Path, base_root: Path | None = None):
        self.pak_path = Path(pak_path).resolve()
        super().__init__(base_root if base_root is not None else self.pak_path.parent)
        self._local = threading.local()
        self._entries = self._load_toc()

    def _load_toc(self) -> dict[str, dict]:
        file_size = self.pak_path.stat().st_size
        if file_size < PAK_HEADER_STRUCT.size:
            raise ValueError(f"corrupt pak header: {self.pak_path}")
        with self.pak_path.open("rb") as fh:
            header = fh.read(PAK_HEADER_STRUCT.size)
            magic, toc_offset, toc_length = PAK_HEADER_STRUCT.unpack(header)
            if magic != PAK_MAGIC:
                raise ValueError(f"invalid pak magic in {self.pak_path}")
            if (toc_offset < PAK_HEADER_STRUCT.size
                    or toc_length <= 0
                    or toc_offset + toc_length > file_size):
                raise ValueError(f"invalid pak TOC bounds in {self.pak_path}")
            fh.seek(toc_offset)
            toc_raw = fh.read(toc_length)
        toc = json.loads(toc_raw.decode("utf-8"))
        if not isinstance(toc, dict) or toc.get("format") != 1 or not isinstance(toc.get("entries"), dict):
            raise ValueError(f"unsupported pak TOC schema in {self.pak_path}")
        entries: dict[str, dict] = {}
        for raw_key, meta in toc["entries"].items():
            key = normalize_resource_key(raw_key)
            if not isinstance(meta, dict):
                raise ValueError(f"invalid TOC metadata for {key}")
            offset = meta.get("offset")
            size = meta.get("size")
            raw_size = meta.get("raw_size")
            codec = meta.get("codec")
            digest = meta.get("sha256")
            if (key in entries
                    or type(offset) is not int or type(size) is not int or type(raw_size) is not int
                    or codec not in _ALLOWED_CODECS
                    or (codec == CODEC_STORE and size != raw_size)
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdefABCDEF" for c in digest)
                    or offset < PAK_HEADER_STRUCT.size or size < 0 or raw_size < 0
                    or offset + size > toc_offset):
                raise ValueError(f"corrupt TOC entry for {key}")
            entries[key] = {
                "offset": offset,
                "size": size,
                "raw_size": raw_size,
                "codec": codec,
                "sha256": digest.lower(),
            }
        return entries

    def resolve_key(self, target: str | Path) -> str:
        return normalize_resource_key(target, root=self.base_root)

    def _entry(self, target: str | Path) -> tuple[str, dict]:
        key = self.resolve_key(target)
        meta = self._entries.get(key)
        if meta is None:
            raise FileNotFoundError(f"asset not in pak: {key}")
        return key, meta

    def exists(self, target: str | Path) -> bool:
        try:
            key = self.resolve_key(target)
        except ValueError:
            return False
        return key in self._entries

    @contextmanager
    def session(self) -> Iterator["PakResourceStore"]:
        active: list[tuple[BinaryIO, int]] = getattr(self._local, "stack", [])
        if not hasattr(self._local, "stack"):
            self._local.stack = active
        if active:
            fh, depth = active[-1]
            active[-1] = (fh, depth + 1)
            try:
                yield self
            finally:
                fh, depth = active[-1]
                active[-1] = (fh, depth - 1)
            return
        with self.pak_path.open("rb") as fh:
            active.append((fh, 1))
            try:
                yield self
            finally:
                active.pop()

    def _read_slice(self, offset: int, size: int) -> bytes:
        stack: list[tuple[BinaryIO, int]] | None = getattr(self._local, "stack", None)
        if stack:
            fh = stack[-1][0]
            fh.seek(offset)
            return fh.read(size)
        with self.pak_path.open("rb") as fh:
            fh.seek(offset)
            return fh.read(size)

    def _payload(self, key: str, meta: dict) -> bytes:
        raw = self._read_slice(meta["offset"], meta["size"])
        if len(raw) != meta["size"]:
            raise IOError(f"truncated pak payload for {key}")
        data = raw if meta["codec"] == CODEC_STORE else zlib.decompress(raw)
        if len(data) != meta["raw_size"]:
            raise ValueError(f"size mismatch in pak for {key}")
        return data

    def read_verified(self, target: str | Path) -> tuple[bytes, str]:
        key, meta = self._entry(target)
        version = _file_version(self.pak_path)
        cache_key = (key, version, meta["sha256"])
        hit = self._verified_get(cache_key)
        if hit is not None:
            return hit
        data = self._payload(key, meta)
        digest = hashlib.sha256(data).hexdigest()
        if digest != meta["sha256"]:
            raise ValueError(f"sha256 mismatch in pak for {key}")
        if _file_version(self.pak_path) != version:
            raise OSError(f"pak changed while reading: {key}")
        return self._verified_put(cache_key, data, digest)

    def read_bytes(self, target: str | Path, *, verify_hash: bool = True) -> bytes:
        if verify_hash:
            return self.read_verified(target)[0]
        key, meta = self._entry(target)
        return self._payload(key, meta)

    def sha256(self, target: str | Path) -> str:
        return self.read_verified(target)[1]

    def stat_signature(self, target: str | Path) -> tuple:
        _key, meta = self._entry(target)
        return ("pak", meta["raw_size"], meta["sha256"], _file_version(self.pak_path))

    def list_keys(self, prefix: str = "") -> tuple[str, ...]:
        if not prefix:
            return tuple(sorted(self._entries))
        norm = prefix.replace("\\", "/").lstrip("./")
        return tuple(sorted(k for k in self._entries if k.startswith(norm)))


_STORE_LOCK = threading.Lock()
_STORE_CACHE: dict[tuple[Path, bool, int, int], PakResourceStore] = {}


def clear_store_cache() -> None:
    """Clear cached ResourceStore instances (primarily for tests)."""
    with _STORE_LOCK:
        _STORE_CACHE.clear()


def resource_store(root: Path | None = None) -> ResourceStore:
    """Return the active ResourceStore for ``root`` (defaults to ``resource_dir()``).

    Prefers direct ``FolderResourceStore`` when ``work/asset_registry.json`` exists on disk
    (developer tree or mock filesystem tests), and selects ``PakResourceStore`` when
    ``assets.pak`` is present without loose ``work/asset_registry.json`` (packaged runtime
    or pak-backed test directories).
    """
    base = Path(root).resolve() if root is not None else resource_dir().resolve()
    if base.is_file() and base.suffix.lower() == ".pak":
        st = base.stat()
        cache_key = (base, True, st.st_size, st.st_mtime_ns)
        with _STORE_LOCK:
            cached = _STORE_CACHE.get(cache_key)
            if cached is None:
                cached = PakResourceStore(base)
                _STORE_CACHE[cache_key] = cached
            return cached

    loose_registry = (base / "work" / "asset_registry.json").is_file()
    pak_path = base / PAK_FILENAME
    if not loose_registry and pak_path.is_file():
        st = pak_path.stat()
        cache_key = (pak_path.resolve(), False, st.st_size, st.st_mtime_ns)
        with _STORE_LOCK:
            cached = _STORE_CACHE.get(cache_key)
            if cached is None:
                cached = PakResourceStore(pak_path, base_root=base)
                _STORE_CACHE[cache_key] = cached
            return cached
    cache_key = (base, "folder")
    with _STORE_LOCK:
        cached = _STORE_CACHE.get(cache_key)
        if cached is None:
            cached = FolderResourceStore(base)
            _STORE_CACHE[cache_key] = cached
        return cached


def _external_explicit_path(target: str | Path, base_root: Path) -> Path | None:
    """Return ``target`` if caller passed a concrete absolute Path outside ``base_root`` without ``..``."""
    if not isinstance(target, Path) or "\x00" in str(target) or not target.is_absolute() or ".." in target.parts:
        return None
    resolved_root = Path(os.path.abspath(str(base_root)))
    resolved_cand = Path(os.path.abspath(str(target)))
    try:
        resolved_cand.relative_to(resolved_root)
        return None
    except ValueError:
        return target


def read_resource_bytes(path_or_key: str | Path, root: Path | None = None) -> bytes:
    """Read bytes from an explicit external on-disk Path (e.g. test fixture) or ResourceStore."""
    if "\x00" in str(path_or_key):
        raise ValueError("NUL byte in resource key")
    store = resource_store(root)
    ext = _external_explicit_path(path_or_key, store.base_root)
    if ext is not None:
        return ext.read_bytes()
    return store.read_bytes(path_or_key)


def open_resource_image(path_or_key: str | Path, root: Path | None = None) -> Image.Image:
    """Load an image from an explicit external on-disk Path (e.g. test fixture) or ResourceStore."""
    payload = read_resource_bytes(path_or_key, root=root)
    with Image.open(io.BytesIO(payload)) as raw:
        raw.load()
        return raw.copy()


def resource_exists(path_or_key: str | Path, root: Path | None = None) -> bool:
    """Return True if resource exists at an explicit external Path or in active ResourceStore."""
    if "\x00" in str(path_or_key):
        return False
    store = resource_store(root)
    ext = _external_explicit_path(path_or_key, store.base_root)
    if ext is not None:
        try:
            return ext.is_file()
        except (ValueError, OSError):
            return False
    return store.exists(path_or_key)


def resource_stat_signature(path_or_key: str | Path, root: Path | None = None) -> tuple:
    """Return an immutable cache signature for an explicit external Path or active ResourceStore entry."""
    if "\x00" in str(path_or_key):
        raise ValueError("NUL byte in resource key")
    store = resource_store(root)
    ext = _external_explicit_path(path_or_key, store.base_root)
    if ext is not None:
        st = ext.stat()
        return ("fs", st.st_size, st.st_mtime_ns)
    return store.stat_signature(path_or_key)
