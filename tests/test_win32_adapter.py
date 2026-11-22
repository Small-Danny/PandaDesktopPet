"""Injected Win32 calls only: tests never mutate real desktop windows."""
from __future__ import annotations

import ctypes
import unittest
from unittest.mock import patch

from app.platform import win32
from app.platform.win32 import WindowsDesktopAdapter, WorkArea


class FakeFunction:
    def __init__(self, name, handler):
        self.__name__ = name
        self.handler = handler
        self.calls = []

    def __call__(self, *arguments):
        self.calls.append(arguments)
        result = self.handler(*arguments)
        checker = getattr(self, "errcheck", None)
        return checker(result, self, arguments) if checker else result


class FakeNative:
    def __init__(self):
        self.error = 0
        self.fail = set()
        self.style = 0
        self.tick = 20
        self.input_tick = 0xFFFFFFF0
        self.info_sizes = []
        self.monitors = [
            (WorkArea(-1920, -200, 0, 1000), WorkArea(-1920, -160, 0, 960)),
            (WorkArea(0, 0, 1920, 1080), WorkArea(0, 0, 1920, 1040)),
        ]
        for name, handler in (
            ("EnumDisplayMonitors", self.enumerate), ("GetMonitorInfoW", self.monitor_info),
            ("ShowWindow", lambda *args: 0), ("SetWindowPos", lambda *args: 1),
            ("GetWindowLongPtrW", lambda *args: self.style),
            ("SetWindowLongPtrW", self.set_style),
            ("GetLastInputInfo", self.last_input), ("GetTickCount", lambda: self.tick),
        ):
            def wrapped(*args, operation=name, implementation=handler):
                if operation in self.fail:
                    self.error = 5
                    return 0
                return implementation(*args)
            setattr(self, name, FakeFunction(name, wrapped))
        # Same fake supports the 32-bit export names.
        self.GetWindowLongW = self.GetWindowLongPtrW
        self.SetWindowLongW = self.SetWindowLongPtrW

    def enumerate(self, hdc, clipping, callback, data):
        for index in range(len(self.monitors)):
            rect = win32._RECT()
            if not callback(0x100000000 + index, None, ctypes.byref(rect), data):
                return 0
        return 1

    def monitor_info(self, handle, info_pointer):
        info = ctypes.cast(info_pointer, ctypes.POINTER(win32._MONITORINFO)).contents
        self.info_sizes.append(info.cbSize)
        bounds, work = self.monitors[handle - 0x100000000]
        for target, area in ((info.rcMonitor, bounds), (info.rcWork, work)):
            for key in ("left", "top", "right", "bottom"):
                setattr(target, key, getattr(area, key))
        return 1

    def set_style(self, hwnd, index, value):
        previous = self.style
        self.style = value
        return previous

    def last_input(self, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(win32._LASTINPUTINFO)).contents
        self.input_size = info.cbSize
        info.dwTime = self.input_tick
        return 1

    def backend(self):
        return win32._CtypesWin32Backend(
            self, self, get_last_error=lambda: self.error,
            set_last_error=lambda value: setattr(self, "error", value))


class WorkAreaTests(unittest.TestCase):
    def test_geometry_and_negative_origin_clamping(self):
        area = WorkArea(-1920, -160, 0, 960)
        self.assertEqual((area.width, area.height), (1920, 1120))
        self.assertEqual(area.clamp(-2000, -300, 192, 192), (-1920, -160))
        self.assertEqual(area.clamp(10, 980, 192, 192), (-192, 768))
        self.assertEqual(area.clamp(-500, 300, 192, 192), (-500, 300))

    def test_oversized_axes_pin_independently(self):
        area = WorkArea(-100, -50, 100, 100)
        self.assertEqual(area.clamp(30, 20, 300, 20), (-100, 20))
        self.assertEqual(area.clamp(30, 20, 20, 300), (30, -50))
        self.assertEqual(area.clamp(30, 20, 300, 300), (-100, -50))
        self.assertEqual(area.clamp(300, 300, 0, 0), (100, 100))

    def test_invalid_geometry_raises(self):
        with self.assertRaises(ValueError):
            WorkArea(0, 0, 0, 20)
        with self.assertRaises(ValueError):
            WorkArea(0, 20, 20, 0)
        with self.assertRaises(ValueError):
            WorkArea(0, 0, 20, 20).clamp(0, 0, -1, 5)


