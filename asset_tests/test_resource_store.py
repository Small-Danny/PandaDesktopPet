"""Tests for app.resource_store, tools.pack_assets, and .pak-backed runtime subsystems."""
from __future__ import annotations

import gc
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from PIL import Image

from app.asset_images import AssetImageCache
from app.bubble import _render_frame
from app.bubble_art import frame_layout as bubble_frame_layout
from app.bubble_themes import get_theme
from app.engine.asset_policy import CANVAS_ANCHORS
from app.engine.assets import AssetRegistry
from app.resource_store import (
    FolderResourceStore,
    PakResourceStore,
    clear_store_cache,
    open_resource_image,
    read_resource_bytes,
    resource_exists,
    resource_stat_signature,
    resource_store,
)
from app.sprites import SpriteLibrary
from app.standby import _fitted_wallpaper, load_wallpapers
from tools.pack_assets import pack_assets

ROOT = Path(__file__).resolve().parent.parent


def _make_png(size: tuple[int, int] = (256, 256), color: tuple[int, int, int, int] = (255, 160, 190, 255)) -> bytes:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    w, h = size
    for x in range(w // 4, 3 * w // 4):
        for y in range(h // 4, min(h - 12, 3 * h // 4)):
            im.putpixel((x, y), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _make_9slice_png(size: tuple[int, int] = (240, 200)) -> bytes:
    w, h = size
    im = Image.new("RGBA", size, (255, 240, 246, 255))
    for x in range(w):
        for y in range(6):
            im.putpixel((x, y), (220, 120, 160, 255))
            im.putpixel((x, h - 1 - y), (220, 120, 160, 255))
    for y in range(h):
        for x in range(6):
            im.putpixel((x, y), (220, 120, 160, 255))
            im.putpixel((w - 1 - x, y), (220, 120, 160, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _make_cur_bytes(width: int = 32, height: int = 32, hotspot: tuple[int, int] = (4, 3)) -> bytes:
    """Minimal valid 32-bpp DIB-backed .cur binary for CreateIconFromResourceEx."""
    xor_bytes = b"\xff\x80\xa0\xff" * (width * height)
    and_stride = ((width + 31) // 32) * 4
    and_bytes = b"\x00" * (and_stride * height)
    # BITMAPINFOHEADER (40 bytes): biHeight is 2 * height (XOR + AND masks)
    bih = struct.pack("<IiiHHIIIIII", 40, width, height * 2, 1, 32, 0, len(xor_bytes) + len(and_bytes), 0, 0, 0, 0)
    image_data = bih + xor_bytes + and_bytes
    icondir = struct.pack("<HHH", 0, 2, 1)
    entry = struct.pack("<BBBBHHII", width if width < 256 else 0, height if height < 256 else 0, 0, 0, hotspot[0], hotspot[1], len(image_data), 6 + 16)
    return icondir + entry + image_data


class ResourceStoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_store_cache()

    def test_verified_payload_reused_through_resolver_and_decoder_then_invalidated(self):
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as pak_tmp:
            src,pak_dir=Path(src_tmp),Path(pak_tmp)
            path=self._build_synthetic_pak(src,pak_dir)
            store=PakResourceStore(path,base_root=pak_dir)
            registry=AssetRegistry(pak_dir/'work/asset_registry.json',pak_dir,store=store)
            with mock.patch.object(store,'_payload',wraps=store._payload) as reads:
                spec=registry.resolve('chorong','idle')
                images=AssetImageCache(registry)
                images.load_animation(spec)
                store.sha256(spec.frames[0]);store.read_bytes(spec.frames[0])
                self.assertEqual(reads.call_count,1)
            raw=bytearray(path.read_bytes());raw[store._entries[spec.frames[0]]['offset']]^=0xFF
            path.write_bytes(raw)
            with self.assertRaises((ValueError,OSError)):
                store.read_bytes(spec.frames[0])

    def test_folder_verified_bytes_follow_file_version(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'a.txt';path.write_bytes(b'old')
            store=FolderResourceStore(root)
            self.assertEqual(store.read_verified('a.txt'),(b'old',hashlib.sha256(b'old').hexdigest()))
            path.write_bytes(b'new data')
            self.assertEqual(store.read_verified('a.txt'),(b'new data',hashlib.sha256(b'new data').hexdigest()))

    def _build_synthetic_pak(self, src_dir: Path, pak_dir: Path) -> Path:
        # 1. Minimal approved character registry with Chorong basic actions
        char_dir = src_dir / "work" / "characters" / "chorong"
        char_dir.mkdir(parents=True, exist_ok=True)
        files_meta = {}
        assets_meta = {}
        for act in ("idle", "walk", "cheer", "sleep"):
            rel = f"chorong/{act}_01.png"
            png = _make_png((256, 256), (250, 150, 180, 255))
            (src_dir / "work" / "characters" / rel).write_bytes(png)
            with Image.open(io.BytesIO(png)) as raw:
                bbox = list(raw.getchannel("A").getbbox())
            sha = hashlib.sha256(png).hexdigest()
            files_meta[f"chorong/{act}_01"] = {
                "path": rel,
                "sha256": sha,
                "runtime_ok": True,
                "ExcludeFromRuntime": False,
                "review_status": "approved",
                "alpha_bbox": bbox,
                "source_size": [256, 256],
                "normalization_mode": "bbox",
                "normalization_scale": 1.0,
                "anchor": list(CANVAS_ANCHORS[(256, 256)]),
            }
            assets_meta[f"chorong.{act}"] = {
                "member": "chorong",
                "action": act,
                "frames": [f"work/characters/{rel}"],
                "fps": 6.0,
                "loop": True,
                "canvas": [256, 256],
                "anchor": list(CANVAS_ANCHORS[(256, 256)]),
                "interruptible": True,
                "tags": [],
                "runtime_ok": True,
            }
        (src_dir / "work" / "asset_registry.json").write_text(
            json.dumps({"schema_version": 1, "assets": assets_meta, "files": files_meta}),
            encoding="utf-8",
        )

        # 2. Wallpaper manifest + image
        wb_dir = src_dir / "work" / "standby_backgrounds"
        wb_dir.mkdir(parents=True, exist_ok=True)
        wall_im = Image.new("RGB", (64, 48), (40, 60, 100))
        wall_buf = io.BytesIO()
        wall_im.save(wall_buf, format="JPEG")
        wall_bytes = wall_buf.getvalue()
        (wb_dir / "test_bg.jpg").write_bytes(wall_bytes)
        (src_dir / "work" / "standby_backgrounds.json").write_text(
            json.dumps({
                "schema_version": 1,
                "backgrounds": [{
                    "key": "bg_pak_test",
                    "path": "work/standby_backgrounds/test_bg.jpg",
                    "sha256": hashlib.sha256(wall_bytes).hexdigest(),
                    "width": 64,
                    "height": 48,
                    "status": "approved",
                    "labels": {"zh_TW": "測試桌布", "ko": "테스트", "en": "Test"},
                }],
            }),
            encoding="utf-8",
        )

        # 3. Bubble 9-slice + food + ui_icon + cursor + quotes + 419 scene
        (src_dir / "work" / "bubbles").mkdir(parents=True, exist_ok=True)
        (src_dir / "work" / "bubbles" / "bubble_chorong_pink.png").write_bytes(_make_9slice_png())
        (src_dir / "work" / "foods").mkdir(parents=True, exist_ok=True)
        (src_dir / "work" / "foods" / "chicken_feet_64.png").write_bytes(_make_png((64, 64), (255, 200, 120, 255)))
        (src_dir / "work" / "ui_icons").mkdir(parents=True, exist_ok=True)
        (src_dir / "work" / "ui_icons" / "cursor_paw_smooth.cur").write_bytes(_make_cur_bytes())
        (src_dir / "work" / "ui_icons" / "icon_status.png").write_bytes(_make_png((32, 32), (240, 100, 160, 255)))
        scene_dir = src_dir / "work" / "scenes" / "anniversary_419"
        scene_dir.mkdir(parents=True, exist_ok=True)
        for s_name in ("loop_1.png", "loop_2.png", "loop_3.png", "loop_4.png", "surprise.png"):
            (scene_dir / s_name).write_bytes(_make_png((96, 64), (255, 190, 210, 255)))
        (src_dir / "work" / "quotes.json").write_text(
            json.dumps({"chorong": [{"zh": "測試語錄", "ko": "테스트", "en": "Test line", "quote_category": "COMPANION_LINE"}]}),
            encoding="utf-8",
        )

        rel_paths = [
            "work/asset_registry.json",
            *(f"work/characters/chorong/{act}_01.png" for act in ("idle", "walk", "cheer", "sleep")),
            "work/standby_backgrounds.json",
            "work/standby_backgrounds/test_bg.jpg",
            "work/bubbles/bubble_chorong_pink.png",
            "work/foods/chicken_feet_64.png",
            "work/ui_icons/cursor_paw_smooth.cur",
            "work/ui_icons/icon_status.png",
            *(f"work/scenes/anniversary_419/{s}" for s in ("loop_1.png", "loop_2.png", "loop_3.png", "loop_4.png", "surprise.png")),
            "work/quotes.json",
        ]
        pak_path = pak_dir / "assets.pak"
        summary = pack_assets(src_dir, pak_path, rel_paths=rel_paths)
        self.assertEqual(summary["entry_count"], len(rel_paths))
        return pak_path

    def test_pak_roundtrip_traversal_rejection_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as pak_tmp:
            src_dir, pak_dir = Path(src_tmp), Path(pak_tmp)
            pak_path = self._build_synthetic_pak(src_dir, pak_dir)

            store = resource_store(pak_dir)
            self.assertIsInstance(store, PakResourceStore)
            self.assertIsInstance(resource_store(src_dir), FolderResourceStore)

            # Assert zero loose image/cursor files in pak_dir
            loose = [p for p in pak_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".cur"}]
            self.assertEqual(loose, [])

            # Session batching & image decoding work identically with zero handles left open
            with store.session():
                self.assertTrue(store.exists("work/characters/chorong/idle_01.png"))
                self.assertTrue(store.exists(pak_dir / "work" / "foods" / "chicken_feet_64.png"))
                self.assertFalse(store.exists("work/nonexistent.png"))
                with store.open_image("work/foods/chicken_feet_64.png") as im:
                    self.assertEqual(im.size, (64, 64))

            # Path traversal and escape rejected
            for bad in ("../secret.txt", "work/../../etc/passwd", "/abs/path.png", "C:/win/test.png", "a\x00b"):
                with self.subTest(bad=bad):
                    self.assertFalse(store.exists(bad))
                    with self.assertRaises(ValueError):
                        store.read_bytes(bad)

            # Corrupt a single payload byte and verify fail-closed sha256 rejection
            raw = bytearray(pak_path.read_bytes())
            first_meta = next(iter(store._entries.values()))
            raw[first_meta["offset"]] ^= 0xFF
            tampered = pak_dir / "tampered.pak"
            tampered.write_bytes(bytes(raw))
            tampered_store = PakResourceStore(tampered, base_root=pak_dir)
            first_key = next(iter(tampered_store._entries))
            with self.assertRaises((ValueError, Exception)):
                tampered_store.read_bytes(first_key)

            # Explicit external Temp Path: missing raises OSError (FileNotFoundError),
            # while string / '..' / NUL escape attempts still raise ValueError (or False for exists).
            with tempfile.TemporaryDirectory() as ext_tmp:
                ext_dir = Path(ext_tmp)
                existing_ext = ext_dir / "ext_9slice.png"
                existing_ext.write_bytes(_make_9slice_png((240, 200)))
                self.assertTrue(resource_exists(existing_ext, root=pak_dir))
                self.assertEqual(bubble_frame_layout(existing_ext).size, (240, 200))
                self.assertEqual(resource_stat_signature(existing_ext, root=pak_dir)[0], "fs")

                with self.assertRaises(FileNotFoundError):
                    open_resource_image(ext_dir / "missing.png", root=pak_dir)
                with self.assertRaises(FileNotFoundError):
                    read_resource_bytes(ext_dir / "missing.bin", root=pak_dir)
                with self.assertRaises(FileNotFoundError):
                    resource_stat_signature(ext_dir / "missing.bin", root=pak_dir)
                with self.assertRaises(ValueError):
                    open_resource_image(str(existing_ext), root=pak_dir)
                with self.assertRaises(ValueError):
                    read_resource_bytes(ext_dir / "sub" / ".." / "ext_9slice.png", root=pak_dir)
                self.assertFalse(resource_exists("a\x00b", root=pak_dir))
                self.assertFalse(resource_exists(str(existing_ext), root=pak_dir))
                with self.assertRaises(ValueError):
                    read_resource_bytes("a\x00b", root=pak_dir)

    def test_runtime_subsystems_read_from_pak_without_loose_files(self) -> None:
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as pak_tmp:
            src_dir, pak_dir = Path(src_tmp), Path(pak_tmp)
            self._build_synthetic_pak(src_dir, pak_dir)

            # 1. AssetRegistry + AssetImageCache
            reg = AssetRegistry(pak_dir / "work" / "asset_registry.json", pak_dir)
            cache = AssetImageCache(reg)
            spec = reg.resolve("chorong", "idle")
            self.assertIsNotNone(spec)
            actual, frames = cache.load_animation(spec)
            self.assertEqual(actual.action, "idle")
            self.assertEqual(len(frames), 1)

            # 2. Standby wallpapers
            specs = load_wallpapers(pak_dir)
            self.assertEqual(len(specs), 1)
            self.assertEqual(specs[0].key, "bg_pak_test")
            with mock.patch("app.standby.resource_dir", return_value=pak_dir):
                fitted = _fitted_wallpaper(specs[0].path, 128, 96)
                self.assertEqual(fitted.size, (128, 96))

            # 3. Resource helpers & bubble theme 9-slice layout from .pak
            with mock.patch("app.resource_store.resource_dir", return_value=pak_dir), \
                 mock.patch("app.bubble_themes.resource_dir", return_value=pak_dir):
                self.assertTrue(resource_exists(pak_dir / "work" / "foods" / "chicken_feet_64.png", root=pak_dir))
                theme = get_theme("chorong_pink")
                nine_path = theme.get_nine_slice_path()
                self.assertIsNotNone(nine_path)
                layout = bubble_frame_layout(nine_path)
                self.assertEqual(layout.size, (240, 200))

                class _Geo:
                    width = 240
                    height = 240
                    scale = 1.0
                    cap_top = 40
                    cap_bottom = 40
                    right_cut = None
                rendered = _render_frame(nine_path, layout, _Geo())
                self.assertEqual(rendered.size, (240, 240))

            # 4. Win32 loads directly from the pak. Tk receives a verified temporary file.
            import app.cursor_manager as cm
            orig_cache = dict(cm._CURSOR_CACHE)
            cm._CURSOR_CACHE.clear()
            try:
                with mock.patch("app.cursor_manager.UI_ICONS_DIR", pak_dir / "work" / "ui_icons"), \
                     mock.patch("app.cursor_manager.RES_ROOT", pak_dir), \
                     mock.patch("app.resource_store.resource_dir", return_value=pak_dir):
                    self.assertIsNone(cm.get_cursor_path("paw_smooth"))
                    spec = cm.get_tkinter_cursor_spec("paw_smooth")
                    self.assertTrue(spec.startswith("@"))
                    self.assertEqual(Path(spec[1:]).read_bytes(),
                                     cm.read_resource_bytes("work/ui_icons/cursor_paw_smooth.cur", root=pak_dir))
                    hcur = cm.load_cursor("paw_smooth")
                    self.assertTrue(bool(hcur))
            finally:
                cm.cleanup_cursor_files()
                cm._CURSOR_CACHE.clear()
                cm._CURSOR_CACHE.update(orig_cache)

    def test_ui_modules_and_cursor_hook_from_pak(self) -> None:
        from types import SimpleNamespace

        import app.anniversary_scene as ann_mod
        import app.cursor_manager as cm
        import app.food_panel as fp_mod
        import app.main as main_mod
        import app.personalities as pers_mod
        import app.pink_context_menu as pcm_mod
        import app.profile_card as pc_mod
        import app.settings_panel as sp_mod
        import app.status_card as sc_mod
        import app.tray as tray_mod

        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as pak_tmp:
            src_dir, pak_dir = Path(src_tmp), Path(pak_tmp)
            self._build_synthetic_pak(src_dir, pak_dir)
            orig_cache = dict(cm._CURSOR_CACHE)
            cm._CURSOR_CACHE.clear()
            root = tk.Tk()
            root.withdraw()
            try:
                with mock.patch("app.resource_store.resource_dir", return_value=pak_dir), \
                     mock.patch("app.cursor_manager.UI_ICONS_DIR", pak_dir / "work" / "ui_icons"), \
                     mock.patch("app.cursor_manager.RES_ROOT", pak_dir), \
                     mock.patch.object(pers_mod, "QUOTES_JSON_PATH", pak_dir / "work" / "quotes.json"), \
                     mock.patch.object(pers_mod, "QUOTES_TXT_PATH", pak_dir / "work" / "apink成員暖心語錄.txt"), \
                     mock.patch.object(fp_mod, "FOODS_DIR", pak_dir / "work" / "foods"), \
                     mock.patch.object(pcm_mod, "UI_ICONS_DIR", pak_dir / "work" / "ui_icons"), \
                     mock.patch.object(pc_mod, "ROOT", pak_dir), \
                     mock.patch.object(sc_mod, "ROOT", pak_dir):
                    # Personalities quotes loaded from .pak
                    loaded_quotes = pers_mod._load_all_warm_quotes()
                    self.assertEqual(loaded_quotes["chorong"][0]["zh"], "測試語錄")

                    # System tray icon loaded from .pak (center pixel != transparent blank)
                    tray_obj = tray_mod.PandaSystemTray(pak_dir / "work" / "foods" / "chicken_feet_64.png")
                    self.assertEqual(tray_obj.img.size, (32, 32))
                    self.assertEqual(tray_obj.img.getpixel((16, 16)), (255, 200, 120, 255))

                    # Food panel icons loaded from .pak
                    food_panel = fp_mod.FoodCafePanel(root, work_area=(0, 0, 1200, 900))
                    try:
                        self.assertIn("chicken_feet", food_panel._icon_cache)
                    finally:
                        food_panel.close()

                    # Pink context menu icons loaded from .pak + lazy submenu/peek flyout cursor hooks
                    owner = SimpleNamespace(settings={"mouse_cursor": "paw_smooth"})
                    menu = pcm_mod.PinkContextMenu(
                        root,
                        items=[pcm_mod.MenuItemSpec("Status", lambda: None, icon_name="icon_status")],
                        work_area=(0, 0, 1200, 900),
                    )
                    try:
                        self.assertIsNotNone(menu._get_icon("icon_status"))
                        main_mod.PandaPet._apply_cursor_to_panel(owner, menu)
                        menu._open_submenu(0, [pcm_mod.MenuItemSpec("SubItem", lambda: None)])
                        self.assertIsNotNone(menu._sub_window)
                        self.assertIsNotNone(menu._sub_canvas)
                        self.assertIn(int(menu._sub_window.winfo_id()), cm._HWND_HOOKS)
                        self.assertIn(int(menu._sub_canvas.winfo_id()), cm._HWND_HOOKS)
                        menu._open_peek(0, 220, [pcm_mod.MenuItemSpec("PeekItem", lambda: None)])
                        self.assertIsNotNone(menu._peek_window)
                        self.assertIsNotNone(menu._peek_canvas)
                        self.assertIn(int(menu._peek_window.winfo_id()), cm._HWND_HOOKS)
                        self.assertIn(int(menu._peek_canvas.winfo_id()), cm._HWND_HOOKS)
                    finally:
                        menu.close()

                    # SettingsPanel notif_guide inherits active .pak cursor across child widgets
                    settings_panel = sp_mod.SettingsPanel(
                        root,
                        lang="zh_TW",
                        char_key="chorong",
                        state={},
                        on_change=lambda _k, _v: True,
                    )
                    try:
                        main_mod.PandaPet._apply_cursor_to_panel(owner, settings_panel)
                        self.assertIn(int(settings_panel.window.winfo_id()), cm._HWND_HOOKS)
                        self.assertTrue(settings_panel.open_notif_guide())
                        self.assertIsNotNone(settings_panel.notif_guide)
                        guide = settings_panel.notif_guide
                        self.assertIn(int(guide.window.winfo_id()), cm._HWND_HOOKS)
                        self.assertIn(int(guide.text.winfo_id()), cm._HWND_HOOKS)
                        self.assertEqual(cm._HWND_HOOKS[int(guide.text.winfo_id())][2], "paw_smooth")
                        self.assertEqual(guide.text.cget("cursor"), cm.get_tkinter_cursor_spec("paw_smooth"))
                        child_buttons = [w for w in guide.window.winfo_children() if isinstance(w, tk.Button)]
                        self.assertTrue(child_buttons)
                        self.assertIn(int(child_buttons[0].winfo_id()), cm._HWND_HOOKS)
                        # Reverting to system cursor uninstalls child hooks and restores read-only text arrow
                        owner.settings["mouse_cursor"] = "system"
                        main_mod.PandaPet._apply_cursor_to_panel(owner, settings_panel)
                        self.assertNotIn(int(guide.window.winfo_id()), cm._HWND_HOOKS)
                        self.assertNotIn(int(guide.text.winfo_id()), cm._HWND_HOOKS)
                        self.assertNotIn(int(child_buttons[0].winfo_id()), cm._HWND_HOOKS)
                        self.assertEqual(guide.text.cget("cursor"), "arrow")
                        owner.settings["mouse_cursor"] = "paw_smooth"
                    finally:
                        settings_panel.close()

                    # Profile card avatar loaded from .pak via SpriteLibrary
                    card = pc_mod.MemberProfileCard(root, initial_member="chorong")
                    try:
                        self.assertIsNotNone(card._avatar_photo)
                    finally:
                        card.close()

                    # Status card 4-frame avatar sequence loaded from .pak
                    status = sc_mod.PandaStatusCard(root, char_key="chorong")
                    try:
                        self.assertEqual(len(status.avatar_frames), 4)
                    finally:
                        status.close()

                    # Anniversary scene loader reads frame from .pak
                    fake_scene = object.__new__(ann_mod.AnniversaryScene)
                    fake_scene.parent = root
                    photo = fake_scene._load(pak_dir / "work" / "scenes" / "anniversary_419" / "loop_1.png", 100)
                    self.assertEqual(photo.height(), 100)

                    # Win32 WM_SETCURSOR subclass hook installs cleanly on Tk canvas HWND and restores on system
                    canvas = tk.Canvas(root, width=64, height=64)
                    canvas.pack()
                    root.update_idletasks()
                    hwnd = int(canvas.winfo_id())
                    self.assertTrue(cm.set_window_cursor(hwnd, "paw_smooth"))
                    self.assertIn(hwnd, cm._HWND_HOOKS)
                    self.assertTrue(cm.reset_window_cursor(hwnd))
                    self.assertNotIn(hwnd, cm._HWND_HOOKS)
            finally:
                tray_obj = food_panel = menu = settings_panel = guide = None
                child_buttons = card = status = fake_scene = photo = canvas = None
                cm._CURSOR_CACHE.clear()
                cm._CURSOR_CACHE.update(orig_cache)
                try:
                    root.update_idletasks()
                except Exception:
                    pass
                root.destroy()
                gc.collect()


if __name__ == "__main__":
    unittest.main()
