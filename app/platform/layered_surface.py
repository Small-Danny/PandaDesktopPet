"""Win32 UpdateLayeredWindow (ULW_ALPHA) per-pixel alpha sprite surface.

Design contract (Option A+ Stage 1):
1. Four orthogonal responsibilities:
   - present(image, x=None, y=None, opacity=1.0): Premultiply RGBA -> BGRA into a
     reused 32-bit top-down DIBSection (biHeight = -h) and call UpdateLayeredWindow
     with ULW_ALPHA and BLENDFUNCTION.SourceConstantAlpha (0..255). Reallocates the
     DIBSection only when (width, height) changes, always restoring old_obj via
     SelectObject before calling DeleteObject(hbmp).
   - move(x, y): Reposition the surface without rebuilding or re-uploading pixel data
     (supports negative multi-monitor coordinates).
   - set_visibility(visible) / close(): Manage ShowWindow(SW_SHOWNOACTIVATE) / SW_HIDE,
     WS_EX_NOACTIVATE, TOPMOST, and deterministic GDI resource cleanup (SelectObject,
     DeleteObject, DeleteDC; idempotent close() + safe __del__).
   - set_input_policy(policy): Toggle between 'interactive' (WS_EX_LAYERED only: Windows
     automatically passes through alpha == 0 pixels and delivers mouse events on
     alpha >= 1 pixels to the Tk Toplevel) and 'passthrough' (adds WS_EX_TRANSPARENT
     for full-window click-through).
2. Strict Win32 / 64-bit / Tk invariants:
   - NEVER call Tk's attributes('-transparentcolor', ...) or attributes('-alpha', ...)
     on a window managed by LayeredSpriteSurface (mixing SetLayeredWindowAttributes
     with UpdateLayeredWindow causes subsequent ULW calls to fail).
   - Every Win32 HANDLE / HWND / HDC / HBITMAP / HGDIOBJ ctypes signature is explicitly
     typed as 64-bit pointer-sized c_void_p.
   - Authoritative (x, y, width, height, opacity, visible, input_policy) state is
     maintained on the surface object without relying on asynchronous Tk winfo_* queries.
   - Supports clean backend injection / headless fallback when sys.platform != 'win32'
     or in unit tests with mock windows.
"""
from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any, Literal

from PIL import Image

LOGGER = logging.getLogger(__name__)

InputPolicy = Literal["interactive", "passthrough"]

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOCOPYBITS = 0x0100

BI_RGB = 0
DIB_RGB_COLORS = 0
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
ULW_ALPHA = 0x00000002
GR_GDIOBJECTS = 0

_BOOL = ctypes.c_int32
_BYTE = ctypes.c_uint8
_WORD = ctypes.c_uint16
_DWORD = ctypes.c_uint32
_LONG = ctypes.c_int32
_LONG_PTR = ctypes.c_ssize_t
_HANDLE = ctypes.c_void_p


class _POINT(ctypes.Structure):
    _fields_ = [("x", _LONG), ("y", _LONG)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", _LONG), ("cy", _LONG)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", _BYTE),
        ("BlendFlags", _BYTE),
        ("SourceConstantAlpha", _BYTE),
        ("AlphaFormat", _BYTE),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", _DWORD),
        ("biWidth", _LONG),
        ("biHeight", _LONG),
        ("biPlanes", _WORD),
        ("biBitCount", _WORD),
        ("biCompression", _DWORD),
        ("biSizeImage", _DWORD),
        ("biXPelsPerMeter", _LONG),
        ("biYPelsPerMeter", _LONG),
        ("biClrUsed", _DWORD),
        ("biClrImportant", _DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", _DWORD * 3),
    ]


