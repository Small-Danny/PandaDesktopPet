"""Copy the publishable part of this workshop into a clean folder, ready for a fresh ``git init``.

    python tools/export_public_repo.py ../PandaDesktopPet-public

Allowlist, not blocklist: code, tests, docs and exactly the assets the running pet reads
(tools/runtime_manifest.py). User data, references, staging, evidence and one-off scripts stay behind.
The target must be empty or absent; nothing here touches git or the network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.runtime_manifest import runtime_files  # noqa: E402

SOURCE_DIRS = ("app", "tests", "scripts", "installer")     # screenshots enter via the explicit allowlist
CODE_ONLY_DIRS = ("app", "tests", "scripts", "installer")
SOURCE_SUFFIXES = {".py", ".md", ".png", ".json", ".txt", ".iss", ".isl"}
CODE_ONLY_SUFFIXES = {".py", ".md", ".json", ".txt", ".iss", ".isl"}
BINARY_ASSET_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".cur", ".ico", ".pak"})
DOC_SCREENSHOT_ALLOWLIST = frozenset({
    "docs/screenshots/desktop_interaction.jpg",
    "docs/screenshots/fortune_room.jpg",
    "docs/screenshots/standby_stage.jpg",
})
ROOT_FILES = (
    "README.md", "README_PORTABLE.txt", "LICENSE", "ASSETS-LICENSE.md", ".gitignore", ".gitattributes",
    "requirements.txt", "requirements-build.txt", "PandaDesktopPet.spec",
    "build_exe.bat", "debug_run.bat", "LaunchPandaPet.bat", "啟動熊貓桌寵.vbs",
)
# Pipeline tools the tests import or that a contributor needs to add art; no machine-specific paths.
TOOLS = (
    "runtime_manifest.py", "export_public_repo.py", "asset_catalog.py", "clean_edge_fringe.py",
    "prepare_bubble_art.py", "stage_food_icons.py", "stage_googleflow_assets.py",
    "extract_rongdoong.py", "build_provenance.py", "pack_assets.py",
)
# This test module deliberately checks privately retained original art and audit
# snapshots. Keep it intact, outside default public tests discovery, and report
# the required workshop inputs rather than masking its failures with skip/pass.
WORKSHOP_TESTS = {
    "tests/test_wave2_integration.py": (
        "work/asset_review_policy.json, full workshop inventory and approved character art"
    ),
    "tests/test_asset_review_policy_consistency.py": (
        "work/asset_review_policy.json and full workshop character inventory, including blocked/excluded images"
    ),
    "tests/test_bubble_asset_preparation.py": (
        "reference/ original background6/background8 sheets, work/bubbles/source/ original backups, "
        "and work/evidence/x6/asset_inventory.json"
    ),
    "tests/test_quotes_export_workshop.py": "work/quotes_verified_58_export.md (workshop quotes markdown export ledger)",
}
# Integration & media tests that read approved work/ assets or run full PandaPet GUI sessions.
# In --no-assets code-only exports, keep them intact under asset_tests/ rather than masking failures.
ASSET_REQUIRED_TESTS = {
    "tests/test_wave6_regressions.py": "PandaPet runtime, approved sprites, and the previously built assets.pak",
    "tests/test_9slice_audit.py": "work/bubbles/ frame PNGs",
    "tests/test_action_placement.py": "work/characters/ approved sprite registry frames",
    "tests/test_action_window_alignment.py": "PandaPet runtime + work/characters/ frames",
    "tests/test_all_members_food_animation_matrix.py": "PandaPet runtime + work/characters/ & work/foods/",
    "tests/test_birthday_dialog.py": "work/characters/bomi/situational_all1/bomi_walk_wink.png edge fringe check",
    "tests/test_bubble_rendering.py": "work/characters/bomi/idle_01.png & PandaPet bubble rendering",
    "tests/test_c2_integration.py": "PandaPet runtime + work/characters/ & work/quotes.json",
    "tests/test_c2b_integration.py": "PandaPet runtime + work/characters/ & work/quotes.json",
    "tests/test_c4_integration.py": "PandaPet runtime + work/characters/ & work/quotes.json",
    "tests/test_c5_integration.py": "PandaPet runtime + work/standby_backgrounds & work/characters/",
    "tests/test_celebration_roster.py": "RES_ROOT + SpriteLibrary approved celebration frames",
    "tests/test_cursor_manager.py": "work/ui_icons/*.cur/.png & PandaPet cursor integration",
    "tests/test_daily_actions.py": "PandaPet runtime + work/asset_registry.json & sprites",
    "tests/test_debug_platform_integration.py": "PandaPet runtime + work/characters/ frames",
    "tests/test_disappearing_panda_fix.py": "PandaPet runtime + work/characters/ frames",
    "tests/test_dome_scenes.py": "PandaPet/Standby runtime + work/characters/ & work/standby_backgrounds/ dome assets",
    "tests/test_disliked_feed_animation.py": "PandaPet runtime + work/characters/ & work/foods/",
    "tests/test_enduser_build.py": "imports test_pink_context_menu (work/ui_icons & PandaPet menu runtime)",
    "tests/test_eunji_boxing_mole.py": "work/asset_registry.json & approved eunji boxing sprites",
    "tests/test_feed_food_log.py": "PandaPet runtime + work/foods/ & work/characters/",
    "tests/test_feed_full.py": "PandaPet runtime + work/foods/ & work/characters/",
    "tests/test_first_run_tip.py": "PandaPet runtime + work/foods/ & work/characters/",
    "tests/test_food_expansion.py": "work/foods/ PNG files",
    "tests/test_food_panel.py": "work/foods/ icon PNGs for FoodCafePanel",
    "tests/test_food_panel_dpi.py": "PandaPet runtime + work/foods/ icons",
    "tests/test_food_prop_mapping.py": "PandaPet runtime + work/foods/ icons",
    "tests/test_fortune_room.py": "PandaPet/Standby runtime + work/characters/, work/scenes/fortune_room/, & wallpaper",
    "tests/test_fortune_theater_cache_key.py": "work/scenes/fortune_room/ theater frames",
    "tests/test_high_dpi_ui_scaling.py": "work/characters/ sprites for MemberProfileCard DPI scaling checks",
    "tests/test_i18n_language_switch.py": "PandaPet runtime + work/characters/ & work/quotes.json",
    "tests/test_layered_pet_integration.py": "PandaPet ULW runtime + work/characters/ sprites",
    "tests/test_long_notification_bubble.py": "work/bubbles/ frame PNGs",
    "tests/test_notification_queue.py": "PandaPet runtime + work/characters/ frames",
    "tests/test_pet_lifecycle.py": "PandaPet runtime + work/characters/ frames",
    "tests/test_pink_context_menu.py": "work/ui_icons/ & work/standby_backgrounds.json for PinkContextMenu",
    "tests/test_policy_blacklist_guard.py": "work/asset_review_policy.json & approved character PNGs",
    "tests/test_profile_card.py": "work/characters/ sprites for MemberProfileCard",
    "tests/test_profile_card_bubble.py": "PandaPet runtime + work/characters/ sprites",
    "tests/test_profile_greeting.py": "PandaPet runtime + work/characters/ sprites",
    "tests/test_quotes_and_i18n_v13.py": "work/quotes.json companion lines ledger",
    "tests/test_resource_store.py": "work/ runtime assets for PakResourceStore & UI integration tests",
    "tests/test_satiety_persistence.py": "PandaPet runtime + work/foods/ & work/characters/",
    "tests/test_settings_apply.py": "PandaPet runtime + work/characters/ sprites",
    "tests/test_settings_wiring.py": "PandaPet runtime + work/characters/ sprites",
    "tests/test_special_actions.py": "PandaPet runtime + work/characters/ special animations",
    "tests/test_sprite_equalize.py": "work/characters/ approved sprite frames",
    "tests/test_stage_calibration.py": "work/asset_registry.json & approved stage/action sprites",
    "tests/test_holiday_previews_and_standby_modes.py": "PandaPet runtime + work/characters/ & work/standby_backgrounds/",
    "tests/test_standby_drawn_scene_actions.py": "work/asset_registry.json & standby action sprites",
    "tests/test_standby_memory_release.py": "PandaPet/Standby runtime + work/characters/ & work/standby_backgrounds/",
    "tests/test_standby_pet_restore.py": "imports test_action_window_alignment (PandaPet runtime + sprites)",
    "tests/test_standby_scenes.py": "work/characters/ & work/standby_backgrounds/",
    "tests/test_standby_soft_edges.py": "SpriteLibrary + work/standby_backgrounds/ & work/characters/",
    "tests/test_standby_wallpapers.py": "work/standby_backgrounds.json & JPG wallpapers",
    "tests/test_status_card_and_quotes.py": "work/quotes.json & work/characters/ frames",
    "tests/test_user_batch_1108.py": "PandaPet runtime + work/characters/ & work/foods/",
    "tests/test_verified_quotes.py": "work/quotes.json companion lines ledger",
}
# Never publish, wherever they turn up.
FORBIDDEN_NAMES = {"settings.json", "runtime.json"}
FORBIDDEN_TEXT = ("\\Users\\", "/Users/", "AionUi")


def public_files(root: Path = ROOT, *, include_assets: bool = True) -> list[str]:
    """Repo-relative POSIX paths of everything that goes into export, sorted."""
    out: set[str] = set(runtime_files(root)) if include_assets else set()
    dirs = SOURCE_DIRS if include_assets else CODE_ONLY_DIRS
    suffixes = SOURCE_SUFFIXES if include_assets else CODE_ONLY_SUFFIXES
    for name in dirs:
        base_dir = root / name
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in suffixes:
                rel = path.relative_to(root).as_posix()
                if not include_assets and Path(rel).suffix.lower() in BINARY_ASSET_SUFFIXES:
                    continue
                out.add(rel)
    out.update(name for name in ROOT_FILES if (root / name).is_file())
    out.update(name for name in DOC_SCREENSHOT_ALLOWLIST if (root / name).is_file())
    for name in TOOLS:
        tool_path = root / "tools" / name
        if not tool_path.is_file():
            if include_assets or name != "pack_assets.py":
                raise FileNotFoundError(f"public pipeline dependency missing: tools/{name}")
            continue
        out.add(f"tools/{name}")
    return sorted(out)


def audit(root: Path, files: list[str], *, include_assets: bool = True) -> list[str]:
    """Problems that must be fixed before exporting: user data files, leaked assets, or machine paths."""
    problems = []
    for rel in files:
        path = root / rel
        if not path.resolve().is_relative_to(root.resolve()):
            problems.append(f"source escapes root: {rel}")
            continue
        if path.name.casefold() in FORBIDDEN_NAMES:
            problems.append(f"user data file: {rel}")
        if not include_assets:
            if rel.startswith(("work/", "reference/", "staging/")) or (path.suffix.lower() in BINARY_ASSET_SUFFIXES and rel not in DOC_SCREENSHOT_ALLOWLIST):
                problems.append(f"asset leaked into code-only export: {rel}")
        if path.suffix.lower() in {".py", ".md", ".bat", ".vbs", ".spec", ".txt", ".iss", ".isl"} and rel != "tools/export_public_repo.py":
            text = path.read_text(encoding="utf-8", errors="replace")
            problems += [f"machine-specific text {needle!r}: {rel}" for needle in FORBIDDEN_TEXT if needle in text]
    return problems


def _clear_target_for_overwrite(target: Path, root: Path) -> None:
    resolved_target = target.resolve()
    resolved_root = root.resolve()
    if resolved_target == resolved_root or resolved_root.is_relative_to(resolved_target):
        raise SystemExit(f"refusing to overwrite source root or parent directory: {resolved_target}")
    if len(resolved_target.parts) <= 2:
        raise SystemExit(f"refusing to overwrite shallow/drive path: {resolved_target}")
    for entry in resolved_target.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def export(
    target: Path,
    root: Path = ROOT,
    *,
    include_assets: bool = True,
    overwrite: bool = False,
) -> list[str]:
    if target.exists() and any(target.iterdir()):
        if not overwrite:
            raise SystemExit(f"target is not empty: {target}")
        _clear_target_for_overwrite(target, root)
    target.mkdir(parents=True, exist_ok=True)
    files = public_files(root, include_assets=include_assets)
    problems = audit(root, files, include_assets=include_assets)
    if problems:
        raise SystemExit("refusing to export:\n  " + "\n  ".join(problems))
    hashes = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in files}
    records = []
    asset_tests = []
    for rel in files:
        if rel in WORKSHOP_TESTS:
            destination = "workshop_tests/" + Path(rel).name
        elif not include_assets and rel in ASSET_REQUIRED_TESTS:
            destination = "asset_tests/" + Path(rel).name
            asset_tests.append({"source_path": rel, "exported_path": destination, "required_assets": ASSET_REQUIRED_TESTS[rel]})
        else:
            destination = rel
        dest = target / destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != hashes[rel]:
            raise RuntimeError(f"source changed while exporting: {rel}; use a new empty target")
        records.append({"path": destination, "source_path": rel, "sha256": hashes[rel]})
    # A late source change cannot turn this export into a mixed, unbound snapshot.
    for rel, expected in hashes.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"source changed while exporting: {rel}; use a new empty target")
    workshop = [dict(source_path=rel, exported_path="workshop_tests/" + Path(rel).name,
                     required_private_inputs=reason) for rel, reason in WORKSHOP_TESTS.items() if rel in files]
    output_paths = [record["path"] for record in records]
    if workshop:
        readme = target / "workshop_tests/README.md"
        readme.write_text(
            "# Workshop source-art tests\n\n"
            "These unchanged tests require original art and audit evidence intentionally not distributed.\n"
            "They are separate from `python -m unittest discover -s tests`. No missing-input test is auto-passed.\n"
            "With the matching original inputs supplied in the same relative locations, run:\n\n"
            "`python -m unittest discover -s workshop_tests`\n\n"
            + "\n".join(f"- {row['exported_path']}: {row['required_private_inputs']}" for row in workshop) + "\n",
            encoding="utf-8")
        output_paths.append("workshop_tests/README.md")
    if asset_tests:
        asset_readme = target / "asset_tests/README.md"
        asset_readme.parent.mkdir(parents=True, exist_ok=True)
        asset_readme.write_text(
            "# Asset-dependent runtime & integration tests\n\n"
            "These tests require runtime artwork (`work/`) or `assets.pak`, intentionally omitted from `--no-assets`.\n"
            "Once approved runtime assets are restored into `work/` (see `../ASSETS_REQUIRED.md`), run:\n\n"
            "`python -m unittest discover -s asset_tests`\n\n"
            + "\n".join(f"- {row['exported_path']}: {row['required_assets']}" for row in asset_tests) + "\n",
            encoding="utf-8")
        output_paths.append("asset_tests/README.md")
    if not include_assets:
        assets_req = target / "ASSETS_REQUIRED.md"
        assets_req.write_text(
            "# Required Runtime Assets (Omitted from Code-Only Export)\n\n"
            "This repository was exported with `--no-assets`: runtime images, cursors, `.pak` bundles,\n"
            "and `work/` assets are excluded. Only the three explicitly allowlisted documentation JPGs may be included;\n"
            "these screenshots remain subject to ASSETS-LICENSE.md. No other images are included.\n\n"
            "To run the desktop pet or `asset_tests/` locally:\n"
            "1. Supply the matching approved `work/` asset tree (never commit `work/` into this code-only repo):\n"
            "   - `work/asset_registry.json` & `work/characters/**`\n"
            "   - `work/foods/**`, `work/bubbles/**`, `work/ui_icons/**`\n"
            "   - `work/scenes/**`, `work/standby_backgrounds.json`, `work/standby_backgrounds/**`\n"
            "   - `work/quotes.json`, `work/apink成員暖心語錄.txt`\n"
            "2. Optional: pack validated assets into a single indexed container via:\n"
            "   `python tools/pack_assets.py --output build/assets.pak`\n"
            "3. Run pure code / synthetic-fixture tests cleanly without images:\n"
            "   `python -m unittest discover -s tests`\n",
            encoding="utf-8")
        output_paths.append("ASSETS_REQUIRED.md")
    report = {
        "schema_version": 1,
        "include_assets": include_assets,
        "documentation_screenshots": sorted(DOC_SCREENSHOT_ALLOWLIST.intersection(files)),
        "audit": problems,
        "files": records,
        "workshop_tests": workshop,
        "asset_tests": asset_tests,
        "default_test_command": "python -m unittest discover -s tests",
        "input_bytes_verified": True,
    }
    (target / "PUBLIC_EXPORT_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    output_paths.append("PUBLIC_EXPORT_REPORT.json")
    return sorted(output_paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path, nargs="?", help="empty folder to export into")
    parser.add_argument("--list", action="store_true", help="only print what would be exported")
    parser.add_argument("--no-assets", dest="include_assets", action="store_false",
                        help="export code and docs with three allowlisted screenshots; exclude runtime assets")
    parser.add_argument("--overwrite", action="store_true",
                        help="clear existing non-.git contents in target directory before exporting")
    args = parser.parse_args()
    if args.list or not args.target:
        files = public_files(include_assets=args.include_assets)
        print("\n".join(files))
        print(f"{len(files)} files, {sum((ROOT / f).stat().st_size for f in files) / 1e6:.1f} MB", file=sys.stderr)
        for problem in audit(ROOT, files, include_assets=args.include_assets):
            print("PROBLEM", problem, file=sys.stderr)
        return
    files = export(args.target.resolve(), include_assets=args.include_assets, overwrite=args.overwrite)
    print(f"exported {len(files)} files to {args.target.resolve()}")


if __name__ == "__main__":
    main()
