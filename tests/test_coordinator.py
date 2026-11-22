"""Headless tests for engine.coordinator (no Tk / PIL needed).

Run:  python -m unittest tests.test_coordinator -v
"""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import (  # noqa: E402
    ActorState,
    CameoActorSpec,
    CameoScript,
    CoordinatorAPI,
    CoordinatorEventType as Ev,
    EventRequest,
    GlobalMode,
    Priority,
    RejectReason,
    SubmitStatus,
)
from app.engine.coordinator import SOFT_PREEMPT_MAX_WAIT_S, StateCoordinator  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.wall = dt.datetime(2026, 11, 5, 10, 0, 0)

    def now(self) -> dt.datetime:
        return self.wall + dt.timedelta(seconds=self.t - 1000.0)

    def monotonic(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


def req(kind: str, prio: Priority, **kw) -> EventRequest:
    return EventRequest(kind=kind, priority=prio, **kw)


CAMEO = CameoScript(
    cameo_id="duo_test",
    actors=(CameoActorSpec(member="bomi", role="guest", perform_action="cheer"),),
)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.c = StateCoordinator(clock=self.clock, member="chorong")
        self.events: list = []
        self.c.subscribe(self.events.append)

    def types(self) -> list[Ev]:
        return [e.type for e in self.events]


class TestBasics(Base):
    def test_implements_protocol(self) -> None:
        self.assertIsInstance(self.c, CoordinatorAPI)

    def test_initial_snapshot(self) -> None:
        s = self.c.snapshot()
        self.assertEqual(s.mode, GlobalMode.NORMAL)
        self.assertEqual(s.actor_state, ActorState.IDLE)
        self.assertEqual(s.priority, Priority.AMBIENT)
        self.assertIsNone(s.active)

    def test_ambient_changes_state(self) -> None:
        self.c.set_ambient(ActorState.WALK)
        self.assertEqual(self.c.actor_state, ActorState.WALK)
        self.assertIn(Ev.STATE_CHANGED, self.types())
        r = self.c.submit(req("roam.sleep", Priority.AMBIENT, state=ActorState.SLEEP))
        self.assertEqual(r.status, SubmitStatus.STARTED)
        self.assertEqual(self.c.actor_state, ActorState.SLEEP)

    def test_duration_ends_and_returns_to_ambient(self) -> None:
        self.c.set_ambient(ActorState.WALK)
        r = self.c.submit(req("feed", Priority.USER, duration_s=2.0))
        self.assertEqual(r.status, SubmitStatus.STARTED)
        self.assertEqual(self.c.actor_state, ActorState.CHEER)
        self.clock.advance(1.9)
        self.c.tick()
        self.assertEqual(self.c.actor_state, ActorState.CHEER)
        self.clock.advance(0.2)
        self.c.tick()
        self.assertEqual(self.c.actor_state, ActorState.WALK)
        self.assertIn(Ev.ENDED, self.types())

    def test_finish_open_ended(self) -> None:
        r = self.c.submit(req("x", Priority.USER, duration_s=None))
        self.clock.advance(999)
        self.c.tick()
        self.assertIsNotNone(self.c.snapshot().active)
        self.assertTrue(self.c.finish(r.event_id))
        self.assertIsNone(self.c.snapshot().active)
        self.assertFalse(self.c.finish(r.event_id))


class TestPriority(Base):
    def test_system_soft_preempts_at_frame_boundary(self) -> None:
        self.c.set_ambient(ActorState.WALK)
        r = self.c.submit(req("birthday", Priority.SYSTEM, action="cake"))
        self.assertEqual(r.status, SubmitStatus.PENDING)
        self.assertEqual(self.c.actor_state, ActorState.WALK)
        self.c.on_frame_boundary()
        self.assertEqual(self.c.snapshot().active.event_id, r.event_id)
        self.assertEqual(self.c.action, "cake")

    def test_soft_preempt_safety_timeout(self) -> None:
        r = self.c.submit(req("chime", Priority.SYSTEM))
        self.c.tick()
        self.assertIsNone(self.c.snapshot().active)
        self.clock.advance(SOFT_PREEMPT_MAX_WAIT_S)
        self.c.tick()
        self.assertEqual(self.c.snapshot().active.event_id, r.event_id)

    def test_system_queues_behind_system_fifo(self) -> None:
        a = self.c.submit(req("a", Priority.SYSTEM, duration_s=1))
        self.c.on_frame_boundary()
        b = self.c.submit(req("b", Priority.SYSTEM, duration_s=1))
        c = self.c.submit(req("c", Priority.SYSTEM, duration_s=1))
        self.assertEqual((b.status, c.status), (SubmitStatus.QUEUED, SubmitStatus.QUEUED))
        self.assertEqual(self.c.snapshot().queue, (b.event_id, c.event_id))
        self.clock.advance(1)
        self.c.tick()
        self.assertEqual(self.c.snapshot().active.event_id, b.event_id)
        self.clock.advance(1)
        self.c.tick()
        self.assertEqual(self.c.snapshot().active.event_id, c.event_id)
        self.assertNotEqual(a.event_id, c.event_id)

    def test_system_preempts_spontaneous(self) -> None:
        s = self.c.submit(req("roam.run", Priority.SPONTANEOUS, state=ActorState.RUN, duration_s=5))
        self.c.on_frame_boundary()
        self.assertEqual(self.c.actor_state, ActorState.RUN)
        y = self.c.submit(req("water", Priority.SYSTEM))
        self.assertEqual(y.status, SubmitStatus.PENDING)
        self.c.on_frame_boundary()
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)
        pre = [e for e in self.events if e.type is Ev.PREEMPTED]
        self.assertEqual(pre[0].event_id, s.event_id)
        self.assertFalse(pre[0].requeued)

    def test_system_supersedes_pending_spontaneous(self) -> None:
        s = self.c.submit(req("roam.hop", Priority.SPONTANEOUS))
        self.assertEqual(s.status, SubmitStatus.PENDING)
        y = self.c.submit(req("water", Priority.SYSTEM))
        self.assertEqual(self.c.snapshot().pending_id, y.event_id)
        cancelled = [e.event_id for e in self.events if e.type is Ev.CANCELLED]
        self.assertIn(s.event_id, cancelled)

    def test_user_preempts_system_and_requeues_it(self) -> None:
        y = self.c.submit(req("birthday", Priority.SYSTEM, duration_s=3))
        self.c.on_frame_boundary()
        u = self.c.submit(req("click", Priority.USER, duration_s=1))
        self.assertEqual(self.c.snapshot().active.event_id, u.event_id)
        self.assertEqual(self.c.snapshot().queue, (y.event_id,))
        pre = [e for e in self.events if e.type is Ev.PREEMPTED][0]
        self.assertTrue(pre.requeued)
        self.clock.advance(1)
        self.c.tick()
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)

    def test_newer_user_replaces_user(self) -> None:
        a = self.c.submit(req("feed", Priority.USER))
        b = self.c.submit(req("click", Priority.USER))
        self.assertEqual(self.c.snapshot().active.event_id, b.event_id)
        self.assertIn(a.event_id, [e.event_id for e in self.events if e.type is Ev.PREEMPTED])

    def test_spontaneous_rejected_when_busy(self) -> None:
        self.c.submit(req("feed", Priority.USER))
        r = self.c.submit(req("roam.run", Priority.SPONTANEOUS))
        self.assertEqual((r.status, r.reason), (SubmitStatus.REJECTED, RejectReason.BUSY))

    def test_spontaneous_does_not_wake_sleep(self) -> None:
        self.c.set_ambient(ActorState.SLEEP)
        r = self.c.submit(req("roam.run", Priority.SPONTANEOUS, wakes_sleep=False))
        self.assertEqual(r.reason, RejectReason.STATE)
        y = self.c.submit(req("notify", Priority.SYSTEM))  # wakes_sleep default True
        self.assertTrue(y.accepted)


