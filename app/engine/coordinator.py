"""coordinator.py — State Coordinator & Priority Arbiter (pure logic, headless).

Implements ``contracts.CoordinatorAPI``. One coordinator drives the *host*
pet (the member currently on the desktop). Cameo guests are reserved through
an L2 request; their own windows/animations are run by the cameo engine,
which listens for PREEMPTED/CANCELLED to play the graceful exit.

Arbitration rules (PRD V2.2 matrix)
-----------------------------------
L4 USER        start immediately; preempts anything below USER and any USER
               event. Preempted SYSTEM events are requeued at the front.
               ``begin_user_interaction`` (drag / menu) behaves the same and
               holds the actor in DRAGGED until ``end_user_interaction``.
L3 SYSTEM      soft preempt: becomes *pending* and starts at the next
               ``on_frame_boundary()`` (or after SOFT_PREEMPT_MAX_WAIT_S).
               Queued while a USER/SYSTEM event runs, the user is
               interacting, or the mode is STANDBY / SUSPENDED.
L2 CAMEO       starts only in NORMAL with the actor IDLE/WALK and nothing
               active / pending / queued; never queued. Mode reads CAMEO
               while it runs.
L1 SPONTANEOUS natural transition: pending until the next frame boundary;
               rejected when anything >= L1 is active, pending or queued.
L0 AMBIENT     persistent base state (``set_ambient``) shown when idle.

Cooldowns / daily limits are checked on submit *and* re-checked when a
queued event finally starts; they are recorded when an event starts.

Threading: not thread-safe by design — call from the Tk thread only.
Listener callbacks run after the triggering call has finished mutating
state, so listeners may safely call back into the coordinator.
"""
from __future__ import annotations

import datetime as _dt
import itertools
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from .contracts import (
    CAMEO_ALLOWED_STATES,
    ActiveEvent,
    ActorState,
    Clock,
    CoordinatorEvent,
    CoordinatorEventType as EvType,
    CoordinatorListener,
    CoordinatorSnapshot,
    EventRequest,
    GlobalMode,
    Priority,
    RejectReason,
    SubmitResult,
    SubmitStatus,
    SystemClock,
)

log = logging.getLogger(__name__)

SOFT_PREEMPT_MAX_WAIT_S = 1.0
"""Safety net: a pending soft preempt starts even if no frame boundary came."""

_EPS = 1e-6  # float slack for monotonic arithmetic


@dataclass
class _Waiting:
    event_id: int
    request: EventRequest
    since: float  # monotonic time it started waiting
    seq: int      # FIFO tie-breaker (lower = earlier)


