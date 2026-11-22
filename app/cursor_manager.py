"""app/cursor_manager.py — Kawaii Windows Mouse Cursor Loader and HWND Cursor Controller.

Provides native Windows mouse cursor support for Apink Desktop Pet:
- Supports both smooth vector cursors and retro pixel-art cursors:
  * "paw_smooth": Pink panda paw cursor (smooth)
  * "mitten_smooth": Kawaii pointing mitten with heart (smooth)
  * "paw_pixel": Retro pixel-art panda paw
  * "mitten_pixel": Retro pixel-art pointing mitten
  * "system": Restores default Windows system cursor
- Loads multi-resolution .cur files (32x32 / 48x48) with accurate hotspot tip geometry.
- Controls window class cursor via SetClassLongPtrW / SetCursor.
"""
from __future__ import annotations

import ctypes
import atexit
import hashlib
import logging
import struct
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterable, Optional

from app.paths import resource_dir
from app.resource_store import read_resource_bytes

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
RES_ROOT = resource_dir()
UI_ICONS_DIR = RES_ROOT / "work" / "ui_icons"

GCLP_HCURSOR = -12
GWLP_WNDPROC = -4
IDC_ARROW = 32512
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_WINDOWPOSCHANGED = 0x0047
WM_NCDESTROY = 0x0082
WM_CAPTURECHANGED = 0x0215
WM_MOUSELEAVE = 0x02A3
HTNOWHERE = 0
HTCLIENT = 1
HTTRANSPARENT = 0xFFFF
HTERROR = 0xFFFE
SM_CXCURSOR = 13
_HT_CLIENT_OR_TRANSPARENT = frozenset({HTNOWHERE, HTTRANSPARENT, HTERROR})
_WM_REAPPLY_CURSOR_MSGS = frozenset({
    0x0200,  # WM_MOUSEMOVE — TkWinChildProc resets cursor via TkpSetCursor(NULL) when tk cursor == ""
    0x0201,  # WM_LBUTTONDOWN
    0x0202,  # WM_LBUTTONUP
    0x0203,  # WM_LBUTTONDBLCLK
    0x0204,  # WM_RBUTTONDOWN
    0x0205,  # WM_RBUTTONUP
    0x0207,  # WM_MBUTTONDOWN
    0x0208,  # WM_MBUTTONUP
    0x020A,  # WM_MOUSEWHEEL
    0x02A1,  # WM_MOUSEHOVER
})
_WM_CAPTURED_REAPPLY_MSGS = frozenset({
    WM_WINDOWPOSCHANGED,
    WM_CAPTURECHANGED,
    WM_MOUSELEAVE,
})

CURSOR_FILES = {
    "paw_smooth": "cursor_paw_smooth.cur",
    "mitten_smooth": "cursor_mitten_smooth.cur",
    "paw_pixel": "cursor_paw_pixel.cur",
    "mitten_pixel": "cursor_mitten_pixel.cur",
}

_CURSOR_CACHE: dict[str, int] = {}
# True only while this process has replaced the OS arrow; nothing system-wide is touched otherwise.
_GLOBAL_APPLIED = False
_CURSOR_FILE_LOCK = threading.RLock()
_CURSOR_TEMP: tempfile.TemporaryDirectory | None = None
_CURSOR_PATHS: dict[tuple[str, str], Path] = {}


def cleanup_cursor_files() -> None:
    """Release packed CUR materializations after the last Tk window is destroyed."""
    global _CURSOR_TEMP
    with _CURSOR_FILE_LOCK:
        _CURSOR_PATHS.clear()
        temp, _CURSOR_TEMP = _CURSOR_TEMP, None
        if temp is not None:
            temp.cleanup()


atexit.register(cleanup_cursor_files)


