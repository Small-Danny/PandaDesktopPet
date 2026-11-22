"""Headless Unicode-aware wrapping shared by bubble rendering and measurement.

This implements a practical subset of Unicode grapheme boundaries, not full UAX
#29 or language-specific word segmentation. Render contiguous nonemoji clusters
as one text run, and emoji clusters as fixed-width cells matching emoji_width.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
import math
import unicodedata


def _regional(char: str) -> bool:
    return 0x1F1E6 <= ord(char) <= 0x1F1FF


def _extend(char: str) -> bool:
    code = ord(char)
    return (unicodedata.category(char).startswith("M")
            or 0xFE00 <= code <= 0xFE0F or 0xE0100 <= code <= 0xE01EF
            or 0x1F3FB <= code <= 0x1F3FF or 0xE0020 <= code <= 0xE007F)


def _hangul(char: str) -> str:
    code = ord(char)
    if 0x1100 <= code <= 0x115F or 0xA960 <= code <= 0xA97C:
        return "L"
    if 0x1160 <= code <= 0x11A7 or 0xD7B0 <= code <= 0xD7C6:
        return "V"
    if 0x11A8 <= code <= 0x11FF or 0xD7CB <= code <= 0xD7FB:
        return "T"
    if 0xAC00 <= code <= 0xD7A3:
        return "LV" if (code - 0xAC00) % 28 == 0 else "LVT"
    return ""


def iter_clusters(text: str) -> Iterator[str]:
    """Keep combining marks, modifiers, keycaps, ZWJ chains and flag pairs intact."""
    cluster = ""
    for char in text:
        if not cluster:
            cluster = char
            continue
        previous = cluster[-1]
        left, right = _hangul(previous), _hangul(char)
        hangul_join = ((left == "L" and right in ("L", "V", "LV", "LVT"))
                       or (left in ("LV", "V") and right in ("V", "T"))
                       or (left in ("LVT", "T") and right == "T"))
        if previous == "\r" and char == "\n":
            cluster += char
        elif previous in "\r\n" or char in "\r\n":
            yield cluster
            cluster = char
        elif (_extend(char) or char == "\u200d" or previous == "\u200d"
              or hangul_join
              or (_regional(char) and len(cluster) == 1 and _regional(cluster))):
            cluster += char
        else:
            yield cluster
            cluster = char
    if cluster:
        yield cluster


def is_emoji(cluster: str) -> bool:
    """Identify emoji cells, honoring explicit VS15 text presentation."""
    if not cluster or "\ufe0e" in cluster and "\ufe0f" not in cluster:
        return False
    if cluster.endswith("\u20e3") and cluster[0] in "0123456789#*":
        return True
    for char in cluster:
        code = ord(char)
        if (0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF
                or 0x2194 <= code <= 0x2199 or 0x23E9 <= code <= 0x23F3
                or 0x23F8 <= code <= 0x23FA or 0x25FB <= code <= 0x25FE
                or 0x2B05 <= code <= 0x2B07
                or code in (0xA9, 0xAE, 0x203C, 0x2049, 0x2122, 0x2139,
                            0x21A9, 0x21AA, 0x231A, 0x231B, 0x2328, 0x23CF,
                            0x24C2, 0x25AA, 0x25AB, 0x25B6, 0x25C0,
                            0x2934, 0x2935, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
                            0x3030, 0x303D, 0x3297, 0x3299)):
            return True
    return False


def layout_lines(
    text: str,
    max_width: float,
    measure: Callable[[str], float],
    emoji_width: float,
) -> tuple[tuple[str, ...], ...]:
    """Wrap at whitespace when possible, otherwise at intact cluster boundaries.

    Explicit LF/CRLF/CR and blank paragraphs survive. Spaces are retained, including
    spaces at soft line ends. Nonemoji text is measured in contiguous runs so font
    kerning/shaping matches rendering. One oversized nonemoji cluster is returned
    alone; callers may shrink its font. An oversized emoji raises ValueError so a
    caller cannot silently render an icon outside its available width.
    """
    if not math.isfinite(max_width) or max_width <= 0:
        raise ValueError("max_width must be finite and positive")
    if not math.isfinite(emoji_width) or emoji_width < 0:
        raise ValueError("emoji_width must be finite and nonnegative")

    def width(clusters: list[str]) -> float:
        total = 0.0
        run: list[str] = []
        for cluster in clusters:
            if is_emoji(cluster):
                if emoji_width > max_width:
                    raise ValueError("emoji_width exceeds max_width; reduce icon size")
                if run:
                    value = measure("".join(run))
                    if not math.isfinite(value) or value < 0:
                        raise ValueError("measure must return finite nonnegative widths")
                    total += value
                    run.clear()
                total += emoji_width
            else:
                run.append(cluster)
        if run:
            value = measure("".join(run))
            if not math.isfinite(value) or value < 0:
                raise ValueError("measure must return finite nonnegative widths")
            total += value
        return total

    lines: list[tuple[str, ...]] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        pending: list[str] = []
        for cluster in iter_clusters(paragraph):
            pending.append(cluster)
            while width(pending) > max_width:
                if len(pending) == 1:
                    lines.append(tuple(pending))
                    pending.clear()
                    break
                # Last whitespace among the fitting prefix is the preferred break.
                split = next((i + 1 for i in range(len(pending) - 2, -1, -1)
                              if pending[i].isspace()), len(pending) - 1)
                lines.append(tuple(pending[:split]))
                pending = pending[split:]
        if pending or not paragraph:
            lines.append(tuple(pending))
    return tuple(lines)