class StateCoordinator:
    """Two-dimensional state holder (GlobalMode x ActorState) + arbiter."""

    def __init__(
        self,
        clock: Optional[Clock] = None,
        member: str = "chorong",
        ambient: ActorState = ActorState.IDLE,
    ) -> None:
        self._clock: Clock = clock or SystemClock()
        self._member = member
        self._base_mode = GlobalMode.NORMAL
        self._ambient_state = ambient
        self._ambient_action: Optional[str] = None
        self._active: Optional[ActiveEvent] = None
        self._pending: Optional[_Waiting] = None
        self._queue: list[_Waiting] = []
        self._user_kind: Optional[str] = None
        self._last_start: dict[str, float] = {}
        self._daily: dict[tuple[str, _dt.date], int] = {}
        self._ids = itertools.count(1)
        self._seq = itertools.count()
        self._counted: set[int] = set()  # event ids whose cooldown/daily use was recorded
        self._listeners: list[CoordinatorListener] = []
        self._outbox: list[CoordinatorEvent] = []
        self._depth = 0
        self._last_seen: tuple[GlobalMode, ActorState, Optional[str]] = self._visible()

    # ── observation ──────────────────────────────────────────────────────
    @property
    def mode(self) -> GlobalMode:
        if (
            self._base_mode is GlobalMode.NORMAL
            and self._active is not None
            and self._active.request.priority is Priority.CAMEO
        ):
            return GlobalMode.CAMEO
        return self._base_mode

    @property
    def actor_state(self) -> ActorState:
        if self._user_kind is not None:
            return ActorState.DRAGGED
        if self._active is not None:
            return self._active.request.state
        return self._ambient_state

    @property
    def action(self) -> Optional[str]:
        if self._user_kind is not None:
            return None
        if self._active is not None:
            return self._active.request.action
        return self._ambient_action

    def snapshot(self) -> CoordinatorSnapshot:
        if self._user_kind is not None:
            prio = Priority.USER
        elif self._active is not None:
            prio = self._active.request.priority
        else:
            prio = Priority.AMBIENT
        return CoordinatorSnapshot(
            mode=self.mode,
            actor_state=self.actor_state,
            action=self.action,
            priority=prio,
            active=self._active,
            ambient_state=self._ambient_state,
            user_interacting=self._user_kind is not None,
            pending_id=self._pending.event_id if self._pending else None,
            queue=tuple(w.event_id for w in self._sorted_queue()),
            member=self._member,
        )

    def subscribe(self, listener: CoordinatorListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsubscribe

    # ── requests ─────────────────────────────────────────────────────────
    def submit(self, request: EventRequest) -> SubmitResult:
        with self._op():
            return self._submit(request)

    def finish(self, event_id: int) -> bool:
        with self._op():
            if self._active is None or self._active.event_id != event_id:
                return False
            self._end_active(EvType.ENDED, "finished")
            self._advance()
            return True

    def cancel(self, event_id: int, reason: str = "cancelled") -> bool:
        with self._op():
            if self._active is not None and self._active.event_id == event_id:
                self._end_active(EvType.CANCELLED, reason)
                self._advance()
                return True
            if self._pending is not None and self._pending.event_id == event_id:
                w, self._pending = self._pending, None
                self._emit(EvType.CANCELLED, w.event_id, w.request, reason)
                return True
            for w in self._queue:
                if w.event_id == event_id:
                    self._queue.remove(w)
                    self._emit(EvType.CANCELLED, w.event_id, w.request, reason)
                    return True
            return False

    def set_ambient(self, state: ActorState, action: Optional[str] = None) -> None:
        if state is ActorState.DRAGGED:
            raise ValueError("DRAGGED is driven by begin/end_user_interaction")
        with self._op():
            self._ambient_state = state
            self._ambient_action = action

    # ── user interaction ─────────────────────────────────────────────────
    def begin_user_interaction(self, kind: str = "drag") -> None:
        with self._op():
            if self._user_kind is not None:
                self._user_kind = kind
                return
            self._user_kind = kind
            self._interrupt_all(reason=f"user:{kind}")

    def end_user_interaction(self) -> None:
        with self._op():
            if self._user_kind is None:
                return
            self._user_kind = None
            self._advance()

    # ── global mode / member ─────────────────────────────────────────────
    def set_mode(self, mode: GlobalMode) -> None:
        if mode is GlobalMode.CAMEO:
            raise ValueError("CAMEO mode is derived from an active cameo request")
        with self._op():
            if mode is self._base_mode:
                return
            self._base_mode = mode
            if mode is not GlobalMode.NORMAL:
                self._interrupt_all(reason=f"mode:{mode.value}")
            else:
                self._advance()

    def set_member(self, member: str) -> None:
        with self._op():
            if member == self._member:
                return
            self._member = member
            if self._active is not None and self._active.request.priority is Priority.CAMEO:
                self._end_active(EvType.CANCELLED, "member_changed")
                self._advance()

    # ── time ─────────────────────────────────────────────────────────────
    def tick(self) -> None:
        with self._op():
            now = self._clock.monotonic()
            a = self._active
            if a is not None and a.request.duration_s is not None:
                if now - a.started_at >= a.request.duration_s - _EPS:
                    self._end_active(EvType.ENDED, "duration")
            for w in list(self._queue):
                if now - w.since > w.request.queue_ttl_s:
                    self._queue.remove(w)
                    self._emit(EvType.CANCELLED, w.event_id, w.request, "expired")
            if self._pending is not None and now - self._pending.since >= SOFT_PREEMPT_MAX_WAIT_S:
                self._apply_pending()
            self._advance()

    def on_frame_boundary(self) -> None:
        with self._op():
            if self._pending is not None:
                self._apply_pending()

    # ── internals: arbitration ───────────────────────────────────────────
    def _submit(self, req: EventRequest) -> SubmitResult:
        reason = self._limit_reason(req)
        if reason is not None:
            return self._reject(req, reason)

        if req.priority is Priority.AMBIENT:
            self._ambient_state = req.state
            self._ambient_action = req.action
            return SubmitResult(SubmitStatus.STARTED)

        if (
            self.actor_state is ActorState.SLEEP
            and not req.wakes_sleep
            and req.priority < Priority.USER
        ):
            return self._reject(req, RejectReason.STATE)

        if req.priority is Priority.USER:
            if self._base_mode is not GlobalMode.NORMAL:
                return self._reject(req, RejectReason.MODE)
            event_id = next(self._ids)
            self._interrupt_all(reason=f"user:{req.kind}")
            self._start(event_id, req)
            return SubmitResult(SubmitStatus.STARTED, event_id)

        if req.priority is Priority.SYSTEM:
            event_id = next(self._ids)
            busy = (
                self._base_mode is not GlobalMode.NORMAL
                or self._user_kind is not None
                or (self._active is not None and self._active.request.priority >= Priority.SYSTEM)
                or (self._pending is not None and self._pending.request.priority >= Priority.SYSTEM)
                or bool(self._queue)
            )
            if busy:
                self._enqueue(_Waiting(event_id, req, self._clock.monotonic(), next(self._seq)))
                return SubmitResult(SubmitStatus.QUEUED, event_id)
            if self._pending is not None:  # lower-priority pending (spontaneous)
                w, self._pending = self._pending, None
                self._emit(EvType.CANCELLED, w.event_id, w.request, f"superseded:{req.kind}")
            self._pending = _Waiting(event_id, req, self._clock.monotonic(), next(self._seq))
            return SubmitResult(SubmitStatus.PENDING, event_id)

        # CAMEO / SPONTANEOUS: opportunistic, never queued
        if self._base_mode is not GlobalMode.NORMAL:
            return self._reject(req, RejectReason.MODE)
        if self._user_kind is not None:
            return self._reject(req, RejectReason.USER_ACTIVE)
        if self._active is not None or self._pending is not None or self._queue:
            return self._reject(req, RejectReason.BUSY)

        event_id = next(self._ids)
        if req.priority is Priority.CAMEO:
            if self._ambient_state not in CAMEO_ALLOWED_STATES:
                return self._reject(req, RejectReason.STATE)
            self._start(event_id, req)
            return SubmitResult(SubmitStatus.STARTED, event_id)

        self._pending = _Waiting(event_id, req, self._clock.monotonic(), next(self._seq))
        return SubmitResult(SubmitStatus.PENDING, event_id)

    def _limit_reason(self, req: EventRequest) -> Optional[RejectReason]:
        bucket = req.bucket
        if req.cooldown_s > 0 and bucket in self._last_start:
            if self._clock.monotonic() - self._last_start[bucket] < req.cooldown_s:
                return RejectReason.COOLDOWN
        if req.daily_limit is not None:
            if self._daily.get((bucket, self._clock.now().date()), 0) >= req.daily_limit:
                return RejectReason.DAILY_LIMIT
        return None

    def _interrupt_all(self, reason: str) -> None:
        """Clear active + pending for a higher authority (user / mode change).

        SYSTEM events are requeued at the front (and restart from the
        beginning later); everything else, including an older USER event,
        is dropped.
        """
        if self._pending is not None:
            w, self._pending = self._pending, None
            if w.request.priority is Priority.SYSTEM:
                self._enqueue(w, front=True)
            else:
                self._emit(EvType.CANCELLED, w.event_id, w.request, reason)
        a = self._active
        if a is not None:
            requeue = a.request.priority is Priority.SYSTEM
            self._active = None
            self._emit(EvType.PREEMPTED, a.event_id, a.request, reason, requeued=requeue)
            if requeue:
                self._enqueue(
                    _Waiting(a.event_id, a.request, self._clock.monotonic(), -1), front=True,
                )

    def _apply_pending(self) -> None:
        w, self._pending = self._pending, None
        if w is None:
            return
        a = self._active
        if a is not None:
            if a.request.priority >= w.request.priority:
                # Something at least as important started meanwhile.
                if w.request.priority is Priority.SYSTEM:
                    self._enqueue(w, front=True)
                else:
                    self._emit(EvType.CANCELLED, w.event_id, w.request, "superseded")
                return
            self._active = None
            self._emit(EvType.PREEMPTED, a.event_id, a.request, f"soft:{w.request.kind}")
        reason = self._restart_limit_reason(w)
        if reason is not None:
            self._emit(EvType.CANCELLED, w.event_id, w.request, reason.value)
            return
        self._start(w.event_id, w.request)

    def _advance(self) -> None:
        """Start the next queued event if the stage is free."""
        while (
            self._active is None
            and self._pending is None
            and self._user_kind is None
            and self._base_mode is GlobalMode.NORMAL
            and self._queue
        ):
            w = self._sorted_queue()[0]
            self._queue.remove(w)
            reason = self._restart_limit_reason(w)
            if reason is not None:
                self._emit(EvType.CANCELLED, w.event_id, w.request, reason.value)
                continue
            self._start(w.event_id, w.request)

    def _restart_limit_reason(self, w: _Waiting) -> Optional[RejectReason]:
        """Limits are re-checked for waiting events, but an event that already
        started once (preempted + requeued) was counted then and resumes freely."""
        if w.event_id in self._counted:
            return None
        return self._limit_reason(w.request)

    def _start(self, event_id: int, req: EventRequest) -> None:
        now = self._clock.monotonic()
        self._active = ActiveEvent(event_id, req, now)
        if event_id not in self._counted:
            self._counted.add(event_id)
            self._last_start[req.bucket] = now
            if req.daily_limit is not None:
                key = (req.bucket, self._clock.now().date())
                self._daily[key] = self._daily.get(key, 0) + 1
        self._emit(EvType.STARTED, event_id, req)

    def _end_active(self, type_: EvType, reason: str) -> None:
        a, self._active = self._active, None
        if a is not None:
            self._emit(type_, a.event_id, a.request, reason)

    def _enqueue(self, w: _Waiting, front: bool = False) -> None:
        if front:
            first = min((x.seq for x in self._queue), default=0)
            w = _Waiting(w.event_id, w.request, self._clock.monotonic(), first - 1)
        self._queue.append(w)
        self._emit(EvType.QUEUED, w.event_id, w.request, "front" if front else None)

    def _sorted_queue(self) -> list[_Waiting]:
        return sorted(self._queue, key=lambda w: (-int(w.request.priority), w.seq))

    def _reject(self, req: EventRequest, reason: RejectReason) -> SubmitResult:
        self._emit(EvType.REJECTED, None, req, reason.value)
        return SubmitResult(SubmitStatus.REJECTED, None, reason)

    # ── internals: events ────────────────────────────────────────────────
    def _visible(self) -> tuple[GlobalMode, ActorState, Optional[str]]:
        return (self.mode, self.actor_state, self.action)

    def _emit(
        self,
        type_: EvType,
        event_id: Optional[int],
        request: Optional[EventRequest],
        reason: Optional[str] = None,
        requeued: bool = False,
    ) -> None:
        self._outbox.append(
            CoordinatorEvent(type_, self.snapshot(), event_id, request, reason, requeued)
        )

    def _op(self) -> "_Op":
        return _Op(self)

    def _flush(self) -> None:
        mode, state, action = seen = self._visible()
        last_mode, last_state, last_action = self._last_seen
        if mode is not last_mode:
            self._emit(EvType.MODE_CHANGED, None, None, f"{last_mode.value}->{mode.value}")
        if state is not last_state or action != last_action:
            self._emit(EvType.STATE_CHANGED, None, None, f"{last_state.value}->{state.value}")
        self._last_seen = seen
        while self._outbox:
            batch, self._outbox = self._outbox, []
            for ev in batch:
                for listener in list(self._listeners):
                    try:
                        listener(ev)
                    except Exception:  # a broken listener must not stall arbitration
                        log.exception("coordinator listener failed on %s", ev.type)


class _Op:
    """Re-entrancy guard: flush listener events once the outermost call ends."""

    __slots__ = ("_c",)

    def __init__(self, c: StateCoordinator) -> None:
        self._c = c

    def __enter__(self) -> None:
        self._c._depth += 1

    def __exit__(self, *exc: object) -> None:
        self._c._depth -= 1
        if self._c._depth == 0 and exc[0] is None:
            self._c._flush()
