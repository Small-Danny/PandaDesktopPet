"""Headless regression: reviewed action offsets survive registry decode."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from app.asset_images import AssetImageCache
from app.engine.assets import AssetRegistry
from tools.asset_catalog import baseline_policy, build_catalog


class PreservedCanvasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / "work/characters"
        member = self.assets / "bomi"
        member.mkdir(parents=True)
        frames = {}
        for action in ("idle", "walk", "cheer", "sleep"):
            im = Image.new("RGBA", (256, 256))
            ImageDraw.Draw(im).rectangle((70, 40, 150, 230), fill="orange")
            im.save(member / f"{action}_01.png")
            frames[action] = [f"{action}_01.png"]
        (member / "manifest.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
        self.policy = baseline_policy(self.assets)
        self.originals = []
        self.paths = []
        for i, box in enumerate(((80, 100, 110, 239), (105, 65, 135, 204))):
            im = Image.new("RGBA", (256, 256))
            ImageDraw.Draw(im).rectangle(box, fill=(200, 80, 40, 255))
            path = member / "jump" / f"frame_{i}.png"
            path.parent.mkdir(exist_ok=True)
            im.save(path)
            rel = path.relative_to(self.assets).as_posix()
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.policy["approved"][rel] = sha
            self.policy.setdefault("preserve_canvas", {})[rel] = sha
            self.paths.append(rel)
            self.originals.append(im)
        self.policy["animations"] = {"bomi.jump": {
            "member": "bomi", "action": "jump", "frames": self.paths + [self.paths[0]],
            "fps": 6, "tags": ["standby"], "loop": False,
        }}

    def load(self, policy=None):
        catalog = build_catalog(self.assets, policy or self.policy)
        path = self.root / "work/registry.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        registry = AssetRegistry(path, self.root)
        return catalog, registry, AssetImageCache(registry)

    def test_preserves_pixels_offsets_and_explicit_repeat_order(self):
        catalog, registry, cache = self.load()
        spec = registry.resolve("bomi", "jump")
        self.assertEqual(spec.action, "jump")
        self.assertEqual(spec.fps, 6)
        actual, frames = cache.load_animation(spec)
        self.assertEqual(actual.asset_id, "bomi.jump")
        for actual_image, expected in zip(frames, self.originals + [self.originals[0]]):
            self.assertEqual(actual_image.tobytes(), expected.tobytes())
        self.assertNotEqual(frames[0].getchannel("A").getbbox(), frames[1].getchannel("A").getbbox())
        self.assertEqual(catalog, build_catalog(self.assets, self.policy))

    def test_base_decode_is_unchanged(self):
        _, before, old_cache = self.load({k: v for k, v in self.policy.items()
                                         if k not in ("animations", "preserve_canvas")})
        expected = old_cache.load_frames(before.resolve("bomi", "walk"))[0].tobytes()
        _, after, new_cache = self.load()
        self.assertEqual(new_cache.load_frames(after.resolve("bomi", "walk"))[0].tobytes(), expected)

    def test_preserve_hash_is_independent_review_gate(self):
        self.policy["preserve_canvas"][self.paths[0]] = "0" * 64
        catalog, registry, _ = self.load()
        self.assertEqual(catalog["files"][self.paths[0][:-4]]["review_status"], "blocked")
        self.assertEqual(registry.resolve("bomi", "jump").action, "idle")

    def test_pending_frame_cannot_enter_group(self):
        self.policy["approved"].pop(self.paths[1])
        _, registry, _ = self.load()
        self.assertNotIn("jump", registry.actions("bomi", "standby"))

    def test_invalid_group_cannot_override_base_or_escape(self):
        cases = [{"fps": float("nan")}, {"fps": True}, {"tags": "standby"},
                 {"frames": ["bomi/../../outside.png"]}, {"frames": ["eunji/frame.png"]}]
        for changes in cases:
            with self.subTest(changes=changes):
                policy = copy.deepcopy(self.policy)
                policy["animations"]["bomi.jump"].update(changes)
                with self.assertRaises(ValueError):
                    self.load(policy)
        policy = copy.deepcopy(self.policy)
        group = policy["animations"].pop("bomi.jump")
        group["action"] = "walk"
        policy["animations"]["bomi.walk"] = group
        with self.assertRaises(ValueError):
            self.load(policy)

    def test_unknown_decode_mode_falls_back_instead_of_reanchoring(self):
        _, registry, cache = self.load()
        registry.data["files"][self.paths[0][:-4]]["normalization_mode"] = "unknown"
        actual, _ = cache.load_animation(registry.resolve("bomi", "jump"))
        self.assertEqual(actual.action, "idle")

    def test_group_cannot_mix_normalization_modes(self):
        self.policy["preserve_canvas"].pop(self.paths[0])
        with self.assertRaisesRegex(ValueError, "mixes reviewed normalization modes"):
            self.load()

    def test_invalid_preserve_policy_fails_before_inventory(self):
        self.policy["preserve_canvas"] = [self.paths[0]]
        with self.assertRaisesRegex(ValueError, "must be objects"):
            self.load()

    def large_fixture(self):
        for index, relative in enumerate(self.paths):
            image = Image.new("RGBA", (384, 384))
            image.paste(self.originals[index], (64, 128))
            path = self.assets / relative
            image.save(path)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.policy["approved"][relative] = sha
            self.policy["preserve_canvas"][relative] = sha
            self.originals[index] = image
        self.policy["animations"]["bomi.jump"]["canvas"] = [384, 384]

    def test_large_canvas_preserves_pixels_anchor_and_cache_budget(self):
        self.large_fixture()
        _, registry, cache = self.load()
        spec = registry.resolve("bomi", "jump")
        self.assertEqual(spec.canvas, (384, 384))
        self.assertEqual(spec.anchor, (192, 372))
        actual, frames = cache.load_animation(spec)
        self.assertEqual(actual.action, "jump")
        for frame, expected in zip(frames, self.originals + [self.originals[0]]):
            self.assertEqual(frame.tobytes(), expected.tobytes())
        self.assertEqual(cache.cache_size_bytes, 2 * 384 * 384 * 4)
        limited = AssetImageCache(registry, cache_bytes=384 * 384 * 4)
        limited.load_animation(spec)
        self.assertLessEqual(limited.cache_size_bytes, 384 * 384 * 4)

    def test_large_canvas_requires_standby_and_matching_file_geometry(self):
        self.large_fixture()
        self.policy["animations"]["bomi.jump"]["tags"] = []
        with self.assertRaisesRegex(ValueError, "tagged standby"):
            self.load()
        self.policy["animations"]["bomi.jump"]["tags"] = ["standby"]
        self.policy["animations"]["bomi.jump"]["canvas"] = [256, 256]
        with self.assertRaisesRegex(ValueError, "geometry differs"):
            self.load()

    def test_runtime_rejects_large_canvas_missing_gate_or_tampered_anchor(self):
        self.large_fixture()
        _, registry, _ = self.load()
        item = registry.data["assets"]["bomi.jump"]
        for changes in ({"tags": []}, {"tags": None}, {"anchor": [128, 244]},
                        {"canvas": [384.0, 384.0]}):
            with self.subTest(changes=changes):
                original = copy.deepcopy(item)
                item.update(changes)
                self.assertEqual(registry.resolve("bomi", "jump").action, "idle")
                item.clear()
                item.update(original)

    def test_desktop_action_is_explicit_opt_in_for_large_canvas(self):
        self.large_fixture()
        self.policy["animations"]["bomi.jump"]["tags"] = ["desktop_action"]
        _, registry, cache = self.load()
        spec = registry.resolve("bomi", "jump")
        self.assertEqual(spec.canvas, (384, 384))
        self.assertEqual(spec.tags, ("desktop_action",))
        self.assertEqual(len(cache.load_frames(spec)), 3)

    def test_hanging_props_may_extend_below_the_feet_on_tall_canvas(self):
        self.large_fixture()
        for index, relative in enumerate(self.paths):
            image = Image.new("RGBA", (384, 416))
            image.paste(self.originals[index], (0, 0))
            ImageDraw.Draw(image).rectangle((270, 380, 280, 405), fill="purple")
            path = self.assets / relative
            image.save(path)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.policy["approved"][relative] = sha
            self.policy["preserve_canvas"][relative] = sha
        self.policy["animations"]["bomi.jump"]["canvas"] = [384, 416]
        _, registry, cache = self.load()
        spec = registry.resolve("bomi", "jump")
        self.assertEqual(spec.anchor, (192, 372))
        self.assertEqual(spec.canvas, (384, 416))
        images = cache.load_frames(spec)
        self.assertEqual(images[0].getpixel((275, 400))[3], 255)

    def test_secret_visitor_has_separate_namespace_and_requires_hidden_policy(self):
        relative = "shared/secret_visitor/frame.png"
        path = self.assets / relative
        path.parent.mkdir(parents=True)
        self.originals[0].save(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.policy["approved"][relative] = digest
        self.policy["preserve_canvas"][relative] = digest
        trigger = dict(mode="easter_egg_only", allowed_contexts=["concert_stage_audience", "anniversary_0419"],
                       allow_random_cameo=False, expose_name_in_ui=False)
        self.policy["animations"]["shared.secret_clover_visitor"] = dict(
            member="shared", action="secret_clover_visitor", frames=[relative, relative], fps=6,
            tags=["desktop_action", "secret"], trigger_policy=trigger)
        _, registry, cache = self.load()
        spec = registry.resolve(None, "secret_clover_visitor")
        self.assertEqual(spec.member, None)
        self.assertEqual(len(cache.load_frames(spec)), 2)
        self.assertNotIn("secret_clover_visitor", registry.actions("bomi"))
        self.assertEqual(registry.actions(None, "standby"), ())
        trigger["allow_random_cameo"] = True
        with self.assertRaisesRegex(ValueError, "hidden-only"):
            self.load()


if __name__ == "__main__":
    unittest.main()