class TestUserInteraction(Base):
    def test_drag_interrupts_and_resumes(self) -> None:
        self.c.set_ambient(ActorState.WALK)
        y = self.c.submit(req("water", Priority.SYSTEM, duration_s=2))
        self.c.on_frame_boundary()
        self.c.begin_user_interaction("drag")
        s = self.c.snapshot()
        self.assertEqual(s.actor_state, ActorState.DRAGGED)
        self.assertEqual(s.priority, Priority.USER)
        self.assertEqual(s.queue, (y.event_id,))
        # system events wait while dragging
        z = self.c.submit(req("chime", Priority.SYSTEM))
        self.assertEqual(z.status, SubmitStatus.QUEUED)
        self.c.tick()
        self.assertEqual(self.c.actor_state, ActorState.DRAGGED)
        self.c.end_user_interaction()
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)
        self.assertEqual(self.c.snapshot().queue, (z.event_id,))

    def test_spontaneous_rejected_while_dragging(self) -> None:
        self.c.begin_user_interaction()
        r = self.c.submit(req("roam.run", Priority.SPONTANEOUS))
        self.assertEqual(r.reason, RejectReason.USER_ACTIVE)


class TestCameo(Base):
    def test_cameo_starts_and_sets_mode(self) -> None:
        r = self.c.submit(CAMEO.to_request())
        self.assertEqual(r.status, SubmitStatus.STARTED)
        self.assertEqual(self.c.mode, GlobalMode.CAMEO)
        self.assertIn(Ev.MODE_CHANGED, self.types())
        self.clock.advance(CAMEO.enter_s + CAMEO.perform_s + CAMEO.exit_s)
        self.c.tick()
        self.assertEqual(self.c.mode, GlobalMode.NORMAL)

    def test_cameo_cooldown_30min(self) -> None:
        self.c.submit(CAMEO.to_request())
        self.clock.advance(15)
        self.c.tick()
        r = self.c.submit(CAMEO.to_request())
        self.assertEqual(r.reason, RejectReason.COOLDOWN)
        self.clock.advance(1800)
        self.assertTrue(self.c.submit(CAMEO.to_request()).accepted)

    def test_cameo_requires_idle_or_walk(self) -> None:
        self.c.set_ambient(ActorState.SLEEP)
        self.assertEqual(self.c.submit(CAMEO.to_request()).reason, RejectReason.STATE)

    def test_cameo_not_in_standby(self) -> None:
        self.c.set_mode(GlobalMode.STANDBY)
        self.assertEqual(self.c.submit(CAMEO.to_request()).reason, RejectReason.MODE)

    def test_user_drag_abandons_cameo(self) -> None:
        r = self.c.submit(CAMEO.to_request())
        self.c.begin_user_interaction("drag")
        pre = [e for e in self.events if e.type is Ev.PREEMPTED]
        self.assertEqual(pre[0].event_id, r.event_id)
        self.assertFalse(pre[0].requeued)
        self.assertEqual(pre[0].request.payload["script"], CAMEO)
        self.c.end_user_interaction()
        self.assertIsNone(self.c.snapshot().active)

    def test_system_soft_preempts_cameo(self) -> None:
        r = self.c.submit(CAMEO.to_request())
        y = self.c.submit(req("birthday", Priority.SYSTEM))
        self.assertEqual(y.status, SubmitStatus.PENDING)
        self.c.on_frame_boundary()
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)
        self.assertEqual(self.c.mode, GlobalMode.NORMAL)
        self.assertIn(r.event_id, [e.event_id for e in self.events if e.type is Ev.PREEMPTED])

    def test_member_change_cancels_cameo(self) -> None:
        self.c.submit(CAMEO.to_request())
        self.c.set_member("bomi")
        self.assertIsNone(self.c.snapshot().active)
        self.assertEqual(self.c.snapshot().member, "bomi")

    def test_set_mode_cameo_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            self.c.set_mode(GlobalMode.CAMEO)


