"""hotkey.py — Global Windows Hotkey Listener for PandaDesktopPet.

Registers global hotkeys using native Windows user32.RegisterHotKey API.
Features:
- Global system-wide shortcut detection (e.g. Ctrl+Shift+S)
- Thread-safe dispatch to Tkinter main thread
- Clean background daemon thread with message pump
- Graceful shutdown with PostThreadMessage
"""
from __future__ import annotations

import ctypes
import threading
from typing import Callable

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parses hotkey string into (modifiers, virtual_key_code)."""
    parts = [p.strip().upper() for p in hotkey_str.split("+")]
    mods = MOD_NOREPEAT
    vk = 0
    for p in parts[:-1]:
        if p in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif p == "SHIFT":
            mods |= MOD_SHIFT
        elif p == "ALT":
            mods |= MOD_ALT
        elif p in ("WIN", "WINDOWS"):
            mods |= MOD_WIN

    key = parts[-1]
    if key.startswith("F") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1:
        vk = ord(key)
    return mods, vk


class GlobalHotkeyManager:
    """Listens for a global hotkey across the entire Windows OS."""

    def __init__(self, hotkey_str: str, on_trigger: Callable[[], None]) -> None:
        self.hotkey_str = hotkey_str
        self.on_trigger = on_trigger
        self.hotkey_id = 8801
        self.thread: threading.Thread | None = None
        self.thread_id: int | None = None
        self.running = False

    def start(self) -> None:
        if self.running or not self.hotkey_str:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self) -> None:
        self.thread_id = threading.get_native_id()
        mods, vk = parse_hotkey(self.hotkey_str)
        if not vk:
            return

        success = user32.RegisterHotKey(0, self.hotkey_id, mods, vk)
        if not success:
            return

        msg = MSG()
        try:
            while self.running:
                res = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
                if res <= 0 or msg.message == WM_QUIT:
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    if self.on_trigger:
                        self.on_trigger()
        finally:
            try:
                user32.UnregisterHotKey(0, self.hotkey_id)
            except Exception:
                pass

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.thread_id:
            try:
                user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)