def premultiply_rgba_to_bgra(image: Image.Image) -> tuple[bytes, int, int]:
    """Convert any PIL Image into tightly packed top-down premultiplied BGRA bytes."""
    cached = getattr(image, "_ulw_premultiplied_bgra", None)
    if (
        isinstance(cached, tuple)
        and len(cached) == 3
        and (cached[1], cached[2]) == image.size
    ):
        return cached
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    w, h = rgba.size
    if w <= 0 or h <= 0:
        raise ValueError(f"sprite image dimensions must be positive, got {(w, h)}")
    bgra = rgba.convert("RGBa").tobytes("raw", "BGRa")
    return bgra, w, h


ULW_COMPOSED_BASE_BYTES = 32 * 1024 * 1024


def ulw_composed_budget(display_px: int) -> int:
    """Bytes of premultiplied BGRA frames kept for the desktop pet (32 MB, up to 64 MB at 2x)."""
    area = (max(1, int(display_px or 192)) / 240.0) ** 2
    return int(ULW_COMPOSED_BASE_BYTES * min(2.0, max(1.0, area)))


class PremultipliedFrame:
    """Ready-to-present premultiplied BGRA pixels; carries no PIL image (one copy only)."""

    __slots__ = ("size", "_ulw_premultiplied_bgra")

    def __init__(self, bgra: bytes, width: int, height: int) -> None:
        self.size = (int(width), int(height))
        self._ulw_premultiplied_bgra = (bgra, int(width), int(height))

    @classmethod
    def from_image(cls, image: Image.Image) -> "PremultipliedFrame":
        return cls(*premultiply_rgba_to_bgra(image))

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def nbytes(self) -> int:
        return len(self._ulw_premultiplied_bgra[0])


def resolve_window_hwnd(window: Any) -> int:
    """Resolve the outer top-level Win32 HWND for a Tk Toplevel/Tk or raw handle."""
    if isinstance(window, int) and not isinstance(window, bool):
        if window <= 0:
            raise ValueError("hwnd must be a positive integer")
        return window
    try:
        window.update_idletasks()
    except Exception:
        pass
    try:
        frame = window.wm_frame()
        if frame:
            hwnd = int(frame, 16) if isinstance(frame, str) and frame.startswith("0x") else int(frame)
            if hwnd > 0:
                return hwnd
    except Exception:
        pass
    hwnd = int(window.winfo_id())
    if sys.platform == "win32" and hwnd > 0:
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            get_parent = user32.GetParent
            get_parent.argtypes = [_HANDLE]
            get_parent.restype = _HANDLE
            parent = get_parent(hwnd)
            if parent:
                return int(parent)
        except Exception:
            pass
    return hwnd


def current_process_gdi_objects() -> int | None:
    """Return the current process GDI object count on Windows, or None on other platforms."""
    if sys.platform != "win32":
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_proc = kernel32.GetCurrentProcess
    get_proc.argtypes = []
    get_proc.restype = _HANDLE
    get_gui = user32.GetGuiResources
    get_gui.argtypes = [_HANDLE, _DWORD]
    get_gui.restype = _DWORD
    return int(get_gui(get_proc(), GR_GDIOBJECTS))


