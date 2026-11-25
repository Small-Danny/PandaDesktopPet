"""app/settings_panel.py — Unified "Default + Custom" Appearance & Caring Reminders UI Panel.

Replaces legacy Windows native cascading submenus for Speech Bubble Themes, Pet Size,
Text Size, Hourly Chime, and Sedentary Reminders with a kawaii glassmorphic 2-tab panel:
- Tab 1 (`appearance`): Speech Bubble Theme ("✨ Default: Auto by Member" + 9 Custom Theme Cards
  with matching names including "🪻 丁香紫霧優雅風" & "🍓 草莓馬卡龍甜點風"), Pet Size, and Text Size.
- Tab 2 (`reminders`): Unified Caring Reminders ("🔔 Default: 60m + Hourly Chime + Member Line" +
  Custom Interval Presets 0/30/45/60/90/120m, Custom Minute Input 5..240m, Hourly Chime Toggle,
  Custom Reminder Message up to 60 chars, and Instant Preview button).
- Pure UI module: never imports `app.main` or writes JSON files directly; delegates all mutations
  via `on_change(key, value)`, `on_reset(section)`, and `on_preview(kind)`.
"""
from __future__ import annotations

from collections.abc import Mapping
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Any, Callable, Optional
from PIL import Image, ImageTk

from app.bubble import _draw_round_rect
from app.bubble_themes import THEMES, get_theme
from app.i18n import get_member_display_name, get_theme_display_name
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, scale_canvas, ui_scale
from app.status_card import MEMBER_THEMES
from app.storage.settings import VALID_NOTIFY_BUBBLE_STYLES

BG_TRANSPARENT = "#ff00fe"
ROOT = Path(__file__).resolve().parent.parent

PANEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "appearance": {
        "bubble_theme": "auto",
        "pet_size": "medium",
        "text_size": "medium",
        "standby_clock_position": "top_right",
    },
    "reminders": {
        "hourly_chime": True,
        "hourly_start": 9,
        "hourly_end": 22,
        "sedentary_interval_min": 60,
        "sedentary_message": "",
        "notify_bubble_style": "banner",
    },
}

_PREFERRED_THEME_ORDER = (
    "chorong_pink",
    "bomi_coral",
    "eunji_comic",
    "namjoo_purple",
    "hayoung_yellow",
    "roco_pink",
    "lilac_mauve",
    "ruby_velvet",
    "classic",
)
THEME_KEYS_ORDER: tuple[str, ...] = tuple(
    [k for k in _PREFERRED_THEME_ORDER if k in THEMES]
    + [k for k in THEMES if k not in _PREFERRED_THEME_ORDER]
)

INTERVAL_PRESETS: tuple[int, ...] = (0, 30, 45, 60, 90, 120)

