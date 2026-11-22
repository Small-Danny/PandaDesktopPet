"""Synthetic release-boundary tests; no original artwork or user data is needed."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import export_public_repo as public
from tools import runtime_manifest as runtime


class PublicExportTest(unittest.TestCase):
    def test_full_export_only_copies_allowlisted_documentation_screenshots(self):
        for rel in public.DOC_SCREENSHOT_ALLOWLIST:
            self.write(rel, b"reviewed screenshot")
        for rel in ("docs/screenshots/sprites.png", "docs/screenshots/old.jpg"):
            self.write(rel, b"unreviewed screenshot")
        target = Path(self.tmp.name) / "full_with_screenshots"
        public.export(target, self.root, include_assets=True)
        docs = target / "docs/screenshots"
        self.assertEqual(
            {path.relative_to(target).as_posix() for path in docs.rglob("*") if path.is_file()},
            public.DOC_SCREENSHOT_ALLOWLIST,
        )
        report = json.loads((target / "PUBLIC_EXPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertEqual(report["documentation_screenshots"], sorted(public.DOC_SCREENSHOT_ALLOWLIST))
        self.assertEqual(report["audit"], [])

    def test_documentation_screenshots_exact_allowlist(self):
        for rel in public.DOC_SCREENSHOT_ALLOWLIST:
            self.write(rel, b'documentation fixture')
        for rel in ('docs/screenshots/unreviewed.jpg', 'docs/screenshots/sprites.png',
                    'reference/desktop_interaction.jpg', 'work/desktop_interaction.jpg',
                    'staging/fortune_room.jpg', 'docs/screenshots/assets.pak'):
            self.write(rel, b'private fixture')
            self.assertNotIn(rel, public.public_files(self.root, include_assets=False))
            self.assertTrue(public.audit(self.root, [rel], include_assets=False))
        files = public.public_files(self.root, include_assets=False)
        self.assertTrue(public.DOC_SCREENSHOT_ALLOWLIST.issubset(files))
        self.assertEqual(public.audit(self.root, files, include_assets=False), [])
        target = Path(self.tmp.name) / 'documentation_code'
        public.export(target, self.root, include_assets=False)
        report = json.loads((target/'PUBLIC_EXPORT_REPORT.json').read_text(encoding='utf-8'))
        self.assertEqual(report['documentation_screenshots'], sorted(public.DOC_SCREENSHOT_ALLOWLIST))
        self.assertEqual(report['audit'], [])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        self.frame = "bomi/idle_01.png"
        self.write("work/characters/" + self.frame, b"synthetic approved image")
        self.record = {"path": self.frame, "sha256": self.digest("work/characters/" + self.frame),
                       "review_status": "approved", "runtime_ok": True}
        self.registry = {"files": {"bomi/idle_01": self.record}}
        for name in runtime.RUNTIME_FILES:
            self.write(name, b"{}")
        self.save_registry()
        for name in public.TOOLS:
            self.write("tools/" + name, b"# synthetic pipeline dependency\n")

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def digest(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def save_registry(self):
        self.write("work/asset_registry.json", json.dumps(self.registry).encode())

    def test_only_known_approved_hash_bound_character_frames_are_included(self):
        self.write("work/characters/bomi/new_unreviewed.png", b"not approved")
        self.write("work/characters/bomi/blocked.png", b"blocked")
        self.registry["files"]["blocked"] = dict(self.record, path="bomi/blocked.png", review_status="blocked")
        self.save_registry()
        files = runtime.runtime_files(self.root)
        self.assertIn("work/characters/" + self.frame, files)
        self.assertNotIn("work/characters/bomi/new_unreviewed.png", files)
        self.assertNotIn("work/characters/bomi/blocked.png", files)

    def test_changed_or_missing_approved_frame_refuses_both_build_and_export(self):
        self.write("work/characters/" + self.frame, b"changed after approval")
        with self.assertRaisesRegex(ValueError, "approved character bytes changed"):
            runtime.runtime_files(self.root)
        with self.assertRaisesRegex(ValueError, "approved character bytes changed"):
            public.public_files(self.root)
        (self.root / "work/characters" / self.frame).unlink()
        with self.assertRaises(FileNotFoundError):
            runtime.runtime_files(self.root)

    def test_nested_user_data_backups_logs_and_source_images_are_never_resources(self):
        bad = []
        for directory in runtime.RUNTIME_DIRS:
            for suffix in ("settings.json", "runtime.json", "private/portrait.png", "BACKUP/old.png",
                           "backup_2026/old.png", "logs/log.png", "source/raw.png", "old.png.bak"):
                relative = directory + "/" + suffix
                self.write(relative, b"synthetic private marker")
                bad.append(relative)
        self.write("work/foods/food.png", b"public icon")
        self.write("work/foods/foods_preview.png", b"preview strip")
        self.write("work/ui_icons/_preview_ui_icons.png", b"preview icons")
        files = runtime.runtime_files(self.root)
        self.assertIn("work/foods/food.png", files)
        self.assertNotIn("work/foods/foods_preview.png", files)
        self.assertNotIn("work/ui_icons/_preview_ui_icons.png", files)
        self.assertFalse(set(files).intersection(bad))

    def test_approved_private_or_escaping_paths_are_rejected(self):
        for relative in ("../outside.png", "/absolute.png", "bomi/private/portrait.png",
                         "bomi/backup_2026/frame.png", "bomi/settings.png"):
            with self.subTest(relative=relative):
                self.record["path"] = relative
                self.save_registry()
                with self.assertRaises(ValueError):
                    runtime.runtime_files(self.root)

    def test_legacy_fallback_keeps_only_explicit_original_frame_names(self):
        manifest = {"frames": {"idle": ["idle_01.png"]}}
        self.write("work/rongdoong_processed_v2/manifest.json", json.dumps(manifest).encode())
        self.write("work/rongdoong_processed_v2/idle_01.png", b"known legacy frame")
        self.write("work/rongdoong_processed_v2/new_unreviewed.png", b"unknown")
        files = runtime.runtime_files(self.root)
        self.assertIn("work/rongdoong_processed_v2/idle_01.png", files)
        self.assertNotIn("work/rongdoong_processed_v2/new_unreviewed.png", files)
        manifest["frames"]["idle"] = ["new_unreviewed.png"]
        self.write("work/rongdoong_processed_v2/manifest.json", json.dumps(manifest).encode())
        with self.assertRaisesRegex(ValueError, "unexpected legacy"):
            runtime.runtime_files(self.root)

    def test_transitive_cutout_dependency_is_required_in_the_public_pipeline(self):
        self.assertIn("extract_rongdoong.py", public.TOOLS)
        self.assertIn("tools/extract_rongdoong.py", public.public_files(self.root))
        (self.root / "tools/extract_rongdoong.py").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "extract_rongdoong"):
            public.public_files(self.root)

    def test_workshop_source_art_tests_are_preserved_and_separated_not_auto_passed(self):
        original = b'raise RuntimeError("matching original fixtures are required")\n'
        self.write("tests/test_bubble_asset_preparation.py", original)
        self.write("tests/test_portable.py", b"import unittest\nclass Portable(unittest.TestCase):\n def test_ok(self): self.assertEqual(2+2,4)\n")
        target = Path(self.tmp.name) / "public"
        files = public.export(target, self.root)
        self.assertNotIn("tests/test_bubble_asset_preparation.py", files)
        self.assertEqual((target / "workshop_tests/test_bubble_asset_preparation.py").read_bytes(), original)
        report = json.loads((target / "PUBLIC_EXPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["workshop_tests"]), 1)
        self.assertIn("original", report["workshop_tests"][0]["required_private_inputs"])
        self.assertTrue(report["input_bytes_verified"])
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                                cwd=target, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "workshop_tests", "-q"],
                                cwd=target, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"matching original fixtures are required", result.stderr)

    def test_source_drift_during_export_refuses_a_mixed_snapshot(self):
        self.write("app/probe.py", b"old bytes\n")
        real_copy = public.shutil.copy2

        def mutate_then_copy(source, target):
            if Path(source).name == "probe.py":
                Path(source).write_bytes(b"new bytes\n")
            return real_copy(source, target)

        with patch.object(public.shutil, "copy2", side_effect=mutate_then_copy):
            with self.assertRaisesRegex(RuntimeError, "source changed while exporting"):
                public.export(Path(self.tmp.name) / "public", self.root)

    def test_no_assets_export_excludes_all_binaries_and_separates_asset_tests(self):
        self.write("app/logic.py", b"VALUE = 42\n")
        self.write("docs/screenshots/demo.png", b"png")
        self.write("work/standby_backgrounds/bg.jpg", b"jpg")
        self.write("work/ui_icons/cursor.cur", b"cur")
        self.write("tests/test_pure_code.py", b"import unittest\nfrom app.logic import VALUE\nclass Pure(unittest.TestCase):\n def test_val(self): self.assertEqual(VALUE, 42)\n")
        self.write("tests/test_daily_actions.py", b'raise RuntimeError("needs approved sprites")\n')

        target = Path(self.tmp.name) / "code_only"
        git_sentinel = target / ".git" / "HEAD"
        git_sentinel.parent.mkdir(parents=True, exist_ok=True)
        git_sentinel.write_text("ref: refs/heads/master\n", encoding="utf-8")
        (target / "stale.txt").write_text("stale", encoding="utf-8")

        exported = public.export(target, self.root, include_assets=False, overwrite=True)
        self.assertFalse((target / "stale.txt").exists())
        self.assertTrue(git_sentinel.is_file())
        self.assertTrue((target / "ASSETS_REQUIRED.md").is_file())
        self.assertIn("tests/test_pure_code.py", exported)
        self.assertNotIn("tests/test_daily_actions.py", exported)
        self.assertIn("asset_tests/test_daily_actions.py", exported)

        binaries = [
            p for p in target.rglob("*")
            if p.is_file() and ".git" not in p.parts
            and (p.suffix.lower() in {".png", ".jpg", ".jpeg", ".cur", ".ico", ".pak"} or "work" in p.parts)
        ]
        self.assertEqual(binaries, [])

        report = json.loads((target / "PUBLIC_EXPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertFalse(report["include_assets"])
        self.assertEqual(len(report["asset_tests"]), 1)

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                                cwd=target, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_assets_standby_imports_relocated_alignment_sibling(self):
        # Exercise the real standby module's import, without creating Tk windows
        # or requiring production artwork in this synthetic public fixture.
        actual_path = Path(__file__).with_name('test_standby_pet_restore.py')
        if not actual_path.is_file():
            actual_path = Path(__file__).resolve().parents[1] / 'asset_tests/test_standby_pet_restore.py'
        actual = actual_path.read_bytes()
        self.write('tests/test_standby_pet_restore.py', actual)
        self.write('tests/test_action_window_alignment.py',
                   b'import unittest\nclass ActionWindowAlignmentTest(unittest.TestCase): pass\n')
        self.write('tests/__init__.py', b'')
        self.write('app/engine/contracts.py', b'GlobalMode = object\n')
        self.write('app/platform/win32.py', b'WorkArea = object\n')
        target = Path(self.tmp.name) / 'relocated_code_only'
        public.export(target, self.root, include_assets=False)
        self.assertFalse((target / 'tests/test_action_window_alignment.py').exists())
        script = (
            "import sys, pathlib, importlib.util; "
            "sys.path[:0] = [str(pathlib.Path.cwd()/'asset_tests'), str(pathlib.Path.cwd())]; "
            "assert importlib.util.find_spec('tests.test_action_window_alignment') is None; "
            "import test_standby_pet_restore as restored; "
            "assert restored.alignment.__name__ == 'test_action_window_alignment'; "
            "assert restored.StandbyPetRestoreTest.__bases__[0] is restored.alignment.ActionWindowAlignmentTest"
        )
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script], cwd=target,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