class TestModesAndLimits(Base):
    def test_standby_holds_system_until_normal(self) -> None:
        self.c.set_mode(GlobalMode.STANDBY)
        y = self.c.submit(req("birthday", Priority.SYSTEM))
        self.assertEqual(y.status, SubmitStatus.QUEUED)
        self.c.tick()
        self.assertIsNone(self.c.snapshot().active)
        self.c.set_mode(GlobalMode.NORMAL)
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)

    def test_entering_standby_requeues_active_system(self) -> None:
        y = self.c.submit(req("birthday", Priority.SYSTEM))
        self.c.on_frame_boundary()
        self.c.set_mode(GlobalMode.SUSPENDED)
        self.assertIsNone(self.c.snapshot().active)
        self.assertEqual(self.c.snapshot().queue, (y.event_id,))

    def test_user_rejected_outside_normal(self) -> None:
        self.c.set_mode(GlobalMode.STANDBY)
        self.assertEqual(self.c.submit(req("feed", Priority.USER)).reason, RejectReason.MODE)

    def test_queue_ttl_expires(self) -> None:
        self.c.set_mode(GlobalMode.STANDBY)
        y = self.c.submit(req("water", Priority.SYSTEM, queue_ttl_s=60))
        self.clock.advance(61)
        self.c.tick()
        self.assertEqual(self.c.snapshot().queue, ())
        cancelled = [e for e in self.events if e.type is Ev.CANCELLED]
        self.assertEqual((cancelled[0].event_id, cancelled[0].reason), (y.event_id, "expired"))

    def test_daily_limit_resets_next_day(self) -> None:
        r1 = self.c.submit(req("birthday", Priority.SYSTEM, daily_limit=1, duration_s=1))
        self.c.on_frame_boundary()
        self.clock.advance(2)
        self.c.tick()
        r2 = self.c.submit(req("birthday", Priority.SYSTEM, daily_limit=1))
        self.assertTrue(r1.accepted)
        self.assertEqual(r2.reason, RejectReason.DAILY_LIMIT)
        self.clock.advance(24 * 3600)
        self.assertTrue(self.c.submit(req("birthday", Priority.SYSTEM, daily_limit=1)).accepted)

    def test_requeued_daily_limited_event_resumes(self) -> None:
        y = self.c.submit(req("birthday", Priority.SYSTEM, daily_limit=1, duration_s=5))
        self.c.on_frame_boundary()
        self.c.submit(req("click", Priority.USER, duration_s=1))  # preempts + requeues
        self.clock.advance(1)
        self.c.tick()
        self.assertEqual(self.c.snapshot().active.event_id, y.event_id)
        # still counted exactly once for the day
        self.assertEqual(
            self.c.submit(req("birthday", Priority.SYSTEM, daily_limit=1)).reason,
            RejectReason.DAILY_LIMIT,
        )

    def test_cancel_queued(self) -> None:
        self.c.set_mode(GlobalMode.STANDBY)
        y = self.c.submit(req("water", Priority.SYSTEM))
        self.assertTrue(self.c.cancel(y.event_id))
        self.assertEqual(self.c.snapshot().queue, ())
        self.assertFalse(self.c.cancel(12345))


class TestListeners(Base):
    def test_listener_reentrancy_and_errors(self) -> None:
        calls = []

        def bad(_ev) -> None:
            raise RuntimeError("boom")

        def chain(ev) -> None:
            # start a follow-up USER event when the first one ends
            if ev.type is Ev.ENDED and ev.request.kind == "first":
                calls.append(self.c.submit(req("second", Priority.USER)))

        self.c.subscribe(bad)
        self.c.subscribe(chain)
        with self.assertLogs("app.engine.coordinator", level="ERROR"):
            r = self.c.submit(req("first", Priority.USER, duration_s=1))
            self.clock.advance(1)
            self.c.tick()
        self.assertTrue(r.accepted)
        self.assertEqual(self.c.snapshot().active.request.kind, "second")
        self.assertEqual(len(calls), 1)

    def test_unsubscribe(self) -> None:
        got = []
        unsub = self.c.subscribe(got.append)
        unsub()
        self.c.submit(req("x", Priority.USER))
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
