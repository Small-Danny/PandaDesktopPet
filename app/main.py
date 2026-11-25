"""PandaDesktopPet — Apink Panda Windows Desktop Pet 2.0.

Features:
- Standalone transparent borderless window (Tkinter runtime, zero third-party dependencies).
- 5 Apink member panda characters (Chorong, Bomi, Eunji, Namjoo, Hayoung).
- High-DPI scaling awareness on Windows (SetProcessDpiAwareness).
- Autonomous edge roaming along the screen bottom/edges when idle.
- OS-wide idle detection (GetLastInputInfo): auto sleep when away, cheer greeting upon return.
- Configurable sedentary / stretch reminder (久坐提醒: 30m, 45m, 60m, immediate test).
- Windows Toast notification relay via read-only wpndatabase.db monitoring.
- Authentic Apink member favorite foods feeding system with custom Korean reaction dialogues:
  - Universal favorites: 辣雞爪, 冰美式咖啡 (all members love them!)
  - Chorong (初瓏): 抹茶蛋糕
  - Bomi (普美): 炸醬麵, 魚餅湯
  - Eunji (恩地): 烤雞蛋, 炸醬麵, 部隊鍋泡麵
  - Namjoo (南珠): 冰美式, 泡菜豬肉
  - Hayoung (夏榮): 現烤麵包, 烤地瓜
- Fullscreen Panda Standby / Screensaver mode with clock and border-patrolling pandas.
- Zero-console launchers (LaunchPandaPet.bat / 啟動熊貓桌寵.vbs) and build_exe.bat PyInstaller packaging.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import dataclasses
import gc
import weakref
import datetime
import hashlib
import re
import json
import logging
import math
import os
import random
import sys
import time
from typing import Any, Sequence
import tkinter as tk
from collections import OrderedDict, deque
from pathlib import Path

from PIL import Image, ImageTk

# Ensure project root is in sys.path when executed as `python app/main.py`
_ROOT_DIR = Path(__file__).resolve().parents[1]
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

# Enable High-DPI awareness on Windows to prevent coordinate drift
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from app.bubble import KawaiiSpeechBubble
from app.bubble_themes import THEMES as BUBBLE_THEMES, get_theme_for_member
from app.engine.contracts import (
    ActorState,
    CoordinatorEvent,
    CameoPhase,
    CoordinatorEventType,
    EventRequest,
    GlobalMode,
    Priority,
)
from app.engine.calendar import CalendarScheduler, OffsetClock
from app.platform.layered_surface import LayeredSpriteSurface, PremultipliedFrame, ulw_composed_budget
from app.platform.win32 import WindowsDesktopAdapter, WorkArea, is_workstation_locked, ui_scale
from app.engine.contracts import SystemClock
from app.engine.coordinator import StateCoordinator
from app.engine.cameo import CameoDirector, SpeechCue, CameoFrame, member_full_name
from app.engine.speech_queue import SpeechDecision, SpeechQueue, SpeechRequest
from app.foods import (
    get_feed_animation,
    FOOD_ITEMS,
    SATIETY_DECAY_SECONDS_PER_PERCENT,
    SATIETY_FULL_THRESHOLD,
    feed_pet,
    get_full_reaction,
    get_food_name,
    SATIETY_MAX,
    SATIETY_HUNGRY_THRESHOLD,
    SATIETY_FEED_BOOST,
    SATIETY_FAV_FEED_BOOST,
    get_hunger_aegyo_quote,
)
from app.food_log import normalize as normalize_food_log, outcomes as food_outcomes, record as record_food
from app.i18n import LOCALES, t, get_weekday_names, get_member_display_name, get_member_short_name, get_theme_display_name
from app.notifications import RECENT_LIMIT, WindowsNotificationMonitor, drawer_entry, notif_text, relay_bubble
from app.paths import adopt_legacy_user_data, app_dir, is_developer_mode, resource_dir, user_data_dir
from app.resource_store import resource_exists
from app.personalities import (
    get_cheer_quote,
    get_member_badge,
    get_random_chat_quote,
    get_random_warm_quote,
    get_sleep_quote,
)
from app.standby import (
    PandaStandbyOverlay,
    SPRITE_PX,
    StandbyWarmupManager,
    STANDBY_BINARY_ALPHA,
    STANDBY_EDGE_REFINE,
    seed_prepared_member_pil,
    trim_fitted_wallpapers,
    walk_feet_point,
)
from app.sprites import MIRROR_UNSAFE, SpriteLibrary, directional_action
from app.action_frames import available_actions, load_exact_action, xmas_poses
from app.action_cache import MISSING, ActionEntry, ActionFrameCache, action_cache_budget
from app.anniversary_scene import AnniversaryScene
from app.daily_actions import (
    CHRISTMAS, DRINK_REACTION, EAT_REACTION, FESTIVAL_COOLDOWN_S, FOOD_MEMBER_ANIMATIONS, MAJOR_FESTIVALS,
    NATURAL_ANIMATIONS,
    NATURAL_INTERVAL_S, NATURAL_POSES, NEW_YEAR, RARE_POSES, SIGNATURE_INTERVAL_S, SIGNATURE_POOL, TAP_REACTION,
    festival_occurrence_key, festival_on, pick_natural, pick_signature, FULL_REACTION, PAT_REACTION, SULK_REACTION,
)
from app.festival_greetings import PREVIEW_ACTION_FESTIVAL, festival_greeting
from app.group_celebration import GroupCelebration, scale_sprite_frame
from app.dome_stage import (
    DOME_CONCERT_FRAME_MS,
    DOME_CONCERT_FRAMES_PER_OUTFIT,
    DomeDesktopPreview,
    EUNJI_DOME_CONCERT_OUTFITS,
    EUNJI_DOME_PERSONAL_ACTION,
    dome_concert_cycle_ms,
    dome_concert_step,
    resolved_eunji_dome_outfits,
)
from app.new_year_countdown import NewYearCountdown
from app.fortune_room import FortuneRoomDialog, FORTUNE_LOVE_DESKTOP_ACTION
from app.cameo_view import CameoActorWindow
from app.birthday_dialog import BirthdayDialog, DEFAULT_NICKNAME, format_birthday, read_birthday
from app.bubble_layout import is_emoji
from app.status_card import PandaStatusCard, get_passion_tier
from app.storage.settings import PersistenceService, VALID_NOTIFY_BUBBLE_STYLES, VALID_STANDBY_CLOCK_POSITIONS
from app.tray import PandaSystemTray
from app.hotkey import GlobalHotkeyManager

ROOT = app_dir()
RES_ROOT = resource_dir()
CHARACTERS_DIR = RES_ROOT / "work" / "characters"
# Writable user data (settings.json + runtime.json): %APPDATA%\PandaDesktopPet.
# PANDA_DATA_DIR lets tests and portable setups point elsewhere without touching
# the real profile. LEGACY_DATA_DIR is where it lived before (next to the art).
DATA_DIR = user_data_dir()
LEGACY_DATA_DIR = ROOT / "work"
SPECIAL_DATE_QUEUE_TTL_S = 12 * 3600  # birthdays may wait out a long standby
CAMEO_FIRST_DELAY_S = (8 * 60, 15 * 60)    # first automatic visit after launch
CAMEO_INTERVAL_S = (30 * 60, 45 * 60)      # then roughly every 30-45 min
CAMEO_RETRY_S = (60, 180)                  # stage busy -> try again soon
CAMEO_TICK_MS = 25
FIRST_RUN_TIP_DELAY_MS = 4500   # after the welcome card closes; lets "birthday saved" finish first
CAMEO_MAX_OS_IDLE_S = 120                  # only when the user is at the desk to see it
STARTUP_DIR = Path(Path.home()) / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"
VBS_PATH = STARTUP_DIR / "PandaDesktopPet.vbs"
ERROR_ALREADY_EXISTS = 183
SATIETY_KEY = "satiety_by_member"   # runtime: {member: 0..100}; members never fed start full


def member_satiety(runtime: dict, member: str) -> float:
    """Stored satiety of one member; a missing or broken value counts as full."""
    table = runtime.get(SATIETY_KEY)
    value = table.get(member) if isinstance(table, dict) else None
    if type(value) not in (int, float) or value != value:     # bool, None, str, NaN
        return 100.0
    return max(0.0, min(100.0, float(value)))


def store_satiety(runtime: dict, member: str, value: float, ts: float) -> None:
    """Write one member's satiety; ts is when the member on stage starts decaying from it."""
    if not isinstance(runtime.get(SATIETY_KEY), dict):
        runtime[SATIETY_KEY] = {}
    runtime[SATIETY_KEY][member] = round(max(0.0, min(100.0, value)), 1)
    runtime["last_satiety_update"] = ts


def migrate_shared_satiety(runtime: dict, member: str) -> None:
    """The old single runtime["satiety"] belongs to the member on stage at first start."""
    legacy = runtime.pop("satiety", None)
    if isinstance(runtime.get(SATIETY_KEY), dict):
        return                                  # the per-member table already wins
    runtime[SATIETY_KEY] = {}
    if type(legacy) in (int, float) and legacy == legacy:
        runtime[SATIETY_KEY][member] = round(max(0.0, min(100.0, float(legacy))), 1)


def acquire_single_instance(data_dir: Path):
    """Hold a named mutex per data folder; None when another pet already runs on it.

    Two pets on one folder overwrite each other's runtime.json every minute
    (satiety jumping between their values). If the mutex cannot be created we
    still start, rather than refuse to run.
    """
    if sys.platform != "win32":
        return True
    key = hashlib.sha1(str(Path(data_dir).resolve()).lower().encode("utf-8")).hexdigest()[:16]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR)
    kernel32.CloseHandle.argtypes = (ctypes.wintypes.HANDLE,)
    handle = kernel32.CreateMutexW(None, False, f"Local\\PandaDesktopPet_{key}")
    if not handle:
        log.warning("single-instance mutex unavailable (error %s)", ctypes.get_last_error())
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle

BG = "#ff00fe"

IDLE_MS = 180
WALK_MS = 140
CHEER_MS = 135
SLEEP_MS = 220
WALK_STEP = 7

STATES = ("idle", "walk", "cheer", "sleep")

PET_SIZE_MAP = {"small": 144, "medium": 192, "large": 240}


def pet_display_px(size_key: str, scale: float, work_area=None) -> int:
    """Logical pet preference to physical pixels, with a real work-area safety cap."""
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        scale = 1.0
    if not math.isfinite(scale) or scale <= 0:
        scale = 1.0
    px = round(PET_SIZE_MAP.get(size_key, PET_SIZE_MAP["medium"]) * min(4.0, scale))
    # Synthetic/missing monitor probes must not silently change the preference.
    if isinstance(work_area, WorkArea):
        height = work_area.bottom - work_area.top
        if height >= 480:
            px = min(px, round(height * 0.60))
    return max(48, px)
TEXT_SIZES = ("small", "medium", "large")
SEDENTARY_MIN_RANGE = (5, 240)      # custom interval in minutes; 0 = off
SEDENTARY_MESSAGE_MAX = 60          # custom reminder text, characters
# "Default" for each settings panel section (the custom choices live in settings).
SETTINGS_DEFAULTS = {
    "appearance": {"bubble_theme": "auto", "pet_size": "medium", "text_size": "medium",
                   "standby_clock_position": "top_right"},
    "reminders": {"hourly_chime": True, "hourly_start": 9, "hourly_end": 22,
                  "sedentary_interval_min": 60, "sedentary_message": "", "notify_bubble_style": "banner"},
}


def hourly_range(settings) -> tuple[int, int]:
    """The saved chime hours (start <= end, 0-23); anything else is the 09-22 default."""
    start, end = settings.get("hourly_start", 9), settings.get("hourly_end", 22)
    if type(start) is int and type(end) is int and 0 <= start <= end <= 23:
        return start, end
    return 9, 22


def clean_reminder_text(text: object) -> str | None:
    """Custom sedentary text: control characters removed, trimmed; None if not usable."""
    if not isinstance(text, str):
        return None
    cleaned = "".join(ch for ch in text if ch.isprintable()).strip()
    return cleaned if len(cleaned) <= SEDENTARY_MESSAGE_MAX else None


def rescale_pet_window(
    x_old: int, y_old: int, w_old: int, h_old: int,
    w_new: int, h_new: int, area: WorkArea,
) -> tuple[int, int]:
    """Recalculate top-left coordinates keeping bottom-center anchor constant on the ground."""
    anchor_x = x_old + w_old // 2
    anchor_y = y_old + h_old
    x_new = anchor_x - w_new // 2
    y_new = anchor_y - h_new
    x_clamped = max(area.left, min(x_new, area.right - w_new))
    y_clamped = max(area.top, min(y_new, area.bottom - h_new))
    return x_clamped, y_clamped

# Coordinator actor state -> sprite set (until the asset registry provides
# dedicated run/hop/special animations).
SPRITE_FOR_STATE = {
    ActorState.IDLE: "idle",
    ActorState.WALK: "walk",
    ActorState.RUN: "walk",
    ActorState.HOP: "walk",
    ActorState.CHEER: "cheer",
    ActorState.SPECIAL: "cheer",
    ActorState.SLEEP: "sleep",
    ActorState.DRAGGED: "idle",
}
AMBIENT_FOR_SPRITE = {"idle": ActorState.IDLE, "walk": ActorState.WALK, "sleep": ActorState.SLEEP}
CHEER_CYCLE_FRAMES = 6   # ping-pong 0,1,2,3,2,1
DRAG_THRESHOLD_PX = 4    # a click is not a drag until the pointer moves this far

# Exact registry actions (app/action_frames.py); each is used only when that
# member has it approved, otherwise the pet keeps its base cheer / idle frames.
DRAG_ACTION = "interaction_drag"
CHEER_LIGHTSTICK_ACTION = "special_cheer_lightstick"
BIRTHDAY_ACTION = "special_birthday"
SPECIAL_ACTIONS = (
    "special_birthday", "special_cartwheel", "special_hapkido_kick", "special_gorilla",
    "special_sing_highnote", "standby_stretch", "special_cheer_lightstick", "special_soccer_kick",
    "special_gaming", "special_blow_kiss", "special_guitar", "special_taekwondo", "special_boxing",
    # Approved multi-frame animations (2026-11-10); strictly animated only.
    "scene_flamingo", "daily_cat_cuddle", "interaction_eat",
    # Fortune studio animations (2026-11-16).
    "fortune_tarot_reader", "fortune_student", "fortune_love_reading",
)
CHRISTMAS_ACTION = "festival_christmas"
SECRET_VISITOR_ACTION = "secret_clover_visitor"
# Windows Tk resolves a glyph missing from the UI font (emoji) by a synchronous GDI font
# fallback: ~15 ms per new glyph, so the first settings / status / food panel froze for
# 0.5-1.3 s. Idle startup lays these out once, in small slices, on a hidden canvas.
GLYPH_WARMUP_DELAY_MS = 4000
GLYPH_WARMUP_SLICE_S = 0.02
GLYPH_WARMUP_GAP_MS = 40
GLYPH_WARMUP_EXTRA = (
    "언어♥★•×✨💬🛠📏📝🕰⏰💌🔔💾⚡↺🌸🍊💎💜💛🍫🍇🫐−①②③─▶▸◀☀☕♀♈♋♌♓✈✉✓✕✦❄❌⭐🌊🌯🌶🌽🌿"
    "🍋🍍🍓🍔🍖🍗🍚🍞🍠🍡🍨🍮🍯🍰🍲🍵🍶🍺🍻🍽🎀🎵🎶🏆🏊🏕🏷🐛👑👥💕💦💨💫📖📧🔓🔕🔥🔴🕹🖼"
    "😅😆😊😋😤😫😷🙅🚨🚫🛌🤐🥀🥂🥃🥓🥖🥗🥙🥚🥛🥟🥣🥩🥬🥭🥰🥵🦀🧁🧄🧇🧊🧋🪻🫓🫘"
)
_GLYPH_SKIP = ((0x2E80, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF),
               (0x3000, 0x303F), (0x1100, 0x11FF), (0x3130, 0x318F), (0x2000, 0x206F),
               (0xFE00, 0xFE0F))


def warmup_glyphs() -> list[str]:
    """Symbols and emoji the UI shows (every locale string plus panel art), in first-seen order."""
    seen: dict[str, None] = {}
    texts = [GLYPH_WARMUP_EXTRA, *(v for loc in LOCALES.values() for v in loc.values())]
    for text in texts:
        for ch in text:
            o = ord(ch)
            if o >= 0x2000 and o != 0x20E3 and not any(a <= o <= b for a, b in _GLYPH_SKIP):
                seen.setdefault(ch, None)
    return list(seen)


def glyph_warmup_fonts(lang: str) -> list[tuple]:
    """The panel fonts that pay the fallback cost: the current language's family first."""
    family = {"ko": "Malgun Gothic", "en": "Segoe UI"}.get(lang, "Microsoft JhengHei")
    fonts = [(family, 10), (family, 9, "bold"), (family, 9, "normal"), (family, 10, "bold"),
             (family, 12, "bold"), (family, 8, "normal"), (family, 7, "bold"),
             ("Microsoft JhengHei UI", 10, "bold"), ("Microsoft JhengHei UI", 9, "bold"),
             ("Microsoft JhengHei UI", 9, "normal"), ("Microsoft JhengHei UI", 8, "normal"),
             ("Microsoft JhengHei UI", 8, "bold"), ("Microsoft JhengHei UI", 7, "bold")]
    return list(dict.fromkeys(fonts))
CHRISTMAS_V3_SHARE = 0.75    # of Christmas idle shows; the rest are the single-image poses
SEASONAL_POSE_S = 4.0
ANNIVERSARY_419_KIND = "calendar.anniversary.apink419"
ANNIVERSARY_SCENE_S = 9.0
TAP_REACTION_S = 1.4
HEAD_PAT_SHARE = 0.5     # a click in the top half of the window lands on the head: a pat
TAP_COOLDOWN_S = 1.5
FEED_REACTION_S = 2.8
SIGNATURE_RESERVE_S = 25.0    # no small action right before a signature move
SPECIAL_MIN_S = 2.4      # a special action plays whole passes, at least this long
DEBUG_SPECIAL_HOLD_S = 3600.0   # a debug-forced special loops until released

log = logging.getLogger(__name__)

MEMBERS = [
    ("chorong", "初瓏 (Chorong)", 0),
    ("bomi", "普美 (Bomi)", 1),
    ("eunji", "恩地 (Eunji)", 2),
    ("namjoo", "南珠 (Namjoo)", 3),
    ("hayoung", "夏榮 (Hayoung)", 4),
]
MEMBER_KEYS = [m[0] for m in MEMBERS]
_TITLE_NAMES = {  # every way a header may spell the speaker's name
    "chorong": ("初瓏", "朴初瓏", "Chorong", "Park Chorong", "초롱", "박초롱"),
    "bomi": ("普美", "尹普美", "Bomi", "Yoon Bomi", "보미", "윤보미"),
    "eunji": ("恩地", "鄭恩地", "Eunji", "Jeong Eunji", "은지", "정은지"),
    "namjoo": ("南珠", "金南珠", "Namjoo", "Kim Namjoo", "남주", "김남주"),
    "hayoung": ("夏榮", "吳夏榮", "Hayoung", "Oh Hayoung", "하영", "오하영"),
}


def bubble_title(header: str, sub_badge: str, speaker: str, lang: str) -> tuple[str, str]:
    """("✦ 朴初瓏", chips): title is just the speaker's full name; no "Apink" tag.

    Anything else the caller put in the header ("⏰ 貼心提醒", "🔔 來自 LINE") is kept
    as the first chip, minus the speaker's own name, the 🐼 marker and "Apink".
    """
    title = f"✦ {member_full_name(speaker, lang)}"
    rest = header or ""
    for name in sorted(_TITLE_NAMES.get(speaker, ()), key=len, reverse=True):
        rest = rest.replace(f"({name})", "").replace(name, "")
    rest = re.sub(r"\bApink\b", "", rest, flags=re.IGNORECASE).replace("🐼", "").replace("()", "")
    rest = " ".join(rest.split())
    if rest and any(ch.isalnum() for ch in rest):
        sub_badge = f"{rest}｜{sub_badge}" if sub_badge else rest
    return title, sub_badge
WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
IDLE_SLEEP_TIMEOUT_SEC = 180  # 3 minutes of OS idle -> sleep


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_system_idle_seconds() -> float:
    """Returns the number of seconds since the last user input across the entire OS."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0.0


@dataclasses.dataclass(frozen=True)
class FeedResult:
    """What one feed did. outcome: invalid | refused_full | disliked | favourite | normal.

    newly_unlocked is only True when the discovery was also saved (saved=True).
    """
    outcome: str
    drink_full: bool = False
    newly_unlocked: bool = False
    saved: bool = False


def _use_layered_surface(use_layered: bool | None = None) -> bool:
    """Return True when the main pet window should use Win32 UpdateLayeredWindow (ULW_ALPHA)."""
    if use_layered is not None:
        return bool(use_layered)
    if sys.platform != "win32":
        return False
    raw = os.environ.get("PANDA_DISABLE_ULW", "").strip().lower()
    return raw not in ("1", "true", "yes", "on")



def process_private_bytes() -> int | None:
    """Private (commit) bytes of this process on Windows; None elsewhere or on failure."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]

        counters = _PMC()
        counters.cb = ctypes.sizeof(_PMC)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return int(counters.PrivateUsage)
    except Exception:
        return None

