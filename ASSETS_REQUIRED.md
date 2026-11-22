# Required Runtime Assets (Omitted from Code-Only Export)

This repository was exported with `--no-assets`: runtime images, cursors, `.pak` bundles,
and `work/` assets are excluded. Only the three explicitly allowlisted documentation JPGs may be included;
these screenshots remain subject to ASSETS-LICENSE.md. No other images are included.

To run the desktop pet or `asset_tests/` locally:
1. Supply the matching approved `work/` asset tree (never commit `work/` into this code-only repo):
   - `work/asset_registry.json` & `work/characters/**`
   - `work/foods/**`, `work/bubbles/**`, `work/ui_icons/**`
   - `work/scenes/**`, `work/standby_backgrounds.json`, `work/standby_backgrounds/**`
   - `work/quotes.json`, `work/apink成員暖心語錄.txt`
2. Optional: pack validated assets into a single indexed container via:
   `python tools/pack_assets.py --output build/assets.pak`
3. Run pure code / synthetic-fixture tests cleanly without images:
   `python -m unittest discover -s tests`
