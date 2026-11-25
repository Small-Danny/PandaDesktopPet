"""Bind a portable build to its exact source/resource bytes, without user data.

The spec writes build_inputs.json before compilation. After PyInstaller finishes,
verify the bundled copy and current inputs before recording artifact hashes.
This is build consistency evidence, not a GUI/runtime acceptance certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import marshal
from pathlib import Path
import sys
from types import CodeType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write_portable_notices(root: Path, output: Path) -> None:
    """Prepare readable release notices without building or changing assets."""
    output.mkdir(parents=True, exist_ok=True)
    text = (root / "README_PORTABLE.txt").read_text(encoding="utf-8-sig")
    (output / "README.txt").write_text(text, encoding="utf-8-sig")
    (output / "LICENSE").write_bytes((root / "LICENSE").read_bytes())
    (output / "ASSETS-LICENSE.md").write_bytes((root / "ASSETS-LICENSE.md").read_bytes())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def capture_inputs(root: Path) -> dict:
    from tools.runtime_manifest import runtime_files

    root = root.resolve()
    sources = {p.relative_to(root).as_posix() for p in (root / "app").rglob("*.py")}
    sources.update(("PandaDesktopPet.spec", "build_exe.bat", "requirements.txt",
                    "requirements-build.txt", "LICENSE", "ASSETS-LICENSE.md",
                    "tools/runtime_manifest.py", "tools/build_provenance.py"))
    if (root / "tools/pack_assets.py").is_file():
        sources.add("tools/pack_assets.py")
    for path in ("README_PORTABLE.txt", "installer/PandaDesktopPet.iss"):
        if (root / path).is_file():
            sources.add(path)
    paths = sorted(sources | set(runtime_files(root)))
    hashes = {}
    for rel in paths:
        path = (root / rel).resolve()
        path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or linked build input: {rel}")
        hashes[rel] = digest(path)
    return {"schema_version": 1, "files": hashes}


def write_snapshot(root: Path, target: Path) -> Path:
    data = capture_inputs(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(encoded(data), encoding="utf-8")
    return target


def normalized_code(code: CodeType) -> CodeType:
    """Ignore build-machine filenames, retaining the actual compiled program."""
    return code.replace(co_filename="<source>", co_consts=tuple(
        normalized_code(value) if isinstance(value, CodeType) else value
        for value in code.co_consts))


def verify_embedded_code(root: Path, exe: Path) -> list[str]:
    # A copied new JSON file beside an old EXE must never pass verification.
    # PyInstaller is a build dependency only; the running pet does not import it.
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(exe))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    modules = {"main": marshal.loads(archive.extract("main"))}
    for name in pyz.toc:
        if name.startswith("app."):
            code = pyz.extract(name)
            if isinstance(code, CodeType):
                modules[name] = code
    required = {"main", "app.paths", "app.food_panel", "app.resource_store"}
    if not required.issubset(modules):
        raise ValueError("executable is missing required application modules")
    verified = []
    for name, actual in modules.items():
        relative = "app/main.py" if name == "main" else name.replace(".", "/") + ".py"
        path = root / relative
        if not path.is_file():
            path = root / relative.removesuffix(".py") / "__init__.py"
        if not path.is_file():
            raise ValueError(f"embedded module has no reviewed source: {name}")
        expected = compile(path.read_bytes(), str(path), "exec", dont_inherit=True, optimize=0)
        if normalized_code(actual) != normalized_code(expected):
            raise ValueError(f"embedded application code differs: {name}")
        verified.append(name)
    return sorted(verified)


def verify_and_record(root: Path, folder: Path) -> dict:
    folder = folder.resolve()
    snapshot = folder / "_internal" / "build_inputs.json"
    recorded = json.loads(snapshot.read_text(encoding="utf-8"))
    current = capture_inputs(root)
    if recorded != current:
        raise ValueError("build inputs changed or the bundled snapshot is stale; rebuild required")
    exe = folder / "PandaDesktopPet.exe"
    if not exe.is_file():
        raise ValueError("portable executable missing")
    verified_modules = verify_embedded_code(root, exe)
    internal_dir = folder / "_internal"
    expected_work = {
        rel: expected
        for rel, expected in recorded["files"].items()
        if rel.startswith("work/")
    }
    pak_path = internal_dir / "assets.pak"
    if pak_path.is_file():
        if (internal_dir / "work").exists():
            raise ValueError("loose work directory must not be bundled alongside assets.pak")
        loose_assets = sorted(
            p.relative_to(internal_dir).as_posix()
            for p in internal_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".cur"}
        )
        if loose_assets:
            raise ValueError(
                f"loose image/cursor files bundled alongside assets.pak: {loose_assets[0]}"
            )
        from app.resource_store import PakResourceStore

        store = PakResourceStore(pak_path, base_root=internal_dir)
        with store.session():
            actual_keys = set(store.list_keys("work/"))
            expected_keys = set(expected_work)
            if actual_keys != expected_keys:
                missing = sorted(expected_keys - actual_keys)
                extra = sorted(actual_keys - expected_keys)
                raise ValueError(
                    f"assets.pak entries mismatch (missing={missing[:3]}, extra={extra[:3]})"
                )
            for rel, expected in expected_work.items():
                if store.sha256(rel) != expected:
                    raise ValueError(f"bundled resource missing or changed: {rel}")
        packaging_mode = "pak"
        pak_sha = digest(pak_path)
    else:
        # Legacy loose resource layout (preserved for fixture tests and fallback builds).
        for rel, expected in expected_work.items():
            path = internal_dir / rel
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f"bundled resource missing or changed: {rel}")
        packaging_mode = "loose"
        pak_sha = None
    for name in ("LICENSE", "ASSETS-LICENSE.md"):
        path = internal_dir / name
        if not path.is_file() or digest(path) != recorded["files"][name]:
            raise ValueError(f"bundled notice missing or changed: {name}")
    report = {
        "schema_version": 1,
        "status": "BUILD_BYTES_VERIFIED_RUNTIME_NOT_TESTED",
        "packaging_mode": packaging_mode,
        "input_snapshot_sha256": digest(snapshot),
        "executable_sha256": digest(exe),
        "inputs": recorded,
        "python_version": sys.version.split()[0],
        "embedded_app_modules_verified": verified_modules,
    }
    if pak_sha is not None:
        report["assets_pak_sha256"] = pak_sha
    target = folder / "build_manifest.json"
    target.write_text(encoded(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="built portable folder containing the exe")
    args = parser.parse_args()
    report = verify_and_record(ROOT, args.folder)
    print(report["status"], report["executable_sha256"])


if __name__ == "__main__":
    main()
