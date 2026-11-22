"""Typed Win32 desktop boundary; importing this module never touches a window.

Coordinates must share the caller's DPI-awareness context. This adapter does not
change process DPI policy. Supply actual fallback_bounds from Tk on platforms or
systems where monitor enumeration is unavailable. No taskbar size is assumed.
"""
from __future__ import annotations

from collections.abc import Callable
import ctypes
from dataclasses import dataclass
import logging
import sys

LOGGER = logging.getLogger(__name__)
GWL_EXSTYLE = -20


def ui_scale(widget) -> float:
    """Scale 96-DPI pixel dimensions to Tk's active DPI, clamped to [1.0, 4.0]."""
    return max(1.0, min(4.0, widget.winfo_fpixels("1i") / 96.0))


def scale_canvas(canvas, scale: float) -> None:
    """Scale every item on a Tk Canvas built in 96-DPI design pixels by *scale*."""
    if abs(scale - 1.0) < 1e-4:
        return
    canvas.scale("all", 0, 0, scale, scale)
    for item in canvas.find_all():
        kind = canvas.type(item)
        if kind in ("polygon", "line", "rectangle", "oval", "arc"):
            raw = canvas.itemcget(item, "width")
            if raw:
                w = float(raw)
                if w > 0:
                    canvas.itemconfigure(item, width=w * scale)
        elif kind == "text":
            raw = canvas.itemcget(item, "width")
            if raw:
                w = float(raw)
                if w > 0:
                    canvas.itemconfigure(item, width=w * scale)
WS_EX_NOACTIVATE = 0x08000000
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOCOPYBITS = 0x0100


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("desktop rectangle must have positive dimensions")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def clamp(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        """Keep a fitting window inside; pin oversized axes to the area's origin."""
        if width < 0 or height < 0:
            raise ValueError("window dimensions cannot be negative")
        return (min(max(x, self.left), max(self.left, self.right - width)),
                min(max(y, self.top), max(self.top, self.bottom - height)))

    def _distance_squared(self, x: int, y: int) -> int:
        # RECT uses exclusive right/bottom; this also resolves shared-edge points.
        dx = max(self.left - x, 0, x - (self.right - 1))
        dy = max(self.top - y, 0, y - (self.bottom - 1))
        return dx * dx + dy * dy


# Fixed-width Windows scalars keep structures correct even in non-Windows tests.
_BOOL = ctypes.c_int32
_DWORD = ctypes.c_uint32
_LONG = ctypes.c_int32
_LONG_PTR = ctypes.c_ssize_t
_HANDLE = ctypes.c_void_p


class _RECT(ctypes.Structure):
    _fields_ = [(key, _LONG) for key in ("left", "top", "right", "bottom")]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", _DWORD), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", _DWORD)]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", _DWORD), ("dwTime", _DWORD)]


_MonitorCallback = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    _BOOL, _HANDLE, _HANDLE, ctypes.POINTER(_RECT), _LONG_PTR)