PANEL_I18N: dict[str, dict[str, str]] = {
    "title": {
        "zh_TW": "🎀 粉熊外觀與貼心提醒設定",
        "ko": "🎀 판다 외관 및 알림 설정",
        "en": "🎀 Panda Appearance & Reminders",
    },
    "tab_appearance": {
        "zh_TW": "🎨 對話框與外觀",
        "ko": "🎨 말풍선·외관",
        "en": "🎨 Appearance",
    },
    "tab_reminders": {
        "zh_TW": "⏰ 貼心提醒通知",
        "ko": "⏰ 다정한 알림",
        "en": "⏰ Reminders",
    },
    "mode_default_active": {
        "zh_TW": "✨ 目前模式：預設設定",
        "ko": "✨ 현재 모드: 기본 설정",
        "en": "✨ Mode: Default Settings",
    },
    "mode_custom_active": {
        "zh_TW": "🛠️ 目前模式：自訂設定",
        "ko": "🛠️ 현재 모드: 사용자 지정",
        "en": "🛠️ Mode: Custom Settings",
    },
    "btn_restore_default": {
        "zh_TW": "↺ 恢復預設設定",
        "ko": "↺ 기본값 복원",
        "en": "↺ Restore Defaults",
    },
    "sec_bubble_theme": {
        "zh_TW": "💬 說話氣泡風格（僅變更桌面說話氣泡，不影響設定視窗；預設跟隨成員）",
        "ko": "💬 말풍선 테마 (바탕화면 말풍선만 변경, 설정창 제외 · 기본 멤버별 자동)",
        "en": "💬 Speech Bubble Theme (Desktop bubble only, not panels · Default Auto)",
    },
    "theme_auto_title": {
        "zh_TW": "✨ 預設：依成員自動切換專屬應援框 (Auto)",
        "ko": "✨ 기본: 멤버별 전용 응원 말풍선 자동 전환 (Auto)",
        "en": "✨ Default: Auto Switch by Active Member (Auto)",
    },
    "theme_auto_sub": {
        "zh_TW": "切換角色時自動搭配成員應援色氣泡（設定與功能面板維持粉紅主題）",
        "ko": "멤버 변경 시 전용 응원 말풍선 자동 적용 (설정·기능 패널은 핑크 테마 유지)",
        "en": "Matches member cheering bubble on switch (settings & panels keep pink theme)",
    },
    "sec_pet_size": {
        "zh_TW": "📏 桌寵尺寸",
        "ko": "📏 데스크펫 크기",
        "en": "📏 Pet Size",
    },
    "sec_text_size": {
        "zh_TW": "📝 說話氣泡字級（僅調整桌面說話氣泡文字）",
        "ko": "📝 말풍선 글자 크기 (바탕화면 말풍선 텍스트만 조절)",
        "en": "📝 Bubble Text Size (Adjusts desktop speech bubble text only)",
    },
    "pet_small": {"zh_TW": "小 (144px)", "ko": "작게 (144px)", "en": "Small (144px)"},
    "pet_medium": {"zh_TW": "✨ 中 (192px 預設)", "ko": "✨ 보통 (192px 기본)", "en": "✨ Medium (192px Default)"},
    "pet_large": {"zh_TW": "大 (240px)", "ko": "크게 (240px)", "en": "Large (240px)"},
    "txt_small": {"zh_TW": "小字 (9pt)", "ko": "작은 글씨 (9pt)", "en": "Small (9pt)"},
    "txt_medium": {"zh_TW": "✨ 適中 (10pt 預設)", "ko": "✨ 보통 (10pt 기본)", "en": "✨ Medium (10pt Default)"},
    "txt_large": {"zh_TW": "大字 (12pt)", "ko": "큰 글씨 (12pt)", "en": "Large (12pt)"},
    "sec_standby_clock": {
        "zh_TW": "🕰️ 待機時鐘應援資訊框位置（待機中也可按 H 鍵切換純賞圖）",
        "ko": "🕰️ 대기화면 시계·응원 정보 위치 (대기 중 H 키로 순수 감상 전환)",
        "en": "🕰️ Standby Clock & Info Position (Press H in standby for pure view)",
    },
    "clock_pos_top_right": {
        "zh_TW": "✨ 右上角 (預設)",
        "ko": "✨ 오른쪽 위 (기본)",
        "en": "✨ Top Right (Default)",
    },
    "clock_pos_top_left": {
        "zh_TW": "左上角",
        "ko": "왼쪽 위",
        "en": "Top Left",
    },
    "clock_pos_hidden": {
        "zh_TW": "隱藏（純賞背景）",
        "ko": "숨김 (배경 감상)",
        "en": "Hidden (Pure View)",
    },
    "sec_interval": {
        "zh_TW": "⏰ 久坐提醒：每隔多久提醒你起來動一動（預設 60 分鐘，可自訂 5～240）",
        "ko": "⏰ 스트레칭 알림: 몇 분마다 일어나 움직이라고 알려줄까요? (기본 60분, 5~240분)",
        "en": "⏰ Stretch reminder: how often to nudge you to move (default 60 min, 5–240)",
    },
    "interval_off": {"zh_TW": "關閉", "ko": "끄기", "en": "Off"},
    "interval_unit": {"zh_TW": "{m} 分鐘", "ko": "{m}분", "en": "{m}m"},
    "interval_default_unit": {"zh_TW": "✨ {m} 分 (預設)", "ko": "✨ {m}분 (기본)", "en": "✨ {m}m (Def)"},
    "custom_min_label": {
        "zh_TW": "🛠️ 自訂分鐘 (5~240)：",
        "ko": "🛠️ 직접 입력 (5~240분):",
        "en": "🛠️ Custom mins (5~240):",
    },
    "btn_apply_min": {"zh_TW": "套用分鐘", "ko": "적용", "en": "Apply"},
    "custom_min_invalid": {
        "zh_TW": "⚠️ 請輸入 5～240 之間的整數分鐘（或點上方「關閉」）",
        "ko": "⚠️ 5~240 사이의 정수(분)를 입력해 주세요 (또는 위 '끄기' 선택)",
        "en": "⚠️ Enter a whole number between 5 and 240 mins (or click 'Off' above)",
    },
    "sec_hourly": {
        "zh_TW": "🕰️ 整點報時關懷",
        "ko": "🕰️ 정각 알림",
        "en": "🕰️ Hourly Chime",
    },
    "hourly_desc": {
        "zh_TW": "整點冒泡泡報時",
        "ko": "정각 말풍선 알림",
        "en": "Bubble on the hour",
    },
    "hourly_range": {"zh_TW": "時段", "ko": "시간대", "en": "Hours"},
    "hourly_on": {"zh_TW": "✓ 已開啟 (預設)", "ko": "✓ 켜짐 (기본)", "en": "✓ Enabled (Default)"},
    "hourly_off": {"zh_TW": "已關閉", "ko": "꺼짐", "en": "Disabled"},
    "sec_message": {
        "zh_TW": "💌 久坐提醒要說什麼（預設：成員專屬台詞；也可改成你自己的提醒）",
        "ko": "💌 알림에 뭐라고 말할까요? (기본: 멤버 대사, 직접 쓴 문구도 가능)",
        "en": "💌 What the reminder says (default: the member's own line, or your own note)",
    },
    "btn_msg_default": {
        "zh_TW": "✨ 預設：成員專屬關懷台詞",
        "ko": "✨ 기본: 멤버별 다정한 대사",
        "en": "✨ Default: Member Caring Line",
    },
    "btn_msg_apply": {
        "zh_TW": "💾 套用自訂台詞",
        "ko": "💾 문구 적용",
        "en": "💾 Apply Note",
    },
    "msg_placeholder_hint": {
        "zh_TW": "最多 60 字，例如「該喝水、點眼藥水囉！」；留空就用成員台詞",
        "ko": "최대 60자까지 직접 입력 가능 (비워두면 기본 멤버 대사 사용)",
        "en": "Up to 60 chars custom reminder text (leave empty for default member line)",
    },
    "btn_preview": {
        "zh_TW": "⚡ 試播一次提醒泡泡（不會重設計時）",
        "ko": "⚡ 알림 말풍선 미리보기 (타이머는 그대로)",
        "en": "⚡ Preview the reminder bubble (timer keeps running)",
    },
    "sec_pet_first": {
        "zh_TW": "🐾 讓通知改由桌寵播報（不跳 Windows 橫幅）與直播隱私遮罩",
        "ko": "🐾 알림을 펫이 대신 알려주기 (Windows 배너 끄기) · 방송 마스크",
        "en": "🐾 Let the pet announce notifications (no Windows banners) · stream mask",
    },
    "pet_first_desc": {
        "zh_TW": "① 按右邊按鈕，打開「系統 › 通知」，最上面的「通知」保持開啟。\n"
                 "② 全部改由桌寵播報：開啟「請勿打擾」，Teams、LINE 等所有 App 都不跳橫幅，改由桌寵念出（通知仍進通知中心）。\n"
                 "③ 只換某些 App：往下找到該 App，關閉「顯示通知橫幅」，保留「在通知中心顯示通知」。\n"
                 "桌寵讀的是通知中心，所以通知一定要能進通知中心。",
        "ko": "① 오른쪽 버튼으로 '시스템 › 알림'을 열고 맨 위 '알림'은 켜 두세요.\n"
              "② 모두 펫에게: '방해 금지'를 켜면 Teams·LINE 등 모든 앱의 배너가 사라지고 펫이 알려줘요.\n"
              "③ 일부 앱만: 아래에서 앱을 골라 '알림 배너 표시'를 끄고 '알림 센터에 알림 표시'는 유지하세요.\n"
              "펫은 알림 센터를 읽으므로 알림 센터에는 꼭 남아야 해요.",
        "en": "① Right button: System › Notifications; keep 'Notifications' on.\n"
              "② All apps via the pet: turn on 'Do not disturb' - no banners, the pet reads them.\n"
              "③ Some apps: turn off their 'banners', keep 'notification center' on.\n"
              "The pet reads the notification center, so alerts must still arrive there.",
    },
    "btn_notif_guide": {
        "zh_TW": "📖 各 App 通知設定指南",
        "ko": "📖 앱별 알림 설정 가이드",
        "en": "📖 App Setup Guide",
    },
    "btn_open_win_notif": {
        "zh_TW": "⚙️ 開啟 Windows 通知設定",
        "ko": "⚙️ Windows 알림 설정 열기",
        "en": "⚙️ Windows Settings",
    },
    "privacy_label": {
        "zh_TW": "🔒 直播隱私遮罩（僅顯示「App 有新通知」，隱藏敏感正文）",
        "ko": "🔒 방송 프라이버시 마스크 (민감 본문 숨김 · 앱 이름만 표시)",
        "en": "🔒 Stream Privacy Mask (Show App name only, hide body text)",
    },
    "privacy_on": {"zh_TW": "🔒 遮罩開啟", "ko": "🔒 마스크 켜짐", "en": "🔒 Mask ON"},
    "privacy_off": {"zh_TW": "🔓 遮罩關閉", "ko": "🔓 마스크 꺼짐", "en": "🔓 Mask OFF"},
    "notify_bubble_style": {"zh_TW": "通知氣泡樣式", "ko": "알림 말풍선 스타일", "en": "Notification Bubble Style"},
    "notify_style_banner": {"zh_TW": "B · 雙層醒目（預設）", "ko": "B · 강조 카드 (기본)", "en": "B · Bold Card (default)"},
    "notify_style_sticky": {"zh_TW": "C · 便條貼", "ko": "C · 메모지", "en": "C · Sticky Note"},
    "notify_style_standard": {"zh_TW": "一般樣式（關閉醒目）", "ko": "일반 (강조 끄기)", "en": "Standard (highlight off)"},
}

_FITTED_LAYOUT_CACHE: dict[tuple[int, int, int, int, float, int, int], tuple[float, float, int, int]] = {}


def _card_theme_label(tkey: str, lang: str) -> str:
    label = get_theme_display_name(tkey, lang)
    if tkey == "classic" and label.endswith(" (Classic)"):
        return label[: -len(" (Classic)")]
    return label


