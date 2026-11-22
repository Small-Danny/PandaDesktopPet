"""bubble_themes.py — Visual themes and member-specific palettes for KawaiiSpeechBubble."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from app.bubble_art import FrameLayout, frame_layout
from app.paths import resource_dir
from app.resource_store import resource_exists


@dataclass(frozen=True)
class BubbleTheme:
    key: str
    name_zh: str
    bg_fill: str
    outline_color: str
    header_color: str
    text_color: str
    chip_fill: str
    chip_outline: str
    chip_text: str
    badge_color: str
    close_btn_bg: str
    close_btn_cross: str
    inner_card_fill: str = "#ffffff"
    inner_card_outline: str = "#f5dce6"
    nine_slice_file: Optional[str] = None
    cap_insets: tuple[int, int, int, int] = (45, 45, 45, 45)
    # Hand-picked stretch rows (source px) for art where every row crosses an
    # ornament: (cut row, left border row, inner fill row, right border row).
    stretch_rows: Optional[tuple[int, int, int, int]] = None
    right_cut_row: Optional[int] = None

    def get_nine_slice_path(self) -> Optional[Path]:
        if not self.nine_slice_file:
            return None
        base = resource_dir()
        p = base / "work" / "bubbles" / self.nine_slice_file
        return p if resource_exists(p, root=base) else None

    def frame_layout(self) -> Optional[FrameLayout]:
        """Measured layout of the frame art (with ``stretch_rows`` applied), or None."""
        path = self.get_nine_slice_path()
        if path is None:
            return None
        layout = frame_layout(path, root=resource_dir())
        if self.stretch_rows is not None:
            cut, left, fill, right = self.stretch_rows
            layout = replace(layout, band=(cut, cut + 1), border_rows=(left, right), fill_row=fill,
                             right_cut=self.right_cut_row)
        return layout


THEMES: dict[str, BubbleTheme] = {
    "classic": BubbleTheme(
        key="classic",
        name_zh="經典粉紅",
        bg_fill="#fffafd",
        outline_color="#ecadc3",
        header_color="#953b62",
        text_color="#423142",
        chip_fill="#fceaf1",
        chip_outline="#f4d5e1",
        chip_text="#9a4b6c",
        badge_color="#b04d76",
        close_btn_bg="#f9eaf0",
        close_btn_cross="#a9798a",
        inner_card_fill="#ffffff",
        inner_card_outline="#f5dce6",
    ),
    "chorong_pink": BubbleTheme(
        key="chorong_pink",
        name_zh="初瓏 ‧ 櫻粉馬卡龍",
        bg_fill="#fffbfa",
        outline_color="#f988ac",
        header_color="#e14b7d",
        text_color="#3c383a",
        chip_fill="#fdecf2",
        chip_outline="#f9cad9",
        chip_text="#c83e6d",
        badge_color="#d65184",
        close_btn_bg="#fae6ee",
        close_btn_cross="#b8738a",
        inner_card_fill="#ffffff",
        inner_card_outline="#fbe3eb",
        nine_slice_file="bubble_chorong_pink.png",
        stretch_rows=(116, 116, 164, 164),
        right_cut_row=164,
    ),
    "bomi_coral": BubbleTheme(
        key="bomi_coral",
        name_zh="普美 ‧ 陽光珊瑚橘",
        bg_fill="#fff9f5",
        outline_color="#ffa060",
        header_color="#dc6428",
        text_color="#3d3630",
        chip_fill="#ffeede",
        chip_outline="#ffd2b8",
        chip_text="#c0521c",
        badge_color="#d45e22",
        close_btn_bg="#ffe9dc",
        close_btn_cross="#b67a58",
        inner_card_fill="#ffffff",
        inner_card_outline="#ffe2d0",
        nine_slice_file="bubble_bomi_coral.png",
    ),
    "eunji_comic": BubbleTheme(
        key="eunji_comic",
        name_zh="恩地 ‧ 晴空元氣藍",
        bg_fill="#f4faff",
        outline_color="#5cb4e6",
        header_color="#1976d2",
        text_color="#2c343b",
        chip_fill="#e6f3fc",
        chip_outline="#c0e0f8",
        chip_text="#1565c0",
        badge_color="#1e88e5",
        close_btn_bg="#e1f0fa",
        close_btn_cross="#608da9",
        inner_card_fill="#ffffff",
        inner_card_outline="#d8ecfa",
        nine_slice_file="bubble_eunji_comic.png",
        stretch_rows=(165, 165, 144, 122),
        right_cut_row=122,
    ),
    "namjoo_purple": BubbleTheme(
        key="namjoo_purple",
        name_zh="南珠 ‧ 夢幻星願紫",
        bg_fill="#faf5ff",
        outline_color="#b388ff",
        header_color="#8e24aa",
        text_color="#382e40",
        chip_fill="#f3e5f5",
        chip_outline="#dfc0f8",
        chip_text="#7b1fa2",
        badge_color="#9c27b0",
        close_btn_bg="#ede1f6",
        close_btn_cross="#9273a8",
        inner_card_fill="#ffffff",
        inner_card_outline="#eddcf8",
        nine_slice_file="bubble_namjoo_purple.png",
        stretch_rows=(160, 160, 144, 169),
        right_cut_row=169,
    ),
    "hayoung_yellow": BubbleTheme(
        key="hayoung_yellow",
        name_zh="夏榮 ‧ 溫暖蜂蜜黃",
        bg_fill="#fffdf2",
        outline_color="#f5b432",
        header_color="#cd870f",
        text_color="#3e382b",
        chip_fill="#fff7d6",
        chip_outline="#ffe48a",
        chip_text="#b87208",
        badge_color="#c9820f",
        close_btn_bg="#fdf3cf",
        close_btn_cross="#a6874e",
        inner_card_fill="#ffffff",
        inner_card_outline="#fef0b8",
        nine_slice_file="bubble_hayoung_yellow.png",
    ),
    "roco_pink": BubbleTheme(
        key="roco_pink",
        name_zh="典雅洛可可公主風",
        bg_fill="#fffbfd",
        outline_color="#eeb1b8",
        header_color="#9c5b6a",
        text_color="#3d3436",
        chip_fill="#fdeef0",
        chip_outline="#f8d4d8",
        chip_text="#944858",
        badge_color="#aa5366",
        close_btn_bg="#fbe7eb",
        close_btn_cross="#a56a76",
        inner_card_fill="#ffffff",
        inner_card_outline="#fce3e7",
        nine_slice_file="bubble_roco_pink.png",
    ),
    "lilac_mauve": BubbleTheme(
        key="lilac_mauve",
        name_zh="丁香紫霧優雅風",
        bg_fill="#fcfaff",
        outline_color="#b8a2c8",
        header_color="#6d4c82",
        text_color="#362f3d",
        chip_fill="#f2ebf8",
        chip_outline="#d8c7e6",
        chip_text="#5e3c74",
        badge_color="#7e5399",
        close_btn_bg="#eee4f6",
        close_btn_cross="#8a6f9e",
        inner_card_fill="#ffffff",
        inner_card_outline="#eedef8",
        nine_slice_file="bubble_lilac_mauve.png",
    ),
    "ruby_velvet": BubbleTheme(
        key="ruby_velvet",
        name_zh="草莓馬卡龍甜點風",
        bg_fill="#fffafc",
        outline_color="#e87a98",
        header_color="#c93b66",
        text_color="#3d2c32",
        chip_fill="#fdebf0",
        chip_outline="#f9c8d6",
        chip_text="#b8325a",
        badge_color="#d4426e",
        close_btn_bg="#fce4ec",
        close_btn_cross="#b05874",
        inner_card_fill="#ffffff",
        inner_card_outline="#fadce6",
        nine_slice_file="bubble_ruby_velvet.png",
    ),
}

MEMBER_DEFAULT_THEME: dict[str, str] = {
    "chorong": "chorong_pink",
    "bomi": "bomi_coral",
    "eunji": "eunji_comic",
    "namjoo": "namjoo_purple",
    "hayoung": "hayoung_yellow",
}


def get_theme(key: str) -> BubbleTheme:
    """Retrieve theme by key; unknown key defaults to classic."""
    return THEMES.get(key, THEMES["classic"])


def get_theme_for_member(member_key: str, setting: str = "auto") -> BubbleTheme:
    """If user setting is 'auto' (default), resolve theme based on active member;
    otherwise return user's explicit theme choice.
    """
    if setting and setting != "auto" and setting in THEMES:
        return THEMES[setting]
    theme_key = MEMBER_DEFAULT_THEME.get(member_key.lower(), "chorong_pink")
    return THEMES.get(theme_key, THEMES["chorong_pink"])