class _CtypesWin32Backend:
    """Raw APIs may be injected for tests; each callable supports ctypes attributes."""

    def __init__(self, user32=None, kernel32=None, *, get_last_error=None, set_last_error=None):
        self._get_error = get_last_error or ctypes.get_last_error
        self._set_error = set_last_error or ctypes.set_last_error
        self.user32 = user32 if user32 is not None else ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = kernel32 if kernel32 is not None else ctypes.WinDLL("kernel32", use_last_error=True)
        self._enum = self._bind(self.user32.EnumDisplayMonitors,
                                [_HANDLE, ctypes.POINTER(_RECT), _MonitorCallback, _LONG_PTR],
                                _BOOL, self._check_bool)
        self._monitor_info = self._bind(self.user32.GetMonitorInfoW,
                                       [_HANDLE, ctypes.POINTER(_MONITORINFO)], _BOOL, self._check_bool)
        # ShowWindow's BOOL means previous visibility, not success/failure.
        self._show = self._bind(self.user32.ShowWindow, [_HANDLE, ctypes.c_int], _BOOL)
        self._position = self._bind(self.user32.SetWindowPos,
                                   [_HANDLE, _HANDLE, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint32], _BOOL, self._check_bool)
        suffix = "LongPtrW" if ctypes.sizeof(_HANDLE) == 8 else "LongW"
        self._get_style = self._bind(getattr(self.user32, f"GetWindow{suffix}"),
                                    [_HANDLE, ctypes.c_int], _LONG_PTR, self._check_long)
        self._set_style = self._bind(getattr(self.user32, f"SetWindow{suffix}"),
                                    [_HANDLE, ctypes.c_int, _LONG_PTR], _LONG_PTR, self._check_long)
        self._last_input = self._bind(self.user32.GetLastInputInfo,
                                     [ctypes.POINTER(_LASTINPUTINFO)], _BOOL, self._check_bool)
        self._ticks = self._bind(self.kernel32.GetTickCount, [], _DWORD)

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

    def _check_long(self, result, function, arguments):
        if result == 0 and self._get_error() != 0:
            raise self._native_error(function)
        return result

    def enumerate_monitors(self) -> tuple[tuple[WorkArea, WorkArea], ...]:
        monitors: list[tuple[WorkArea, WorkArea]] = []
        failures: list[Exception] = []

        @_MonitorCallback
        def visit(monitor, device_context, rect, data):
            try:
                info = _MONITORINFO()
                info.cbSize = ctypes.sizeof(info)
                self._monitor_info(monitor, ctypes.byref(info))
                def area(rectangle):
                    return WorkArea(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)
                monitors.append((area(info.rcMonitor), area(info.rcWork)))
                return 1
            except Exception as error:
                # ctypes callbacks cannot propagate exceptions through native frames.
                failures.append(error)
                return 0

        self._set_error(0)
        try:
            self._enum(None, None, visit, 0)
        except OSError as error:
            if failures:
                raise failures[0] from error
            raise
        if failures:
            raise failures[0]
        if not monitors:
            raise OSError("EnumDisplayMonitors returned no monitors")
        return tuple(monitors)

    def show_without_activation(self, hwnd: int) -> None:
        self._show(hwnd, SW_SHOWNOACTIVATE)
        self._position(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                       SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def position_without_activation(self, hwnd: int, x: int, y: int) -> None:
        self._position(hwnd, HWND_TOPMOST, x, y, 0, 0,
                       SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOCOPYBITS)

    def set_noactivate(self, hwnd: int) -> None:
        self._set_error(0)
        style = self._get_style(hwnd, GWL_EXSTYLE)
        if style & WS_EX_NOACTIVATE:
            return
        self._set_error(0)
        self._set_style(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        # Flush cached style without moving, resizing, activating or reordering.
        self._position(hwnd, None, 0, 0, 0, 0,
                       SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def idle_seconds(self) -> float:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        self._last_input(ctypes.byref(info))
        return ((self._ticks() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def is_workstation_locked() -> bool | None:
    """True while input belongs to the secure desktop (lock screen), None when unknown.

    The lock screen runs on the Winlogon desktop, which this process cannot open, so
    the input desktop is either unavailable or not named "Default". WTSINFOEX's
    SessionFlags was tried first and reported "locked" on an unlocked Windows 11.
    Never raises.
    """
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        open_input = user32.OpenInputDesktop
        open_input.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_input.restype = ctypes.c_void_p
        get_info = user32.GetUserObjectInformationW
        get_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                             ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        get_info.restype = ctypes.c_int
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
        user32.CloseDesktop.restype = ctypes.c_int
        desktop = open_input(0, False, 0x0001)          # DESKTOP_READOBJECTS
        if not desktop:
            return True
        try:
            name = ctypes.create_unicode_buffer(64)
            needed = ctypes.c_uint32()
            if not get_info(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed)):  # UOI_NAME
                return None
            return name.value.lower() != "default"
        finally:
            user32.CloseDesktop(desktop)
    except Exception:
        LOGGER.debug("lock state probe failed", exc_info=True)
        return None


class WindowsDesktopAdapter:
    """Errors are logged and appended to error_events; mutation methods return bool.

    The optional backend implements enumerate_monitors() -> ((bounds, work), ...),
    show_without_activation(hwnd), set_noactivate(hwnd), and idle_seconds(). Only
    pass window handles owned by the caller. A successful API call does not prove
    foreground behavior on a real desktop; native integration needs separate QA.
    """

    def __init__(self, *, backend=None,
                 fallback_bounds: WorkArea | Callable[[], WorkArea] | None = None):
        self.error_events: list[str] = []
        self._fallback = fallback_bounds
        self._backend = backend
        if backend is None and sys.platform == "win32":
            try:
                self._backend = _CtypesWin32Backend()
            except (OSError, AttributeError) as error:
                self._report("initialize", error)

    def _report(self, operation: str, error: Exception) -> None:
        message = f"{operation}: {error}"
        self.error_events.append(message)
        del self.error_events[:-128]
        LOGGER.warning(message)

    def _monitors(self) -> tuple[tuple[WorkArea, WorkArea], ...]:
        if self._backend is not None:
            try:
                monitors = tuple(self._backend.enumerate_monitors())
                if not monitors:
                    raise OSError("no monitors returned")
                return monitors
            except (OSError, ValueError) as error:
                self._report("enumerate_monitors", error)
        if self._fallback is None:
            raise RuntimeError("Monitor enumeration unavailable; supply fallback_bounds")
        fallback = self._fallback() if callable(self._fallback) else self._fallback
        if not isinstance(fallback, WorkArea):
            raise TypeError("fallback_bounds must provide a WorkArea")
        return ((fallback, fallback),)

    def enumerate_work_areas(self) -> tuple[WorkArea, ...]:
        return tuple(work for bounds, work in self._monitors())

    def work_area_for_point(self, x: int, y: int) -> WorkArea:
        # Select by full monitor bounds, even for a point over its taskbar.
        return min(self._monitors(), key=lambda pair: pair[0]._distance_squared(x, y))[1]

    def enumerate_monitor_bounds(self) -> tuple[WorkArea, ...]:
        """Full bounds (incl. taskbar) of every monitor."""
        return tuple(bounds for bounds, work in self._monitors())

    def monitor_bounds_for_point(self, x: int, y: int) -> WorkArea:
        """Full nearest monitor bounds, including its taskbar (for standby)."""
        return min(self._monitors(), key=lambda pair: pair[0]._distance_squared(x, y))[0]

    def clamp(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        return self.work_area_for_point(x, y).clamp(x, y, width, height)

    def _window_operation(self, operation: str, hwnd: int, *arguments) -> bool:
        if not isinstance(hwnd, int) or isinstance(hwnd, bool) or hwnd <= 0:
            raise ValueError("hwnd must be a positive native window handle")
        if self._backend is None:
            self._report(operation, OSError("Win32 backend unavailable"))
            return False
        try:
            getattr(self._backend, operation)(hwnd, *arguments)
            return True
        except OSError as error:
            self._report(operation, error)
            return False

    def show_without_activation(self, hwnd: int) -> bool:
        return self._window_operation("show_without_activation", hwnd)

    def set_noactivate(self, hwnd: int) -> bool:
        return self._window_operation("set_noactivate", hwnd)

    def position_without_activation(self, hwnd: int, x: int, y: int) -> bool:
        """Move to absolute desktop coordinates, including negative monitor origins."""
        return self._window_operation("position_without_activation", hwnd, x, y)

    def idle_seconds(self) -> float | None:
        if self._backend is None:
            return None
        try:
            return self._backend.idle_seconds()
        except OSError as error:
            self._report("idle_seconds", error)
            return None