def _get_win32_cursor_apis():
    try:
        user32 = ctypes.windll.user32
        set_cls = getattr(user32, "SetClassLongPtrW", getattr(user32, "SetClassLongW", None))
        if set_cls is not None:
            set_cls.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_cls.restype = ctypes.c_void_p
        get_wnd = getattr(user32, "GetWindowLongPtrW", getattr(user32, "GetWindowLongW", None))
        if get_wnd is not None:
            get_wnd.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_wnd.restype = ctypes.c_void_p
        set_wnd = getattr(user32, "SetWindowLongPtrW", getattr(user32, "SetWindowLongW", None))
        if set_wnd is not None:
            set_wnd.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_wnd.restype = ctypes.c_void_p
        call_wnd = getattr(user32, "CallWindowProcW", None)
        if call_wnd is not None:
            call_wnd.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
            ]
            call_wnd.restype = ctypes.c_ssize_t
        return set_cls, get_wnd, set_wnd, call_wnd
    except Exception:
        return None, None, None, None


_SetClassLongPtr, _GetWindowLongPtr, _SetWindowLongPtr, _CallWindowProc = _get_win32_cursor_apis()
_WNDPROC_TYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
)
# Map hwnd -> [orig_wndproc, c_callback, cursor_key, cb_addr] so callback stays alive while installed.
_HWND_HOOKS: dict[int, list] = {}


def get_cursor_path(cursor_key: str) -> Optional[Path]:
    filename = CURSOR_FILES.get(cursor_key)
    if not filename:
        return None
    path = UI_ICONS_DIR / filename
    return path if path.exists() else None


def _materialize_packed_cursor(cursor_key: str) -> Path | None:
    """Give Tk and Win32 the same packed multi-resolution cursor file."""
    filename = CURSOR_FILES.get(cursor_key)
    if filename is None:
        return None
    # Tk must own a real custom cursor too: a blank spec makes Tk briefly
    # select IDC_ARROW inside its native mouse procedure before our hook runs.
    global _CURSOR_TEMP
    key = (str(RES_ROOT.resolve()), cursor_key)
    with _CURSOR_FILE_LOCK:
        path = _CURSOR_PATHS.get(key)
        if path is None:
            try:
                raw = read_resource_bytes(f"work/ui_icons/{filename}", root=RES_ROOT)
                if len(raw) < 6 or struct.unpack_from("<HH", raw) != (0, 2):
                    raise ValueError("invalid packed CUR header")
                digest = hashlib.sha256(raw).hexdigest()
                if _CURSOR_TEMP is None:
                    _CURSOR_TEMP = tempfile.TemporaryDirectory(prefix="panda_cursor_", ignore_cleanup_errors=True)
                path = Path(_CURSOR_TEMP.name) / f"{cursor_key}-{digest}.cur"
                # Exclusive creation inside an unguessable per-process directory.
                try:
                    with path.open("xb") as stream:
                        stream.write(raw)
                except FileExistsError:
                    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                        raise ValueError("cursor cache collision")
                _CURSOR_PATHS[key] = path
            except (OSError, ValueError) as exc:
                LOGGER.warning("Cannot materialize packed cursor %s: %s", cursor_key, exc)
                return None
    return path


def get_tkinter_cursor_spec(cursor_key: str) -> str:
    """Return Tkinter-compatible cursor specification string.

    On Windows Tkinter, external .cur files are specified as '@<forward_slash_path>'.
    Returns '' for standard system arrow cursor.
    """
    if cursor_key == "system":
        return ""
    path = get_cursor_path(cursor_key) or _materialize_packed_cursor(cursor_key)
    if path is None:
        return ""
    from tkinter import _join
    return _join((f"@{path.resolve().as_posix()}",))


SPI_SETCURSORS = 0x0057
OCR_NORMAL = 32512


