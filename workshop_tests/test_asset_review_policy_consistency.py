"""Approval declarations cannot contradict the checked registry snapshot."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AssetReviewPolicyConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((ROOT / 'work/asset_review_policy.json').read_text(encoding='utf-8'))
        cls.registry = json.loads((ROOT / 'work/asset_registry.json').read_text(encoding='utf-8'))

    def test_every_approval_names_current_approved_bytes(self):
        for path, expected in self.policy['approved'].items():
            with self.subTest(path=path):
                entry = self.registry['files'].get(path.removesuffix('.png'))
                self.assertIsNotNone(entry)
                self.assertEqual(entry['review_status'], 'approved')
                self.assertTrue(entry['runtime_ok'])
                self.assertEqual(entry['sha256'], expected)
                self.assertEqual(hashlib.sha256((ROOT / 'work/characters' / path).read_bytes()).hexdigest(), expected)

    def test_blocked_and_preview_images_are_never_approved(self):
        self.assertFalse(set(self.policy['approved']) & set(self.policy.get('blocked', {})))
        self.assertFalse(any(Path(p).name == 'preview_sheet.png' for p in self.policy['approved']))

    def test_denied_files_cannot_become_pending_on_policy_rebuild(self):
        from tools.asset_catalog import inspect_asset
        root = ROOT / 'work/characters'
        for record in self.registry['files'].values():
            if record['review_status'] not in {'blocked', 'excluded'}:
                continue
            with self.subTest(path=record['path']):
                actual = inspect_asset(root / record['path'], root, self.policy)
                self.assertEqual(actual['review_status'], record['review_status'])
                self.assertFalse(actual['runtime_ok'])


if __name__ == '__main__':
    unittest.main()
