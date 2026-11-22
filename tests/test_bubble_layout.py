"""Pure stdlib layout checks; no Tk display or external assets required."""
from __future__ import annotations

import unittest

from app.bubble_layout import is_emoji, iter_clusters, layout_lines


class BubbleLayoutTests(unittest.TestCase):
    def test_combining_thai_and_decomposed_hangul(self):
        self.assertEqual(list(iter_clusters("a\u0301ก\u0e49한한")),
                         ["a\u0301", "ก\u0e49", "한", "한"])

    def test_emoji_sequences_and_flags_stay_intact(self):
        clusters = ["👩🏽‍💻", "👨‍👩‍👧‍👦", "🇹🇼", "🇰🇷", "1️⃣", "✌️", "👍🏿"]
        self.assertEqual(list(iter_clusters("".join(clusters))), clusters)
        self.assertTrue(all(is_emoji(cluster) for cluster in clusters))
        self.assertEqual(list(iter_clusters("🇹🇼🇰")), ["🇹🇼", "🇰"])

    def test_text_presentation_and_plain_text(self):
        self.assertFalse(is_emoji("♥︎"))
        self.assertTrue(is_emoji("♥️"))
        self.assertFalse(is_emoji("初"))
        self.assertFalse(is_emoji("A"))
        self.assertFalse(is_emoji(""))

    def test_blank_lines_crlf_and_trailing_newline(self):
        lines = layout_lines("A\r\n\r\nB\rC\n", 20, len, 2)
        self.assertEqual(lines, (("A",), (), ("B",), ("C",), ()))
        self.assertEqual(layout_lines("", 20, len, 2), ((),))

    def test_english_prefers_whitespace(self):
        lines = layout_lines("hello world again", 8, len, 2)
        self.assertEqual(["".join(line) for line in lines], ["hello ", "world ", "again"])

    def test_long_url_breaks_without_losing_content(self):
        text = "https://example.test/" + "abcdefghij" * 20
        lines = layout_lines(text, 13, len, 2)
        self.assertEqual("".join("".join(line) for line in lines), text)
        self.assertTrue(all(len("".join(line)) <= 13 for line in lines))

    def test_multilingual_text_and_emoji_meet_width(self):
        text = "初瓏熊貓 한글 ภาษาไทย 👩🏽‍💻 🇹🇼 1️⃣"
        measure = lambda run: len(list(iter_clusters(run))) * 2
        lines = layout_lines(text, 9, measure, 3)
        self.assertEqual("".join("".join(line) for line in lines), text)
        for line in lines:
            self.assertLessEqual(sum(3 if is_emoji(c) else 2 for c in line), 9)

    def test_contiguous_run_measurement_accounts_for_kerning(self):
        measure = lambda run: 9 if run == "AV" else len(run) * 6
        self.assertEqual(layout_lines("AV", 10, measure, 5), (("A", "V"),))
        self.assertEqual(layout_lines("AV♥️AV", 23, measure, 5),
                         (("A", "V", "♥️", "A", "V"),))

    def test_oversized_nonemoji_is_an_explicit_single_cluster(self):
        self.assertEqual(layout_lines("初a", 5, lambda s: len(s) * 9, 3),
                         (("初",), ("a",)))

    def test_invalid_widths_and_measurements_raise(self):
        for maximum in (0, -1, float("nan"), float("inf")):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                layout_lines("a", maximum, len, 2)
        for emoji_width in (-1, float("inf"), float("nan")):
            with self.subTest(emoji_width=emoji_width), self.assertRaises(ValueError):
                layout_lines("a", 5, len, emoji_width)
        with self.assertRaises(ValueError):
            layout_lines("👍", 5, len, 6)
        for measured in (-1, float("nan"), float("inf")):
            with self.subTest(measured=measured), self.assertRaises(ValueError):
                layout_lines("a", 5, lambda _: measured, 2)


if __name__ == "__main__":
    unittest.main()
