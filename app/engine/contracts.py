"""contracts.py — Shared interface contracts between engine modules and UI layers.

Owner: Claude Code (coordinator / cameo / calendar / UI integration).
Consumers: Codex (assets registry, debug panel, lifecycle clock, storage).

Rules
-----
- Pure data + Protocols only. No tkinter / PIL / pystray imports.
- Everything here is single-threaded by contract: callers running on other
  threads (pystray, hotkey listener) MUST marshal into the Tk thread
  (``root.after(0, ...)``) before touching a Coordinator.
- Changing a field name or enum value is a breaking change: bump
  ``CONTRACTS_VERSION`` and notify the other owner.

Sections
--------
1. Time            : Clock protocol (wall time + monotonic, debug offset aware)
2. State model     : GlobalMode x ActorState (two independent dimensions)
3. Arbitration     : Priority levels L0..L4, EventRequest, SubmitResult
4. Observation     : CoordinatorSnapshot, CoordinatorEvent, listener
5. Coordinator API : Protocol implemented by engine/coordinator.py
6. Assets          : AnimationSpec + AssetResolver protocol + registry JSON schema
7. Cameo           : CameoScript / CameoActorSpec / CameoPhase
"""
from __future__ import annotations

import datetime as _dt
import time as _time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

CONTRACTS_VERSION = 1

MEMBER_KEYS: tuple[str, ...] = ("chorong", "bomi", "eunji", "namjoo", "hayoung")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Time
# ─────────────────────────────────────────────────────────────────────────────
@runtime_checkable
class Clock(Protocol):
    """Time source. Debug panel / tests swap in an offset or fake clock.

    ``now()`` is wall-clock local time (calendar, birthdays, daily limits).
    ``monotonic()`` is seconds for durations / cooldowns; it must never go
    backwards, even when the debug panel shifts ``now()``.
    """

    def now(self) -> _dt.datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    """Default real-time clock."""

    def now(self) -> _dt.datetime:
        return _dt.datetime.now()

    def monotonic(self) -> float:
        return _time.monotonic()


# ─────────────────────────────────────────────────────────────────────────────
# 2. State model
# ─────────────────────────────────────────────────────────────────────────────
class GlobalMode(str, Enum):
    NORMAL = "normal"          # desktop companion running
    CAMEO = "cameo"            # guest member(s) on screen
    STANDBY = "standby"        # full-screen standby overlay shown
    SUSPENDED = "suspended"    # hidden (fullscreen app / user paused)


class ActorState(str, Enum):
    """Main pet action category. Exact animation is ``action`` (registry key)."""

    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    HOP = "hop"
    CHEER = "cheer"
    SPECIAL = "special"        # eat / dance / exercise / birthday ... see action
    SLEEP = "sleep"
    DRAGGED = "dragged"        # held by the mouse (user interaction)


# States the pet can be in while a cameo may start.
CAMEO_ALLOWED_STATES: frozenset[ActorState] = frozenset({ActorState.IDLE, ActorState.WALK})


# ─────────────────────────────────────────────────────────────────────────────
# 3. Arbitration
# ─────────────────────────────────────────────────────────────────────────────
class Priority(IntEnum):
    """PRD V2.2 Priority Arbiter Matrix.

    L4 USER        : immediate preempt (drag, context menu, click reactions)
    L3 SYSTEM      : soft preempt at next frame boundary (birthday, reminders,
                     notification relay, hourly chime); queued if busy with >= L3
    L2 CAMEO       : only when NORMAL + IDLE/WALK and nothing >= L1 active;
                     never queued; abandoned on any user interaction
    L1 SPONTANEOUS : random run/hop/stumble; only when nothing >= L1 active
    L0 AMBIENT     : base roam / idle / sleep (persistent background behaviour)
    """

    AMBIENT = 0
    SPONTANEOUS = 1
    CAMEO = 2
    SYSTEM = 3
    USER = 4


@dataclass(frozen=True)
class EventRequest:
    """A request to change what the pet is doing.

    kind          : stable identifier, e.g. "feed", "birthday.chorong",
                    "reminder.water", "notify.relay", "roam.run", "cameo.duo".
    priority      : arbitration level.
    state         : ActorState to enter while the event is active.
    action        : optional registry action key (e.g. "birthday_cake");
                    None = default animation for ``state``.
    duration_s    : active time; None = until ``Coordinator.finish(id)``.
                    Ignored for AMBIENT (ambient is persistent).
    cooldown_key  : cooldown / daily-limit bucket; defaults to ``kind``.
    cooldown_s    : min seconds between *starts* of this bucket (0 = none).
    daily_limit   : max starts per local calendar day (None = unlimited).
    queue_ttl_s   : how long an L3 request may wait in the queue.
    wakes_sleep   : if False and pet is SLEEP, the request is rejected.
    payload       : opaque data for the UI (speech text, food id, script...).
    source        : free text for logs / debug HUD ("calendar", "tray", ...).
    """

    kind: str
    priority: Priority
    state: ActorState = ActorState.CHEER
    action: Optional[str] = None
    duration_s: Optional[float] = 2.5
    cooldown_key: Optional[str] = None
    cooldown_s: float = 0.0
    daily_limit: Optional[int] = None
    queue_ttl_s: float = 300.0
    wakes_sleep: bool = True
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = ""

    @property
    def bucket(self) -> str:
        return self.cooldown_key or self.kind