def apply_system_cursor_global(cursor_key: str) -> bool:
    """Optionally apply custom cursor to the entire Windows OS."""
    global _GLOBAL_APPLIED
    if cursor_key == "system":
        return restore_system_cursor_global()
    hcur = load_cursor(cursor_key)
    if not hcur:
        return False
    try:
        user32 = ctypes.windll.user32
        copy_icon = user32.CopyIcon
        copy_icon.argtypes = [ctypes.c_void_p]
        copy_icon.restype = ctypes.c_void_p
        set_sys = user32.SetSystemCursor
        set_sys.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        copy = copy_icon(hcur)
        if copy:
            if set_sys(copy, OCR_NORMAL):
                _GLOBAL_APPLIED = True
                return True
            destroy_cursor = user32.DestroyCursor
            destroy_cursor.argtypes = [ctypes.c_void_p]
            destroy_cursor.restype = ctypes.c_int
            destroy_cursor(copy)
    except Exception as exc:
        LOGGER.warning("apply_system_cursor_global failed: %s", exc)
    return False


def restore_system_cursor_global() -> bool:
    """Restore standard Windows OS cursors via SystemParametersInfoW (only if we replaced them).

    This runs on every hover over the pet, so it must stay a no-op for the normal pet-only cursor.
    """
    global _GLOBAL_APPLIED
    if not _GLOBAL_APPLIED:
        return True
    try:
        restored = bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, 0, 0))
        if restored:
            _GLOBAL_APPLIED = False
        return restored
    except Exception as exc:
        LOGGER.warning("restore_system_cursor_global failed: %s", exc)
        return False


atexit.register(restore_system_cursor_global)


def _load_cursor_from_bytes(data: bytes) -> int:
    """Create a Win32 HCURSOR in memory from .cur binary bytes (no temp files)."""
    if len(data) < 6:
        return 0
    reserved, cur_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or cur_type != 2 or count < 1 or len(data) < 6 + count * 16:
        return 0
    user32 = ctypes.windll.user32
    desired = int(user32.GetSystemMetrics(SM_CXCURSOR) or 32)
    best = None
    for idx in range(count):
        bw, bh, _cc, _res, hx, hy, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + idx * 16)
        if size <= 0 or offset + size > len(data):
            continue
        w = 256 if bw == 0 else bw
        h = 256 if bh == 0 else bh
        rank = 0 if w == desired else (1 if w > desired else 2)
        score = (rank, abs(w - desired), -size)
        if best is None or score < best[0]:
            best = (score, w, h, hx, hy, data[offset:offset + size])
    if best is None:
        return 0
    _score, w, h, hx, hy, img_bytes = best
    payload = struct.pack("<HH", hx, hy) + img_bytes
    buf = ctypes.create_string_buffer(payload, len(payload))
    create_icon = user32.CreateIconFromResourceEx
    create_icon.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    create_icon.restype = ctypes.c_void_p
    hcur = create_icon(buf, len(payload), 0, 0x00030000, w, h, 0)
    return int(hcur or 0)


def load_cursor(cursor_key: str) -> int:
    """Load or retrieve cached HCURSOR for given cursor key; returns 0 if system or failed."""
    if cursor_key in _CURSOR_CACHE:
        return _CURSOR_CACHE[cursor_key]

    user32 = ctypes.windll.user32
    if cursor_key == "system":
        try:
            load_cur = user32.LoadCursorW
            load_cur.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            load_cur.restype = ctypes.c_void_p
            h = int(load_cur(None, ctypes.c_void_p(IDC_ARROW)) or 0)
            if h:
                _CURSOR_CACHE["system"] = h
            return h
        except Exception:
            return 0

    source_path = get_cursor_path(cursor_key)
    path = source_path or _materialize_packed_cursor(cursor_key)
    if path is not None:
        try:
            load_from_file = user32.LoadCursorFromFileW
            load_from_file.argtypes = [ctypes.c_wchar_p]
            load_from_file.restype = ctypes.c_void_p
            hcur = int(load_from_file(str(path.resolve())) or 0)
            if hcur:
                _CURSOR_CACHE[cursor_key] = hcur
                return hcur
        except Exception as exc:
            LOGGER.warning("Failed to load cursor %s from %s: %s", cursor_key, path, exc)
        if source_path is None:
            return 0

    filename = CURSOR_FILES.get(cursor_key)
    if not filename:
        return 0
    try:
        raw = read_resource_bytes(f"work/ui_icons/{filename}", root=RES_ROOT)
        hcur = _load_cursor_from_bytes(raw)
        if hcur:
            _CURSOR_CACHE[cursor_key] = hcur
            return hcur
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.debug("Cursor %s not found in resource store: %s", cursor_key, exc)
    except Exception as exc:
        LOGGER.warning("Failed to load packed cursor %s: %s", cursor_key, exc)

    return 0


