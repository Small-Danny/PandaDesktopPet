"""Headless tests for engine.speech_queue.

Run:  python -m unittest tests.test_speech_queue -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.contracts import Priority  # noqa: E402
from app.engine.speech_queue import (  # noqa: E402
    MIN_REQUEUE_MS,
    SpeechDecision as D,
    SpeechQueue,
    SpeechRequest,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self):  # pragma: no cover - unused
        raise NotImplementedError

    def monotonic(self) -> float:
        return self.t


def sp(text: str, prio: Priority, **kw) -> SpeechRequest:
    return SpeechRequest(text=text, priority=prio, **kw)


class TestSpeechQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.q = SpeechQueue(clock=self.clock)

    def test_show_when_free(self) -> None:
        self.assertEqual(self.q.offer(sp("hi", Priority.USER)), D.SHOW)
        self.assertEqual(self.q.current.text, "hi")

    def test_notification_not_overwritten_by_reminder(self) -> None:
        self.q.offer(sp("notif", Priority.SYSTEM))
        self.assertEqual(self.q.offer(sp("stretch", Priority.SYSTEM)), D.QUEUED)
        self.assertEqual(self.q.current.text, "notif")
        self.q.closed()
        self.assertEqual(self.q.next_ready().text, "stretch")

    def test_spontaneous_dropped_when_busy(self) -> None:
        self.q.offer(sp("notif", Priority.SYSTEM))
        self.assertEqual(self.q.offer(sp("chatter", Priority.SPONTANEOUS)), D.DROPPED)
        self.assertEqual(self.q.pending(), ())

    def test_system_replaces_spontaneous(self) -> None:
        self.q.offer(sp("chatter", Priority.SPONTANEOUS))
        self.assertEqual(self.q.offer(sp("notif", Priority.SYSTEM)), D.SHOW)
        self.assertEqual(self.q.pending(), ())  # chatter not requeued

    def test_user_replaces_system_and_requeues_remaining(self) -> None:
        self.q.offer(sp("notif", Priority.SYSTEM, duration_ms=7000))
        self.clock.t = 1.0
        self.assertEqual(self.q.offer(sp("feed", Priority.USER)), D.SHOW)
        (requeued,) = self.q.pending()
        self.assertEqual((requeued.text, requeued.duration_ms), ("notif", 6000))
        self.clock.t = 6.9
        self.q.offer(sp("feed2", Priority.USER))
        self.q.closed()
        # requeued notif had been shown ~0s more; min remaining enforced on re-preempt only
        self.assertEqual(self.q.next_ready().text, "notif")

    def test_requeue_minimum_duration(self) -> None:
        self.q.offer(sp("notif", Priority.SYSTEM, duration_ms=3000))
        self.clock.t = 2.9
        self.q.offer(sp("click", Priority.USER))
        self.assertEqual(self.q.pending()[0].duration_ms, MIN_REQUEUE_MS)

    def test_user_replaces_user(self) -> None:
        self.q.offer(sp("a", Priority.USER))
        self.assertEqual(self.q.offer(sp("b", Priority.USER)), D.SHOW)
        self.assertEqual(self.q.pending(), ())

    def test_hold_queues_system_drops_user(self) -> None:
        self.q.hold(True)
        self.assertIsNone(self.q.current)
        self.assertEqual(self.q.offer(sp("notif", Priority.SYSTEM)), D.QUEUED)
        self.assertEqual(self.q.offer(sp("chat", Priority.USER)), D.QUEUED)
        self.assertEqual(self.q.offer(sp("chatter", Priority.SPONTANEOUS)), D.DROPPED)
        self.assertIsNone(self.q.next_ready())
        self.q.hold(False)
        self.assertEqual(self.q.next_ready().text, "chat")  # USER outranks SYSTEM

    def test_ttl_expiry(self) -> None:
        self.q.offer(sp("a", Priority.USER))
        self.q.offer(sp("notif", Priority.SYSTEM, ttl_s=10))
        self.clock.t = 11
        self.q.closed()
        self.assertIsNone(self.q.next_ready())

    def test_max_len_drops_least_important(self) -> None:
        q = SpeechQueue(clock=self.clock, max_len=2)
        q.offer(sp("shown", Priority.USER))
        q.offer(sp("s1", Priority.SYSTEM))
        q.offer(sp("s2", Priority.SYSTEM))
        q.offer(sp("s3", Priority.SYSTEM))
        self.assertEqual([r.text for r in q.pending()], ["s1", "s2"])

    def test_next_ready_waits_for_close(self) -> None:
        self.q.offer(sp("a", Priority.SYSTEM))
        self.q.offer(sp("b", Priority.SYSTEM))
        self.assertIsNone(self.q.next_ready())
        self.q.closed()
        self.assertEqual(self.q.next_ready().text, "b")
        self.assertEqual(self.q.current.text, "b")

    def test_cameo_turn_taking(self) -> None:
        # Cameo guest line is shown
        self.assertEqual(self.q.offer(sp("guest line", Priority.CAMEO)), D.SHOW)
        self.assertEqual(self.q.current.text, "guest line")
        # Cameo host reply turn-takes without getting dropped
        self.assertEqual(self.q.offer(sp("host reply", Priority.CAMEO)), D.SHOW)
        self.assertEqual(self.q.current.text, "host reply")


if __name__ == "__main__":
    unittest.main(verbosity=2)
