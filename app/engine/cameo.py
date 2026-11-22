"""cameo.py — Guest-member cameo director (pure logic, headless).

A cameo reserves the stage through an L2 coordinator request
(``CameoScript.to_request()``); this director then runs the guest's timeline:

    ENTER    trot in from the screen edge on the free side of the host
    PERFORM  stand next to the host and interact (~10 s); speech cues fire
    EXIT     wave, then trot back off-screen (normal), or — when the cameo is
             preempted / cancelled (drag, L3 event, mode change) — a quick
             0.8 s wave + trot-away with fade-out. Never vanishes instantly.
    DONE     window can be destroyed; the coordinator reservation is released

The UI calls ``update()`` from a fast timer (~40 ms) and renders the returned
``CameoFrame``; it forwards coordinator events to ``on_coord_event``.
Not thread-safe (Tk thread only).
"""
from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from .contracts import (
    MEMBER_KEYS,
    CameoActorSpec,
    CameoPhase,
    CameoScript,
    Clock,
    CoordinatorAPI,
    CoordinatorEvent,
    CoordinatorEventType,
    RejectReason,
    StagePosition,
    SubmitResult,
    SubmitStatus,
    SystemClock,
)

TROT_SPEED_PX_S = 150.0       # 1x gait speed, scaled with the visible pet
MIN_ENTER_S = 1.0
ENTER_FADE_S = 0.25
NORMAL_WAVE_S = 0.8           # goodbye wave before trotting off
INTERRUPT_WAVE_S = 0.3        # interrupted: short wave ...
INTERRUPT_TROT_S = 0.5        # ... then trot away while fading (total 0.8 s)
STAND_GAP_PX = 8              # gap between host and guest sprites
MANUAL_BUCKET = "cameo.manual"

# ── How the members address each other (real Apink usage) ───────────────
# Everyone calls Chorong "unnie"; Chorong (eldest/leader) calls the others
# "<name>呀". 93-line Bomi & Eunji address each other by given name.
# Namjoo (95) calls the three older members "unnie" and
# Hayoung "夏榮呀". Maknae Hayoung (96) calls all four "unnie".
_UNNIE = {
    "zh_TW": "{zh}姐姐", "ko": "{ko} 언니", "en": "{en} unnie",
}
_YA = {   # older -> younger, affectionate vocative
    "zh_TW": "{zh}呀", "ko": "{ko_voc}", "en": "{en}-ya",
}
_FRIEND = {  # same-age friends
    "zh_TW": "{zh}", "ko": "{ko_voc}", "en": "{en}",
}
_NAMES = {
    "chorong": dict(zh="初瓏", ko="초롱", ko_voc="초롱아", en="Chorong", zh_full="朴初瓏", ko_full="박초롱", en_full="Park Chorong"),
    "bomi":    dict(zh="普美", ko="보미", ko_voc="보미야", en="Bomi", zh_full="尹普美", ko_full="윤보미", en_full="Yoon Bomi"),
    "eunji":   dict(zh="恩地", ko="은지", ko_voc="은지야", en="Eunji", zh_full="鄭恩地", ko_full="정은지", en_full="Jeong Eunji"),
    "namjoo":  dict(zh="南珠", ko="남주", ko_voc="남주야", en="Namjoo", zh_full="金南珠", ko_full="김남주", en_full="Kim Namjoo"),
    "hayoung": dict(zh="夏榮", ko="하영", ko_voc="하영아", en="Hayoung", zh_full="吳夏榮", ko_full="오하영", en_full="Oh Hayoung"),
}
_AGE_ORDER = ("chorong", "bomi", "eunji", "namjoo", "hayoung")  # eldest -> maknae
_SAME_AGE = {frozenset({"bomi", "eunji"})}


def member_full_name(member: str, lang: str = "zh_TW") -> str:
    """Full name for titles: 朴初瓏 / 박초롱 / Park Chorong."""
    names = _NAMES.get(member)
    if names is None:
        return member
    key = {"ko": "ko_full", "en": "en_full"}.get(lang, "zh_full")
    return names[key]