_U32_PRIVATE = ctypes.WinDLL("user32") if hasattr(ctypes, "WinDLL") else None
_U32_SET_CURSOR = None
_U32_IS_WINDOW = None
_U32_GET_CAPTURE = None
if _U32_PRIVATE is not None:
    try:
        _U32_SET_CURSOR = _U32_PRIVATE.SetCursor
        _U32_SET_CURSOR.argtypes = [ctypes.c_void_p]
        _U32_SET_CURSOR.restype = ctypes.c_void_p
        _U32_IS_WINDOW = _U32_PRIVATE.IsWindow
        _U32_IS_WINDOW.argtypes = [ctypes.c_void_p]
        _U32_IS_WINDOW.restype = ctypes.c_int
        _U32_GET_CAPTURE = _U32_PRIVATE.GetCapture
        _U32_GET_CAPTURE.argtypes = []
        _U32_GET_CAPTURE.restype = ctypes.c_void_p
    except Exception:
        _U32_SET_CURSOR = None
        _U32_IS_WINDOW = None
        _U32_GET_CAPTURE = None


def _is_win32_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        if _U32_IS_WINDOW is not None:
            return bool(_U32_IS_WINDOW(hwnd))
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [ctypes.c_void_p]
        return bool(user32.IsWindow(hwnd))
    except Exception:
        return False


def _is_captured_by_hook() -> bool:
    """Return True when the active Win32 mouse capture HWND belongs to a hooked window."""
    if _U32_GET_CAPTURE is None or not _HWND_HOOKS:
        return False
    try:
        cap = int(_U32_GET_CAPTURE() or 0)
        return bool(cap and cap in _HWND_HOOKS)
    except Exception:
        return False


def _set_active_cursor(hcur: int) -> None:
    """Invoke Win32 SetCursor for a loaded HCURSOR without raising on headless calls."""
    if not hcur:
        return
    try:
        if _U32_SET_CURSOR is not None:
            _U32_SET_CURSOR(hcur)
            return
        set_cur = ctypes.windll.user32.SetCursor
        set_cur.argtypes = [ctypes.c_void_p]
        set_cur.restype = ctypes.c_void_p
        set_cur(hcur)
    except Exception:
        pass


def reapply_active_cursor(cursor_key: str) -> bool:
    """Immediately re-assert a non-system Win32 HCURSOR during drag/capture updates."""
    if not cursor_key or cursor_key == "system":
        return False
    hcur = load_cursor(cursor_key)
    if not hcur:
        return False
    _set_active_cursor(hcur)
    return True


def _prune_stale_hooks() -> None:
    """Drop entries whose HWND is already gone.

    Some native controls (e.g. Tk's Scrollbar) restore their own WndProc before WM_NCDESTROY,
    so our hook never sees the destroy message and its entry would otherwise linger.
    """
    for hwnd in [h for h in _HWND_HOOKS if not _is_win32_window(h)]:
        _HWND_HOOKS.pop(hwnd, None)


