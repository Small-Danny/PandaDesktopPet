"""Headless fixtures for review gates, normalization, fallback and cache limits."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from tools.asset_catalog import baseline_policy, build_catalog
from app.engine.assets import AssetRegistry, AssetUnavailable
from app.engine.contracts import AssetResolver
from app.asset_images import AssetImageCache


class AssetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "work/characters"
        member = self.assets / "bomi"
        member.mkdir(parents=True)
        manifest = {"frames": {}}
        for action in ("idle", "walk", "cheer", "sleep"):
            frames = []
            for index in range(2):
                name = f"{action}_{index + 1:02}.png"
                image = Image.new("RGBA", (192, 192))
                ImageDraw.Draw(image).rectangle((60, 30, 130, 183), fill=(255, 120, index, 255))
                image.save(member / name)
                frames.append(name)
            manifest["frames"][action] = frames
        (member / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        pending = Image.new("RGBA", (256, 256))
        ImageDraw.Draw(pending).rectangle((24, 24, 232, 232), fill=(255, 0, 0, 255))
        pending.save(member / "pending.png")
        Image.new("RGBA", (256, 256), (255, 0, 0, 255)).save(member / "preview_sheet.png")
        self.policy = baseline_policy(self.assets)
        self.path = self.root / "work/asset_registry.json"
        self.rebuild()

    def rebuild(self, limit=32 * 1024 * 1024):
        self.catalog = build_catalog(self.assets, self.policy)
        self.path.write_text(json.dumps(self.catalog), encoding="utf-8")
        self.registry = AssetRegistry(self.path, self.root)
        self.images = AssetImageCache(self.registry, limit)

    def test_inventory_deterministic_and_pending_is_not_approved(self):
        self.assertEqual(self.catalog, build_catalog(self.assets, self.policy))
        self.assertEqual(self.catalog["summary"]["png_count"], 10)
        self.assertEqual(self.catalog["summary"]["review_status_counts"], {
            "approved": 8, "excluded": 1, "pending_review": 1})
        self.assertEqual(self.registry.resolve("bomi", "pending").action, "idle")
        self.assertNotIn("pending", self.registry.actions("bomi"))

    def test_actions_reuses_validated_records_until_signature_changes(self):
        frame = self.assets / "bomi/idle_01.png"
        store = self.registry.store
        with patch.object(store, "sha256", wraps=store.sha256) as sha:
            actions = self.registry.actions("bomi")
            self.assertGreater(sha.call_count, 0)
            sha.reset_mock()
            self.assertEqual(self.registry.actions("bomi"), actions)
            sha.assert_not_called()

            st = frame.stat()
            os.utime(frame, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
            self.assertEqual(self.registry.actions("bomi"), actions)
            sha.assert_called_once_with("work/characters/bomi/idle_01.png")
            frame.unlink()
            self.assertNotIn("idle", self.registry.actions("bomi"))

    def test_contract_paths_and_normalization(self):
        self.assertIsInstance(self.registry, AssetResolver)
        spec = self.registry.resolve("bomi", "walk")
        self.assertEqual(spec.canvas, (256, 256))
        self.assertEqual(spec.anchor, (128, 244))
        self.assertTrue(spec.frames[0].startswith("work/characters/"))
        frames = self.images.load_frames(spec)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].size, (256, 256))
        self.assertEqual(frames[0].getchannel("A").getbbox()[3], 244)

    def test_changed_approved_bytes_require_review(self):
        Image.new("RGBA", (192, 192)).save(self.assets / "bomi/walk_01.png")
        self.assertEqual(self.registry.resolve("bomi", "walk").action, "idle")
        self.rebuild()
        self.assertEqual(self.catalog["files"]["bomi/walk_01"]["review_status"], "blocked")

    def test_missing_frame_falls_back_whole_animation(self):
        spec = self.registry.resolve("bomi", "walk")
        (self.assets / "bomi/walk_01.png").unlink()
        fallback = self.registry.resolve("bomi", "walk")
        self.assertEqual(fallback.action, "idle")
        actual, frames = self.images.load_animation(spec)
        self.assertEqual(actual.action, "idle")
        self.assertEqual(len(frames), 2)

    def test_no_safe_baseline_returns_none_and_load_raises(self):
        spec = self.registry.resolve("bomi", "walk")
        for path in (self.assets / "bomi").glob("*_0*.png"):
            path.unlink()
        self.assertIsNone(self.registry.resolve("bomi", "walk"))
        with self.assertRaises(AssetUnavailable):
            self.images.load_frames(spec)

    def test_preview_cannot_be_whitelisted(self):
        import hashlib
        path = self.assets / "bomi/preview_sheet.png"
        self.policy["approved"]["bomi/preview_sheet.png"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.rebuild()
        self.assertFalse(self.catalog["files"]["bomi/preview_sheet"]["runtime_ok"])
        self.assertNotIn("preview_sheet", self.registry.actions("bomi"))

    def test_known_semantic_block_cannot_be_whitelisted(self):
        import hashlib
        relative = "eunji/situational_v6_3/eunji_microphone_belt.png"
        path = self.assets / relative
        path.parent.mkdir(parents=True)
        Image.new("RGBA", (256, 256), (1, 2, 3, 255)).save(path)
        self.policy["approved"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.rebuild()
        self.assertEqual(self.catalog["files"][relative.removesuffix(".png")]["review_status"], "blocked")

    def test_cache_budget_eviction_and_release(self):
        self.rebuild(limit=256 * 256 * 4)
        self.images.load_frames(self.registry.resolve("bomi", "walk"))
        self.assertEqual(self.images.cache_size_bytes, 256 * 256 * 4)
        self.assertEqual(len(self.images._cache), 1)
        self.images.clear_cache()
        self.assertEqual(self.images.cache_size_bytes, 0)

    def test_zero_cache_does_not_retain_decoded_images(self):
        self.rebuild(limit=0)
        frames = self.images.load_frames(self.registry.resolve("bomi", "walk"))
        self.assertEqual(len(frames), 2)
        self.assertEqual(self.images.cache_size_bytes, 0)

    def test_fallback_cycle_terminates_at_baseline(self):
        self.registry.data["assets"]["bomi.bad"] = {"runtime_ok": False, "fallback": "bomi.other"}
        self.registry.data["assets"]["bomi.other"] = {"runtime_ok": False, "fallback": "bomi.bad"}
        self.assertEqual(self.registry.resolve("bomi", "bad").action, "idle")

    def test_asset_tree_escape_rejected(self):
        item = self.registry.data["assets"]["bomi.walk"]
        item["frames"] = ["work/characters/../../outside.png"]
        self.assertEqual(self.registry.resolve("bomi", "walk").action, "idle")

    def test_missing_root_is_error(self):
        with self.assertRaises(ValueError):
            build_catalog(self.root / "missing", self.policy)


if __name__ == "__main__":
    unittest.main()