def address(speaker: str, listener: str, lang: str = "zh_TW") -> str:
    """What ``speaker`` calls ``listener`` (vocative), following real Apink usage."""
    lang = lang if lang in _UNNIE else "zh_TW"
    names = _NAMES[listener]
    if frozenset({speaker, listener}) in _SAME_AGE:
        form = _FRIEND
    elif _AGE_ORDER.index(listener) < _AGE_ORDER.index(speaker):
        form = _UNNIE
    else:
        form = _YA
    return form[lang].format(**names)


# Visit dialogue (source_type = "stylized": original fan-made lines in each
# member's style — NOT real quotes; real quotes must carry a verified source).
# {call} = how the guest addresses the host; host reply uses {call} for the guest.
GUEST_LINES: Mapping[str, Mapping[str, str]] = {
    "chorong": {
        "zh_TW": "{call}～隊長來巡房囉！有沒有好好休息呀？🧹",
        "ko": "{call}~ 리더가 순찰 왔어! 잘 쉬고 있어? 🧹",
        "en": "{call}~ Leader on patrol! Are you taking breaks? 🧹",
    },
    "bomi": {
        "zh_TW": "{call}～嘿嘿，我帶零食來串門子了！要不要一起吃？🍗",
        "ko": "{call}~ 헤헤, 간식 들고 놀러 왔어! 같이 먹을래? 🍗",
        "en": "{call}~ Hehe, I brought snacks! Want to share? 🍗",
    },
    "eunji": {
        "zh_TW": "{call}～路過幫你唱一小段應援歌，加油加油！🎤",
        "ko": "{call}~ 지나가다 응원송 한 소절! 힘내! 🎤",
        "en": "{call}~ Just passing by with a little cheer song. Fighting! 🎤",
    },
    "namjoo": {
        "zh_TW": "{call}！我發現一家超好吃的甜點店，下次一起去～🍰",
        "ko": "{call}! 엄청 맛있는 디저트 가게 찾았어, 다음에 같이 가자~ 🍰",
        "en": "{call}! I found an amazing dessert place, let's go together~ 🍰",
    },
    "hayoung": {
        "zh_TW": "{call}～在幹嘛呀？我也要一起玩！🎮",
        "ko": "{call}~ 뭐 해요? 저도 같이 놀래요! 🎮",
        "en": "{call}~ What are you doing? Let me play too! 🎮",
    },
}
HOST_REPLY: Mapping[str, str] = {
    "zh_TW": "{call}！謝謝你來陪我～💕",
    "ko": "{call}! 놀러 와 줘서 고마워~ 💕",
    "en": "{call}! Thanks for visiting~ 💕",
}


@dataclass(frozen=True)
class SpeechCue:
    speaker: str        # member key
    text: str
    is_guest: bool


@dataclass(frozen=True)
class CameoFrame:
    """What the UI should render for the guest right now."""

    phase: CameoPhase
    member: str
    action: str         # registry / sprite action: "walk", "cheer", "idle"
    x: float
    y: float
    facing: int         # +1 right, -1 left
    alpha: float        # window opacity 0..1
    cues: tuple[SpeechCue, ...] = ()


@dataclass
class CameoRun:
    event_id: int
    script: CameoScript
    guest: str
    host: str
    y: float
    start_x: float
    stand_x: float
    exit_x: float
    started_at: float
    exit_started_at: Optional[float] = None
    exit_from_x: float = 0.0
    interrupted: bool = False
    finished: bool = False
    cues_fired: set = field(default_factory=set)
    trot_speed_px_s: float = TROT_SPEED_PX_S

    @property
    def faces_host(self) -> int:
        """Facing that looks at the host: the host is on the side away from the edge."""
        return -1 if self.exit_x > self.stand_x else 1