class SubmitStatus(str, Enum):
    STARTED = "started"            # active immediately
    PENDING = "pending"            # soft preempt: starts at next frame boundary
    QUEUED = "queued"              # waiting behind an equal/higher event
    REJECTED = "rejected"          # not allowed now (see reason)


class RejectReason(str, Enum):
    COOLDOWN = "cooldown"
    DAILY_LIMIT = "daily_limit"
    MODE = "mode"                  # global mode forbids it (standby / suspended / cameo)
    BUSY = "busy"                  # higher/equal priority active and not queueable
    STATE = "state"                # actor state forbids it (sleep, dragged, not idle/walk)
    USER_ACTIVE = "user_active"    # user is interacting (dragging / menu)


@dataclass(frozen=True)
class SubmitResult:
    status: SubmitStatus
    event_id: Optional[int] = None
    reason: Optional[RejectReason] = None

    @property
    def accepted(self) -> bool:
        return self.status is not SubmitStatus.REJECTED


# ─────────────────────────────────────────────────────────────────────────────
# 4. Observation
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ActiveEvent:
    event_id: int
    request: EventRequest
    started_at: float              # monotonic seconds


@dataclass(frozen=True)
class CoordinatorSnapshot:
    """Read-only view for UI rendering and the debug HUD."""

    mode: GlobalMode
    actor_state: ActorState
    action: Optional[str]
    priority: Priority             # priority of what currently drives the actor
    active: Optional[ActiveEvent]
    ambient_state: ActorState
    user_interacting: bool
    pending_id: Optional[int]
    queue: tuple[int, ...]         # queued event ids, in start order
    member: str


class CoordinatorEventType(str, Enum):
    STARTED = "started"
    ENDED = "ended"                # finished normally (duration elapsed / finish())
    PREEMPTED = "preempted"        # interrupted; may be requeued (see requeued)
    CANCELLED = "cancelled"        # explicitly cancelled / mode change / expired
    QUEUED = "queued"
    REJECTED = "rejected"
    MODE_CHANGED = "mode_changed"
    STATE_CHANGED = "state_changed"


@dataclass(frozen=True)
class CoordinatorEvent:
    type: CoordinatorEventType
    snapshot: CoordinatorSnapshot
    event_id: Optional[int] = None
    request: Optional[EventRequest] = None
    reason: Optional[str] = None
    requeued: bool = False


CoordinatorListener = Callable[[CoordinatorEvent], None]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Coordinator API
# ─────────────────────────────────────────────────────────────────────────────
@runtime_checkable
class CoordinatorAPI(Protocol):
    """Implemented by ``engine.coordinator.StateCoordinator``.

    Driving loop (UI side):
      - call ``tick()`` from a periodic timer (e.g. every 100~250 ms);
      - call ``on_frame_boundary()`` when the current animation wraps to frame 0;
      - render from ``snapshot()`` or react to listener events.
    """

    # requests
    def submit(self, request: EventRequest) -> SubmitResult: ...
    def finish(self, event_id: int) -> bool: ...
    def cancel(self, event_id: int, reason: str = "cancelled") -> bool: ...
    def set_ambient(self, state: ActorState, action: Optional[str] = None) -> None: ...

    # user interaction (L4)
    def begin_user_interaction(self, kind: str = "drag") -> None: ...
    def end_user_interaction(self) -> None: ...

    # global mode
    def set_mode(self, mode: GlobalMode) -> None: ...
    def set_member(self, member: str) -> None: ...

    # time
    def tick(self) -> None: ...
    def on_frame_boundary(self) -> None: ...

    # observation
    def snapshot(self) -> CoordinatorSnapshot: ...
    def subscribe(self, listener: CoordinatorListener) -> Callable[[], None]: ...


# ─────────────────────────────────────────────────────────────────────────────
# 6. Assets
# ─────────────────────────────────────────────────────────────────────────────
BASE_ACTIONS: tuple[str, ...] = ("idle", "walk", "cheer", "sleep")
"""Every member MUST resolve these four; they terminate every fallback chain."""