def _pt(key: str, lang: str, **kwargs: Any) -> str:
    entry = PANEL_I18N.get(key, {})
    text = entry.get(lang, entry.get("zh_TW", key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def _font_family(lang: str) -> str:
    if lang == "ko":
        return "Malgun Gothic"
    if lang == "en":
        return "Segoe UI"
    return "Microsoft JhengHei"


def _coerce_work_area(
    work_area: tuple[int, int, int, int] | WorkArea | None,
) -> Optional[WorkArea]:
    if isinstance(work_area, WorkArea):
        return work_area
    if isinstance(work_area, (tuple, list)) and len(work_area) == 4:
        try:
            left, top, right, bottom = (int(v) for v in work_area)
            if right > left and bottom > top:
                return WorkArea(left, top, right, bottom)
        except (TypeError, ValueError):
            return None
    return None


def _sanitize_state(raw: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for section in PANEL_DEFAULTS.values():
        merged.update(section)
    if not isinstance(raw, Mapping):
        return merged
    bt = raw.get("bubble_theme")
    if isinstance(bt, str) and (bt == "auto" or bt in THEMES):
        merged["bubble_theme"] = bt
    ps = raw.get("pet_size")
    if ps in ("small", "medium", "large"):
        merged["pet_size"] = ps
    ts = raw.get("text_size")
    if ts in ("small", "medium", "large"):
        merged["text_size"] = ts
    scp = raw.get("standby_clock_position")
    if scp in ("top_right", "top_left", "hidden"):
        merged["standby_clock_position"] = scp
    hc = raw.get("hourly_chime")
    if type(hc) is bool:
        merged["hourly_chime"] = hc
    hs, he = raw.get("hourly_start"), raw.get("hourly_end")
    if type(hs) is int and type(he) is int and 0 <= hs <= he <= 23:
        merged["hourly_start"], merged["hourly_end"] = hs, he
    si = raw.get("sedentary_interval_min")
    if type(si) is int and (si == 0 or 5 <= si <= 240):
        merged["sedentary_interval_min"] = si
    sm = raw.get("sedentary_message")
    if isinstance(sm, str):
        merged["sedentary_message"] = sm
    npm = raw.get("notify_privacy_mode")
    merged["notify_privacy_mode"] = npm if type(npm) is bool else False
    notify_style = raw.get("notify_bubble_style")
    if isinstance(notify_style, str) and notify_style in VALID_NOTIFY_BUBBLE_STYLES:
        merged["notify_bubble_style"] = notify_style
    return merged


class SettingsPanel:
    """Unified Default + Custom Settings Panel for Appearance and Caring Reminders."""

    TABS = ("appearance", "reminders")

    def __init__(
        self,
        parent: tk.Misc,
        lang: str = "zh_TW",
        char_key: str = "chorong",
        state: Optional[Mapping[str, Any]] = None,
        on_change: Optional[Callable[[str, Any], bool]] = None,
        on_reset: Optional[Callable[[str], bool]] = None,
        on_preview: Optional[Callable[[str], bool]] = None,
        on_close: Optional[Callable[[], None]] = None,
        initial_tab: str = "appearance",
        work_area: tuple[int, int, int, int] | WorkArea | None = None,
    ) -> None:
        self.parent = parent
        self.lang = lang if lang in ("zh_TW", "ko", "en") else "zh_TW"
        self.char_key = char_key if char_key in MEMBER_THEMES else "chorong"
        self.state = _sanitize_state(state)
        self.on_change = on_change
        self.on_reset = on_reset
        self.on_preview = on_preview
        self.on_close = on_close
        self.active_tab = initial_tab if initial_tab in self.TABS else "appearance"
        self._explicit_work_area: Optional[WorkArea] = _coerce_work_area(work_area)

        self._closed = False
        self._drag_offset = (0, 0)
        self._dragging = False
        self.last_clamped_pos: tuple[int, int] = (0, 0)
        self._present_after_id: Optional[str] = None
        self.interval_entry: Optional[tk.Entry] = None
        self.msg_entry: Optional[tk.Entry] = None
        self.interval_error: str = ""
        self._rendered_signature: Optional[tuple[str, str, str]] = None
        self._pressed_tag: Optional[str] = None
        self._fonts: dict[tuple[str, int, str], tkfont.Font] = {}

        self._design_w = 600
        self._design_h = 812

        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.win = self.window
        try:
            top = parent.winfo_toplevel()
            if not top.overrideredirect() and top.winfo_viewable():
                self.window.transient(parent)
        except Exception:
            pass
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.wm_attributes("-transparentcolor", BG_TRANSPARENT)
        except tk.TclError:
            pass
        self.window.configure(bg=BG_TRANSPARENT)
        self._desktop = WindowsDesktopAdapter(fallback_bounds=self._tk_fallback_work_area)
        self._raw_ui_scale = ui_scale(self.window)
        self.ui_scale = self._raw_ui_scale
        self._font_scale = 1.0
        self.w = round(self._design_w * self.ui_scale)
        self.h = round(self._design_h * self.ui_scale)
        self._compute_fitted_layout()

        self.canvas = tk.Canvas(
            self.window,
            width=self.w,
            height=self.h,
            bg=BG_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self._position_near_parent()
        self._render()
        cursor_key = getattr(self, "_cursor_key", None)
        if cursor_key:
            from app.cursor_manager import apply_cursor_to_widgets
            apply_cursor_to_widgets((self.window, self.canvas), cursor_key)

        self.canvas.bind("<ButtonPress-1>", self._on_drag_begin)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.window.deiconify()
        self.window.update_idletasks()
        self.window.lift()
        self._present_after_id = self.window.after_idle(self._present_after_menu)

    def _present_after_menu(self) -> None:
        self._present_after_id = None
        try:
            if not self._closed and self.window.winfo_exists():
                self.window.deiconify()
                self.window.lift()
        except tk.TclError:
            pass

    def _tk_fallback_work_area(self) -> WorkArea:
        try:
            sw = max(640, int(self.window.winfo_screenwidth()))
            sh = max(480, int(self.window.winfo_screenheight()))
        except Exception:
            sw, sh = 1920, 1080
        return WorkArea(0, 0, sw, sh)

    def _active_work_area(self, anchor_x: int, anchor_y: int) -> WorkArea:
        if self._explicit_work_area is not None:
            return self._explicit_work_area
        try:
            return self._desktop.work_area_for_point(anchor_x, anchor_y)
        except Exception:
            return self._tk_fallback_work_area()

    def _hwnd(self) -> int:
        self.window.update_idletasks()
        frame = self.window.wm_frame()
        if frame:
            return int(frame, 16) if frame.startswith("0x") else int(frame)
        return int(self.window.winfo_id())

    def _compute_fitted_layout(self) -> None:
        try:
            px = int(self.parent.winfo_rootx()) + max(1, int(self.parent.winfo_width())) // 2
            py = int(self.parent.winfo_rooty()) + max(1, int(self.parent.winfo_height())) // 2
        except Exception:
            px, py = 600, 300
        area = self._active_work_area(px, py)
        cache_key = (
            area.left,
            area.top,
            area.right,
            area.bottom,
            round(self._raw_ui_scale, 4),
            self._design_w,
            self._design_h,
        )
        cached = _FITTED_LAYOUT_CACHE.get(cache_key)
        if cached is not None:
            self._font_scale, self.ui_scale, self.w, self.h = cached
            return
        avail_w = max(320, area.width - 16)
        avail_h = max(380, area.height - 16)
        raw_w = self._design_w * self._raw_ui_scale
        raw_h = self._design_h * self._raw_ui_scale
        fit = 1.0
        if raw_w > avail_w or raw_h > avail_h:
            fit = min(avail_w / max(1.0, raw_w), avail_h / max(1.0, raw_h))
        self._font_scale = fit
        self.ui_scale = max(0.5, self._raw_ui_scale * fit)
        self.w = max(320, min(avail_w, round(self._design_w * self.ui_scale)))
        self.h = max(380, min(avail_h, round(self._design_h * self.ui_scale)))
        _FITTED_LAYOUT_CACHE[cache_key] = (self._font_scale, self.ui_scale, self.w, self.h)

    def _fpt(self, pt: int) -> int:
        if self._font_scale < 0.999:
            return -max(7, round(pt * (96.0 / 72.0) * self.ui_scale))
        return pt

    def _font(self, fam: str, pt: int, weight: str = "normal") -> tkfont.Font:
        sz = self._fpt(pt)
        key = (fam, sz, weight)
        f = self._fonts.get(key)
        if f is None:
            f = tkfont.Font(root=self.window, family=fam, size=sz, weight=weight)
            self._fonts[key] = f
        return f

    def _move_window(self, x: int, y: int) -> None:
        """Place window at virtual-desktop (x, y) via Win32 SetWindowPos to avoid Tk -x right-edge semantics."""
        self.last_clamped_pos = (int(x), int(y))
        if self.window.winfo_width() != self.w or self.window.winfo_height() != self.h:
            self.window.geometry(f"{self.w}x{self.h}+{max(0, int(x))}+{max(0, int(y))}")
        hwnd = self._hwnd()
        if not self._desktop.position_without_activation(hwnd, int(x), int(y)):
            if x >= 0 and y >= 0:
                self.window.geometry(f"{self.w}x{self.h}+{int(x)}+{int(y)}")

    def _position_near_parent(self) -> None:
        try:
            px = int(self.parent.winfo_rootx())
            py = int(self.parent.winfo_rooty())
            pw = max(1, int(self.parent.winfo_width()))
            ph = max(1, int(self.parent.winfo_height()))
        except Exception:
            px, py, pw, ph = 600, 300, 192, 192

        work = self._active_work_area(px + pw // 2, py + ph // 2)
        cand_x = px - self.w - 16
        if cand_x < work.left:
            cand_x = px + pw + 16
        x, y = work.clamp(cand_x, py - 80, self.w, self.h)
        self._move_window(x, y)

    def is_section_default(self, section: str) -> bool:
        defaults = PANEL_DEFAULTS.get(section, {})
        return all(self.state.get(k) == v for k, v in defaults.items())

    def switch_tab(self, tab_key: str) -> None:
        if tab_key not in self.TABS or self._closed:
            return
        self.active_tab = tab_key
        self._render()

    def apply_change(self, key: str, value: Any) -> bool:
        """Delegate change to controller (`on_change`); controller calls `refresh(state=...)` as SSOT."""
        if self._closed:
            return False
        if self.on_change is not None:
            return bool(self.on_change(key, value))
        self.state[key] = value
        self._render()
        return True

    def reset_section(self, section: str) -> bool:
        """Delegate section reset to controller (`on_reset`); controller calls `refresh(state=...)` as SSOT."""
        if self._closed or section not in PANEL_DEFAULTS:
            return False
        if self.on_reset is not None:
            return bool(self.on_reset(section))
        for k, v in PANEL_DEFAULTS[section].items():
            self.state[k] = v
        self._render()
        return True

    def trigger_preview(self, kind: str = "sedentary") -> bool:
        if self._closed:
            return False
        if self.on_preview is not None:
            return bool(self.on_preview(kind))
        return False

    def refresh(
        self,
        *,
        state: Optional[Mapping[str, Any]] = None,
        char_key: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> None:
        if self._closed:
            return
        if state is not None:
            self.state = _sanitize_state(state)
        if char_key is not None and char_key in MEMBER_THEMES:
            self.char_key = char_key
        if lang is not None and lang in ("zh_TW", "ko", "en"):
            self.lang = lang
        if not self.window.winfo_exists():
            return
        sig = (self.active_tab, self.char_key, self.lang)
        if sig == self._rendered_signature and self._fast_update_state():
            return
        self._render()

    def _fast_update_state(self) -> bool:
        c = self.canvas
        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        fam = _font_family(self.lang)
        is_def = self.is_section_default(self.active_tab)
        status_items = c.find_withtag("mode_status_text")
        if not status_items:
            return False
        c.itemconfigure(
            status_items[0],
            text=_pt("mode_default_active" if is_def else "mode_custom_active", self.lang),
            fill="#2e7d32" if is_def else theme["primary"],
        )
        if self.active_tab == "appearance":
            cur_theme = self.state.get("bubble_theme", "auto")
            auto_sel = cur_theme == "auto"
            for item in c.find_withtag("theme_auto"):
                kind = c.type(item)
                if kind == "polygon":
                    c.itemconfigure(
                        item,
                        fill=theme["header_fill"] if auto_sel else "#ffffff",
                        outline=theme["primary"] if auto_sel else theme["badge_border"],
                        width=(2.5 if auto_sel else 1.0) * self.ui_scale,
                    )
            auto_title = c.find_withtag("theme_auto_title_text")
            if auto_title:
                check_prefix = "✓ " if auto_sel else ""
                c.itemconfigure(auto_title[0], text=f"{check_prefix}{_pt('theme_auto_title', self.lang)}")

            for tkey in THEME_KEYS_ORDER:
                b_theme = get_theme(tkey)
                is_sel = cur_theme == tkey
                bg_items = c.find_withtag(f"theme_bg_{tkey}")
                txt_items = c.find_withtag(f"theme_txt_{tkey}")
                if not bg_items or not txt_items:
                    return False
                c.itemconfigure(
                    bg_items[0],
                    outline=b_theme.header_color if is_sel else b_theme.outline_color,
                    width=(2.5 if is_sel else 1.2) * self.ui_scale,
                )
                label = _card_theme_label(tkey, self.lang)
                if is_sel:
                    label = f"✓ {label}"
                c.itemconfigure(
                    txt_items[0],
                    text=label,
                    font=self._font(fam, 8, "bold" if is_sel else "normal"),
                    fill=b_theme.header_color if is_sel else b_theme.text_color,
                )

            for group, state_key, opts in (
                ("pet_size", "pet_size", ("small", "medium", "large")),
                ("text_size", "text_size", ("small", "medium", "large")),
                ("standby_clock", "standby_clock_position", ("top_right", "top_left", "hidden")),
            ):
                cur_val = self.state.get(state_key)
                for opt in opts:
                    is_sel = cur_val == opt
                    for item in c.find_withtag(f"{group}_{opt}"):
                        if c.type(item) == "polygon":
                            c.itemconfigure(
                                item,
                                fill=theme["primary"] if is_sel else "#ffffff",
                                outline=theme["primary"] if is_sel else theme["badge_border"],
                            )
                        elif c.type(item) == "text":
                            c.itemconfigure(item, fill="#ffffff" if is_sel else theme["accent"])
            return True
        return False

    def _destroy_entries(self) -> None:
        from app.cursor_manager import release_cursor_hooks

        for attr in ("interval_entry", "msg_entry"):
            widget = getattr(self, attr, None)
            setattr(self, attr, None)
            if widget is not None:
                try:
                    release_cursor_hooks((widget,))
                    widget.destroy()
                except Exception:
                    pass

    def _render(self) -> None:
        if self._closed or not self.window.winfo_exists():
            return
        self._destroy_entries()
        c = self.canvas
        c.delete("all")

        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        fam = _font_family(self.lang)
        w, h = self._design_w, self._design_h

        # Outer shadow & card body
        _draw_round_rect(c, 6, 8, w - 2, h - 2, r=24, fill=theme["glow"], outline="")
        _draw_round_rect(
            c, 4, 4, w - 6, h - 6, r=24,
            fill="#ffffff", outline=theme["border"], width=3,
        )
        _draw_round_rect(
            c, 12, 12, w - 14, h - 14, r=18,
            fill=theme["soft_bg"], outline="",
        )

        # Header banner (draggable)
        _draw_round_rect(
            c, 16, 16, w - 18, 64, r=14,
            fill=theme["header_fill"], outline=theme["badge_border"], width=1,
            tags=("drag_handle",),
        )
        member_label = get_member_display_name(self.char_key, self.lang)
        c.create_text(
            28, 40,
            text=f"{_pt('title', self.lang)}  ·  {member_label}",
            font=self._font(fam, 11, "bold"),
            fill=theme["primary"],
            anchor="w",
            tags=("drag_handle",),
        )

        # Close button
        _draw_round_rect(
            c, w - 52, 24, w - 24, 52, r=10,
            fill="#ffffff", outline=theme["badge_border"], width=1,
            tags=("btn_close",),
        )
        c.create_text(
            w - 38, 38,
            text="×",
            font=self._font(fam, 12, "bold"),
            fill=theme["primary"],
            tags=("btn_close",),
        )

        # 2 Tabs: Appearance vs Reminders
        tab_y1, tab_y2 = 74, 110
        tab_w = (w - 44) // 2
        for idx, tkey in enumerate(self.TABS):
            tx1 = 18 + idx * (tab_w + 8)
            tx2 = tx1 + tab_w
            is_active = tkey == self.active_tab
            t_fill = theme["primary"] if is_active else "#ffffff"
            t_fg = "#ffffff" if is_active else theme["accent"]
            t_out = theme["primary"] if is_active else theme["badge_border"]
            tag = f"tab_{tkey}"
            _draw_round_rect(
                c, tx1, tab_y1, tx2, tab_y2, r=12,
                fill=t_fill, outline=t_out, width=1.5,
                tags=(tag,),
            )
            c.create_text(
                (tx1 + tx2) // 2, (tab_y1 + tab_y2) // 2,
                text=_pt(f"tab_{tkey}", self.lang),
                font=self._font(fam, 10, "bold"),
                fill=t_fg,
                tags=(tag,),
            )

        # Default vs Custom Status Strip + Restore Default Button
        is_def = self.is_section_default(self.active_tab)
        strip_y1, strip_y2 = 118, 152
        _draw_round_rect(
            c, 18, strip_y1, w - 18, strip_y2, r=10,
            fill="#ffffff", outline=theme["badge_border"], width=1,
        )
        status_txt = _pt("mode_default_active" if is_def else "mode_custom_active", self.lang)
        status_fg = "#2e7d32" if is_def else theme["primary"]
        c.create_text(
            30, (strip_y1 + strip_y2) // 2,
            text=status_txt,
            font=self._font(fam, 9, "bold"),
            fill=status_fg,
            anchor="w",
            tags=("mode_status_text",),
        )

        rst_tag = f"btn_reset_{self.active_tab}"
        _draw_round_rect(
            c, w - 166, strip_y1 + 4, w - 26, strip_y2 - 4, r=8,
            fill=theme["pill_fill"], outline=theme["primary"], width=1,
            tags=(rst_tag,),
        )
        c.create_text(
            w - 96, (strip_y1 + strip_y2) // 2,
            text=_pt("btn_restore_default", self.lang),
            font=self._font(fam, 8, "bold"),
            fill=theme["primary"],
            tags=(rst_tag,),
        )

        if self.active_tab == "appearance":
            self._render_appearance_tab(c, theme, fam)
        else:
            self._render_reminders_tab(c, theme, fam)
        cursor_key = getattr(self, "_cursor_key", None) or getattr(self.window, "_panda_cursor_key", None)
        if cursor_key:
            from app.cursor_manager import apply_cursor_to_widgets

            apply_cursor_to_widgets((self.window, self.canvas, self.interval_entry, self.msg_entry), cursor_key)
        scale_canvas(c, self.ui_scale)
        for item in c.find_all():
            if c.type(item) == "window":
                for opt in ("width", "height"):
                    raw_val = c.itemcget(item, opt)
                    if raw_val:
                        c.itemconfigure(item, **{opt: round(float(raw_val) * self.ui_scale)})
        self._rendered_signature = (self.active_tab, self.char_key, self.lang)

    def _render_appearance_tab(self, c: tk.Canvas, theme: dict[str, str], fam: str) -> None:
        w = self._design_w
        cur_theme = self.state.get("bubble_theme", "auto")

        # Section 1: Bubble Theme ("Default Auto" + "9 Custom Cards")
        c.create_text(
            24, 168,
            text=_pt("sec_bubble_theme", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )

        # Prominent Default Auto Card
        auto_sel = cur_theme == "auto"
        auto_y1, auto_y2 = 182, 232
        _draw_round_rect(
            c, 18, auto_y1, w - 18, auto_y2, r=12,
            fill=theme["header_fill"] if auto_sel else "#ffffff",
            outline=theme["primary"] if auto_sel else theme["badge_border"],
            width=2.5 if auto_sel else 1,
            tags=("theme_auto",),
        )
        check_prefix = "✓ " if auto_sel else ""
        c.create_text(
            32, auto_y1 + 16,
            text=f"{check_prefix}{_pt('theme_auto_title', self.lang)}",
            font=self._font(fam, 9, "bold"),
            fill=theme["primary"],
            anchor="w",
            width=w - 64,
            tags=("theme_auto", "theme_auto_title_text"),
        )
        c.create_text(
            32, auto_y1 + 35,
            text=_pt("theme_auto_sub", self.lang),
            font=self._font(fam, 8),
            fill="#666666",
            anchor="w",
            width=w - 64,
            tags=("theme_auto",),
        )

        # 3x3 Grid of Custom Themes
        cols = 3
        gap_x, gap_y = 10, 8
        card_w = (w - 36 - gap_x * (cols - 1)) // cols
        card_h = 54
        start_y = 242

        for idx, tkey in enumerate(THEME_KEYS_ORDER):
            r_idx = idx // cols
            c_idx = idx % cols
            cx1 = 18 + c_idx * (card_w + gap_x)
            cy1 = start_y + r_idx * (card_h + gap_y)
            cx2 = cx1 + card_w
            cy2 = cy1 + card_h

            b_theme = get_theme(tkey)
            is_sel = cur_theme == tkey
            tag = f"theme_{tkey}"

            _draw_round_rect(
                c, cx1, cy1, cx2, cy2, r=11,
                fill=b_theme.bg_fill,
                outline=b_theme.header_color if is_sel else b_theme.outline_color,
                width=2.5 if is_sel else 1.2,
                tags=(tag, f"theme_bg_{tkey}"),
            )
            # Color swatch pill on the left of each theme card
            _draw_round_rect(
                c, cx1 + 8, cy1 + 10, cx1 + 24, cy2 - 10, r=6,
                fill=b_theme.chip_fill,
                outline=b_theme.outline_color,
                width=1.2,
                tags=(tag,),
            )
            label = _card_theme_label(tkey, self.lang)
            if is_sel:
                label = f"✓ {label}"
            c.create_text(
                cx1 + 30, (cy1 + cy2) // 2,
                text=label,
                font=self._font(fam, 8, "bold" if is_sel else "normal"),
                fill=b_theme.header_color if is_sel else b_theme.text_color,
                anchor="w",
                width=card_w - 36,
                tags=(tag, f"theme_txt_{tkey}"),
            )

        # Section 2: Pet Size & Text Size
        sec2_y = 432
        c.create_text(
            24, sec2_y,
            text=_pt("sec_pet_size", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
        )
        cur_pet = self.state.get("pet_size", "medium")
        pill_w = (w - 36 - 20) // 3
        for idx, (pkey, i18n_k) in enumerate((("small", "pet_small"), ("medium", "pet_medium"), ("large", "pet_large"))):
            px1 = 18 + idx * (pill_w + 10)
            px2 = px1 + pill_w
            py1, py2 = sec2_y + 12, sec2_y + 44
            is_sel = cur_pet == pkey
            tag = f"pet_size_{pkey}"
            _draw_round_rect(
                c, px1, py1, px2, py2, r=10,
                fill=theme["primary"] if is_sel else "#ffffff",
                outline=theme["primary"] if is_sel else theme["badge_border"],
                width=1.5,
                tags=(tag,),
            )
            c.create_text(
                (px1 + px2) // 2, (py1 + py2) // 2,
                text=_pt(i18n_k, self.lang),
                font=self._font(fam, 8, "bold"),
                fill="#ffffff" if is_sel else theme["accent"],
                tags=(tag,),
            )

        sec3_y = 490
        c.create_text(
            24, sec3_y,
            text=_pt("sec_text_size", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )
        cur_txt = self.state.get("text_size", "medium")
        for idx, (tkey, i18n_k) in enumerate((("small", "txt_small"), ("medium", "txt_medium"), ("large", "txt_large"))):
            px1 = 18 + idx * (pill_w + 10)
            px2 = px1 + pill_w
            py1, py2 = sec3_y + 12, sec3_y + 44
            is_sel = cur_txt == tkey
            tag = f"text_size_{tkey}"
            _draw_round_rect(
                c, px1, py1, px2, py2, r=10,
                fill=theme["primary"] if is_sel else "#ffffff",
                outline=theme["primary"] if is_sel else theme["badge_border"],
                width=1.5,
                tags=(tag,),
            )
            c.create_text(
                (px1 + px2) // 2, (py1 + py2) // 2,
                text=_pt(i18n_k, self.lang),
                font=self._font(fam, 8, "bold"),
                fill="#ffffff" if is_sel else theme["accent"],
                tags=(tag,),
            )

        sec4_y = 552
        c.create_text(
            24, sec4_y,
            text=_pt("sec_standby_clock", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )
        cur_clock = self.state.get("standby_clock_position", "top_right")
        clock_opts = (
            ("top_right", "clock_pos_top_right"),
            ("top_left", "clock_pos_top_left"),
            ("hidden", "clock_pos_hidden"),
        )
        for idx, (ckey, i18n_k) in enumerate(clock_opts):
            px1 = 18 + idx * (pill_w + 10)
            px2 = px1 + pill_w
            py1, py2 = sec4_y + 12, sec4_y + 44
            is_sel = cur_clock == ckey
            tag = f"standby_clock_{ckey}"
            _draw_round_rect(
                c, px1, py1, px2, py2, r=10,
                fill=theme["primary"] if is_sel else "#ffffff",
                outline=theme["primary"] if is_sel else theme["badge_border"],
                width=1.5,
                tags=(tag,),
            )
            c.create_text(
                (px1 + px2) // 2, (py1 + py2) // 2,
                text=_pt(i18n_k, self.lang),
                font=self._font(fam, 8, "bold"),
                fill="#ffffff" if is_sel else theme["accent"],
                tags=(tag,),
            )

    def _render_reminders_tab(self, c: tk.Canvas, theme: dict[str, str], fam: str) -> None:
        w = self._design_w
        cur_min = int(self.state.get("sedentary_interval_min", 60))
        cur_hourly = bool(self.state.get("hourly_chime", True))
        cur_msg = str(self.state.get("sedentary_message", ""))

        # Card 1: Interval Presets + Custom Minutes Input
        c.create_text(
            24, 168,
            text=_pt("sec_interval", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )
        _draw_round_rect(
            c, 18, 182, w - 18, 282, r=12,
            fill="#ffffff", outline=theme["badge_border"], width=1.2,
        )

        pill_w = (w - 60 - 5 * 8) // 6
        for idx, mins in enumerate(INTERVAL_PRESETS):
            px1 = 30 + idx * (pill_w + 8)
            px2 = px1 + pill_w
            py1, py2 = 194, 228
            is_sel = cur_min == mins
            tag = f"interval_{mins}"
            _draw_round_rect(
                c, px1, py1, px2, py2, r=9,
                fill=theme["primary"] if is_sel else theme["pill_fill"],
                outline=theme["primary"] if is_sel else theme["badge_border"],
                width=1.5 if is_sel else 1,
                tags=(tag,),
            )
            if mins == 0:
                lbl = _pt("interval_off", self.lang)
            elif mins == 60:
                lbl = _pt("interval_default_unit", self.lang, m=60)
            else:
                lbl = _pt("interval_unit", self.lang, m=mins)
            c.create_text(
                (px1 + px2) // 2, (py1 + py2) // 2,
                text=lbl,
                font=self._font(fam, 8, "bold"),
                fill="#ffffff" if is_sel else theme["accent"],
                tags=(tag,),
            )

        # Custom Minute Row (-5m, Entry, +5m, Apply)
        c.create_text(
            32, 255,
            text=_pt("custom_min_label", self.lang),
            font=self._font(fam, 8, "bold"),
            fill="#555555",
            anchor="w",
            width=158,
        )

        # -5 button
        _draw_round_rect(
            c, 195, 240, 235, 270, r=8,
            fill=theme["pill_fill"], outline=theme["badge_border"], width=1,
            tags=("btn_min_dec",),
        )
        c.create_text(215, 255, text="-5", font=self._font(fam, 8, "bold"), fill=theme["primary"], tags=("btn_min_dec",))

        self.interval_entry = tk.Entry(
            self.window,
            font=self._font(fam, 9, "bold"),
            justify="center",
            fg=theme["primary"],
            bg="#fffafd",
            relief="solid",
            bd=1,
        )
        self.interval_entry.insert(0, str(cur_min if cur_min > 0 else 60))
        self.interval_entry.bind("<Return>", lambda _e: self._submit_custom_interval())
        c.create_window(275, 255, window=self.interval_entry, width=64, height=26)

        # +5 button
        _draw_round_rect(
            c, 315, 240, 355, 270, r=8,
            fill=theme["pill_fill"], outline=theme["badge_border"], width=1,
            tags=("btn_min_inc",),
        )
        c.create_text(335, 255, text="+5", font=self._font(fam, 8, "bold"), fill=theme["primary"], tags=("btn_min_inc",))

        # Apply custom minutes button
        _draw_round_rect(
            c, 370, 240, 470, 270, r=8,
            fill=theme["header_fill"], outline=theme["primary"], width=1.2,
            tags=("btn_apply_interval",),
        )
        c.create_text(
            420, 255,
            text=_pt("btn_apply_min", self.lang),
            font=self._font(fam, 8, "bold"),
            fill=theme["primary"],
            tags=("btn_apply_interval",),
        )

        if self.interval_error:
            c.create_text(
                32, 275,
                text=self.interval_error,
                font=self._font(fam, 7, "bold"),
                fill="#c62828",
                anchor="w",
                tags=("interval_error_text",),
            )

        # Card 2: Hourly Chime Toggle
        c.create_text(
            24, 300,
            text=_pt("sec_hourly", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
        )
        _draw_round_rect(
            c, 18, 314, w - 18, 364, r=12,
            fill="#ffffff", outline=theme["badge_border"], width=1.2,
        )
        # Chime hours: [-] 09:00 [+] ~ [-] 22:00 [+] (inclusive, each end 0-23).
        start_h, end_h = int(self.state.get("hourly_start", 9)), int(self.state.get("hourly_end", 22))
        c.create_text(32, 339, text=_pt("hourly_range", self.lang), font=self._font(fam, 8, "bold"),
                      fill="#555555", anchor="w")
        for key, hour, x0 in (("hourly_start", start_h, 70), ("hourly_end", end_h, 204)):
            for sign, bx in ((-1, x0), (1, x0 + 76)):
                tag = f"btn_{key}_{'dec' if sign < 0 else 'inc'}"
                _draw_round_rect(c, bx, 326, bx + 24, 352, r=7, fill=theme["pill_fill"],
                                 outline=theme["badge_border"], width=1, tags=(tag,))
                c.create_text(bx + 12, 339, text="−" if sign < 0 else "+", font=self._font(fam, 9, "bold"),
                              fill=theme["primary"], tags=(tag,))
            c.create_text(x0 + 50, 339, text=f"{hour:02d}:00", font=self._font(fam, 9, "bold"), fill=theme["primary"])
        c.create_text(192, 339, text="～", font=self._font(fam, 9, "bold"), fill="#555555")
        c.create_text(
            312, 339,
            text=_pt("hourly_desc", self.lang),
            font=self._font(fam, 8),
            fill="#555555",
            anchor="w",
        )
        _draw_round_rect(
            c, w - 150, 323, w - 30, 355, r=10,
            fill=theme["primary"] if cur_hourly else "#e0e0e0",
            outline=theme["primary"] if cur_hourly else "#bdbdbd",
            width=1.2,
            tags=("btn_toggle_hourly",),
        )
        c.create_text(
            w - 90, 339,
            text=_pt("hourly_on" if cur_hourly else "hourly_off", self.lang),
            font=self._font(fam, 8, "bold"),
            fill="#ffffff" if cur_hourly else "#555555",
            tags=("btn_toggle_hourly",),
        )

        # Card 3: Custom Reminder Message ("Default Member Line" vs "Custom Note")
        c.create_text(
            24, 382,
            text=_pt("sec_message", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )
        _draw_round_rect(
            c, 18, 396, w - 18, 492, r=12,
            fill="#ffffff", outline=theme["badge_border"], width=1.2,
        )

        is_default_msg = cur_msg == ""
        _draw_round_rect(
            c, 30, 406, 250, 436, r=8,
            fill=theme["primary"] if is_default_msg else theme["pill_fill"],
            outline=theme["primary"],
            width=1.2,
            tags=("btn_msg_default",),
        )
        c.create_text(
            140, 421,
            text=_pt("btn_msg_default", self.lang),
            font=self._font(fam, 8, "bold"),
            fill="#ffffff" if is_default_msg else theme["primary"],
            tags=("btn_msg_default",),
        )

        self.msg_entry = tk.Entry(
            self.window,
            font=self._font(fam, 9),
            fg="#333333",
            bg="#fffafd",
            relief="solid",
            bd=1,
        )
        if cur_msg:
            self.msg_entry.insert(0, cur_msg)
        self.msg_entry.bind("<Return>", lambda _e: self._submit_custom_message())
        c.create_window(230, 456, window=self.msg_entry, width=396, height=26)

        _draw_round_rect(
            c, 440, 442, w - 30, 470, r=8,
            fill=theme["header_fill"], outline=theme["primary"], width=1.2,
            tags=("btn_apply_msg",),
        )
        c.create_text(
            (440 + w - 30) // 2, 456,
            text=_pt("btn_msg_apply", self.lang),
            font=self._font(fam, 8, "bold"),
            fill=theme["primary"],
            tags=("btn_apply_msg",),
        )

        c.create_text(
            32, 480,
            text=_pt("msg_placeholder_hint", self.lang),
            font=self._font(fam, 7),
            fill="#777777",
            anchor="w",
            width=w - 64,
        )

        # Bottom Action Button: Preview Reminder Now
        _draw_round_rect(
            c, 18, 504, w - 18, 540, r=12,
            fill=theme["header_fill"], outline=theme["primary"], width=1.5,
            tags=("btn_preview_sedentary",),
        )
        c.create_text(
            w // 2, 522,
            text=_pt("btn_preview", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["primary"],
            tags=("btn_preview_sedentary",),
        )

        # Card 4: Windows notification guide, stream privacy and relay bubble style.
        cur_privacy = bool(self.state.get("notify_privacy_mode", False))
        c.create_text(
            24, 556,
            text=_pt("sec_pet_first", self.lang),
            font=self._font(fam, 9, "bold"),
            fill=theme["accent"],
            anchor="w",
            width=w - 48,
        )
        _draw_round_rect(
            c, 18, 570, w - 18, 798, r=12,
            fill="#ffffff", outline=theme["badge_border"], width=1.2,
        )
        c.create_text(
            30, 610,
            text=_pt("pet_first_desc", self.lang),
            font=self._font(fam, 8),
            fill="#555555",
            anchor="nw",
            width=w - 60,
            tags=("pet_first_desc",),
        )
        _draw_round_rect(
            c, w - 186, 576, w - 28, 604, r=8,
            fill=theme["pill_fill"], outline=theme["primary"], width=1.2,
            tags=("btn_open_win_notif",),
        )
        c.create_text(
            (w - 186 + w - 28) // 2, 590,
            text=_pt("btn_open_win_notif", self.lang),
            font=self._font(fam, 8, "bold"),
            fill=theme["primary"],
            tags=("btn_open_win_notif",),
        )

        # LINE / Telegram / Teams / Outlook / Gmail: where each app's "Windows notifications" switch is.
        _draw_round_rect(
            c, 30, 576, 250, 604, r=8,
            fill=theme["header_fill"], outline=theme["primary"], width=1.2,
            tags=("btn_notif_guide",),
        )
        c.create_text(
            140, 590,
            text=_pt("btn_notif_guide", self.lang),
            font=self._font(fam, 8, "bold"),
            fill=theme["primary"],
            tags=("btn_notif_guide",),
        )

        c.create_text(
            30, 722,
            text=_pt("privacy_label", self.lang),
            font=self._font(fam, 8, "bold"),
            fill="#444444",
            anchor="w",
            width=w - 190,
        )
        _draw_round_rect(
            c, w - 150, 708, w - 28, 736, r=9,
            fill=theme["primary"] if cur_privacy else "#e0e0e0",
            outline=theme["primary"] if cur_privacy else "#bdbdbd",
            width=1.2,
            tags=("btn_toggle_privacy",),
        )
        c.create_text(
            (w - 150 + w - 28) // 2, 722,
            text=_pt("privacy_on" if cur_privacy else "privacy_off", self.lang),
            font=self._font(fam, 8, "bold"),
            fill="#ffffff" if cur_privacy else "#555555",
            tags=("btn_toggle_privacy",),
        )
        c.create_text(30, 749, text=_pt("notify_bubble_style", self.lang),
                      font=self._font(fam, 8, "bold"), fill="#444444", anchor="w",
                      tags=("notify_style_label",))
        current_style = self.state["notify_bubble_style"]
        gap = 8
        button_w = (w - 60 - 2 * gap) / 3
        for index, key in enumerate(("banner", "sticky", "standard")):
            x = 30 + index * (button_w + gap)
            tag = f"notify_style_option_{key}"
            selected = current_style == key
            _draw_round_rect(c, x, 766, x + button_w, 794, r=8,
                             fill=theme["primary"] if selected else theme["pill_fill"],
                             outline=theme["primary"], tags=(tag,))
            c.create_text(x + button_w / 2, 780, text=_pt(f"notify_style_{key}", self.lang),
                          font=self._font(fam, 8, "bold"),
                          fill="#ffffff" if selected else theme["accent"], tags=(tag,))

    def _apply_notif_guide_cursor(self) -> None:
        guide = getattr(self, "notif_guide", None)
        cursor_key = getattr(self, "_cursor_key", None)
        if guide is None or getattr(guide, "closed", False) or not cursor_key:
            return
        from app.cursor_manager import apply_cursor_to_widgets

        apply_cursor_to_widgets((guide.window,), cursor_key)

    def open_notif_guide(self) -> bool:
        """The per-app guide window (one at a time; closes with the panel)."""
        if self._closed:
            return False
        guide = getattr(self, "notif_guide", None)
        if guide is not None and not guide.closed:
            guide.lift()
            self._apply_notif_guide_cursor()
            return True
        from app.notif_guide import NotifGuideWindow
        theme = MEMBER_THEMES.get(self.char_key, MEMBER_THEMES["chorong"])
        try:
            near = (
                self.window.winfo_rootx() + round(30 * self.ui_scale),
                self.window.winfo_rooty() + round(40 * self.ui_scale),
            )
        except tk.TclError:
            near = None
        self.notif_guide = NotifGuideWindow(
            self.window, self.lang,
            theme={"primary": theme["primary"], "accent": theme["accent"],
                   "soft_bg": theme.get("soft_bg", "#fff5f9"), "badge_border": theme["badge_border"]},
            font_family=_font_family(self.lang), near=near)
        self._apply_notif_guide_cursor()
        return True

    def open_windows_notification_settings(self) -> bool:
        import os
        try:
            if hasattr(os, "startfile"):
                os.startfile("ms-settings:notifications")
                return True
        except Exception:
            pass
        return False

    def _show_interval_error(self) -> None:
        self.interval_error = _pt("custom_min_invalid", self.lang)
        if not self._closed and self.window.winfo_exists():
            self.canvas.delete("interval_error_text")
            item = self.canvas.create_text(
                round(32 * self.ui_scale),
                round(275 * self.ui_scale),
                text=self.interval_error,
                font=self._font(_font_family(self.lang), 7, "bold"),
                fill="#c62828",
                anchor="w",
                tags=("interval_error_text",),
            )
            _ = item

    def _submit_custom_interval(self) -> bool:
        if self.interval_entry is None:
            return False
        raw = self.interval_entry.get().strip()
        try:
            val = int(raw)
        except ValueError:
            self._show_interval_error()
            return False
        if not (5 <= val <= 240):
            self._show_interval_error()
            return False
        self.interval_error = ""
        ok = self.apply_change("sedentary_interval_min", val)
        if not ok:
            self._show_interval_error()
        return ok

    def _submit_custom_message(self) -> bool:
        if self.msg_entry is None:
            return False
        raw = self.msg_entry.get()
        return self.apply_change("sedentary_message", raw)

    _INTERACTIVE_PREFIXES = (
        "theme_",
        "pet_size_",
        "text_size_",
        "standby_clock_",
        "interval_",
        "notify_style_option_",
        "tab_",
        "btn_",
    )

    def _interactive_tag_at(self, event: tk.Event) -> Optional[str]:
        x = getattr(event, "x", None)
        y = getattr(event, "y", None)
        items = (
            self.canvas.find_overlapping(x, y, x, y)
            if x is not None and y is not None
            else self.canvas.find_withtag("current")
        )
        for item in reversed(items):
            for t in self.canvas.gettags(item):
                if t.startswith(self._INTERACTIVE_PREFIXES) and not t.startswith(("theme_bg_", "theme_txt_", "theme_auto_title_")):
                    return t
        for t in self.canvas.gettags("current"):
            if t.startswith(self._INTERACTIVE_PREFIXES) and not t.startswith(("theme_bg_", "theme_txt_", "theme_auto_title_")):
                return t
        return None

    def _dispatch_tag(self, tag: str) -> None:
        if tag == "btn_close":
            self.close()
        elif tag.startswith("tab_"):
            self.switch_tab(tag[4:])
        elif tag.startswith("btn_reset_"):
            self.reset_section(tag[10:])
        elif tag == "theme_auto":
            self.apply_change("bubble_theme", "auto")
        elif tag.startswith("theme_"):
            self.apply_change("bubble_theme", tag[6:])
        elif tag.startswith("pet_size_"):
            self.apply_change("pet_size", tag[9:])
        elif tag.startswith("text_size_"):
            self.apply_change("text_size", tag[10:])
        elif tag.startswith("standby_clock_"):
            self.apply_change("standby_clock_position", tag[14:])
        elif tag.startswith("interval_") and tag != "interval_error_text":
            try:
                self.apply_change("sedentary_interval_min", int(tag[9:]))
            except ValueError:
                pass
        elif tag == "btn_min_dec":
            cur_min = int(self.state.get("sedentary_interval_min", 60))
            self.apply_change("sedentary_interval_min", max(5, (cur_min or 60) - 5))
        elif tag == "btn_min_inc":
            cur_min = int(self.state.get("sedentary_interval_min", 60))
            self.apply_change("sedentary_interval_min", min(240, (cur_min or 60) + 5))
        elif tag == "btn_apply_interval":
            self._submit_custom_interval()
        elif tag in ("btn_hourly_start_dec", "btn_hourly_start_inc", "btn_hourly_end_dec", "btn_hourly_end_inc"):
            key = "hourly_start" if "hourly_start" in tag else "hourly_end"
            sign = -1 if tag.endswith("_dec") else 1
            hour = int(self.state.get(key, 9 if key == "hourly_start" else 22))
            self.apply_change(key, min(23, max(0, hour + sign)))
        elif tag == "btn_toggle_hourly":
            self.apply_change("hourly_chime", not bool(self.state.get("hourly_chime", True)))
        elif tag == "btn_msg_default":
            self.apply_change("sedentary_message", "")
        elif tag == "btn_apply_msg":
            self._submit_custom_message()
        elif tag == "btn_preview_sedentary":
            self.trigger_preview("sedentary")
        elif tag == "btn_open_win_notif":
            self.open_windows_notification_settings()
        elif tag == "btn_notif_guide":
            self.open_notif_guide()
        elif tag == "btn_toggle_privacy":
            self.apply_change("notify_privacy_mode", not bool(self.state.get("notify_privacy_mode", False)))
        elif tag.startswith("notify_style_option_"):
            self.apply_change("notify_bubble_style", tag.removeprefix("notify_style_option_"))

    def _on_drag_begin(self, event: tk.Event) -> None:
        hit = self._interactive_tag_at(event)
        if hit is not None:
            self._pressed_tag = hit
            self._dragging = False
            return
        self._pressed_tag = None
        self._dragging = True
        self.window.lift()
        self._drag_offset = (event.x_root - self.last_clamped_pos[0], event.y_root - self.last_clamped_pos[1])

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self._dragging or self._closed:
            return
        nx = event.x_root - self._drag_offset[0]
        ny = event.y_root - self._drag_offset[1]
        work = self._active_work_area(event.x_root, event.y_root)
        cx, cy = work.clamp(nx, ny, self.w, self.h)
        self._move_window(cx, cy)

    def _on_drag_end(self, event: tk.Event) -> None:
        self._dragging = False
        pressed, self._pressed_tag = self._pressed_tag, None
        if self._closed:
            return
        target = self._interactive_tag_at(event)
        if target is not None and (pressed is None or pressed == target):
            self._dispatch_tag(target)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        guide = getattr(self, "notif_guide", None)
        if guide is not None:
            guide.close()
        if self._present_after_id is not None:
            try:
                self.window.after_cancel(self._present_after_id)
            except Exception:
                pass
            self._present_after_id = None
        self._destroy_entries()
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            pass
        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass
