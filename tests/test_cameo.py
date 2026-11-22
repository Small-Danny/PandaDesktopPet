"""Headless tests for engine.cameo (CameoDirector + real StateCoordinator).

Run:  python -m unittest tests.test_cameo -v
"""
from __future__ import annotations

import datetime as dt
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.cameo import (  # noqa: E402
    INTERRUPT_TROT_S,
    INTERRUPT_WAVE_S,
    NORMAL_WAVE_S,
    CameoDirector,
)
from app.engine.contracts import (  # noqa: E402
    ActorState,
    CameoPhase,
    EventRequest,
    GlobalMode,
    Priority,
    RejectReason,
    SubmitStatus,
)
from app.engine.coordinator import StateCoordinator  # noqa: E402

SW, W, Y = 1920, 192, 800


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> dt.datetime:
        return dt.datetime(2026, 11, 5, 10) + dt.timedelta(seconds=self.t)

    def monotonic(self) -> float:
        return self.t


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.coord = StateCoordinator(clock=self.clock, member="chorong")
        self.d = CameoDirector(self.coord, clock=self.clock, rng=random.Random(1))
        self.coord.subscribe(self.d.on_coord_event)

    def start(self, host_x: float = 200, **kw):
        return self.d.try_start("chorong", host_x, W, SW, Y, **kw)

    def advance(self, s: float):
        self.clock.t += s
        self.coord.tick()
        return self.d.update()

    def run_to_done(self, step: float = 0.05, limit: float = 60.0):
        frames = []
        while self.d.run is not None and limit > 0:
            frames.append(self.advance(step))
            limit -= step
        return frames


class TestStart(Base):
    def test_wide_bomi_canvas_does_not_speed_up_the_guest(self):
        for width in (192, 222):
            clock = FakeClock()
            coord = StateCoordinator(clock=clock, member="bomi")
            director = CameoDirector(coord, clock=clock, rng=random.Random(1))
            director.try_start("bomi", 400, width, 1300, 800, display_px=192)
            self.assertEqual(director.run.trot_speed_px_s, 150)

    def test_dpi_scaled_speed_is_retained_for_exit(self):
        for scale in (1, 2):
            clock=FakeClock();coord=StateCoordinator(clock=clock,member='chorong')
            director=CameoDirector(coord,clock=clock,rng=random.Random(1))
            director.try_start('chorong',200*scale,192*scale,1920*scale,800*scale)
            run = director.run
            self.assertEqual(run.trot_speed_px_s, 150 * scale)
            self.assertAlmostEqual(run.script.enter_s, (run.start_x - run.stand_x) / (150 * scale))

    def test_wide_monitor_keeps_step_length_instead_of_accelerating(self):
        self.assertTrue(self.d.try_start("chorong", 200, W, 3840, Y).accepted)
        first = self.advance(0.1)
        second = self.advance(0.1)
        self.assertAlmostEqual(first.x - second.x, 15.0)

    def test_guest_is_never_host_and_stage_reserved(self) -> None:
        r = self.start()
        self.assertEqual(r.status, SubmitStatus.STARTED)
        self.assertNotEqual(self.d.run.guest, "chorong")
        self.assertEqual(self.coord.mode, GlobalMode.CAMEO)
        self.assertEqual(self.coord.actor_state, ActorState.IDLE)

    def test_side_with_room(self) -> None:
        self.start(host_x=200)
        self.assertGreater(self.d.run.stand_x, 200)          # right of host
        self.assertEqual(self.d.run.start_x, SW)              # enters from right edge
        self.d.run = None
        self.coord = StateCoordinator(clock=self.clock)
        self.d = CameoDirector(self.coord, clock=self.clock)
        self.d.try_start("bomi", SW - W, W, SW, Y)
        self.assertLess(self.d.run.stand_x, SW - W)           # no room right -> left
        self.assertEqual(self.d.run.start_x, -W)

    def test_rejected_when_busy_or_sleeping(self) -> None:
        self.coord.set_ambient(ActorState.SLEEP)
        self.assertEqual(self.start().reason, RejectReason.STATE)
        self.coord.set_ambient(ActorState.IDLE)
        self.coord.submit(EventRequest("feed", Priority.USER))
        self.assertEqual(self.start().reason, RejectReason.BUSY)
        self.assertIsNone(self.d.run)

    def test_30_min_cooldown_and_manual_bypass(self) -> None:
        self.start()
        self.run_to_done()
        self.assertEqual(self.start().reason, RejectReason.COOLDOWN)
        self.assertTrue(self.start(manual=True).accepted)

    def test_explicit_guest(self) -> None:
        self.start(guest="hayoung")
        self.assertEqual(self.d.run.guest, "hayoung")


class TestTimeline(Base):
    def test_full_normal_flow(self) -> None:
        self.start()
        run = self.d.run
        f = self.advance(0.01)
        self.assertEqual((f.phase, f.action, f.facing), (CameoPhase.ENTER, "walk", -1))
        f = self.advance(run.script.enter_s)
        self.assertEqual(f.phase, CameoPhase.PERFORM)
        self.assertEqual(f.x, run.stand_x)
        self.assertEqual(f.facing, -1)  # looks at the host on its left
        self.assertEqual([c.is_guest for c in f.cues], [True])
        f = self.advance(run.script.perform_s / 2)
        self.assertEqual([c.is_guest for c in f.cues], [False])
        from app.engine.cameo import address
        self.assertTrue(f.cues[0].text.startswith(address(run.host, run.guest)))
        frames = self.run_to_done()
        exits = [x for x in frames if x.phase is CameoPhase.EXIT]
        self.assertEqual(exits[0].action, "cheer")            # wave first
        self.assertEqual(exits[-1].action, "walk")            # then trot
        self.assertEqual(frames[-1].phase, CameoPhase.DONE)
        self.assertEqual(frames[-1].x, run.exit_x)             # really off-screen
        self.assertIsNone(self.coord.snapshot().active)       # stage released
        self.assertEqual(self.coord.mode, GlobalMode.NORMAL)

    def test_cues_fire_once(self) -> None:
        self.start()
        cues = [c for f in self.run_to_done(step=0.1) for c in f.cues]
        self.assertEqual(len(cues), 2)

    def test_drag_interrupt_graceful_exit(self) -> None:
        self.start()
        self.advance(self.d.run.script.enter_s + 1)
        stand = self.d.run.stand_x
        self.coord.begin_user_interaction("drag")
        f = self.d.update()
        self.assertEqual((f.phase, f.action), (CameoPhase.EXIT, "cheer"))
        self.assertEqual(f.alpha, 1.0)                         # never vanishes instantly
        frames = self.run_to_done(step=0.02)
        total = len(frames) * 0.02
        self.assertAlmostEqual(total, INTERRUPT_WAVE_S + INTERRUPT_TROT_S, delta=0.06)
        fading = [x.alpha for x in frames if x.phase is CameoPhase.EXIT and x.action == "walk"]
        self.assertTrue(all(a >= b for a, b in zip(fading, fading[1:])))
        self.assertGreater(frames[-1].x, stand)                # trotted away, toward edge

    def test_interrupt_during_enter_starts_from_current_x(self) -> None:
        self.start()
        run = self.d.run
        self.advance(run.script.enter_s / 2)
        self.coord.submit(EventRequest("birthday", Priority.SYSTEM))
        self.coord.on_frame_boundary()                         # L3 soft-preempts cameo
        self.assertTrue(run.interrupted)
        self.assertTrue(run.stand_x < run.exit_from_x < run.start_x)

    def test_l3_event_takes_stage_after_cameo(self) -> None:
        self.start()
        self.advance(3)
        r = self.coord.submit(EventRequest("birthday", Priority.SYSTEM))
        self.coord.on_frame_boundary()
        self.assertEqual(self.coord.snapshot().active.event_id, r.event_id)
        self.run_to_done()
        self.assertEqual(self.coord.snapshot().active.event_id, r.event_id)  # not finished by cameo

    def test_abort(self) -> None:
        self.start()
        self.advance(2)
        self.d.abort()
        frames = self.run_to_done(step=0.02)
        self.assertEqual(frames[-1].phase, CameoPhase.DONE)

    def test_lang(self) -> None:
        self.d.lang = "en"
        self.start(guest="bomi")
        cues = [c for f in self.run_to_done(step=0.1) for c in f.cues]
        self.assertIn("snacks", cues[0].text)
        self.assertTrue(cues[0].text.startswith("Chorong unnie"))
        self.assertTrue(cues[1].text.startswith("Bomi-ya"))

    def test_dialogue_uses_address_matrix(self) -> None:
        self.start(guest="hayoung")  # host chorong
        cues = [c for f in self.run_to_done(step=0.1) for c in f.cues]
        self.assertTrue(cues[0].text.startswith("初瓏姐姐"))
        self.assertTrue(cues[1].text.startswith("夏榮呀"))


class TestAddressMatrix(unittest.TestCase):
    def test_matrix(self) -> None:
        from app.engine.cameo import address
        cases = {
            # everyone -> Chorong: unnie
            ("bomi", "chorong"): "初瓏姐姐", ("hayoung", "chorong"): "初瓏姐姐",
            ("namjoo", "chorong"): "初瓏姐姐", ("eunji", "chorong"): "初瓏姐姐",
            # Chorong -> everyone: <name>呀
            ("chorong", "bomi"): "普美呀", ("chorong", "eunji"): "恩地呀",
            ("chorong", "namjoo"): "南珠呀", ("chorong", "hayoung"): "夏榮呀",
            # 93 line: same-age friends, given name
            ("eunji", "bomi"): "普美", ("bomi", "eunji"): "恩地",
            # Namjoo: unnie to the three older, 夏榮呀 to the maknae
            ("namjoo", "bomi"): "普美姐姐", ("namjoo", "eunji"): "恩地姐姐",
            ("namjoo", "hayoung"): "夏榮呀",
            # Hayoung: unnie to all four
            ("hayoung", "bomi"): "普美姐姐", ("hayoung", "eunji"): "恩地姐姐",
            ("hayoung", "namjoo"): "南珠姐姐",
        }
        for (speaker, listener), expected in cases.items():
            self.assertEqual(address(speaker, listener), expected, (speaker, listener))

    def test_korean_and_english(self) -> None:
        from app.engine.cameo import address
        self.assertEqual(address("hayoung", "chorong", "ko"), "초롱 언니")
        self.assertEqual(address("eunji", "bomi", "ko"), "보미야")
        self.assertEqual(address("bomi", "eunji", "ko"), "은지야")
        self.assertEqual(address("chorong", "hayoung", "ko"), "하영아")
        self.assertEqual(address("namjoo", "eunji", "en"), "Eunji unnie")
        self.assertEqual(address("eunji", "bomi", "en"), "Bomi")
        self.assertEqual(address("bomi", "eunji", "en"), "Eunji")


if __name__ == "__main__":
    unittest.main(verbosity=2)
