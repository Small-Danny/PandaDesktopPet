# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build of the portable (no-install) pet:  python -m PyInstaller --noconfirm PandaDesktopPet.spec
# Output: dist/PandaDesktopPet/PandaDesktopPet.exe + _internal/ (one folder, zip it to share).
# One-folder rather than one-file: starts faster and unpacks nothing into %TEMP% on every launch.
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from tools.build_provenance import write_snapshot  # noqa: E402
from tools.pack_assets import pack_assets  # noqa: E402


def _build_app_icon(src_png: Path, dst_ico: Path) -> Path:
    """Build multi-size Windows .ico from approved Chorong sprite into build/ (never in _internal/)."""
    dst_ico.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_png) as raw:
        rgba = raw.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        cropped = rgba.crop(bbox) if bbox else rgba
    side = max(cropped.width, cropped.height)
    pad = max(4, round(side * 0.06))
    canvas_side = side + pad * 2
    square = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    square.paste(cropped, ((canvas_side - cropped.width) // 2, (canvas_side - cropped.height) // 2), cropped)
    base = square.resize((256, 256), Image.Resampling.LANCZOS)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(dst_ico, format="ICO", sizes=sizes)
    return dst_ico


ico_path = _build_app_icon(ROOT / "work" / "characters" / "chorong" / "idle_01.png", ROOT / "build" / "PandaDesktopPet.ico")

# Bundle all validated runtime assets into a single indexed assets.pak container
# (zero loose PNG/JPG/CUR files exposed under dist/PandaDesktopPet/_internal/).
pak_summary = pack_assets(ROOT, ROOT / "build" / "assets.pak")
snapshot = write_snapshot(ROOT, ROOT / "build" / "build_inputs.json")
datas = [
    (pak_summary["output"], "."),
    (str(snapshot), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "ASSETS-LICENSE.md"), "."),
]

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    excludes=["numpy", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PandaDesktopPet",
    icon=str(ico_path),
    console=False,
    upx=False,          # UPX-packed executables trip antivirus heuristics
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="PandaDesktopPet")

# End-user notices must be visible beside the executable, outside _internal.
from tools.build_provenance import write_portable_notices
write_portable_notices(ROOT, Path(DISTPATH) / coll.name)