class CameoDirector:
    def __init__(
        self,
        coordinator: CoordinatorAPI,
        clock: Optional[Clock] = None,
        rng: Optional[random.Random] = None,
        members: Sequence[str] = MEMBER_KEYS,
        perform_s: float = 10.0,
    ) -> None:
        self._coord = coordinator
        self._clock: Clock = clock or SystemClock()
        self._rng = rng or random.Random()
        self._members = tuple(members)
        self._perform_s = perform_s
        self.run: Optional[CameoRun] = None
        self.lang = "zh_TW"

    # ── starting ─────────────────────────────────────────────────────────
    def pick_guest(self, host: str, guest: Optional[str] = None) -> str:
        """Choose an eligible guest before UI assets are loaded or time starts."""
        candidates = [m for m in self._members if m != host]
        return guest if guest in candidates else self._rng.choice(candidates)

    def try_start(
        self,
        host: str,
        host_x: float,
        sprite_w: float,
        screen_w: float,
        ground_y: float,
        guest: Optional[str] = None,
        manual: bool = False,
        *,
        display_px: float | None = None,
    ) -> SubmitResult:
        """Plan a cameo and ask the coordinator for the stage.

        ``manual`` (menu / debug) uses a separate cooldown bucket so it can be
        shown on demand without consuming the 30-minute automatic budget.
        """
        if self.run is not None:
            return SubmitResult(SubmitStatus.REJECTED, None, RejectReason.BUSY)
        guest = self.pick_guest(host, guest)

        # Stand on the side with room; enter from the screen edge on that side.
        room_right = host_x + 2 * sprite_w + STAND_GAP_PX <= screen_w
        if room_right:
            position, stand_x, edge_x = StagePosition.RIGHT_OF_HOST, host_x + sprite_w + STAND_GAP_PX, screen_w
        else:
            position, stand_x, edge_x = StagePosition.LEFT_OF_HOST, host_x - sprite_w - STAND_GAP_PX, -sprite_w
        stand_x = max(0.0, min(stand_x, screen_w - sprite_w))
        dist = abs(edge_x - stand_x)
        speed = TROT_SPEED_PX_S * max(0.25, (display_px if display_px is not None else sprite_w) / 192.0)
        # Let wide monitors take longer rather than speeding up the guest.
        enter_s = max(MIN_ENTER_S, dist / speed)
        exit_s = NORMAL_WAVE_S + enter_s

        script = CameoScript(
            cameo_id=f"visit.{guest}",
            actors=(CameoActorSpec(member=guest, role="guest", perform_action="cheer",
                                   enter_action="walk", exit_action="walk", position=position),),
            perform_s=self._perform_s,
            enter_s=enter_s,
            exit_s=exit_s,
        )
        req = script.to_request()
        if manual:
            req = dataclasses.replace(req, cooldown_key=MANUAL_BUCKET, cooldown_s=0.0)
        result = self._coord.submit(req)
        if result.status is SubmitStatus.STARTED and result.event_id is not None:
            self.run = CameoRun(
                event_id=result.event_id, script=script, guest=guest, host=host,
                y=ground_y, start_x=edge_x, stand_x=stand_x, exit_x=edge_x,
                started_at=self._clock.monotonic(), trot_speed_px_s=speed,
            )
        return result

    # ── coordinator feedback ─────────────────────────────────────────────
    def on_coord_event(self, ev: CoordinatorEvent) -> None:
        run = self.run
        if run is None or ev.event_id != run.event_id:
            return
        if ev.type in (CoordinatorEventType.PREEMPTED, CoordinatorEventType.CANCELLED):
            self._begin_exit(interrupted=True)
        elif ev.type is CoordinatorEventType.ENDED:
            self._begin_exit(interrupted=False)

    def abort(self) -> None:
        """Interrupt from the UI side (e.g. pet hidden): graceful exit."""
        if self.run is not None:
            self._begin_exit(interrupted=True)

    def discard(self) -> None:
        """Drop the cameo immediately (screen covered by standby / app closing)."""
        run, self.run = self.run, None
        if run is not None and not run.finished:
            run.finished = True
            self._coord.cancel(run.event_id, "discarded")

    # ── timeline ─────────────────────────────────────────────────────────
    def update(self) -> Optional[CameoFrame]:
        run = self.run
        if run is None:
            return None
        now = self._clock.monotonic()
        s = run.script
        t = now - run.started_at
        cues: list[SpeechCue] = []

        if run.exit_started_at is None and t >= s.enter_s + s.perform_s:
            self._begin_exit(interrupted=False)

        if run.exit_started_at is not None:
            return self._exit_frame(run, now)

        if t < s.enter_s:
            k = t / s.enter_s
            x = run.start_x + (run.stand_x - run.start_x) * k
            fade = min(1.0, max(0.0, t / ENTER_FADE_S))
            alpha = fade * fade * (3.0 - 2.0 * fade)
            return CameoFrame(CameoPhase.ENTER, run.guest, "walk", x, run.y,
                              self._toward(run.start_x, run.stand_x), alpha)

        # PERFORM: greet (cheer) first, then relax (idle) facing the host
        p = t - s.enter_s
        if "guest" not in run.cues_fired:
            run.cues_fired.add("guest")
            cues.append(SpeechCue(run.guest, self._guest_line(run.guest, run.host), True))
        if p >= s.perform_s / 2 and "host" not in run.cues_fired:
            run.cues_fired.add("host")
            reply = HOST_REPLY.get(self.lang, HOST_REPLY["zh_TW"])
            cues.append(SpeechCue(run.host, reply.format(call=address(run.host, run.guest, self.lang)), False))
        action = "cheer" if p < 2.0 or p >= s.perform_s - 1.5 else "idle"
        return CameoFrame(CameoPhase.PERFORM, run.guest, action, run.stand_x, run.y,
                          run.faces_host, 1.0, tuple(cues))

    # ── internals ────────────────────────────────────────────────────────
    def _begin_exit(self, interrupted: bool) -> None:
        run = self.run
        if run is None or run.exit_started_at is not None:
            return
        now = self._clock.monotonic()
        t = now - run.started_at
        if t < run.script.enter_s:
            k = max(0.0, t / run.script.enter_s)
            run.exit_from_x = run.start_x + (run.stand_x - run.start_x) * k
        else:
            run.exit_from_x = run.stand_x
        run.exit_started_at = now
        run.interrupted = interrupted

    def _exit_frame(self, run: CameoRun, now: float) -> CameoFrame:
        e = now - run.exit_started_at  # type: ignore[operator]
        wave_s = INTERRUPT_WAVE_S if run.interrupted else NORMAL_WAVE_S
        if run.interrupted:
            trot_s = INTERRUPT_TROT_S
            trot_dist = min(abs(run.exit_x - run.exit_from_x), run.trot_speed_px_s * trot_s)
        else:
            trot_dist = abs(run.exit_x - run.exit_from_x)
            trot_s = max(MIN_ENTER_S, trot_dist / run.trot_speed_px_s)
        direction = 1 if run.exit_x >= run.exit_from_x else -1

        if e < wave_s:  # wave goodbye toward the host
            return CameoFrame(CameoPhase.EXIT, run.guest, "cheer", run.exit_from_x, run.y, run.faces_host, 1.0)
        k = (e - wave_s) / trot_s
        if k >= 1.0:
            self._finish(run)
            return CameoFrame(CameoPhase.DONE, run.guest, "walk",
                              run.exit_from_x + direction * trot_dist, run.y, direction, 0.0)
        x = run.exit_from_x + direction * trot_dist * k
        alpha = 1.0 - k if run.interrupted else (1.0 if k < 0.7 else (1.0 - k) / 0.3)
        return CameoFrame(CameoPhase.EXIT, run.guest, "walk", x, run.y, direction, max(0.0, alpha))

    def _finish(self, run: CameoRun) -> None:
        if run.finished:
            return
        run.finished = True
        self.run = None
        # Release the stage early if the reservation is still running.
        self._coord.finish(run.event_id)

    def _guest_line(self, guest: str, host: str) -> str:
        lines = GUEST_LINES.get(guest, {})
        template = lines.get(self.lang) or lines.get("zh_TW", "")
        return template.format(call=address(guest, host, self.lang))

    @staticmethod
    def _toward(from_x: float, to_x: float) -> int:
        return 1 if to_x >= from_x else -1