@dataclass(frozen=True)
class AnimationSpec:
    """One playable animation, as resolved from the registry.

    frames      : paths relative to ``paths.resource_dir()``, in play order.
    anchor      : (x, y) pixel in the frame that touches the ground
                  (``bottom_center`` pre-computed from alpha bbox).
    canvas      : (w, h) of each frame in pixels.
    fallback    : asset_id to use if frames fail to load; chain must end in a
                  BASE_ACTIONS asset of the same member.
    runtime_ok  : False = excluded (preview sheets, suspicious crops). The
                  resolver MUST NOT return runtime_ok=False specs.
    """

    asset_id: str
    member: Optional[str]          # None for shared / multi-actor assets
    action: str
    frames: tuple[str, ...]
    fps: float = 7.0
    loop: bool = True
    anchor: tuple[int, int] = (96, 184)
    canvas: tuple[int, int] = (192, 192)
    fallback: Optional[str] = None
    interruptible: bool = True
    tags: tuple[str, ...] = ()
    runtime_ok: bool = True


@runtime_checkable
class AssetResolver(Protocol):
    """Implemented by ``engine.assets`` (Codex).

    ``resolve`` walks the fallback chain and returns None only if even the
    base action is missing. ``actions`` lists runtime_ok action keys.
    """

    def resolve(self, member: Optional[str], action: str) -> Optional[AnimationSpec]: ...
    def actions(self, member: Optional[str], tag: Optional[str] = None) -> tuple[str, ...]: ...


REGISTRY_SCHEMA_VERSION = 1
REGISTRY_JSON_EXAMPLE = """
{
  "schema_version": 1,
  "generated_by": "tools/build_asset_registry.py",
  "assets": {
    "eunji.walk": {
      "member": "eunji",
      "action": "walk",
      "frames": ["work/characters/eunji/walk_01.png", "..."],
      "fps": 7, "loop": true,
      "canvas": [192, 192], "anchor": [96, 184],
      "fallback": "eunji.idle",
      "interruptible": true,
      "tags": ["base", "locomotion"],
      "runtime_ok": true,
      "notes": ""
    },
    "shared.duo_bomi_eunji_banter_standoff": {
      "member": null, "actors": ["bomi", "eunji"],
      "action": "duo_banter_standoff",
      "frames": ["work/characters/shared/interactions_duo/duo_bomi_eunji_banter_standoff.png"],
      "fps": 1, "loop": true, "canvas": [256, 256], "anchor": [128, 248],
      "fallback": null, "tags": ["cameo", "duo"], "runtime_ok": true
    }
  }
}
"""
"""Illustrative only. The on-disk registry format (work/asset_registry.json,
built by tools/scan_asset_registry.py) is owned by the assets module; the
binding contract for runtime consumers is ``AssetResolver`` -> ``AnimationSpec``.
Readers must ignore unknown keys; ``actors`` only on multi-actor assets."""


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cameo
# ─────────────────────────────────────────────────────────────────────────────
class CameoPhase(str, Enum):
    ENTER = "enter"        # guest runs in from screen edge
    PERFORM = "perform"    # interaction loop (~10 s)
    EXIT = "exit"          # wave + run off (also used on interruption, ~0.8 s)
    DONE = "done"


class StagePosition(str, Enum):
    LEFT_OF_HOST = "left_of_host"
    RIGHT_OF_HOST = "right_of_host"
    SPECTATOR_CORNER = "spectator_corner"


@dataclass(frozen=True)
class CameoActorSpec:
    member: str
    role: str                          # "guest", "instigator", "peacemaker", "spectator"...
    perform_action: str                # registry action key while performing
    enter_action: str = "walk"
    exit_action: str = "walk"          # "wave_run" once assets exist
    position: StagePosition = StagePosition.RIGHT_OF_HOST


@dataclass(frozen=True)
class CameoScript:
    """Declarative cameo. Host = the current desktop member.

    host_action : what the host plays while the cameo performs (None = idle).
    shared_asset: optional multi-actor asset_id replacing per-actor windows
                  (e.g. duo images that already contain both pandas).
    """

    cameo_id: str
    actors: tuple[CameoActorSpec, ...]
    host_action: Optional[str] = None
    shared_asset: Optional[str] = None
    perform_s: float = 10.0
    enter_s: float = 1.5
    exit_s: float = 0.8
    cooldown_s: float = 1800.0         # "at most once per 30 minutes"
    requires_host: Optional[str] = None  # only when this member is the host
    weight: float = 1.0                # random selection weight

    def to_request(self) -> EventRequest:
        """Coordinator request that reserves the stage for the whole cameo."""
        return EventRequest(
            kind=f"cameo.{self.cameo_id}",
            priority=Priority.CAMEO,
            state=ActorState.IDLE,
            action=self.host_action,
            duration_s=self.enter_s + self.perform_s + self.exit_s,
            cooldown_key="cameo",
            cooldown_s=self.cooldown_s,
            wakes_sleep=False,
            payload={"script": self},
            source="cameo",
        )
