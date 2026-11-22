# Workshop source-art tests

These unchanged tests require original art and audit evidence intentionally not distributed.
They are separate from `python -m unittest discover -s tests`. No missing-input test is auto-passed.
With the matching original inputs supplied in the same relative locations, run:

`python -m unittest discover -s workshop_tests`

- workshop_tests/test_wave2_integration.py: work/asset_review_policy.json, full workshop inventory and approved character art
- workshop_tests/test_asset_review_policy_consistency.py: work/asset_review_policy.json and full workshop character inventory, including blocked/excluded images
- workshop_tests/test_bubble_asset_preparation.py: reference/ original background6/background8 sheets, work/bubbles/source/ original backups, and work/evidence/x6/asset_inventory.json
- workshop_tests/test_quotes_export_workshop.py: work/quotes_verified_58_export.md (workshop quotes markdown export ledger)