def _install_cursor_hook(hwnd: int, cursor_key: str) -> bool:
    if _GetWindowLongPtr is None or _SetWindowLongPtr is None or _CallWindowProc is None:
        return False
    _prune_stale_hooks()
    if not _is_win32_window(hwnd):
        return False

    existing = _HWND_HOOKS.get(hwnd)
    if existing is not None:
        existing[2] = cursor_key
        return True

    def _wnd_proc(cb_hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        key_hwnd = int(cb_hwnd or 0)
        entry = _HWND_HOOKS.get(key_hwnd)
        if entry is None:
            return 0
        orig_proc, _cb, cur_key, cb_addr = entry
        if msg == WM_NCDESTROY:
            entry[2] = "system"
            if _GetWindowLongPtr is not None and _SetWindowLongPtr is not None and orig_proc:
                try:
                    cur_proc = int(_GetWindowLongPtr(key_hwnd, GWLP_WNDPROC) or 0)
                    if cur_proc == cb_addr:
                        _SetWindowLongPtr(key_hwnd, GWLP_WNDPROC, orig_proc)
                except Exception:
                    pass
            try:
                return int(_CallWindowProc(orig_proc, key_hwnd, msg, wparam, lparam))
            finally:
                _HWND_HOOKS.pop(key_hwnd, None)
        elif msg == WM_SETCURSOR and cur_key != "system":
            ht = lparam & 0xFFFF
            if ht == HTCLIENT or (
                ht in _HT_CLIENT_OR_TRANSPARENT
                and (int(wparam or 0) in _HWND_HOOKS or _is_captured_by_hook())
            ):
                hcur = load_cursor(cur_key)
                if hcur:
                    _set_active_cursor(hcur)
                    return 1
        ret = int(_CallWindowProc(orig_proc, key_hwnd, msg, wparam, lparam))
        ht_after = lparam & 0xFFFF
        should_reapply = (
            msg in _WM_REAPPLY_CURSOR_MSGS
            or (msg == WM_MOUSEACTIVATE and (ht_after == HTCLIENT or _is_captured_by_hook()))
            or (
                msg in _WM_CAPTURED_REAPPLY_MSGS
                and (_is_captured_by_hook() or (msg == WM_CAPTURECHANGED and int(lparam or 0) in _HWND_HOOKS))
            )
        )
        if should_reapply:
            # Re-read hook state after Tk runs because callbacks (e.g. clicking "system" or closing) can mutate it.
            latest = _HWND_HOOKS.get(key_hwnd)
            if latest is not None and latest[2] != "system":
                _set_active_cursor(load_cursor(latest[2]))
        return ret

    orig_proc = int(_GetWindowLongPtr(hwnd, GWLP_WNDPROC) or 0)
    if not orig_proc:
        return False
    cb = _WNDPROC_TYPE(_wnd_proc)
    cb_addr = int(ctypes.cast(cb, ctypes.c_void_p).value or 0)
    if not cb_addr:
        return False
    entry = [orig_proc, cb, cursor_key, cb_addr]
    _HWND_HOOKS[hwnd] = entry
    if not _SetWindowLongPtr(hwnd, GWLP_WNDPROC, cb_addr):
        _HWND_HOOKS.pop(hwnd, None)
        return False
    return True


def _uninstall_cursor_hook(hwnd: int) -> None:
    entry = _HWND_HOOKS.get(hwnd)
    if entry is None:
        return
    entry[2] = "system"
    orig_proc, _cb, _key, cb_addr = entry
    try:
        if not _is_win32_window(hwnd):
            _HWND_HOOKS.pop(hwnd, None)
            return
        if _GetWindowLongPtr is not None and _SetWindowLongPtr is not None:
            cur_proc = int(_GetWindowLongPtr(hwnd, GWLP_WNDPROC) or 0)
            if cur_proc == cb_addr:
                _SetWindowLongPtr(hwnd, GWLP_WNDPROC, orig_proc)
                _HWND_HOOKS.pop(hwnd, None)
    except Exception:
        pass


def set_window_cursor(hwnd: int, cursor_key: str) -> bool:
    """Apply custom or system cursor to the specified Win32 HWND via per-HWND subclassing."""
    if not hwnd or _GetWindowLongPtr is None or _SetWindowLongPtr is None or _CallWindowProc is None:
        return False

    if cursor_key == "system":
        _uninstall_cursor_hook(hwnd)
        sys_hcur = load_cursor("system")
        if not sys_hcur:
            return False
        _set_active_cursor(sys_hcur)
        return True

    hcur = load_cursor(cursor_key)
    if not hcur:
        _uninstall_cursor_hook(hwnd)
        sys_hcur = load_cursor("system")
        if sys_hcur:
            _set_active_cursor(sys_hcur)
        return False

    if not _install_cursor_hook(hwnd, cursor_key):
        return False
    _set_active_cursor(hcur)
    return True


def reset_window_cursor(hwnd: int) -> bool:
    """Reset window cursor back to system standard arrow."""
    _prune_stale_hooks()
    return set_window_cursor(hwnd, "system")


def _widget_window_hwnds(widget: Any) -> list[int]:
    """Collect unique Win32 HWNDs (outer wm_frame and client winfo_id) for a widget."""
    hwnds: list[int] = []
    seen: set[int] = set()
    if hasattr(widget, "wm_frame"):
        try:
            frame = widget.wm_frame()
            if frame:
                f_str = str(frame).strip()
                frame_hwnd = int(f_str, 16) if f_str.startswith("0x") else int(f_str)
                if frame_hwnd and frame_hwnd not in seen:
                    seen.add(frame_hwnd)
                    hwnds.append(frame_hwnd)
        except Exception:
            pass
    try:
        client_hwnd = int(widget.winfo_id())
        if client_hwnd and client_hwnd not in seen:
            seen.add(client_hwnd)
            hwnds.append(client_hwnd)
    except Exception:
        pass
    return hwnds


def apply_cursor_to_widgets(widgets: Iterable[Any], cursor_key: str, *, recursive: bool = True) -> list[Any]:
    """Configure Tk and Win32 cursors uniformly across widgets (and descendants by default)."""
    _prune_stale_hooks()
    spec = get_tkinter_cursor_spec(cursor_key)
    target_key = cursor_key
    applied: list[Any] = []
    seen: set[int] = set()
    queue: list[Any] = list(widgets)
    idx = 0
    while idx < len(queue):
        widget = queue[idx]
        idx += 1
        if widget is None or id(widget) in seen:
            continue
        seen.add(id(widget))
        applied.append(widget)
        if not hasattr(widget, "_default_tk_cursor"):
            try:
                widget._default_tk_cursor = str(widget.cget("cursor") or "")
            except Exception:
                widget._default_tk_cursor = ""
        tk_cursor = getattr(widget, "_default_tk_cursor", "") if cursor_key == "system" else spec
        try:
            widget.config(cursor=tk_cursor)
        except Exception:
            pass
        try:
            widget._panda_cursor_key = target_key
        except Exception:
            pass
        for hwnd in _widget_window_hwnds(widget):
            set_window_cursor(hwnd, target_key)
        if hasattr(widget, "wm_frame") and hasattr(widget, "bind") and not getattr(widget, "_panda_cursor_map_bound", False):
            try:
                def _on_map(_e: Any = None, w: Any = widget) -> None:
                    cur_key = getattr(w, "_panda_cursor_key", "system")
                    for h in _widget_window_hwnds(w):
                        set_window_cursor(h, cur_key)

                widget.bind("<Map>", _on_map, add="+")
                widget._panda_cursor_map_bound = True
            except Exception:
                pass
        if recursive:
            try:
                queue.extend(widget.winfo_children())
            except Exception:
                pass
    return applied


def release_cursor_hooks(widgets: Iterable[Any]) -> None:
    """Unhook widgets (and descendants) about to be destroyed, without touching the active cursor."""
    queue: list[Any] = list(widgets)
    while queue:
        widget = queue.pop()
        if widget is None:
            continue
        for hwnd in _widget_window_hwnds(widget):
            _uninstall_cursor_hook(hwnd)
        try:
            queue.extend(widget.winfo_children())
        except Exception:
            pass
    _prune_stale_hooks()