class _Win32LayeredBackend:
    """Typed 64-bit Win32 GDI + User32 backend for UpdateLayeredWindow."""

    def __init__(self, user32=None, gdi32=None, *, get_last_error=None, set_last_error=None) -> None:
        self._get_error = get_last_error or ctypes.get_last_error
        self._set_error = set_last_error or ctypes.set_last_error
        self.user32 = user32 if user32 is not None else ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = gdi32 if gdi32 is not None else ctypes.WinDLL("gdi32", use_last_error=True)

        suffix = "LongPtrW" if ctypes.sizeof(_HANDLE) == 8 else "LongW"
        self._get_style = self._bind(
            getattr(self.user32, f"GetWindow{suffix}"),
            [_HANDLE, ctypes.c_int],
            _LONG_PTR,
            self._check_long,
        )
        self._set_style = self._bind(
            getattr(self.user32, f"SetWindow{suffix}"),
            [_HANDLE, ctypes.c_int, _LONG_PTR],
            _LONG_PTR,
            self._check_long,
        )
        self._show = self._bind(self.user32.ShowWindow, [_HANDLE, ctypes.c_int], _BOOL)
        self._set_pos = self._bind(
            self.user32.SetWindowPos,
            [_HANDLE, _HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, _DWORD],
            _BOOL,
            self._check_bool,
        )
        self._update_layered = self._bind(
            self.user32.UpdateLayeredWindow,
            [
                _HANDLE,
                _HANDLE,
                ctypes.POINTER(_POINT),
                ctypes.POINTER(_SIZE),
                _HANDLE,
                ctypes.POINTER(_POINT),
                _DWORD,
                ctypes.POINTER(_BLENDFUNCTION),
                _DWORD,
            ],
            _BOOL,
            self._check_bool,
        )
        self._get_dc = self._bind(self.user32.GetDC, [_HANDLE], _HANDLE, self._check_handle)
        self._release_dc = self._bind(self.user32.ReleaseDC, [_HANDLE, _HANDLE], ctypes.c_int)

        self._create_compat_dc = self._bind(self.gdi32.CreateCompatibleDC, [_HANDLE], _HANDLE, self._check_handle)
        self._delete_dc = self._bind(self.gdi32.DeleteDC, [_HANDLE], _BOOL, self._check_bool)
        self._create_dib = self._bind(
            self.gdi32.CreateDIBSection,
            [
                _HANDLE,
                ctypes.POINTER(_BITMAPINFO),
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
                _HANDLE,
                _DWORD,
            ],
            _HANDLE,
            self._check_handle,
        )
        self._select_obj = self._bind(self.gdi32.SelectObject, [_HANDLE, _HANDLE], _HANDLE, self._check_handle)
        self._delete_obj = self._bind(self.gdi32.DeleteObject, [_HANDLE], _BOOL, self._check_bool)

        self._mem_dc: int = 0
        self._hbmp: int = 0
        self._old_obj: int = 0
        self._bits_ptr: int = 0
        self._dib_size: tuple[int, int] = (0, 0)

    @staticmethod
    def _bind(function, arguments, result, errcheck=None):
        function.argtypes = arguments
        function.restype = result
        if errcheck is not None:
            function.errcheck = errcheck
        return function

    def _native_error(self, function) -> OSError:
        code = self._get_error()
        name = getattr(function, "__name__", "Win32 API")
        return OSError(code, f"{name} failed (Win32 error {code})")

    def _check_bool(self, result, function, arguments):
        if not result:
            raise self._native_error(function)
        return result

    def _check_handle(self, result, function, arguments):
        if not result:
            raise self._native_error(function)
        return int(result)

    def _check_long(self, result, function, arguments):
        if result == 0 and self._get_error() != 0:
            raise self._native_error(function)
        return int(result)

    def get_exstyle(self, hwnd: int) -> int:
        self._set_error(0)
        return int(self._get_style(hwnd, GWL_EXSTYLE))

    def set_exstyle(self, hwnd: int, style: int, *, flush: bool = False) -> int:
        self._set_error(0)
        prev = int(self._set_style(hwnd, GWL_EXSTYLE, style))
        if flush:
            self._set_pos(
                hwnd,
                None,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        return prev

    def ensure_layered_style(self, hwnd: int, *, passthrough: bool, noactivate: bool) -> int:
        style = self.get_exstyle(hwnd)
        target = style | WS_EX_LAYERED
        if noactivate:
            target |= WS_EX_NOACTIVATE
        if passthrough:
            target |= WS_EX_TRANSPARENT
        else:
            target &= ~WS_EX_TRANSPARENT
        if target != style:
            self.set_exstyle(hwnd, target, flush=True)
        return target

    def clear_layered_style(self, hwnd: int) -> int:
        style = self.get_exstyle(hwnd)
        target = style & ~(WS_EX_LAYERED | WS_EX_TRANSPARENT)
        if target != style:
            self.set_exstyle(hwnd, target, flush=True)
        return target

    def _release_dib(self) -> None:
        if self._mem_dc and self._old_obj:
            try:
                self._select_obj(self._mem_dc, self._old_obj)
            except OSError:
                pass
            self._old_obj = 0
        if self._hbmp:
            try:
                self._delete_obj(self._hbmp)
            except OSError:
                pass
            self._hbmp = 0
        self._bits_ptr = 0
        self._dib_size = (0, 0)

    def _ensure_dib(self, width: int, height: int) -> None:
        if not self._mem_dc:
            self._mem_dc = int(self._create_compat_dc(None))
        if self._hbmp and self._dib_size == (width, height) and self._bits_ptr:
            return
        self._release_dib()
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = width * height * 4
        bits = ctypes.c_void_p()
        hbmp = int(self._create_dib(self._mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0))
        if not bits.value:
            self._delete_obj(hbmp)
            raise OSError("CreateDIBSection returned NULL pixel buffer")
        try:
            old = int(self._select_obj(self._mem_dc, hbmp))
        except Exception:
            self._delete_obj(hbmp)
            raise
        self._hbmp = hbmp
        self._old_obj = old
        self._bits_ptr = int(bits.value)
        self._dib_size = (width, height)

    def present(
        self,
        hwnd: int,
        bgra_bytes: bytes,
        width: int,
        height: int,
        x: int,
        y: int,
        alpha_byte: int,
    ) -> None:
        byte_len = width * height * 4
        if len(bgra_bytes) != byte_len:
            raise ValueError(f"expected {byte_len} premultiplied BGRA bytes, got {len(bgra_bytes)}")
        self._ensure_dib(width, height)
        ctypes.memmove(self._bits_ptr, bgra_bytes, byte_len)
        pt_dst = _POINT(int(x), int(y))
        size = _SIZE(int(width), int(height))
        pt_src = _POINT(0, 0)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, int(alpha_byte) & 0xFF, AC_SRC_ALPHA)
        self._update_layered(
            hwnd,
            None,
            ctypes.byref(pt_dst),
            ctypes.byref(size),
            self._mem_dc,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

    def move(self, hwnd: int, x: int, y: int) -> None:
        pt_dst = _POINT(int(x), int(y))
        self._update_layered(
            hwnd,
            None,
            ctypes.byref(pt_dst),
            None,
            None,
            None,
            0,
            None,
            0,
        )

    def set_opacity(
        self,
        hwnd: int,
        alpha_byte: int,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> None:
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, int(alpha_byte) & 0xFF, AC_SRC_ALPHA)
        try:
            self._update_layered(
                hwnd,
                None,
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )
        except OSError:
            if not self._mem_dc or width <= 0 or height <= 0:
                raise
            pt_dst = _POINT(int(x), int(y))
            size = _SIZE(int(width), int(height))
            pt_src = _POINT(0, 0)
            self._update_layered(
                hwnd,
                None,
                ctypes.byref(pt_dst),
                ctypes.byref(size),
                self._mem_dc,
                ctypes.byref(pt_src),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )

    def set_visibility(
        self,
        hwnd: int,
        visible: bool,
        *,
        topmost: bool = True,
        reorder: bool = True,
    ) -> None:
        if visible:
            self._show(hwnd, SW_SHOWNOACTIVATE)
            if topmost and reorder:
                self._set_pos(
                    hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
        else:
            self._show(hwnd, SW_HIDE)

    def close(self) -> None:
        self._release_dib()
        if self._mem_dc:
            try:
                self._delete_dc(self._mem_dc)
            except OSError:
                pass
            self._mem_dc = 0


class _HeadlessLayeredBackend:
    """In-memory backend for non-Win32 platforms or headless unit tests."""

    def __init__(self) -> None:
        self.exstyle: int = 0
        self.last_bgra: bytes = b""
        self.dib_size: tuple[int, int] = (0, 0)
        self.dib_allocations: int = 0
        self.present_count: int = 0
        self.move_count: int = 0
        self.opacity_update_count: int = 0
        self.last_alpha_byte: int = 255
        self.last_reorder: bool = True
        self.visible: bool = False
        self.closed: bool = False

    def get_exstyle(self, hwnd: int) -> int:
        return self.exstyle

    def set_exstyle(self, hwnd: int, style: int, *, flush: bool = False) -> int:
        prev = self.exstyle
        self.exstyle = int(style)
        return prev

    def ensure_layered_style(self, hwnd: int, *, passthrough: bool, noactivate: bool) -> int:
        target = self.exstyle | WS_EX_LAYERED
        if noactivate:
            target |= WS_EX_NOACTIVATE
        if passthrough:
            target |= WS_EX_TRANSPARENT
        else:
            target &= ~WS_EX_TRANSPARENT
        self.exstyle = target
        return target

    def clear_layered_style(self, hwnd: int) -> int:
        target = self.exstyle & ~(WS_EX_LAYERED | WS_EX_TRANSPARENT)
        self.exstyle = target
        return target

    def present(
        self,
        hwnd: int,
        bgra_bytes: bytes,
        width: int,
        height: int,
        x: int,
        y: int,
        alpha_byte: int,
    ) -> None:
        if self.dib_size != (width, height):
            self.dib_size = (width, height)
            self.dib_allocations += 1
        self.last_bgra = bgra_bytes
        self.last_alpha_byte = int(alpha_byte) & 0xFF
        self.present_count += 1

    def move(self, hwnd: int, x: int, y: int) -> None:
        self.move_count += 1

    def set_opacity(
        self,
        hwnd: int,
        alpha_byte: int,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> None:
        self.last_alpha_byte = int(alpha_byte) & 0xFF
        self.opacity_update_count += 1

    def set_visibility(
        self,
        hwnd: int,
        visible: bool,
        *,
        topmost: bool = True,
        reorder: bool = True,
    ) -> None:
        self.visible = bool(visible)
        self.last_reorder = bool(reorder)

    def close(self) -> None:
        self.last_bgra = b""
        self.dib_size = (0, 0)
        self.closed = True


class LayeredSpriteSurface:
    """Per-pixel alpha sprite surface driven by Win32 UpdateLayeredWindow (ULW_ALPHA)."""

    def __init__(
        self,
        window: Any,
        *,
        x: int = 0,
        y: int = 0,
        opacity: float = 1.0,
        input_policy: InputPolicy = "interactive",
        noactivate: bool = True,
        topmost: bool = True,
        backend: Any | None = None,
    ) -> None:
        if input_policy not in ("interactive", "passthrough"):
            raise ValueError(f"input_policy must be 'interactive' or 'passthrough', got {input_policy!r}")
        self._window = window
        self._hwnd = resolve_window_hwnd(window)
        self._x = int(x)
        self._y = int(y)
        self._width = 0
        self._height = 0
        self._opacity = self._clamp_opacity(opacity)
        self._input_policy: InputPolicy = input_policy
        self._noactivate = bool(noactivate)
        self._topmost = bool(topmost)
        self._visible = False
        self._closed = False
        self._has_frame = False

        if backend is not None:
            self._backend = backend
        elif sys.platform == "win32":
            self._backend = _Win32LayeredBackend()
        else:
            self._backend = _HeadlessLayeredBackend()

        self._backend.ensure_layered_style(
            self._hwnd,
            passthrough=(self._input_policy == "passthrough"),
            noactivate=self._noactivate,
        )

    @staticmethod
    def _clamp_opacity(opacity: float) -> float:
        val = float(opacity)
        if val < 0.0:
            return 0.0
        if val > 1.0:
            return 1.0
        return val

    @property
    def hwnd(self) -> int:
        return self._hwnd

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def geometry_box(self) -> tuple[int, int, int, int]:
        """Authoritative (x, y, width, height) in screen coordinates."""
        return (self._x, self._y, self._width, self._height)

    @property
    def opacity(self) -> float:
        return self._opacity

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def input_policy(self) -> InputPolicy:
        return self._input_policy

    @property
    def closed(self) -> bool:
        return self._closed

    def present(
        self,
        image: Image.Image,
        *,
        x: int | None = None,
        y: int | None = None,
        opacity: float | None = None,
    ) -> None:
        """Convert RGBA PIL image to premultiplied BGRA and composite via ULW_ALPHA."""
        if self._closed:
            raise RuntimeError("LayeredSpriteSurface is closed")
        if x is not None:
            self._x = int(x)
        if y is not None:
            self._y = int(y)
        if opacity is not None:
            self._opacity = self._clamp_opacity(opacity)

        bgra, w, h = premultiply_rgba_to_bgra(image)
        alpha_byte = round(self._opacity * 255.0)
        self._backend.present(self._hwnd, bgra, w, h, self._x, self._y, alpha_byte)
        self._width = w
        self._height = h
        self._has_frame = True

    def move(self, x: int, y: int) -> None:
        """Move the layered window without rebuilding or re-uploading the DIBSection."""
        if self._closed:
            raise RuntimeError("LayeredSpriteSurface is closed")
        self._x = int(x)
        self._y = int(y)
        if self._has_frame:
            self._backend.move(self._hwnd, self._x, self._y)

    def set_opacity(self, opacity: float) -> None:
        """Update BLENDFUNCTION.SourceConstantAlpha without re-uploading the DIBSection."""
        if self._closed:
            raise RuntimeError("LayeredSpriteSurface is closed")
        self._opacity = self._clamp_opacity(opacity)
        if self._has_frame:
            alpha_byte = round(self._opacity * 255.0)
            self._backend.set_opacity(
                self._hwnd,
                alpha_byte,
                self._x,
                self._y,
                self._width,
                self._height,
            )

    def set_input_policy(self, policy: InputPolicy) -> None:
        """Switch between 'interactive' (alpha hit-tested) and 'passthrough' (WS_EX_TRANSPARENT)."""
        if self._closed:
            raise RuntimeError("LayeredSpriteSurface is closed")
        if policy not in ("interactive", "passthrough"):
            raise ValueError(f"input_policy must be 'interactive' or 'passthrough', got {policy!r}")
        self._input_policy = policy
        self._backend.ensure_layered_style(
            self._hwnd,
            passthrough=(policy == "passthrough"),
            noactivate=self._noactivate,
        )

    def set_visibility(self, visible: bool, *, reorder: bool = True) -> None:
        """Show (SW_SHOWNOACTIVATE + optional TOPMOST reorder) or hide (SW_HIDE) the layered window."""
        if self._closed:
            raise RuntimeError("LayeredSpriteSurface is closed")
        self._visible = bool(visible)
        if self._visible:
            self._backend.ensure_layered_style(
                self._hwnd,
                passthrough=(self._input_policy == "passthrough"),
                noactivate=self._noactivate,
            )
        self._backend.set_visibility(
            self._hwnd,
            self._visible,
            topmost=self._topmost,
            reorder=bool(reorder),
        )

    def close(self, *, clear_exstyle: bool = False) -> None:
        """Deterministically release GDI DIBSection and memory DC; idempotent."""
        if clear_exstyle:
            try:
                clear_fn = getattr(self._backend, "clear_layered_style", None)
                if clear_fn is not None:
                    clear_fn(self._hwnd)
            except Exception:
                LOGGER.debug("LayeredSpriteSurface clear_layered_style failed", exc_info=True)
        if self._closed:
            return
        self._closed = True
        self._visible = False
        try:
            self._backend.close()
        except Exception:
            LOGGER.debug("LayeredSpriteSurface backend close failed", exc_info=True)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
