"""Build provenance rejects stale inputs and missing/tampered packaged resources."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.build_provenance import capture_inputs, normalized_code, verify_and_record, write_snapshot


class BuildProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.folder = Path(self.tmp.name) / "portable"
        for rel in ("app/main.py", "PandaDesktopPet.spec", "build_exe.bat", "requirements.txt",
                    "requirements-build.txt", "LICENSE", "ASSETS-LICENSE.md",
                    "tools/runtime_manifest.py", "tools/build_provenance.py", "work/icon.png"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(rel.encode())
        self.patch = patch("tools.runtime_manifest.runtime_files", return_value=["work/icon.png"])
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.archive_check = patch("tools.build_provenance.verify_embedded_code", return_value=["main"])
        self.archive_check.start()
        self.addCleanup(self.archive_check.stop)
        self.snapshot = write_snapshot(self.root, self.folder / "_internal/build_inputs.json")
        for rel in ("work/icon.png", "LICENSE", "ASSETS-LICENSE.md"):
            path = self.folder / "_internal" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / rel, path)
        (self.folder / "PandaDesktopPet.exe").write_bytes(b"synthetic executable fixture")

    def test_exact_inputs_and_resources_produce_bound_report(self):
        report = verify_and_record(self.root, self.folder)
        self.assertEqual(report["status"], "BUILD_BYTES_VERIFIED_RUNTIME_NOT_TESTED")
        self.assertEqual(report["inputs"], capture_inputs(self.root))
        self.assertEqual(json.loads((self.folder / "build_manifest.json").read_text()), report)
        self.assertNotIn(str(self.root), self.snapshot.read_text())

    def test_source_changed_after_snapshot_is_rejected(self):
        (self.root / "app/main.py").write_bytes(b"newer code")
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            verify_and_record(self.root, self.folder)
        self.assertFalse((self.folder / "build_manifest.json").exists())

    def test_added_source_module_is_also_detected(self):
        (self.root / "app/new_module.py").write_bytes(b"new module")
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            verify_and_record(self.root, self.folder)

    def test_bad_resources_and_notices_do_not_get_success_report(self):
        for rel in ("work/icon.png", "LICENSE", "ASSETS-LICENSE.md"):
            path = self.folder / "_internal" / rel
            original = path.read_bytes()
            path.write_bytes(b"tampered")
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, "missing or changed"):
                verify_and_record(self.root, self.folder)
            self.assertFalse((self.folder / "build_manifest.json").exists())
            path.write_bytes(original)

    def test_missing_executable_is_rejected(self):
        (self.folder / "PandaDesktopPet.exe").unlink()
        with self.assertRaisesRegex(ValueError, "executable missing"):
            verify_and_record(self.root, self.folder)

    def test_old_executable_cannot_pass_with_a_copied_new_snapshot(self):
        with patch("tools.build_provenance.verify_embedded_code",
                   side_effect=ValueError("embedded application code differs: main")):
            with self.assertRaisesRegex(ValueError, "embedded application code differs"):
                verify_and_record(self.root, self.folder)
        self.assertFalse((self.folder / "build_manifest.json").exists())

    def test_code_comparison_ignores_paths_but_retains_nested_behavior(self):
        first = compile("def f():\n return 1\n", "machine_A/module.py", "exec")
        moved = compile("def f():\n return 1\n", "machine_B/module.py", "exec")
        changed = compile("def f():\n return 2\n", "machine_A/module.py", "exec")
        self.assertEqual(normalized_code(first), normalized_code(moved))
        self.assertNotEqual(normalized_code(first), normalized_code(changed))

    def test_pak_bundle_verifies_and_rejects_loose_or_tampered_assets(self):
        from tools.pack_assets import pack_assets

        pak_folder = Path(self.tmp.name) / "portable_pak"
        snapshot = write_snapshot(self.root, pak_folder / "_internal/build_inputs.json")
        self.assertTrue(snapshot.is_file())
        pack_assets(self.root, pak_folder / "_internal/assets.pak", rel_paths=["work/icon.png"])
        for name in ("LICENSE", "ASSETS-LICENSE.md"):
            shutil.copy2(self.root / name, pak_folder / "_internal" / name)
        (pak_folder / "PandaDesktopPet.exe").write_bytes(b"synthetic executable fixture")

        report = verify_and_record(self.root, pak_folder)
        self.assertEqual(report["packaging_mode"], "pak")
        self.assertIn("assets_pak_sha256", report)

        # Reject loose PNG leaked into _internal/ alongside assets.pak
        leaked = pak_folder / "_internal/leak.png"
        leaked.write_bytes(b"png")
        with self.assertRaisesRegex(ValueError, "loose image/cursor"):
            verify_and_record(self.root, pak_folder)
        leaked.unlink()

        # Reject corrupted assets.pak payload
        pak_path = pak_folder / "_internal/assets.pak"
        raw = bytearray(pak_path.read_bytes())
        raw[24] ^= 0xFF
        pak_path.write_bytes(bytes(raw))
        with self.assertRaisesRegex(ValueError, "sha256|missing or changed"):
            verify_and_record(self.root, pak_folder)


if __name__ == "__main__":
    unittest.main()
