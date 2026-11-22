"""tray.py — Windows System Tray (系統工具列通知區域小圖示) integration for PandaDesktopPet.

Allows minimizing / hiding the pet to the tray, and restoring anytime by clicking the icon.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

from app.i18n import t
from app.resource_store import open_resource_image, resource_exists


class PandaSystemTray:
    def __init__(
        self,
        icon_path: Path,
        on_toggle_show: Callable[[], None] | None = None,
        on_status_card: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
        lang: str = "zh_TW",
        *,
        on_wake_pet: Callable[[], None] | None = None,
        on_hide_pet: Callable[[], None] | None = None,
    ) -> None:
        self.on_wake_pet = on_wake_pet or on_toggle_show or (lambda: None)
        self.on_hide_pet = on_hide_pet or (lambda: None)
        self.on_toggle_show = on_toggle_show or self.on_wake_pet
        self.on_status_card = on_status_card or (lambda: None)
        self.on_exit = on_exit or (lambda: None)
        self.lang = lang

        # Load or create 32x32 icon image
        if resource_exists(icon_path):
            with open_resource_image(icon_path) as raw:
                img = raw.convert("RGBA").resize((32, 32), Image.Resampling.LANCZOS)
        else:
            # Fallback simple pink circle icon
            img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))

        self.img = img
        self.icon: pystray.Icon | None = None
        self.is_visible = True

        self.build_icon()

    def build_icon(self) -> None:
        wake_label = t("tray_wake_pet", self.lang)
        hide_label = t("tray_hide_pet", self.lang)
        menu = pystray.Menu(
            pystray.MenuItem(wake_label, lambda icon, item: self.on_wake_pet(), default=True),
            pystray.MenuItem(hide_label, lambda icon, item: self.on_hide_pet()),
            pystray.MenuItem(t("status_card", self.lang), lambda icon, item: self.on_status_card()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("exit", self.lang), lambda icon, item: self.on_exit()),
        )
        tip = t("tray_tip", self.lang)
        # pystray names its window class after id(icon). An earlier icon whose class is
        # still registered can have had the same address (WinError 1410); holding the
        # failed attempt keeps that address taken so the retry lands elsewhere.
        failed: list[OSError] = []
        while True:
            try:
                self.icon = pystray.Icon("PandaDesktopPet", self.img, tip, menu)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) != 1410 or len(failed) >= 8:
                    raise
                failed.append(exc)

    def set_visible_state(self, visible: bool) -> None:
        self.is_visible = visible
        if self.icon:
            wake_label = t("tray_wake_pet", self.lang)
            hide_label = t("tray_hide_pet", self.lang)
            menu = pystray.Menu(
                pystray.MenuItem(wake_label, lambda icon, item: self.on_wake_pet(), default=True),
                pystray.MenuItem(hide_label, lambda icon, item: self.on_hide_pet()),
                pystray.MenuItem(t("status_card", self.lang), lambda icon, item: self.on_status_card()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(t("exit", self.lang), lambda icon, item: self.on_exit()),
            )
            self.icon.menu = menu

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self.set_visible_state(self.is_visible)

    def start(self) -> None:
        if self.icon:
            thread = threading.Thread(target=self.icon.run, daemon=True)
            thread.start()

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

