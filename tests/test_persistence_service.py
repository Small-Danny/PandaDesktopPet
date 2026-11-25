"""Headless persistence checks; all writes are confined to temporary directories."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS, PersistenceService, UnsupportedSchemaError


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = PersistenceService(self.root)

    def test_empty_directory_defaults_do_not_write(self):
        settings, runtime = self.service.load()
        self.assertEqual(settings["mode"], "auto")
        self.assertEqual(runtime["feed_count"], 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_notification_style_defaults_on_legacy_load_and_round_trips(self):
        (self.root / "settings.json").write_text('{"mode":"manual"}', encoding="utf-8")
        self.assertEqual(self.service.load()[0]["notify_bubble_style"], "banner")
        for style in ("sticky", "standard", "banner"):
            self.service.save({"notify_bubble_style": style}, {})
            self.assertEqual(PersistenceService(self.root).load()[0]["notify_bubble_style"], style)
        saved = (self.root / "settings.json").read_bytes()
        for bad in ("unknown", [], None):
            with self.assertRaisesRegex(ValueError, "notify_bubble_style"):
                self.service.save({"notify_bubble_style": bad}, {})
        self.assertEqual((self.root / "settings.json").read_bytes(), saved)

    def test_first_migration_preserves_settings_and_stats_idempotently(self):
        legacy = {"mode": "manual", "manual_character": "bomi", "feed_count": 447,
                  "cheer_passion": 3450, "companion_start_time": 123.5, "extension": "保留"}
        original = json.dumps(legacy, ensure_ascii=False).encode("utf-8")
        (self.root / "settings.json").write_bytes(original)
        settings, runtime = self.service.load()
        self.assertEqual(runtime["feed_count"], 447)
        self.assertEqual(runtime["companion_start_time"], 123.5)
        self.assertEqual(settings["extension"], "保留")
        self.assertNotIn("cheer_passion", settings)
        self.assertEqual((self.root / "settings.json.bak").read_bytes(), original)
        after = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(self.service.load(), (settings, runtime))
        self.assertEqual(after, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_existing_runtime_wins_during_interrupted_migration(self):
        self.service.save({"mode": "auto"}, {"feed_count": 99})
        (self.root / "settings.json").write_text('{"feed_count": 4}', encoding="utf-8")
        _, runtime = self.service.load()
        self.assertEqual(runtime["feed_count"], 99)

    def test_save_reload_separation_and_previous_backup(self):
        self.service.save({"mode": "manual", "extension": "初瓏"}, {"feed_count": 7})
        old = (self.root / "runtime.json").read_bytes()
        self.service.save({"mode": "auto"}, {"feed_count": 8})
        settings, runtime = PersistenceService(self.root).load()
        self.assertEqual(settings["mode"], "auto")
        self.assertEqual(runtime["feed_count"], 8)
        self.assertNotIn("feed_count", json.loads((self.root / "settings.json").read_text())["data"])
        self.assertEqual((self.root / "runtime.json.bak").read_bytes(), old)

    def test_corrupt_primary_restores_good_backup_without_overwriting_it(self):
        self.service.save({}, {"feed_count": 7})
        self.service.save({}, {"feed_count": 8})
        backup = (self.root / "runtime.json.bak").read_bytes()
        (self.root / "runtime.json").write_bytes(b"broken primary")
        with self.assertLogs("app.storage.settings", level="WARNING"):
            _, runtime = self.service.load()
        self.assertEqual(runtime["feed_count"], 7)
        self.assertEqual((self.root / "runtime.json").read_bytes(), backup)
        self.assertEqual((self.root / "runtime.json.bak").read_bytes(), backup)
        evidence = list(self.root.glob("runtime.json.*.corrupt"))
        self.assertEqual([p.read_bytes() for p in evidence], [b"broken primary"])
        self.assertTrue(any("Recovered" in event for event in self.service.recovery_events))

    def test_both_corrupt_use_defaults_and_preserve_both_originals(self):
        (self.root / "runtime.json").write_bytes(b"primary bad")
        (self.root / "runtime.json.bak").write_bytes(b"backup bad")
        with self.assertLogs("app.storage.settings", level="WARNING"):
            _, runtime = self.service.load()
        self.assertEqual(runtime["feed_count"], 0)
        self.assertEqual({p.read_bytes() for p in self.root.glob("*.corrupt")},
                         {b"primary bad", b"backup bad"})
        self.assertEqual((self.root / "runtime.json.bak").read_bytes(), b"backup bad")

    def test_invalid_objects_and_counter_types_are_rejected_before_any_write(self):
        for value in (-1, True, "3", 1.5, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.service.save({}, {"feed_count": value})
        with self.assertRaises(ValueError):
            self.service.save([], {})
        with self.assertRaises(ValueError):
            self.service.save({"notify_relay": "yes"}, {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_misplaced_fields_are_rejected(self):
        for settings, runtime in (({"feed_count": 3}, {}), ({}, {"mode": "manual"})):
            with self.assertRaises(ValueError):
                self.service.save(settings, runtime)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_non_object_json_is_corruption(self):
        (self.root / "settings.json").write_bytes(b"[]")
        with self.assertLogs("app.storage.settings", level="WARNING"):
            settings, _ = self.service.load()
        self.assertEqual(settings["mode"], "auto")
        self.assertEqual(next(self.root.glob("*.corrupt")).read_bytes(), b"[]")

    def test_future_schema_is_not_overwritten(self):
        original = b'{"schema_version": 2, "data": {}}'
        (self.root / "settings.json").write_bytes(original)
        with self.assertRaises(UnsupportedSchemaError):
            self.service.load()
        self.assertEqual((self.root / "settings.json").read_bytes(), original)
        self.assertEqual(list(self.root.glob("*.corrupt")), [])

    def test_replace_failure_preserves_primary_and_cleans_temp(self):
        self.service.save({}, {"feed_count": 7})
        old = (self.root / "runtime.json").read_bytes()
        actual_replace = os.replace

        def fail_primary(src, dst):
            self.assertEqual(Path(src).parent, self.root)
            if Path(dst).name == "runtime.json":
                raise PermissionError("injected locked primary")
            return actual_replace(src, dst)

        with patch("app.storage.settings.os.replace", side_effect=fail_primary):
            with self.assertRaisesRegex(PermissionError, "injected"):
                self.service.save({}, {"feed_count": 8})
        self.assertEqual((self.root / "runtime.json").read_bytes(), old)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_save_corrupt_primary_does_not_rotate_it_over_good_backup(self):
        self.service.save({}, {"feed_count": 1})
        self.service.save({}, {"feed_count": 2})
        backup = (self.root / "runtime.json.bak").read_bytes()
        (self.root / "runtime.json").write_bytes(b"bad")
        with self.assertLogs("app.storage.settings", level="WARNING"):
            self.service.save({}, {"feed_count": 3})
        self.assertEqual((self.root / "runtime.json.bak").read_bytes(), backup)
        self.assertEqual(next(self.root.glob("*.corrupt")).read_bytes(), b"bad")

    def test_fsync_failure_leaves_original_and_cleans_temp(self):
        self.service.save({}, {"feed_count": 1})
        old = (self.root / "runtime.json").read_bytes()
        with patch("app.storage.settings.os.fsync", side_effect=OSError("injected fsync failure")):
            with self.assertRaisesRegex(OSError, "fsync failure"):
                self.service.save({}, {"feed_count": 2})
        self.assertEqual((self.root / "runtime.json").read_bytes(), old)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_settings_failure_can_leave_runtime_committed_independently(self):
        self.service.save({"mode": "auto"}, {"feed_count": 1})
        old_settings = (self.root / "settings.json").read_bytes()
        actual_replace = os.replace

        def fail_settings(src, dst):
            if Path(dst).name == "settings.json":
                raise PermissionError("injected settings failure")
            return actual_replace(src, dst)

        with patch("app.storage.settings.os.replace", side_effect=fail_settings):
            with self.assertRaisesRegex(PermissionError, "settings failure"):
                self.service.save({"mode": "manual"}, {"feed_count": 2})
        settings, runtime = self.service.load()
        self.assertEqual(settings["mode"], "auto")
        self.assertEqual(runtime["feed_count"], 2)
        self.assertEqual((self.root / "settings.json").read_bytes(), old_settings)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_omitted_festival_welcome_seen_is_isolated_across_loads(self):
        self.service.save(dict(DEFAULT_SETTINGS), {"cheer_passion": 500})
        _, runtime1 = self.service.load()
        _, runtime2 = self.service.load()
        self.assertEqual(runtime1["festival_welcome_seen"], {})
        self.assertEqual(runtime2["festival_welcome_seen"], {})
        self.assertIsNot(runtime1["festival_welcome_seen"], DEFAULT_RUNTIME["festival_welcome_seen"])
        self.assertIsNot(runtime1["festival_welcome_seen"], runtime2["festival_welcome_seen"])
        runtime1["festival_welcome_seen"]["lantern:2026"] = True
        _, runtime3 = self.service.load()
        self.assertEqual(DEFAULT_RUNTIME["festival_welcome_seen"], {})
        self.assertEqual(runtime2["festival_welcome_seen"], {})
        self.assertEqual(runtime3["festival_welcome_seen"], {})

    def test_missing_runtime_defaults_never_share_mutable_nested_state(self):
        _, runtime1 = self.service.load()
        _, runtime2 = self.service.load()
        self.assertIsNot(runtime1["festival_welcome_seen"], DEFAULT_RUNTIME["festival_welcome_seen"])
        self.assertIsNot(runtime1["festival_welcome_seen"], runtime2["festival_welcome_seen"])
        runtime1["festival_welcome_seen"]["christmas:2026"] = True
        _, runtime3 = self.service.load()
        self.assertEqual(DEFAULT_RUNTIME["festival_welcome_seen"], {})
        self.assertEqual(runtime2["festival_welcome_seen"], {})
        self.assertEqual(runtime3["festival_welcome_seen"], {})


if __name__ == "__main__":
    unittest.main()
