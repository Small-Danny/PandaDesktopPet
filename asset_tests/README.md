# Asset-dependent runtime & integration tests

These tests require runtime artwork (`work/`) or `assets.pak`, intentionally omitted from `--no-assets`.
Once approved runtime assets are restored into `work/` (see `../ASSETS_REQUIRED.md`), run:

`python -m unittest discover -s asset_tests`

- asset_tests/test_9slice_audit.py: work/bubbles/ frame PNGs
- asset_tests/test_action_placement.py: work/characters/ approved sprite registry frames
- asset_tests/test_action_window_alignment.py: PandaPet runtime + work/characters/ frames
- asset_tests/test_all_members_food_animation_matrix.py: PandaPet runtime + work/characters/ & work/foods/
- asset_tests/test_birthday_dialog.py: work/characters/bomi/situational_all1/bomi_walk_wink.png edge fringe check
- asset_tests/test_bubble_rendering.py: work/characters/bomi/idle_01.png & PandaPet bubble rendering
- asset_tests/test_c2_integration.py: PandaPet runtime + work/characters/ & work/quotes.json
- asset_tests/test_c2b_integration.py: PandaPet runtime + work/characters/ & work/quotes.json
- asset_tests/test_c4_integration.py: PandaPet runtime + work/characters/ & work/quotes.json
- asset_tests/test_c5_integration.py: PandaPet runtime + work/standby_backgrounds & work/characters/
- asset_tests/test_celebration_roster.py: RES_ROOT + SpriteLibrary approved celebration frames
- asset_tests/test_cursor_manager.py: work/ui_icons/*.cur/.png & PandaPet cursor integration
- asset_tests/test_daily_actions.py: PandaPet runtime + work/asset_registry.json & sprites
- asset_tests/test_debug_platform_integration.py: PandaPet runtime + work/characters/ frames
- asset_tests/test_disappearing_panda_fix.py: PandaPet runtime + work/characters/ frames
- asset_tests/test_disliked_feed_animation.py: PandaPet runtime + work/characters/ & work/foods/
- asset_tests/test_dome_scenes.py: PandaPet/Standby runtime + work/characters/ & work/standby_backgrounds/ dome assets
- asset_tests/test_enduser_build.py: imports test_pink_context_menu (work/ui_icons & PandaPet menu runtime)
- asset_tests/test_eunji_boxing_mole.py: work/asset_registry.json & approved eunji boxing sprites
- asset_tests/test_feed_food_log.py: PandaPet runtime + work/foods/ & work/characters/
- asset_tests/test_feed_full.py: PandaPet runtime + work/foods/ & work/characters/
- asset_tests/test_first_run_tip.py: PandaPet runtime + work/foods/ & work/characters/
- asset_tests/test_food_expansion.py: work/foods/ PNG files
- asset_tests/test_food_panel.py: work/foods/ icon PNGs for FoodCafePanel
- asset_tests/test_food_panel_dpi.py: PandaPet runtime + work/foods/ icons
- asset_tests/test_food_prop_mapping.py: PandaPet runtime + work/foods/ icons
- asset_tests/test_fortune_room.py: PandaPet/Standby runtime + work/characters/, work/scenes/fortune_room/, & wallpaper
- asset_tests/test_fortune_theater_cache_key.py: work/scenes/fortune_room/ theater frames
- asset_tests/test_high_dpi_ui_scaling.py: work/characters/ sprites for MemberProfileCard DPI scaling checks
- asset_tests/test_holiday_previews_and_standby_modes.py: PandaPet runtime + work/characters/ & work/standby_backgrounds/
- asset_tests/test_i18n_language_switch.py: PandaPet runtime + work/characters/ & work/quotes.json
- asset_tests/test_layered_pet_integration.py: PandaPet ULW runtime + work/characters/ sprites
- asset_tests/test_long_notification_bubble.py: work/bubbles/ frame PNGs
- asset_tests/test_notification_queue.py: PandaPet runtime + work/characters/ frames
- asset_tests/test_pet_lifecycle.py: PandaPet runtime + work/characters/ frames
- asset_tests/test_pink_context_menu.py: work/ui_icons/ & work/standby_backgrounds.json for PinkContextMenu
- asset_tests/test_policy_blacklist_guard.py: work/asset_review_policy.json & approved character PNGs
- asset_tests/test_profile_card.py: work/characters/ sprites for MemberProfileCard
- asset_tests/test_profile_card_bubble.py: PandaPet runtime + work/characters/ sprites
- asset_tests/test_profile_greeting.py: PandaPet runtime + work/characters/ sprites
- asset_tests/test_quotes_and_i18n_v13.py: work/quotes.json companion lines ledger
- asset_tests/test_resource_store.py: work/ runtime assets for PakResourceStore & UI integration tests
- asset_tests/test_satiety_persistence.py: PandaPet runtime + work/foods/ & work/characters/
- asset_tests/test_settings_apply.py: PandaPet runtime + work/characters/ sprites
- asset_tests/test_settings_wiring.py: PandaPet runtime + work/characters/ sprites
- asset_tests/test_special_actions.py: PandaPet runtime + work/characters/ special animations
- asset_tests/test_sprite_equalize.py: work/characters/ approved sprite frames
- asset_tests/test_stage_calibration.py: work/asset_registry.json & approved stage/action sprites
- asset_tests/test_standby_drawn_scene_actions.py: work/asset_registry.json & standby action sprites
- asset_tests/test_standby_memory_release.py: PandaPet/Standby runtime + work/characters/ & work/standby_backgrounds/
- asset_tests/test_standby_pet_restore.py: imports test_action_window_alignment (PandaPet runtime + sprites)
- asset_tests/test_standby_scenes.py: work/characters/ & work/standby_backgrounds/
- asset_tests/test_standby_soft_edges.py: SpriteLibrary + work/standby_backgrounds/ & work/characters/
- asset_tests/test_standby_wallpapers.py: work/standby_backgrounds.json & JPG wallpapers
- asset_tests/test_status_card_and_quotes.py: work/quotes.json & work/characters/ frames
- asset_tests/test_user_batch_1108.py: PandaPet runtime + work/characters/ & work/foods/
- asset_tests/test_verified_quotes.py: work/quotes.json companion lines ledger
- asset_tests/test_wave6_regressions.py: PandaPet runtime, approved sprites, and the previously built assets.pak
