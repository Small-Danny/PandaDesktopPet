"""test_bubble_themes.py — Unit tests for bubble themes and member-specific palettes."""
from __future__ import annotations

import unittest
from app.bubble_themes import (
    BubbleTheme,
    THEMES,
    get_theme,
    get_theme_for_member,
    MEMBER_DEFAULT_THEME,
)


class TestBubbleThemes(unittest.TestCase):
    def test_theme_keys_present(self):
        expected_keys = {
            "classic",
            "chorong_pink",
            "bomi_coral",
            "eunji_comic",
            "namjoo_purple",
            "hayoung_yellow",
            "roco_pink",
            "lilac_mauve",
            "ruby_velvet",
        }
        for k in expected_keys:
            self.assertIn(k, THEMES)
            theme = THEMES[k]
            self.assertEqual(theme.key, k)
            self.assertTrue(theme.name_zh)
            self.assertTrue(theme.bg_fill.startswith("#"))
            self.assertTrue(theme.outline_color.startswith("#"))
            self.assertTrue(theme.header_color.startswith("#"))

    def test_hayoung_theme_is_warm_yellow(self):
        theme = get_theme("hayoung_yellow")
        self.assertEqual(theme.key, "hayoung_yellow")
        self.assertEqual(theme.name_zh, "夏榮 ‧ 溫暖蜂蜜黃")
        # Check that it's warm yellow, NOT pink
        self.assertEqual(theme.outline_color.lower(), "#f5b432")
        self.assertEqual(theme.header_color.lower(), "#cd870f")

    def test_get_theme_unknown_fallback(self):
        theme = get_theme("non_existent_key")
        self.assertEqual(theme.key, "classic")

    def test_get_theme_for_member_auto(self):
        self.assertEqual(get_theme_for_member("hayoung", "auto").key, "hayoung_yellow")
        self.assertEqual(get_theme_for_member("chorong", "auto").key, "chorong_pink")
        self.assertEqual(get_theme_for_member("bomi", "auto").key, "bomi_coral")
        self.assertEqual(get_theme_for_member("eunji", "auto").key, "eunji_comic")
        self.assertEqual(get_theme_for_member("namjoo", "auto").key, "namjoo_purple")

    def test_get_theme_for_member_manual_override(self):
        # When user manually overrides to chorong_pink, hayoung should use chorong_pink
        theme = get_theme_for_member("hayoung", "chorong_pink")
        self.assertEqual(theme.key, "chorong_pink")


if __name__ == "__main__":
    unittest.main()