class PandaPet:
    def __init__(self, data_dir: Path | None = None, *, use_layered: bool | None = None) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

        # settings = user preferences, runtime = stats (passion / feed count);
        # stored separately with atomic writes + .bak recovery.
        self.store = PersistenceService(data_dir or DATA_DIR)
        self._persist_ok = True
        self._persist_errors: list[tuple[str, str]] = []
        self.settings, self.runtime = self.load_settings()
        self.developer_mode = is_developer_mode(self.settings)
        normalize_food_log(self.runtime)
        self.food_panel = None
        self.settings_panel = None
        self.group_celebration: GroupCelebration | None = None
        self.mode = self.settings.get("mode", "auto")
        self.char_key = self.resolve_active_character()
        self._use_ulw = _use_layered_surface(use_layered)
        self.layered_surface: LayeredSpriteSurface | None = None
        self._ulw_fail_count: int = 0
        self._ulw_composed_cache: OrderedDict[tuple[int, int, int, int, int], tuple[Image.Image, weakref.ref]] = OrderedDict()

        initial_area = WindowsDesktopAdapter(fallback_bounds=lambda: WorkArea(
            0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())).work_area_for_point(200, 200)
        target_px = pet_display_px(self.settings.get("pet_size", "medium"), ui_scale(self.root), initial_area)
        self.sprites = SpriteLibrary(
            RES_ROOT,
            display_px=target_px,
            equalize=True,
            binary_alpha=not self._use_ulw,
            edge_refine=self._want_edge_refine(target_px),
        )
        # Stage 3: guest windows (cameo, celebrations, 419, dome preview) share the active ULW/ColorKey mode.
        self.guest_sprites = self.sprites
        self.frames: dict[str, list[tk.PhotoImage]] = {}
        self.flipped_walk_cache: dict[str, list[tk.PhotoImage]] = {}
        # (member, action, display_px, facing) -> ActionEntry, or None when not approved.
        # One byte-bounded LRU (was four unbounded dicts that grew to GBs at 192 DPI).
        self._action_lru = ActionFrameCache(action_cache_budget(target_px))
        # Bounded guest PhotoImages shared by celebrations (see GroupCelebration.photo_cache).
        self._celebration_photos: OrderedDict = OrderedDict()
        self._shown_action: str | None = None
        self._shown_member: str | None = None
        self._shown_facing: int = 1
        self._frame_pad = (0, 0, 0, 0)   # window margin (left, top, right, bottom) for large actions
        self.load_character_frames(self.char_key)

        self.width = self.frames["idle"][0].width()
        self.height = self.frames["idle"][0].height()
        self.birthday_dialog = None
        self.profile_card = None

        self.window = tk.Toplevel(self.root)
        if self._use_ulw:
            # Keep withdrawn until the first ULW frame is presented so startup never flashes #ff00fe.
            self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=BG)
        self.desktop = WindowsDesktopAdapter(fallback_bounds=lambda: WorkArea(
            0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight()))
        self.debug_panel = None
        self._debug_event_id = None
        self._debug_paused = False
        if not self._use_ulw:
            try:
                self.window.attributes("-transparentcolor", BG)
            except tk.TclError:
                pass

        self.canvas = tk.Canvas(
            self.window,
            width=self.width,
            height=self.height,
            bg=BG,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.image = self.canvas.create_image(0, 0, anchor="nw")

        area = self.desktop.work_area_for_point(200, 200)
        self.x, self.y = area.clamp(200, area.bottom - self.height, self.width, self.height)

        # State Coordinator owns "what the pet is doing"; ``self.state`` is a
        # sprite-level view of it (see the property below).
        # One clock for coordinator + calendar; the debug panel can shift it.
        self.clock = OffsetClock(SystemClock())
        self.coord = StateCoordinator(clock=self.clock, member=self.char_key)
        self.coord.subscribe(self._on_coord_event)
        self.speech = SpeechQueue(clock=self.clock)
        self._spoken_event_ids: set[int] = set()
        # Calendar handles birthdays / 419 / holidays / hourly chime. The
        # sedentary reminder stays in _tick_1s_body because it counts *active*
        # desk time (pauses when the user is away), so it is disabled here.
        self.calendar = CalendarScheduler(
            clock=self.clock,
            sedentary_interval_min=0,
            enable_hourly_chime=self.settings.get("hourly_chime", True),
            hourly_chime_range=hourly_range(self.settings),
        )
        bday = read_birthday(self.settings.get("user_birthday"))
        self.calendar.set_user_birthday(
            *(bday or (None, None)),
            nickname=self.settings.get("user_nickname") or DEFAULT_NICKNAME,
        )
        # Cameo: a guest member visits (L2, at most once per 30 min).
        self.cameo = CameoDirector(self.coord, clock=self.clock)
        self.coord.subscribe(self.cameo.on_coord_event)
        # Day the auto rota was last applied; _tick_1s_body rolls over at midnight.
        self._last_auto_date: datetime.date = self._auto_schedule_today()
        self.cameo_window: CameoActorWindow | None = None
        self._cameo_after: str | None = None
        self._cameo_phase: CameoPhase | None = None
        self._cameo_t0 = 0.0
        self.face_override: int | None = None  # host faces the guest during a cameo
        self.next_cameo_at = time.time() + random.uniform(*CAMEO_FIRST_DELAY_S)
        self.next_signature_at = time.time() + random.uniform(*SIGNATURE_INTERVAL_S)
        self.next_festival_at = 0.0
        self._last_signature: dict[str, str] = {}
        self.next_natural_at = time.time() + random.uniform(*NATURAL_INTERVAL_S)
        self._last_natural: dict[str, str] = {}
        self._next_tap_at = 0.0
        self._ny_countdown_year: int | None = None
        self._ny_announced_minutes: set[int] = set()
        self._ny_announced_secs: set[int] = set()
        self._ny_pending_clock_year: int | None = None
        self._new_year_celebrated_year: int | None = None
        self._new_year_celebrated = False
        self._last_festival_state: tuple[str | None, bool, str | None] | None = None

        self.frame_idx = 0
        self.direction = 1   # 1 = right, -1 = left
        self.walk_cycles = 0
        self.drag_start = None
        self.dragging = False
        self._press_root = (0, 0)
        self._drag_cursor_after: str | None = None
        self.last_user_activity = time.time()
        self.was_os_sleeping = False

        # Autonomous Roam
        self.next_roam_time = time.time() + random.uniform(12.0, 22.0)
        self.target_roam_x: int | None = None

        # Sedentary Reminder
        self.sedentary_active_sec = 0

        # Stats & Timers
        self.session_start_time = time.time()
        self.accumulated_companion_seconds = self.runtime.get("total_companion_seconds", 0)
        if self.accumulated_companion_seconds == 0 and self.runtime.get("feed_count", 0) > 0:
            self.accumulated_companion_seconds = self.runtime.get("feed_count", 0) * 120
            self.runtime["total_companion_seconds"] = self.accumulated_companion_seconds
        self.companion_start_time = self.session_start_time
        self._last_companion_save = time.time()
        self.feed_count = self.runtime.get("feed_count", 0)
        self.lang = self.settings.get("lang", "zh_TW")

        # Satiety (飽腹度 0~100, 2小時自然衰減10%, 純陪伴零懲罰), one value per member.
        # All five get hungry at the same rate while the app runs (the members off
        # stage too, see _decay_everyone); a restart continues from the saved values.
        migrate_shared_satiety(self.runtime, self.char_key)
        self.satiety = member_satiety(self.runtime, self.char_key)
        self.last_satiety_update = time.time()
        store_satiety(self.runtime, self.char_key, self.satiety, self.last_satiety_update)

        # Notifications, Bubble & Standby
        self.notif_monitor = WindowsNotificationMonitor()
        # Recent relayed notifications, RAM only (gone when the pet exits); Windows keeps its own.
        self.recent_notifications: deque[dict[str, str]] = deque(maxlen=RECENT_LIMIT)
        self.anniversary_scene = None
        self.new_year_clock = None
        self.active_bubble: KawaiiSpeechBubble | None = None
        self.status_card: PandaStatusCard | None = None
        self.profile_card = None
        self.notification_drawer = None
        self.pink_menu = None
        self.standby_overlay: PandaStandbyOverlay | None = None
        self._menu_active: bool = False
        self.member_double_clicks: dict[str, int] = {k: 0 for k in MEMBER_KEYS}

        # System Tray Integration (Thread-safe Tkinter callbacks, default action is wake & lift)
        icon_path = RES_ROOT / "work" / "foods" / "chicken_feet_64.png"
        self.tray = PandaSystemTray(
            icon_path=icon_path,
            on_wake_pet=lambda: self.root.after(0, self.show_from_tray),
            on_hide_pet=lambda: self.root.after(0, self.hide_to_tray),
            on_status_card=lambda: self.root.after(0, self.show_status_card),
            on_exit=lambda: self.root.after(0, self.close),
            lang=self.lang,
        )
        self.tray.start()

        # Global Hotkey for Standby Screensaver
        self.hotkey_str = self.settings.get("standby_hotkey", "Ctrl+Shift+S")
        self.hotkey_manager = GlobalHotkeyManager(
            self.hotkey_str,
            on_trigger=lambda: self.root.after(0, self.open_standby_screen),
        )
        self.hotkey_manager.start()

        if self._use_ulw:
            try:
                self.layered_surface = LayeredSpriteSurface(
                    self.window,
                    x=self.x,
                    y=self.y,
                    opacity=1.0,
                    input_policy="interactive",
                    noactivate=True,
                    topmost=True,
                )
            except Exception:
                log.exception("LayeredSpriteSurface init failed; falling back to ColorKey")
                self._use_ulw = False
                self.layered_surface = None
                self.sprites.binary_alpha = True
                if hasattr(self.sprites, "set_edge_refine"):
                    self.sprites.set_edge_refine(False)
                self.sprites._members.clear()
                self.guest_sprites = self.sprites
                self.load_character_frames(self.char_key)
                try:
                    self.window.attributes("-transparentcolor", BG)
                except tk.TclError:
                    pass
                self.window.deiconify()
        self.window.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        if self.layered_surface is not None and not self.layered_surface.closed:
            self._present_layered_pet()
            self.window.deiconify()
            self.layered_surface.set_visibility(True)
        else:
            self.window.update_idletasks()

        self.build_menu()

        for bind_target in (self.canvas, self.window):
            bind_target.bind("<ButtonPress-1>", self.drag_begin)
            bind_target.bind("<B1-Motion>", self.drag_move)
            bind_target.bind("<ButtonRelease-1>", self.drag_end)
            bind_target.bind("<Double-Button-1>", lambda _: self.on_double_click())
            bind_target.bind("<Button-3>", self.show_menu)
            bind_target.bind("<Enter>", self._on_enter_pet)
            bind_target.bind("<Leave>", self._on_leave_pet)
        self.window.bind("<Control-Shift-Key-S>", lambda _: self.open_standby_screen())
        self.window.bind("<Control-Shift-Key-s>", lambda _: self.open_standby_screen())
        self.window.bind("<F9>", lambda _: self.open_standby_screen())
        if self.developer_mode:
            self.window.bind("<F12>", lambda _: self.open_debug_panel())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.apply_mouse_cursor()
        self.window.bind("<Map>", lambda _e: self.apply_mouse_cursor(), add="+")

        self._last_festival_state = self._festival_state_key()
        self._festival_preview_active = False
        self._standby_warmup = StandbyWarmupManager()
        from app.desktop_warmup import DesktopWarmupManager
        self._desktop_warmup = DesktopWarmupManager()
        self._loop_after: dict[str, str] = {}  # periodic loops, cancelled on close
        self._after_widgets: dict[str, object] = {}  # owning widget per tracked key for clean after_cancel
        self.animate()
        self._loop_after["desktop_warmup"] = self.window.after(2000, self._start_desktop_warmup)
        self._loop_after["tick_1s"] = self.window.after(1000, self.tick_1s)
        self._loop_after["tick_3s"] = self.window.after(3000, self.tick_3s)
        self._loop_after["festival_welcome"] = self.window.after(1400, self._maybe_festival_welcome)
        self._loop_after["standby_warmup"] = self.window.after(2000, self._start_standby_warmup)
        self._loop_after["glyph_warmup"] = self.window.after(GLYPH_WARMUP_DELAY_MS, self._glyph_warmup_step)
        if not self.settings.get("user_birthday") and not self.settings.get("onboarding_prompted"):
            self._loop_after["onboarding"] = self.window.after(1500, self._check_first_run_onboarding)

    # ── State coordination ───────────────────────────────────────────────
    @property
    def state(self) -> str:
        """Sprite set currently shown: one of STATES."""
        return SPRITE_FOR_STATE.get(self.coord.actor_state, "idle")

    @state.setter
    def state(self, value: str) -> None:
        self.coord.set_ambient(AMBIENT_FOR_SPRITE.get(value, ActorState.IDLE))

    def _on_coord_event(self, ev: CoordinatorEvent) -> None:
        if ev.type is CoordinatorEventType.STATE_CHANGED:
            self.frame_idx = 0
            self.walk_cycles = 0
            self._walk_subpx = 0.0
            if ev.snapshot.actor_state is ActorState.WALK:
                # Roaming horizontal locomotion must strictly use real walking gaits (walk_01..04)
                self.current_walk_action = "walk"
            else:
                self.target_roam_x = None
        elif (
            ev.type is CoordinatorEventType.STARTED
            and ev.request is not None
            and ev.request.source.startswith("calendar")
            and ev.event_id not in self._spoken_event_ids
        ):
            # A preempted+requeued event restarts with the same id; its bubble
            # was already requeued by the speech queue, so speak only once.
            self._spoken_event_ids.add(ev.event_id)
            self._show_event_speech(ev.request)
            if ev.request.kind == ANNIVERSARY_419_KIND and self.settings.get("festival_auto_enabled", True):
                self._open_anniversary_scene()

    def _set_ambient(self, sprite: str) -> None:
        self.coord.set_ambient(AMBIENT_FOR_SPRITE.get(sprite, ActorState.IDLE))

    def load_settings(self) -> tuple[dict, dict]:
        """Load (settings, runtime); migrates the legacy mixed settings.json.

        On failure (I/O error, newer schema) we run on defaults and stop
        saving, so a file we cannot understand is never overwritten.
        """
        try:
            settings, runtime = self.store.load()
        except Exception as error:
            log.exception("loading settings failed; using defaults, saving disabled")
            from app.storage.settings import DEFAULT_RUNTIME, DEFAULT_SETTINGS
            self._persist_ok = False
            self._persist_errors.append(("persist_load_failed", str(error)))
            return dict(DEFAULT_SETTINGS), dict(DEFAULT_RUNTIME)
        # A one-time legacy migration or clean backup recovery is logged rather than alarming users.
        for e in self.store.recovery_events:
            if not e.startswith("Migrated legacy"):
                log.warning("Storage recovery note: %s", e)
        return settings, runtime

    def get_total_companion_seconds(self) -> int:
        session_elapsed = int(time.time() - getattr(self, "session_start_time", time.time()))
        return getattr(self, "accumulated_companion_seconds", 0) + max(0, session_elapsed)

    def get_companion_minutes(self) -> int:
        return max(1, self.get_total_companion_seconds() // 60)

    def save_settings(self) -> bool:
        """True only when both files were written."""
        if getattr(self, "_batch_depth", 0) > 0:
            self._batch_dirty_save = True
            return True
        if not self._persist_ok:
            return False
        try:
            self.runtime["total_companion_seconds"] = self.get_total_companion_seconds()
            self.store.save(self.settings, self.runtime)
        except Exception as error:
            log.exception("saving settings failed")
            self._persist_errors.append(("persist_save_failed", str(error)))
            return False
        return True

    def _report_persist_errors(self) -> None:
        """Surface storage recovery / failures once as a system bubble."""
        if not self._persist_errors:
            return
        msg = "\n".join(t(key, self.lang, error=error) for key, error in self._persist_errors[-3:])
        self._persist_errors.clear()
        self._toast(msg, header=t("persist_header", self.lang), duration_ms=8000,
                    priority=Priority.SYSTEM, kind="storage.error")

    _PANEL_ATTRS = (
        "status_card", "profile_card", "birthday_dialog", "fortune_dialog",
        "food_panel", "settings_panel", "notification_drawer", "pink_menu",
    )

    def _has_active_subpanel(self) -> bool:
        for attr in self._PANEL_ATTRS:
            panel = getattr(self, attr, None)
            if panel is not None:
                win = getattr(panel, "window", None) or getattr(panel, "win", None)
                if win is not None:
                    try:
                        if win.winfo_exists() and win.winfo_viewable():
                            return True
                    except Exception:
                        pass
        return False

    def _lift_active_panels(self) -> None:
        """Keep user-opened interactive panels above bubbles and celebration guests."""
        for attr in self._PANEL_ATTRS:
            panel = getattr(self, attr, None)
            if panel is None:
                continue
            win = getattr(panel, "window", None) or getattr(panel, "win", None)
            if win is not None:
                try:
                    if win.winfo_exists() and win.winfo_viewable():
                        win.lift()
                except tk.TclError:
                    pass

    def ensure_topmost(self) -> None:
        """Maintain topmost without requesting keyboard focus."""
        if is_workstation_locked() is True:
            return
        if getattr(self, "_menu_active", False):
            return
        if hasattr(self, "menu") and self.menu.winfo_ismapped():
            return
        if not self.window.winfo_exists() or not self.window.winfo_viewable():
            return
        try:
            if self._has_active_subpanel():
                if self.window.tk.getboolean(self.window.attributes("-topmost")):
                    return
                # Keep the pet above normal apps, with its cards above the pet.
                self.window.attributes("-topmost", True)
                self._lift_bubble()
                return
            surf = getattr(self, "layered_surface", None)
            if surf is not None and not surf.closed:
                if surf.visible:
                    surf.set_visibility(True)
                return
            hwnd = self._pet_hwnd()
            self.desktop.set_noactivate(hwnd)
            self.desktop.show_without_activation(hwnd)
        except (tk.TclError, ValueError, OSError):
            log.exception("Cannot maintain pet window style")

    def _schedule_once_after(self, key: str, widget, delay_ms: int | None, callback) -> None:
        """Schedule a replaceable one-shot Tk callback, cancelled on close when tracked."""
        if getattr(self, "_closing", False):
            return
        afters = getattr(self, "_loop_after", None)
        widgets = getattr(self, "_after_widgets", None)
        if isinstance(afters, dict):
            old = afters.pop(key, None)
            old_widget = widgets.pop(key, self.window) if isinstance(widgets, dict) else widget
            if old is not None:
                try:
                    old_widget.after_cancel(old)
                except Exception:
                    pass
        aid = widget.after_idle(callback) if delay_ms is None else widget.after(delay_ms, callback)
        if isinstance(afters, dict) and aid is not None:
            afters[key] = aid
            if isinstance(widgets, dict):
                widgets[key] = widget

    def _lift_bubble(self) -> None:
        """Keep active panels above pet/celebration guests, and short-lived speech bubble on top."""
        if getattr(self, "_closing", False):
            return
        if hasattr(self, "_lift_active_panels"):
            self._lift_active_panels()
        bubble = getattr(self, "active_bubble", None)
        win = getattr(bubble, "window", None)
        try:
            if win is not None and win.winfo_exists():
                win.lift()
        except tk.TclError:
            pass

    def _pet_monitor_bounds(self):
        """Full bounds (incl. taskbar) of the monitor the pet is on; None = primary."""
        lookup = getattr(self.desktop, "monitor_bounds_for_point", None)
        if lookup is None:
            return None
        try:
            return lookup(self.x + self.width // 2, self.y + self.height // 2)
        except Exception:
            log.exception("monitor lookup failed; standby on primary screen")
            return None

    def _other_monitor_bounds(self, mine) -> tuple:
        """Full bounds of every other monitor (standby covers them too); () when unknown."""
        lookup = getattr(self.desktop, "enumerate_monitor_bounds", None)
        if mine is None or lookup is None:
            return ()
        try:
            return tuple(b for b in lookup() if b != mine)
        except Exception:
            log.exception("monitor enumeration failed; standby covers one screen")
            return ()

    def _pet_hwnd(self) -> int:
        surf = getattr(self, "layered_surface", None)
        if surf is not None and not surf.closed:
            return surf.hwnd
        frame = self.window.wm_frame()
        return int(frame, 16) if frame.startswith("0x") else int(frame)

    def _pet_is_visible(self) -> bool:
        surf = getattr(self, "layered_surface", None)
        if surf is not None and not surf.closed:
            return bool(surf.visible and self.window.winfo_viewable())
        return bool(self.window.winfo_viewable())

    def _set_pet_visibility(self, visible: bool) -> None:
        surf = getattr(self, "layered_surface", None)
        if visible:
            self.window.deiconify()
            if surf is not None and not surf.closed:
                surf.set_visibility(True)
                self._present_layered_pet()
        else:
            if surf is not None and not surf.closed:
                surf.set_visibility(False)
            self.window.withdraw()

    def _fallback_to_colorkey(self) -> None:
        """Runtime fallback from ULW to ColorKey after consecutive UpdateLayeredWindow failures."""
        surf = getattr(self, "layered_surface", None)
        self.layered_surface = None
        self._use_ulw = False
        self._ulw_fail_count = 0
        if isinstance(getattr(self, "_ulw_composed_cache", None), OrderedDict):
            self._ulw_composed_cache.clear()
        else:
            self._ulw_composed_cache = OrderedDict()
        if surf is not None:
            try:
                surf.close(clear_exstyle=True)
            except Exception:
                log.debug("layered_surface close on fallback failed", exc_info=True)
        self.sprites.binary_alpha = True
        if hasattr(self.sprites, "set_edge_refine"):
            self.sprites.set_edge_refine(False)
        self.sprites._members.clear()
        self.sprites._directional_placement.clear()
        self.guest_sprites = self.sprites
        self.flipped_walk_cache.clear()
        self._actions().clear()
        self._actions().set_budget(action_cache_budget(self.sprites.display_px))
        if getattr(self, "_celebration_photos", None) is not None:
            self._celebration_photos.clear()
        self.load_character_frames(self.char_key)
        try:
            self.window.attributes("-transparentcolor", BG)
        except tk.TclError:
            pass
        try:
            self.canvas.itemconfigure(self.image, image=self.current_frame())
        except tk.TclError:
            pass

    def _present_layered_pet(self, pil_frame: Image.Image | None = None,
                             image_xy: tuple[int, int] | None = None) -> None:
        surf = getattr(self, "layered_surface", None)
        if surf is None or surf.closed:
            return
        raw_frame = pil_frame if pil_frame is not None else self.current_pil_frame()
        if raw_frame is None:
            return
        pad = getattr(self, "_frame_pad", (0, 0, 0, 0))
        w = max(1, self.width + pad[0] + pad[2])
        h = max(1, self.height + pad[1] + pad[3])
        wx = int(self.x - pad[0])
        wy = int(self.y - pad[1])
        ix, iy = image_xy if image_xy is not None else getattr(self, "_last_image_xy", (0, 0))
        ix, iy = int(ix), int(iy)
        cache_key = (id(raw_frame), ix, iy, w, h)
        cache = getattr(self, "_ulw_composed_cache", None)
        if not isinstance(cache, OrderedDict):
            cache = OrderedDict()
            self._ulw_composed_cache = cache
        cached = cache.get(cache_key)
        if cached is not None and cached[1]() is raw_frame:
            cache.move_to_end(cache_key)
            frame_im = cached[0]
        else:
            if (ix, iy) != (0, 0) or raw_frame.size != (w, h):
                box_im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                box_im.paste(raw_frame, (ix, iy))
            else:
                box_im = raw_frame
            # Premultiplied BGRA lives only in this byte-bounded cache; it is never attached
            # to the cached action frame (that kept a third copy alive for every frame).
            try:
                frame_im = PremultipliedFrame.from_image(box_im)
            except Exception:
                frame_im = box_im
            # 2026-11-22: a weak reference only checks identity; a strong one kept every
            # raw action frame alive after the action cache had evicted it (~14 MB).
            cache[cache_key] = (frame_im, weakref.ref(raw_frame))
            for dead in [k for k, v in cache.items() if v[1]() is None]:
                del cache[dead]
            limit = ulw_composed_budget(getattr(self.sprites, "display_px", 192))
            total = sum(getattr(v[0], "nbytes", 0) for v in cache.values())
            while len(cache) > 2 and total > limit:
                _k, (old, _raw) = cache.popitem(last=False)
                total -= getattr(old, "nbytes", 0)
        try:
            surf.present(frame_im, x=wx, y=wy)
            self._last_ulw_frame_id = id(raw_frame)
            if not surf.visible and self.window.state() != "withdrawn":
                surf.set_visibility(True)
            self._ulw_fail_count = 0
        except OSError:
            self._ulw_fail_count = getattr(self, "_ulw_fail_count", 0) + 1
            log.warning("ULW present failed (%d/3)", self._ulw_fail_count, exc_info=True)
            if self._ulw_fail_count >= 3:
                log.error("3 consecutive ULW failures; falling back to ColorKey")
                self._fallback_to_colorkey()

    def _place_pet(self) -> None:
        # The window may be larger than the base box while a large action plays.
        wx, wy = int(self.x - self._frame_pad[0]), int(self.y - self._frame_pad[1])
        surf = getattr(self, "layered_surface", None)
        if surf is not None and not surf.closed:
            surf.move(wx, wy)
            # Keep Tk's internal winfo_x/y/rootx/rooty synchronized for child panels and menus,
            # and inform the desktop adapter (also keeps injected test backends synchronized).
            if not (getattr(self, "_menu_active", False) or self._has_active_subpanel()):
                self.desktop.position_without_activation(self._pet_hwnd(), wx, wy)
            self.window.geometry(f"+{wx}+{wy}")
            return
        if getattr(self, "_menu_active", False) or self._has_active_subpanel():
            self.window.geometry(f"+{wx}+{wy}")
            return
        if not self.desktop.position_without_activation(self._pet_hwnd(), wx, wy):
            # Tk geometry fallback; negative coordinates are absolute using '+-'.
            self.window.geometry(f"+{wx}+{wy}")

    def memory_snapshot(self) -> dict:
        """Resident image caches in MB (debug HUD; the bounded budgets are in app/action_cache.py)."""
        mb = 1024 * 1024
        out = {"actions": self._actions().stats()}
        composed = getattr(self, "_ulw_composed_cache", None) or {}
        out["ulw_composed_mb"] = round(sum(getattr(v[0], "nbytes", 0) for v in composed.values()) / mb, 1)
        out["ulw_composed_entries"] = len(composed)
        try:
            from app.standby import PREPARED_IMAGES
            out["prepared_mb"] = round(PREPARED_IMAGES.size_bytes / mb, 1)
        except Exception:
            pass
        private = process_private_bytes()
        if private is not None:
            out["process_private_mb"] = round(private / mb, 1)
        return out

    def open_debug_panel(self) -> None:
        from app.tools.debug_panel import DebugBindings, DeveloperDebugPanel
        if self.debug_panel is not None and not self.debug_panel._closed:
            self.debug_panel.window.lift()
            return
        def snapshot():
            state = self.coord.snapshot()
            return {"member": self.char_key, "mode": state.mode.value,
                    "state": state.actor_state.value, "action": state.action,
                    "priority": int(state.priority),
                    "active": ({"id": state.active.event_id,"kind": state.active.request.kind}
                               if state.active else None), "pending_id": state.pending_id,
                    "queue": state.queue, "frame": self.frame_idx,
                    "position": (self.x,self.y), "wall_time": self.clock.now(),
                    "offset_seconds": self.clock.offset_seconds,
                    "paused": self._debug_paused,
                    "cache_bytes": self.sprites.cache.cache_size_bytes if self.sprites.cache else None}
        def extra_snapshot():
            return {"pet_size": self.settings.get("pet_size"),
                    "display_px": getattr(self.sprites, "display_px", None),
                    "ui_scale": round(ui_scale(self.window), 3),
                    "box": {"width": self.width, "height": self.height},
                    "canvas": {"width": self.canvas.winfo_width(), "height": self.canvas.winfo_height()},
                    "window": self.window.winfo_geometry(),
                    "frame_pad": self._frame_pad,
                    "shown_action": self._shown_action,
                    "bubble_theme": self.settings.get("bubble_theme", "auto"),
                    "satiety": round(self._current_satiety(), 1),
                    "memory": self.memory_snapshot(),
                    "data_dir": str(self.store.base_dir)}
        def after_time_change():
            try:
                self._sync_festival_state()
            except Exception:
                log.exception("debug time change: festival sync failed")
        def shift(hours):
            self.clock.offset_seconds += hours * 3600
            after_time_change()
        def reset():
            self.clock.offset_seconds = 0
            after_time_change()
        def set_time(target):
            self.clock.offset_seconds = (target - self.clock.base.now()).total_seconds()
            after_time_change()
        bindings = DebugBindings(snapshot,tuple(MEMBER_KEYS),self.switch_character,
                                 lambda:tuple(sorted(self.frames)),self._debug_play,
                                 lambda paused:setattr(self,"_debug_paused",paused),
                                 self._debug_step,shift,reset,self._debug_release,
                                 lang=self.lang,special_actions=self._debug_special_actions,
                                 set_time=set_time,extra_snapshot=extra_snapshot)
        self.debug_panel = DeveloperDebugPanel(self.root,bindings)
        PandaPet._apply_cursor_to_panel(self, self.debug_panel)
        try:
            self.debug_panel.place_in(self.desktop.work_area_for_point(self.x + self.width // 2, self.y))
        except Exception:
            log.exception("debug panel placement failed")

    def _debug_special_actions(self) -> tuple[str, ...]:
        """This member's approved special and festival actions, for forced playback."""
        festivals = available_actions(self.sprites, self.char_key, tuple(f.action for f in MAJOR_FESTIVALS))
        return tuple(dict.fromkeys((*self.available_special_actions(), *festivals)))

    def _debug_play(self, action: str) -> None:
        if action in self.frames:
            self._debug_release()
            result = self.coord.submit(EventRequest(kind="debug.force",priority=Priority.USER,
                                      state=ActorState(action),action=action,
                                      duration_s=None,source="debug"))
            if not result.accepted:
                raise RuntimeError(f"Action rejected: {result.reason}")
            self._debug_event_id = result.event_id
            self.frame_idx = 0
            return
        if action not in self._debug_special_actions():
            raise ValueError("Only loaded approved base, special or festival actions may be forced")
        self._debug_release()
        if not self.trigger_special_action(action, kind="debug.force", hold_s=DEBUG_SPECIAL_HOLD_S):
            raise RuntimeError(f"Action rejected: {action}")
        active = self.coord.snapshot().active
        self._debug_event_id = active.event_id if active is not None else None
        self.frame_idx = 0

    def _debug_step(self, delta: int) -> None:
        self._debug_paused = True
        self.frame_idx = (self.frame_idx + delta) % self.cycle_length()
        self._show_canvas_frame()
        self._present_layered_pet()

    def _debug_release(self) -> None:
        self._debug_paused = False
        if self._debug_event_id is not None:
            self.coord.cancel(self._debug_event_id,"debug_released")
            self._debug_event_id = None

    def _auto_schedule_today(self) -> datetime.date:
        """Today for the rota: the shared (debug-shiftable) clock once it exists."""
        clock = getattr(self, "clock", None)
        if clock is None:
            clock = getattr(getattr(self, "calendar", None), "clock", None)
        if clock is not None:
            return clock.now().date()
        return datetime.date.today()   # __init__ resolves the member before the clock exists

    def get_auto_character(self) -> str:
        today = PandaPet._auto_schedule_today(self)
        weekday = today.weekday()
        if weekday < 5:
            return MEMBER_KEYS[weekday]
        rng = random.Random(str(today))
        return rng.choice(MEMBER_KEYS)

    def resolve_active_character(self) -> str:
        if self.mode == "manual":
            manual = self.settings.get("manual_character", "chorong")
            if manual in MEMBER_KEYS:
                return manual
        return self.get_auto_character()

    def get_active_name(self) -> str:
        return get_member_display_name(self.char_key, self.lang)

    def get_character_dir(self, char_key: str) -> Path:
        char_dir = CHARACTERS_DIR / char_key
        if resource_exists(char_dir / "manifest.json", root=RES_ROOT):
            return char_dir
        return RES_ROOT / "work" / "rongdoong_processed_v2"

    def get_flipped_walk_frames(self, char_key: str, action: str = "walk") -> list[tk.PhotoImage]:
        cache_key = f"{char_key}:{action}"
        if cache_key not in self.flipped_walk_cache:
            frames = self.sprites.load_member(char_key, self.root).flipped(action)
            self.flipped_walk_cache[cache_key] = frames
            if action == "walk":
                self.flipped_walk_cache[char_key] = frames
        return self.flipped_walk_cache[cache_key]

    def load_character_frames(self, char_key: str) -> None:
        """Approved registry sprites (legacy manifest fallback), see app/sprites.py."""
        self.frames = self.sprites.load_member(char_key, self.root).frames
        self.char_key = char_key
        if getattr(self, "_desktop_warmup", None) is not None:
            self._schedule_standby_warmup()

    def switch_character(self, char_key: str, mode: str = "manual") -> None:
        if char_key != self.char_key:
            self._swap_satiety(char_key)
        self.mode = mode
        self.settings["mode"] = mode
        if mode == "manual":
            self.settings["manual_character"] = char_key
        self.save_settings()

        self.load_character_frames(char_key)
        if mode == "auto":   # marked once the member is really on stage; a failed load retries
            self._last_auto_date = PandaPet._auto_schedule_today(self)
        self.coord.set_member(char_key)
        if getattr(self, "_festival_preview_active", False) and hasattr(self, "cancel_festival_preview"):
            self.cancel_festival_preview()
        elif hasattr(self, "_close_group_celebration"):
            self._close_group_celebration()
        self.build_menu()
        self.frame_idx = 0
        self._refresh_visual_appearance()
        self._last_festival_state = self._festival_state_key()
        self._toast(t("char_switched", self.lang, name=self.get_active_name()), duration_ms=2500)
        self._refresh_status_card()
        self._refresh_birthday_dialog()
        self._refresh_fortune_dialog()
        self._refresh_profile_card()
        self._refresh_food_panel()
        self._refresh_settings_panel()
        self._refresh_notification_drawer()

    def _decay_everyone(self, now: float) -> None:
        """Apply the decay since the last update to all five, not only the member on stage.

        Off-stage members used to stay full until their turn, so after a week of one
        member on duty the other four still showed 100 %.
        """
        drop = max(0.0, now - getattr(self, "last_satiety_update", now)) / SATIETY_DECAY_SECONDS_PER_PERCENT
        for member in MEMBER_KEYS:
            if member != self.char_key:
                store_satiety(self.runtime, member, member_satiety(self.runtime, member) - drop, now)
        self.satiety = max(0.0, self.satiety - drop)
        self.last_satiety_update = now
        store_satiety(self.runtime, self.char_key, self.satiety, now)

    def _swap_satiety(self, new_member: str) -> None:
        """Everyone takes the decay so far; then the arriving member resumes her value."""
        now = time.time()
        self._decay_everyone(now)
        self.satiety = member_satiety(self.runtime, new_member)
        self.last_satiety_update = now
        store_satiety(self.runtime, new_member, self.satiety, now)

    def _refresh_status_card(self) -> None:
        """Live-refresh the status card if it is open."""
        if not self.status_card:
            return
        try:
            if self.status_card.window.winfo_exists():
                self.status_card.refresh(
                    char_key=self.char_key,
                    char_name=self.get_active_name(),
                    badge_desc=str(get_member_badge(self.char_key, self.lang)),
                    passion_points=self.runtime.get("cheer_passion", 0),
                    companion_start_time=self.companion_start_time,
                    feed_count=self.feed_count,
                    lang=self.lang,
                    total_companion_seconds=self.get_total_companion_seconds(),
                    satiety=self.satiety,
                )
            else:
                self.status_card = None
        except Exception:
            log.exception("status card refresh failed")
            self.status_card = None

    def _refresh_birthday_dialog(self) -> None:
        """Live-refresh birthday dialog if open."""
        if not getattr(self, "birthday_dialog", None):
            return
        try:
            if self.birthday_dialog.win.winfo_exists():
                self.birthday_dialog.refresh_theme(self.char_key, self.lang)
                PandaPet._apply_cursor_to_panel(self, self.birthday_dialog)
            else:
                self.birthday_dialog = None
        except Exception:
            log.exception("birthday dialog refresh failed")
            self.birthday_dialog = None

    def _refresh_fortune_dialog(self) -> None:
        """Live-refresh Eunji Fortune Studio popup language if open."""
        dlg = getattr(self, "fortune_dialog", None)
        if not dlg:
            return
        try:
            if dlg.win.winfo_exists():
                dlg.set_language(self.lang)
                PandaPet._apply_cursor_to_panel(self, dlg)
            else:
                self.fortune_dialog = None
        except Exception:
            log.exception("fortune dialog refresh failed")
            self.fortune_dialog = None

    def _refresh_profile_card(self) -> None:
        """Live-refresh member profile card if open."""
        if not getattr(self, "profile_card", None):
            return
        try:
            if self.profile_card.win.winfo_exists():
                self.profile_card.lang = self.lang
                if self.char_key in self.profile_card.members:
                    self.profile_card.current_idx = self.profile_card.members.index(self.char_key)
                self.profile_card.render_current()
                self._on_profile_context_changed()   # the page may have changed under a greeting
            else:
                self.profile_card = None
        except Exception:
            log.exception("profile card refresh failed")
            self.profile_card = None

    def switch_to_auto_schedule(self) -> None:
        self.mode = "auto"
        self.settings["mode"] = "auto"
        self.save_settings()
        char_key = self.get_auto_character()
        self.switch_character(char_key, mode="auto")

    def _auto_rollover_blocked(self) -> bool:
        """Swapping the member now would break a scene: standby, cameo, drag, festival."""
        coord = getattr(self, "coord", None)
        return bool(
            getattr(self, "standby_overlay", None) is not None
            or getattr(self, "_standby_resume_pending", False)
            or getattr(self, "_desktop_was_locked", False)
            or getattr(self, "dragging", False)
            or (coord is not None and coord.mode is not GlobalMode.NORMAL)
            or getattr(self, "cameo_window", None) is not None
            or getattr(self, "group_celebration", None) is not None
            or getattr(self, "_festival_preview_active", False)
        )

    def _check_auto_schedule_rollover(self) -> bool:
        """Midnight in auto mode: hand over to the new day's member. True if switched.

        Deferred (date not marked) while a scene is up, so it completes on the
        first plain desktop tick afterwards. Manual mode is never touched.
        """
        if getattr(self, "mode", "auto") != "auto":
            return False
        today = PandaPet._auto_schedule_today(self)
        if getattr(self, "_last_auto_date", None) == today:
            return False
        if PandaPet._auto_rollover_blocked(self):
            return False
        target = self.get_auto_character()
        if target != self.char_key:
            self.switch_character(target, mode="auto")   # also marks _last_auto_date
            return True
        self._last_auto_date = today
        self.build_menu()   # the menu's weekday label still names yesterday
        return False

    def is_autostart_enabled(self) -> bool:
        return VBS_PATH.is_file()

    def toggle_autostart(self) -> None:
        if self.is_autostart_enabled():
            try:
                VBS_PATH.unlink()
            except Exception:
                pass
        else:
            try:
                STARTUP_DIR.mkdir(parents=True, exist_ok=True)
                # Packaged build: relaunch this exe. From source: the compiled exe if
                # one was built, else pythonw.
                exe_path = ROOT / "dist" / "PandaDesktopPet" / "PandaDesktopPet.exe"
                if getattr(sys, "frozen", False):
                    target_cmd = f'"{sys.executable}"'
                elif exe_path.exists():
                    target_cmd = f'"{exe_path}"'
                else:
                    pythonw = Path(sys.executable).with_name("pythonw.exe")
                    target_cmd = f'"{pythonw if pythonw.is_file() else Path(sys.executable)}" -B -X utf8 "{ROOT}\\app\\main.py"'

                escaped_cmd = target_cmd.replace('"', '""')
                vbs_code = (
                    'Set WshShell = CreateObject("WScript.Shell")\r\n'
                    f'WshShell.CurrentDirectory = "{ROOT}"\r\n'
                    f'WshShell.Run "{escaped_cmd}", 0, False\r\n'
                )
                VBS_PATH.write_text(vbs_code, encoding="utf-16", newline="")
            except Exception:
                pass
        self.build_menu()

    def _toast(
        self,
        msg: str,
        duration_ms: int = 4200,
        icon_path: Path | None = None,
        header: str = "",
        sub_badge: str = "",
        badge_text: str = "",
        priority: Priority = Priority.USER,
        kind: str = "",
        anchor: tuple[int, int] | None = None,
        speaker: str | None = None,
        anchor_size: tuple[int, int] | None = None,
        origin: str = "pet",
    ) -> bool:
        """Offer a speech bubble to the priority queue; returns True if shown now.

        USER bubbles replace whatever is showing; SYSTEM bubbles (notifications,
        reminders) wait their turn instead of overwriting each other; lower
        priority chatter is dropped when the stage is busy.
        """
        if getattr(self, "_batch_depth", 0) > 0:
            self._batch_last_toast = (
                (msg,),
                {
                    "duration_ms": duration_ms, "icon_path": icon_path, "header": header,
                    "sub_badge": sub_badge, "badge_text": badge_text, "priority": priority,
                    "kind": kind, "anchor": anchor, "speaker": speaker,
                    "anchor_size": anchor_size, "origin": origin,
                },
            )
            return True
        req = SpeechRequest(
            text=msg,
            priority=priority,
            duration_ms=duration_ms,
            header=header,
            sub_badge=sub_badge,
            badge_text=badge_text,
            icon_path=str(icon_path) if icon_path else None,
            kind=kind,
            anchor=anchor,
            speaker=speaker,
            anchor_size=anchor_size,
            origin=origin,
        )
        if self.speech.offer(req) is not SpeechDecision.SHOW:
            return False
        self._render_bubble(req)
        return True

    def _render_bubble(self, req: SpeechRequest) -> None:
        """Displays a cute speech bubble above the pet, clamped to screen bounds."""
        self._close_bubble_window()
        msg, duration_ms, header = req.text, req.duration_ms, req.header
        sub_badge, badge_text = req.sub_badge, req.badge_text
        icon_path = Path(req.icon_path) if req.icon_path else None
        at_card = req.origin == "profile_card"

        # A card greeting is shown at the card: the pet is not called out or stopped.
        # If pet was hidden/withdrawn in tray, deiconify it so bubble is never orphaned!
        # Never deiconify while the 419 anniversary group photo or dome desktop preview
        # is standing in for the pet (or while standby covers the screen).
        pet_visible = self._pet_is_visible() if hasattr(self, "_pet_is_visible") else bool(self.window.winfo_viewable())
        if (
            not at_card
            and not pet_visible
            and getattr(self, "anniversary_scene", None) is None
            and getattr(self, "dome_preview", None) is None
            and getattr(self, "standby_overlay", None) is None
        ):
            if hasattr(self, "_set_pet_visibility"):
                self._set_pet_visibility(True)
            else:
                self.window.deiconify()
            if hasattr(self, "tray") and self.tray:
                self.tray.set_visible_state(True)

        # Halt roaming / walking immediately so the pet does not walk away while speaking!
        if not at_card and self.coord.snapshot().ambient_state is ActorState.WALK:
            self._set_ambient("idle")
            self.target_roam_x = None

        self.ensure_topmost()

        # Title is only the speaking member's name; whatever the caller put in
        # the header (e.g. "⏰ 貼心提醒", "🔔 來自 LINE") becomes the first chip.
        speaker = req.speaker or self.char_key
        header, sub_badge = bubble_title(header, sub_badge, speaker, self.lang)
        if not icon_path:
            avatar_path = RES_ROOT / "work" / "characters" / speaker / "idle_01.png"
            if resource_exists(avatar_path, root=RES_ROOT):
                icon_path = avatar_path
        cur_theme_mode = self.settings.get("bubble_theme", "auto")
        bubble_theme = get_theme_for_member(speaker, cur_theme_mode)
        size = req.anchor_size
        target_w, target_h = size if size and size[0] > 0 and size[1] > 0 else (self.width, self.height)
        is_relay = req.kind == "notify.relay"
        bubble = KawaiiSpeechBubble(
            parent=self.window,
            target_x=req.anchor[0] if req.anchor else self.x,
            target_y=req.anchor[1] if req.anchor else self.y,
            sprite_w=target_w,
            sprite_h=target_h,
            header=header,
            sub_badge=sub_badge,
            message=msg,
            badge_text=badge_text,
            icon_path=icon_path,
            duration_ms=duration_ms,
            theme=bubble_theme,
            text_size=self.settings.get("text_size", "medium"),
            notify_style=self.settings.get("notify_bubble_style", "banner") if is_relay else "standard",
            notify_tag=t("notify_sticky_tag", self.lang) if is_relay else "",
            on_close=lambda: self._on_bubble_closed(bubble),
        )
        self.active_bubble = bubble
        PandaPet._apply_cursor_to_panel(self, bubble)
        self.ensure_topmost()

    def _on_bubble_closed(self, bubble: KawaiiSpeechBubble) -> None:
        """Bubble timed out or was clicked; the next queued bubble follows shortly."""
        if bubble is not self.active_bubble:
            return  # stale callback from a bubble we already replaced
        self.active_bubble = None
        self.speech.closed()
        PandaPet._schedule_once_after(self, "speech_pump", self.window, 400, self._pump_speech)

    def _pump_speech(self) -> None:
        if getattr(self, "_closing", False):
            return
        if self.active_bubble is None:
            req = self.speech.next_ready()
            if req is not None:
                self._render_bubble(req)

    def _close_bubble_window(self) -> None:
        bubble, self.active_bubble = self.active_bubble, None
        if bubble:
            try:
                bubble.dismiss()
            except Exception:
                log.exception("bubble dismiss failed")

    def _dismiss_toast(self) -> None:
        """Close the visible bubble; queued bubbles stay queued."""
        self._close_bubble_window()
        self.speech.closed()

    def feed(self, food_id: str) -> FeedResult:
        self.record_activity()
        food = next((f for f in FOOD_ITEMS if f["id"] == food_id), None)
        if not food:
            return FeedResult("invalid")

        is_disliked = self.char_key in food.get("disliked", [])
        food_name = get_food_name(food, self.lang)
        food_icon = RES_ROOT / "work" / "foods" / f"{food_id}_64.png"
        if not resource_exists(food_icon, root=RES_ROOT):
            food_icon = RES_ROOT / "work" / "foods" / f"{food_id}.png"
        has_food_icon = resource_exists(food_icon, root=RES_ROOT)

        # Full stomach (disliked reactions still win): solid food is refused and
        # changes nothing; a drink is still sipped, with a "full but..." line.
        full_line = None
        satiety_now = self._current_satiety()
        if not is_disliked and satiety_now >= SATIETY_FULL_THRESHOLD:
            is_drink, full_line = get_full_reaction(food_id, self.char_key, self.lang)
            if not is_drink:
                self._play_reaction(FULL_REACTION, "feed.full", FEED_REACTION_S, once=True)
                self._toast(
                    full_line,
                    duration_ms=4500,
                    icon_path=food_icon if has_food_icon else None,
                    header=t("feed_full_header", self.lang, food=food_name),
                    badge_text=t("feed_full_badge", self.lang, satiety=int(round(satiety_now))),
                    kind="feed.full",
                )
                return FeedResult("refused_full")

        is_fav, reaction = feed_pet(food_id, self.char_key, lang=self.lang)
        if full_line:
            reaction = full_line
        if is_disliked:
            passion_gain = 1
            satiety_boost = 5.0
        elif is_fav:
            passion_gain = 10
            satiety_boost = SATIETY_FAV_FEED_BOOST
        else:
            passion_gain = 5
            satiety_boost = SATIETY_FEED_BOOST

        self.runtime["cheer_passion"] = self.runtime.get("cheer_passion", 0) + passion_gain
        self.feed_count += 1
        self.runtime["feed_count"] = self.feed_count

        # Satiety recovery (本命美食暴擊 +35%, 一般美食 +20%, 避雷趣味 +5%)
        # Start from the decayed value: the decay since the last 60 s tick is not stored yet.
        self.satiety = min(SATIETY_MAX, satiety_now + satiety_boost)
        self.last_satiety_update = time.time()
        store_satiety(self.runtime, self.char_key, self.satiety, self.last_satiety_update)
        # The discovery goes into the same save as the stats; if that save fails it
        # is taken back, so the café never stamps a food that is not on disk.
        outcome = "disliked" if is_disliked else "favourite" if is_fav else "normal"
        newly = record_food(self.runtime, self.char_key, food_id, outcome, int(time.time()))
        saved = self.save_settings()
        if newly and not saved:
            self.runtime["food_log"][self.char_key].pop(food_id, None)

        reactions = EAT_REACTION if get_feed_animation(food) == "eat" else DRINK_REACTION
        if is_disliked:
            # Her own drawing of this food first (it shows the refusal); never the member
            # aliases, which are ordinary eating poses. It plays the full reaction time so the
            # refusal can be seen; without one she sulks for a single pass.
            played = (self._play_reaction({}, "feed", FEED_REACTION_S, first=(f"feed_{food_id}",))
                      or self._play_reaction(SULK_REACTION, "feed", FEED_REACTION_S, once=True))
        else:
            specific = FOOD_MEMBER_ANIMATIONS.get((self.char_key, food_id), ())
            played = self._play_reaction(reactions, "feed", FEED_REACTION_S, first=(f"feed_{food_id}", *specific))
        if not played:
            self.trigger_cheer(cycles=3 if is_fav else 2, kind="feed")
        total_p = self.runtime["cheer_passion"]
        lvl, tier_title = get_passion_tier(total_p, lang=self.lang)

        if is_disliked:
            header = t("feed_disliked_header", self.lang, food=food_name)
            badge_text = t("feed_disliked_badge", self.lang)
        elif full_line:
            header = t("feed_full_drink_header", self.lang, food=food_name)
            badge_text = f"+{passion_gain}🔥 ({tier_title})"
        elif is_fav:
            header = t("feed_fav_header", self.lang, food=food_name)
            badge_text = f"+{passion_gain}🔥 ({tier_title})"
        else:
            header = t("feed_header", self.lang, food=food_name)
            badge_text = f"+{passion_gain}🔥 ({tier_title})"

        self._toast(
            reaction,
            duration_ms=4500,
            icon_path=food_icon if has_food_icon else None,
            header=header,
            badge_text=badge_text,
            kind="feed",
        )
        self._refresh_status_card()
        self._refresh_food_panel()
        return FeedResult(outcome, drink_full=bool(full_line), newly_unlocked=newly and saved, saved=saved)

    def _current_satiety(self) -> float:
        """Satiety with the decay since the last 60 s update applied (not stored)."""
        elapsed = max(0.0, time.time() - getattr(self, "last_satiety_update", time.time()))
        return max(0.0, self.satiety - elapsed / SATIETY_DECAY_SECONDS_PER_PERCENT)

    def show_status_card(self) -> None:
        self.record_activity()
        if self.status_card:
            try:
                if self.status_card.window.winfo_exists():
                    self.status_card.window.deiconify()
                    self.status_card.window.lift()
                    return
            except Exception:
                pass
            self.status_card = None

        badge_desc = str(get_member_badge(self.char_key, self.lang))
        self.status_card = PandaStatusCard(
            parent=self.window,
            char_key=self.char_key,
            char_name=self.get_active_name(),
            badge_desc=badge_desc,
            passion_points=self.runtime.get("cheer_passion", 0),
            companion_start_time=self.companion_start_time,
            feed_count=self.feed_count,
            anchor_x=self.x,
            anchor_y=self.y,
            lang=self.lang,
            total_companion_seconds=self.get_total_companion_seconds(),
            satiety=self.satiety,
            on_close=self._on_status_card_closed,
        )
        try:
            self.status_card.window.lift()
        except Exception:
            pass
        PandaPet._apply_cursor_to_panel(self, self.status_card)

    def _on_status_card_closed(self) -> None:
        self.status_card = None

    def open_food_panel(self) -> None:
        self.record_activity()
        panel = self.food_panel
        if panel is not None:
            try:
                if panel.window.winfo_exists():
                    panel.window.deiconify()
                    panel.window.lift()
                    self._lift_bubble()
                    return
            except tk.TclError:
                pass
            self.food_panel = None

        from app.food_panel import FoodCafePanel
        self.food_panel = FoodCafePanel(
            self.window,
            lang=self.lang,
            char_key=self.char_key,
            satiety_getter=self._current_satiety,
            outcomes=food_outcomes(self.runtime, self.char_key),
            on_feed=self.feed,
            on_close=self._on_food_panel_closed,
            work_area=self._pet_work_area(),
        )
        # Placing the panel moves it to the top of the topmost band; a showing bubble stays above.
        self._lift_bubble()
        PandaPet._apply_cursor_to_panel(self, self.food_panel)

    def _pet_work_area(self):
        """Work area (without taskbar) of the monitor the pet is on; None = panel decides."""
        lookup = getattr(self.desktop, "work_area_for_point", None)
        if lookup is None:
            return None
        try:
            return lookup(self.x + self.width // 2, self.y + self.height // 2)
        except Exception:
            log.exception("work area lookup failed")
            return None

    def _on_food_panel_closed(self) -> None:
        self.food_panel = None
        self._schedule_memory_reclaim()

    def _refresh_food_panel(self) -> None:
        panel = self.food_panel
        if panel is None:
            return
        try:
            if panel.window.winfo_exists():
                # Called after feed() has saved (or taken back) the discovery:
                # the snapshot only holds what is on disk.
                panel.refresh(char_key=self.char_key, lang=self.lang,
                              outcomes=food_outcomes(self.runtime, self.char_key))
            else:
                self.food_panel = None
        except Exception:
            log.exception("food panel refresh failed")
            self.food_panel = None

    def _close_food_panel(self) -> None:
        panel, self.food_panel = self.food_panel, None
        if panel is not None:
            try:
                panel.close()
            except Exception:
                log.exception("food panel close failed")

    def open_settings_panel(self, tab: str = "appearance") -> None:
        """Appearance & reminders panel ("default + custom"); one at a time."""
        self.record_activity()
        panel = self.settings_panel
        if panel is not None:
            try:
                if panel.window.winfo_exists():
                    panel.switch_tab(tab)
                    panel.window.deiconify()
                    panel.window.lift()
                    self._lift_bubble()
                    PandaPet._schedule_once_after(   # the first idle lift may still be pending
                        self, "lift_bubble", self.window, None, self._lift_bubble
                    )
                    return
            except tk.TclError:
                pass
            self.settings_panel = None

        from app.settings_panel import SettingsPanel
        self.settings_panel = SettingsPanel(
            self.window,
            lang=self.lang,
            char_key=self.char_key,
            state=self.settings_state(),
            on_change=self._on_settings_change,
            on_reset=self._on_settings_reset,
            on_preview=self.preview_reminder,
            on_close=self._on_settings_panel_closed,
            initial_tab=tab,
            work_area=self._pet_work_area(),
        )
        # The panel lifts itself again once idle; queued after that, a showing bubble stays above.
        self._lift_bubble()
        PandaPet._schedule_once_after(self, "lift_bubble", self.window, None, self._lift_bubble)
        PandaPet._apply_cursor_to_panel(self, self.settings_panel)

    def _on_settings_change(self, key: str, value) -> bool:
        ok = self.apply_setting(key, value)
        self._refresh_settings_panel()       # the panel shows what main holds, accepted or not
        return ok

    def _on_settings_reset(self, section: str) -> bool:
        ok = self.reset_settings(section)
        self._refresh_settings_panel()
        return ok

    def _on_settings_panel_closed(self) -> None:
        self.settings_panel = None

    def _refresh_settings_panel(self) -> None:
        panel = self.settings_panel
        if panel is None:
            return
        try:
            if panel.window.winfo_exists():
                panel.refresh(state=self.settings_state(), char_key=self.char_key, lang=self.lang)
            else:
                self.settings_panel = None
        except Exception:
            log.exception("settings panel refresh failed")
            self.settings_panel = None

    def _close_settings_panel(self) -> None:
        panel, self.settings_panel = self.settings_panel, None
        if panel is not None:
            try:
                panel.close()
            except Exception:
                log.exception("settings panel close failed")

    def open_profile_card(self) -> None:
        self.record_activity()
        if hasattr(self, "profile_card") and self.profile_card:
            try:
                if self.profile_card.win.winfo_exists():
                    self.profile_card.win.lift()
                    return
            except Exception:
                pass
            self.profile_card = None

        from app.profile_card import MemberProfileCard
        self.profile_card = MemberProfileCard(
            parent=self.window,
            initial_member=self.char_key,
            lang=self.lang,
            on_greeting=self._on_profile_greeting,
            on_context_change=self._on_profile_context_changed,
            on_close=self._on_profile_card_closed,
        )
        PandaPet._apply_cursor_to_panel(self, self.profile_card)

    def _on_profile_greeting(self, member_key: str, greeting_text: str) -> bool:
        """True when the greeting bubble is showing at the card (the card may animate her)."""
        self.record_activity()
        avatar = RES_ROOT / "work" / "characters" / member_key / "idle_01.png"
        greeting = dict(
            header=f"🐼 {get_member_display_name(member_key, self.lang)}",
            speaker=member_key,
            sub_badge=t("profile_title", self.lang),
            icon_path=avatar if resource_exists(avatar, root=RES_ROOT) else None,
            duration_ms=4500,
            priority=Priority.USER,
            kind="profile.greeting",
        )
        if member_key != self.char_key:
            # Another member greets from her card: the pet does not cheer or speak for her.
            # Not queued while held (standby): a late bubble would point at an old card spot.
            card = getattr(self, "profile_card", None)
            bounds = card.avatar_bounds() if card is not None and hasattr(card, "avatar_bounds") else None
            if bounds is None or self.speech.held:
                return False
            x, y, w, h = bounds
            shown = self._toast(greeting_text, anchor=(x, y), anchor_size=(w, h), origin="profile_card", **greeting)
            PandaPet._schedule_once_after(self, "lift_bubble", self.root, None, self._lift_bubble)
            return shown
        self._toast(greeting_text, **greeting)
        # The card may be raised by the same click after this; keep the bubble on top.
        PandaPet._schedule_once_after(self, "lift_bubble", self.root, None, self._lift_bubble)
        self.trigger_cheer(cycles=2)
        return False                     # the pet itself greets, not the card

    def _on_profile_context_changed(self) -> None:
        """The card changed page, was dragged or closed: its greeting bubble no longer fits.

        Only a card bubble is closed; a notification it interrupted comes back via the queue.
        """
        current = self.speech.current
        if current is None or current.origin != "profile_card":
            return
        self._dismiss_toast()
        PandaPet._schedule_once_after(self, "speech_pump", self.window, 400, self._pump_speech)

    def set_sedentary_interval(self, mins: int) -> None:
        self.settings["sedentary_interval_min"] = mins
        self.sedentary_active_sec = 0
        self.save_settings()
        self.build_menu()
        if mins > 0:
            self._toast(t("sedentary_set", self.lang, mins=mins), duration_ms=2500)
        else:
            self._toast(t("sedentary_closed", self.lang), duration_ms=2500)

    def test_sedentary_alert(self) -> None:
        """Menu 'test reminder' — user initiated, shows immediately."""
        self.sedentary_alert(priority=Priority.USER)

    def sedentary_alert(self, priority: Priority = Priority.SYSTEM) -> None:
        self.trigger_cheer(cycles=3, priority=priority, kind="reminder.sedentary")
        char_name = self.get_active_name()
        msg = self.settings.get("sedentary_message") or t("sedentary_hint", self.lang)
        header = t("sedentary_header", self.lang, name=char_name)
        sub_badge = t("sedentary_badge", self.lang)
        self._toast(
            msg,
            header=header,
            sub_badge=sub_badge,
            duration_ms=6000,
            priority=priority,
            kind="reminder.sedentary",
        )

    def toggle_notify_relay(self) -> None:
        new_val = not self.settings.get("notify_relay", True)
        self.settings["notify_relay"] = new_val
        self.save_settings()
        self.build_menu()
        status = t("status_on", self.lang) if new_val else t("status_off", self.lang)
        self._toast(t("notify_relay_status", self.lang, status=status), duration_ms=2500)

    def toggle_notify_privacy(self) -> None:
        """Privacy mode (streaming / screen sharing): bubbles name the app only."""
        new_val = self.settings.get("notify_privacy_mode", False) is not True
        self.settings["notify_privacy_mode"] = new_val
        self.save_settings()
        self.build_menu()
        self._refresh_settings_panel()
        self._refresh_notification_drawer()
        status = t("status_on", self.lang) if new_val else t("status_off", self.lang)
        self._toast(notif_text(t, "notify_privacy_status", self.lang, status=status), duration_ms=2500)

    toggle_notify_privacy_mode = toggle_notify_privacy

    def set_notify_bubble_style(self, style_key: str, *, silent: bool = False) -> bool:
        if not isinstance(style_key, str) or style_key not in VALID_NOTIFY_BUBBLE_STYLES:
            return False
        if style_key == self.settings.get("notify_bubble_style", "banner"):
            return True
        self.settings["notify_bubble_style"] = style_key
        self.save_settings()
        self.build_menu()
        if not silent:
            self._refresh_settings_panel()
            label = t(f"notify_style_{style_key}", self.lang)
            self._toast(t("notify_bubble_style_status", self.lang, style=label), duration_ms=2500)
        return True

    def clear_recent_notifications(self) -> None:
        """Empties the pet's RAM list only; the Windows notification centre is not touched."""
        self.recent_notifications.clear()
        self._refresh_notification_drawer()
        self._toast(
            t("notif_drawer_cleared_toast", self.lang),
            header="Apink Panda",
            duration_ms=3500,
        )

    def apply_mouse_cursor(self, cursor_key: str | None = None) -> None:
        """Apply active cursor to pet canvas, window, and any open subpanels."""
        if cursor_key is None:
            cursor_key = self.settings.get("mouse_cursor", "paw_smooth")
        from app.cursor_manager import (
            apply_cursor_to_widgets,
            get_tkinter_cursor_spec,
            set_window_cursor,
            apply_system_cursor_global,
            restore_system_cursor_global,
        )
        spec = get_tkinter_cursor_spec(cursor_key)

        # 1. Tkinter native cursor for pet canvas and main window
        try:
            self.canvas.config(cursor=spec)
            self.window.config(cursor=spec)
        except Exception as exc:
            log.debug("apply_mouse_cursor tk config error: %s", exc)

        # 2. Apply to open subpanels
        panel_widgets: list[Any] = []
        for attr in (
            "status_card", "profile_card", "birthday_dialog",
            "food_panel", "settings_panel", "notification_drawer", "pink_menu",
            "active_bubble", "fortune_dialog", "group_celebration", "cameo_window",
            "anniversary_scene", "dome_preview", "new_year_clock",
        ):
            panel = getattr(self, attr, None)
            if panel is not None:
                try:
                    panel._cursor_key = cursor_key
                except Exception:
                    pass
                panel_widgets.extend(self._collect_panel_cursor_widgets(panel))

        # 3. Apply Win32 window class / WM_SETCURSOR cursor (supports in-memory .cur in .pak builds and mapped wrapper HWNDs)
        seen_hwnds: set[int] = set()
        for raw_hwnd in (
            lambda: (
                int(frame, 16) if (frame := self.window.wm_frame()).startswith("0x") else int(frame)
            ) if self.window.wm_frame() else 0,
            lambda: int(self.window.winfo_id()),
            lambda: int(self.canvas.winfo_id()),
        ):
            try:
                hwnd = int(raw_hwnd() or 0)
                if hwnd and hwnd not in seen_hwnds:
                    seen_hwnds.add(hwnd)
                    set_window_cursor(hwnd, cursor_key)
            except Exception:
                pass
        apply_cursor_to_widgets(panel_widgets, cursor_key)

        # 4. If global system cursor is enabled in settings, apply to whole OS
        if self.settings.get("mouse_cursor_global", False):
            apply_system_cursor_global(cursor_key)
        else:
            restore_system_cursor_global()

    @staticmethod
    def _collect_panel_cursor_widgets(panel: Any) -> list[Any]:
        attrs = (
            "window", "win", "canvas",
            "_sub_window", "_sub_canvas", "_peek_window", "_peek_canvas",
            "vis_win", "vis_canvas", "bubble_window", "_bubble_canvas",
        )
        candidates = [getattr(panel, attr, None) for attr in attrs]
        guide = getattr(panel, "notif_guide", None)
        if guide is not None and not getattr(guide, "closed", False):
            candidates.extend(getattr(guide, attr, None) for attr in ("window", "text"))
        for actor in getattr(panel, "windows", ()):
            candidates.extend(actor[:2])
        actor_windows = getattr(panel, "actor_windows", None)
        if isinstance(actor_windows, dict):
            candidates.extend(w for w in actor_windows.values() if isinstance(w, tk.Misc))
        actor_canvases = getattr(panel, "_actor_canvases", None)
        if isinstance(actor_canvases, dict):
            candidates.extend(
                entry[0] for entry in actor_canvases.values()
                if isinstance(entry, tuple) and entry and isinstance(entry[0], tk.Misc)
            )
        return list({id(widget): widget for widget in candidates if widget is not None}.values())

    @classmethod
    def _apply_cursor_to_panel(cls, owner: Any, panel: Any) -> None:
        if panel is None:
            return
        settings = getattr(owner, "settings", None)
        if not isinstance(settings, dict):
            return
        cursor_key = settings.get("mouse_cursor", "paw_smooth")
        try:
            panel._cursor_key = cursor_key
        except Exception:
            pass
        from app.cursor_manager import apply_cursor_to_widgets

        apply_cursor_to_widgets(cls._collect_panel_cursor_widgets(panel), cursor_key)

    def _on_enter_pet(self, event: Any = None) -> None:
        self.apply_mouse_cursor()

    def _on_leave_pet(self, event: Any = None) -> None:
        pass

    def set_mouse_cursor(self, cursor_key: str) -> None:
        """Change active mouse cursor style ("paw_smooth", "mitten_smooth", "paw_pixel", "mitten_pixel", "system")."""
        from app.storage.settings import VALID_MOUSE_CURSORS
        if cursor_key not in VALID_MOUSE_CURSORS:
            return
        self.settings["mouse_cursor"] = cursor_key
        self.save_settings()
        self.apply_mouse_cursor(cursor_key)
        self.build_menu()
        if hasattr(self, "_refresh_pink_menu"):
            self._refresh_pink_menu()
        name_key = f"cursor_{cursor_key}"
        cursor_name = t(name_key, self.lang)
        self._toast(t("cursor_applied_toast", self.lang, cursor=cursor_name), duration_ms=2500)

    def open_notification_drawer(self) -> None:
        """Open the kawaii RAM-only 20-item Recent Notifications Drawer."""
        self.record_activity()
        drawer = getattr(self, "notification_drawer", None)
        if drawer is not None:
            try:
                if drawer.window.winfo_exists():
                    drawer.items = list(self.recent_notifications)[:20]
                    drawer.privacy_mode = bool(self.settings.get("notify_privacy_mode", False))
                    drawer._render()
                    drawer.window.deiconify()
                    drawer.window.lift()
                    return
            except tk.TclError:
                pass
            self.notification_drawer = None

        from app.pink_context_menu import NotificationDrawerWindow
        self.notification_drawer = NotificationDrawerWindow(
            self.window,
            lang=self.lang,
            char_key=self.char_key,
            items=list(self.recent_notifications),
            privacy_mode=bool(self.settings.get("notify_privacy_mode", False)),
            on_clear=self.clear_recent_notifications,
            on_toggle_privacy=lambda: (self.toggle_notify_privacy() or bool(self.settings.get("notify_privacy_mode", False))),
            on_close=lambda: setattr(self, "notification_drawer", None),
            work_area=self._pet_work_area(),
            anchor_box=(int(self.x), int(self.y), int(self.width), int(self.height)),
        )
        PandaPet._apply_cursor_to_panel(self, self.notification_drawer)

    def _refresh_notification_drawer(self) -> None:
        drawer = getattr(self, "notification_drawer", None)
        if drawer is None:
            return
        try:
            if drawer.window.winfo_exists():
                drawer.lang = self.lang
                drawer.char_key = self.char_key
                drawer.items = list(self.recent_notifications)[:20]
                drawer.privacy_mode = bool(self.settings.get("notify_privacy_mode", False))
                drawer._render()
            else:
                self.notification_drawer = None
        except Exception:
            self.notification_drawer = None

    def _close_notification_drawer(self) -> None:
        drawer, self.notification_drawer = getattr(self, "notification_drawer", None), None
        if drawer is not None:
            try:
                drawer.close()
            except Exception:
                pass

    def _close_pink_menu(self) -> None:
        pm, self.pink_menu = getattr(self, "pink_menu", None), None
        self._menu_active = False
        if pm is not None:
            try:
                pm.close()
            except Exception:
                pass

    def relay_notifications(self, items: list[dict[str, str]]) -> None:
        """New Windows toasts from one poll: all go to the RAM list, one bubble shows them."""
        if not items:
            return
        now = datetime.datetime.now()
        for item in items:
            self.recent_notifications.append(drawer_entry(item, now))
        self._refresh_notification_drawer()
        privacy = self.settings.get("notify_privacy_mode", False) is True
        header, msg = relay_bubble(items, self.lang, privacy, t)
        self.trigger_cheer(cycles=2, priority=Priority.SYSTEM, kind="notify.relay")
        self._toast(
            msg,
            header=header,
            sub_badge=t("windows_notif_badge", self.lang),
            duration_ms=7000,
            priority=Priority.SYSTEM,
            kind="notify.relay",
        )

    def settings_state(self) -> dict:
        """Snapshot of the values the settings panel shows."""
        state = {key: self.settings.get(key, default)
                 for section in SETTINGS_DEFAULTS.values() for key, default in section.items()}
        state["sedentary_message"] = self.settings.get("sedentary_message", "")
        state["notify_privacy_mode"] = bool(self.settings.get("notify_privacy_mode", False))
        return state

    def apply_setting(self, key: str, value) -> bool:
        """Settings panel change; True = accepted and applied (saving is best effort, as for
        every setter), False = rejected and nothing changed."""
        if key in ("bubble_theme", "pet_size", "text_size", "standby_clock_position") and not isinstance(value, str):
            return False
        if key == "bubble_theme":
            if value != "auto" and value not in BUBBLE_THEMES:
                return False
            if value != self.settings.get("bubble_theme", "auto"):
                self.set_bubble_theme(value)
        elif key == "pet_size":
            if value not in PET_SIZE_MAP:
                return False
            self.set_pet_size(value)
        elif key == "text_size":
            if value not in TEXT_SIZES:
                return False
            self.set_text_size(value)
        elif key == "standby_clock_position":
            if value not in VALID_STANDBY_CLOCK_POSITIONS:
                return False
            if value != self.settings.get("standby_clock_position", "top_right"):
                self.settings["standby_clock_position"] = value
                self.save_settings()
        elif key == "hourly_chime":
            if type(value) is not bool:
                return False
            if value != self.settings.get("hourly_chime", True):
                self.toggle_hourly_chime()
        elif key in ("hourly_start", "hourly_end"):
            if type(value) is not int or not 0 <= value <= 23:
                return False
            start, end = hourly_range(self.settings)
            # Moving one end past the other drags it along, so the range never turns inside out.
            new = (value, max(end, value)) if key == "hourly_start" else (min(start, value), value)
            if new != (start, end):
                self.set_hourly_range(*new)
        elif key == "sedentary_interval_min":
            low, high = SEDENTARY_MIN_RANGE
            if type(value) is not int or not (value == 0 or low <= value <= high):
                return False
            if value != self.settings.get("sedentary_interval_min", 60):
                self.set_sedentary_interval(value)
        elif key == "sedentary_message":
            cleaned = clean_reminder_text(value)
            if cleaned is None:
                return False
            if cleaned != self.settings.get("sedentary_message", ""):
                self.settings["sedentary_message"] = cleaned
                self.save_settings()
        elif key == "notify_privacy_mode":
            if type(value) is not bool:
                return False
            if value != bool(self.settings.get("notify_privacy_mode", False)):
                self.toggle_notify_privacy()
        elif key == "notify_bubble_style":
            return self.set_notify_bubble_style(value, silent=True)
        else:
            return False
        return True

    def reset_settings(self, section: str) -> bool:
        """Settings panel "default" button for one section."""
        defaults = SETTINGS_DEFAULTS.get(section)
        if defaults is None:
            return False
        depth = getattr(self, "_batch_depth", 0)
        self._batch_depth = depth + 1
        if depth == 0:
            self._batch_dirty_save = False
            self._batch_dirty_menu = False
            self._batch_last_toast = None
        try:
            for key, value in defaults.items():
                self.apply_setting(key, value)
        finally:
            self._batch_depth = depth
            if depth == 0:
                if getattr(self, "_batch_dirty_save", False):
                    self._batch_dirty_save = False
                    if hasattr(self, "save_settings"):
                        self.save_settings()
                if getattr(self, "_batch_dirty_menu", False):
                    self._batch_dirty_menu = False
                    if hasattr(self, "build_menu"):
                        self.build_menu()
                last_toast = getattr(self, "_batch_last_toast", None)
                self._batch_last_toast = None
                if last_toast is not None and hasattr(self, "_toast"):
                    args, kwargs = last_toast
                    self._toast(*args, **kwargs)
        return True

    def preview_reminder(self, kind: str) -> bool:
        """Settings panel "try it": shows the reminder now, the real countdown is untouched."""
        if kind != "sedentary":
            return False
        self.test_sedentary_alert()
        return True

    def set_hourly_range(self, start: int, end: int) -> None:
        """Hours (inclusive) whose o'clock gets a chime bubble."""
        self.settings["hourly_start"], self.settings["hourly_end"] = start, end
        self.calendar.hourly_chime_range = (start, end)
        self.save_settings()

    def toggle_hourly_chime(self) -> None:
        new_val = not self.settings.get("hourly_chime", True)
        self.settings["hourly_chime"] = new_val
        self.calendar.enable_hourly_chime = new_val
        self.save_settings()
        self.build_menu()
        status = t("status_on", self.lang) if new_val else t("status_off", self.lang)
        self._toast(t("hourly_chime_status", self.lang, status=status), duration_ms=2500)

    def _standby_layout_params(self, bounds=None) -> tuple[int, int, int]:
        """Compute standby ``(sw, sh, sprite_px)`` on the Tk main thread."""
        b = bounds if bounds is not None else self._pet_monitor_bounds()
        if b is not None:
            sw, sh = max(1, b.right - b.left), max(1, b.bottom - b.top)
        else:
            try:
                sw = max(1, int(self.window.winfo_screenwidth()))
                sh = max(1, int(self.window.winfo_screenheight()))
            except Exception:
                sw, sh = 1920, 1080
        try:
            k = max(1.0, min(4.0, float(self.window.winfo_fpixels("1i")) / 96.0))
        except Exception:
            k = 1.0
        current_px = getattr(self.sprites, "display_px", None)
        sprite_px = (current_px if isinstance(current_px, int) and current_px > 0 else
                     pet_display_px(self.settings.get("pet_size", "medium"), k, b))
        return sw, sh, sprite_px

    def _is_warmup_busy(self) -> bool:
        """Thread-safe check used by the background warmup thread to yield while GUI is busy."""
        if getattr(self, "_menu_active", False) or getattr(self, "dragging", False):
            return True
        if getattr(self, "standby_overlay", None) is not None:
            return True
        return (time.time() - getattr(self, "last_user_activity", 0.0)) < 0.8

    def _schedule_standby_warmup(self, delay_ms: int = 2000) -> None:
        if getattr(self, "_desktop_warmup", None) is not None:
            self._desktop_warmup.cancel()
            self._schedule_once_after("desktop_warmup", self.window, delay_ms, self._start_desktop_warmup)
        warmup = getattr(self, "_standby_warmup", None)
        if warmup is None or not hasattr(self, "window") or not hasattr(self, "_loop_after"):
            return
        old = self._loop_after.pop("standby_warmup", None)
        if old is not None:
            try:
                self.window.after_cancel(old)
            except Exception:
                pass
        if delay_ms > 0:
            self._loop_after["standby_warmup"] = self.window.after(delay_ms, self._start_standby_warmup)
        else:
            self._start_standby_warmup()

    def _glyph_warmup_step(self) -> None:
        """Lay out a few pending (font, glyph) pairs on a hidden canvas, then yield to Tk."""
        self._loop_after.pop("glyph_warmup", None)
        if getattr(self, "_closing", False):
            return
        queue = getattr(self, "_glyph_warmup_queue", None)
        if queue is None:
            queue = self._glyph_warmup_queue = deque(
                (font, ch) for font in glyph_warmup_fonts(self.lang)
                for ch in warmup_glyphs()
            )
        if self.dragging or getattr(self, "standby_overlay", None) is not None:
            self._loop_after["glyph_warmup"] = self.window.after(500, self._glyph_warmup_step)
            return
        try:
            canvas = getattr(self, "_glyph_warmup_canvas", None)
            if canvas is None:
                canvas = self._glyph_warmup_canvas = tk.Canvas(self.root, width=1, height=1)
            deadline = time.perf_counter() + GLYPH_WARMUP_SLICE_S
            while queue:
                font, ch = queue.popleft()
                canvas.delete(canvas.create_text(0, 0, text=ch, font=font))
                if time.perf_counter() >= deadline:
                    break
        except tk.TclError:
            queue.clear()
        if queue:
            self._loop_after["glyph_warmup"] = self.window.after(GLYPH_WARMUP_GAP_MS, self._glyph_warmup_step)
        else:
            canvas, self._glyph_warmup_canvas = getattr(self, "_glyph_warmup_canvas", None), None
            if canvas is not None:
                try:
                    canvas.destroy()
                except tk.TclError:
                    pass

    def _start_desktop_warmup(self) -> None:
        self._loop_after.pop("desktop_warmup", None)
        if getattr(self, "_closing", False) or getattr(self, "standby_overlay", None) is not None:
            return
        self._desktop_warmup.schedule(
            RES_ROOT, self.sprites.display_px, 1, 1,
            today=self.calendar.clock.now().date(), active_member=self.char_key,
            busy_check=self._is_warmup_busy,
            binary_alpha=bool(getattr(self.sprites, "binary_alpha", True)),
            edge_refine=bool(getattr(self.sprites, "edge_refine", False)),
            registry=getattr(self.sprites, "registry", None),
        )

    def _start_standby_warmup(self) -> None:
        self._loop_after.pop("standby_warmup", None)
        warmup = getattr(self, "_standby_warmup", None)
        if warmup is None or getattr(self, "standby_overlay", None) is not None:
            return
        sw, sh, sprite_px = self._standby_layout_params()
        if (
            getattr(self.sprites, "display_px", None) == sprite_px
            and getattr(self.sprites, "registry", None) is not None
            and bool(getattr(self.sprites, "binary_alpha", True)) == STANDBY_BINARY_ALPHA
            and bool(getattr(self.sprites, "edge_refine", False)) == STANDBY_EDGE_REFINE
        ):
            member_entry = self.sprites._members.get(self.char_key)
            if member_entry is not None and member_entry.source == "registry":
                seed_prepared_member_pil(
                    self.sprites,
                    self.char_key,
                    getattr(member_entry, "_pil", None),
                )
        active_scene = self.settings.get("standby_scene") or None
        today = self.clock.now().date() if hasattr(self, "clock") else datetime.date.today()
        warmup.schedule(
            RES_ROOT,
            sprite_px=sprite_px,
            screen_w=sw,
            screen_h=sh,
            active_scene=active_scene,
            today=today,
            busy_check=self._is_standby_warmup_busy,
            active_member=self.char_key,
            registry=getattr(self.sprites, "registry", None),
        )

    def _is_standby_warmup_busy(self) -> bool:
        desktop = getattr(self, "_desktop_warmup", None)
        return self._is_warmup_busy() or (desktop is not None and desktop.is_running())

    def open_standby_screen(self, scene: str | None = None) -> None:
        if self.standby_overlay:
            return
        self._reset_restore_counters()
        self._standby_resume_pending = False
        pending_warmup = self._loop_after.pop("standby_warmup", None)
        if pending_warmup is not None:
            self.window.after_cancel(pending_warmup)
        if getattr(self, "_standby_warmup", None) is not None:
            self._standby_warmup.cancel()
        if getattr(self, "_desktop_warmup", None) is not None:
            self._desktop_warmup.cancel()
        desktop_after = self._loop_after.pop("desktop_warmup", None)
        if desktop_after is not None:
            self.window.after_cancel(desktop_after)
        resume = self._loop_after.pop("standby_resume", None)
        if resume is not None:
            self.window.after_cancel(resume)
        tray_restore = self._loop_after.pop("tray_restore", None)
        if tray_restore is not None:
            self.window.after_cancel(tray_restore)
        # STANDBY: coordinator parks system events, speech queue holds bubbles,
        # so nothing can deiconify the pet on top of the standby screen.
        self.end_drag()
        self._stop_cameo()  # screen gets covered: no exit animation needed
        self._close_bubble_window()
        self._close_food_panel()
        self._close_settings_panel()
        self._close_group_celebration()
        self._close_new_year_clock()
        self._close_pink_menu()
        self._close_notification_drawer()
        self.speech.hold(True)
        self.coord.set_mode(GlobalMode.STANDBY)
        # Temporarily hide desktop pet window so there's no floating 6th panda on the screensaver
        try:
            self._set_pet_visibility(False)
        except Exception:
            pass

        _StandbyClass = PandaStandbyOverlay
        flipped_walks = self.get_flipped_walk_frames(self.char_key)
        minutes = self.get_companion_minutes()
        chosen_scene = scene or self.settings.get("standby_scene") or None
        bounds = self._pet_monitor_bounds()
        _sw, _sh, _sprite_px = self._standby_layout_params(bounds)
        if (
            getattr(self.sprites, "display_px", None) == _sprite_px
            and getattr(self.sprites, "registry", None) is not None
        ):
            _member_entry = self.sprites._members.get(self.char_key)
            if _member_entry is not None and _member_entry.source == "registry":
                seed_prepared_member_pil(
                    self.sprites,
                    self.char_key,
                    getattr(_member_entry, "_pil", None),
                )
        clock_position = self.settings.get("standby_clock_position", "top_right")
        self.standby_overlay = _StandbyClass(
            parent=self.root,
            char_key=self.char_key,
            char_name=self.get_active_name(),
            lang=self.lang,
            frames=self.frames,
            flipped_walk_frames=flipped_walks,
            passion_points=self.runtime.get("cheer_passion", 0),
            companion_minutes=minutes,
            on_close=self.on_standby_closed,
            lock_on_exit=self.settings.get("standby_lock_workstation", True) if scene is None else False,
            show_panda_tags=False,
            # None = automatic (December -> christmas, otherwise a daily pick);
            # the user can cycle scenes with Left/Right inside standby.
            scene=chosen_scene,
            bounds=bounds,
            other_bounds=self._other_monitor_bounds(bounds),
            clock_position=clock_position,
            display_px=_sprite_px,
        )

    def toggle_standby_lock(self) -> None:
        new_val = not self.settings.get("standby_lock_workstation", True)
        self.settings["standby_lock_workstation"] = new_val
        self.save_settings()
        self.build_menu()
        status = t("status_on", self.lang) if new_val else t("status_off", self.lang)
        self._toast(t("standby_lock_status", self.lang, status=status), duration_ms=3000)

    def on_standby_closed(self) -> None:
        self.standby_overlay = None
        self._schedule_memory_reclaim()
        self._reset_restore_counters()
        self._standby_resume_pending = True
        # LockWorkStation is asynchronous. Keep speech held and the coordinator
        # parked until a later callback observes the interactive desktop again.
        self._schedule_standby_resume()

    def _on_fortune_dialog_closed(self) -> None:
        self.fortune_dialog = None
        self._schedule_memory_reclaim()

    def _schedule_memory_reclaim(self, delay_ms: int = 1500) -> None:
        """One full gc pass shortly after a big window closes (2026-11-22).

        Standby, the fortune room and group celebrations leave reference cycles (Tk
        callbacks, lambdas). Python only runs a full pass after many container allocations;
        decoded pixels do not count, so each closed standby could keep 200+ MB until some
        much later pass. Measured: 230 -> 518 -> 778 -> 935 MB over three standby rounds
        without it, ~320-340 MB flat with it.
        """
        window = getattr(self, "window", None)
        if window is None or not hasattr(self, "_schedule_once_after"):
            gc.collect()
            return
        self._schedule_once_after("memory_reclaim", window, delay_ms, self._reclaim_memory)

    def _reclaim_memory(self) -> None:
        if getattr(self, "_closing", False):
            return
        if getattr(self, "standby_overlay", None) is None:
            trim_fitted_wallpapers(keep=1)
        gc.collect()

    def _reset_restore_counters(self) -> None:
        self._standby_unknown_count = 0
        self._standby_restore_failures = 0
        self._tray_restore_failures = 0

    def _schedule_standby_resume(self, delay_ms: int = 500) -> None:
        old = self._loop_after.pop("standby_resume", None)
        if old is not None:
            self.window.after_cancel(old)
        self._loop_after["standby_resume"] = self.window.after(delay_ms, self._resume_after_standby)

    def _retry_desktop_restore(self, kind: str) -> None:
        """Bound failed mapping/restore attempts; actual OS lock waits are separate."""
        attr = f"_{kind}_restore_failures"
        count = getattr(self, attr, 0) + 1
        setattr(self, attr, count)
        if count in (1, 6):
            log.warning("%s desktop restore failed (attempt %s/6); try the tray if recovery stops", kind, count,
                        exc_info=count == 1 and sys.exc_info()[0] is not None)
        if count >= 6:
            if getattr(self, "tray", None):
                self.tray.set_visible_state(bool(self.window.winfo_viewable()))
            if kind == "standby":
                self._standby_resume_pending = False
                self._desktop_was_locked = False
                self.coord.set_mode(GlobalMode.NORMAL)
                self.speech.hold(False)
            return
        if kind == "standby":
            self._schedule_standby_resume(min(500 * 2 ** (count - 1), 4000))
        else:
            self._loop_after["tray_restore"] = self.window.after(
                min(100 * 2 ** (count - 1), 1000), self.show_from_tray)

    def _recover_pet_geometry(self) -> bool:
        """Re-home the base box after a monitor/work-area change, preserving action offsets."""
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height // 2)
        position = area.clamp(self.x, self.y, self.width, self.height)
        if position == (self.x, self.y):
            return False
        self.x, self.y = position
        self.target_roam_x = None
        self._place_pet()
        return True

    def _restore_pet_window(self) -> bool:
        self._recover_pet_geometry()
        self._sync_frame_box(self._visual_action())
        left, top, right, bottom = self._frame_pad
        self.canvas.config(width=self.width + left + right, height=self.height + top + bottom)
        self.window.geometry(f"{self.width + left + right}x{self.height + top + bottom}"
                             f"+{int(self.x - left)}+{int(self.y - top)}")
        self._show_canvas_frame(state="normal")
        surf = getattr(self, "layered_surface", None)
        if surf is None or surf.closed:
            self.window.attributes("-transparentcolor", BG)
        self.desktop.set_noactivate(self._pet_hwnd())
        self.window.deiconify()
        if surf is not None and not surf.closed:
            surf.set_visibility(True)
            self._present_layered_pet()
        self.window.update_idletasks()
        self._place_pet()
        self.window.lift()
        self.ensure_topmost()
        # MapNotify/ConfigureNotify are normal Tk events, not idle work. A mapped
        # top-level can still have an unmapped 1x1 canvas until the next event turn.
        # Never run nested update(); the caller retries through after instead.
        if not self.window.winfo_viewable() or not self.canvas.winfo_viewable():
            return False
        if getattr(self, "tray", None):
            self.tray.set_visible_state(True)
        return True

    def _resume_after_standby(self) -> None:
        self._loop_after.pop("standby_resume", None)
        if not getattr(self, "_standby_resume_pending", False) or self.standby_overlay is not None:
            return
        locked = is_workstation_locked()
        if locked is True:
            self._standby_unknown_count = 0
            self._schedule_standby_resume()
            return
        if locked is None:
            self._standby_unknown_count = getattr(self, "_standby_unknown_count", 0) + 1
            if self._standby_unknown_count < 10:
                self._schedule_standby_resume()
                return
            if self._standby_unknown_count == 10:
                log.warning("Desktop lock state unknown for 10 probes; attempting standby recovery")
        else:
            self._standby_unknown_count = 0
        try:
            if not self._restore_pet_window():
                self._retry_desktop_restore("standby")
                return
        except Exception:
            self._retry_desktop_restore("standby")
            return
        self._standby_resume_pending = False
        self._reset_restore_counters()
        self._desktop_was_locked = False
        self.record_activity()
        self.coord.set_mode(GlobalMode.NORMAL)
        self.speech.hold(False)
        self._set_ambient("idle")
        self.trigger_cheer(cycles=2, kind="standby.exit")
        char_name = self.get_active_name()
        self._toast(t("standby_closed_toast", self.lang, name=char_name), duration_ms=2500)
        self._schedule_standby_warmup(delay_ms=1500)
        self._schedule_festival_welcome()

    def toggle_visible(self) -> None:
        if self._pet_is_visible():
            self.hide_to_tray()
        else:
            self.show_from_tray()

    def hide_to_tray(self) -> None:
        self._tray_restore_failures = 0
        restore = self._loop_after.pop("tray_restore", None)
        if restore is not None:
            self.window.after_cancel(restore)
        self._close_group_celebration(restore_pet=False)
        self._stop_cameo()
        self._set_pet_visibility(False)
        self._dismiss_toast()
        if hasattr(self, "tray") and self.tray:
            self.tray.set_visible_state(False)

    def show_from_tray(self) -> None:
        restore = self._loop_after.pop("tray_restore", None)
        if restore is not None:
            self.window.after_cancel(restore)
        else:
            self._tray_restore_failures = 0  # a fresh, explicit user request
        if self.standby_overlay is not None or getattr(self, "_standby_resume_pending", False):
            return
        if is_workstation_locked() is True:
            return
        try:
            ready = self._restore_pet_window()
        except Exception:
            ready = False
        if not ready:
            self._retry_desktop_restore("tray")
            return
        self._tray_restore_failures = 0
        self.trigger_cheer(cycles=2, kind="tray.wake")
        self._toast(t("welcome_back", self.lang), duration_ms=2500)

    show_and_lift_pet = show_from_tray

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self.settings["lang"] = lang
        self.cameo.lang = lang
        self.save_settings()
        if hasattr(self, "tray") and self.tray:
            self.tray.set_language(lang)
        self.build_menu()
        self._refresh_status_card()
        self._refresh_birthday_dialog()
        self._refresh_fortune_dialog()
        self._refresh_profile_card()
        self._refresh_food_panel()
        self._refresh_settings_panel()
        self._refresh_notification_drawer()
        self._toast(t("lang_switched_toast", self.lang), duration_ms=2000)

    def set_bubble_theme(self, theme_key: str) -> None:
        self.settings["bubble_theme"] = theme_key
        self.save_settings()
        self.build_menu()
        theme_name = get_theme_display_name(theme_key, self.lang)
        switched_msg = t("theme_switched", self.lang, theme=theme_name)
        self._toast(switched_msg, duration_ms=2500)   # was self.say(): no such method

    def _want_edge_refine(self, display_px: int | None = None) -> bool:
        """Enable 8-bit 8x contour refinement whenever ULW is active, at every pet size.

        2026-11-22: 144 px used to skip it; the unrefined path keeps light stair-step pixels
        on the dark contour (and unsharp-mask overshoot), visible on a 96 DPI small pet.
        """
        return bool(getattr(self, "_use_ulw", False))

    def set_pet_size(self, size_key: str) -> None:
        if size_key not in PET_SIZE_MAP or size_key == self.settings.get("pet_size"):
            return
        self.settings["pet_size"] = size_key
        self.save_settings()

        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height)
        target_px = pet_display_px(size_key, ui_scale(self.window), area)
        want_refine = self._want_edge_refine(target_px)
        if hasattr(self.sprites, "resize") and getattr(self.sprites, "resource_root", None) == RES_ROOT:
            try:
                self.sprites.resize(target_px, edge_refine=want_refine)
            except TypeError:
                self.sprites.resize(target_px)
        else:
            self.sprites = SpriteLibrary(
                RES_ROOT,
                display_px=target_px,
                equalize=True,
                binary_alpha=not getattr(self, "_use_ulw", False),
                edge_refine=want_refine,
            )
        self.guest_sprites = self.sprites
        if isinstance(getattr(self, "_ulw_composed_cache", None), OrderedDict):
            self._ulw_composed_cache.clear()
        else:
            self._ulw_composed_cache = OrderedDict()
        self.flipped_walk_cache.clear()
        self._actions().clear()
        self._actions().set_budget(action_cache_budget(self.sprites.display_px))
        if getattr(self, "_celebration_photos", None) is not None:
            self._celebration_photos.clear()
        self.load_character_frames(self.char_key)

        w_new = self.frames["idle"][0].width()
        h_new = self.frames["idle"][0].height()
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height)
        self.x, self.y = rescale_pet_window(self.x, self.y, self.width, self.height, w_new, h_new, area)
        self.width, self.height = w_new, h_new

        # Re-fit the active action; the one guarded resize hides the new layered surface
        # until Tk has painted it (an unguarded canvas/geometry change flashed a black box).
        self._frame_pad, self._shown_action = (0, 0, 0, 0), None
        self._refresh_visual_appearance(force_box=True)
        self.build_menu()
        self.ensure_topmost()
        self._toast(t("size_switched_toast", self.lang), duration_ms=2500)

    def set_text_size(self, text_size_key: str) -> None:
        if text_size_key not in ("small", "medium", "large") or text_size_key == self.settings.get("text_size"):
            return
        self.settings["text_size"] = text_size_key
        self.save_settings()
        self.build_menu()
        self._toast(t("size_switched_toast", self.lang), duration_ms=2500)

    def preview_standby_scene(self, scene_name: str) -> None:
        self.record_activity()
        if self.standby_overlay:
            try:
                self.standby_overlay.dismiss()
            except Exception:
                pass
            self.standby_overlay = None
        PandaPet._schedule_once_after(
            self,
            "standby_preview",
            self.root,
            120,
            lambda: None if getattr(self, "_closing", False) else self.open_standby_screen(scene=scene_name),
        )

    def _christmas_look(self, member: str) -> str:
        """The Christmas animation or one of the member's Christmas poses, in turn at random."""
        return random.choice((CHRISTMAS_ACTION, *xmas_poses(self.sprites, member)))

    def _action_duration_s(self, frames, frame_ms: int) -> float:
        """Whole passes of the animation; a single-image pose is simply held."""
        if len(frames) == 1:
            return SEASONAL_POSE_S
        one_pass_s = len(frames) * frame_ms / 1000.0
        return max(1, math.ceil(SPECIAL_MIN_S / one_pass_s)) * one_pass_s

    def _play_auto_action(self, action: str, kind: str) -> float:
        """Idle-time show (L1, so it never displaces anything): its seconds, 0 if not played."""
        loaded = self._action_frames(self.char_key, action)
        if loaded is None:
            return 0.0
        duration = self._action_duration_s(loaded[0], loaded[1])
        req = EventRequest(kind=kind, priority=Priority.SPONTANEOUS, state=ActorState.SPECIAL,
                           action=action, duration_s=duration)
        return duration if self.coord.submit(req).accepted else 0.0

    def _auto_show_busy(self) -> bool:
        return (self.group_celebration is not None or self.anniversary_scene is not None
                or self.new_year_clock is not None or self.cameo_window is not None)

    def _maybe_signature_action(self, now: float) -> float:
        """Every few minutes of idling the member does one of her signature moves."""
        if now < self.next_signature_at or not self.settings.get("daily_signature_enabled", True):
            return 0.0
        if self._active_festival_costume() is not None:
            return 0.0
        if self._auto_show_busy():
            return 0.0
        self.next_signature_at = now + random.uniform(*SIGNATURE_INTERVAL_S)
        member = self.char_key
        action = pick_signature(available_actions(self.sprites, member, SIGNATURE_POOL.get(member, ())),
                                self._last_signature.get(member))
        duration = self._play_auto_action(action, "daily.signature") if action else 0.0
        if duration:
            self._last_signature[member] = action
        return duration

    def _active_festival_costume(self) -> str | None:
        """Scheme 2: approved festival costume worn all day while active, else None."""
        if not self.settings.get("festival_auto_enabled", True):
            return None
        today = self.calendar.clock.now().date() if hasattr(self, "calendar") else datetime.date.today()
        festival = festival_on(today)
        if festival is None:
            return None
        return festival.action if self._action_frames(self.char_key, festival.action) is not None else None

    def _festival_state_key(self) -> tuple[str | None, bool, str | None]:
        enabled = bool(self.settings.get("festival_auto_enabled", True))
        today = self.calendar.clock.now().date() if hasattr(self, "calendar") else datetime.date.today()
        festival = festival_on(today)
        return (festival.key if festival else None, enabled, self._active_festival_costume())

    def _maybe_natural_action(self, now: float) -> float:
        """Between signature moves: a wave, a stretch, a passing expression."""
        if now < self.next_natural_at or not self.settings.get("daily_signature_enabled", True):
            return 0.0
        if self._active_festival_costume() is not None:
            return 0.0
        if self._auto_show_busy() or self.next_signature_at - now < SIGNATURE_RESERVE_S:
            return 0.0
        self.next_natural_at = now + random.uniform(*NATURAL_INTERVAL_S)
        member = self.char_key
        pools = [available_actions(self.sprites, member, table.get(member, ()))
                 for table in (NATURAL_ANIMATIONS, NATURAL_POSES, RARE_POSES)]
        action = pick_natural(*pools, self._last_natural.get(member))
        duration = self._play_auto_action(action, "daily.natural") if action else 0.0
        if duration:
            self._last_natural[member] = action
        return duration

    def _play_reaction(self, table: dict, kind: str, pose_s: float, *, first=(), once: bool = False) -> bool:
        """The user's own action gets this member's reaction; False when she has none.

        Names are tried in order (``first``, then the table's) and the first one drawn for her
        plays. ``once`` plays an animation a single pass: a tap or a pat is a quick moment.
        """
        loaded = action = None
        for action in (*first, *table.get(self.char_key, ())):
            loaded = self._action_frames(self.char_key, action)
            if loaded is not None:
                break
        if loaded is None:
            return False
        frames, frame_ms = loaded[0], loaded[1]
        if len(frames) == 1:
            duration = pose_s
        elif once:
            duration = len(frames) * frame_ms / 1000.0
        else:
            duration = self._action_duration_s(frames, frame_ms)
        req = EventRequest(kind=kind, priority=Priority.USER, state=ActorState.SPECIAL,
                           action=action, duration_s=duration)
        return self.coord.submit(req).accepted

    def _react_to_tap(self, head: bool = False) -> None:
        """A plain click: a quick look (a pat on the head), never over something already playing."""
        now = time.time()
        if now < self._next_tap_at or self.state != "idle" or self.coord.snapshot().active is not None:
            return
        self._next_tap_at = now + TAP_COOLDOWN_S
        if self._active_festival_costume() is not None:
            self.trigger_cheer(cycles=1, priority=Priority.USER,
                               kind="interaction.pat" if head else "interaction.tap")
            return
        self._play_reaction(PAT_REACTION if head else TAP_REACTION,
                            "interaction.pat" if head else "interaction.tap", TAP_REACTION_S, once=True)

    def _festival_look(self, festival) -> str:
        if festival is CHRISTMAS:
            poses = xmas_poses(self.sprites, self.char_key)
            if poses and random.random() >= CHRISTMAS_V3_SHARE:
                return random.choice(poses)
        return festival.action

    def _maybe_festival_action(self, now: float) -> float:
        """On a festival day a roam decision may become that festival's action instead."""
        if now < self.next_festival_at or not self.settings.get("festival_auto_enabled", True):
            return 0.0
        festival = festival_on(self.calendar.clock.now().date())
        if festival is None or self._auto_show_busy() or random.random() >= festival.chance:
            return 0.0
        duration = self._play_auto_action(self._festival_look(festival), f"festival.{festival.key}")
        if duration:
            self.next_festival_at = now + FESTIVAL_COOLDOWN_S
        return duration

    def preview_christmas_event(self) -> None:
        self.record_activity()
        self.celebrate_together(
            host_action=self._christmas_look(self.char_key),
            guest_action=self._christmas_look,
            is_preview=True,
        )
        christmas_speeches = {
            "zh_TW": "🎄 Merry Christmas！聖誕快樂，願溫暖與平安伴隨每位粉熊～❄️💖",
            "ko": "🎄 메리 크리스마스! 따뜻하고 행복한 성탄절 보내요, 사랑해요 판다들～❄️💖",
            "en": "🎄 Merry Christmas! Wishing all pandas warmth, joy and peace~ ❄️💖",
        }
        speech = christmas_speeches.get(self.lang, christmas_speeches["zh_TW"])
        header = {
            "zh_TW": "🎄 聖誕節特別祝賀",
            "ko": "🎄 크리스마스 스페셜",
            "en": "🎄 Merry Christmas Special",
        }.get(self.lang, "🎄 聖誕節特別祝賀")
        self._toast(speech, duration_ms=6000, header=header, badge_text="Christmas Event 🎁")

    def preview_new_year_event(self) -> None:
        """Jan 1 manual preview: all five celebrate without mutating state or countdown history."""
        self.record_activity()
        self.celebrate_together(
            host_action=self._new_year_look(self.char_key),
            guest_action=self._new_year_look,
            is_preview=True,
        )
        speeches = {
            "zh_TW": "🎊 Happy New Year！新的一年開始囉，五隻熊貓陪你開啟充滿元氣的每一天～✨",
            "ko": "🎊 새해 첫날이 밝았어요! 에이핑크 다섯 판다와 함께 희망찬 새해를 시작해요～✨",
            "en": "🎊 Happy New Year's Day! All five pandas wish you an energetic and joyful new year~ ✨",
        }
        title = t("preview_event_new_year", self.lang)
        self._toast(speeches.get(self.lang, speeches["zh_TW"]), duration_ms=6000, header=title)

    def preview_festival_event(self, action: str, title: str) -> None:
        """Lunar New Year / Lantern / Mid-Autumn: all five temporarily in that festival's costume."""
        self.record_activity()
        self.celebrate_together(host_action=action, guest_action=action, is_preview=True)
        key = PREVIEW_ACTION_FESTIVAL.get(action)
        greeting = festival_greeting(key, self.char_key, self.lang) if key else None
        self._toast(greeting or title, duration_ms=6000, header=title)

    def is_festival_preview_active(self) -> bool:
        return bool(getattr(self, "_festival_preview_active", False) and self.group_celebration is not None)

    def cancel_festival_preview(self) -> bool:
        """Stop an active manual holiday preview and restore today's real costume or everyday pose."""
        was_preview = bool(getattr(self, "_festival_preview_active", False))
        if not was_preview:
            return False
        self._close_group_celebration()
        self._dismiss_toast()
        self._refresh_visual_appearance()
        return True

    def _musical_look(self, member: str) -> str:
        """A gown dance where she has one drawn, otherwise her gown pose."""
        dances = available_actions(self.sprites, member, ("musical_step", "musical_swish", "musical_bow"))
        return random.choice(dances) if dances else "musical_pose"

    def preview_musical_event(self) -> None:
        """All five in their royal musical gowns."""
        self.record_activity()
        self.celebrate_together(host_action=self._musical_look(self.char_key), guest_action=self._musical_look)
        title = t("preview_event_musical", self.lang)
        self._toast(title, duration_ms=6000, header=title)

    def preview_dome_baseball_event(self) -> None:
        """All five synced at Taipei Dome cheering with trilingual overhead banner."""
        self.record_activity()
        self._close_group_celebration()
        try:
            self.dome_preview = DomeDesktopPreview(
                self,
                "baseball",
                load_action_fn=load_exact_action,
                available_fn=available_actions,
                on_done=self._on_dome_preview_done,
            )
        except Exception:
            log.exception("dome baseball preview failed")
            self.dome_preview = None
            self._set_pet_visibility(True)
            return
        PandaPet._apply_cursor_to_panel(self, self.dome_preview)

    def preview_eunji_dome_event(self) -> None:
        """Eunji center-stage dreaming of a future Taipei Dome solo concert with 4 flanks."""
        self.record_activity()
        self._close_group_celebration()
        try:
            self.dome_preview = DomeDesktopPreview(
                self,
                "eunji_dream",
                load_action_fn=load_exact_action,
                available_fn=available_actions,
                on_done=self._on_dome_preview_done,
            )
        except Exception:
            log.exception("eunji dome preview failed")
            self.dome_preview = None
            self._set_pet_visibility(True)
            return
        PandaPet._apply_cursor_to_panel(self, self.dome_preview)
        self._toast(
            t("dome_eunji_dream_msg", self.lang),
            duration_ms=7000,
            header=t("dome_eunji_dream_title", self.lang),
            badge_text="Future Dream 🩷",
        )

    def preview_new_year_countdown(self) -> None:
        """Try-out of the New Year's Eve clock: ten seconds, then the celebration."""
        self.record_activity()
        self._start_new_year_clock(10)

    def _start_new_year_clock(self, seconds: int) -> None:
        if self.new_year_clock is not None:
            return
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height // 2)
        try:
            self.new_year_clock = NewYearCountdown(
                self.root, seconds, (self.x, self.y, self.width, self.height),
                (area.left, area.top, area.right, area.bottom), self.lang, self._on_new_year_clock_done)
        except Exception:
            log.exception("new year clock failed")
            self.new_year_clock = None
            if self._ny_pending_clock_year is not None:
                self._new_year_celebrated = True
                self._new_year_celebrated_year = self._ny_pending_clock_year
                self._ny_pending_clock_year = None
                self._celebrate_new_year(mark_welcome=True)
            else:
                self._celebrate_new_year(is_preview=True)
        else:
            PandaPet._apply_cursor_to_panel(self, self.new_year_clock)

    def _on_new_year_clock_done(self) -> None:
        self.new_year_clock = None
        real_event = self._ny_pending_clock_year is not None
        if real_event:
            self._new_year_celebrated = True
            self._new_year_celebrated_year = self._ny_pending_clock_year
            self._ny_pending_clock_year = None
        self._celebrate_new_year(mark_welcome=real_event, is_preview=not real_event)

    def _close_new_year_clock(self) -> None:
        self._ny_pending_clock_year = None
        clock, self.new_year_clock = self.new_year_clock, None
        if clock is not None:
            clock.cancel()

    def _new_year_look(self, member: str) -> str:
        """Prefer dedicated Jan 1 costume when approved, else lightstick cheer (never Lunar NY hanbok)."""
        return NEW_YEAR.action if self._action_frames(member, NEW_YEAR.action) is not None else CHEER_LIGHTSTICK_ACTION

    def _celebrate_new_year(self, *, mark_welcome: bool = False, is_preview: bool = False) -> None:
        if mark_welcome:
            today = self.calendar.clock.now().date() if hasattr(self, "calendar") else datetime.date.today()
            pair = festival_occurrence_key(today)
            if pair is not None and pair[0] is NEW_YEAR:
                self._mark_festival_welcome_seen(pair[1])
        self.celebrate_together(
            host_action=self._new_year_look(self.char_key),
            guest_action=self._new_year_look,
            is_preview=is_preview,
        )
        ny_speeches = {
            "zh_TW": "🎆 5... 4... 3... 2... 1... 跨年快樂！🎉✨\nApink 全員祝最親愛的粉熊：新的一年健康平安、心想事成！永遠在一起～💖",
            "ko": "🎆 5... 4... 3... 2... 1... 새해 복 많이 받으세요! 🎉✨\n에이핑크가 판다의 새로운 한 해를 온 마음으로 응원해요! 사랑해요～💖",
            "en": "🎆 5... 4... 3... 2... 1... Happy New Year! 🎉✨\nApink wishes our dearest panda a wonderful year full of joy and love! Forever together~ 💖",
        }
        speech = ny_speeches.get(self.lang, ny_speeches["zh_TW"])
        header = {
            "zh_TW": "🎆 跨年特別歡呼倒數",
            "ko": "🎆 새해 카운트다운 스페셜",
            "en": "🎆 New Year's Eve Countdown",
        }.get(self.lang, "🎆 跨年特別歡呼倒數")
        self._toast(speech, duration_ms=8000, header=header, badge_text="Happy New Year 🎆")

    def _check_new_year_countdown(self) -> None:
        """Countdown system for Dec 31st 23:30 ~ Jan 1st missed-midnight catchup."""
        if getattr(self, "standby_overlay", None) is not None:
            return
        dt_now = self.calendar.clock.now() if hasattr(self, "calendar") else datetime.datetime.now()
        month, day, hour, minute, second = dt_now.month, dt_now.day, dt_now.hour, dt_now.minute, dt_now.second
        if month == 12 and day == 31:
            target_year = dt_now.year + 1
            if self._ny_countdown_year != target_year:
                self._ny_countdown_year = target_year
                self._ny_announced_minutes.clear()
                self._ny_announced_secs.clear()
                self._new_year_celebrated = (self._new_year_celebrated_year == target_year)
            if hour == 23 and minute >= 30:
                if minute < 59:
                    if minute not in self._ny_announced_minutes:
                        self._ny_announced_minutes.add(minute)
                        rem_min = 60 - minute
                        header = t("newyear_countdown_header", self.lang)
                        msg = t("newyear_countdown_toast", self.lang, m=rem_min)
                        badge_text = t("newyear_countdown_badge", self.lang, m=rem_min)
                        self._toast(msg, duration_ms=4000, header=header, badge_text=badge_text)
                else:
                    if second < 10 and 59 not in self._ny_announced_minutes:
                        self._ny_announced_minutes.add(59)
                        header = t("newyear_countdown_header", self.lang)
                        self._toast(t("newyear_countdown_toast", self.lang, m=1), duration_ms=4000,
                                    header=header, badge_text=t("newyear_countdown_badge", self.lang, m=1))
                    elif 10 <= second < 30:
                        milestone = 10 if second < 20 else 20
                        if milestone not in self._ny_announced_secs:
                            self._ny_announced_minutes.add(59)
                            self._ny_announced_secs.update(range(10, milestone + 1, 10))
                            rem_sec = 60 - second
                            self._toast(t("newyear_countdown_sec", self.lang, s=rem_sec),
                                        duration_ms=1200, badge_text=f"{rem_sec}s ⏰")
                    elif second >= 30 and self.new_year_clock is None and not getattr(self, "_new_year_celebrated", False):
                        self._ny_pending_clock_year = target_year
                        self._start_new_year_clock(60 - second)
        elif month == 1 and day == 1:
            target_year = dt_now.year
            seen = self.runtime.get("festival_welcome_seen")
            if self._ny_countdown_year != target_year:
                self._ny_countdown_year = target_year
                self._ny_announced_minutes.clear()
                self._ny_announced_secs.clear()
                self._new_year_celebrated = (self._new_year_celebrated_year == target_year)
            if (self._new_year_celebrated_year != target_year
                    and not getattr(self, "_new_year_celebrated", False)
                    and not (isinstance(seen, dict) and seen.get(f"new_year:{target_year}"))
                    and self.new_year_clock is None):
                if self.coord.mode is GlobalMode.NORMAL and not self.dragging:
                    self._new_year_celebrated = True
                    self._new_year_celebrated_year = target_year
                    self._celebrate_new_year(mark_welcome=True)

    def _mark_festival_welcome_seen(self, occ_key: str) -> None:
        pending = self._loop_after.pop("festival_welcome", None)
        if pending is not None and hasattr(self, "window"):
            try:
                self.window.after_cancel(pending)
            except Exception:
                pass
        seen = self.runtime.get("festival_welcome_seen")
        if not isinstance(seen, dict):
            seen = {}
            self.runtime["festival_welcome_seen"] = seen
        if seen.get(occ_key) is True:
            return
        seen[occ_key] = True
        self.save_settings()

    def _schedule_festival_welcome(self, delay_ms: int = 350) -> None:
        if (getattr(self, "_closing", False) or not hasattr(self, "window")
                or not hasattr(self, "_loop_after")):
            return
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
            return
        old = self._loop_after.pop("festival_welcome", None)
        if old is not None:
            try:
                self.window.after_cancel(old)
            except Exception:
                pass
        self._loop_after["festival_welcome"] = self.window.after(delay_ms, self._maybe_festival_welcome)

    def _maybe_festival_welcome(self) -> bool:
        """First-encounter real-festival ritual: all five play a brief welcome once per festival occurrence."""
        if not self.settings.get("festival_auto_enabled", True):
            return False
        if (self.coord.mode not in (GlobalMode.NORMAL, GlobalMode.CAMEO)
                or getattr(self, "standby_overlay", None) is not None):
            return False
        today = self.calendar.clock.now().date() if hasattr(self, "calendar") else datetime.date.today()
        pair = festival_occurrence_key(today)
        if pair is None:
            return False
        festival, occ_key = pair
        seen = self.runtime.get("festival_welcome_seen")
        if isinstance(seen, dict) and seen.get(occ_key):
            return False
        if self.coord.mode is GlobalMode.CAMEO or self.dragging or self._auto_show_busy():
            self._schedule_festival_welcome(delay_ms=1500)
            return False
        self._mark_festival_welcome_seen(occ_key)
        if festival is NEW_YEAR:
            self._new_year_celebrated = True
            self._new_year_celebrated_year = today.year
            host_action = self._new_year_look(self.char_key)
            guest_action = self._new_year_look
        elif festival is CHRISTMAS:
            host_action = self._christmas_look(self.char_key)
            guest_action = self._christmas_look
        else:
            host_action = festival.action
            guest_action = festival.action
        self.celebrate_together(duration_ms=4500, host_action=host_action, guest_action=guest_action)
        fest_name = t(f"festival_name_{festival.key}", self.lang)
        self._toast(
            festival_greeting(festival.key, self.char_key, self.lang)
            or t("festival_welcome_msg", self.lang, festival=fest_name),
            duration_ms=4500,
            header=t("festival_welcome_title", self.lang),
        )
        return True

    def celebrate_together(self, duration_ms: int = 8000, host_action: str = BIRTHDAY_ACTION,
                           guest_action=BIRTHDAY_ACTION, secret_visitor: bool = False,
                           is_preview: bool = False) -> None:
        """The pet plays host_action and the other four join her (guest_action may pick per member).

        The host keeps her costume as long as her guests do: a hanbok pose alone would end
        after a few seconds and leave her in everyday clothes beside four guests in hanbok.
        """
        self._close_group_celebration()
        self._festival_preview_active = bool(is_preview)
        hold_s = duration_ms / 1000.0
        if (not self.trigger_special_action(host_action, kind="celebrate.together", hold_s=hold_s)
                and not self.trigger_special_action(CHEER_LIGHTSTICK_ACTION, kind="celebrate.together",
                                                    hold_s=hold_s)):
            self.trigger_cheer(cycles=3)
        # Compute host's expanded bounds and warm host frames before opening guests so the host
        # does not dance solo while the four guest windows are still decoding.
        shown = self._visual_action()
        facing = self._visual_facing(shown)
        pad = (0, 0, 0, 0)
        loaded = self._visual_pil_frames_and_offset(self.char_key, shown, facing) if shown else None
        if loaded is not None:
            (dx, dy), first = loaded[2], loaded[0][0]
            fw, fh = first.width, first.height
            pad = (max(0, -dx), max(0, -dy), max(0, dx + fw - self.width), max(0, dy + fh - self.height))
        host_bounds = (self.x - pad[0], self.x + self.width + pad[2])
        guests: list[str | None] = [m for m in MEMBER_KEYS if m != self.char_key]
        if secret_visitor:
            guests.insert(0, None)
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height // 2)
        try:
            guest_lib = getattr(self, "guest_sprites", None) or self.sprites
            self.group_celebration = GroupCelebration(
                self.root, guest_lib, guests, (self.x, self.y, self.width, self.height),
                (area.left, area.right), action=guest_action, duration_ms=duration_ms,
                on_done=self._on_group_celebration_done, visitor_action=SECRET_VISITOR_ACTION,
                host_bounds=host_bounds,
                photo_cache=getattr(self, "_celebration_photos", None),
                on_placed=self._on_group_celebration_placed, stagger=False,
                use_layered=getattr(self, "_use_ulw", None),
            )
            PandaPet._apply_cursor_to_panel(self, self.group_celebration)
        except Exception:
            log.exception("group celebration failed")
            self.group_celebration = None
            self._festival_preview_active = False
            self._refresh_visual_appearance()
            return
        self.frame_idx = 0
        party = self.group_celebration
        if party is not None and isinstance(getattr(party, "guest_scale", 1.0), float) and party.guest_scale < 1.0:
            self._set_host_party_scale(party.guest_scale)   # refreshes the host box itself
        else:
            self._refresh_visual_appearance()
        if self.group_celebration is not None:
            self.group_celebration._t0 = time.monotonic()
        try:
            self.window.lift()                       # the host stays in front of her guests
            surf = getattr(self, "layered_surface", None)
            if surf is not None and not surf.closed and surf.visible:
                surf.set_visibility(True, reorder=True)
        except tk.TclError:
            pass
        self._lift_bubble()

    def _on_group_celebration_placed(self, party: GroupCelebration) -> None:
        """Cold guests open a few Tk turns after the host starts: give them the cursor, host in front."""
        if party is not getattr(self, "group_celebration", None):
            return          # placed inside the constructor; celebrate_together does this right after
        PandaPet._apply_cursor_to_panel(self, party)
        if isinstance(getattr(party, "guest_scale", 1.0), float) and party.guest_scale < 1.0:
            self._set_host_party_scale(party.guest_scale)
        try:
            self.window.lift()
            surf = getattr(self, "layered_surface", None)
            if surf is not None and not surf.closed and surf.visible:
                surf.set_visibility(True, reorder=True)
        except tk.TclError:
            pass
        self._lift_bubble()

    def _on_group_celebration_done(self) -> None:
        self.group_celebration = None
        self._set_host_party_scale(1.0)
        self._schedule_memory_reclaim()
        was_preview = getattr(self, "_festival_preview_active", False)
        self._festival_preview_active = False
        if was_preview:
            active = self.coord.snapshot().active
            if active is not None and active.request.kind == "celebrate.together":
                self.coord.cancel(active.event_id, "preview_finished")
            self._refresh_visual_appearance()
        self._schedule_festival_welcome()

    def _close_group_celebration(self, *, restore_pet: bool = True) -> None:
        was_preview = getattr(self, "_festival_preview_active", False)
        self._festival_preview_active = False
        dome_prev, self.dome_preview = getattr(self, "dome_preview", None), None
        if dome_prev is not None:
            try:
                dome_prev.close(restore_pet=restore_pet)
            except Exception:
                log.exception("dome preview close failed")
        scene, self.anniversary_scene = self.anniversary_scene, None
        if scene is not None:
            scene.close()
        party, self.group_celebration = self.group_celebration, None
        if party is not None:
            try:
                party.close()
            except Exception:
                log.exception("group celebration close failed")
        if restore_pet:
            self._set_host_party_scale(1.0)
        else:
            self._host_party_scale = 1.0
        if party is not None or scene is not None:
            self._schedule_memory_reclaim()
        if was_preview:
            active = self.coord.snapshot().active
            if active is not None and active.request.kind == "celebrate.together":
                self.coord.cancel(active.event_id, "preview_cancelled")
        if was_preview or party is not None or scene is not None or dome_prev is not None:
            self._schedule_festival_welcome()

    def _open_anniversary_scene(self) -> None:
        """The group photo stands in for the pet (she is in it), who returns when it ends."""
        self._close_group_celebration()
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height // 2)
        try:
            guest_lib = getattr(self, "guest_sprites", None) or self.sprites
            self.anniversary_scene = AnniversaryScene(
                self.root, guest_lib, RES_ROOT / "work" / "scenes" / "anniversary_419",
                (self.x, self.y, self.width, self.height), (area.left, area.top, area.right, area.bottom),
                on_done=self._on_anniversary_scene_done,
                use_layered=getattr(self, "_use_ulw", None),
            )
        except Exception:
            log.exception("anniversary scene failed")
            self.anniversary_scene = None
            self.celebrate_together(secret_visitor=True)
            return
        PandaPet._apply_cursor_to_panel(self, self.anniversary_scene)
        self._set_pet_visibility(False)

    def _on_profile_card_closed(self) -> None:
        self.profile_card = None

    def _on_dome_preview_done(self) -> None:
        self.dome_preview = None
        self._schedule_memory_reclaim()

    def _on_anniversary_scene_done(self) -> None:
        self.anniversary_scene = None
        self._schedule_memory_reclaim()
        try:
            self._set_pet_visibility(True)
            self.ensure_topmost()
        except tk.TclError:
            pass

    def preview_anniversary_event(self) -> None:
        self.record_activity()
        self._open_anniversary_scene()
        anniv_speeches = {
            "zh_TW": "💖 419 是 Apink 與粉熊的出道紀念日！永遠是 Apink，永遠在一起～✨🐼",
            "ko": "💖 4월 19일, 에이핑크와 판다의 데뷔 기념일! 영원히 우리는 에이핑크, 영원히 함께해요～✨🐼",
            "en": "💖 April 19, Apink & Panda Debut Anniversary! Forever Apink, forever together~ ✨🐼",
        }
        speech = anniv_speeches.get(self.lang, anniv_speeches["zh_TW"])
        header = {
            "zh_TW": "💖 Apink 419 出道週年慶典",
            "ko": "💖 에이핑크 419 데뷔 기념일",
            "en": "💖 Apink 419 Debut Anniversary",
        }.get(self.lang, "💖 Apink 419 出道週年慶典")
        self._toast(speech, duration_ms=6000, header=header, badge_text="Apink 419 🎂")

    def preview_birthday_event(self) -> None:
        self.record_activity()
        self.celebrate_together()
        bday_speeches = {
            "chorong": {
                "zh_TW": "今天是初瓏隊長的生日！🎂 讓我們一起祝瓏隊長生日快樂～",
                "ko": "오늘은 롱리더 박초롱의 생일! 🎂 초롱이의 생일을 축하해주세요～",
                "en": "Today is Leader Chorong's Birthday! 🎂 Happy Birthday to Chorong~",
            },
            "bomi": {
                "zh_TW": "今天是吃貨小太陽普美的生日！🍗 準備好大餐為普美慶生啦～",
                "ko": "오늘은 뽀미 윤보미의 생일! 🍗 맛있는 거 듬뿍 먹고 행복한 생일～",
                "en": "Today is Bomi's Birthday! 🍗 Feast time to celebrate Bomi's day~",
            },
            "eunji": {
                "zh_TW": "今天是恩地的生日！🎤 靈魂主唱恩地生日快樂，永遠為妳應援！",
                "ko": "오늘은 정은지의 생일! 🎤 우리 메인보컬 믕지 생일 축하해, 영원히 응원해!",
                "en": "Today is Eunji's Birthday! 🎤 Happy birthday to our main vocal Eunji!",
            },
            "namjoo": {
                "zh_TW": "今天是活力南珠的生日！💖 祝甜美可愛的小太陽南珠生日快樂！",
                "ko": "오늘은 비타민 김남주의 생일! 💖 사랑스러운 남주 생일 많이 축하해주세요!",
                "en": "Today is Namjoo's Birthday! 💖 Wishing sweet sunshine Namjoo happy birthday!",
            },
            "hayoung": {
                "zh_TW": "今天是忙內夏榮的生日！🎮 熱騰騰的烤地瓜與滿滿祝福送達！",
                "ko": "오늘은 막내 오하영의 생일! 🎮 달콤한 군고구마와 따뜻한 축하를 보내요!",
                "en": "Today is Maknae Hayoung's Birthday! 🎮 Sweet sweet potatoes & best wishes!",
            },
        }
        sp_map = bday_speeches.get(self.char_key, bday_speeches["chorong"])
        speech = sp_map.get(self.lang, sp_map["zh_TW"])
        header = f"🎂 {get_member_display_name(self.char_key, self.lang)} Birthday"
        self._toast(speech, duration_ms=6000, header=header, badge_text="Happy Birthday 🎉")

    def preview_user_birthday_event(self) -> None:
        self.record_activity()
        self.celebrate_together()
        nick = (
            self.settings.get("user_nickname")
            or getattr(self.calendar, "user_nickname", None)
            or DEFAULT_NICKNAME
        )
        user_bday_speeches = {
            "chorong": {
                "zh_TW": f"親愛的朋友 {nick}，生日快樂！🎂 感謝你來到這個世界上，也感謝你的青春裡有 Apink 的旋律。隊長初瓏願你的新一歲每天都被溫柔與平安擁抱～謝謝你一直默默守護我們！🌸💖",
                "ko": f"소중한 우리 {nick}, 생일 축하해요!🎂 세상에 태어나줘서, 그리고 에이핑크의 노래를 함께해 줘서 진심으로 고마워요. 롱리더가 온 마음 다해 따뜻함과 평온을 빌어줄게요～ 사랑해요!🌸💖",
                "en": f"Dearest {nick}, Happy Birthday! 🎂 Thank you for gracing the world with your presence, and for letting Apink be the soundtrack of your youth. May your new year be wrapped in gentle peace and joy~ 🌸💖",
            },
            "bomi": {
                "zh_TW": f"嗷嗚～今天全宇宙最重要的 VIP 就是 {nick} 啦！🎉 生日快樂！今天的減肥菜單通通作廢，炸醬麵、炸雞隨便吃！普美要把一整年份的大笑元氣通通灌注給你，許的願望全都要成真喔！啾咪！🍗😆",
                "ko": f"와아아～ 오늘 우주 최고의 주인공은 바로 {nick}!🎉 생일 축하해요! 오늘만큼은 다이어트 금지, 짜장면에 치킨 맘껏 먹는 날이에요! 뽀미의 웃음 비타민 풀충전해서 쏩니다! 뿅!🍗😆",
                "en": f"Woof! The official VIP of the universe today is {nick}! 🎉 Happy Birthday! Forget diets today—eat all the Jajangmyeon and fried chicken you crave! Bomi sends a million megawatts of laughter your way! Chu! 🍗😆",
            },
            "eunji": {
                "zh_TW": f"Hey {nick}！祝你生日大快樂啊！🎤 又平安健康地長大了一歲，真替你驕傲！今天恩地把最高音的祝福唱給你聽，願你走過的每一條路都繁花似錦！今晚記得跟重要的人乾一杯喔！乾杯～🍻🎵",
                "ko": f"야～ 우리 {nick}! 생일 축하한다!🎤 건강하게 한 살 더 멋지게 자라줘서 뿌듯해! 오늘 은지가 시원한 3단 고음 축가 불러줄게. 걷는 길마다 꽃길만 펼쳐지길. 시원하게 짠하자!🍻🎵",
                "en": f"Hey {nick}! Happy Birthday to you! 🎤 So proud to see you grow another wonderful year. Eunji's belting out a personal high-note anthem for you today! May flowers bloom along every path you tread. Cheers! 🍻🎵",
            },
            "namjoo": {
                "zh_TW": f"最最可愛的 {nick} 生日快樂！☀️ 今天南珠小太陽只為你一個人升起！把所有的煩惱都丟掉，吃口甜甜的蛋糕，接收滿滿的幸運維他命！今年一定要成為全世界最幸福的人喔～😋💖",
                "ko": f"세상에서 제일 사랑스러운 {nick}, 생일 축하해요!☀️ 오늘 남주 해님은 오직 당신만을 위해 떠올랐어요! 달콤한 케이크 한입 베어 물고 행복 바이러스 듬뿍 받기 약속! 세상에서 제일 행복해요～😋💖",
                "en": f"Dearest {nick}, Happy Birthday! ☀️ Namjoo's sunshine is shining exclusively for you today! Toss away all worries, take a huge bite of sweet cake, and absorb pure joy. You deserve the absolute happiest year! 😋💖",
            },
            "hayoung": {
                "zh_TW": f"忙內夏榮祝 {nick} 生日快樂！🎮 今天在人生的排位賽裡，你就是全場 MVP！剛出爐香噴噴的烤地瓜分你最大的一塊～今天不用努力工作，盡情享受屬於你的狂歡派對吧！耶～🍠🏆",
                "ko": f"막내 하영이가 우리 {nick} 생일 축하해요!🎮 오늘 인생 랭크전의 단독 MVP는 바로 당신! 갓 구운 달콤한 군고구마 제일 큰 걸로 양보할게요～ 오늘은 열일 말고 신나게 즐겨요! 앗싸～🍠🏆",
                "en": f"Maknae Hayoung wishes {nick} the happiest birthday! 🎮 You're the unquestioned MVP in the ranked match of life today! Handing you the largest piping-hot sweet potato~ Have the ultimate victory blast today! 🍠🏆",
            },
        }
        sp_map = user_bday_speeches.get(self.char_key, user_bday_speeches["chorong"])
        speech = sp_map.get(self.lang, sp_map["zh_TW"])
        header = {
            "zh_TW": f"🎉 祝 {nick} 生日快樂！",
            "ko": f"🎉 {nick}님 생일을 축하해요!",
            "en": f"🎉 Happy Birthday, {nick}!",
        }.get(self.lang, f"🎉 祝 {nick} 生日快樂！")
        self._toast(speech, duration_ms=6500, header=header, badge_text="Panda Birthday 🎂")

    def build_menu(self) -> None:
        if getattr(self, "_batch_depth", 0) > 0:
            self._batch_dirty_menu = True
            return
        old_menu = getattr(self, "menu", None)
        if old_menu is not None:
            try:
                old_menu.destroy()
            except Exception:
                pass
        self.menu = tk.Menu(self.window, tearoff=False)

        # Actions section
        for label, state in [
            (t("idle", self.lang), "idle"),
            (t("walk", self.lang), "walk"),
            (t("cheer", self.lang), "cheer"),
            (t("sleep", self.lang), "sleep"),
        ]:
            self.menu.add_command(label=label, command=lambda s=state: self.set_state(s, manual=True))

        self.menu.add_command(label=t("status_card", self.lang), command=self.show_status_card)
        stay_on = self.settings.get("stay_in_place", False)
        stay_lbl = t("stay_in_place_toggle", self.lang)
        self.menu.add_command(label=f"✓ {stay_lbl}" if stay_on else stay_lbl, command=self.toggle_stay_in_place)
        self.menu.add_command(label=t("member_profile", self.lang), command=self.open_profile_card)
        self.menu.add_command(label=t("chat", self.lang), command=self.chat_with_pet)
        self.menu.add_command(label=t("invite_cameo", self.lang), command=self.invite_cameo)
        self.menu.add_command(label=t("set_birthday", self.lang), command=self.open_birthday_dialog)
        cameo_on = self.settings.get("cameo_enabled", True)
        cameo_lbl = t("cameo_toggle", self.lang)
        self.menu.add_command(label=f"✓ {cameo_lbl}" if cameo_on else cameo_lbl,
                              command=self.toggle_cameo)
        for key, label_key, toggle in (("daily_signature_enabled", "daily_signature_toggle", self.toggle_daily_signature),
                                       ("festival_auto_enabled", "festival_auto_toggle", self.toggle_festival_auto)):
            label = t(label_key, self.lang)
            self.menu.add_command(label=f"✓ {label}" if self.settings.get(key, True) else label, command=toggle)
        self.menu.add_separator()

        self.menu.add_command(label=t("food_cafe", self.lang), command=self.open_food_panel)
        # Bubble theme, pet / text size, hourly chime and sedentary reminder live in the panel.
        self.menu.add_command(label=t("settings_panel", self.lang), command=self.open_settings_panel)

        # Notification relay toggle
        notif_on = self.settings.get("notify_relay", True)
        notif_lbl = f"✓ {t('notify_relay', self.lang)}" if notif_on else t("notify_relay", self.lang)
        self.menu.add_command(label=notif_lbl, command=self.toggle_notify_relay)

        # Notification drawer & clear commands
        drawer_badge = f"{len(self.recent_notifications)}/20"
        self.menu.add_command(
            label=f"{t('notif_drawer_menu', self.lang)} ({drawer_badge})",
            command=self.open_notification_drawer,
        )
        self.menu.add_command(
            label=t("notif_drawer_clear_menu", self.lang),
            command=self.clear_recent_notifications,
        )

        # Standby Screen Submenu
        standby_menu = tk.Menu(self.menu, tearoff=False)
        hk_display = f" ({self.hotkey_str})" if hasattr(self, "hotkey_str") and self.hotkey_str else " (Ctrl+Shift+S)"
        standby_menu.add_command(label=f"{t('standby_open', self.lang)}{hk_display}", command=self.open_standby_screen)
        lock_on = self.settings.get("standby_lock_workstation", True)
        lock_lbl = f"✓ {t('standby_lock', self.lang)}" if lock_on else t("standby_lock", self.lang)
        standby_menu.add_command(label=lock_lbl, command=self.toggle_standby_lock)
        self.menu.add_cascade(label=t("standby", self.lang), menu=standby_menu)

        self.menu.add_separator()

        # Character switching submenu
        char_menu = tk.Menu(self.menu, tearoff=False)
        today = datetime.date.today()
        auto_char = self.get_auto_character()
        wd_names = get_weekday_names(self.lang)
        auto_label = f"{t('auto_schedule', self.lang)} ({wd_names[today.weekday()]}: {get_member_display_name(auto_char, self.lang)})"
        if self.mode == "auto":
            auto_label = f"✓ {auto_label}"
        char_menu.add_command(label=auto_label, command=self.switch_to_auto_schedule)
        char_menu.add_separator()

        for key, name, weekday in MEMBERS:
            item_label = f"{wd_names[weekday]}｜{get_member_display_name(key, self.lang)}"
            if self.mode == "manual" and self.char_key == key:
                item_label = f"✓ {item_label}"
            char_menu.add_command(
                label=item_label,
                command=lambda k=key: self.switch_character(k, mode="manual"),
            )

        char_menu.add_separator()
        char_menu.add_command(label=t("random_pick", self.lang), command=self.random_character)
        self.menu.add_cascade(label=f"{t('switch_character', self.lang)} ({get_member_display_name(self.char_key, self.lang)})", menu=char_menu)

        # Special Scenes & Holidays Preview Submenu
        preview_menu = tk.Menu(self.menu, tearoff=False)
        preview_menu.add_command(label=t("preview_standby_christmas", self.lang), command=lambda: self.preview_standby_scene("christmas"))
        preview_menu.add_command(label=t("preview_standby_campfire", self.lang), command=lambda: self.preview_standby_scene("campfire"))
        preview_menu.add_command(label=t("preview_standby_starfield", self.lang), command=lambda: self.preview_standby_scene("starfield"))
        preview_menu.add_command(label=t("preview_standby_practice", self.lang), command=lambda: self.preview_standby_scene("practice_room"))
        preview_menu.add_separator()
        preview_menu.add_command(label=t("preview_event_new_year", self.lang), command=self.preview_new_year_event)
        preview_menu.add_command(label=t("preview_event_lunar_ny", self.lang), command=lambda: self.preview_festival_event("festival_lunar_ny", t("preview_event_lunar_ny", self.lang)))
        preview_menu.add_command(label=t("preview_event_lantern", self.lang), command=lambda: self.preview_festival_event("festival_lantern", t("preview_event_lantern", self.lang)))
        preview_menu.add_command(label=t("preview_event_mid_autumn", self.lang), command=lambda: self.preview_festival_event("festival_mid_autumn", t("preview_event_mid_autumn", self.lang)))
        preview_menu.add_command(label=t("preview_event_christmas", self.lang), command=self.preview_christmas_event)
        if self.is_festival_preview_active():
            preview_menu.add_command(label=t("preview_festival_cancel", self.lang), command=self.cancel_festival_preview)
        if self.developer_mode:
            preview_menu.add_separator()
            preview_menu.add_command(label=t("preview_event_newyearseve", self.lang), command=self.preview_new_year_countdown)
            preview_menu.add_command(label=t("preview_event_419", self.lang), command=self.preview_anniversary_event)
            preview_menu.add_command(label=t("preview_event_birthday", self.lang), command=self.preview_birthday_event)
            preview_menu.add_command(label=t("preview_event_user_birthday", self.lang), command=self.preview_user_birthday_event)
            preview_menu.add_command(label=t("preview_event_musical", self.lang), command=self.preview_musical_event)
            preview_menu.add_command(label=t("preview_event_dome_baseball", self.lang), command=self.preview_dome_baseball_event)
            preview_menu.add_command(label=t("preview_event_dome_eunji", self.lang), command=self.preview_eunji_dome_event)
        self.menu.add_cascade(label=t("preview_scenes", self.lang), menu=preview_menu)

        # Hide to Tray & Language
        self.menu.add_separator()
        self.menu.add_command(label=t("hide_to_tray", self.lang), command=self.hide_to_tray)

        lang_menu = tk.Menu(self.menu, tearoff=False)
        for code, name in [("zh_TW", "繁體中文"), ("ko", "한국어"), ("en", "English")]:
            opt = f"✓ {name}" if self.lang == code else name
            lang_menu.add_command(label=opt, command=lambda c=code: self.set_language(c))
        self.menu.add_cascade(label=t("lang_switch", self.lang), menu=lang_menu)

        # Mouse Cursor Style Submenu
        cur_style = self.settings.get("mouse_cursor", "paw_smooth")
        cursor_menu = tk.Menu(self.menu, tearoff=False)
        for c_key, c_label in [
            ("paw_smooth", t("cursor_paw_smooth", self.lang)),
            ("mitten_smooth", t("cursor_mitten_smooth", self.lang)),
            ("paw_pixel", t("cursor_paw_pixel", self.lang)),
            ("mitten_pixel", t("cursor_mitten_pixel", self.lang)),
            ("system", t("cursor_system", self.lang)),
        ]:
            prefix = "✓ " if cur_style == c_key else ""
            cursor_menu.add_command(
                label=f"{prefix}{c_label}",
                command=lambda k=c_key: self.set_mouse_cursor(k),
            )
        self.menu.add_cascade(label=t("cursor_style_menu", self.lang), menu=cursor_menu)

        # Autostart
        autostart_label = f"✓ {t('autostart', self.lang)}" if self.is_autostart_enabled() else t("autostart", self.lang)
        self.menu.add_command(label=autostart_label, command=self.toggle_autostart)

        self.menu.add_separator()
        if self.developer_mode:
            self.menu.add_command(label=t("debug_panel", self.lang), command=self.open_debug_panel)
        self.menu.add_command(label=t("exit", self.lang), command=self.close)

    def random_character(self) -> None:
        candidates = [k for k in MEMBER_KEYS if k != self.char_key]
        pick = random.choice(candidates if candidates else MEMBER_KEYS)
        self.switch_character(pick, mode="manual")

    def record_activity(self) -> None:
        self.last_user_activity = time.time()
        self.target_roam_x = None

    def chat_with_pet(self) -> None:
        self.record_activity()
        self.trigger_cheer(cycles=2)
        import random
        if self.satiety < SATIETY_HUNGRY_THRESHOLD and random.random() < 0.5:
            quote = get_hunger_aegyo_quote(self.char_key, self.lang)
            hunger_badge = {
                "zh_TW": "🥺 肚子咕嚕嚕～討食中",
                "ko": "🥺 배에서 꼬르륵～ 간식 줘요",
                "en": "🥺 Tummy Growling~ Feed me",
            }.get(self.lang, "🥺 肚子咕嚕嚕～討食中")
            self._toast(quote, sub_badge=hunger_badge, duration_ms=4800, kind="hunger")
            return
        badge, quote = get_random_chat_quote(self.char_key, self.lang)
        self._toast(quote, sub_badge=badge, duration_ms=4800)

    def on_double_click(self) -> None:
        self.record_activity()
        self.ensure_topmost()
        self.trigger_cheer(cycles=2)

        # 點擊計數：第 1 次為招牌金句，第 2 次及之後為隨機 50 句心靈雞湯暖心語錄
        count = self.member_double_clicks.get(self.char_key, 0)
        self.member_double_clicks[self.char_key] = count + 1

        import random
        if self.satiety < SATIETY_HUNGRY_THRESHOLD and random.random() < 0.4:
            quote = get_hunger_aegyo_quote(self.char_key, self.lang)
            hunger_badge = {
                "zh_TW": "🥺 肚子餓了～撒嬌討食",
                "ko": "🥺 배고파요～ 간식 애교",
                "en": "🥺 Hungry Aegyo~ Feed me",
            }.get(self.lang, "🥺 肚子餓了～撒嬌討食")
            self._toast(quote, sub_badge=hunger_badge, duration_ms=5000, kind="hunger")
            return

        if count == 0:
            # 第一次點擊：經典招牌元氣應援金句！
            msg = get_cheer_quote(self.char_key, self.lang)
            sub_tag = {
                "zh_TW": "招牌元氣應援 💖",
                "ko": "시그니처 응원 💖",
                "en": "Signature Cheer 💖",
            }.get(self.lang, "招牌元氣應援 💖")
        else:
            # 第二次及後續點擊：隨機 50 句專屬心靈雞湯語錄！
            msg = get_random_warm_quote(self.char_key, self.lang)
            sub_tag = {
                "zh_TW": "Apink 暖心語錄 💌",
                "ko": "에이핑크 힐링 어록 💌",
                "en": "Apink Warm Quote 💌",
            }.get(self.lang, "Apink 暖心語錄 💌")

        self._toast(msg, sub_badge=sub_tag, duration_ms=5000)

    def set_state(self, state: str, manual: bool = False) -> None:
        """Explicit state choice (context menu / tests); "cheer" becomes a USER event.

        Sets the ambient base state and ends the current non-system event so
        the choice is visible immediately. Internal behaviour (roam, sleep
        detection) uses ``_set_ambient`` and never cancels events.
        """
        self.record_activity()
        if getattr(self, "_festival_preview_active", False) and hasattr(self, "cancel_festival_preview"):
            self.cancel_festival_preview()
        elif (
            getattr(self, "dome_preview", None) is not None
            or getattr(self, "group_celebration", None) is not None
            or getattr(self, "anniversary_scene", None) is not None
        ) and hasattr(self, "_close_group_celebration"):
            self._close_group_celebration()
        if state == "cheer":
            # The user's own cheer uses her approved lightstick cheer when she has one.
            if not self.trigger_special_action(CHEER_LIGHTSTICK_ACTION, kind="manual.cheer"):
                self.trigger_cheer(cycles=2, kind="manual.cheer")
            return
        active = self.coord.snapshot().active
        if active is not None and active.request.priority is not Priority.SYSTEM:
            self.coord.cancel(active.event_id, "manual_state")
        self._set_ambient(state)
        self.frame_idx = 0
        self.walk_cycles = 0
        if hasattr(self, "_refresh_visual_appearance") and hasattr(self, "canvas"):
            self._refresh_visual_appearance()
        if state == "sleep" and manual:
            self._toast(f"💤 {get_sleep_quote(self.char_key, self.lang)}", duration_ms=2800)

    def trigger_cheer(
        self,
        cycles: int = 2,
        priority: Priority = Priority.USER,
        kind: str = "cheer",
        **request_kw,
    ) -> bool:
        """Ask the coordinator for a cheer; returns True if accepted (now or later)."""
        duration_s = cycles * CHEER_CYCLE_FRAMES * CHEER_MS / 1000.0
        req = EventRequest(
            kind=kind,
            priority=priority,
            state=ActorState.CHEER,
            duration_s=duration_s,
            **request_kw,
        )
        return self.coord.submit(req).accepted

    def _actions(self) -> ActionFrameCache:
        lru = getattr(self, "_action_lru", None)
        if lru is None:
            sprites = getattr(self, "sprites", None)
            lru = ActionFrameCache(action_cache_budget(getattr(sprites, "display_px", 192) or 192))
            self._action_lru = lru
        return lru

    def _action_entry(self, member: str, action: str, facing: int = 1) -> ActionEntry | None:
        """Cached exact action at pet size for one facing (left = mirrored); None if absent.

        While a group celebration had to shrink its guests (narrow screen), the host's own
        frames are shrunk by the same factor around her feet so all five match (2026-11-22).
        """
        scale = getattr(self, "_host_party_scale", 1.0)
        if member == getattr(self, "char_key", None) and isinstance(scale, float) and scale < 0.999:
            return self._scaled_action_entry(member, action, facing, scale)
        return self._unscaled_action_entry(member, action, facing)

    def _scaled_action_entry(self, member: str, action: str, facing: int, scale: float) -> ActionEntry | None:
        base = self._unscaled_action_entry(member, action, facing)
        if base is None:
            return None
        sprites = getattr(self, "sprites", None)
        px = getattr(sprites, "display_px", 192) or 192
        lru = self._actions()
        key = (member, action, px, -1 if facing < 0 else 1, round(scale, 4))
        entry = lru.get(key)
        if entry is not MISSING:
            return entry
        wfx, wfy = walk_feet_point(px)
        dx, dy = base.offset
        frames = tuple(scale_sprite_frame(im, scale, sprites, default_binary=not self._ulw_active())
                       for im in base.pil)
        # Scale about the feet point so she keeps standing on the same spot.
        offset = (round(wfx + (dx - wfx) * scale), round(wfy + (dy - wfy) * scale))
        entry = ActionEntry(frames, base.frame_ms, offset, getattr(self, "root", None))
        lru.put(key, entry)
        return entry

    def _set_host_party_scale(self, scale: float) -> None:
        scale = float(scale) if isinstance(scale, (int, float)) and 0 < scale < 1.0 else 1.0
        if scale == getattr(self, "_host_party_scale", 1.0):
            return
        self._host_party_scale = scale
        try:
            self._refresh_visual_appearance(force_box=True)
        except Exception:
            log.exception("host party scale refresh failed")

    def _unscaled_action_entry(self, member: str, action: str, facing: int = 1) -> ActionEntry | None:
        if facing < 0 and member in MIRROR_UNSAFE:
            action, facing = directional_action(member, action, -1), 1
        facing = -1 if facing < 0 else 1
        sprites = getattr(self, "sprites", None)
        px = getattr(sprites, "display_px", 192) or 192
        lru = self._actions()
        key = (member, action, px, facing)
        entry = lru.get(key)
        if entry is not MISSING:
            return entry
        master = getattr(self, "root", None)
        if facing > 0:
            loaded = load_exact_action(self.sprites, member, action)
            entry = None if loaded is None else ActionEntry(
                loaded.frames, loaded.frame_ms, loaded.offset, master)
        else:
            base = self._unscaled_action_entry(member, action, 1)
            if base is None:
                entry = None
            else:
                dx, dy = base.offset
                fw = base.pil[0].width
                wfx = walk_feet_point(px)[0]
                entry = ActionEntry(
                    tuple(im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for im in base.pil),
                    base.frame_ms, (2 * wfx - fw - dx, dy), master)
        lru.put(key, entry)
        return entry

    def _action_frames(self, member: str, action: str
                       ) -> tuple[Sequence, float, tuple[int, int]] | None:
        """(frames, frame_ms, offset) of an approved exact action at pet size, cached; None if absent.

        ``frames`` is a lazy PhotoImage sequence: a Tk image is built only when a frame is
        indexed (ColorKey canvas), never by the ULW animation loop.
        offset = frame top-left relative to the base frame's (non-zero for large desktop canvases).
        """
        entry = self._action_entry(member, action, 1)
        return None if entry is None else entry.tk_tuple()

    def _flipped_action_frames(self, member: str, action: str
                               ) -> tuple[Sequence, float, tuple[int, int]] | None:
        """Left-facing frames and mirror-adjusted offset for walking/facing left in large or custom actions."""
        if member in MIRROR_UNSAFE:
            return self._action_frames(member, directional_action(member, action, -1))
        entry = self._action_entry(member, action, -1)
        return None if entry is None else entry.tk_tuple()

    def _visual_pil_frames_and_offset(
        self, member: str, action: str, facing: int = 1
    ) -> tuple[tuple[Image.Image, ...], float, tuple[int, int]] | None:
        entry = self._action_entry(member, action, facing)
        return None if entry is None else entry.pil_tuple()

    def _visual_frames_and_offset(self, member: str, action: str, facing: int = 1
                                  ) -> tuple[Sequence, float, tuple[int, int]] | None:
        if facing < 0:
            return self._flipped_action_frames(member, action)
        return self._action_frames(member, action)

    def _ulw_active(self) -> bool:
        surf = getattr(self, "layered_surface", None)
        return surf is not None and not surf.closed

    def _show_canvas_frame(self, **options):
        """Point the Tk canvas at the current frame; skipped on ULW (the canvas is never shown
        there, and assigning it would build a PhotoImage per frame)."""
        if self._ulw_active():
            if options:
                self.canvas.itemconfigure(self.image, **options)
            return None
        frame = self.current_frame()
        self.canvas.itemconfigure(self.image, image=frame, **options)
        return frame

    def _sync_frame_box(self, action: str | None, facing: int | None = None, *, force: bool = False) -> None:
        """Grow the window around the pet for a larger action canvas; feet stay on the same pixel.

        self.x / self.y / width / height keep describing the base box (bubbles, drag, clamping).
        A pet-size change keeps pad == (0, 0, 0, 0) but still resizes the window, so it must
        also take the guarded path below (force, or the canvas no longer matches the box).
        """
        pad, image_xy = (0, 0, 0, 0), (0, 0)
        if facing is None:
            facing = self._visual_facing(action)
        loaded = self._visual_pil_frames_and_offset(self.char_key, action, facing) if action else None
        if loaded is not None:
            (dx, dy), first = loaded[2], loaded[0][0]
            fw, fh = first.width, first.height
            pad = (max(0, -dx), max(0, -dy), max(0, dx + fw - self.width), max(0, dy + fh - self.height))
            image_xy = (pad[0] + dx, pad[1] + dy)
        self._last_image_xy = image_xy
        w, h = self.width + pad[0] + pad[2], self.height + pad[1] + pad[3]
        surf = getattr(self, "layered_surface", None)
        use_ulw = surf is not None and not surf.closed
        if (force or pad != self._frame_pad
                or int(float(self.canvas.cget("width"))) != w
                or int(float(self.canvas.cget("height"))) != h):
            alpha = None
            if (not use_ulw and sys.platform == "win32" and self.window.winfo_viewable()
                    and (w > self.canvas.winfo_width() or h > self.canvas.winfo_height())):
                # Windows can composite the newly allocated layered surface before
                # Tk paints it. Keep the HWND mapped but transparent during that pass.
                alpha = self.window.attributes("-alpha")
                self.window.attributes("-alpha", 0.0)
            try:
                self._frame_pad = pad
                self.canvas.config(width=w, height=h)
                self.window.geometry(f"{w}x{h}+{int(self.x - pad[0])}+{int(self.y - pad[1])}")
                self.canvas.coords(self.image, *image_xy)
                if use_ulw:
                    pil_im = (
                        loaded[0][self.frame_idx % len(loaded[0])]
                        if loaded and loaded[0]
                        else self.current_pil_frame()
                    )
                    self._present_layered_pet(pil_im, image_xy=image_xy)
                else:
                    tk_loaded = self._visual_frames_and_offset(self.char_key, action, facing) if action else None
                    frame = tk_loaded[0][self.frame_idx % len(tk_loaded[0])] if tk_loaded else self.current_frame()
                    self.canvas.itemconfigure(self.image, image=frame)
                self.window.update_idletasks()
            finally:
                if alpha is not None and self.window.winfo_exists():
                    self.window.attributes("-alpha", alpha)
            if (
                getattr(self, "dragging", False)
                or getattr(self, "drag_start", None) is not None
                or self._pointer_over_pet_now()
            ):
                self._reapply_drag_cursor()
        else:
            self.canvas.coords(self.image, *image_xy)
            if use_ulw:
                self._present_layered_pet(image_xy=image_xy)

    def _visual_facing(self, action: str | None) -> int:
        if action is None or self.dragging or self.char_key in MIRROR_UNSAFE:
            return 1
        active_action = self.coord.action
        if active_action == action and self.coord.actor_state in (ActorState.SPECIAL, ActorState.CHEER):
            return -1 if self.face_override == -1 else 1
        if self.state == "walk":
            return -1 if self.direction == -1 else 1
        return -1 if self.face_override == -1 else 1

    def _active_eunji_dome_step(self) -> tuple[str, int] | None:
        """Return `(outfit_action, local_frame_idx)` while `special_eunji_dome_dream` plays."""
        if (
            self.coord.action != EUNJI_DOME_PERSONAL_ACTION
            or self.char_key != "eunji"
            or self.coord.actor_state not in (ActorState.SPECIAL, ActorState.CHEER)
        ):
            self._eunji_dome_effect_state = None
            return None
        snap = self.coord.snapshot()
        event_id = snap.active.event_id if snap.active is not None else None
        cached = getattr(self, "_eunji_dome_effect_state", None)
        if cached is None or cached[0] != event_id:
            outfits = tuple(
                o for o in resolved_eunji_dome_outfits(self.sprites, available_fn=available_actions)
                if self._action_frames("eunji", o) is not None
            )
            if not outfits:
                return None
            cached = (event_id, time.monotonic(), outfits)
            self._eunji_dome_effect_state = cached
        _eid, t0, outfits = cached
        elapsed_ms = max(0.0, (time.monotonic() - t0) * 1000.0)
        return dome_concert_step(elapsed_ms, outfits)

    def _visual_action(self) -> str | None:
        """The exact action drawn now instead of the base sprite, if it is approved."""
        if self.dragging:
            return DRAG_ACTION if self._action_frames(self.char_key, DRAG_ACTION) else None
        action = self.coord.action
        if action == EUNJI_DOME_PERSONAL_ACTION:
            step = self._active_eunji_dome_step()
            if step is not None:
                return step[0]
        if (action and action not in STATES
                and self.coord.actor_state in (ActorState.SPECIAL, ActorState.CHEER)
                and self._action_frames(self.char_key, action)):
            return action
        # Asymmetric left-facing locomotion has priority over standing costumes;
        # never slide a right-facing holiday pose to the left or mirror its mole.
        if self.state == "walk":
            directed = directional_action(self.char_key, "walk", self.direction)
            if directed != "walk" and self._action_frames(self.char_key, directed):
                return directed
        if self.state != "sleep":
            costume = self._active_festival_costume()
            if costume is not None:
                return costume
        return None

    def _refresh_visual_appearance(self, *, force_box: bool = False) -> None:
        """Synchronize frame box and displayed image immediately after costume/date/member transitions."""
        shown = self._visual_action()
        facing = self._visual_facing(shown)
        if (shown, self.char_key) != (self._shown_action, self._shown_member):
            self.frame_idx = 0
        self._shown_action, self._shown_member, self._shown_facing = shown, self.char_key, facing
        self._sync_frame_box(shown, facing, force=force_box)
        self._show_canvas_frame()
        self._present_layered_pet()

    def _sync_festival_state(self) -> None:
        """Apply holiday costume on festival start and auto-revert at midnight / toggle-off."""
        state_key = self._festival_state_key()
        if state_key == getattr(self, "_last_festival_state", None):
            return
        self._last_festival_state = state_key
        if state_key[2] is None:
            active = self.coord.snapshot().active
            if active is not None and (
                active.request.kind.startswith("festival.")
                or (active.request.kind.startswith("calendar.holiday.")
                    and str(active.request.action or "").startswith("festival_"))
            ):
                self.coord.cancel(active.event_id, "festival_ended")
        elif state_key[0] is not None and state_key[1]:
            self._schedule_festival_welcome()
        self._refresh_visual_appearance()

    def available_special_actions(self, member: str | None = None) -> tuple[str, ...]:
        """The SPECIAL_ACTIONS this member has approved (for menus)."""
        target = member or self.char_key
        found = list(available_actions(self.sprites, target, SPECIAL_ACTIONS))
        if (
            target == "eunji"
            and resolved_eunji_dome_outfits(self.sprites, available_fn=available_actions)
        ):
            found.append(EUNJI_DOME_PERSONAL_ACTION)
        return tuple(found)

    def trigger_special_action(self, action_key: str, member: str | None = None,
                               kind: str | None = None, hold_s: float | None = None) -> bool:
        """Play one member's special action; False when it is not approved (nothing changes).

        Another member is switched to first (the user picked that member's trick).
        ``hold_s`` keeps it on at least that long (whole passes), e.g. as long as a party lasts.
        """
        member = member or self.char_key
        if member not in MEMBER_KEYS or action_key in STATES:
            return False
        if action_key == EUNJI_DOME_PERSONAL_ACTION:
            if member != "eunji":
                return False
            outfits = resolved_eunji_dome_outfits(self.sprites, available_fn=available_actions)
            if not outfits:
                return False
            self.record_activity()
            if member != self.char_key:
                self.switch_character(member, mode=self.mode)
            playable = tuple(o for o in outfits if self._action_frames("eunji", o) is not None)
            if not playable:
                return False
            one_pass_s = dome_concert_cycle_ms(playable) / 1000.0
            duration = one_pass_s
            if hold_s is not None and duration < hold_s:
                duration = math.ceil(hold_s / one_pass_s) * one_pass_s
            self._eunji_dome_effect_state = None
            req = EventRequest(
                kind=kind or f"special.{action_key}",
                priority=Priority.USER,
                state=ActorState.SPECIAL,
                action=action_key,
                duration_s=duration,
            )
            res = self.coord.submit(req)
            if res.accepted:
                self._active_eunji_dome_step()
            return res.accepted
        if not available_actions(self.sprites, member, (action_key,)):
            return False
        self.record_activity()
        if member != self.char_key:
            self.switch_character(member, mode=self.mode)
        loaded = self._action_frames(member, action_key)
        if loaded is None:
            return False
        frames, frame_ms, _offset = loaded
        duration = self._action_duration_s(frames, frame_ms)
        if hold_s is not None and duration < hold_s:
            one_pass_s = len(frames) * frame_ms / 1000.0
            duration = hold_s if len(frames) == 1 else math.ceil(hold_s / one_pass_s) * one_pass_s
        req = EventRequest(kind=kind or f"special.{action_key}", priority=Priority.USER,
                           state=ActorState.SPECIAL, action=action_key, duration_s=duration)
        return self.coord.submit(req).accepted

    def _cancel_drag_cursor_after(self) -> None:
        after_id = getattr(self, "_drag_cursor_after", None)
        win = getattr(self, "window", None)
        if after_id and win is not None:
            try:
                win.after_cancel(after_id)
            except Exception:
                pass
        self._drag_cursor_after = None

    def _pointer_over_pet_now(self) -> bool:
        win = getattr(self, "window", None)
        if win is None:
            return False
        try:
            px, py = win.winfo_pointerxy()
            surf = getattr(self, "layered_surface", None)
            if surf is not None and not surf.closed and surf.width > 0 and surf.height > 0:
                wx, wy, ww, wh = surf.geometry_box
            else:
                wx = int(win.winfo_rootx())
                wy = int(win.winfo_rooty())
                ww = int(win.winfo_width())
                wh = int(win.winfo_height())
            return wx <= px < wx + ww and wy <= py < wy + wh
        except Exception:
            return False

    def _reapply_drag_cursor(self) -> None:
        """Keep the active custom HCURSOR intact through Tk capture/resize/idle updates."""
        cursor_key = self.settings.get("mouse_cursor", "paw_smooth")
        if cursor_key == "system":
            return
        from app.cursor_manager import reapply_active_cursor

        reapply_active_cursor(cursor_key)
        win = getattr(self, "window", None)
        if win is not None and getattr(self, "_drag_cursor_after", None) is None:
            def _idle_reapply() -> None:
                self._drag_cursor_after = None
                cur_key = self.settings.get("mouse_cursor", "paw_smooth")
                if cur_key == "system":
                    return
                if (
                    getattr(self, "drag_start", None) is not None
                    or getattr(self, "dragging", False)
                    or self._pointer_over_pet_now()
                ):
                    reapply_active_cursor(cur_key)

            try:
                self._drag_cursor_after = win.after_idle(_idle_reapply)
            except Exception:
                self._drag_cursor_after = None

    def drag_begin(self, event: tk.Event) -> None:
        self.record_activity()
        self.ensure_topmost()
        self.drag_start = (event.x_root - self.x, event.y_root - self.y)
        self._press_root = (event.x_root, event.y_root)
        self._reapply_drag_cursor()

    def drag_move(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        self.record_activity()
        if not self.dragging:
            px, py = self._press_root
            if abs(event.x_root - px) + abs(event.y_root - py) < DRAG_THRESHOLD_PX:
                self._reapply_drag_cursor()
                return  # still a click, not a drag
            # Real drag starts: L4 preempts everything, bubble would be left behind.
            self.dragging = True
            self._dismiss_toast()
            self._close_bubble_window()
            if self.coord.snapshot().ambient_state is ActorState.SLEEP:
                self._set_ambient("idle")
            self.coord.begin_user_interaction("drag")
        dx, dy = self.drag_start
        area = self.desktop.work_area_for_point(event.x_root, event.y_root)
        # x/y and the pointer offset describe the base box. The previous
        # animation's larger canvas must not move that box away from an edge.
        # _place_pet applies the current padding only to the window origin.
        self.x, self.y = area.clamp(event.x_root - dx, event.y_root - dy,
                                   self.width, self.height)
        self._place_pet()
        self._reapply_drag_cursor()

    def drag_end(self, event: tk.Event) -> None:
        tapped = self.drag_start is not None and not self.dragging
        head = tapped and self.drag_start[1] < self.height * HEAD_PAT_SHARE
        self.end_drag()
        self.record_activity()
        if tapped:
            self._react_to_tap(head)
        if self._pointer_over_pet_now():
            self._reapply_drag_cursor()

    def end_drag(self) -> None:
        self._cancel_drag_cursor_after()
        self.drag_start = None
        if self.dragging:
            self.dragging = False
            self.coord.end_user_interaction()

    def _on_pink_menu_closed(self) -> None:
        self.pink_menu = None
        self._menu_active = False
        try:
            self.ensure_topmost()
        except tk.TclError:
            pass

    def show_menu(self, event: tk.Event) -> None:
        self.record_activity()
        self._close_pink_menu()
        self._menu_active = True
        from app.pink_context_menu import PinkContextMenu, build_pet_context_menu_items
        try:
            self.pink_menu = PinkContextMenu(
                self.window,
                lang=self.lang,
                char_key=self.char_key,
                items=build_pet_context_menu_items(self),
                anchor_x=event.x_root,
                anchor_y=event.y_root,
                work_area=self._pet_work_area(),
                on_close=self._on_pink_menu_closed,
            )
            PandaPet._apply_cursor_to_panel(self, self.pink_menu)
        except Exception:
            self._menu_active = False
            try:
                self.ensure_topmost()
            except tk.TclError:
                pass

    def _walk_frames(self):
        action = getattr(self, "current_walk_action", "walk")
        if action not in self.frames:
            action = "walk"
        if self.direction == -1:
            return self.get_flipped_walk_frames(self.char_key, action)
        return self.frames[action]

    def _resolve_current_frame(self, *, as_pil: bool = False):
        """Single source of truth for current Tk PhotoImage (`as_pil=False`) and PIL Image (`as_pil=True`)."""
        dome_step = self._active_eunji_dome_step() if not self.dragging else None
        if dome_step is not None:
            outfit, local_idx = dome_step
            facing = self._visual_facing(outfit)
            loaded = (
                self._visual_pil_frames_and_offset(self.char_key, outfit, facing)
                if as_pil
                else self._visual_frames_and_offset(self.char_key, outfit, facing)
            )
            if loaded is not None and loaded[0]:
                frames = loaded[0]
                return frames[local_idx % len(frames)]

        action = self._visual_action()
        if action is not None:
            facing = self._visual_facing(action)
            loaded = (
                self._visual_pil_frames_and_offset(self.char_key, action, facing)
                if as_pil
                else self._visual_frames_and_offset(self.char_key, action, facing)
            )
            if loaded is not None and loaded[0]:
                frames = loaded[0]
                return frames[self.frame_idx % len(frames)]

        if self.state == "walk":
            if as_pil:
                member_sprites = self.sprites.load_member(self.char_key, self.root)
                walk_act = getattr(self, "current_walk_action", "walk")
                if walk_act not in self.frames:
                    walk_act = "walk"
                frames = member_sprites.get_pil(walk_act, self.direction)
                if frames:
                    return frames[self.frame_idx % len(frames)]
                idle_frames = member_sprites.get_pil("idle", 1)
                return idle_frames[0] if idle_frames else None
            frames = self._walk_frames()
            return frames[self.frame_idx % len(frames)] if frames else self.frames["idle"][0]

        if as_pil:
            member_sprites = self.sprites.load_member(self.char_key, self.root)
            facing = self.face_override if self.face_override is not None else 1
            frames = member_sprites.get_pil(self.state, facing)
            if not frames:
                idle_frames = member_sprites.get_pil("idle", 1)
                return idle_frames[0] if idle_frames else None
        else:
            frames = self.frames[self.state]
            if self.face_override is not None:
                frames = self.sprites.load_member(self.char_key, self.root).get(self.state, self.face_override)
            if not frames:
                return self.frames["idle"][0]

        if self.state == "cheer":
            seq = (0, 1, 2, 3, 2, 1)
            idx = seq[self.frame_idx % len(seq)]
            return frames[idx % len(frames)]

        return frames[self.frame_idx % len(frames)]

    def current_pil_frame(self) -> Image.Image | None:
        """Return the current PIL RGBA frame corresponding to ``current_frame()``."""
        try:
            return self._resolve_current_frame(as_pil=True)
        except Exception:
            return None

    def current_frame(self):
        return self._resolve_current_frame(as_pil=False)

    def _frame_token(self):
        """Identity of the frame currently on screen, to tell when a walk frame advanced.

        ULW compares the last presented PIL frame id (no Tk image exists there); ColorKey the canvas image name.
        """
        if self._ulw_active():
            return getattr(self, "_last_ulw_frame_id", None)
        return self.canvas.itemcget(self.image, "image")

    def cycle_length(self) -> int:
        """Frames per animation loop of the current sprite (frame-boundary unit)."""
        dome_step = self._active_eunji_dome_step() if not self.dragging else None
        if dome_step is not None and getattr(self, "_eunji_dome_effect_state", None):
            outfits = self._eunji_dome_effect_state[2]
            return max(1, len(outfits) * DOME_CONCERT_FRAMES_PER_OUTFIT)
        action = self._visual_action()
        if action is not None:
            return max(1, len(self._action_frames(self.char_key, action)[0]))
        if self.state == "walk":
            return max(1, len(self._walk_frames()))
        if self.state == "cheer":
            return CHEER_CYCLE_FRAMES
        return max(1, len(self.frames.get(self.state, ())))

    def step_walk(self) -> None:
        self.x = int(self.x)
        # Pause walking immediately if speaking so the pet doesn't abandon its speech bubble
        if self.active_bubble is not None:
            self._set_ambient("idle")
            self.target_roam_x = None
            return

        if self.settings.get("stay_in_place", False):
            self.target_roam_x = None
            if self.state == "walk":
                self._set_ambient("idle")
            return

        area = self.desktop.work_area_for_point(self.x+self.width//2,self.y+self.height//2)
        min_x,max_x = area.left,max(area.left,area.right-self.width)
        if self.target_roam_x is not None:
            self.target_roam_x = min(max(self.target_roam_x,min_x),max_x)
            if self.target_roam_x == self.x:
                self.target_roam_x = None
                self._walk_subpx = 0.0
                self._set_ambient("idle")
                return
        # Check boundary collision
        if self.x <= min_x + 10:
            self.direction = 1
        elif self.x >= max_x - 10:
            self.direction = -1

        # Keep distance/time constant even for differently timed directional art.
        if self.target_roam_x is not None:
            self.direction = 1 if self.target_roam_x > self.x else -1
        shown = self._visual_action()
        loaded = self._action_frames(self.char_key, shown) if shown else None
        frame_ms = max(16, round(loaded[1])) if loaded is not None else WALK_MS
        distance = WALK_STEP * frame_ms / WALK_MS * (self.sprites.display_px / 192.0)
        travel = distance * self.direction + getattr(self, "_walk_subpx", 0.0)
        delta = int(travel + (1e-9 if travel >= 0 else -1e-9))
        self._walk_subpx = travel - delta

        # Check target roam arrival using the same step as movement.
        if self.target_roam_x is not None:
            if abs(self.x - int(self.target_roam_x)) <= abs(delta):
                self.x = int(self.target_roam_x)
                self._walk_subpx = 0.0
                self.target_roam_x = None
                self._place_pet()
                self._set_ambient("idle")
                return

        next_x = self.x + delta
        self.x, self.y = area.clamp(next_x, self.y, self.width, self.height)
        if self.x != next_x:
            self._walk_subpx = 0.0
        self._place_pet()

    def check_roam_ai(self) -> None:
        """Autonomous edge roaming when pet is unbothered."""
        snap = self.coord.snapshot()
        if (
            self.state != "idle"
            or snap.active is not None
            or snap.pending_id is not None
            or snap.mode is not GlobalMode.NORMAL
            or self.drag_start is not None
            or self.standby_overlay is not None
            or self.active_bubble is not None
            or not self.window.winfo_viewable()
            or getattr(self, "_menu_active", False)
            or self._has_active_subpanel()
        ):
            return

        now = time.time()
        # Only trigger roam if user is not actively clicking/dragging the pet,
        # but is still active on the computer (OS idle < 3 min)
        if now - self.last_user_activity > 10.0 and get_system_idle_seconds() < IDLE_SLEEP_TIMEOUT_SEC:
            shown = self._maybe_signature_action(now) or self._maybe_natural_action(now)
            if shown:
                self.next_roam_time = now + shown + random.uniform(4.0, 10.0)
                return
            if now >= self.next_roam_time:
                self.next_roam_time = now + random.uniform(14.0, 26.0)
                if self._maybe_festival_action(now):
                    return
                if self.settings.get("stay_in_place", False):
                    if random.random() < 0.40:
                        if self.trigger_cheer(cycles=2, priority=Priority.SPONTANEOUS, kind="roam.chat", wakes_sleep=False):
                            badge, quote = get_random_chat_quote(self.char_key, self.lang)
                            self._toast(quote, sub_badge=badge, duration_ms=3800, priority=Priority.SPONTANEOUS, kind="roam.chat")
                    return
                roll = random.random()
                area = self.desktop.work_area_for_point(self.x+self.width//2,self.y+self.height//2)
                min_x,max_x = area.left,max(area.left,area.right-self.width)

                if roll < 0.65:
                    # 65% chance: Roam along bottom edge
                    if self.x < min_x + 120:
                        target = random.randint(min(min_x+300,max_x),max_x)
                    elif self.x > max_x - 120:
                        target = random.randint(min_x,max(min_x,max_x-300))
                    else:
                        target = random.randint(min_x,max_x)
                    self.target_roam_x = target
                    self._set_ambient("walk")
                elif roll < 0.82:
                    # 17% chance: Mini cheer with authentic member hobby quote (L1)
                    if self.trigger_cheer(
                        cycles=2,
                        priority=Priority.SPONTANEOUS,
                        kind="roam.chat",
                        wakes_sleep=False,
                    ):
                        badge, quote = get_random_chat_quote(self.char_key, self.lang)
                        self._toast(
                            quote,
                            sub_badge=badge,
                            duration_ms=3800,
                            priority=Priority.SPONTANEOUS,
                            kind="roam.chat",
                        )

    def tick_1s(self) -> None:
        """1-second periodic tick for OS idle detection and sedentary reminder."""
        try:
            self._tick_1s_body()
        except Exception:
            log.exception("tick_1s failed")
        self._loop_after["tick_1s"] = self.window.after(1000, self.tick_1s)

    def _flush_periodic_companion_state(self, *, refresh_ui: bool = True) -> None:
        """Persist periodic companion time & natural satiety decay every 60s."""
        now = time.time()
        if now - getattr(self, "_last_companion_save", 0) >= 60.0:
            self._last_companion_save = now
            # 2 hours (7200s) = 10% decay -> 1% per 720s. 0 satiety = zero penalty, no health loss.
            if now - getattr(self, "last_satiety_update", now) >= 60.0:
                self._decay_everyone(now)
            self.save_settings()
            if refresh_ui:
                self._refresh_status_card()

    def _tick_1s_body(self) -> None:
        locked = is_workstation_locked()
        if locked is True:
            if not getattr(self, "_desktop_was_locked", False):
                self._restore_after_unlock = self.window.state() != "withdrawn"
            self._desktop_was_locked = True
            self._flush_periodic_companion_state(refresh_ui=False)
            return
        if getattr(self, "_standby_resume_pending", False):
            return
        if locked is False and getattr(self, "_desktop_was_locked", False):
            if getattr(self, "_restore_after_unlock", False) and self.standby_overlay is None:
                if not self._restore_pet_window():
                    return
            self._desktop_was_locked = False
        if self.standby_overlay is None and self.window.winfo_viewable():
            self._recover_pet_geometry()
            self.ensure_topmost()
        os_idle = get_system_idle_seconds()
        ambient = self.coord.snapshot().ambient_state

        # OS Idle to Sleep / Wake detection (sleep is the ambient base state)
        if os_idle >= IDLE_SLEEP_TIMEOUT_SEC:
            if ambient is not ActorState.SLEEP and not self.dragging:
                self._set_ambient("sleep")
                self.was_os_sleeping = True
        else:
            if self.was_os_sleeping:
                self.was_os_sleeping = False
                if ambient is ActorState.SLEEP:
                    self._set_ambient("idle")
                    if self.coord.mode is GlobalMode.NORMAL:
                        self.trigger_cheer(cycles=2, priority=Priority.SYSTEM, kind="wake")
                        self._toast(
                            f"🐼 {self.get_active_name()}：{t('welcome_back', self.lang)}",
                            duration_ms=3000,
                            priority=Priority.SYSTEM,
                            kind="wake",
                        )

        # Sedentary reminder accounting
        sedentary_min = self.settings.get("sedentary_interval_min", 60)
        if sedentary_min > 0:
            if os_idle < 300:  # User actively at desk
                self.sedentary_active_sec += 1
                if self.sedentary_active_sec >= sedentary_min * 60:
                    self.sedentary_active_sec = 0
                    self.sedentary_alert(priority=Priority.SYSTEM)
            else:
                # User stepped away for > 5 min, pause/reset
                self.sedentary_active_sec = 0

        # Periodic 60s persistence of companion time and natural satiety decay
        self._flush_periodic_companion_state(refresh_ui=True)

        self._check_auto_schedule_rollover()   # before the calendar, so today's greetings name today's member
        self.poll_calendar()
        self._check_new_year_countdown()
        self.maybe_auto_cameo(os_idle)
        self.coord.tick()
        self._pump_speech()
        self._report_persist_errors()
        self.check_roam_ai()

    # ── Cameo (guest member visits) ──────────────────────────────────────
    def maybe_auto_cameo(self, os_idle: float) -> None:
        """Low-frequency automatic visit; only while the user is at the desk."""
        now = time.time()
        if now < self.next_cameo_at or not self.settings.get("cameo_enabled", True):
            return
        if os_idle > CAMEO_MAX_OS_IDLE_S or self.active_bubble is not None:
            self.next_cameo_at = now + random.uniform(*CAMEO_RETRY_S)
            return
        started = self.start_cameo()
        self.next_cameo_at = now + random.uniform(*(CAMEO_INTERVAL_S if started else CAMEO_RETRY_S))

    def invite_cameo(self) -> None:
        """Menu: invite a guest now (separate cooldown from the automatic visits)."""
        self.record_activity()
        if not self.start_cameo(manual=True):
            self._toast(t("cameo_busy", self.lang), duration_ms=2500)

    def toggle_cameo(self) -> None:
        new_val = not self.settings.get("cameo_enabled", True)
        self.settings["cameo_enabled"] = new_val
        self.save_settings()
        self.build_menu()
        status = t("status_on", self.lang) if new_val else t("status_off", self.lang)
        self._toast(t("cameo_auto_status", self.lang, status=status), duration_ms=2500)

    def _toggle_auto_setting(self, key: str, label_key: str) -> None:
        self.settings[key] = not self.settings.get(key, True)
        self.save_settings()
        self.build_menu()
        status = t("status_on" if self.settings[key] else "status_off", self.lang)
        self._toast(f"{t(label_key, self.lang)}：{status}", duration_ms=2500)

    def toggle_daily_signature(self) -> None:
        self._toggle_auto_setting("daily_signature_enabled", "daily_signature_toggle")

    def toggle_festival_auto(self) -> None:
        self._toggle_auto_setting("festival_auto_enabled", "festival_auto_toggle")
        self._sync_festival_state()

    def toggle_stay_in_place(self) -> None:
        """Toggle whether pet stays fixed in current position or roams freely."""
        new_val = not self.settings.get("stay_in_place", False)
        self.settings["stay_in_place"] = new_val
        if new_val:
            self.target_roam_x = None
            if self.state == "walk":
                self._set_ambient("idle")
            self._toast(t("stay_in_place_notice_on", self.lang), duration_ms=2800)
        else:
            self.next_roam_time = time.time() + 5.0
            self._toast(t("stay_in_place_notice_off", self.lang), duration_ms=2800)
        self.save_settings()
        self.build_menu()

    def start_cameo(self, manual: bool = False, guest: str | None = None) -> bool:
        if (
            self.standby_overlay is not None
            or self.cameo_window is not None
            or not self.window.winfo_viewable()
            or self.cameo.run is not None
        ):
            return False
        chosen_guest = self.cameo.pick_guest(self.char_key, guest)
        try:
            # Cold decode and PhotoImage creation must precede both coordinator
            # duration and director started_at, or the first ENTER frame jumps.
            guest_lib = getattr(self, "guest_sprites", None) or self.sprites
            sprites = guest_lib.load_member(chosen_guest, self.root)
        except Exception:
            log.exception("cameo sprites failed; no visit started")
            return False
        self.cameo.lang = self.lang
        # The director works in 0..width of the host's monitor; shift back on render.
        area = self.desktop.work_area_for_point(self.x + self.width // 2, self.y + self.height // 2)
        self._cameo_work_area = area
        result = self.cameo.try_start(
            host=self.char_key,
            host_x=self.x - area.left,
            sprite_w=self.width,
            screen_w=area.width,
            ground_y=self.y,
            guest=chosen_guest,
            manual=manual,
            display_px=self.sprites.display_px,
        )
        log.info("cameo request -> %s %s", result.status.value,
                 result.reason.value if result.reason else "")
        run = self.cameo.run
        if run is None:
            return False
        try:
            self.cameo_window = CameoActorWindow(
                self.root,
                sprites,
                on_click=lambda: self._on_cameo_guest_clicked(run.guest),
                on_double_click=lambda: self._on_cameo_guest_double_clicked(run.guest),
                desktop=self.desktop,
                use_layered=getattr(self, "_use_ulw", None),
            )
            PandaPet._apply_cursor_to_panel(self, self.cameo_window)
        except Exception:
            log.exception("cameo window failed; cancelling visit")
            self.cameo.discard()
            return False
        self._cameo_phase = None
        self._cameo_t0 = time.monotonic()
        # A manual visit is the user's next interaction. Release the previous
        # click/double-click speech only after the guest window was created:
        # otherwise its USER priority drops both lower-priority cameo cues.
        # Keep SYSTEM notifications and their pending queue intact.
        current_speech = self.speech.current
        if manual and current_speech is not None and current_speech.priority is Priority.USER:
            self._dismiss_toast()
        self._cameo_loop()
        return True

    def _cameo_loop(self) -> None:
        self._cameo_after = None
        try:
            frame = self.cameo.update()
        except Exception:
            log.exception("cameo update failed")
            frame = None
        if frame is None or self.cameo_window is None:
            self._stop_cameo()
            return
        area = self._cameo_work_area
        frame = dataclasses.replace(frame, x=frame.x + area.left)
        elapsed_ms = (time.monotonic() - self._cameo_t0) * 1000
        if frame.phase is CameoPhase.DONE:
            self.cameo_window.render(frame, elapsed_ms, area)
            self._stop_cameo()
            return
        if frame.phase is CameoPhase.EXIT and self._cameo_phase is not CameoPhase.EXIT:
            # Guest is leaving: its speech bubble must not stay behind.
            cur = self.speech.current
            if cur is not None and cur.kind.startswith("cameo"):
                self._dismiss_toast()
        if frame.phase is CameoPhase.PERFORM and self._cameo_phase is not CameoPhase.PERFORM:
            # Guest has arrived: host turns to face it for the chat.
            self.face_override = 1 if frame.x >= self.x else -1
        elif frame.phase is CameoPhase.EXIT:
            self.face_override = None
        self._cameo_phase = frame.phase
        self.cameo_window.render(frame, elapsed_ms, area)
        for cue in frame.cues:
            self._speak_cameo_cue(cue, frame)
        self._cameo_after = self.window.after(CAMEO_TICK_MS, self._cameo_loop)

    def _speak_cameo_cue(self, cue: SpeechCue, frame: CameoFrame) -> None:
        run = self.cameo.run
        perform_ms = int(run.script.perform_s * 1000) if run else 10000
        avatar = CHARACTERS_DIR / cue.speaker / "idle_01.png"
        self._toast(
            cue.text,
            header=f"🐼 {self._member_short_names().get(cue.speaker, cue.speaker)}",
            speaker=cue.speaker,
            sub_badge=t("cameo_badge", self.lang) if cue.is_guest else "",
            icon_path=avatar if resource_exists(avatar, root=RES_ROOT) else None,
            # each line ends before the next one starts, so neither is dropped
            duration_ms=perform_ms // 2 - 400,
            priority=Priority.CAMEO,
            kind="cameo.guest" if cue.is_guest else "cameo.host",
            anchor=(int(frame.x), int(frame.y)) if cue.is_guest else None,
        )

    def _stop_cameo(self) -> None:
        """Tear down immediately (standby / tray / exit / finished)."""
        if self._cameo_after is not None:
            try:
                self.window.after_cancel(self._cameo_after)
            except Exception:
                pass
            self._cameo_after = None
        self.cameo.discard()
        if self.cameo_window is not None:
            self.cameo_window.destroy()
            self.cameo_window = None
        self._cameo_phase = None
        self.face_override = None

    def _on_cameo_guest_clicked(self, guest: str) -> None:
        self.record_activity()
        if not self.cameo_window:
            return
        gx = int(getattr(self.cameo_window, "last_x", self.x + 100))
        gy = int(getattr(self.cameo_window, "last_y", self.y))
        greetings = {
            "chorong": {
                "zh_TW": "隊長來探班囉！大家都有乖乖工作嗎？🐱✨",
                "ko": "롱리더가 출동했어요! 다들 열심히 일하고 계시죠?🐱✨",
                "en": "Leader Chorong checking in! Working hard today? 🐱✨",
            },
            "bomi": {
                "zh_TW": "嗷嗚！被你抓到了～我是來找炸醬麵跟小點心的！🍜🐶",
                "ko": "우와! 딱 걸렸네～ 맛있는 간식 찾으러 왔지요!🍜🐶",
                "en": "Woof! You caught me~ On a mission for tasty snacks! 🍜🐶",
            },
            "eunji": {
                "zh_TW": "哎唷！被你發現了～恩地來幫大家唱首應援歌！🎤💙",
                "ko": "어머나! 들켰네요～ 은지가 파워풀한 응원가 불러드릴게요!🎤💙",
                "en": "Oh my! You spotted me~ Eunji's here to belt out a cheer song! 🎤💙",
            },
            "namjoo": {
                "zh_TW": "登登！小太陽南珠閃亮登場～給你一口滿滿的維他命！☀️😋",
                "ko": "짜잔! 비타민 남주 깜짝 등장～ 행복 바이러스 듬뿍 받아요!☀️😋",
                "en": "Ta-da! Sunshine Namjoo here to recharge your vitamin energy! ☀️😋",
            },
            "hayoung": {
                "zh_TW": "嘻嘻！忙內夏榮正在實況串門子中～烤地瓜分你一口！🍠🎮",
                "ko": "히히! 막내 하영이의 깜짝 방송 중～ 군고구마 나눠먹어요!🍠🎮",
                "en": "Hehe! Maknae Hayoung live on cameo stream~ Sharing sweet potatoes! 🍠🎮",
            },
        }
        member_g = greetings.get(guest, greetings["chorong"])
        msg = member_g.get(self.lang, member_g["zh_TW"])
        avatar = CHARACTERS_DIR / guest / "idle_01.png"
        self._toast(
            msg,
            header=f"🐼 {self._member_short_names().get(guest, guest)}",
            speaker=guest,
            sub_badge=t("cameo_badge", self.lang),
            icon_path=avatar if resource_exists(avatar, root=RES_ROOT) else None,
            duration_ms=4000,
            priority=Priority.USER,
            kind="cameo.guest_click",
            anchor=(gx, gy),
        )

    def _on_cameo_guest_double_clicked(self, guest: str) -> None:
        self.record_activity()
        if not self.cameo_window:
            return
        gx = int(getattr(self.cameo_window, "last_x", self.x + 100))
        gy = int(getattr(self.cameo_window, "last_y", self.y))
        avatar = CHARACTERS_DIR / guest / "idle_01.png"
        cheers = {
            "zh_TW": "耶～最喜歡跟粉熊一起玩了！Apink 화이팅！🎉💖",
            "ko": "야호～ 판다들과 함께하는 게 제일 신나요! 에이핑크 화이팅！🎉💖",
            "en": "Yay~ Playing with Pandas is the best! Apink Hwaiting! 🎉💖",
        }
        msg = cheers.get(self.lang, cheers["zh_TW"])
        self._toast(
            msg,
            header=f"🐼 {self._member_short_names().get(guest, guest)}",
            speaker=guest,
            sub_badge=t("interaction_badge", self.lang),
            icon_path=avatar if resource_exists(avatar, root=RES_ROOT) else None,
            duration_ms=4500,
            priority=Priority.USER,
            kind="cameo.guest_double_click",
            anchor=(gx, gy),
        )
        self.trigger_cheer(cycles=2)

    # ── User birthday ────────────────────────────────────────────────────
    def open_birthday_dialog(self) -> None:
        self.record_activity()
        if hasattr(self, "birthday_dialog") and self.birthday_dialog:
            try:
                if self.birthday_dialog.win.winfo_exists():
                    self.birthday_dialog.win.lift()
                    return
            except Exception:
                pass
            self.birthday_dialog = None

        self.birthday_dialog = BirthdayDialog(
            self.window,
            current=read_birthday(self.settings.get("user_birthday")),
            nickname=self.settings.get("user_nickname") or DEFAULT_NICKNAME,
            on_save=self.set_user_birthday,
            lang=self.lang,
            member_key=self.char_key,
            on_close=self._on_birthday_dialog_closed,
        )
        PandaPet._apply_cursor_to_panel(self, self.birthday_dialog)

    def _on_birthday_dialog_closed(self) -> None:
        self.birthday_dialog = None

    def _today_fortune(self):
        from secrets import token_hex
        from app.fortune_reading import daily_fortune

        day = self.calendar.clock.now().date()
        salt = self.runtime.get("fortune_salt")
        new_salt = not isinstance(salt, str) or not salt
        if new_salt:
            salt = token_hex(16)
        saved = self.runtime.get("fortune_daily")
        reading, record = daily_fortune(day, salt, saved)
        if new_salt or saved != record:
            self.runtime["fortune_salt"] = salt
            self.runtime["fortune_daily"] = record
            self.save_settings()
        return reading

    def show_daily_fortune_bubble(self) -> None:
        from app.fortune_reading import daily_bubble_content

        self.record_activity()
        content = daily_bubble_content(self._today_fortune(), self.lang)
        self._toast(content.pop("message"), duration_ms=9000, kind="fortune.daily", speaker="eunji", **content)

    def open_fortune_room(self) -> None:
        """Open Eunji's animated Tarot Fortune Studio popup."""
        self.record_activity()
        existing = getattr(self, "fortune_dialog", None)
        if existing is not None:
            try:
                if existing.win.winfo_exists():
                    existing.set_language(self.lang)
                    PandaPet._apply_cursor_to_panel(self, existing)
                    existing.win.lift()
                    return
            except Exception:
                pass
            self.fortune_dialog = None
        self.fortune_dialog = FortuneRoomDialog(
            self.window,
            lang=self.lang,
            res_root=RES_ROOT,
            daily_provider=self._today_fortune,
            clock=self.calendar.clock.now,
            reduced_motion=self.settings.get("fortune_reduced_motion", False),
            on_motion_change=self._set_fortune_reduced_motion,
            on_summon_desktop=lambda: self.trigger_special_action(FORTUNE_LOVE_DESKTOP_ACTION, "eunji"),
            on_close=self._on_fortune_dialog_closed,
        )
        PandaPet._apply_cursor_to_panel(self, self.fortune_dialog)

    def _set_fortune_reduced_motion(self, enabled: bool) -> None:
        self.settings["fortune_reduced_motion"] = enabled
        self.save_settings()

    def set_user_birthday(self, month: int | None, day: int | None, nickname: str) -> None:
        self.settings["user_birthday"] = format_birthday(month, day)
        self.settings["user_nickname"] = nickname
        self.save_settings()
        self.calendar.set_user_birthday(month, day, nickname=nickname)
        if month and day:
            self._toast(t("birthday_saved", self.lang, month=month, day=day, nickname=nickname),
                        duration_ms=4000)
        else:
            self._toast(t("birthday_cleared", self.lang), duration_ms=2500)

    def _check_first_run_onboarding(self) -> None:
        """First-run onboarding popup to introduce pandas and invite user to enter nickname and birthday."""
        if self.settings.get("user_birthday"):
            return
        self.settings["onboarding_prompted"] = True
        self.save_settings()
        self.open_birthday_dialog()
        if self.birthday_dialog:
            prev_on_close = self.birthday_dialog.on_close

            def _on_first_run_birthday_closed() -> None:
                if prev_on_close:
                    prev_on_close()
                self._queue_first_run_tip()

            self.birthday_dialog.on_close = _on_first_run_birthday_closed

    def _queue_first_run_tip(self) -> None:
        """Once the welcome card is gone, say how to play; waits out the 'birthday saved' bubble."""
        self._loop_after["first_run_tip"] = self.window.after(FIRST_RUN_TIP_DELAY_MS, self._show_first_run_tip)

    def _show_first_run_tip(self) -> None:
        self._toast(t("first_run_tip", self.lang), duration_ms=9000)

    def _member_short_names(self) -> dict[str, str]:
        """Display names: '初瓏' for zh_TW, '초롱' for ko, 'Chorong' for en."""
        return {key: get_member_short_name(key, self.lang) for key in MEMBER_KEYS}

    def poll_calendar(self) -> None:
        """Submit due calendar events (L3); their bubble shows when they START."""
        self._sync_festival_state()
        for req in self.calendar.poll_all_due_events(self.char_key, lang=self.lang):
            if req.kind.startswith(("calendar.birthday", "calendar.anniversary", "calendar.holiday")):
                req = dataclasses.replace(req, queue_ttl_s=SPECIAL_DATE_QUEUE_TTL_S)
            if req.kind == ANNIVERSARY_419_KIND and self.settings.get("festival_auto_enabled", True):
                req = dataclasses.replace(req, duration_s=ANNIVERSARY_SCENE_S)   # as long as the photo
            result = self.coord.submit(req)
            log.info("calendar %s -> %s %s", req.kind, result.status.value,
                     result.reason.value if result.reason else "")

    def _show_event_speech(self, req: EventRequest) -> None:
        """Bubble for calendar events, shown in sync with their animation."""
        text = req.payload.get("text")
        if not text:
            return
        title = req.payload.get("title")
        if title:
            header = title if is_emoji(title[0]) else f"🎉 {title}"
        else:
            header = f"🐼 {self.get_active_name()}"
        self._toast(text, header=header, duration_ms=int(max(req.duration_s or 4, 4) * 1000) + 2000,
                    priority=Priority.SYSTEM, kind=req.kind)

    def tick_3s(self) -> None:
        """3-second periodic tick for Windows notification relay."""
        if self.settings.get("notify_relay", True):
            self.relay_notifications(self.notif_monitor.check_new_notifications())

        self._loop_after["tick_3s"] = self.window.after(3000, self.tick_3s)

    def _schedule_animate(self, delay_ms: int) -> None:
        if getattr(self, "_closing", False):
            return
        prev = self._loop_after.pop("animate", None)
        if prev is not None:
            try:
                self.window.after_cancel(prev)
            except Exception:
                pass
        self._loop_after["animate"] = self.window.after(delay_ms, self.animate)

    def animate(self) -> None:
        if getattr(self, "_closing", False):
            return
        if self._debug_paused:
            self._schedule_animate(100)
            return
        try:
            # Ends timed events (cheer durations) before choosing the frame.
            self.coord.tick()

            walking = self.state == "walk" and not self.dragging and self.standby_overlay is None
            use_ulw = hasattr(self, "_ulw_active") and self._ulw_active()
            token_fn = getattr(self, "_frame_token", None)
            if walking:
                previous = token_fn() if token_fn is not None else self.canvas.itemcget(self.image, "image")
            else:
                previous = None
            shown = self._visual_action()
            facing = self._visual_facing(shown)
            if (shown, self.char_key, facing) != (self._shown_action, self._shown_member, self._shown_facing):
                action_changed = (shown, self.char_key) != (self._shown_action, self._shown_member)
                self._shown_action, self._shown_member, self._shown_facing = shown, self.char_key, facing
                if shown is not None and action_changed:
                    self.frame_idx = 0                   # an exact action starts at its first frame
                self._sync_frame_box(shown, facing)
            show_canvas = getattr(self, "_show_canvas_frame", None)
            if show_canvas is not None:
                drawn_frame = show_canvas()
            else:
                drawn_frame = self.current_frame()
                self.canvas.itemconfigure(self.image, image=drawn_frame)
            if hasattr(self, "_present_layered_pet"):
                self._present_layered_pet()
            if walking:
                current = (
                    token_fn() if (use_ulw and token_fn is not None)
                    else ("" if drawn_frame is None else str(drawn_frame))
                )
            if walking and (current != previous or self.cycle_length() <= 1):
                direction = self.direction
                self.step_walk()
                if self.state == "walk" and self.direction != direction:
                    self._refresh_visual_appearance()
                    shown = self._shown_action
            self.frame_idx += 1

            if self.frame_idx % self.cycle_length() == 0:
                if self.state == "walk":
                    self.walk_cycles += 1
                    if self.walk_cycles % 2 == 0:
                        self.current_walk_action = "walk"
                    if self.walk_cycles >= 6 and self.target_roam_x is None:
                        self._set_ambient("idle")
                # Soft preempts (L3) and spontaneous actions (L1) switch here.
                self.coord.on_frame_boundary()
        except Exception:
            log.exception("animate failed")

        delay = {
            "idle": IDLE_MS,
            "walk": WALK_MS,
            "cheer": CHEER_MS,
            "sleep": SLEEP_MS,
        }.get(self.state, IDLE_MS)
        if self._shown_action is not None:
            loaded = self._action_frames(self.char_key, self._shown_action)
            if loaded is not None:
                delay = max(16, round(loaded[1]))
        if (
            self.coord.action == EUNJI_DOME_PERSONAL_ACTION
            and getattr(self, "_eunji_dome_effect_state", None) is not None
        ):
            _eid, t0, _outfits = self._eunji_dome_effect_state
            elapsed_ms = max(0.0, (time.monotonic() - t0) * 1000.0)
            rem_ms = DOME_CONCERT_FRAME_MS - (elapsed_ms % DOME_CONCERT_FRAME_MS)
            delay = max(16, min(DOME_CONCERT_FRAME_MS, round(rem_ms) + 2))

        self._schedule_animate(delay)

    def close(self) -> None:
        self._closing = True
        self._reset_restore_counters()
        self._standby_resume_pending = False
        self._save_on_close()
        if self.debug_panel is not None:
            self.debug_panel.close()
        self._stop_cameo()
        self.speech.clear()
        self._close_bubble_window()
        if hasattr(self, "hotkey_manager") and self.hotkey_manager:
            try:
                self.hotkey_manager.stop()
            except Exception:
                pass
        if hasattr(self, "tray") and self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.status_card:
            try:
                self.status_card.close()
            except Exception:
                pass
        if hasattr(self, "profile_card") and self.profile_card:
            try:
                self.profile_card.close()
            except Exception:
                pass
        self._close_food_panel()
        self._close_settings_panel()
        self._close_group_celebration()
        self._close_new_year_clock()
        self._close_pink_menu()
        self._close_notification_drawer()
        if hasattr(self, "birthday_dialog") and self.birthday_dialog:
            try:
                self.birthday_dialog.win.destroy()
            except Exception:
                pass
        fortune = getattr(self, "fortune_dialog", None)
        self.fortune_dialog = None
        if fortune is not None:
            try:
                fortune.close()
            except Exception:
                pass
        if self.standby_overlay:
            try:
                self.standby_overlay.win.destroy()
            except Exception:
                pass
        self._cancel_drag_cursor_after()
        widgets = getattr(self, "_after_widgets", {})
        for key, after_id in list(self._loop_after.items()):
            owner = widgets.pop(key, self.window)
            try:
                owner.after_cancel(after_id)
            except Exception:
                pass
        self._loop_after.clear()
        widgets.clear()
        self._shutdown_warmup_workers()
        surf = getattr(self, "layered_surface", None)
        if surf is not None:
            try:
                surf.close()
            except Exception:
                pass
        try:
            from app.cursor_manager import restore_system_cursor_global
            restore_system_cursor_global()
        except Exception:
            pass
        self.root.destroy()
        # Reclaim this lifetime's Tk garbage here, on the Tk thread, so no later
        # background thread's GC pass finalizes it (Tcl_AsyncDelete, 0x80000003).
        gc.collect()
        from app.cursor_manager import cleanup_cursor_files
        try:
            cleanup_cursor_files()
        except OSError:
            log.warning("Could not clean up temporary cursor files", exc_info=True)

    def _shutdown_warmup_workers(self) -> None:
        """Stop both warm-up workers and wait until their threads are gone (before root.destroy)."""
        managers = [m for m in (getattr(self, "_standby_warmup", None), getattr(self, "_desktop_warmup", None))
                    if m is not None]
        for manager in managers:
            try:
                manager.request_shutdown()
            except Exception:
                log.exception("warmup shutdown request failed")
        # Collect pending Tk garbage on this thread first: a worker that ran GC on it
        # would block marshalling Tcl calls to us while we sit in join().
        gc.collect()
        for manager in managers:
            try:
                manager.join()
            except Exception:
                log.exception("warmup join failed")

    def _save_on_close(self) -> None:
        """Keep satiety (with the decay since the last 60 s tick) and companion time."""
        self._decay_everyone(time.time())
        self.save_settings()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if not os.environ.get("PANDA_DATA_DIR"):
        try:
            _adopted = adopt_legacy_user_data(DATA_DIR, LEGACY_DATA_DIR)
        except OSError:
            log.warning("could not copy settings from %s", LEGACY_DATA_DIR, exc_info=True)
        else:
            if _adopted:
                log.info("copied %s from %s to %s", _adopted, LEGACY_DATA_DIR, DATA_DIR)
    _instance = acquire_single_instance(DATA_DIR)  # held for the life of the process
    if _instance is None:
        log.info("another pet already runs on %s; exiting", DATA_DIR)
        # debug_run.bat asks for a distinct code so its console explains the instant exit.
        sys.exit(int(os.environ.get("PANDA_DUPLICATE_EXIT_CODE", "0") or 0))
    PandaPet().run()
