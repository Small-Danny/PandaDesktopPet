"""tests/test_layered_surface.py — Stage 1 verification for LayeredSpriteSurface (Win32 ULW_ALPHA)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.platform.layered_surface import (  # noqa: E402
    AC_SRC_ALPHA,
    AC_SRC_OVER,
    BI_RGB,
    DIB_RGB_COLORS,
    LayeredSpriteSurface,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    _BITMAPINFO,
    _BITMAPINFOHEADER,
    _BLENDFUNCTION,
    _HeadlessLayeredBackend,
    _Win32LayeredBackend,
    current_process_gdi_objects,
    premultiply_rgba_to_bgra,
)


class LayeredSpriteSurfaceUnitTests(unittest.TestCase):
    def test_premultiply_rgba_to_bgra_exact_values(self) -> None:
        img = Image.new("RGBA", (3, 1))
        img.putpixel((0, 0), (255, 0, 128, 255))   # fully opaque
        img.putpixel((1, 0), (200, 100, 50, 128))  # 50% alpha
        img.putpixel((2, 0), (255, 255, 255, 0))   # transparent
        bgra, w, h = premultiply_rgba_to_bgra(img)
        self.assertEqual((w, h), (3, 1))
        self.assertEqual(len(bgra), 12)
        # Pixel 0: B=128, G=0, R=255, A=255
        self.assertEqual(tuple(bgra[0:4]), (128, 0, 255, 255))
        # Pixel 1: premultiplied ~ (25, 50, 100, 128)
        b1, g1, r1, a1 = bgra[4:8]
        self.assertEqual(a1, 128)
        self.assertAlmostEqual(r1, 100, delta=1)
        self.assertAlmostEqual(g1, 50, delta=1)
        self.assertAlmostEqual(b1, 25, delta=1)
        # Pixel 2: premultiplied zero
        self.assertEqual(tuple(bgra[8:12]), (0, 0, 0, 0))

    def test_headless_backend_lifecycle_and_state(self) -> None:
        backend = _HeadlessLayeredBackend()
        surf = LayeredSpriteSurface(
            12345,
            x=100,
            y=200,
            opacity=0.8,
            input_policy="interactive",
            backend=backend,
        )
        self.assertEqual(surf.hwnd, 12345)
        self.assertTrue(backend.exstyle & WS_EX_LAYERED)
        self.assertTrue(backend.exstyle & WS_EX_NOACTIVATE)
        self.assertFalse(backend.exstyle & WS_EX_TRANSPARENT)

        im1 = Image.new("RGBA", (144, 144), (255, 100, 150, 200))
        surf.present(im1)
        self.assertEqual(surf.geometry_box, (100, 200, 144, 144))
        self.assertEqual(backend.dib_allocations, 1)

        # Second present at same size reuses DIB allocation
        surf.present(im1, x=120, y=220, opacity=0.5)
        self.assertEqual(surf.geometry_box, (120, 220, 144, 144))
        self.assertAlmostEqual(surf.opacity, 0.5)
        self.assertEqual(backend.dib_allocations, 1)

        # Move updates coordinates without re-uploading DIB
        surf.move(-350, 480)
        self.assertEqual(surf.geometry_box, (-350, 480, 144, 144))
        self.assertEqual(backend.move_count, 1)

        # Toggle input policy
        surf.set_input_policy("passthrough")
        self.assertEqual(surf.input_policy, "passthrough")
        self.assertTrue(backend.exstyle & WS_EX_TRANSPARENT)
        surf.set_input_policy("interactive")
        self.assertEqual(surf.input_policy, "interactive")
        self.assertFalse(backend.exstyle & WS_EX_TRANSPARENT)

        # Visibility, set_opacity, reorder=False, and idempotent close(clear_exstyle=True)
        surf.set_opacity(0.4)
        self.assertAlmostEqual(surf.opacity, 0.4)
        self.assertEqual(backend.opacity_update_count, 1)
        self.assertEqual(backend.last_alpha_byte, round(0.4 * 255))
        self.assertEqual(backend.present_count, 2)

        surf.set_visibility(True, reorder=False)
        self.assertTrue(surf.visible)
        self.assertFalse(backend.last_reorder)
        surf.set_visibility(True, reorder=True)
        self.assertTrue(backend.last_reorder)
        surf.set_visibility(False)
        self.assertFalse(surf.visible)
        surf.close(clear_exstyle=True)
        self.assertTrue(surf.closed)
        self.assertFalse(backend.exstyle & WS_EX_LAYERED)
        self.assertFalse(backend.exstyle & WS_EX_TRANSPARENT)
        surf.close()  # idempotent
        with self.assertRaises(RuntimeError):
            surf.present(im1)

    def test_win32_ctypes_signatures_use_64bit_void_pointers(self) -> None:
        if sys.platform != "win32":
            self.skipTest("Win32 only")
        backend = _Win32LayeredBackend()
        try:
            self.assertEqual(ctypes.sizeof(ctypes.c_void_p), 8)
            for fn in (
                backend._get_style,
                backend._set_style,
                backend._show,
                backend._set_pos,
                backend._update_layered,
                backend._create_compat_dc,
                backend._delete_dc,
                backend._create_dib,
                backend._select_obj,
                backend._delete_obj,
            ):
                self.assertIs(fn.argtypes[0], ctypes.c_void_p, f"{fn} arg 0 must be c_void_p")
            for fn in (backend._create_compat_dc, backend._create_dib, backend._select_obj):
                self.assertIs(fn.restype, ctypes.c_void_p, f"{fn} restype must be c_void_p")
        finally:
            backend.close()


@unittest.skipUnless(sys.platform == "win32", "Requires real Win32 desktop and GDI")
class LayeredSpriteSurfaceWin32RealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._cleanup_root)

    def _cleanup_root(self) -> None:
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    def _load_real_or_synthetic_sprite(self, size: int = 192) -> Image.Image:
        real_path = ROOT / "work" / "characters" / "eunji" / "idle_01.png"
        if real_path.is_file():
            with Image.open(real_path) as raw:
                rgba = raw.convert("RGBA")
        else:
            rgba = Image.new("RGBA", (384, 384), (0, 0, 0, 0))
            draw = ImageDraw.Draw(rgba)
            draw.ellipse((48, 48, 336, 336), fill=(255, 220, 235, 255), outline=(90, 60, 75, 180), width=8)
        if rgba.size != (size, size):
            # Pure LANCZOS resize keeping full 8-bit antialiased alpha (0 < alpha < 255)
            rgba = rgba.resize((size, size), Image.Resampling.LANCZOS)
        return rgba

    def test_ulw_opacities_sizes_negative_coords_and_tk_events_without_lwa(self) -> None:
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        self.addCleanup(lambda: top.destroy() if top.winfo_exists() else None)

        # Verify no Tk -transparentcolor or -alpha was set
        self.assertEqual(str(top.wm_attributes("-transparentcolor")), "")

        clicked: list[tuple[int, int]] = []
        top.bind("<Button-1>", lambda e: clicked.append((e.x, e.y)))

        surf = LayeredSpriteSurface(top, x=180, y=180, opacity=1.0, input_policy="interactive")
        self.addCleanup(surf.close)

        sprite_192 = self._load_real_or_synthetic_sprite(192)
        # Confirm 8-bit smooth alpha exists on the LANCZOS-resized sprite
        alphas = set(sprite_192.getchannel("A").tobytes())
        self.assertIn(0, alphas)
        self.assertIn(255, alphas)
        self.assertTrue(any(16 <= a <= 240 for a in alphas), "Expected 8-bit intermediate alpha pixels")

        surf.present(sprite_192, x=180, y=180, opacity=1.0)
        surf.set_visibility(True)
        self.root.update_idletasks()
        self.assertEqual(surf.geometry_box, (180, 180, 192, 192))

        # Test opacities 0.05 .. 1.0 via both present(..., opacity=...) and standalone set_opacity(...)
        for op in (0.05, 0.25, 0.5, 0.85, 1.0):
            surf.present(sprite_192, opacity=op)
            self.assertAlmostEqual(surf.opacity, op)
        for op in (0.15, 0.65, 1.0):
            surf.set_opacity(op)
            self.assertAlmostEqual(surf.opacity, op)
        surf.set_visibility(True, reorder=False)
        self.assertTrue(surf.visible)

        # Test size switching 144 -> 192 -> 240 -> 144
        for sz in (144, 192, 240, 144):
            frame = self._load_real_or_synthetic_sprite(sz)
            surf.present(frame)
            self.assertEqual((surf.width, surf.height), (sz, sz))

        # Test negative coordinates (multi-monitor secondary display coordinates)
        surf.move(-640, -120)
        self.assertEqual(surf.geometry_box, (-640, -120, 144, 144))
        surf.move(220, 220)
        self.assertEqual(surf.geometry_box, (220, 220, 144, 144))

        # Test input policy toggling on the real HWND
        exstyle_inter = surf._backend.get_exstyle(surf.hwnd)
        self.assertTrue(exstyle_inter & WS_EX_LAYERED)
        self.assertTrue(exstyle_inter & WS_EX_NOACTIVATE)
        self.assertFalse(exstyle_inter & WS_EX_TRANSPARENT)

        surf.set_input_policy("passthrough")
        exstyle_pass = surf._backend.get_exstyle(surf.hwnd)
        self.assertTrue(exstyle_pass & WS_EX_TRANSPARENT)

        surf.set_input_policy("interactive")
        exstyle_back = surf._backend.get_exstyle(surf.hwnd)
        self.assertFalse(exstyle_back & WS_EX_TRANSPARENT)

        # Confirm Tk event binding on the same Toplevel still dispatches cleanly
        top.event_generate("<Button-1>", x=40, y=50)
        self.root.update()
        self.assertEqual(clicked, [(40, 50)])

    def test_200_presents_and_20_resizes_have_zero_gdi_handle_leak(self) -> None:
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        self.addCleanup(lambda: top.destroy() if top.winfo_exists() else None)

        frames = {
            144: self._load_real_or_synthetic_sprite(144),
            192: self._load_real_or_synthetic_sprite(192),
            240: self._load_real_or_synthetic_sprite(240),
        }

        surf = LayeredSpriteSurface(top, x=240, y=240, opacity=1.0)
        surf.present(frames[192])
        surf.set_visibility(True)
        self.root.update()
        # Allow Windows uxtheme / DWM one-time thread initialization to settle
        time.sleep(0.4)
        self.root.update()

        gdi_baseline = current_process_gdi_objects()
        self.assertIsNotNone(gdi_baseline)

        # 200 frame updates at fixed size
        for i in range(200):
            surf.present(frames[192], opacity=0.2 + 0.8 * ((i % 10) / 9.0))
        gdi_after_200 = current_process_gdi_objects()

        # 20 size changes across 144 / 192 / 240
        size_cycle = (144, 192, 240, 192)
        for i in range(20):
            sz = size_cycle[i % len(size_cycle)]
            surf.present(frames[sz], x=200 + (i % 5) * 4, y=200 + (i % 5) * 4)
        gdi_after_resizes = current_process_gdi_objects()

        # Zero handle leak across 200 presents and 20 DIBSection reallocations
        self.assertEqual(gdi_after_200, gdi_baseline)
        self.assertEqual(gdi_after_resizes, gdi_baseline)

        surf.close()
        gdi_after_close = current_process_gdi_objects()
        # Closing deterministically releases the compat DC and DIBSection HBITMAP (-2 handles)
        self.assertEqual(gdi_after_close, gdi_baseline - 2)

    def test_screen_composition_preserves_smooth_alpha_without_black_or_magenta_fringe(self) -> None:
        backdrop = tk.Toplevel(self.root)
        backdrop.overrideredirect(True)
        backdrop.attributes("-topmost", True)
        backdrop.configure(bg="#20c060")
        backdrop.geometry("220x220+300+300")
        backdrop.deiconify()
        backdrop.lift()
        self.addCleanup(lambda: backdrop.destroy() if backdrop.winfo_exists() else None)

        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        self.addCleanup(lambda: top.destroy() if top.winfo_exists() else None)

        # Build a test sprite with:
        # - left third: alpha = 0 (transparent -> shows backdrop #20c060)
        # - middle third: alpha = 128 pure white (255, 255, 255, 128 -> blends 50/50 with backdrop)
        # - right third: alpha = 255 pure pink-red (240, 60, 120, 255 -> solid sprite color)
        sprite = Image.new("RGBA", (180, 120), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sprite)
        draw.rectangle((60, 0, 119, 119), fill=(255, 255, 255, 128))
        draw.rectangle((120, 0, 179, 119), fill=(240, 60, 120, 255))

        surf = LayeredSpriteSurface(top, x=320, y=340, opacity=1.0)
        self.addCleanup(surf.close)
        surf.present(sprite, x=320, y=340, opacity=1.0)
        surf.set_visibility(True)
        self.root.update()

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        get_ancestor.restype = ctypes.c_void_p
        window_from_point = user32.WindowFromPoint
        window_from_point.argtypes = [wintypes.POINT]
        window_from_point.restype = ctypes.c_void_p
        allowed_roots = {
            get_ancestor(ctypes.c_void_p(int(h)), 2) or int(h)
            for h in (surf.hwnd, backdrop.winfo_id())
            if h
        }
        sample_points = ((340, 400), (410, 400), (470, 400))
        occluded = any(
            (get_ancestor(window_from_point(wintypes.POINT(px, py)), 2) or 0) not in allowed_roots
            for px, py in sample_points
        )

        shot = None
        if not occluded:
            try:
                shot = ImageGrab.grab(bbox=(320, 340, 500, 460))
            except OSError:
                shot = None
        if shot is None:
            # When running under a non-interactive desktop session or occluded region,
            # composite the live ULW _mem_dc directly over a #20c060 DIB via Win32 GDI AlphaBlend
            # (the exact AC_SRC_OVER | AC_SRC_ALPHA equation used by UpdateLayeredWindow).
            b = surf._backend
            dst_dc = b._create_compat_dc(None)
            bmi = _BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = 180
            bmi.bmiHeader.biHeight = -120
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB
            bmi.bmiHeader.biSizeImage = 180 * 120 * 4
            dst_bits = ctypes.c_void_p()
            dst_bmp = b._create_dib(dst_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(dst_bits), None, 0)
            old_dst = b._select_obj(dst_dc, dst_bmp)
            try:
                green_bg = bytes((96, 192, 32, 255)) * (180 * 120)
                ctypes.memmove(dst_bits.value, green_bg, len(green_bg))
                msimg32 = ctypes.WinDLL("msimg32", use_last_error=True)
                alpha_blend = msimg32.AlphaBlend
                alpha_blend.argtypes = [
                    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    _BLENDFUNCTION,
                ]
                alpha_blend.restype = ctypes.c_int32
                blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
                self.assertEqual(alpha_blend(dst_dc, 0, 0, 180, 120, b._mem_dc, 0, 0, 180, 120, blend), 1)
                raw_out = ctypes.string_at(dst_bits.value, 180 * 120 * 4)
                shot = Image.frombytes("RGBA", (180, 120), raw_out, "raw", "BGRA")
            finally:
                b._select_obj(dst_dc, old_dst)
                b._delete_obj(dst_bmp)
                b._delete_dc(dst_dc)

        px_transparent = shot.getpixel((20, 60))[:3]
        px_semialpha = shot.getpixel((90, 60))[:3]
        px_opaque = shot.getpixel((150, 60))[:3]

        # Transparent region shows the green backdrop (never black #000000 or magenta #ff00fe)
        self.assertGreater(px_transparent[1], 150, f"Expected green backdrop, got {px_transparent}")
        self.assertLess(px_transparent[0], 80, f"Expected green backdrop, got {px_transparent}")

        # 50% white over green (#20c060 = 32, 192, 96) blends to ~(144, 224, 176)
        self.assertTrue(110 <= px_semialpha[0] <= 180, f"Expected 50% blended R, got {px_semialpha}")
        self.assertTrue(195 <= px_semialpha[1] <= 245, f"Expected 50% blended G, got {px_semialpha}")
        self.assertTrue(140 <= px_semialpha[2] <= 210, f"Expected 50% blended B, got {px_semialpha}")

        # Opaque region shows solid sprite color (240, 60, 120)
        self.assertGreater(px_opaque[0], 210, f"Expected solid sprite R, got {px_opaque}")
        self.assertLess(px_opaque[1], 90, f"Expected solid sprite G, got {px_opaque}")


if __name__ == "__main__":
    unittest.main()
