"""speech_queue.py — Priority queue for speech bubbles (pure logic, headless).

Only one bubble is on screen at a time. Rules when a new bubble is offered:

- nothing showing            -> SHOW
- held (standby / suspended) -> QUEUED if priority >= SYSTEM, else DROPPED
- higher priority than shown -> SHOW (replaces). A replaced SYSTEM bubble is
                                requeued at the front with its remaining time
                                (at least MIN_REQUEUE_MS) so notifications and
                                reminders are not lost.
- USER while USER is shown   -> SHOW (latest user action wins)
- otherwise                  -> QUEUED if priority >= SYSTEM, else DROPPED
                                (spontaneous chatter is never worth waiting for)

The UI calls ``closed()`` when the bubble goes away and ``next_ready()`` from a
periodic tick to fetch the next queued bubble. Not thread-safe (Tk thread only).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

from .contracts import Clock, Priority, SystemClock

MIN_REQUEUE_MS = 2500
DEFAULT_MAX_QUEUE = 5


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    priority: Priority = Priority.USER
    duration_ms: int = 4200
    header: str = ""
    sub_badge: str = ""
    badge_text: str = ""
    icon_path: Optional[str] = None
    kind: str = ""
    ttl_s: float = 120.0           # max time waiting in the queue
    anchor: Optional[tuple[int, int]] = None  # sprite top-left to point at; None = host pet
    speaker: Optional[str] = None  # member key shown as the bubble title; None = host pet
    anchor_size: Optional[tuple[int, int]] = None  # (w, h) of the anchor target; None = host sprite
    origin: str = "pet"            # "profile_card": shown at the card, the pet is left alone


class SpeechDecision(str, Enum):
    SHOW = "show"
    QUEUED = "queued"
    DROPPED = "dropped"


@dataclass
class _Queued:
    request: SpeechRequest
    since: float
    seq: int


class SpeechQueue:
    def __init__(self, clock: Optional[Clock] = None, max_len: int = DEFAULT_MAX_QUEUE) -> None:
        self._clock: Clock = clock or SystemClock()
        self._max_len = max_len
        self._current: Optional[SpeechRequest] = None
        self._shown_at = 0.0
        self._queue: list[_Queued] = []
        self._seq = itertools.count()
        self._held = False

    @property
    def current(self) -> Optional[SpeechRequest]:
        return self._current

    @property
    def held(self) -> bool:
        return self._held

    def pending(self) -> tuple[SpeechRequest, ...]:
        return tuple(q.request for q in self._sorted())

    def offer(self, req: SpeechRequest) -> SpeechDecision:
        if self._held:
            return self._enqueue_or_drop(req)
        cur = self._current
        if cur is None:
            self._show(req)
            return SpeechDecision.SHOW
        if req.priority > cur.priority or (
            req.priority is Priority.USER and cur.priority is Priority.USER
        ) or (
            req.priority is Priority.CAMEO and cur.priority is Priority.CAMEO
        ):
            if cur.priority is Priority.SYSTEM:
                elapsed_ms = (self._clock.monotonic() - self._shown_at) * 1000
                remaining = max(MIN_REQUEUE_MS, int(cur.duration_ms - elapsed_ms))
                self._enqueue(replace(cur, duration_ms=remaining), front=True)
            self._show(req)
            return SpeechDecision.SHOW
        return self._enqueue_or_drop(req)

    def closed(self) -> None:
        """The visible bubble went away (timeout, click, programmatic dismiss)."""
        self._current = None

    def next_ready(self) -> Optional[SpeechRequest]:
        """Pop the next bubble to show, if the stage is free and not held."""
        if self._held or self._current is not None:
            return None
        now = self._clock.monotonic()
        self._queue = [q for q in self._queue if now - q.since <= q.request.ttl_s]
        if not self._queue:
            return None
        q = self._sorted()[0]
        self._queue.remove(q)
        self._show(q.request)
        return q.request

    def hold(self, held: bool) -> None:
        """Hold = nothing new is shown (standby / suspended); SYSTEM+ waits."""
        self._held = held
        if held:
            self._current = None

    def clear(self) -> None:
        self._current = None
        self._queue.clear()

    # internals
    def _show(self, req: SpeechRequest) -> None:
        self._current = req
        self._shown_at = self._clock.monotonic()

    def _enqueue_or_drop(self, req: SpeechRequest) -> SpeechDecision:
        if req.priority >= Priority.SYSTEM:
            self._enqueue(req)
            return SpeechDecision.QUEUED
        return SpeechDecision.DROPPED

    def _enqueue(self, req: SpeechRequest, front: bool = False) -> None:
        seq = (min((q.seq for q in self._queue), default=0) - 1) if front else next(self._seq)
        self._queue.append(_Queued(req, self._clock.monotonic(), seq))
        while len(self._queue) > self._max_len:
            # drop the least important, newest item
            self._queue.remove(self._sorted()[-1])

    def _sorted(self) -> list[_Queued]:
        return sorted(self._queue, key=lambda q: (-int(q.request.priority), q.seq))
