"""Exact-source calibration guards for staging, with synthetic sheet pixels."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from app.visual_calibration import FACE_WIDTHS, action_scale, calibrated_frame
from tools import stage_googleflow_assets as staging


class RuntimeCalibrationTest(unittest.TestCase):
    def test_face_scales_preserve_feed_and_occluded_fallbacks(self):
        for action in ("special_taekwondo", "daily_surprise", "winter_cocoa"):
            self.assertIn(f"bomi.{action}", FACE_WIDTHS)
            self.assertGreater(action_scale("bomi", action), 1.0)
        excluded = {"chorong.daily_cat_cuddle", "namjoo.scene_flamingo", "eunji.fortune_love_reading"}
        self.assertTrue(excluded.isdisjoint(FACE_WIDTHS))
        self.assertFalse(any(key.split(".", 1)[1].startswith(("feed_", "christmas_gift"))
                             for key in FACE_WIDTHS))
        self.assertEqual(action_scale("bomi", "feed_americano", 0.92), 0.92)
        self.assertAlmostEqual(action_scale(None, "secret_clover_visitor"), 152 / 156)

    def test_lantern_frame_calibration_uses_verified_f3_only(self):
        cases = (
            ("bomi", "21ec13b6640742de53d005e04b0b73a672a140dd788d37f31538524bdf9204d4", 167, 274, 108),
            ("namjoo", "e6d7ba18efb062ef1d3c4912f16dfcf88ca7cd9a783571931ca63be7f2fd1862", 214, 335, 62),
        )
        for member, digest, split, feet, shift in cases:
            with self.subTest(member=member):
                image = Image.new("RGBA", (384, 416))
                draw = ImageDraw.Draw(image)
                draw.rectangle((10, 24, 30, split - 1), fill="pink")
                draw.rectangle((10, split, 30, feet - 1), fill="red")
                out = calibrated_frame(image, member, "festival_lantern", 2, digest)
                self.assertEqual(out.size, image.size)
                self.assertEqual(out.getbbox(), (10, 24 + shift, 31, 372))
                self.assertEqual(out.getpixel((15, split + shift - 1)), (255, 192, 203, 255))
                self.assertEqual(out.getpixel((15, split + shift)), (255, 0, 0, 255))
                self.assertIs(calibrated_frame(image, member, "festival_lantern", 1, digest), image)
                self.assertIs(calibrated_frame(image, member, "festival_lantern", 2, "0" * 64), image)


class StageCalibrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(staging, "ROOT", self.root).start()
        source = self.root / "reference/sheet.png"
        source.parent.mkdir()
        image = Image.new("RGB", (800, 240), "white")
        for col in range(4):
            ImageDraw.Draw(image).rectangle((col * 200 + 50, 60 - col * 4,
                                            col * 200 + 145, 210 - col * 4), fill="#502020")
        image.save(source)
        base = self.root / "work/characters/bomi/idle.png"
        base.parent.mkdir(parents=True)
        image.save(base)
        self.output = self.root / "work/staging/test"
        self.row = dict(slice_enabled=True, status="candidate", category="festival_variant",
                        member="bomi", action="festival_christmas", grid="1x4",
                        selected_cells=[[0, i] for i in range(4)], excluded_cells=[],
                        play_order=[0, 1, 2, 3], path="reference/sheet.png",
                        sha256=staging.digest(source), width=800, height=240)
        self.cal = {k: copy.deepcopy(self.row[k]) for k in
                    ("member", "action", "selected_cells", "play_order")}
        self.cal.update(source_sha256=self.row["sha256"], source_uniform_scale=.9,
                        base_source="work/characters/bomi/idle.png", base_source_sha256=staging.digest(base))

    def test_raw_source_is_scaled_once_with_common_anchor(self):
        record, frames = staging.stage(self.row, self.output, self.cal)
        self.assertEqual(record["canvas"], [384, 384])
        self.assertEqual(record["anchor"], [192, 372])
        self.assertEqual(record["scale"], .9)
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[0].size, (384, 384))
        self.assertEqual(set(frames[0].getchannel("A").tobytes()), {0, 255})
        self.assertGreater(frames[0].getchannel("A").getbbox()[3],
                           frames[3].getchannel("A").getbbox()[3])

    def test_mismatched_source_or_base_cannot_write_frames(self):
        for key in ("source_sha256", "base_source_sha256"):
            with self.subTest(key=key):
                cal = dict(self.cal, **{key: "0" * 64})
                with self.assertRaises(ValueError):
                    staging.stage(self.row, self.output, cal)
                self.assertEqual(list(self.output.rglob("*.png")), [])

    def test_oversized_or_nonfinite_scale_is_rejected_before_png_write(self):
        for scale in (10, float("nan"), True):
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError):
                    staging.stage(self.row, self.output, dict(self.cal, source_uniform_scale=scale))
                self.assertEqual(list(self.output.rglob("*.png")), [])

    def test_explicit_derived_sheet_requires_original_and_derived_hashes(self):
        path = self.root / "work/staging/derived.png"
        path.parent.mkdir(parents=True)
        Image.open(self.root / self.row["path"]).save(path)
        override = dict(path="work/staging/derived.png", sha256=staging.digest(path),
                        original_sha256=self.row["sha256"])
        row = dict(self.row, reviewed_source_override=override)
        self.assertEqual(staging.checked_source(row), path.resolve())
        for key in ("sha256", "original_sha256"):
            with self.subTest(key=key):
                broken = dict(row, reviewed_source_override=dict(override, **{key: "0" * 64}))
                with self.assertRaises(ValueError):
                    staging.checked_source(broken)

    def test_derived_sheet_cannot_escape_staging(self):
        row = dict(self.row, reviewed_source_override=dict(
            path=self.row["path"], sha256=self.row["sha256"], original_sha256=self.row["sha256"]))
        with self.assertRaisesRegex(ValueError, "outside allowed"):
            staging.checked_source(row)

    def test_reviewed_foot_landmarks_align_ground_without_scaling_each_pose(self):
        cal = dict(self.cal, canvas=[384, 416], source_feet_y=[211, 207, 203, 199])
        record, frames = staging.stage(self.row, self.output, cal)
        self.assertEqual(record["scale"], .9)
        for frame in frames:
            self.assertLessEqual(abs(frame.getchannel("A").getbbox()[3] - 372), 1)
        with self.assertRaisesRegex(ValueError, "foot landmarks"):
            staging.stage(self.row, self.output, dict(cal, source_feet_y=[True] * 4))

    def test_absolute_horizontal_landmarks_correct_uneven_grid_spacing(self):
        cal = dict(self.cal, source_centers_x=[98, 298, 498, 698])
        _, frames = staging.stage(self.row, self.output, cal)
        for frame in frames:
            box = frame.getchannel("A").getbbox()
            self.assertLessEqual(abs((box[0] + box[2]) / 2 - 192), 1)
        for bad in ([True] * 4, [100] * 3, [float("nan")] * 4, [900] * 4):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "horizontal landmarks"):
                staging.stage(self.row, self.output, dict(cal, source_centers_x=bad))

    def masked_row(self):
        source = Image.open(self.root / self.row["path"]).convert("RGB")
        directory = self.root / "work/staging/masks"
        directory.mkdir(parents=True)
        cells = []
        for c in range(4):
            crop = (c * 200, c * 3, (c + 1) * 200, 240)
            mask = staging.exterior_mask(source.crop(crop))
            path = directory / f"{c}.png"
            mask.save(path)
            cells.append(dict(cell=[0, c], crop=crop, alpha_mask=path.relative_to(self.root).as_posix(),
                              sha256=staging.digest(path)))
        return dict(self.row, reviewed_cell_masks=dict(original_sha256=self.row["sha256"], cells=cells))

    def test_reviewed_masks_preserve_original_pixels_and_source_offsets(self):
        _, expected = staging.stage(self.row, self.output / "plain")
        _, actual = staging.stage(self.masked_row(), self.output / "masked")
        self.assertEqual([im.tobytes() for im in expected], [im.tobytes() for im in actual])

    def test_changed_mask_cannot_write_frames(self):
        row = self.masked_row()
        row["reviewed_cell_masks"]["cells"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "cell mask changed"):
            staging.stage(row, self.output)
        self.assertEqual(list(self.output.rglob("frame*.png")), [])


if __name__ == "__main__":
    unittest.main()