class Win32AdapterTests(unittest.TestCase):
    def test_full_monitor_bounds_include_taskbar_and_negative_origin(self):
        self.assertEqual(self.adapter.monitor_bounds_for_point(-1900,-190),self.native.monitors[0][0])
        self.assertEqual(self.adapter.monitor_bounds_for_point(1900,1070),WorkArea(0,0,1920,1080))
        self.assertEqual(self.adapter.work_area_for_point(1900,1070).bottom,1040)

    def test_noactivate_already_present_skips_write_and_frame_change(self):
        self.native.style = win32.WS_EX_NOACTIVATE | 0x80
        self.assertTrue(self.adapter.set_noactivate(123))
        self.assertEqual(self.native.SetWindowLongPtrW.calls,[])
        self.assertEqual(self.native.SetWindowPos.calls,[])

    def setUp(self):
        self.native = FakeNative()
        self.backend = self.native.backend()
        self.fallback = WorkArea(0, 0, 640, 480)
        self.adapter = WindowsDesktopAdapter(backend=self.backend, fallback_bounds=self.fallback)

    def test_monitor_enumeration_uses_work_rectangles_and_cbsize(self):
        expected = tuple(work for bounds, work in self.native.monitors)
        self.assertEqual(self.adapter.enumerate_work_areas(), expected)
        self.assertEqual(self.native.info_sizes, [40, 40])

    def test_nearest_monitor_and_negative_top(self):
        self.assertEqual(self.adapter.work_area_for_point(-1900, -190), self.native.monitors[0][1])
        self.assertEqual(self.adapter.work_area_for_point(9000, -500), self.native.monitors[1][1])
        self.assertEqual(self.adapter.work_area_for_point(-5000, 5000), self.native.monitors[0][1])
        self.assertEqual(self.adapter.clamp(-1900, -190, 192, 192), (-1900, -160))

    def test_monitor_selection_uses_full_bounds_over_taskbar(self):
        self.native.monitors = [
            (WorkArea(0, 0, 100, 100), WorkArea(0, 0, 100, 70)),
            (WorkArea(0, 100, 100, 200), WorkArea(0, 100, 100, 200)),
        ]
        self.assertEqual(self.adapter.work_area_for_point(50, 99), WorkArea(0, 0, 100, 70))
        self.assertEqual(self.adapter.work_area_for_point(50, 100), WorkArea(0, 100, 100, 200))

    def test_enumeration_failure_reports_and_uses_injected_fallback(self):
        self.native.fail.add("EnumDisplayMonitors")
        with self.assertLogs("app.platform.win32", level="WARNING"):
            self.assertEqual(self.adapter.enumerate_work_areas(), (self.fallback,))
        self.assertIn("Win32 error 5", self.adapter.error_events[-1])

    def test_callback_failure_is_observable_and_partial_results_are_discarded(self):
        self.native.fail.add("GetMonitorInfoW")
        with self.assertLogs("app.platform.win32", level="WARNING"):
            self.assertEqual(self.adapter.enumerate_work_areas(), (self.fallback,))
        self.assertIn("GetMonitorInfoW", self.adapter.error_events[-1])

    def test_empty_native_monitor_list_falls_back(self):
        self.native.monitors = []
        with self.assertLogs("app.platform.win32", level="WARNING"):
            self.assertEqual(self.adapter.enumerate_work_areas(), (self.fallback,))

    def test_nonwindows_fallback_is_live_and_missing_fallback_is_explicit(self):
        with patch.object(win32.sys, "platform", "linux"):
            areas = iter([WorkArea(-300, 0, 0, 200), self.fallback])
            adapter = WindowsDesktopAdapter(fallback_bounds=lambda: next(areas))
            self.assertEqual(adapter.enumerate_work_areas(), (WorkArea(-300, 0, 0, 200),))
            self.assertEqual(adapter.enumerate_work_areas(), (self.fallback,))
            with self.assertRaises(RuntimeError):
                WindowsDesktopAdapter().enumerate_work_areas()
            with self.assertLogs("app.platform.win32", level="WARNING"):
                self.assertFalse(adapter.show_without_activation(5))
            self.assertIsNone(adapter.idle_seconds())

    def test_typed_signatures_use_pointer_sized_handles_and_long_ptr(self):
        self.assertEqual(self.native.SetWindowPos.argtypes[:2], [ctypes.c_void_p] * 2)
        self.assertEqual(self.native.GetWindowLongPtrW.restype, ctypes.c_ssize_t)
        self.assertEqual(self.native.SetWindowLongPtrW.argtypes[-1], ctypes.c_ssize_t)
        self.assertEqual(ctypes.sizeof(win32._MONITORINFO), 40)
        self.assertEqual(ctypes.sizeof(win32._LASTINPUTINFO), 8)
        self.assertTrue(callable(self.native.SetWindowPos.errcheck))

    def test_show_hidden_window_zero_return_is_not_an_error(self):
        handle = 0x123456789
        self.assertTrue(self.adapter.show_without_activation(handle))
        self.assertEqual(self.native.ShowWindow.calls, [(handle, win32.SW_SHOWNOACTIVATE)])
        self.assertEqual(self.native.SetWindowPos.calls[-1],
                         (handle, win32.HWND_TOPMOST, 0, 0, 0, 0,
                          win32.SWP_NOMOVE | win32.SWP_NOSIZE | win32.SWP_NOACTIVATE))

    def test_absolute_position_accepts_negative_monitor_coordinates(self):
        self.assertTrue(self.adapter.position_without_activation(0x123456789, -1800, -150))
        self.assertEqual(self.native.SetWindowPos.calls[-1],
                         (0x123456789, win32.HWND_TOPMOST, -1800, -150, 0, 0,
                          win32.SWP_NOSIZE | win32.SWP_NOACTIVATE | win32.SWP_NOCOPYBITS))

    def test_noactivate_preserves_other_bits_without_enabling_clickthrough(self):
        old = (1 << 40) | 0x00080000  # Sentinel above 32 bits plus layered style.
        self.native.style = old
        self.assertTrue(self.adapter.set_noactivate(0x123456789))
        self.assertEqual(self.native.style, old | win32.WS_EX_NOACTIVATE)
        self.assertEqual(self.native.style & 0x20, 0)  # WS_EX_TRANSPARENT stays absent.
        self.assertEqual(self.native.SetWindowPos.calls[-1][-1],
                         win32.SWP_NOMOVE | win32.SWP_NOSIZE | win32.SWP_NOZORDER
                         | win32.SWP_NOACTIVATE | win32.SWP_FRAMECHANGED)

    def test_zero_style_and_zero_previous_style_clear_stale_errors(self):
        self.native.error = 999
        self.assertTrue(self.adapter.set_noactivate(1))
        self.assertEqual(self.native.style, win32.WS_EX_NOACTIVATE)
        self.assertEqual(self.native.error, 0)

    def test_style_and_position_errors_are_reported(self):
        for function in ("GetWindowLongPtrW", "SetWindowLongPtrW", "SetWindowPos"):
            with self.subTest(function=function):
                self.native.fail = {function}
                with self.assertLogs("app.platform.win32", level="WARNING"):
                    self.assertFalse(self.adapter.set_noactivate(1))
                self.assertIn(function, self.adapter.error_events[-1])

    def test_show_and_absolute_position_errors_are_reported(self):
        self.native.fail.add("SetWindowPos")
        with self.assertLogs("app.platform.win32", level="WARNING"):
            self.assertFalse(self.adapter.show_without_activation(1))
            self.assertFalse(self.adapter.position_without_activation(1, -100, 20))
        self.assertEqual(len(self.adapter.error_events), 2)

    def test_idle_elapsed_is_unsigned_tick_rollover_safe(self):
        self.assertAlmostEqual(self.adapter.idle_seconds(), 0.036)
        self.assertEqual(self.native.input_size, 8)
        self.native.input_tick = 2000
        self.native.tick = 5000
        self.assertEqual(self.adapter.idle_seconds(), 3.0)

    def test_idle_failure_is_reported(self):
        self.native.fail.add("GetLastInputInfo")
        with self.assertLogs("app.platform.win32", level="WARNING"):
            self.assertIsNone(self.adapter.idle_seconds())
        self.assertIn("GetLastInputInfo", self.adapter.error_events[-1])

    def test_invalid_handles_rejected_before_native_calls(self):
        for handle in (0, -1, True, "123"):
            with self.subTest(handle=handle), self.assertRaises(ValueError):
                self.adapter.show_without_activation(handle)
        self.assertEqual(self.native.ShowWindow.calls, [])


if __name__ == "__main__":
    unittest.main()
